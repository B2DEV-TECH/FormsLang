"""Phase B extends the existing project database without losing Phase A state."""

import json
import sqlite3

import pytest

from formslang.project_discovery import DiscoveredSource, DiscoveryResult, SourceDiagnostic
from formslang.project_manifest import SourceCandidate
from formslang.project_model import (
    ProjectDescriptor,
    ProjectError,
    RevisionConflict,
    SourceRoot,
)
from formslang.project_store import ProjectStore


@pytest.fixture
def project_store(tmp_path):
    store = ProjectStore.create(tmp_path / 'project', ProjectDescriptor(id='a'*32, name='Orders'))
    try:
        yield store
    finally:
        store.close()


def test_relink_cas_does_not_overwrite_newer_config(project_store):
    revision = project_store.configuration_revision()
    roots = (SourceRoot('forms', 'forms', '../new-source'),)
    project_store.replace_roots(roots, expected_configuration=revision)
    with pytest.raises(RevisionConflict):
        project_store.replace_roots((), expected_configuration=revision)
    assert project_store.descriptor().source_roots == roots
    assert project_store.configuration_revision() == revision + 1


def test_stale_store_reads_latest_metadata_in_update_transaction(project_store):
    observer = ProjectStore.open(project_store.root)
    try:
        roots = (SourceRoot('forms', 'forms', '../a'),)
        project_store.replace_roots(roots, expected_configuration=0)
        with pytest.raises(RevisionConflict):
            observer.replace_roots((), expected_configuration=0)
        assert observer.descriptor().source_roots == roots
    finally:
        observer.close()


def test_mirror_failure_preserves_committed_configuration(project_store, monkeypatch):
    def failed():
        raise ProjectError('mirror unavailable')
    roots = (SourceRoot('f', 'forms', '../forms'),)
    monkeypatch.setattr(project_store, 'sync_descriptor', failed)
    with pytest.raises(ProjectError, match='mirror'):
        project_store.replace_roots(roots, expected_configuration=0)
    reopened = ProjectStore.open(project_store.root)
    try:
        assert reopened.descriptor().source_roots == roots
        assert reopened.configuration_revision() == 1
        mirror = json.loads((reopened.directory / 'project.json').read_text())
        assert mirror['source_roots'][0]['path'] == '../forms'
    finally:
        reopened.close()


def test_invalid_roots_never_advance_configuration(project_store):
    with pytest.raises(ProjectError):
        project_store.replace_roots((SourceRoot('f', 'untrusted', '../x'),), expected_configuration=0)
    assert project_store.configuration_revision() == 0


def discovery(count):
    entries = tuple(DiscoveredSource(SourceCandidate('forms', f'{i:03}.xml', 'xml'),
                                    'DISCOVERED', 'DISCOVERED') for i in range(count))
    return DiscoveryResult(entries, (), {'candidates': count})


def test_discovery_pagination_and_run_immutability(project_store):
    result = discovery(205)
    project_store.record_discovery(result, run_id='1'*32)
    first = project_store.discovery(None)
    assert first['total'] == 205 and len(first['entries']) == 50
    assert first['entries'][0]['candidate']['relative_path'] == '000.xml'
    last = project_store.discovery('1'*32, offset=200, limit=200)
    assert len(last['entries']) == 5
    with pytest.raises(RevisionConflict):
        project_store.record_discovery(discovery(1), run_id='1'*32)
    assert project_store.discovery('1'*32)['total'] == 205


@pytest.mark.parametrize(('offset', 'limit'), [(-1, 50), (0, 0), (0, 201), (True, 50), (0, '50')])
def test_discovery_pagination_rejects_invalid_bounds(project_store, offset, limit):
    with pytest.raises(ProjectError):
        project_store.discovery(None, offset=offset, limit=limit)


def test_empty_discovery_has_useful_empty_state(project_store):
    assert project_store.discovery(None)['available'] is False


def test_diagnostics_are_bounded_separately(project_store):
    diagnostics = tuple(SourceDiagnostic('a'*64, 'bad.xml', 'DISCOVERY', 'INVALID_XML',
        'Invalid XML.', 'Export it again.') for i in range(210))
    project_store.record_discovery(DiscoveryResult((), diagnostics, {'candidates': 0}), run_id='2'*32)
    result = project_store.discovery(None)
    assert result['diagnostics_total'] == 210
    assert len(result['diagnostics']) == 50


