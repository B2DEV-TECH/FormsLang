"""The RBAC matrix (design §5) -- pure functions, no database."""

from __future__ import annotations

import pytest

from formslang import rbac
from formslang.authstore import ADMIN, DEVELOPER, OWNER, VIEWER


@pytest.mark.parametrize(
    "action,allowed_roles",
    [
        (rbac.RENAME_ORGANIZATION, {OWNER}),
        (rbac.DELETE_ORGANIZATION, {OWNER}),
        (rbac.TRANSFER_OWNERSHIP, {OWNER}),
        (rbac.INVITE_MEMBER, {OWNER, ADMIN}),
        (rbac.REMOVE_MEMBER, {OWNER, ADMIN}),
        (rbac.CHANGE_MEMBER_ROLE, {OWNER, ADMIN}),
        (rbac.GRANT_OWNER, {OWNER}),
        (rbac.CREATE_PROJECT, {OWNER, ADMIN, DEVELOPER}),
        (rbac.DELETE_PROJECT, {OWNER, ADMIN, DEVELOPER}),
        (rbac.VIEW_PROJECT, {OWNER, ADMIN, DEVELOPER, VIEWER}),
        (rbac.RUN_CONVERSION, {OWNER, ADMIN, DEVELOPER}),
        (rbac.APPROVE_AI_PROPOSAL, {OWNER, ADMIN, DEVELOPER}),
        (rbac.EXPORT_PROJECT, {OWNER, ADMIN, DEVELOPER}),
        (rbac.GRANT_EXPORT_PERMISSION, {OWNER, ADMIN, DEVELOPER}),
        (rbac.ADOPT_PROJECT, {OWNER, ADMIN}),
        (rbac.CONFIGURE_PROVIDER, {OWNER, ADMIN}),
        (rbac.VIEW_AUDIT_LOG, {OWNER, ADMIN}),
    ],
)
def test_the_matrix_matches_the_design_doc_for_every_role(action, allowed_roles):
    for role in (OWNER, ADMIN, DEVELOPER, VIEWER):
        assert rbac.has_permission(role, action) == (role in allowed_roles), (action, role)


def test_has_permission_rejects_an_unknown_role():
    with pytest.raises(ValueError):
        rbac.has_permission("SUPERUSER", rbac.VIEW_PROJECT)


def test_has_permission_rejects_an_unknown_action():
    with pytest.raises(ValueError):
        rbac.has_permission(OWNER, "launch_the_missiles")


def test_only_an_owner_can_grant_the_owner_role():
    assert rbac.can_change_member_role(OWNER, OWNER) is True
    assert rbac.can_change_member_role(ADMIN, OWNER) is False


def test_an_admin_can_change_a_member_to_admin_or_below():
    assert rbac.can_change_member_role(ADMIN, DEVELOPER) is True
    assert rbac.can_change_member_role(ADMIN, ADMIN) is True


def test_a_developer_cannot_change_anyones_role():
    assert rbac.can_change_member_role(DEVELOPER, VIEWER) is False


def test_owner_admin_and_developer_can_always_export():
    for role in (OWNER, ADMIN, DEVELOPER):
        assert rbac.can_export(role) is True
        assert rbac.can_export(role, has_project_permission=False) is True


def test_a_viewer_can_only_export_with_a_matching_project_permission():
    assert rbac.can_export(VIEWER, has_project_permission=False) is False
    assert rbac.can_export(VIEWER, has_project_permission=True) is True


def test_can_export_rejects_an_unknown_role():
    with pytest.raises(ValueError):
        rbac.can_export("SUPERUSER")


def test_owner_can_reset_anyone_except_another_owner():
    assert rbac.can_reset_password(OWNER, ADMIN) is True
    assert rbac.can_reset_password(OWNER, DEVELOPER) is True
    assert rbac.can_reset_password(OWNER, VIEWER) is True
    assert rbac.can_reset_password(OWNER, OWNER) is False


def test_admin_can_reset_developer_and_viewer_only():
    assert rbac.can_reset_password(ADMIN, DEVELOPER) is True
    assert rbac.can_reset_password(ADMIN, VIEWER) is True
    assert rbac.can_reset_password(ADMIN, ADMIN) is False
    assert rbac.can_reset_password(ADMIN, OWNER) is False


def test_developer_and_viewer_can_never_reset_anyone_elses_password():
    for actor in (DEVELOPER, VIEWER):
        for target in (OWNER, ADMIN, DEVELOPER, VIEWER):
            assert rbac.can_reset_password(actor, target) is False


def test_can_reset_password_rejects_an_unknown_actor_role():
    with pytest.raises(ValueError):
        rbac.can_reset_password("SUPERUSER", VIEWER)


def test_every_action_matches_a_row_actually_defined():
    assert set(rbac.ACTIONS) == set(rbac._MATRIX)
