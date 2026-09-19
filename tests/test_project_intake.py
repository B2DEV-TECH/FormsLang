"""A project descriptor locates evidence; it never grants filesystem authority."""

import json
import multiprocessing
import os
import subprocess
import time
from dataclasses import replace

import pytest

from formslang import authstore, rbac
from formslang.project_model import ProjectBusy, ProjectError
from formslang.project_service import ProjectService


@pytest.fixture
def intake(tmp_path):
    from formslang.project_intake import ProjectIntake
    return ProjectIntake(tmp_path / 'data', tmp_path / 'config')


def test_descriptor_does_not_grant_source_authority(intake):
    with pytest.raises(PermissionError):
        intake.create('Unsafe', [{'root_id': 'f', 'kind': 'forms',
            'area_id': 'unissued', 'relative_path': '../../private'}])
    assert intake.list_recent() == []


def test_local_selection_preview_create_and_reopen_use_real_project(intake, project_sources):
    selected = intake.select_source(project_sources[2].parent, 'forms')
    preview = intake.preview([selected])
    assert preview.inventory['forms']['parseable'] == 1
    created = intake.create('Orders', [selected])
    pid = created['project']['id']
    access = intake.access(pid, rbac.RUN_CONVERSION)
    service = ProjectService(access)
    try:
        result = service.analyze(expected_revision=None, expected_configuration=0)
        assert result['status'] == 'COMPLETED'
    finally:
        service.close()
    from formslang.project_intake import ProjectIntake
    reopened = ProjectIntake(intake.data_dir, intake.config_dir)
    recent = reopened.list_recent()
    assert [p['project']['id'] for p in recent] == [pid]
    assert recent[0]['inventory']['forms']['analyzed'] == 1
    assert recent[0]['analyzed_at']


def test_selection_aliases_do_not_grant_duplicate_roots(intake, project_sources):
    forms = project_sources[2].parent
    first = intake.select_source(forms, 'forms')
    second = intake.select_source(forms / '.', 'forms')
    assert first['area_id'] == second['area_id']
    with pytest.raises(ProjectError):
        intake.create('Duplicate', [first, {**second, 'root_id': 'another'}])


def test_browse_is_contained_and_has_no_source_bodies(intake, project_sources):
    forms = project_sources[2].parent
    (forms / 'child').mkdir()
    selected = intake.select_source(forms, 'forms')
    listing = intake.browse(selected['area_id'])
    assert listing['directories'] == ['child']
    assert 'DEMO_ORDER' not in str(listing)
    with pytest.raises((ProjectError, PermissionError)):
        intake.browse(selected['area_id'], '../database')


def test_open_descriptor_requires_explicit_source_grant(intake, project_sources):
    access, descriptor, _ = project_sources
    service = ProjectService(access)
    service.create(descriptor.name, roots=descriptor.source_roots)
    service.analyze(expected_revision=None, expected_configuration=0)
    service.close()
    opened = intake.open_locator(access.root / '.formslang/project.json')
    access = intake.access(opened['project']['id'], rbac.VIEW_PROJECT)
    assert access.source_roots == ()
    service = ProjectService(access)
    try:
        assert service.assessment() is not None
        assert service.freshness()['status'] == 'UNVERIFIED'
    finally:
        service.close()


def test_local_metadata_does_not_cross_os_user(intake, project_sources, monkeypatch):
    selected = intake.select_source(project_sources[2].parent, 'forms')
    created = intake.create('Private', [selected])
    monkeypatch.setattr('getpass.getuser', lambda: 'different-os-user')
    assert intake.list_recent() == []
    with pytest.raises(PermissionError):
        intake.access(created['project']['id'], rbac.VIEW_PROJECT)
    with pytest.raises(PermissionError):
        intake.preview([selected])


def test_metadata_rejects_redirected_selected_root(intake, project_sources):
    selected = intake.select_source(project_sources[2].parent, 'forms')
    # Revoking the issued root cannot be repaired by trusting project.json.
    created = intake.create('Orders', [selected])
    access = intake.access(created['project']['id'], rbac.RUN_CONVERSION)
    service = ProjectService(replace(access, source_roots=()))
    try:
        with pytest.raises(PermissionError):
            service.discover()
    finally:
        service.close()


