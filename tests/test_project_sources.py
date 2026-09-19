"""Parse immutable local snapshots, never a moving source tree."""

import json
from dataclasses import asdict

import pytest

from formslang import blueprint
from formslang.project_discovery import discover_sources


def prepared(project_sources):
    access, descriptor, _ = project_sources
    return discover_sources(access, descriptor, checkpoint=lambda: None,
                            progress=lambda e: None, preview=False)


def parse(project_sources):
    from formslang.project_sources import parse_staged, stage_sources

    access, descriptor, _ = project_sources
    discovery = prepared(project_sources)
    with stage_sources(access, descriptor, discovery, checkpoint=lambda: None) as staged:
        return parse_staged(descriptor, discovery, staged,
                            checkpoint=lambda: None, progress=lambda e: None)


def test_parser_uses_staged_bytes(project_sources):
    from formslang.project_sources import parse_staged, stage_sources

    access, descriptor, xml = project_sources
    discovery = prepared(project_sources)
    original = xml.read_bytes()
    with stage_sources(access, descriptor, discovery, checkpoint=lambda: None) as staged:
        xml.write_text('<broken>', encoding='utf-8')
        parsed = parse_staged(descriptor, discovery, staged,
                              checkpoint=lambda: None, progress=lambda e: None)
        assert len(parsed.modules) == 1
        path = next(p for p in staged.paths.values() if p.suffix == '.xml')
        assert path.read_bytes() == original
    assert not path.exists()


def test_partial_failure_preserves_other_forms_and_database(project_sources):
    _, _, xml = project_sources
    for name in ('second.xml', 'third.xml'):
        (xml.parent / name).write_bytes(xml.read_bytes())
    (xml.parent / 'bad.xml').write_text('<broken>')
    result = parse(project_sources)
    assert len(result.modules) == 3
    assert set(result.database.tables) == {'ORDERS'}
    assert any(d.error_code == 'INVALID_XML' for d in result.diagnostics)
    assert all('formslang-stage-' not in m.source_path for m in result.modules)
    assert all(m.source_path.startswith('forms/') for m in result.modules)


def test_duplicate_db_object_is_excluded_not_last_writer_wins(project_sources):
    access, _, _ = project_sources
    db = access.source_roots[1]
    (db / 'duplicate.sql').write_text('create table orders (other varchar2(3));')
    result = parse(project_sources)
    assert 'ORDERS' not in result.database.tables
    errors = [d for d in result.diagnostics if d.error_code == 'DUPLICATE_DB_OBJECT']
    assert {d.relative_path for d in errors} == {'orders.sql', 'duplicate.sql'}


def test_package_spec_and_body_share_name_without_conflict(project_sources):
    access, _, _ = project_sources
    db = access.source_roots[1]
    (db / 'api.pks').write_text('create or replace package api as procedure save; end api; /')
    (db / 'api.pkb').write_text('create or replace package body api as procedure save is begin null; end; end api; /')
    result = parse(project_sources)
    assert set(result.database.package_specs) == {'API'}
    assert set(result.database.package_bodies) == {'API'}
    assert not any(d.error_code == 'DUPLICATE_DB_OBJECT' for d in result.diagnostics)
    assert result.database.package_bodies['API'].subprograms[0].source_file == 'database/api.pkb'


def test_unknown_sql_not_counted_as_success(project_sources):
    access, _, _ = project_sources
    (access.source_roots[1] / 'unsupported.trg').write_text('create trigger audit before insert on orders begin null; end; /')
    result = parse(project_sources)
    assert any(d.error_code == 'UNSUPPORTED_SQL' for d in result.diagnostics)


def test_repeat_staging_does_not_change_blueprint_content(project_sources):
    def payload():
        result = parse(project_sources)
        return blueprint.build(result.modules, source_keys=result.source_keys,
                               database_sources=result.database)
    first = payload()
    assert first == payload()
    assert str(project_sources[0].root.parent) not in json.dumps(first)


def test_missing_source_between_discovery_and_staging_is_structured(project_sources):
    from formslang.project_sources import parse_staged, stage_sources

    access, descriptor, xml = project_sources
    discovered = prepared(project_sources)
    xml.unlink()
    with stage_sources(access, descriptor, discovered, checkpoint=lambda: None) as staged:
        result = parse_staged(descriptor, discovered, staged,
                              checkpoint=lambda: None, progress=lambda e: None)
        assert len(result.modules) == 0
        assert any(d.error_code == 'SOURCE_MISSING' for d in result.diagnostics)
        assert any(e.status == 'missing' for e in staged.manifest)


