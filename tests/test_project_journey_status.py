"""WP-39a journey status: read-only, composed from facts the product already saves."""

import pytest

from formslang import rbac
from formslang.project_generation_policy import (
    dependency_edges,
    related_scope,
    unresolved_findings,
)
from formslang.project_intake import ProjectIntake
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
