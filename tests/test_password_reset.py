"""Assisted password reset at the AuthStore level (design doc SS7.5, D2):
who may issue for whom, the single-use expiring token, and what a redeem
does and pointedly does not do (no auto-login, MFA untouched, no account
enumeration). The last-Owner CLI path lives here too.
"""

from __future__ import annotations

import pytest

from formslang import authstore

from conftest import next_mfa_code, setup_confirmed_mfa

PASSWORD = "correct horse battery staple"
NEW_PASSWORD = "a brand new passphrase 42"


def _org(auth_store):
    """Owner + one member of every other role, all in one organization."""
    boot = auth_store.bootstrap_owner("owner@example.com", PASSWORD)
    org_id = boot["organization_id"]
    people = {authstore.OWNER: boot["user_id"]}
    for role, email in (
        (authstore.ADMIN, "admin@example.com"),
        (authstore.DEVELOPER, "dev@example.com"),
        (authstore.VIEWER, "viewer@example.com"),
    ):
        user_id = auth_store.create_user(email, PASSWORD)
        auth_store.create_membership(org_id, user_id, role)
        people[role] = user_id
    return org_id, people


def _issue(auth_store, org_id, people, by, target):
    return auth_store.issue_password_reset(
        issued_by=people[by], target_user_id=people[target], org_id=org_id,
    )


# -- who may issue for whom (SS7.5) ------------------------------------------


def test_an_admin_resets_a_developer_and_the_new_password_works(auth_store):
    org_id, people = _org(auth_store)
    token = _issue(auth_store, org_id, people, authstore.ADMIN, authstore.DEVELOPER)

    user_id = auth_store.redeem_password_reset(token, NEW_PASSWORD)
    assert user_id == people[authstore.DEVELOPER]
    assert auth_store.login("dev@example.com", NEW_PASSWORD).ok
    assert not auth_store.login("dev@example.com", PASSWORD).ok


def test_an_admin_resets_a_viewer(auth_store):
    org_id, people = _org(auth_store)
    token = _issue(auth_store, org_id, people, authstore.ADMIN, authstore.VIEWER)
    auth_store.redeem_password_reset(token, NEW_PASSWORD)
    assert auth_store.login("viewer@example.com", NEW_PASSWORD).ok


def test_an_admin_may_not_reset_another_admin(auth_store):
    org_id, people = _org(auth_store)
    other_admin = auth_store.create_user("admin2@example.com", PASSWORD)
    auth_store.create_membership(org_id, other_admin, authstore.ADMIN)
    with pytest.raises(PermissionError):
        auth_store.issue_password_reset(
            issued_by=people[authstore.ADMIN], target_user_id=other_admin, org_id=org_id,
        )


def test_an_admin_may_not_reset_an_owner(auth_store):
    org_id, people = _org(auth_store)
    with pytest.raises(PermissionError):
        _issue(auth_store, org_id, people, authstore.ADMIN, authstore.OWNER)


def test_an_owner_may_reset_an_admin(auth_store):
    org_id, people = _org(auth_store)
    token = _issue(auth_store, org_id, people, authstore.OWNER, authstore.ADMIN)
    auth_store.redeem_password_reset(token, NEW_PASSWORD)
    assert auth_store.login("admin@example.com", NEW_PASSWORD).ok


def test_an_owner_may_not_reset_another_owner(auth_store):
    """Owner-on-Owner goes through the host CLI, never HTTP -- the refusal
    says so."""
    org_id, people = _org(auth_store)
    other_owner = auth_store.create_user("owner2@example.com", PASSWORD)
    auth_store.create_membership(org_id, other_owner, authstore.OWNER)
    with pytest.raises(PermissionError, match="reset-owner"):
        auth_store.issue_password_reset(
            issued_by=people[authstore.OWNER], target_user_id=other_owner, org_id=org_id,
        )


def test_a_developer_may_not_issue_a_reset_at_all(auth_store):
    org_id, people = _org(auth_store)
    with pytest.raises(PermissionError):
        _issue(auth_store, org_id, people, authstore.DEVELOPER, authstore.VIEWER)


def test_a_target_outside_the_organization_is_refused(auth_store):
    org_id, people = _org(auth_store)
    outsider = auth_store.create_user("elsewhere@example.com", PASSWORD)
    with pytest.raises(authstore.UserNotFound):
        auth_store.issue_password_reset(
            issued_by=people[authstore.OWNER], target_user_id=outsider, org_id=org_id,
        )


# -- the token itself (single-use, expiring, superseded) ---------------------


def test_a_reset_token_is_single_use(auth_store):
    org_id, people = _org(auth_store)
    token = _issue(auth_store, org_id, people, authstore.OWNER, authstore.DEVELOPER)
    auth_store.redeem_password_reset(token, NEW_PASSWORD)
    with pytest.raises(ValueError, match="invalid or expired"):
        auth_store.redeem_password_reset(token, "yet another password")


def test_an_expired_reset_token_is_refused(auth_store):
    org_id, people = _org(auth_store)
    token = _issue(auth_store, org_id, people, authstore.OWNER, authstore.DEVELOPER)
    auth_store.db.execute(
        "UPDATE password_reset_token SET expires_at = '2000-01-01 00:00:00'"
    )
    with pytest.raises(ValueError, match="invalid or expired"):
        auth_store.redeem_password_reset(token, NEW_PASSWORD)