def test_migration_from_phase_a_preserves_review_tables(project_store):
    # Model the exact Phase A table contract independently of the new schema.
    db = project_store.session.db
    original = db.execute('SELECT * FROM modernization_project').fetchone()
    db.execute("INSERT INTO blueprint_review(entity, revision, action, reviewer, comment, decided_at) VALUES ('e','r','DEFER','Reviewer','Keep me','2026-09-19')")
    db.commit()
    reviews = [tuple(row) for row in db.execute('SELECT * FROM blueprint_review')]
    new_tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'project_%'")
                  if r[0] not in {'project_assessment', 'project_module_session'}]
    for name in new_tables:
        db.execute('DROP TABLE "' + name + '"')
    db.commit()
    project_store.close()
    for _ in range(2):
        migrated = ProjectStore.open(project_store.root)
        try:
            assert migrated.configuration_revision() == 0
            assert [tuple(row) for row in migrated.session.db.execute('SELECT * FROM blueprint_review')] == reviews
            assert migrated.descriptor().id == json.loads(original['descriptor_json'])['id']
        finally:
            migrated.close()


def test_failed_discovery_transaction_leaves_no_half_run(project_store):
    db = project_store.session.db
    db.execute("CREATE TRIGGER reject_source BEFORE INSERT ON project_discovery_entry BEGIN SELECT RAISE(ABORT,'injected'); END")
    db.commit()
    with pytest.raises((ProjectError, sqlite3.Error)):
        project_store.record_discovery(discovery(1), run_id='3'*32)
    assert project_store.discovery(None)['available'] is False


def assessment(store):
    from formslang import blueprint
    from formslang.project_assessment import bind_assessment
    from formslang.project_manifest import ManifestEntry, source_id

    manifest = (ManifestEntry(source_id('f', 'a.xml'), 'f', 'a.xml', 'xml', True,
                              'available', 10, 'b'*64),)
    return bind_assessment(store.descriptor(), manifest, blueprint.build([]),
        engines={'test':'1'}, options={}, analyzed_at='2026-09-19T00:00:00Z', status='Current')


@pytest.mark.parametrize('completion', ['COMPLETE', 'COMPLETE_WITH_WARNINGS', 'INCOMPLETE'])
def test_completion_and_phase_a_status_must_agree(project_store, completion):
    value = assessment(project_store)
    value.update(inventory={}, diagnostics=[], completion_state=completion)
    if completion == 'COMPLETE':
        project_store.save_assessment(value, expected_revision=None)
        assert project_store.load_assessment()['completion_state'] == 'COMPLETE'
    else:
        with pytest.raises(ProjectError):
            project_store.save_assessment(value, expected_revision=None)
        assert project_store.load_assessment() is None


@pytest.mark.parametrize('diagnostics', [{}, ['raw stack trace'], [{'safe_message':'secret'}]])
def test_malformed_diagnostics_rejected_before_publication(project_store, diagnostics):
    value = assessment(project_store)
    value.update(inventory={}, diagnostics=diagnostics, completion_state='COMPLETE_WITH_WARNINGS')
    with pytest.raises(ProjectError):
        project_store.save_assessment(value, expected_revision=None)
    assert project_store.load_assessment() is None


def test_incomplete_assessment_retains_structured_failure(project_store):
    from dataclasses import asdict

    value = assessment(project_store)
    value['status'] = 'Incomplete'
    value.update(inventory={}, completion_state='INCOMPLETE', diagnostics=[asdict(SourceDiagnostic(
        'b'*64, 'bad.xml', 'FORMS_PARSING', 'INVALID_XML', 'Invalid XML.', 'Export the module again.'))])
    project_store.save_assessment(value, expected_revision=None)
    assert project_store.load_assessment()['diagnostics'][0]['error_code'] == 'INVALID_XML'


def test_equivalent_json_tuples_do_not_create_revision_collision(project_store):
    value = assessment(project_store)
    value['blueprint']['assessment']['blockers_by_module'] = [('ORDERS', 1)]
    project_store.save_assessment(value, expected_revision=None)
    before = project_store.load_assessment()
    value['analyzed_at'] = '2026-09-20T00:00:00Z'
    project_store.save_assessment(value, expected_revision=value['analysis_revision'])
    assert project_store.load_assessment() == before
