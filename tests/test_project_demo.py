"""The bundled synthetic demo is an ordinary persisted project, not a UI fixture."""

import os
import subprocess
from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest

from formslang import rbac
from formslang.project_intake import ProjectIdentity, ProjectIntake
from formslang.project_model import ProjectError
from formslang.project_service import ProjectService


def analyze(intake, created):
    pid = created['project']['id']
    authorize = lambda: intake.access(pid, rbac.RUN_CONVERSION)
    service = ProjectService(authorize(), authorize=authorize)
    try:
        result = service.analyze(expected_revision=None, expected_configuration=0)
        assert result['status'] in {'COMPLETED', 'COMPLETED_WITH_WARNINGS'}
        return service.assessment()
    finally:
        service.close()


def test_demo_runs_normal_pipeline_and_covers_decision_shapes(tmp_path, monkeypatch):
    from formslang import ai, oracle

    def forbidden(*args, **kwargs):
        raise AssertionError('Demo must not initialize external tooling or AI')

    monkeypatch.setattr(ai, 'provider_from_env', forbidden)
    monkeypatch.setattr(oracle, 'detect_toolchain', forbidden)
    intake = ProjectIntake(tmp_path / 'data', tmp_path / 'config')
    created = intake.create_demo()
    assessment = analyze(intake, created)
    assert assessment['inventory']['forms']['analyzed'] == 2
    assert assessment['inventory']['database']['package_bodies'] == 1
    findings = assessment['blueprint']['findings']
    assert {'PRESERVE', 'REPLACE_WITH_APEX_NATIVE', 'REFACTOR', 'MOVE_TO_PLSQL_API', 'MANUAL_REVIEW'} <= {f['recommendation'] for f in findings}
    assert any(e['attributes'].get('risk', {}).get('level') == 'CRITICAL' for e in assessment['blueprint']['entities'])
    assert intake.list_recent()[0]['project']['analysis_revision'] == assessment['analysis_revision']


def test_demo_copies_are_independent_and_rename_invariant(tmp_path):
    intake = ProjectIntake(tmp_path / 'data', tmp_path / 'config')
    first, second = intake.create_demo(), intake.create_demo()
    baseline = analyze(intake, first)
    for root in second['project']['source_roots']:
        for source in Path(root['path']).iterdir():
            source.write_text(source.read_text(encoding='utf-8').replace('SHIPMENT', 'REQUEST').replace('shipment', 'request'), encoding='utf-8')
    changed = analyze(intake, second)
    assert Counter(f['recommendation'] for f in baseline['blueprint']['findings']) == Counter(f['recommendation'] for f in changed['blueprint']['findings'])
    assert baseline['source_revision'] != changed['source_revision']


def test_managed_demo_needs_membership_but_no_host_source_setup(tmp_path, auth_store, monkeypatch):
    owner = auth_store.bootstrap_owner('demo@example.test', 'correct horse battery staple')
    token, _ = auth_store.create_session(owner['user_id'], owner['organization_id'])
    identity = ProjectIdentity(token, owner['user_id'], owner['organization_id'])
    monkeypatch.setenv('FORMSLANG_AUTH', '1')
    intake = ProjectIntake(tmp_path, tmp_path / 'config', identity=identity)
    created = intake.create_demo()
    assert all('path' not in r for r in created['project']['source_roots'])
    assert analyze(intake, created)['inventory']['forms']['analyzed'] == 2
    foreign = ProjectIntake(tmp_path, tmp_path / 'config', identity=replace(identity, org_id='f' * 32))
    with pytest.raises(PermissionError):
        foreign.create_demo()


def test_demo_rejects_redirected_storage_without_touching_target(tmp_path):
    data, outside = tmp_path / 'data', tmp_path / 'outside'
    data.mkdir()
    outside.mkdir()
    redirected = data / 'demo-sources'
    if os.name == 'nt':
        result = subprocess.run(['cmd', '/c', 'mklink', '/J', str(redirected), str(outside)], capture_output=True, check=False)
        assert result.returncode == 0, result.stderr
    else:
        redirected.symlink_to(outside, target_is_directory=True)
    intake = ProjectIntake(data, tmp_path / 'config')
    with pytest.raises(ProjectError):
        intake.create_demo()
    assert list(outside.iterdir()) == []


def test_viewer_cannot_allocate_demo_sources(tmp_path, auth_store, monkeypatch):
    from formslang import authstore

    owner = auth_store.bootstrap_owner('demo-owner@example.test', 'correct horse battery staple')
    user = auth_store.create_user('demo-viewer@example.test', 'correct horse battery staple')
    auth_store.create_membership(owner['organization_id'], user, authstore.VIEWER)
    token, _ = auth_store.create_session(user, owner['organization_id'])
    monkeypatch.setenv('FORMSLANG_AUTH', '1')
    intake = ProjectIntake(tmp_path, tmp_path / 'config', identity=ProjectIdentity(token, user, owner['organization_id']))
    with pytest.raises(PermissionError):
        intake.create_demo()
    assert not (tmp_path / 'orgs' / owner['organization_id'] / 'demo-sources').exists()


def test_demo_overview_reopens_without_analysis_and_keeps_stale_metrics(tmp_path, monkeypatch):
    intake = ProjectIntake(tmp_path / 'data', tmp_path / 'config')
    created = intake.create_demo()
    pid = created['project']['id']
    assessment = analyze(intake, created)
    authorize = lambda: intake.access(pid, rbac.RUN_CONVERSION)

    service = ProjectService(authorize(), authorize=authorize)
    try:
        current = service.freshness()
        before = service.overview(freshness=current)
    finally:
        service.close()
    assert before['inventory']['forms_modules'] == 2
    assert before['inventory']['database_packages'] >= 1
    assert before['risk_distribution']['CRITICAL'] >= 1
    assert {'AUTO', 'ASSISTED', 'MANUAL', 'UNKNOWN'} == set(before['intervention_distribution'])
    assert len([value for value in before['recommendation_distribution'].values() if value]) >= 5

    def forbidden(*args, **kwargs):
        raise AssertionError('Opening Overview must not reanalyze source')

    monkeypatch.setattr('formslang.project_analysis.analyze_project', forbidden)
    reopened = ProjectService(authorize(), authorize=authorize)
    try:
        assert reopened.overview(freshness=current) == before
        descriptor = reopened.open()
        forms = next(root for root in descriptor.source_roots if root.kind == 'forms')
        source = next((reopened.access.root / forms.path).glob('*.xml'))
        source.write_bytes(source.read_bytes() + b'\n<!-- stale overview fixture -->\n')
        stale = reopened.freshness()
        after = reopened.overview(freshness=stale)
    finally:
        reopened.close()
    assert stale['status'] == 'STALE'
    assert after['assessment']['freshness'] == 'STALE'
    assert after['inventory'] == before['inventory']
    assert assessment['analysis_revision'] == after['assessment']['analysis_revision']
