"""Delivery reads one persisted snapshot, never reanalyzes or fabricates output."""

# ruff: noqa: F811 -- imported pytest fixture

import csv
import hashlib
import io
import json
import zipfile
from dataclasses import replace

import pytest

from formslang.project_model import RevisionConflict, canonical_json, descriptor_to_dict
from tests.test_project_generation import generation_project, prepared  # noqa: F401


def package(service, **options):
    state = service.report_overview()
    return service.report_export('package', state['binding'], **options)


def rename_fixture(service, name):
    descriptor = replace(service.open(), name=name)
    with service._store._write() as db:
        db.execute('UPDATE modernization_project SET descriptor_json=? WHERE id=1',
                   (canonical_json(descriptor_to_dict(descriptor)),))
    service._store.sync_descriptor()
    return descriptor


def test_report_exports_are_stable_and_do_not_analyze(generation_project, monkeypatch):
    service = generation_project
    monkeypatch.setattr(service, 'analyze', lambda **kw: pytest.fail('Reports cannot analyze'))
    first = package(service)
    second = package(service)
    assert first.content_type == 'application/zip' and first.filename == 'modernization-package.zip'
    assert first.body == second.body
    with zipfile.ZipFile(io.BytesIO(first.body)) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    manifest = json.loads(files['manifest.json'])
    assert set(manifest['files']) == set(files) - {'manifest.json'}
    for name, expected in manifest['files'].items():
        assert hashlib.sha256(files[name]).hexdigest() == expected
    assert not any(name.endswith('.sql') or name.startswith('apexlang/') for name in files)
    assert 'generation_timestamp' in manifest and manifest['generation_timestamp'] == []
    assert manifest['assessment_timestamp'] == service.assessment()['analyzed_at']


def test_executive_escapes_labels_and_excludes_source_and_private_notes(generation_project):
    service = generation_project
    rename_fixture(service, '<img src=x onerror=alert(1)>')
    finding = service.review_queue()['rows'][0]
    detail = service.review_detail(finding['id'])
    service.review_decide(finding['id'], {**detail['binding'], 'action': 'DEFER',
                                         'rationale': 'PRIVATE_REVIEW_NOTE'})
    state = service.report_overview()
    output = service.report_export('executive', state['binding'], include_notes=True).body.decode()
    assert '<img src=x' not in output and '&lt;img' in output
    assert 'PRIVATE_REVIEW_NOTE' not in output
    assert str(service.access.root) not in output
    assert '<script' not in output
    assert 'Executive Summary' in output and 'Human Decisions Required' in output


def test_backlog_csv_neutralizes_formula_but_json_preserves_value(generation_project):
    service = generation_project
    descriptor = rename_fixture(service, ' =HYPERLINK("https://invalid")')
    state = service.report_overview()
    raw = json.loads(service.report_export('backlog-json', state['binding']).body)
    data = service.report_export('backlog-csv', state['binding']).body.decode('utf-8-sig')
    rows = list(csv.DictReader(io.StringIO(data)))
    assert raw['rows'][0]['Application'] == descriptor.name
    assert raw['metadata']['snapshot_revision'] == state['binding']['snapshot_revision']
    assert rows[0]['Application'] == "'" + descriptor.name
    assert 'Effort' not in rows[0] and 'Cost' not in rows[0]


def test_report_rejects_stale_review_snapshot(generation_project):
    service = generation_project
    state = service.report_overview()
    row = service.review_queue()['rows'][0]
    detail = service.review_detail(row['id'])
    service.review_decide(row['id'], {**detail['binding'], 'action': 'DEFER'})
    with pytest.raises(RevisionConflict):
        service.report_export('executive', state['binding'])


def test_stale_assessment_can_be_reported_without_current_claim(generation_project):
    service = generation_project
    source = service.access.source_roots[0] / 'forms/notice.xml'
    source.write_text(source.read_text() + '\n<!-- changed -->', encoding='utf-8')
    state = service.report_overview()
    assert state['freshness'] == 'STALE'
    output = service.report_export('executive', state['binding']).body.decode()
    assert 'STALE' in output and 'saved assessment' in output.lower()


def test_package_generated_scope_requires_opt_in_and_hashes(generation_project):
    service = generation_project
    detail = prepared(service)
    artifact = service.generate({**detail['binding'], 'scopes': [detail]})
    default = package(service)
    included = package(service, include_artifacts=True)
    with zipfile.ZipFile(io.BytesIO(default.body)) as archive:
        assert not any(name.startswith('apexlang/') for name in archive.namelist())
    with zipfile.ZipFile(io.BytesIO(included.body)) as archive:
        assert any(name.endswith('application.apx') for name in archive.namelist())
        manifest = json.loads(archive.read('manifest.json'))
        assert manifest['artifacts'][0]['artifact_id'] == artifact['artifact_id']
        assert manifest['artifacts'][0]['validation_status'] == 'Not Validated'
    root = service._store.directory / 'artifacts' / artifact['artifact_id'] / 'application.apex.zip'
    root.write_bytes(b'edited by human')
    with zipfile.ZipFile(io.BytesIO(package(service, include_artifacts=True).body)) as archive:
        assert not any(name.startswith('apexlang/') for name in archive.namelist())
        assert 'ARTIFACT_INTEGRITY' in archive.read('manifest.json').decode()
    assert root.read_bytes() == b'edited by human'


