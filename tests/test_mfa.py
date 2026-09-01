"""TOTP MFA at the AuthStore level (design doc §7.1-§7.4, D6): enrollment,
two-consecutive-code confirmation, login gating by scope, replay protection,
recovery codes, disable, and fail-closed behavior when the OS credential
store is unavailable.

The two names the design doc's §12 test plan calls out by name --
test_the_same_totp_code_is_rejected_on_replay and
test_mfa_operations_fail_closed_when_the_os_credential_store_is_unavailable
-- live here.
"""

from __future__ import annotations

import threading
import time

import pytest
from conftest import next_mfa_code, setup_confirmed_mfa

from formslang import authstore, secrets, totp

PASSWORD = "correct horse battery staple"


def _owner(auth_store):
    return auth_store.bootstrap_owner("owner@example.com", PASSWORD)


def _developer(auth_store, boot):
    dev_id = auth_store.create_user("dev@example.com", PASSWORD)
    auth_store.create_membership(boot["organization_id"], dev_id, authstore.DEVELOPER)
    return dev_id


# -- login gating by scope (§7.1/§7.2) ---------------------------------------


def test_an_owner_without_confirmed_mfa_only_gets_an_enrollment_session(auth_store):
    """Mandatory enrollment: a privileged account that has never confirmed
    MFA -- including one that predates MFA existing -- never receives a
    NORMAL session at login."""
    _owner(auth_store)
    result = auth_store.login("owner@example.com", PASSWORD)
    assert result.ok
    assert result.scope == authstore.BOOTSTRAP_MFA
    assert result.mfa_enrollment_required
    assert not result.mfa_required


def test_an_admin_without_confirmed_mfa_only_gets_an_enrollment_session(auth_store):
    boot = _owner(auth_store)
    admin_id = auth_store.create_user("admin@example.com", PASSWORD)
    auth_store.create_membership(boot["organization_id"], admin_id, authstore.ADMIN)
    result = auth_store.login("admin@example.com", PASSWORD)
    assert result.scope == authstore.BOOTSTRAP_MFA
    assert result.mfa_enrollment_required


def test_a_developer_without_mfa_still_gets_a_normal_session(auth_store):
    """MFA is mandatory for Owner/Admin; for other roles in local mode it
    stays optional (§6), so nothing changes for them."""
    boot = _owner(auth_store)
    _developer(auth_store, boot)
    result = auth_store.login("dev@example.com", PASSWORD)
    assert result.scope == authstore.NORMAL
    assert not result.mfa_required
    assert not result.mfa_enrollment_required


def test_a_user_with_confirmed_mfa_gets_a_pending_session_not_a_normal_one(auth_store):
    boot = _owner(auth_store)
    setup_confirmed_mfa(auth_store, boot["user_id"])
    result = auth_store.login("owner@example.com", PASSWORD)
    assert result.ok
    assert result.scope == authstore.MFA_PENDING
    assert result.mfa_required
    session = auth_store.get_session(result.session_token)
    assert session["scope"] == authstore.MFA_PENDING


def test_completing_the_mfa_step_exchanges_the_pending_session_for_a_normal_one(auth_store):
    boot = _owner(auth_store)
    mfa = setup_confirmed_mfa(auth_store, boot["user_id"])
    pending = auth_store.login("owner@example.com", PASSWORD)
    code = next_mfa_code(auth_store, boot["user_id"], mfa["secret"])
    result = auth_store.complete_mfa_login(pending.session_token, code)
    assert result.ok
    assert result.scope == authstore.NORMAL
    assert auth_store.get_session(result.session_token)["scope"] == authstore.NORMAL
    # The pending token is spent.
    assert auth_store.get_session(pending.session_token) is None


def test_a_wrong_code_does_not_complete_the_mfa_step(auth_store):
    boot = _owner(auth_store)
    setup_confirmed_mfa(auth_store, boot["user_id"])
    pending = auth_store.login("owner@example.com", PASSWORD)
    with pytest.raises(authstore.InvalidMfaCode):
        auth_store.complete_mfa_login(pending.session_token, "000000")
    # The pending session survives for another try.
    assert auth_store.get_session(pending.session_token) is not None