def test_issuing_again_supersedes_the_previous_token(auth_store):
    org_id, people = _org(auth_store)
    first = _issue(auth_store, org_id, people, authstore.OWNER, authstore.DEVELOPER)
    second = _issue(auth_store, org_id, people, authstore.OWNER, authstore.DEVELOPER)
    with pytest.raises(ValueError, match="invalid or expired"):
        auth_store.redeem_password_reset(first, NEW_PASSWORD)
    auth_store.redeem_password_reset(second, NEW_PASSWORD)


def test_a_bogus_expired_and_used_token_all_fail_with_the_same_message(auth_store):
    """No account enumeration (SS7.5): the caller cannot tell a token that
    never existed from one that expired or was already spent."""
    org_id, people = _org(auth_store)
    used = _issue(auth_store, org_id, people, authstore.OWNER, authstore.DEVELOPER)
    auth_store.redeem_password_reset(used, NEW_PASSWORD)

    messages = set()
    for bad in ("never-existed", used, ""):
        with pytest.raises(ValueError) as e:
            auth_store.redeem_password_reset(bad, "whatever password")
        messages.add(str(e.value))
    assert len(messages) == 1


def test_repeated_bad_redeems_from_one_ip_are_rate_limited(auth_store):
    for _i in range(authstore._RL_THRESHOLD):
        with pytest.raises(ValueError):
            auth_store.redeem_password_reset("nope", NEW_PASSWORD, ip="10.0.0.9")
    with pytest.raises(authstore.RateLimited):
        auth_store.redeem_password_reset("nope", NEW_PASSWORD, ip="10.0.0.9")


def test_an_empty_new_password_is_refused_before_touching_the_token(auth_store):
    org_id, people = _org(auth_store)
    token = _issue(auth_store, org_id, people, authstore.OWNER, authstore.DEVELOPER)
    with pytest.raises(ValueError, match="empty"):
        auth_store.redeem_password_reset(token, "")
    # The token survived the refused attempt.
    auth_store.redeem_password_reset(token, NEW_PASSWORD)


# -- what a redeem does and does not do (SS7.5.5) ----------------------------


def test_a_redeem_revokes_every_session_and_does_not_log_the_user_in(auth_store):
    org_id, people = _org(auth_store)
    dev_login = auth_store.login("dev@example.com", PASSWORD)
    assert auth_store.get_session(dev_login.session_token) is not None

    token = _issue(auth_store, org_id, people, authstore.OWNER, authstore.DEVELOPER)
    auth_store.redeem_password_reset(token, NEW_PASSWORD)

    assert auth_store.get_session(dev_login.session_token) is None
    row = auth_store.db.execute(
        "SELECT COUNT(*) AS n FROM session_token "
        "WHERE user_id = ? AND revoked_at IS NULL",
        (people[authstore.DEVELOPER],),
    ).fetchone()
    assert row["n"] == 0  # no auto-login: the redeem created no live session


def test_a_password_reset_preserves_confirmed_mfa(auth_store):
    """SS7.5.5: a reset never weakens the account -- the MFA step still
    stands between the new password and a NORMAL session."""
    org_id, people = _org(auth_store)
    setup_confirmed_mfa(auth_store, people[authstore.DEVELOPER])

    token = _issue(auth_store, org_id, people, authstore.OWNER, authstore.DEVELOPER)
    auth_store.redeem_password_reset(token, NEW_PASSWORD)

    result = auth_store.login("dev@example.com", NEW_PASSWORD)
    assert result.ok
    assert result.scope == authstore.MFA_PENDING
    assert auth_store.has_confirmed_mfa(people[authstore.DEVELOPER])


# -- last-Owner recovery over the CLI (SS7.5) --------------------------------


def test_the_cli_reset_recovers_an_owner_and_revokes_sessions(auth_store):
    org_id, people = _org(auth_store)
    mfa = setup_confirmed_mfa(auth_store, people[authstore.OWNER])

    pending = auth_store.login("owner@example.com", PASSWORD)
    normal = auth_store.complete_mfa_login(
        pending.session_token,
        next_mfa_code(auth_store, people[authstore.OWNER], mfa["secret"]),
    )

    out = auth_store.reset_owner_password_cli("owner@example.com", NEW_PASSWORD)
    assert out["user_id"] == people[authstore.OWNER]
    assert out["sessions_revoked"] >= 1
    assert auth_store.get_session(normal.session_token) is None
    # MFA preserved: the new password still lands on the MFA step.
    assert auth_store.login("owner@example.com", NEW_PASSWORD).scope == authstore.MFA_PENDING


def test_the_cli_reset_refuses_a_non_owner(auth_store):
    _org(auth_store)
    with pytest.raises(PermissionError, match="Owner accounts only"):
        auth_store.reset_owner_password_cli("dev@example.com", NEW_PASSWORD)


def test_the_cli_reset_refuses_an_unknown_email(auth_store):
    _org(auth_store)
    with pytest.raises(authstore.UserNotFound):
        auth_store.reset_owner_password_cli("nobody@example.com", NEW_PASSWORD)


# -- audit hygiene -----------------------------------------------------------


def test_the_reset_lifecycle_is_audited_without_leaking_the_token(auth_store):
    org_id, people = _org(auth_store)
    token = _issue(auth_store, org_id, people, authstore.OWNER, authstore.DEVELOPER)
    auth_store.redeem_password_reset(token, NEW_PASSWORD)

    events = auth_store.list_audit_events(limit=200)
    types = [e["event_type"] for e in events]
    assert "PASSWORD_RESET_ISSUED" in types
    assert "PASSWORD_RESET_COMPLETED" in types

    dumped = repr(events)
    assert token not in dumped
    assert NEW_PASSWORD not in dumped
    assert PASSWORD not in dumped