def test_notes_are_explicit_and_review_history_remains_separate(generation_project):
    service = generation_project
    row = service.review_queue()['rows'][0]
    detail = service.review_detail(row['id'])
    engine = detail['engine_recommendation'] if 'engine_recommendation' in detail else detail['item']['recommendation']
    service.review_decide(row['id'], {**detail['binding'], 'action': 'MODIFY', 'recommendation': 'PRESERVE',
                                    'rationale': 'PRIVATE_RATIONALE'})
    state = service.report_overview()
    default = service.report_export('decisions', state['binding']).body
    sensitive = service.report_export('decisions', state['binding'], include_notes=True).body
    assert b'PRIVATE_RATIONALE' not in default and b'PRIVATE_RATIONALE' in sensitive
    decisions = json.loads(sensitive)
    assert decisions['metadata']['human_notes_included']
    item = next(d for d in decisions['rows'] if d['finding_id'] == row['id'])
    assert item['engine_recommendation'] == engine and item['human_decision'] == 'PRESERVE'
    assert item['history'] and item['review_status'] == 'Changed'


def test_reports_do_not_export_raw_trigger_source(generation_project):
    service = generation_project
    source = service.access.source_roots[0] / 'forms/notice.xml'
    source.write_text(source.read_text().replace('</Block>', '''<Trigger Name="WHEN-VALIDATE-RECORD"
        TriggerText="BEGIN secret_api('SOURCE_BODY_PRIVATE_MARKER'); END;"/></Block>'''), encoding='utf-8')
    service.analyze(expected_revision=service.open().analysis_revision, expected_configuration=0)
    assert 'SOURCE_BODY_PRIVATE_MARKER' in json.dumps(service.assessment())
    with zipfile.ZipFile(io.BytesIO(package(service).body)) as archive:
        assert all(b'SOURCE_BODY_PRIVATE_MARKER' not in archive.read(name) for name in archive.namelist())


def test_source_change_during_report_rejects_current_claim(generation_project, monkeypatch):
    from formslang import project_report_render
    service = generation_project
    state = service.report_overview()
    original = project_report_render.build_files
    def change(snapshot, **options):
        result = original(snapshot, **options)
        source = service.access.source_roots[0] / 'forms/notice.xml'
        source.write_text(source.read_text() + '<!-- changed during export -->', encoding='utf-8')
        return result
    monkeypatch.setattr(project_report_render, 'build_files', change)
    with pytest.raises(RevisionConflict):
        service.report_export('package', state['binding'])


def test_foreign_project_binding_cannot_export(generation_project):
    service = generation_project
    state = service.report_overview()
    with pytest.raises(RevisionConflict):
        service.report_export('package', {**state['binding'], 'project_id': '0' * 32})


def test_missing_module_session_is_excluded_without_recreation(generation_project):
    service = generation_project
    detail = prepared(service)
    service.generate({**detail['binding'], 'scopes': [detail]})
    session = service._store.directory / service._store.module_sessions()[0]['relative_store']
    session.unlink()
    result = package(service, include_artifacts=True)
    assert not session.exists()
    with zipfile.ZipFile(io.BytesIO(result.body)) as archive:
        assert 'ARTIFACT_CODE_UNAVAILABLE' in archive.read('manifest.json').decode()


def test_module_session_directory_is_disclosed_not_opened(generation_project):
    service = generation_project
    detail = prepared(service)
    service.generate({**detail['binding'], 'scopes': [detail]})
    session = service._store.directory / service._store.module_sessions()[0]['relative_store']
    session.unlink()
    session.mkdir()
    with zipfile.ZipFile(io.BytesIO(package(service, include_artifacts=True).body)) as archive:
        assert 'ARTIFACT_CODE_UNAVAILABLE' in archive.read('manifest.json').decode()
    assert session.is_dir()