@pytest.fixture
def tenant_intake(auth_store, tmp_path, project_sources, monkeypatch):
    from formslang.project_intake import ProjectIdentity, ProjectIntake
    owner = auth_store.bootstrap_owner('owner@example.test', 'correct horse battery staple')
    token, _ = auth_store.create_session(owner['user_id'], owner['organization_id'])
    config = tmp_path / 'tenant-config'
    config.mkdir()
    (config / 'project-source-areas.json').write_text(json.dumps({'organizations': {
        owner['organization_id']: {'forms-area': str(project_sources[2].parent)}}}))
    identity = ProjectIdentity(token, owner['user_id'], owner['organization_id'])
    monkeypatch.setenv('FORMSLANG_AUTH', '1')
    intake = ProjectIntake(tmp_path, config, identity=identity)
    selected = {'root_id': 'forms', 'kind': 'forms', 'area_id': 'forms-area', 'relative_path': ''}
    return intake, selected, owner


def test_authenticated_create_is_managed_and_has_no_absolute_source_disclosure(tenant_intake, auth_store):
    intake, selected, owner = tenant_intake
    created = intake.create('Managed', [selected])
    pid = created['project']['id']
    registered = auth_store.get_project(pid)
    assert registered['org_id'] == owner['organization_id']
    assert registered['storage_mode'] == authstore.ADOPTED
    assert str(intake.data_dir) not in json.dumps(created)
    access = intake.access(pid, rbac.RUN_CONVERSION)
    service = ProjectService(access, authorize=lambda: intake.access(pid, rbac.RUN_CONVERSION))
    try:
        assert service.analyze(expected_revision=None, expected_configuration=0)['status'] == 'COMPLETED'
    finally:
        service.close()
    assert intake.list_recent()[0]['inventory']['forms']['analyzed'] == 1
    with pytest.raises(PermissionError):
        intake.select_source(intake.data_dir, 'forms')


@pytest.mark.parametrize('revocation', ['membership', 'session', 'scope', 'organization'])
def test_intake_rechecks_identity_on_every_operation(tenant_intake, auth_store, revocation):
    intake, selected, owner = tenant_intake
    created = intake.create('Managed', [selected])
    if revocation == 'membership':
        auth_store.db.execute('DELETE FROM membership WHERE user_id=?', (owner['user_id'],))
    elif revocation == 'session':
        auth_store.revoke_session(intake.identity.token)
    elif revocation == 'scope':
        auth_store.db.execute("UPDATE session_token SET scope='MFA_PENDING' WHERE user_id=?", (owner['user_id'],))
    else:
        other = auth_store.create_organization('other', 'Other')
        intake.identity = replace(intake.identity, org_id=other)
    for operation in (lambda: intake.access(created['project']['id'], rbac.VIEW_PROJECT),
                      lambda: intake.preview([selected]), intake.list_recent):
        with pytest.raises((PermissionError, authstore.ProjectNotFound)):
            operation()


def test_viewer_cannot_create_but_can_read_organization_project(tenant_intake, auth_store):
    from formslang.project_intake import ProjectIdentity, ProjectIntake
    intake, selected, owner = tenant_intake
    created = intake.create('Managed', [selected])
    uid = auth_store.create_user('viewer@example.test', 'correct horse battery staple')
    auth_store.create_membership(owner['organization_id'], uid, authstore.VIEWER)
    token, _ = auth_store.create_session(uid, owner['organization_id'])
    viewer = ProjectIntake(intake.data_dir, intake.config_dir, identity=ProjectIdentity(token, uid, owner['organization_id']))
    assert viewer.list_recent()[0]['project']['id'] == created['project']['id']
    with pytest.raises(PermissionError):
        viewer.create('Forbidden', [selected])
    with pytest.raises(PermissionError):
        viewer.access(created['project']['id'], rbac.RUN_CONVERSION)


