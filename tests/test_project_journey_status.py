"""WP-39a journey status: read-only, composed from facts the product already saves."""
# ruff: noqa: F811 -- imported pytest fixtures are injected by name

import hashlib
from pathlib import Path

import pytest

from formslang import apeximport, rbac
from formslang.project_generation_policy import (
    dependency_edges,
    related_scope,
    unresolved_findings,
)
from formslang.project_intake import ProjectIntake
from formslang.project_review import ProjectReviewService
from formslang.project_service import ProjectService
from tests.test_project_generation import generation_project, prepared  # noqa: F401


@pytest.fixture
def demo(tmp_path, monkeypatch):
    monkeypatch.setenv('FORMSLANG_AUTH', '0')
    intake = ProjectIntake(tmp_path / 'data', tmp_path / 'config')
    project_id = intake.create_demo()['project']['id']
    authorize = lambda: intake.access(project_id, rbac.RUN_CONVERSION)
    service = ProjectService(authorize(), authorize=authorize)
    assert service.analyze(expected_revision=None, expected_configuration=0)['status'] == 'COMPLETED'
    yield service
    service.close()


def test_related_scope_is_unchanged_by_precomputed_edges(demo):
    blueprint = demo.assessment()['blueprint']
    edges = dependency_edges(blueprint)
    forms = [e for e in blueprint['entities'] if e['type'] == 'FORM']
    assert forms
    for form in forms:
        assert related_scope(blueprint, form['module'], outgoing=edges) == related_scope(blueprint, form['module'])


def test_unresolved_findings_match_generation_review_blockers(demo):
    assessment = demo.assessment()
    checked = 0
    for module in demo.generation_overview()['modules']:
        detail = demo.generation_module(module['source_id'])
        blocked = sorted(b['id'] for b in detail['blockers'] if b['code'] == 'UNRESOLVED_REVIEW')
        unresolved = sorted(f['id'] for f in unresolved_findings(assessment['blueprint'], module['module']))
        assert unresolved == blocked
        checked += len(blocked)
    assert checked > 0


def _tree_digest(root):
    digest = hashlib.sha256()
    for path in sorted(p for p in Path(root).rglob('*') if p.is_file()):
        digest.update(path.relative_to(root).as_posix().encode('utf-8'))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _currency_inputs(service):
    db = service._store.session.db
    plans = {(row[0], row[1]): row[2] for row in db.execute(
        'SELECT source_id,analysis_revision,revision FROM project_target_plan ORDER BY id')}
    sessions = {(s['source_id'], s['revision']): s for s in service._store.module_sessions()}
    return plans, sessions


def test_read_only_generation_detail_writes_nothing(generation_project):
    service = generation_project
    detail = prepared(service)
    generation = service._generation_service()
    fresh = ProjectReviewService(service)._freshness()
    assessment = service.assessment(freshness=fresh)
    before = _tree_digest(service.access.root)
    again = generation._detail(assessment, fresh, detail['source_id'], read_only=True)
    assert again['blockers'] == detail['blockers'] == []
    assert _tree_digest(service.access.root) == before


def test_artifact_currency_is_the_report_rule(generation_project):
    service = generation_project
    detail = prepared(service)
    generated = service.generate({**detail['binding'], 'scopes': [detail]})
    generation = service._generation_service()
    fresh = ProjectReviewService(service)._freshness()
    assessment = service.assessment(freshness=fresh)
    artifact = next(a for a in service.generation_overview()['artifacts']
                    if a['artifact_id'] == generated['artifact_id'])
    plans, sessions = _currency_inputs(service)
    current = {'freshness_status': fresh['status'], 'latest_plans': plans, 'sessions': sessions}
    assert generation.artifact_currency(assessment, artifact, **current) is None
    assert generation.artifact_currency(
        assessment, artifact, **{**current, 'freshness_status': 'STALE'}) == 'ARTIFACT_REVISION_STALE'
    assert generation.artifact_currency(
        assessment, artifact, **{**current, 'latest_plans': {}}) == 'ARTIFACT_REVISION_STALE'
    assert generation.artifact_currency(
        assessment, artifact, **{**current, 'sessions': {}}) == 'ARTIFACT_CODE_UNAVAILABLE'


def test_latest_validation_reads_the_newest_record(generation_project, monkeypatch):
    service = generation_project
    detail = prepared(service)
    generated = service.generate({**detail['binding'], 'scopes': [detail]})
    generation = service._generation_service()
    assert generation.latest_validation(generated['artifact_id']) is None
    monkeypatch.setattr(apeximport, 'sqlcl_version', lambda: '')
    service.generation_validate(generated['artifact_id'])
    assert generation.latest_validation(generated['artifact_id'])['status'] == 'Not Validated'
