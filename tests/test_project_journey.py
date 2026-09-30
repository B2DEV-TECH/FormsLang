"""WP-12 read-only journey contracts on the bundled synthetic project."""

from pathlib import Path

import pytest

from formslang import rbac
from formslang.project_intake import ProjectIntake
from formslang.project_model import ProjectError
from formslang.project_service import ProjectService


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


def test_relationship_evidence_is_bound_to_selected_saved_edge(demo):
    graph = demo.system_map(focus='CUSTOMERS')
    edge = next(e for e in graph['edges'] if e['source_name'] == 'CUSTOMERS'
                and e['target_name'] == 'SHIPMENTS' and e['classification'] == 'OPENS_FORM')
    detail = demo.relationship_evidence(edge['id'])
    assert detail['edge']['id'] == edge['id']
    assert detail['edge']['evidence_refs'] == edge['evidence_refs']
    assert detail['evidence'][0]['id'] == edge['evidence_refs'][0]
    assert detail['evidence'][0]['text'].startswith('OPEN_FORM')
    assert 'OPEN_FORM' in detail['source'][0]['excerpt']
    assert 'SHIPMENTS' not in detail['source'][0]['excerpt']  # literal is redacted
    assert detail['edge']['target_unresolved'] is False


def test_unresolved_relationship_remains_unresolved_in_journey(demo):
    graph = demo.system_map(focus='CUSTOMERS')
    edge = next(e for e in graph['edges'] if e['source_name'] == 'CUSTOMERS'
                and e['classification'] == 'REFERENCES')
    detail = demo.relationship_evidence(edge['id'])
    assert detail['edge']['target_unresolved'] is True
    assert detail['edge']['target_name'] == 'CUSTOMERS'
    assert detail['edge']['classification'] == 'REFERENCES'
    with pytest.raises(ProjectError):
        demo.relationship_evidence('map-edge:does-not-exist')


def test_journey_read_does_not_change_saved_revisions(demo):
    before = demo.assessment()
    graph = demo.system_map(focus='CUSTOMERS')
    demo.relationship_evidence(graph['edges'][0]['id'])
    after = demo.assessment()
    assert (after['analysis_revision'], after['blueprint']['source_revision'],
            after['review_revision']) == (before['analysis_revision'],
                                         before['blueprint']['source_revision'],
                                         before['review_revision'])


def test_missing_form_reference_is_not_a_followable_form(tmp_path, monkeypatch):
    monkeypatch.setenv('FORMSLANG_AUTH', '0')
    intake = ProjectIntake(tmp_path / 'data', tmp_path / 'config')
    created = intake.create_demo()
    source = next(root for root in created['project']['source_roots'] if root['kind'] == 'forms')
    # The copied demo root is the verified synthetic source; change only one
    # literal target so the engine must preserve a symbolic Form reference.
    customers = Path(source['path']) / 'customers.xml'
    original = customers.read_text(encoding='utf-8')
    customers.write_text(original.replace("OPEN_FORM('SHIPMENTS')", "OPEN_FORM('GHOST_FORM')"),
                         encoding='utf-8')
    project_id = created['project']['id']
    authorize = lambda: intake.access(project_id, rbac.RUN_CONVERSION)
    service = ProjectService(authorize(), authorize=authorize)
    try:
        assert service.analyze(expected_revision=None, expected_configuration=0)['status'] == 'COMPLETED'
        graph = service.system_map(focus='CUSTOMERS')
        edge = next(e for e in graph['edges'] if e['source_name'] == 'CUSTOMERS'
                    and e['classification'] == 'OPENS_FORM' and e['target_name'] == 'GHOST_FORM')
        detail = service.relationship_evidence(edge['id'])
        assert detail['edge']['target_layer'] == 'FORM'
        assert detail['edge']['target_unresolved'] is True
    finally:
        service.close()


def test_relationship_source_name_is_bounded(tmp_path, monkeypatch):
    monkeypatch.setenv('FORMSLANG_AUTH', '0')
    intake = ProjectIntake(tmp_path / 'data', tmp_path / 'config')
    created = intake.create_demo()
    source = next(root for root in created['project']['source_roots'] if root['kind'] == 'forms')
    customers = Path(source['path']) / 'customers.xml'
    original = customers.read_text(encoding='utf-8')
    long_name = 'N' * 12000
    customers.write_text(original.replace('Name="WHEN-BUTTON-PRESSED"', f'Name="{long_name}"'),
                         encoding='utf-8')
    project_id = created['project']['id']
    authorize = lambda: intake.access(project_id, rbac.RUN_CONVERSION)
    service = ProjectService(authorize(), authorize=authorize)
    try:
        assert service.analyze(expected_revision=None, expected_configuration=0)['status'] == 'COMPLETED'
        graph = service.system_map(focus='CUSTOMERS')
        edge = next(e for e in graph['edges'] if e['source_name'] == 'CUSTOMERS'
                    and e['target_name'] == 'SHIPMENTS' and e['classification'] == 'OPENS_FORM')
        detail = service.relationship_evidence(edge['id'])
        assert detail['source'][0]['name'] == long_name[:500]
    finally:
        service.close()