def test_registry_failure_retry_preserves_initialized_project(tenant_intake, monkeypatch):
    intake, selected, _ = tenant_intake
    original = authstore.AuthStore.register_modernization_project
    def unavailable(*a, **k):
        raise OSError('simulated registry interruption')
    with monkeypatch.context() as patch:
        patch.setattr(authstore.AuthStore, 'register_modernization_project', unavailable)
        with pytest.raises(OSError):
            intake.create('Resume', [selected])
    descriptors = list(intake.data_dir.glob('orgs/*/projects/*/.formslang/project.json'))
    assert len(descriptors) == 1
    old_id = json.loads(descriptors[0].read_text())['id']
    assert original is not None
    resumed = intake.create('Resume', [selected])
    assert resumed['project']['id'] == old_id


def test_descriptor_mirror_failure_is_resumable_before_registration(tenant_intake, auth_store, monkeypatch):
    from formslang.project_store import ProjectStore
    intake, selected, owner = tenant_intake
    def fail_mirror(self):
        raise OSError('simulated mirror interruption')
    with monkeypatch.context() as patch:
        patch.setattr(ProjectStore, 'sync_descriptor', fail_mirror)
        with pytest.raises(OSError):
            intake.create('Recover mirror', [selected])
    assert auth_store.list_projects_for_org(owner['organization_id']) == []
    resumed = intake.create('Recover mirror', [selected])
    assert auth_store.get_project(resumed['project']['id']) is not None


def test_failed_atomic_locator_write_keeps_previous_index(intake, project_sources, monkeypatch):
    from formslang import project_intake
    first = intake.select_source(project_sources[2].parent, 'forms')
    before = (intake.metadata_root / '.formslang/locators.json').read_bytes()
    def interrupted(*a, **k):
        raise OSError('simulated replace interruption')
    with monkeypatch.context() as patch:
        patch.setattr(project_intake.os, 'replace', interrupted)
        with pytest.raises(OSError):
            intake.select_source(project_sources[0].source_roots[1], 'database')
    assert (intake.metadata_root / '.formslang/locators.json').read_bytes() == before
    assert intake.preview([first]).inventory['forms']['parseable'] == 1


def test_missing_host_areas_does_not_hide_saved_assessment(tenant_intake):
    intake, selected, _ = tenant_intake
    pid = intake.create('Managed', [selected])['project']['id']
    (intake.config_dir / 'project-source-areas.json').unlink()
    assert intake.list_recent()[0]['project']['id'] == pid
    assert intake.access(pid, rbac.VIEW_PROJECT).source_roots == ()
    with pytest.raises(PermissionError):
        intake.preview([selected])


def test_foreign_organization_cannot_list_or_open_project(tenant_intake, auth_store):
    from formslang.project_intake import ProjectIdentity, ProjectIntake
    intake, selected, _ = tenant_intake
    pid = intake.create('Private', [selected])['project']['id']
    other = auth_store.create_organization('other', 'Other')
    uid = auth_store.create_user('other@example.test', 'correct horse battery staple')
    auth_store.create_membership(other, uid, authstore.DEVELOPER)
    token, _ = auth_store.create_session(uid, other)
    foreign = ProjectIntake(intake.data_dir, intake.config_dir, identity=ProjectIdentity(token, uid, other))
    assert foreign.list_recent() == []
    with pytest.raises(authstore.ProjectNotFound):
        foreign.access(pid, rbac.VIEW_PROJECT)


@pytest.mark.skipif(os.name != 'nt', reason='Windows NTFS junction regression')
def test_selected_area_cannot_be_redirected_by_junction(intake, project_sources):
    forms = project_sources[2].parent
    selected = intake.select_source(forms, 'forms')
    moved = forms.with_name('moved')
    forms.rename(moved)
    subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command',
        f"New-Item -ItemType Junction -Path '{forms}' -Target '{moved}' | Out-Null"], check=True, capture_output=True)
    try:
        with pytest.raises(ProjectError):
            intake.preview([selected])
        with pytest.raises(ProjectError):
            intake.browse(selected['area_id'])
    finally:
        os.rmdir(forms)  # The test-created junction only, not its target.
    assert (moved / 'orders.xml').is_file()