def test_standalone_sensitive_exports_identify_snapshot(generation_project):
    service = generation_project
    state = service.report_overview()
    for kind in ('decisions', 'backlog-json', 'backlog-csv'):
        result = service.report_export(kind, state['binding'], include_notes=True)
        assert '-sensitive.' in result.filename
        if kind != 'backlog-csv':
            metadata = json.loads(result.body)['metadata']
            assert metadata['human_notes_included']
            assert metadata['snapshot_revision'] == state['binding']['snapshot_revision']
        else:
            rows = list(csv.DictReader(io.StringIO(result.body.decode('utf-8-sig'))))
            assert rows[0]['Snapshot Revision'] == state['binding']['snapshot_revision']
            assert rows[0]['Sensitivity']


def test_read_only_session_never_creates_or_writes(tmp_path):
    import sqlite3
    from contextlib import closing

    from formslang.store import Store
    path = tmp_path / 'missing.sqlite'
    with pytest.raises(sqlite3.OperationalError):
        Store(path, read_only=True)
    assert not path.exists()
    with closing(Store(path)):
        pass
    with closing(Store(path, read_only=True)) as session, pytest.raises(sqlite3.OperationalError, match='readonly'):
        session.db.execute('CREATE TABLE unauthorized (id INTEGER)')


@pytest.mark.parametrize('prefix', [' ', '\t', '\r', '\n', '\ufeff'])
def test_csv_formula_prefixes(prefix):
    from formslang.project_report_render import csv_bytes
    value = prefix + '=1+1'
    output = csv_bytes([{'Value': value}], ['Value']).decode('utf-8-sig')
    assert next(iter(csv.DictReader(io.StringIO(output))))['Value'] == "'" + value


def test_csv_uses_portable_record_terminators_and_quotes_embedded_cr():
    from formslang.project_report_render import csv_bytes
    output = csv_bytes([{'Value': '\r=1+1'}], ['Value']).decode('utf-8-sig')
    assert output == 'Value\r\n"\'\r=1+1"\r\n'


def test_report_metadata_does_not_disclose_host_paths(generation_project):
    service = generation_project
    rename_fixture(service, r'Client C:\private\customer-passwords')
    with zipfile.ZipFile(io.BytesIO(package(service).body)) as archive:
        assert all(b'customer-passwords' not in archive.read(name) for name in archive.namelist())


def test_duplicated_predicate_literals_stay_in_authorized_evidence(generation_project):
    service = generation_project
    source = service.access.source_roots[0] / 'forms/notice.xml'
    source.write_text(source.read_text().replace('</Block>', '''<Trigger Name="WHEN-VALIDATE-RECORD"
        TriggerText="BEGIN IF :INFO.PASSWORD IN ('SYNTHETIC_SECRET_ONE','SYNTHETIC_SECRET_TWO') THEN NULL; END IF; END;"/></Block>'''), encoding='utf-8')
    (source.parent / 'auth.sql').write_text('''CREATE OR REPLACE PACKAGE BODY auth_api AS
      FUNCTION allowed(p_password VARCHAR2) RETURN BOOLEAN IS BEGIN
      RETURN p_password IN ('SYNTHETIC_SECRET_ONE','SYNTHETIC_SECRET_TWO'); END;
      END auth_api; /''', encoding='utf-8')
    service.analyze(expected_revision=service.open().analysis_revision, expected_configuration=0)
    reasons = [finding['reason'] for finding in service.assessment()['blueprint']['findings']]
    assert any('SYNTHETIC_SECRET_ONE' in reason for reason in reasons), reasons
    with zipfile.ZipFile(io.BytesIO(package(service).body)) as archive:
        for name in archive.namelist():
            assert b'SYNTHETIC_SECRET_ONE' not in archive.read(name), name


def test_visual_figures_do_not_carry_host_or_url_literals(generation_project):
    service = generation_project
    source = service.access.source_roots[0] / 'forms/notice.xml'
    source.write_text(source.read_text().replace('</Block>', '''<Trigger Name="WHEN-NEW-FORM-INSTANCE"
        TriggerText="BEGIN HOST('ping private-host.example.invalid'); WEB.SHOW_DOCUMENT('https://private-portal.example.invalid/x', '_blank'); END;"/></Block>'''), encoding='utf-8')
    service.analyze(expected_revision=service.open().analysis_revision, expected_configuration=0)
    # The authorized local map may name the integration target; delivery must not.
    local = json.dumps(service.system_map(view='ESTATE'))
    assert 'private-portal.example.invalid' in local or 'private-host.example.invalid' in local
    state = service.report_overview()
    executive = service.report_export('executive', state['binding']).body
    technical = service.report_export('technical', state['binding']).body
    assert b'<figure' in executive and b'Integration target (literal omitted' in executive
    with zipfile.ZipFile(io.BytesIO(package(service).body)) as archive:
        members = [archive.read(name) for name in archive.namelist()] + [name.encode() for name in archive.namelist()]
    for body in (executive, technical, *members):
        assert b'private-host.example.invalid' not in body and b'private-portal.example.invalid' not in body
