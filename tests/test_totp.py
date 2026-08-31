"""RFC 6238 TOTP primitive (formslang/totp.py): secret generation, the
otpauth:// URI, and code verification with replay protection.

test_a_known_secret_and_time_produce_the_known_rfc_6238_code is the load-
bearing one: every other test only proves the implementation agrees with
itself, this one proves it agrees with the standard.
"""

from __future__ import annotations

import pytest

from formslang import totp

# RFC 6238 Appendix B's test vectors, ASCII secret "12345678901234567890"
# (20 bytes), base32-encoded for this module's base32-only API. Vector at
# T=59s: SHA-1, 8-digit code "94287082". This module returns 6 digits, so
# the vector's last 6 digits are the truncation this module returns too --
# the truncated-then-mod-10^8-then-mod-10^6 result is the same value
# either way, since both truncations are "take the low decimal digits" of
# the same 31-bit integer.
_RFC_SECRET_B32 = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"  # b32encode(b"12345678901234567890")
_RFC_T59_CODE = "287082"


def test_a_known_secret_and_time_produce_the_known_rfc_6238_code():
    assert totp.generate_code(_RFC_SECRET_B32, at=59) == _RFC_T59_CODE


def test_generate_secret_returns_unpadded_base32():
    secret = totp.generate_secret()
    assert secret == secret.upper()
    assert "=" not in secret
    assert all(ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567" for ch in secret)


def test_generate_secret_is_not_the_same_value_twice():
    assert totp.generate_secret() != totp.generate_secret()


def test_provisioning_uri_carries_the_secret_and_the_expected_fields():
    uri = totp.provisioning_uri("JBSWY3DPEHPK3PXP", account_name="alice@example.com")
    assert uri.startswith("otpauth://totp/")
    assert "secret=JBSWY3DPEHPK3PXP" in uri
    assert "issuer=FormsLang" in uri
    assert "digits=6" in uri
    assert "period=30" in uri
    assert "alice%40example.com" in uri or "alice@example.com" in uri


def test_provisioning_uri_requires_an_account_name():
    with pytest.raises(ValueError):
        totp.provisioning_uri("JBSWY3DPEHPK3PXP", account_name="")


def test_a_freshly_generated_code_verifies_against_its_own_secret():
    secret = totp.generate_secret()
    code = totp.generate_code(secret, at=1_700_000_000)
    assert totp.verify_code(secret, code, at=1_700_000_000) == totp.current_step(at=1_700_000_000)


def test_a_code_for_a_different_secret_does_not_verify():
    secret_a = totp.generate_secret()
    secret_b = totp.generate_secret()
    code = totp.generate_code(secret_a, at=1_700_000_000)
    assert totp.verify_code(secret_b, code, at=1_700_000_000) is None


def test_a_code_far_outside_the_window_does_not_verify():
    secret = totp.generate_secret()
    code = totp.generate_code(secret, at=1_700_000_000)
    ten_minutes_later = 1_700_000_000 + 600
    assert totp.verify_code(secret, code, at=ten_minutes_later) is None


def test_a_code_one_step_early_or_late_verifies_within_the_default_window():
    secret = totp.generate_secret()
    now = 1_700_000_000
    code_next_step = totp.generate_code(secret, at=now + totp.PERIOD_SECONDS)
    assert totp.verify_code(secret, code_next_step, at=now) is not None


def test_a_non_numeric_code_does_not_verify():
    secret = totp.generate_secret()
    assert totp.verify_code(secret, "abcdef") is None


def test_a_code_of_the_wrong_length_does_not_verify():
    secret = totp.generate_secret()
    assert totp.verify_code(secret, "123") is None


def test_an_empty_code_does_not_verify():
    secret = totp.generate_secret()
    assert totp.verify_code(secret, "") is None


def test_the_same_code_is_rejected_on_replay():
    """The exact scenario design doc §7.3.5 calls out: a code, once
    accepted and recorded as last_accepted_step, must never verify again."""
    secret = totp.generate_secret()
    now = 1_700_000_000
    code = totp.generate_code(secret, at=now)
    accepted_step = totp.verify_code(secret, code, at=now)
    assert accepted_step is not None

    replay = totp.verify_code(secret, code, at=now, last_accepted_step=accepted_step)
    assert replay is None


def test_a_later_code_still_verifies_after_an_earlier_one_was_accepted():
    secret = totp.generate_secret()
    now = 1_700_000_000
    first_code = totp.generate_code(secret, at=now)
    first_step = totp.verify_code(secret, first_code, at=now)

    later = now + totp.PERIOD_SECONDS
    second_code = totp.generate_code(secret, at=later)
    second_step = totp.verify_code(secret, second_code, at=later, last_accepted_step=first_step)
    assert second_step is not None
    assert second_step > first_step


def test_an_older_code_than_the_last_accepted_step_does_not_verify():
    """Not just exact reuse -- a step at or before the high-water mark is
    refused even if it wasn't the exact code most recently accepted."""
    secret = totp.generate_secret()
    now = 1_700_000_000
    later = now + totp.PERIOD_SECONDS
    later_code_accepted_step = totp.verify_code(
        secret, totp.generate_code(secret, at=later), at=later
    )

    old_code = totp.generate_code(secret, at=now)
    assert totp.verify_code(
        secret, old_code, at=now, last_accepted_step=later_code_accepted_step, window=5
    ) is None


def test_current_step_advances_by_one_every_period():
    a = totp.current_step(at=1_700_000_000)
    b = totp.current_step(at=1_700_000_000 + totp.PERIOD_SECONDS)
    assert b == a + 1


def test_verify_code_rejects_a_negative_window():
    secret = totp.generate_secret()
    with pytest.raises(ValueError):
        totp.verify_code(secret, "123456", window=-1)