def test_a_normal_session_cannot_be_fed_to_the_mfa_step(auth_store):
    boot = _owner(auth_store)
    _developer(auth_store, boot)
    result = auth_store.login("dev@example.com", PASSWORD)
    with pytest.raises(ValueError):
        auth_store.complete_mfa_login(result.session_token, "123456")


# -- enrollment and confirmation (§7.3) --------------------------------------


def test_enrollment_returns_the_secret_and_uri_and_stores_neither_in_the_db(auth_store):
    boot = _owner(auth_store)
    enrollment = auth_store.mfa_enroll(boot["user_id"])
    assert enrollment["secret"]
    assert enrollment["otpauth_uri"].startswith("otpauth://totp/")
    raw_db = (auth_store.path).read_bytes()
    assert enrollment["secret"].encode("ascii") not in raw_db


def test_a_copied_auth_db_reveals_no_mfa_secret_even_after_confirmation(auth_store):
    """The D6 property in one test: auth.db, taken in isolation, must be
    worthless for minting TOTP codes -- the secret lives only in the OS
    credential store."""
    boot = _owner(auth_store)
    mfa = setup_confirmed_mfa(auth_store, boot["user_id"])
    auth_store.db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    raw_db = (auth_store.path).read_bytes()
    assert mfa["secret"].encode("ascii") not in raw_db
    for code in mfa["recovery_codes"]:
        assert code.encode("ascii") not in raw_db
        assert code.replace("-", "").encode("ascii") not in raw_db


def test_confirmation_requires_two_consecutive_codes(auth_store):
    boot = _owner(auth_store)
    enrollment = auth_store.mfa_enroll(boot["user_id"])
    secret = enrollment["secret"]
    now = time.time()
    same_code = totp.generate_code(secret, at=now)
    with pytest.raises(authstore.InvalidMfaCode):
        auth_store.mfa_confirm(boot["user_id"], same_code, same_code)
    assert not auth_store.has_confirmed_mfa(boot["user_id"])


def test_confirmation_with_consecutive_codes_succeeds_and_returns_recovery_codes(auth_store):
    boot = _owner(auth_store)
    enrollment = auth_store.mfa_enroll(boot["user_id"])
    secret = enrollment["secret"]
    now = time.time()
    codes = auth_store.mfa_confirm(
        boot["user_id"],
        totp.generate_code(secret, at=now),
        totp.generate_code(secret, at=now + totp.PERIOD_SECONDS),
    )
    assert len(codes) == authstore.MFA_RECOVERY_CODE_COUNT
    assert auth_store.has_confirmed_mfa(boot["user_id"])


def test_a_new_enrollment_invalidates_the_previous_unconfirmed_one(auth_store):
    boot = _owner(auth_store)
    first = auth_store.mfa_enroll(boot["user_id"])
    second = auth_store.mfa_enroll(boot["user_id"])
    assert first["secret"] != second["secret"]
    now = time.time()
    with pytest.raises(authstore.InvalidMfaCode):
        auth_store.mfa_confirm(
            boot["user_id"],
            totp.generate_code(first["secret"], at=now),
            totp.generate_code(first["secret"], at=now + totp.PERIOD_SECONDS),
        )
    codes = auth_store.mfa_confirm(
        boot["user_id"],
        totp.generate_code(second["secret"], at=now),
        totp.generate_code(second["secret"], at=now + totp.PERIOD_SECONDS),
    )
    assert codes


def test_enrolling_again_after_confirmation_is_refused(auth_store):
    """No endpoint may ever return a confirmed secret again -- and
    re-enrolling would silently rotate it without proof of possession."""
    boot = _owner(auth_store)
    setup_confirmed_mfa(auth_store, boot["user_id"])
    with pytest.raises(authstore.MfaAlreadyConfirmed):
        auth_store.mfa_enroll(boot["user_id"])


def test_an_expired_enrollment_cannot_be_confirmed(auth_store):
    boot = _owner(auth_store)
    enrollment = auth_store.mfa_enroll(boot["user_id"])
    stale = "2020-01-01 00:00:00"
    auth_store.db.execute(
        "UPDATE mfa_secret SET enrolled_at = ? WHERE user_id = ?", (stale, boot["user_id"])
    )
    secret = enrollment["secret"]
    now = time.time()
    with pytest.raises(authstore.MfaEnrollmentExpired):
        auth_store.mfa_confirm(
            boot["user_id"],
            totp.generate_code(secret, at=now),
            totp.generate_code(secret, at=now + totp.PERIOD_SECONDS),
        )
    # The expired enrollment is gone entirely -- row and vault entry.
    assert auth_store.get_mfa(boot["user_id"]) is None
    assert secrets.get_secret(secrets.SERVICE, f"mfa-totp:{boot['user_id']}") == ""


