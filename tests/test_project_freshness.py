"""Reopening preserves evidence; freshness never substitutes metadata for bytes."""

import os
import shutil
from dataclasses import replace

import pytest

from formslang import database, parser
from formslang.project_jobs import ProjectJobManager
from formslang.project_model import ProjectBusy, RevisionConflict
from formslang.project_service import ProjectService


@pytest.fixture
def analyzed(project_sources):
    access, descriptor, _ = project_sources
    # Authority covers the fixture's relocation destination, not arbitrary folders.
    access = replace(access, source_roots=(access.root.parent,))
    service = ProjectService(access)
    service.create(descriptor.name, roots=descriptor.source_roots)
    service.analyze(expected_revision=None, expected_configuration=0)
    try:
        yield service
    finally:
        service.close()


def test_same_size_and_mtime_change_is_stale(analyzed, project_sources):
    xml = project_sources[2]
    stat = xml.stat()
    raw = xml.read_bytes()
    changed = raw.replace(b'DEMO_ORDER', b'DEMO_OTHER', 1)
    assert len(changed) == len(raw) and changed != raw
    xml.write_bytes(changed)
    os.utime(xml, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    assert analyzed.freshness()['status'] == 'STALE'


def test_reopen_checks_without_parsing_or_rewriting_assessment(analyzed, monkeypatch):
    saved = analyzed.assessment()
    access = analyzed.access
    analyzed.close()
    def forbidden(*a, **k):
        raise AssertionError('freshness must not parse')
    monkeypatch.setattr(parser, 'parse_xml', forbidden)
    monkeypatch.setattr(database, 'parse_database_file', forbidden)
    reopened = ProjectService(access)
    try:
        assert reopened.assessment() == saved
        assert reopened.freshness()['status'] == 'CURRENT'
        assert reopened.assessment()['analyzed_at'] == saved['analyzed_at']
    finally:
        reopened.close()


@pytest.mark.parametrize('change,expected', [('add', 'STALE'), ('delete', 'MISSING_SOURCE'), ('root', 'MISSING_SOURCE')])
def test_inventory_changes_detected(analyzed, project_sources, change, expected):
    xml = project_sources[2]
    if change == 'add':
        (xml.parent / 'new.xml').write_bytes(xml.read_bytes())
    elif change == 'delete':
        xml.unlink()
    else:
        xml.parent.rename(xml.parent.with_name('moved'))
    assert analyzed.freshness()['status'] == expected


@pytest.mark.parametrize('same', [True, False])
def test_relink_fingerprints_content_and_retains_identity(analyzed, project_sources, same):
    xml = project_sources[2]
    saved = analyzed.assessment()
    destination = xml.parent.with_name('relocated')
    shutil.copytree(xml.parent, destination)
    if not same:
        (destination / xml.name).write_text('<different/>')
    result = analyzed.relink('forms', destination, expected_configuration=0)
    assert result['freshness']['status'] == ('CURRENT' if same else 'STALE')
    assert analyzed.open().source_roots[0].id == 'forms'
    assert analyzed._store.configuration_revision() == 1
    assert analyzed.assessment()['analyzed_at'] == saved['analyzed_at']
    assert analyzed._store.load_assessment()['source_manifest'] == saved['source_manifest']
    with pytest.raises(RevisionConflict):
        analyzed.relink('forms', destination, expected_configuration=0)


def test_relink_cannot_escape_host_authority(analyzed, tmp_path):
    before = analyzed.open()
    with pytest.raises(PermissionError):
        analyzed.relink('forms', tmp_path.parent, expected_configuration=0)
    assert analyzed.open() == before


def test_relink_does_not_disrupt_live_analysis(analyzed):
    manager = ProjectJobManager(analyzed.access, lambda: analyzed.access)
    descriptor = analyzed.open()
    with manager.claim('ANALYZE', expected_revision=descriptor.analysis_revision, expected_configuration=0) as lease:
        with pytest.raises(ProjectBusy):
            analyzed.relink('forms', descriptor.source_roots[0].path, expected_configuration=0)
        lease.finish('COMPLETED')


def test_engine_change_has_explicit_freshness_reason(analyzed, monkeypatch):
    from formslang import project_freshness
    monkeypatch.setattr(project_freshness, 'engine_identity', lambda: {'engine': 'different'})
    result = analyzed.freshness()
    assert result['status'] == 'STALE'
    assert 'ENGINE_CHANGED' in result['reasons']


def test_unchanged_partial_assessment_stays_incomplete(analyzed, project_sources):
    (project_sources[2].parent / 'bad.xml').write_text('<broken>')
    analyzed.analyze(expected_revision=analyzed.open().analysis_revision, expected_configuration=0)
    freshness = analyzed.freshness()
    assert freshness['status'] == 'INCOMPLETE'
    assert analyzed.assessment(freshness=freshness)['status'] == 'Incomplete'


def test_legacy_assessment_without_phase_b_fields_can_be_checked(analyzed):
    from formslang.project_freshness import check_freshness
    saved = analyzed._store.load_assessment()
    for field in ('inventory', 'diagnostics', 'completion_state'):
        saved.pop(field)
    assert check_freshness(analyzed.access, analyzed.open(), saved, checkpoint=lambda: None)['status'] == 'CURRENT'


def test_source_access_loss_never_claims_current(analyzed):
    from formslang.project_freshness import check_freshness
    access = replace(analyzed.access, source_roots=())
    result = check_freshness(access, analyzed.open(), analyzed.assessment(), checkpoint=lambda: None)
    assert result['status'] == 'UNVERIFIED'


def test_partial_scan_cannot_be_current_even_when_selected_manifest_matches(analyzed, project_sources, monkeypatch):
    from formslang import project_discovery
    monkeypatch.setattr(project_discovery, 'MAX_DEPTH', 0)
    (project_sources[2].parent / 'deep').mkdir()
    assert analyzed.freshness()['status'] == 'UNVERIFIED'


def test_freshness_projection_suppresses_approval_without_losing_history(analyzed, project_sources):
    saved = analyzed.assessment()
    finding = saved['blueprint']['findings'][0]
    analyzed._store.session.review_blueprint(entity=finding['entity'], revision=finding['revision'],
        action='APPROVE', reviewer='Analyst', comment='Checked')
    project_sources[2].write_bytes(project_sources[2].read_bytes() + b'\n')
    freshness = analyzed.freshness()
    projected = analyzed.assessment(freshness=freshness)
    reviewed = next(f for f in projected['blueprint']['findings'] if f['entity'] == finding['entity'])
    assert projected['status'] == 'Stale'
    assert reviewed['review_state'] == 'STALE'
    assert 'human_decision' not in reviewed
    assert reviewed['review_history'][0]['reviewer'] == 'Analyst'
    assert analyzed._store.load_assessment()['analyzed_at'] == saved['analyzed_at']


def test_open_reconciles_orphaned_job_without_analysis(analyzed):
    access = analyzed.access
    db = analyzed._store.session.db
    db.execute("UPDATE project_job SET status='RUNNING' WHERE job_id=(SELECT job_id FROM project_job LIMIT 1)")
    db.commit()
    analyzed.close()
    reopened = ProjectService(access)
    try:
        reopened.open()
        row = reopened._store.session.db.execute('SELECT status,safe_failure_json FROM project_job LIMIT 1').fetchone()
        assert row[0] == 'FAILED' and 'PROCESS_INTERRUPTED' in row[1]
        assert reopened.assessment() is not None
    finally:
        reopened.close()
