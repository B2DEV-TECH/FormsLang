"""Exact input capture for the two WP-04 identity boundaries."""

import hashlib
from pathlib import Path

import pytest

from formslang import blueprint, blueprint_io, database
from formslang.project_service import ProjectService


def test_direct_snapshot_hashes_the_bytes_it_actually_stages(tmp_path):
    from formslang.blueprint_inputs import _InputSnapshot

    source = tmp_path / 'empty.sql'
    original = b'-- zero parsed objects\r\n'
    source.write_bytes(original)
    with _InputSnapshot() as snapshot:
        staged = snapshot.capture('database', 'empty.sql', source, 'database')
        source.write_bytes(b'-- changed after capture')
        assert staged.read_bytes() == original
        [entry] = snapshot.manifest
        assert entry.sha256 == hashlib.sha256(original).hexdigest()
        assert entry.size_bytes == len(original)
    assert not staged.exists()


def test_direct_load_binds_all_sources_and_uses_staged_form_bytes(tmp_path, sample_xml, monkeypatch):
    database = tmp_path / 'database'
    database.mkdir()
    (database / 'p.sql').write_text('CREATE PACKAGE S.P AS PROCEDURE X; END;', encoding='utf-8')
    empty = database / 'empty.sql'
    empty.write_bytes(b'-- zero objects')
    seen = []
    original_build = blueprint.build

    def capture(*args, **kwargs):
        seen.append(kwargs.pop('_database_identity_scope', None))
        return original_build(*args, **kwargs)

    monkeypatch.setattr(blueprint, 'build', capture)
    original_parse = blueprint_io.parse_xml
    original_bytes = sample_xml.read_bytes()

    def change_original_then_parse(path, **kwargs):
        assert Path(path) != sample_xml
        sample_xml.write_bytes(b'<broken>')
        return original_parse(path, **kwargs)

    monkeypatch.setattr(blueprint_io, 'parse_xml', change_original_then_parse)
    first = blueprint_io.load(sample_xml, tmp_path / 'out', database_sources=[database])
    assert first['failures'] == []
    assert seen[-1] is not None and seen[-1].basis == 'DIRECT_BLUEPRINT_BYTES'
    assert set(seen[-1].sources) == {
        'forms/' + sample_xml.name, 'database/p.sql', 'database/empty.sql'}
    identity = seen[-1].identity
    sample_xml.write_bytes(original_bytes)
    empty.write_bytes(b'-- changed zero-object source')
    blueprint_io.load(sample_xml, tmp_path / 'out', database_sources=[database])
    assert seen[-1].identity != identity


def test_project_build_receives_the_revision_which_will_be_published(project_sources, monkeypatch):
    access, descriptor, _ = project_sources
    service = ProjectService(access)
    service.create(descriptor.name, roots=descriptor.source_roots)
    seen = []
    original = blueprint.build

    def capture(*args, **kwargs):
        seen.append(kwargs.pop('_database_identity_scope', None))
        return original(*args, **kwargs)

    monkeypatch.setattr(blueprint, 'build', capture)
    try:
        result = service.analyze(expected_revision=None, expected_configuration=0)
        assert seen[-1] is not None
        assert seen[-1].basis == 'PROJECT_ANALYSIS_REVISION'
        assert seen[-1].identity == result['analysis_revision']
    finally:
        service.close()


def test_direct_missing_supplied_source_withholds_new_identity(tmp_path, sample_xml):
    source = tmp_path / 'p.sql'
    source.write_text('CREATE PACKAGE S.P AS PROCEDURE X; END;', encoding='utf-8')
    result = blueprint_io.load(sample_xml, tmp_path / 'out',
                               database_sources=[source, tmp_path / 'missing.sql'])
    assert result['database']['identity']['basis'] == 'UNAVAILABLE'
    assert not any(e['attributes'].get('analysis_identity') for e in result['entities'])
    assert result['database']['source_coverage']['summary']['rejected_or_unreadable'] == 1


@pytest.mark.parametrize('shape', ['path', 'str', 'list', 'tuple', 'iterator', 'directory', 'project'])
def test_direct_load_preserves_database_source_shapes(tmp_path, sample_xml, shape):
    root = tmp_path / 'sql'
    root.mkdir()
    source = root / 'p.sql'
    source.write_text('CREATE PACKAGE S.P AS PROCEDURE X; END;', encoding='utf-8')
    sources = {'path': source, 'str': str(source), 'list': [source], 'tuple': (source,),
               'iterator': iter([source]), 'directory': root,
               'project': database.parse_database_sources(source)}
    result = blueprint_io.load(sample_xml, tmp_path / 'out', database_sources=sources[shape])
    specs = [e for e in result['entities'] if e['type'] == 'PACKAGE_SPEC']
    members = [e for e in result['entities'] if e['type'] == 'PACKAGE_SUBPROGRAM']
    assert len(specs) == len(members) == 1
    if shape == 'project':
        assert result['database']['identity']['basis'] == 'UNAVAILABLE'
        assert not specs[0]['attributes'].get('analysis_identity')
        assert members[0]['name'] == 'P.X'
    else:
        assert result['database']['identity']['basis'] == 'DIRECT_BLUEPRINT_BYTES'
        assert members[0]['name'] == 'S.P.X'


@pytest.mark.parametrize('module_name', ['blueprint_inputs.py', 'blueprint_io.py'])
def test_direct_only_engine_change_does_not_invalidate_project_engine(tmp_path, sample_xml, monkeypatch, module_name):
    from formslang.project_manifest import engine_identity

    sql = tmp_path / 'p.sql'
    sql.write_text('CREATE PACKAGE S.P AS PROCEDURE X; END;', encoding='utf-8')
    def direct():
        return blueprint_io.load(sample_xml, tmp_path / 'out', database_sources=sql)['database']['identity']
    project_before = engine_identity()
    direct_before = direct()
    read_bytes = Path.read_bytes
    def changed_module(path):
        result = read_bytes(path)
        return result + b'\n# synthetic direct-engine change\n' if path.name == module_name else result
    monkeypatch.setattr(Path, 'read_bytes', changed_module)
    assert direct() != direct_before
    assert engine_identity() == project_before
