"""The credential-store module (formslang/secrets.py): the original
single-slot AI-key API (get_key/set_key/delete_key, unchanged behavior)
and the general (service, account) API added for D6 (one OS-credential-store
entry per user's MFA secret, docs/auth-multitenancy-design.md §2.3/§4).

Every test here runs against the in-memory backend -- conftest's autouse
isolated_config fixture already sets FORMSLANG_SECRET_BACKEND=memory and
resets it per test, so nothing here ever touches a real keychain.
"""

from __future__ import annotations

import pytest

from formslang import secrets


def test_set_key_then_get_key_round_trips(isolated_config):
    secrets.set_key("sk-example-not-real")
    assert secrets.get_key() == "sk-example-not-real"


def test_get_key_is_empty_string_when_nothing_was_ever_stored(isolated_config):
    assert secrets.get_key() == ""


def test_delete_key_then_get_key_is_empty_string(isolated_config):
    secrets.set_key("sk-example-not-real")
    secrets.delete_key()
    assert secrets.get_key() == ""


def test_setting_an_empty_key_deletes_it(isolated_config):
    secrets.set_key("sk-example-not-real")
    secrets.set_key("")
    assert secrets.get_key() == ""


def test_set_secret_then_get_secret_round_trips(isolated_config):
    secrets.set_secret("FormsLang", "mfa-totp:user-1", "JBSWY3DPEHPK3PXP")
    assert secrets.get_secret("FormsLang", "mfa-totp:user-1") == "JBSWY3DPEHPK3PXP"


def test_get_secret_is_empty_string_when_that_account_was_never_stored(isolated_config):
    assert secrets.get_secret("FormsLang", "mfa-totp:no-such-user") == ""


def test_two_different_accounts_under_the_same_service_do_not_collide(isolated_config):
    """The whole point of D6: each user gets their own vault entry."""
    secrets.set_secret("FormsLang", "mfa-totp:user-1", "SECRETONE")
    secrets.set_secret("FormsLang", "mfa-totp:user-2", "SECRETTWO")
    assert secrets.get_secret("FormsLang", "mfa-totp:user-1") == "SECRETONE"
    assert secrets.get_secret("FormsLang", "mfa-totp:user-2") == "SECRETTWO"


def test_delete_secret_then_get_secret_is_empty_string(isolated_config):
    secrets.set_secret("FormsLang", "mfa-totp:user-1", "JBSWY3DPEHPK3PXP")
    secrets.delete_secret("FormsLang", "mfa-totp:user-1")
    assert secrets.get_secret("FormsLang", "mfa-totp:user-1") == ""


def test_deleting_a_secret_that_was_never_set_does_not_raise(isolated_config):
    secrets.delete_secret("FormsLang", "mfa-totp:never-enrolled")


def test_setting_an_empty_secret_deletes_it(isolated_config):
    secrets.set_secret("FormsLang", "mfa-totp:user-1", "JBSWY3DPEHPK3PXP")
    secrets.set_secret("FormsLang", "mfa-totp:user-1", "")
    assert secrets.get_secret("FormsLang", "mfa-totp:user-1") == ""


def test_reset_memory_backend_clears_every_service_and_account(isolated_config):
    secrets.set_key("sk-example-not-real")
    secrets.set_secret("FormsLang", "mfa-totp:user-1", "JBSWY3DPEHPK3PXP")
    secrets.reset_memory_backend()
    assert secrets.get_key() == ""
    assert secrets.get_secret("FormsLang", "mfa-totp:user-1") == ""


def test_the_ai_key_slot_and_a_general_secret_slot_are_independent(isolated_config):
    secrets.set_key("sk-example-not-real")
    secrets.set_secret("FormsLang", "mfa-totp:user-1", "JBSWY3DPEHPK3PXP")
    assert secrets.get_key() == "sk-example-not-real"
    assert secrets.get_secret("FormsLang", "mfa-totp:user-1") == "JBSWY3DPEHPK3PXP"


@pytest.mark.parametrize("bad", ["has space", "line\nbreak", "tab\there"])
def test_set_key_rejects_a_value_with_whitespace(isolated_config, bad):
    with pytest.raises(ValueError):
        secrets.set_key(bad)


@pytest.mark.parametrize("bad", ["has space", "line\nbreak", "control\x07char"])
def test_set_secret_rejects_a_value_with_whitespace_or_control_characters(isolated_config, bad):
    with pytest.raises(ValueError):
        secrets.set_secret("FormsLang", "mfa-totp:user-1", bad)


@pytest.mark.parametrize("bad_service", ["", "has space", "semi;colon", "a" * 201])
def test_get_secret_rejects_an_invalid_service_identifier(isolated_config, bad_service):
    with pytest.raises(ValueError):
        secrets.get_secret(bad_service, "mfa-totp:user-1")


@pytest.mark.parametrize("bad_account", ["", "has space", "semi;colon", "a" * 201])
def test_get_secret_rejects_an_invalid_account_identifier(isolated_config, bad_account):
    with pytest.raises(ValueError):
        secrets.get_secret("FormsLang", bad_account)


def test_set_secret_rejects_an_invalid_identifier_before_touching_the_store(isolated_config):
    with pytest.raises(ValueError):
        secrets.set_secret("FormsLang", "bad account", "JBSWY3DPEHPK3PXP")
    assert secrets.get_secret("FormsLang", "mfa-totp:user-1") == ""


def test_delete_secret_rejects_an_invalid_identifier(isolated_config):
    with pytest.raises(ValueError):
        secrets.delete_secret("FormsLang", "bad account")


def test_get_secret_fails_closed_when_no_credential_store_is_available(
    isolated_config, monkeypatch
):
    """MFA correctness needs 'not enrolled' told apart from 'the vault is
    unreachable' -- collapsing the two into "" would let a transient store
    failure either look like a bypass or an unexplained lockout."""
    monkeypatch.setenv("FORMSLANG_SECRET_BACKEND", "none")
    with pytest.raises(secrets.SecureStorageUnavailable):
        secrets.get_secret("FormsLang", "mfa-totp:user-1")


def test_set_secret_fails_closed_when_no_credential_store_is_available(
    isolated_config, monkeypatch
):
    monkeypatch.setenv("FORMSLANG_SECRET_BACKEND", "none")
    with pytest.raises(secrets.SecureStorageUnavailable):
        secrets.set_secret("FormsLang", "mfa-totp:user-1", "JBSWY3DPEHPK3PXP")


def test_delete_secret_does_not_raise_when_no_credential_store_is_available(
    isolated_config, monkeypatch
):
    """Deleting is the terminal state either way: auth.db, not this module,
    is the source of truth for whether a user is enrolled."""
    monkeypatch.setenv("FORMSLANG_SECRET_BACKEND", "none")
    secrets.delete_secret("FormsLang", "mfa-totp:user-1")


def test_get_key_does_not_raise_when_no_credential_store_is_available(
    isolated_config, monkeypatch
):
    """get_key keeps its original, more forgiving contract: the AI key flow
    tells the user to retype it, so a read failure collapses to ""."""
    monkeypatch.setenv("FORMSLANG_SECRET_BACKEND", "none")
    assert secrets.get_key() == ""


def test_set_key_raises_when_no_credential_store_is_available(isolated_config, monkeypatch):
    monkeypatch.setenv("FORMSLANG_SECRET_BACKEND", "none")
    with pytest.raises(secrets.SecureStorageUnavailable):
        secrets.set_key("sk-example-not-real")