def _create_local_worker(data, config, source, name, result, ready):
    from formslang.project_intake import ProjectIntake
    intake = ProjectIntake(data, config)
    ready.wait(timeout=10)
    for _ in range(100):
        try:
            selected = intake.select_source(source, 'forms')
            break
        except ProjectBusy:
            time.sleep(.02)
    for _ in range(100):
        try:
            project = intake.create(name, [selected])
            result.put(project['project']['id'])
            return
        except ProjectBusy:
            time.sleep(.02)
    raise AssertionError('locator contention did not settle')


def test_concurrent_locator_updates_do_not_lose_projects(intake, project_sources):
    ctx = multiprocessing.get_context('spawn')
    results = ctx.Queue()
    ready = ctx.Barrier(2)
    workers = [ctx.Process(target=_create_local_worker, args=(intake.data_dir, intake.config_dir,
                project_sources[2].parent, name, results, ready)) for name in ('A', 'B')]
    for worker in workers:
        worker.start()
    try:
        ids = {results.get(timeout=20), results.get(timeout=20)}
        for worker in workers:
            worker.join(timeout=10)
            assert worker.exitcode == 0
        assert {p['project']['id'] for p in intake.list_recent()} == ids
    finally:
        for worker in workers:
            if worker.is_alive():
                worker.terminate()
                worker.join(timeout=5)


def test_local_relink_uses_new_explicit_capability(intake, project_sources):
    selected = intake.select_source(project_sources[2].parent, 'forms')
    pid = intake.create('Move', [selected])['project']['id']
    moved = project_sources[2].parent.with_name('relocated')
    project_sources[2].parent.rename(moved)
    replacement = intake.select_source(moved, 'forms')
    result = intake.relink(pid, selected['root_id'], replacement, expected_configuration=0)
    assert result['project']['id'] == pid
    service = ProjectService(intake.access(pid, rbac.RUN_CONVERSION))
    try:
        assert service.analyze(expected_revision=None, expected_configuration=1)['status'] == 'COMPLETED'
    finally:
        service.close()


def test_authenticated_relink_and_conversion_are_audited(tenant_intake, auth_store, monkeypatch, project_sources):
    from formslang import oracle
    from formslang.project_manifest import source_id
    intake, selected, owner = tenant_intake
    pid = intake.create('Audit', [selected])['project']['id']
    intake.relink(pid, 'forms', selected, expected_configuration=0)
    (project_sources[2].parent / 'extra.fmb').write_bytes(b'synthetic')
    def absent():
        raise oracle.OracleToolchainError('missing')
    monkeypatch.setattr(oracle, 'detect_toolchain', absent)
    result = intake.convert(pid, source_id('forms', 'extra.fmb'), expected_configuration=1, confirmed=True)
    assert result['status'] == 'FAILED'
    events = auth_store.list_audit_events(org_id=owner['organization_id'])
    types = {e['event_type'] for e in events}
    assert {'PROJECT_CREATED', 'PROJECT_SOURCES_RELINKED', 'PROJECT_SOURCE_CONVERTED'} <= types


def test_locator_reads_use_committed_snapshot_during_metadata_write(intake, project_sources):
    selected = intake.select_source(project_sources[2].parent, 'forms')
    pid = intake.create('Readable', [selected])['project']['id']
    with intake._metadata(write=True) as pending:
        pending['projects'] = {}
        assert intake.list_recent()[0]['project']['id'] == pid
    assert intake.list_recent() == []


@pytest.mark.skipif(os.name != 'nt', reason='Windows extended-path spelling regression')
@pytest.mark.parametrize('redirected', [False, True])
def test_extended_windows_prefix_is_not_itself_a_redirect(tmp_path, monkeypatch, redirected):
    from pathlib import Path

    from formslang.project_intake import _plain_path
    requested = tmp_path / 'config/project-intake/.formslang'
    original = Path.resolve
    def resolved(path, *a, **k):
        if path == requested:
            destination = tmp_path / 'foreign' if redirected else requested
            return Path('\\\\?\\' + str(destination))
        return original(path, *a, **k)
    monkeypatch.setattr(Path, 'resolve', resolved)
    if redirected:
        with pytest.raises(ProjectError):
            _plain_path(requested)
    else:
        assert _plain_path(requested) == requested