def test_cleanup_sweeps_expired_unconfirmed_enrollments_but_not_confirmed_ones(auth_store):
    boot = _owner(auth_store)
    dev_id = _developer(auth_store, boot)
    setup_confirmed_mfa(auth_store, boot["user_id"])
    auth_store.mfa_enroll(dev_id)
    auth_store.db.execute(
        "UPDATE mfa_secret SET enrolled_at = '2020-01-01 00:00:00' WHERE user_id = ?",
        (dev_id,),
    )
    auth_store.cleanup_expired_sessions()
    assert auth_store.get_mfa(dev_id) is None
    assert auth_store.has_confirmed_mfa(boot["user_id"])


# -- replay protection (§7.3.5) ----------------------------------------------


def test_the_same_totp_code_is_rejected_on_replay(auth_store):
    boot = _owner(auth_store)
    mfa = setup_confirmed_mfa(auth_store, boot["user_id"])
    pending = auth_store.login("owner@example.com", PASSWORD)
    code = next_mfa_code(auth_store, boot["user_id"], mfa["secret"])
    auth_store.complete_mfa_login(pending.session_token, code)

    replay = auth_store.login("owner@example.com", PASSWORD)
    with pytest.raises(authstore.InvalidMfaCode):
        auth_store.complete_mfa_login(replay.session_token, code)


def test_concurrent_validations_of_the_same_code_accept_it_at_most_once(auth_store):
    """§7.3.4's transaction requirement, exercised for real: many threads
    race the same valid code through the same store; the watermark update
    inside BEGIN IMMEDIATE lets exactly one win."""
    boot = _owner(auth_store)
    mfa = setup_confirmed_mfa(auth_store, boot["user_id"])
    code = next_mfa_code(auth_store, boot["user_id"], mfa["secret"])
    pendings = [
        auth_store.login("owner@example.com", PASSWORD).session_token for _ in range(4)
    ]
    outcomes: list[bool] = []
    lock = threading.Lock()

    def attempt(token: str) -> None:
        try:
            auth_store.complete_mfa_login(token, code)
            ok = True
        except (authstore.AuthStoreError, ValueError):
            ok = False
        with lock:
            outcomes.append(ok)

    threads = [threading.Thread(target=attempt, args=(t,)) for t in pendings]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert outcomes.count(True) == 1


# -- recovery codes (§7.3) ----------------------------------------------------


def test_a_recovery_code_completes_login_and_revokes_every_other_session(auth_store):
    boot = _owner(auth_store)
    mfa = setup_confirmed_mfa(auth_store, boot["user_id"])
    pending1 = auth_store.login("owner@example.com", PASSWORD)
    code = next_mfa_code(auth_store, boot["user_id"], mfa["secret"])
    normal = auth_store.complete_mfa_login(pending1.session_token, code)

    pending2 = auth_store.login("owner@example.com", PASSWORD)
    result = auth_store.complete_mfa_login(pending2.session_token, mfa["recovery_codes"][0])
    assert result.ok
    assert result.scope == authstore.NORMAL
    # The previously issued NORMAL session died with the recovery use.
    assert auth_store.get_session(normal.session_token) is None


def test_a_recovery_code_is_single_use(auth_store):
    boot = _owner(auth_store)
    mfa = setup_confirmed_mfa(auth_store, boot["user_id"])
    used = mfa["recovery_codes"][0]
    pending = auth_store.login("owner@example.com", PASSWORD)
    auth_store.complete_mfa_login(pending.session_token, used)
    pending2 = auth_store.login("owner@example.com", PASSWORD)
    with pytest.raises(authstore.InvalidMfaCode):
        auth_store.complete_mfa_login(pending2.session_token, used)


