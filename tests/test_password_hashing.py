"""Password hashing and token primitives (D1)."""

from __future__ import annotations

import pytest

from formslang import authcrypto

PASSWORD = "correct horse battery staple"


def test_a_password_hashes_and_verifies():
    password_hash, password_salt, params_version = authcrypto.hash_password(PASSWORD)
    assert authcrypto.verify_password(PASSWORD, password_hash, password_salt, params_version)


def test_a_wrong_password_does_not_verify():
    password_hash, password_salt, params_version = authcrypto.hash_password(PASSWORD)
    assert not authcrypto.verify_password(
        "wrong password", password_hash, password_salt, params_version
    )


def test_hash_password_never_reuses_a_salt():
    _hash1, salt1, _v1 = authcrypto.hash_password(PASSWORD)
    _hash2, salt2, _v2 = authcrypto.hash_password(PASSWORD)
    assert salt1 != salt2


def test_an_overlong_password_is_rejected_before_hashing():
    too_long = "x" * (authcrypto.MAX_PASSWORD_BYTES + 1)
    with pytest.raises(authcrypto.PasswordTooLong):
        authcrypto.hash_password(too_long)


def test_verify_password_rejects_an_overlong_password_instead_of_hashing_it():
    password_hash, password_salt, params_version = authcrypto.hash_password(PASSWORD)
    too_long = "x" * (authcrypto.MAX_PASSWORD_BYTES + 1)
    assert not authcrypto.verify_password(too_long, password_hash, password_salt, params_version)


def test_an_empty_password_is_rejected():
    with pytest.raises(ValueError):
        authcrypto.hash_password("")


def test_rehash_happens_automatically_when_params_are_outdated():
    assert authcrypto.needs_rehash(0) is True
    assert authcrypto.needs_rehash(authcrypto.CURRENT_PASSWORD_PARAMS_VERSION) is False


def test_verify_password_rejects_an_unknown_params_version():
    password_hash, password_salt, _v = authcrypto.hash_password(PASSWORD)
    assert not authcrypto.verify_password(PASSWORD, password_hash, password_salt, 999)


def test_verify_password_rejects_malformed_stored_values_instead_of_raising():
    assert not authcrypto.verify_password(
        PASSWORD, "not-base64!!", "not-base64!!", authcrypto.CURRENT_PASSWORD_PARAMS_VERSION
    )


def test_new_token_is_url_safe_and_unique():
    a = authcrypto.new_token()
    b = authcrypto.new_token()
    assert a != b
    assert all(c.isalnum() or c in "-_" for c in a)


def test_hash_token_is_deterministic_but_not_reversible():
    token = authcrypto.new_token()
    assert authcrypto.hash_token(token) == authcrypto.hash_token(token)
    assert authcrypto.hash_token(token) != token


def test_constant_time_eq_matches_equal_values_and_rejects_different_ones():
    assert authcrypto.constant_time_eq("abc", "abc")
    assert not authcrypto.constant_time_eq("abc", "abd")


def test_every_configured_params_version_stays_under_the_memory_ceiling():
    for params in authcrypto._SCRYPT_PARAMS.values():
        assert 128 * params["n"] * params["r"] <= 64 * 1024 * 1024
