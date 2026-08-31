"""Session lifecycle: creation, validity, revocation, limits, rotation, cleanup."""

from __future__ import annotations

import pytest

from formslang import authstore

PASSWORD = "correct horse battery staple"


def test_a_freshly_created_session_is_valid(auth_store):
    org_id = auth_store.create_organization("acme", "Acme")
    user_id = auth_store.create_user("dev@example.com", PASSWORD)
    auth_store.create_membership(org_id, user_id, authstore.DEVELOPER)
    raw_token, session = auth_store.create_session(user_id, org_id)
    fetched = auth_store.get_session(raw_token)
    assert fetched is not None
    assert fetched["user_id"] == user_id
    assert fetched["active_org_id"] == org_id
    assert session["scope"] == authstore.NORMAL


def test_an_unknown_token_returns_none(auth_store):
    assert auth_store.get_session("not-a-real-token") is None


def test_a_revoked_session_is_no_longer_valid(auth_store):
    user_id = auth_store.create_user("dev@example.com", PASSWORD)
    raw_token, _session = auth_store.create_session(user_id, None)
    auth_store.revoke_session(raw_token)
    assert auth_store.get_session(raw_token) is None


def test_an_expired_session_is_no_longer_valid(auth_store):
    user_id = auth_store.create_user("dev@example.com", PASSWORD)
    raw_token, session = auth_store.create_session(user_id, None)
    auth_store.db.execute(
        "UPDATE session_token SET expires_at = '2000-01-01 00:00:00' WHERE id = ?",
        (session["id"],),
    )
    assert auth_store.get_session(raw_token) is None


def test_get_session_touches_last_seen_at(auth_store):
    user_id = auth_store.create_user("dev@example.com", PASSWORD)
    raw_token, session = auth_store.create_session(user_id, None)
    auth_store.db.execute(
        "UPDATE session_token SET last_seen_at = '2000-01-01 00:00:00' WHERE id = ?",
        (session["id"],),
    )
    refreshed = auth_store.get_session(raw_token)
    assert refreshed["last_seen_at"] != "2000-01-01 00:00:00"


def test_creating_a_session_beyond_the_limit_revokes_the_oldest(auth_store):
    user_id = auth_store.create_user("dev@example.com", PASSWORD)
    old = []
    for i in range(authstore.MAX_SESSIONS_PER_USER):
        raw_token, session = auth_store.create_session(user_id, None)
        auth_store.db.execute(
            "UPDATE session_token SET created_at = ? WHERE id = ?",
            (f"2020-01-01 00:00:{i:02d}", session["id"]),
        )
        old.append(raw_token)
    newest_raw_token, _newest_session = auth_store.create_session(user_id, None)
    assert auth_store.get_session(old[0]) is None
    assert auth_store.get_session(newest_raw_token) is not None
    still_alive = sum(1 for raw_token in old[1:] if auth_store.get_session(raw_token) is not None)
    assert still_alive == authstore.MAX_SESSIONS_PER_USER - 1


def test_creating_a_session_with_an_unknown_scope_is_rejected(auth_store):
    user_id = auth_store.create_user("dev@example.com", PASSWORD)
    with pytest.raises(ValueError):
        auth_store.create_session(user_id, None, scope="WHATEVER")


def test_switching_organization_revokes_the_old_token_and_issues_a_new_one(auth_store):
    org1 = auth_store.create_organization("acme", "Acme")
    org2 = auth_store.create_organization("beta", "Beta")
    user_id = auth_store.create_user("dev@example.com", PASSWORD)
    auth_store.create_membership(org1, user_id, authstore.DEVELOPER)
    auth_store.create_membership(org2, user_id, authstore.ADMIN)
    raw_token, _session = auth_store.create_session(user_id, org1)
    _new_token, new_session = auth_store.switch_organization(raw_token, org2)
    assert auth_store.get_session(raw_token) is None
    assert new_session["active_org_id"] == org2


def test_switching_to_an_organization_the_user_does_not_belong_to_is_refused(auth_store):
    org1 = auth_store.create_organization("acme", "Acme")
    org2 = auth_store.create_organization("beta", "Beta")
    user_id = auth_store.create_user("dev@example.com", PASSWORD)
    auth_store.create_membership(org1, user_id, authstore.DEVELOPER)
    raw_token, _session = auth_store.create_session(user_id, org1)
    with pytest.raises(authstore.NotAMember):
        auth_store.switch_organization(raw_token, org2)
    assert auth_store.get_session(raw_token) is not None


def test_switching_organization_with_an_invalid_token_is_refused(auth_store):
    org_id = auth_store.create_organization("acme", "Acme")
    with pytest.raises(authstore.SessionNotFound):
        auth_store.switch_organization("not-a-real-token", org_id)


def test_only_a_normal_session_can_switch_organizations(auth_store):
    org1 = auth_store.create_organization("acme", "Acme")
    org2 = auth_store.create_organization("beta", "Beta")
    user_id = auth_store.create_user("dev@example.com", PASSWORD)
    auth_store.create_membership(org2, user_id, authstore.DEVELOPER)
    raw_token, _session = auth_store.create_session(user_id, org1, scope=authstore.MFA_PENDING)
    with pytest.raises(ValueError):
        auth_store.switch_organization(raw_token, org2)


def test_revoke_sessions_for_user_logs_out_everywhere(auth_store):
    user_id = auth_store.create_user("dev@example.com", PASSWORD)
    token1, _ = auth_store.create_session(user_id, None)
    token2, _ = auth_store.create_session(user_id, None)
    auth_store.revoke_sessions_for_user(user_id)
    assert auth_store.get_session(token1) is None
    assert auth_store.get_session(token2) is None


def test_revoke_sessions_for_user_can_be_scoped_to_one_organization(auth_store):
    org1 = auth_store.create_organization("acme", "Acme")
    org2 = auth_store.create_organization("beta", "Beta")
    user_id = auth_store.create_user("dev@example.com", PASSWORD)
    token1, _ = auth_store.create_session(user_id, org1)
    token2, _ = auth_store.create_session(user_id, org2)
    auth_store.revoke_sessions_for_user(user_id, org_id=org1)
    assert auth_store.get_session(token1) is None
    assert auth_store.get_session(token2) is not None


def test_cleanup_expired_sessions_deletes_only_expired_rows(auth_store):
    user_id = auth_store.create_user("dev@example.com", PASSWORD)
    _raw_token, session = auth_store.create_session(user_id, None)
    live_token, _live_session = auth_store.create_session(user_id, None)
    auth_store.db.execute(
        "UPDATE session_token SET expires_at = '2000-01-01 00:00:00' WHERE id = ?",
        (session["id"],),
    )
    deleted = auth_store.cleanup_expired_sessions()
    assert deleted == 1
    row = auth_store.db.execute(
        "SELECT id FROM session_token WHERE id = ?", (session["id"],)
    ).fetchone()
    assert row is None
    assert auth_store.get_session(live_token) is not None