def test_concurrent_uses_of_the_same_recovery_code_succeed_at_most_once(auth_store):
    boot = _owner(auth_store)
    mfa = setup_confirmed_mfa(auth_store, boot["user_id"])
    code = mfa["recovery_codes"][0]
    pendings = [
        auth_store.login("owner@example.com", PASSWORD).session_token for _ in range(4)
    ]
    outcomes: list[bool] = []
    lock = threading.Lock()

    def attempt(token: str) -> None:
        try:
            auth_store.complete_mfa_login(token, code)
            ok = True
        except (authstore.AuthStoreError, ValueError):
            ok = False
        with lock:
            outcomes.append(ok)

    threads = [threading.Thread(target=attempt, args=(t,)) for t in pendings]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert outcomes.count(True) == 1


def test_regenerating_recovery_codes_revokes_all_previous_ones(auth_store):
    boot = _owner(auth_store)
    mfa = setup_confirmed_mfa(auth_store, boot["user_id"])
    code = next_mfa_code(auth_store, boot["user_id"], mfa["secret"])
    fresh = auth_store.mfa_regenerate_recovery_codes(boot["user_id"], code)
    assert len(fresh) == authstore.MFA_RECOVERY_CODE_COUNT
    assert set(fresh).isdisjoint(mfa["recovery_codes"])
    pending = auth_store.login("owner@example.com", PASSWORD)
    with pytest.raises(authstore.InvalidMfaCode):
        auth_store.complete_mfa_login(pending.session_token, mfa["recovery_codes"][1])


def test_recovery_codes_carry_at_least_128_bits_and_are_stored_hashed_only(auth_store):
    boot = _owner(auth_store)
    mfa = setup_confirmed_mfa(auth_store, boot["user_id"])
    for code in mfa["recovery_codes"]:
        assert len(code.replace("-", "")) == 32  # 32 hex chars = 128 bits
    rows = auth_store.db.execute("SELECT code_hash FROM mfa_recovery_code").fetchall()
    hashes = {r["code_hash"] for r in rows}
    for code in mfa["recovery_codes"]:
        assert code not in hashes
        assert code.replace("-", "") not in hashes


# -- disable (§7.4) -----------------------------------------------------------


def test_disabling_mfa_requires_password_and_code_and_revokes_every_session(auth_store):
    boot = _owner(auth_store)
    mfa = setup_confirmed_mfa(auth_store, boot["user_id"])
    pending = auth_store.login("owner@example.com", PASSWORD)
    code = next_mfa_code(auth_store, boot["user_id"], mfa["secret"])
    normal = auth_store.complete_mfa_login(pending.session_token, code)

    with pytest.raises(authstore.InvalidMfaCode):
        auth_store.mfa_disable(
            boot["user_id"], "wrong password",
            next_mfa_code(auth_store, boot["user_id"], mfa["secret"]),
        )
    assert auth_store.has_confirmed_mfa(boot["user_id"])

    code2 = next_mfa_code(auth_store, boot["user_id"], mfa["secret"])
    auth_store.mfa_disable(boot["user_id"], PASSWORD, code2)
    assert not auth_store.has_confirmed_mfa(boot["user_id"])
    assert auth_store.get_session(normal.session_token) is None
    assert secrets.get_secret(secrets.SERVICE, f"mfa-totp:{boot['user_id']}") == ""


def test_disabling_mfa_accepts_a_recovery_code_instead_of_totp(auth_store):
    boot = _owner(auth_store)
    mfa = setup_confirmed_mfa(auth_store, boot["user_id"])
    auth_store.mfa_disable(boot["user_id"], PASSWORD, mfa["recovery_codes"][0])
    assert not auth_store.has_confirmed_mfa(boot["user_id"])


# -- fail-closed vault behavior (§2.3, §12) -----------------------------------


def test_mfa_operations_fail_closed_when_the_os_credential_store_is_unavailable(
    auth_store, monkeypatch
):
    """With no credential store at all, enrollment refuses to start and a
    confirmed user's verification refuses to pass -- an unreachable vault is
    an error, never a bypass and never a plaintext fallback."""
    boot = _owner(auth_store)
    mfa = setup_confirmed_mfa(auth_store, boot["user_id"])
    pending = auth_store.login("owner@example.com", PASSWORD)

    monkeypatch.setenv("FORMSLANG_SECRET_BACKEND", "none")
    code = next_mfa_code(auth_store, boot["user_id"], mfa["secret"])
    with pytest.raises(secrets.SecureStorageUnavailable):
        auth_store.complete_mfa_login(pending.session_token, code)
    # Still MFA_PENDING -- the failure did not mint a NORMAL session.
    assert auth_store.get_session(pending.session_token)["scope"] == authstore.MFA_PENDING

    dev_boot = auth_store.create_user("dev@example.com", PASSWORD)
    with pytest.raises(secrets.SecureStorageUnavailable):
        auth_store.mfa_enroll(dev_boot)
    assert auth_store.get_mfa(dev_boot) is None


