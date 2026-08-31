"""login() and the persisted, per-account/per-IP rate limiting behind it (D3)."""

from __future__ import annotations

import pytest

from formslang import authstore

PASSWORD = "correct horse battery staple"


def _bootstrap(auth_store):
    return auth_store.bootstrap_owner("owner@example.com", PASSWORD)


def test_a_correct_login_issues_a_session(auth_store):
    _bootstrap(auth_store)
    result = auth_store.login("owner@example.com", PASSWORD)
    assert result.ok
    assert result.session_token is not None
    assert auth_store.get_session(result.session_token) is not None


def test_login_scope_is_always_normal_mfa_is_not_wired_up_yet(auth_store):
    _bootstrap(auth_store)
    result = auth_store.login("owner@example.com", PASSWORD)
    assert result.scope == authstore.NORMAL


def test_a_wrong_password_is_refused(auth_store):
    _bootstrap(auth_store)
    result = auth_store.login("owner@example.com", "wrong password")
    assert not result.ok
    assert result.reason == "invalid_credentials"
    assert result.session_token is None


def test_an_unknown_email_is_refused_with_the_same_reason_as_a_wrong_password(auth_store):
    result = auth_store.login("nobody@example.com", PASSWORD)
    assert not result.ok
    assert result.reason == "invalid_credentials"


def test_a_disabled_user_is_refused(auth_store):
    result = _bootstrap(auth_store)
    auth_store.db.execute(
        "UPDATE user SET disabled_at = ? WHERE id = ?", ("2026-01-01 00:00:00", result["user_id"])
    )
    login_result = auth_store.login("owner@example.com", PASSWORD)
    assert not login_result.ok


def test_a_user_with_no_organization_cannot_log_in(auth_store):
    auth_store.create_user("lonely@example.com", PASSWORD)
    result = auth_store.login("lonely@example.com", PASSWORD)
    assert not result.ok
    assert result.reason == "no_organization"


def test_a_user_in_two_organizations_must_pick_one(auth_store):
    org1 = auth_store.create_organization("acme", "Acme")
    org2 = auth_store.create_organization("beta", "Beta")
    user_id = auth_store.create_user("dev@example.com", PASSWORD)
    auth_store.create_membership(org1, user_id, authstore.DEVELOPER)
    auth_store.create_membership(org2, user_id, authstore.ADMIN)
    result = auth_store.login("dev@example.com", PASSWORD)
    assert not result.ok
    assert result.reason == "organization_required"
    assert {m["org_id"] for m in result.organizations} == {org1, org2}
    picked = auth_store.login("dev@example.com", PASSWORD, org_id=org2)
    assert picked.ok
    assert picked.active_org_id == org2


def test_picking_an_organization_the_user_does_not_belong_to_is_rejected(auth_store):
    org1 = auth_store.create_organization("acme", "Acme")
    org2 = auth_store.create_organization("beta", "Beta")
    user_id = auth_store.create_user("dev@example.com", PASSWORD)
    auth_store.create_membership(org1, user_id, authstore.DEVELOPER)
    with pytest.raises(authstore.NotAMember):
        auth_store.login("dev@example.com", PASSWORD, org_id=org2)


def test_repeated_failures_lock_the_account_out(auth_store):
    _bootstrap(auth_store)
    for _ in range(authstore._RL_THRESHOLD):
        auth_store.login("owner@example.com", "wrong password")
    with pytest.raises(authstore.RateLimited):
        auth_store.login("owner@example.com", PASSWORD)


def test_a_correct_password_clears_the_failure_count(auth_store):
    _bootstrap(auth_store)
    for _ in range(authstore._RL_THRESHOLD - 1):
        auth_store.login("owner@example.com", "wrong password")
    result = auth_store.login("owner@example.com", PASSWORD)
    assert result.ok
    bucket = auth_store.db.execute(
        "SELECT * FROM rate_limit_bucket WHERE key = ?", ("login:account:owner@example.com",)
    ).fetchone()
    assert bucket is None


def test_rate_limit_state_survives_a_process_restart(tmp_path):
    path = tmp_path / "auth.db"
    store = authstore.AuthStore(path)
    store.bootstrap_owner("owner@example.com", PASSWORD)
    for _ in range(authstore._RL_THRESHOLD):
        store.login("owner@example.com", "wrong password")
    store.close()

    reopened = authstore.AuthStore(path)
    try:
        with pytest.raises(authstore.RateLimited):
            reopened.login("owner@example.com", PASSWORD)
    finally:
        reopened.close()


def test_an_ip_probing_many_different_emails_still_gets_locked_out(auth_store):
    for i in range(authstore._RL_THRESHOLD):
        auth_store.login(f"nobody{i}@example.com", PASSWORD, ip="203.0.113.9")
    with pytest.raises(authstore.RateLimited):
        auth_store.login("yet-another@example.com", PASSWORD, ip="203.0.113.9")


def test_a_different_ip_is_not_affected_by_another_ips_lockout(auth_store):
    _bootstrap(auth_store)
    for i in range(authstore._RL_THRESHOLD):
        auth_store.login(f"nobody{i}@example.com", PASSWORD, ip="203.0.113.9")
    # A fresh account, from a different IP, is unaffected.
    result = auth_store.login("owner@example.com", PASSWORD, ip="198.51.100.1")
    assert result.ok


def test_rate_limit_check_and_record_are_directly_testable(auth_store):
    key = "login:account:probe@example.com"
    auth_store.rate_limit_check(key)  # does not raise: no bucket yet
    for _ in range(authstore._RL_THRESHOLD):
        auth_store.rate_limit_record_failure(key)
    with pytest.raises(authstore.RateLimited):
        auth_store.rate_limit_check(key)
    auth_store.rate_limit_record_success(key)
    auth_store.rate_limit_check(key)  # cleared, does not raise
