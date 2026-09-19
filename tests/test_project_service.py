"""Local zero-config usage and existing tenant authorization share one service."""

from dataclasses import replace

import pytest

from formslang import ai, authstore, oracle, rbac
from formslang.project_model import ProjectError, SourceRoot
from formslang.project_service import ProjectService
from formslang.projects import authorized_project_access, local_project_access


def test_local_create_reopen_without_provider_or_auth(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("static project operations must not initialize external services")

    monkeypatch.setenv("FORMSLANG_AUTH", "0")
    monkeypatch.setattr(authstore.AuthStore, "__init__", forbidden)
    monkeypatch.setattr(oracle, "detect_toolchain", forbidden)
    monkeypatch.setattr(ai, "build_provider", forbidden)
    monkeypatch.setattr(ai, "provider_from_env", forbidden)
    access = local_project_access(tmp_path / "project", approved_roots=(tmp_path,))
    service = ProjectService(access)
    try:
        created = service.create("Orders")
        assert created.target.version == "26.1"
        assert service.assessment() is None
    finally:
        service.close()
    reopened = ProjectService(access)
    try:
        assert reopened.open() == created
    finally:
        reopened.close()


def test_auth_enabled_refuses_local_shortcut(tmp_path, monkeypatch):
    monkeypatch.setenv("FORMSLANG_AUTH", "1")
    with pytest.raises(PermissionError):
        local_project_access(tmp_path, approved_roots=(tmp_path,))


def test_sources_need_host_authority_and_viewer_cannot_create(tmp_path, monkeypatch):
    monkeypatch.setenv("FORMSLANG_AUTH", "0")
    access = local_project_access(tmp_path / "project", approved_roots=())
    service = ProjectService(access)
    with pytest.raises(PermissionError):
        service.create("Orders", roots=(SourceRoot("f", "forms", "../source"),))
    viewer = ProjectService(replace(access, actions=frozenset({rbac.VIEW_PROJECT})))
    with pytest.raises(PermissionError):
        viewer.create("Orders")
    with pytest.raises(PermissionError):
        viewer.import_session(tmp_path / "secret.db", source_key="legacy/source")
    assert not (tmp_path / "project/.formslang").exists()


def test_missing_project_is_not_created_by_read(tmp_path, monkeypatch):
    monkeypatch.setenv("FORMSLANG_AUTH", "0")
    service = ProjectService(local_project_access(tmp_path / "missing", approved_roots=()))
    with pytest.raises(ProjectError):
        service.assessment()
    assert not (tmp_path / "missing").exists()


def test_redirected_root_rejected_after_access_created(tmp_path, monkeypatch):
    monkeypatch.setenv("FORMSLANG_AUTH", "0")
    root, other = tmp_path / "project", tmp_path / "other"
    other.mkdir()
    access = local_project_access(root, approved_roots=(tmp_path,))
    try:
        root.symlink_to(other, target_is_directory=True)
    except OSError:
        pytest.skip("OS does not permit symlinks")
    with pytest.raises(ProjectError):
        ProjectService(access).create("Orders")
    assert not (other / ".formslang").exists()


def test_tenant_resolution_and_revocation(auth_store, tmp_path, monkeypatch):
    monkeypatch.setenv("FORMSLANG_AUTH", "0")
    root = tmp_path / "project"
    service = ProjectService(local_project_access(root, approved_roots=(tmp_path,)))
    service.create("Orders")
    service.close()
    owner = auth_store.bootstrap_owner("owner@example.test", "correct horse battery staple")
    registered = auth_store.register_external_project(owner["organization_id"], "Orders",
        root / ".formslang/project.session.db", created_by=owner["user_id"])
    other_org = auth_store.create_organization("other", "Other")
    args = {"active_org_id": owner["organization_id"], "user_id": owner["user_id"],
            "action": rbac.VIEW_PROJECT, "data_dir": tmp_path, "approved_roots": (tmp_path,)}
    access = authorized_project_access(auth_store, registered["id"], **args)
    assert access.actor == owner["user_id"] and access.org_id == owner["organization_id"]
    viewer = auth_store.create_user("viewer@example.test", "correct horse battery staple")
    auth_store.create_membership(owner["organization_id"], viewer, authstore.VIEWER)
    export_args = {**args, "user_id": viewer, "action": rbac.EXPORT_PROJECT}
    with pytest.raises(PermissionError):
        authorized_project_access(auth_store, registered["id"], **export_args)
    auth_store.grant_project_permission(registered["id"], viewer, "EXPORT", granted_by=owner["user_id"])
    granted = authorized_project_access(auth_store, registered["id"], **export_args)
    assert rbac.EXPORT_PROJECT in granted.actions and rbac.ADOPT_PROJECT not in granted.actions
    for project_id, org_id in (("missing", owner["organization_id"]), (registered["id"], other_org)):
        with pytest.raises(authstore.ProjectNotFound):
            authorized_project_access(auth_store, project_id, **{**args, "active_org_id": org_id})
    # Remove membership directly in this isolated fixture to model external revocation.
    auth_store.db.execute("DELETE FROM membership WHERE user_id=?", (owner["user_id"],))
    auth_store.db.commit()
    with pytest.raises(authstore.ProjectNotFound):
        authorized_project_access(auth_store, registered["id"], **args)
