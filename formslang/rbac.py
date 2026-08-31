"""The RBAC matrix (design §5). Pure functions -- no I/O, no database.

Every function here answers "is this allowed", given role names the caller
already fetched from a fresh :class:`~formslang.authstore.Membership` row.
Nothing in this module trusts a cached or stale role: re-deriving that
membership on every request is the caller's job (the HTTP layer, in
Phase 2), same as the design doc requires ("every check runs server-side,
from a fresh Membership row, every request").

Two rules the matrix enforces are *not* here, on purpose, because they are
not role-vs-role questions:

- **The last Owner of an organization can never be removed or demoted.**
  That is a membership-count question, only answerable against the live
  database, so it lives in :func:`formslang.authstore.AuthStore.update_membership_role`
  and :func:`~formslang.authstore.AuthStore.remove_membership`, inside the
  same transaction that would do the change.
- **Viewing or resetting another user's MFA secret.** The design doc's
  answer is "nobody -- the route does not exist" (§5). There is nothing to
  gate because there is nothing to call; MFA itself is Phase 3 (see
  :mod:`formslang.authstore`'s module docstring).
"""

from __future__ import annotations

from .authstore import ADMIN, DEVELOPER, OWNER, ROLES, VIEWER

# -- actions ------------------------------------------------------------------

RENAME_ORGANIZATION = "rename_organization"
DELETE_ORGANIZATION = "delete_organization"
TRANSFER_OWNERSHIP = "transfer_ownership"
INVITE_MEMBER = "invite_member"
REMOVE_MEMBER = "remove_member"
CHANGE_MEMBER_ROLE = "change_member_role"  # up to Admin -- granting Owner is separate, see can_change_member_role
GRANT_OWNER = "grant_owner"
CREATE_PROJECT = "create_project"
DELETE_PROJECT = "delete_project"
VIEW_PROJECT = "view_project"  # open a project, read-only
RUN_CONVERSION = "run_conversion"  # run analysis, convert units -- a write
APPROVE_AI_PROPOSAL = "approve_ai_proposal"
EXPORT_PROJECT = "export_project"  # Viewer handled separately -- see can_export
GRANT_EXPORT_PERMISSION = "grant_export_permission"
ADOPT_PROJECT = "adopt_project"
CONFIGURE_PROVIDER = "configure_provider"
VIEW_AUDIT_LOG = "view_audit_log"

_MATRIX: dict[str, frozenset[str]] = {
    RENAME_ORGANIZATION: frozenset({OWNER}),
    DELETE_ORGANIZATION: frozenset({OWNER}),
    TRANSFER_OWNERSHIP: frozenset({OWNER}),
    INVITE_MEMBER: frozenset({OWNER, ADMIN}),
    REMOVE_MEMBER: frozenset({OWNER, ADMIN}),
    CHANGE_MEMBER_ROLE: frozenset({OWNER, ADMIN}),
    GRANT_OWNER: frozenset({OWNER}),
    CREATE_PROJECT: frozenset({OWNER, ADMIN, DEVELOPER}),
    DELETE_PROJECT: frozenset({OWNER, ADMIN, DEVELOPER}),
    VIEW_PROJECT: frozenset({OWNER, ADMIN, DEVELOPER, VIEWER}),
    RUN_CONVERSION: frozenset({OWNER, ADMIN, DEVELOPER}),
    APPROVE_AI_PROPOSAL: frozenset({OWNER, ADMIN, DEVELOPER}),
    EXPORT_PROJECT: frozenset({OWNER, ADMIN, DEVELOPER}),
    GRANT_EXPORT_PERMISSION: frozenset({OWNER, ADMIN, DEVELOPER}),
    ADOPT_PROJECT: frozenset({OWNER, ADMIN}),
    CONFIGURE_PROVIDER: frozenset({OWNER, ADMIN}),
    VIEW_AUDIT_LOG: frozenset({OWNER, ADMIN}),
}

ACTIONS = tuple(_MATRIX)


def has_permission(role: str, action: str) -> bool:
    """The flat, per-role/per-action matrix. No cross-role or ownership logic."""
    if role not in ROLES:
        raise ValueError(f"unknown role {role!r}")
    if action not in _MATRIX:
        raise ValueError(f"unknown action {action!r}")
    return role in _MATRIX[action]


def can_change_member_role(actor_role: str, new_role: str) -> bool:
    """Whether ``actor_role`` may set a member's role to ``new_role``.

    Granting Owner is its own, Owner-only action (§5's "Grant the Owner
    role" row) -- Admin can change roles generally, but never up to Owner.
    Demoting *out of* Owner is the same ``CHANGE_MEMBER_ROLE`` action; the
    last-Owner protection that also guards it lives in ``authstore``, not
    here.
    """
    if new_role == OWNER:
        return actor_role == OWNER
    return has_permission(actor_role, CHANGE_MEMBER_ROLE)


def can_export(role: str, has_project_permission: bool = False) -> bool:
    """Owner/Admin/Developer can always export; a Viewer needs a matching
    ``project_permission(EXPORT)`` row for that specific project."""
    if role in (OWNER, ADMIN, DEVELOPER):
        return True
    if role == VIEWER:
        return has_project_permission
    raise ValueError(f"unknown role {role!r}")


def can_reset_password(actor_role: str, target_role: str) -> bool:
    """D2's cross-role restriction on *initiating a reset for another member*.

    Not for a user's own password -- resetting your own is always allowed
    for every role and is not a cross-role question, so it is not modeled
    here; the caller should short-circuit on ``actor_user_id == target_user_id``
    before ever reaching this function.
    """
    if actor_role == OWNER:
        return target_role != OWNER
    if actor_role == ADMIN:
        return target_role in (DEVELOPER, VIEWER)
    if actor_role == DEVELOPER or actor_role == VIEWER:
        return False
    raise ValueError(f"unknown role {actor_role!r}")