def test_huge_source_not_read_into_parser(project_sources, monkeypatch):
    from formslang import project_sources as sources

    monkeypatch.setattr(sources, 'MAX_SOURCE_BYTES', 1)
    result = parse(project_sources)
    assert not result.modules
    assert any(d.error_code == 'SOURCE_TOO_LARGE' for d in result.diagnostics)


def test_parse_failure_does_not_leak_source_text(project_sources):
    _, _, xml = project_sources
    xml.write_text('<Module SECRET-password-content>')
    result = parse(project_sources)
    text = json.dumps([asdict(d) for d in result.diagnostics])
    assert 'SECRET-password-content' not in text
    assert str(xml.parent) not in text


def test_cancel_staging_cleans_owned_temporary_directory(project_sources):
    from formslang.project_sources import stage_sources

    access, descriptor, _ = project_sources
    discovered = prepared(project_sources)
    def cancelled():
        raise InterruptedError('cancel')
    with pytest.raises(InterruptedError), stage_sources(access, descriptor, discovered, checkpoint=cancelled):
        pytest.fail('cancelled staging should not yield')
    assert not list(access.root.glob('.formslang/runs/formslang-stage-*'))


def test_progress_has_per_phase_totals_and_real_order(project_sources):
    from formslang.project_sources import parse_staged, stage_sources

    access, descriptor, _ = project_sources
    discovered = prepared(project_sources)
    events = []
    with stage_sources(access, descriptor, discovered, checkpoint=lambda: None) as staged:
        parse_staged(descriptor, discovered, staged, checkpoint=lambda: None, progress=events.append)
    assert events[0]['phase'] == 'FORMS_PARSING'
    assert events[0]['total'] == 1
    for phase in ('FORMS_PARSING', 'DATABASE_PARSING'):
        phase_events = [e for e in events if e['phase'] == phase]
        assert phase_events[-1]['processed'] == phase_events[-1]['total'] == 1


def test_source_changed_between_hash_and_copy_is_not_parsed(project_sources, monkeypatch):
    from formslang import project_sources as sources

    access, descriptor, xml = project_sources
    discovered = prepared(project_sources)
    original = sources.fingerprint_sources
    def change_after_hash(*args, **kwargs):
        result = original(*args, **kwargs)
        if result[0].relative_path == 'orders.xml':
            xml.write_text('<changed/>')
        return result
    monkeypatch.setattr(sources, 'fingerprint_sources', change_after_hash)
    with sources.stage_sources(access, descriptor, discovered, checkpoint=lambda: None) as staged:
        result = sources.parse_staged(descriptor, discovered, staged,
                                      checkpoint=lambda: None, progress=lambda e: None)
        assert not result.modules
        assert any(d.error_code == 'SOURCE_CHANGED' for d in result.diagnostics)


def test_unsupported_only_estate_retains_gaps(project_sources):
    access, _, xml = project_sources
    xml.write_text('<Module><MenuModule /></Module>')
    (access.source_roots[1] / 'orders.sql').write_text('select 1 from dual;')
    result = parse(project_sources)
    assert not result.modules and not result.database.tables
    assert {d.error_code for d in result.diagnostics} == {'UNSUPPORTED_XML', 'UNSUPPORTED_SQL'}


def test_view_extension_parsed_by_existing_engine(project_sources):
    access, _, _ = project_sources
    (access.source_roots[1] / 'orders.vw').write_text('create view orders_v as select id from orders;')
    assert set(parse(project_sources).database.views) == {'ORDERS_V'}


def test_schema_ambiguity_is_conflict_not_false_ownership(project_sources):
    access, _, _ = project_sources
    (access.source_roots[1] / 'other.sql').write_text('create table other_schema.orders (code number);')
    result = parse(project_sources)
    assert not result.database.tables
    assert any(d.error_code == 'DUPLICATE_DB_OBJECT' for d in result.diagnostics)


def test_same_bytes_at_distinct_locations_are_disclosed(project_sources):
    _, _, xml = project_sources
    (xml.parent / 'copy.xml').write_bytes(xml.read_bytes())
    result = parse(project_sources)
    assert len(result.modules) == 2
    assert any(d.error_code == 'IDENTICAL_CONTENT' for d in result.diagnostics)
