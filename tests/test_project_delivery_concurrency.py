"""Separate-connection mutations must not mix delivery snapshots or recreate state."""

# ruff: noqa: F811 -- shared pytest fixture
import io
import json
import sqlite3
import zipfile
from contextlib import closing

import pytest

from formslang.project_model import RevisionConflict
from tests.test_project_generation import generation_project, prepared  # noqa: F401


def append_legacy_review(service, finding, note):
    # Simulates the existing legacy writer, outside the project worker lock.
    with closing(sqlite3.connect(service._store.session.path)) as db:
        db.execute('''INSERT INTO blueprint_review
            (entity,revision,action,recommendation,target,comment,reviewer,
             coverage,coverage_evidence,finding_snapshot,decided_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
            (finding['entity'], finding['revision'], 'DEFER', finding['recommendation'], '', note,
             'SYNTHETIC_PRIVATE_REVIEWER', 'REQUIRES_REVIEW', '', '{}', '2026-09-21T00:00:00+00:00'))
        db.commit()


def test_review_between_capture_reads_conflicts(generation_project, monkeypatch):
    service = generation_project
    finding = service.assessment()['blueprint']['findings'][0]
    state = service.report_overview()
    original = service.assessment
    def interleaved(**kwargs):
        result = original(**kwargs)
        monkeypatch.setattr(service, 'assessment', original)
        append_legacy_review(service, finding, 'BETWEEN_CAPTURE_TRANSACTIONS')
        return result
    monkeypatch.setattr(service, 'assessment', interleaved)
    with pytest.raises(RevisionConflict):
        service.report_export('decisions', state['binding'], include_notes=True)


def test_review_during_render_preserves_snapshot(generation_project, monkeypatch):
    from formslang import project_report_render
    service = generation_project
    finding = service.assessment()['blueprint']['findings'][0]
    append_legacy_review(service, finding, 'BEFORE_CAPTURE')
    state = service.report_overview()
    original = project_report_render.build_files
    def interleaved(*args, **kwargs):
        append_legacy_review(service, finding, 'AFTER_CAPTURE')
        return original(*args, **kwargs)
    monkeypatch.setattr(project_report_render, 'build_files', interleaved)
    output = service.report_export('decisions', state['binding'], include_notes=True)
    revision = json.loads(output.body)['metadata']['review_revision']
    assert revision == state['binding']['review_revision']
    assert service.assessment()['review_revision'] > revision
    assert b'BEFORE_CAPTURE' in output.body and b'AFTER_CAPTURE' not in output.body
    assert b'SYNTHETIC_PRIVATE_REVIEWER' not in output.body


def test_corrupt_session_is_preserved_and_excluded(generation_project):
    service = generation_project
    detail = prepared(service)
    service.generate({**detail['binding'], 'scopes': [detail]})
    path = service._store.directory / service._store.module_sessions()[0]['relative_store']
    path.rename(path.with_suffix('.preserved'))
    path.write_bytes(b'SYNTHETIC_CORRUPT_DATABASE')
    output = service.report_export('package', service.report_overview()['binding'], include_artifacts=True)
    with zipfile.ZipFile(io.BytesIO(output.body)) as archive:
        assert 'ARTIFACT_CODE_UNAVAILABLE' in archive.read('manifest.json').decode()
        assert not any(name.startswith('apexlang/') for name in archive.namelist())
    assert path.read_bytes() == b'SYNTHETIC_CORRUPT_DATABASE'


def test_aggregate_artifact_size_is_checked_before_retaining_second(generation_project, monkeypatch):
    from formslang import project_reports
    service = generation_project
    detail = prepared(service)
    artifact = service.generate({**detail['binding'], 'scopes': [detail]})
    service.generate({**detail['binding'], 'scopes': [detail]})
    with zipfile.ZipFile(io.BytesIO(service.generation_download(artifact['artifact_id']))) as archive:
        size = sum(entry.file_size for entry in archive.infolist())
    monkeypatch.setattr(project_reports, 'MAX_DELIVERY_BYTES', size + 1)
    reports = project_reports.ProjectReportService(service)
    snapshot, assessment, _ = reports._capture()
    files, excluded = reports._artifacts(snapshot, assessment, True)
    assert sum(map(len, files.values())) == size
    assert len(excluded) == 1 and excluded[0]['reason'] == 'PACKAGE_SIZE_LIMIT'