def test_a_confirmed_user_whose_vault_entry_vanished_cannot_log_in(auth_store):
    """auth.db says MFA is confirmed but the OS store has no secret (the
    database was copied to another machine, or the vault was wiped): that
    is a hard error, not a free pass."""
    boot = _owner(auth_store)
    setup_confirmed_mfa(auth_store, boot["user_id"])
    secrets.delete_secret(secrets.SERVICE, f"mfa-totp:{boot['user_id']}")
    pending = auth_store.login("owner@example.com", PASSWORD)
    with pytest.raises(secrets.SecureStorageUnavailable):
        auth_store.complete_mfa_login(pending.session_token, "123456")


# -- rate limiting covers the MFA step (D3) -----------------------------------


def test_repeated_wrong_codes_lock_the_mfa_step(auth_store):
    boot = _owner(auth_store)
    setup_confirmed_mfa(auth_store, boot["user_id"])
    pending = auth_store.login("owner@example.com", PASSWORD)
    for _ in range(authstore._RL_THRESHOLD):
        with pytest.raises(authstore.InvalidMfaCode):
            auth_store.complete_mfa_login(pending.session_token, "000000")
    with pytest.raises(authstore.RateLimited):
        auth_store.complete_mfa_login(pending.session_token, "000000")


def test_the_mfa_lockout_expires_on_its_own(auth_store):
    boot = _owner(auth_store)
    setup_confirmed_mfa(auth_store, boot["user_id"])
    pending = auth_store.login("owner@example.com", PASSWORD)
    for _ in range(authstore._RL_THRESHOLD):
        with pytest.raises(authstore.InvalidMfaCode):
            auth_store.complete_mfa_login(pending.session_token, "000000")
    auth_store.db.execute(
        "UPDATE rate_limit_bucket SET locked_until = '2020-01-01 00:00:00'"
    )
    with pytest.raises(authstore.InvalidMfaCode):
        auth_store.complete_mfa_login(pending.session_token, "000000")


# -- audit trail (§7, Phase 3 event list) -------------------------------------


def _event_types(auth_store):
    return [r["event_type"] for r in auth_store.db.execute(
        "SELECT event_type FROM audit_log ORDER BY at, id"
    ).fetchall()]


def test_the_mfa_lifecycle_is_audited(auth_store):
    boot = _owner(auth_store)
    mfa = setup_confirmed_mfa(auth_store, boot["user_id"])
    pending = auth_store.login("owner@example.com", PASSWORD)
    with pytest.raises(authstore.InvalidMfaCode):
        auth_store.complete_mfa_login(pending.session_token, "000000")
    code = next_mfa_code(auth_store, boot["user_id"], mfa["secret"])
    auth_store.complete_mfa_login(pending.session_token, code)
    auth_store.mfa_disable(
        boot["user_id"], PASSWORD, mfa["recovery_codes"][0]
    )
    events = _event_types(auth_store)
    for expected in (
        "MFA_ENROLL_STARTED", "MFA_CONFIRMED", "LOGIN_OK",
        "MFA_FAILED", "MFA_DISABLED",
    ):
        assert expected in events


def test_the_audit_log_never_contains_a_secret_or_code(auth_store):
    boot = _owner(auth_store)
    mfa = setup_confirmed_mfa(auth_store, boot["user_id"])
    pending = auth_store.login("owner@example.com", PASSWORD)
    code = next_mfa_code(auth_store, boot["user_id"], mfa["secret"])
    result = auth_store.complete_mfa_login(pending.session_token, code)

    dump = "\n".join(
        " ".join(str(v) for v in dict(r).values())
        for r in auth_store.db.execute("SELECT * FROM audit_log").fetchall()
    )
    assert PASSWORD not in dump
    assert mfa["secret"] not in dump
    assert code not in dump
    assert result.session_token not in dump
    for rc in mfa["recovery_codes"]:
        assert rc not in dump
        assert rc.replace("-", "") not in dump
