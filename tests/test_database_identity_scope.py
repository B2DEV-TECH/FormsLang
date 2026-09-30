"""Private WP-04 namespace contract, independent of byte-capture integration."""

import hashlib
from dataclasses import replace

import pytest

from formslang import database_identity
from formslang.project_manifest import (
    ManifestEntry,
    analysis_revision,
    source_id,
    source_revision,
)


def _manifest(path, content, representation='database'):
    return ManifestEntry(source_id('sources', path), 'sources', path, representation,
                         True, 'available', len(content), hashlib.sha256(content).hexdigest())


def _scope(manifest, *, engines=None, options=None, project_revision=None, required=None):
    return database_identity._analysis_scope(
        manifest, engines=engines or {'blueprint': 'test-engine/5'},
        options=options or {'enterprise': False}, project_revision=project_revision,
        required_source_ids=required or tuple(entry.source_id for entry in manifest))


def test_project_namespace_uses_validated_analysis_revision():
    manifest = (_manifest('p.sql', b'CREATE PACKAGE S.P AS END;'),)
    engines = {'blueprint': 'test-engine/5'}
    options = {'enterprise': False, '_target': {'adapter': 'apex'}}
    revision = analysis_revision(source_revision(manifest, {}), engines, options)
    scope = _scope(manifest, engines=engines, options=options, project_revision=revision)
    assert scope.basis == 'PROJECT_ANALYSIS_REVISION'
    assert scope.identity == revision
    with pytest.raises(ValueError, match='revision'):
        _scope(manifest, engines={'blueprint': 'different-engine'}, options=options,
               project_revision=revision)
    with pytest.raises(ValueError, match='revision'):
        _scope(manifest, engines=engines, options={'enterprise': True},
               project_revision=revision)


def test_direct_namespace_uses_all_raw_source_hashes_including_zero_object_sources():
    package = _manifest('p.sql', b'CREATE PACKAGE S.P AS END;')
    zero = _manifest('empty.sql', b'-- no extracted object')
    form = _manifest('form.xml', b'<FormModule Name="F"/>', 'xml')
    manifest = (package, zero, form)
    scope = _scope(manifest)
    assert scope.basis == 'DIRECT_BLUEPRINT_BYTES'
    assert scope.identity
    assert scope == _scope(tuple(reversed(manifest)))
    assert scope != _scope((package, _manifest('empty.sql', b'-- changed zero-object bytes'), form))
    assert scope != _scope((package, zero, _manifest('form.xml', b'<FormModule Name="F" />', 'xml')))
    assert scope != _scope(manifest, engines={'blueprint': 'test-engine/6'})
    assert scope != _scope(manifest, options={'enterprise': True})


@pytest.mark.parametrize('status', ['missing', 'unreadable', 'changed'])
def test_missing_source_bytes_cannot_emit_new_durable_ids(status):
    known = _manifest('p.sql', b'CREATE PACKAGE S.P AS END;')
    missing = replace(_manifest('unreadable.sql', b''), status=status, sha256=None, size_bytes=None)
    scope = _scope((known, missing))
    assert scope.identity is None
    assert scope.basis == 'UNAVAILABLE'
    occurrence = database_identity.SymbolOccurrence(
        ('PACKAGE', 'S', 'P', None, None), 'sources/p.sql', 1, (1, 0))
    with pytest.raises(ValueError, match='identity'):
        database_identity._entity_id(scope, occurrence)


def test_an_omitted_supplied_source_cannot_be_replaced_by_its_path():
    known = _manifest('p.sql', b'CREATE PACKAGE S.P AS END;')
    absent = source_id('sources', 'zero-object.sql')
    scope = _scope((known,), required=(known.source_id, absent))
    assert scope.identity is None
    assert scope.basis == 'UNAVAILABLE'


def test_private_entity_id_binds_analysis_scope_and_complete_occurrence():
    other = replace(_manifest('p.sql', b'CREATE PACKAGE S.P AS END;'), root_id='other',
                    source_id=source_id('other', 'p.sql'))
    first = _scope((_manifest('p.sql', b'CREATE PACKAGE S.P AS END;'), other))
    changed = _scope((_manifest('p.sql', b'CREATE PACKAGE S.P AS END; -- changed bytes'), other))
    occurrence = database_identity.SymbolOccurrence(
        ('PACKAGE', 'S', 'P', None, None), 'sources/p.sql', 1, (1, 0))
    entity_id = database_identity._entity_id(first, occurrence)
    assert entity_id == database_identity._entity_id(first, occurrence)
    assert entity_id != database_identity._entity_id(changed, occurrence)
    assert entity_id != database_identity._entity_id(first, replace(occurrence, ordinal=(2, 0)))
    assert entity_id != database_identity._entity_id(first, replace(occurrence, source_file='other/p.sql'))
    with pytest.raises(ValueError, match='source'):
        database_identity._entity_id(first, replace(occurrence, source_file='C:/host/p.sql'))


def test_private_entity_id_requires_the_occurrence_source_in_its_manifest():
    scope = _scope((_manifest('p.sql', b'CREATE PACKAGE S.P AS END;'),))
    unknown = database_identity.SymbolOccurrence(
        ('PACKAGE', 'S', 'P', None, None), 'sources/never-supplied.sql', 1, (1, 0))
    with pytest.raises(ValueError, match='source'):
        database_identity._entity_id(scope, unknown)
