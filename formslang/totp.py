"""RFC 6238 TOTP: secret generation, the ``otpauth://`` URI an authenticator
app scans, and code verification with replay protection.

Stdlib-only, same rule as :mod:`formslang.secrets` and
:mod:`formslang.authcrypto`: ``hashlib``, ``hmac``, ``base64``, ``struct``,
``time``, nothing installed. RFC 6238 is RFC 4226 (HOTP) keyed by a time
step instead of a counter, so :func:`_hotp` implements the whole thing.

This module knows nothing about ``auth.db`` or the OS credential store --
it is a pure function of ``(secret, code, time)``. Where the generated
secret is stored (design doc §2.3, D6: one OS-credential-store entry per
user) and where ``last_accepted_step`` is persisted are
:mod:`formslang.authstore`'s job, not this module's. That split is what
lets every test below run with no filesystem and no OS keychain at all.

Defaults match every mainstream authenticator app (Google Authenticator,
Authy, 1Password, Microsoft Authenticator): SHA-1, 6 digits, a 30-second
step. RFC 6238 itself recommends SHA-1 for interoperability -- the stronger
HMAC variants it also defines are opt-in extensions few apps implement.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import struct
import time
import urllib.parse

VERSION = "totp/1"

#: 160 bits -- RFC 4226's own recommended HOTP key size, and what every
#: mainstream authenticator app expects.
SECRET_BYTES = 20
DIGITS = 6
PERIOD_SECONDS = 30
ISSUER = "FormsLang"

#: Accept a code from one step early or late, i.e. up to ~30s of clock
#: drift between server and phone in either direction.
DEFAULT_WINDOW = 1


def generate_secret() -> str:
    """A fresh secret, base32-encoded (RFC 4648, no padding) -- the form
    every authenticator app's manual-entry field expects."""
    return base64.b32encode(os.urandom(SECRET_BYTES)).decode("ascii").rstrip("=")


def _decode_secret(secret: str) -> bytes:
    cleaned = secret.strip().upper().replace(" ", "")
    if not cleaned:
        raise ValueError("empty TOTP secret")
    padded = cleaned + "=" * (-len(cleaned) % 8)
    try:
        return base64.b32decode(padded)
    except (ValueError, TypeError) as e:
        raise ValueError("malformed base32 TOTP secret") from e


def provisioning_uri(secret: str, *, account_name: str, issuer: str = ISSUER) -> str:
    """The ``otpauth://`` URI an authenticator app scans as a QR code or
    imports by hand. Never log or persist this -- it carries the raw
    secret in plain text (design doc §7.3): the response body of the
    enrollment call is the only place it may ever appear.
    """
    if not account_name:
        raise ValueError("account_name is required")
    label = urllib.parse.quote(f"{issuer}:{account_name}")
    query = urllib.parse.urlencode(
        {
            "secret": secret,
            "issuer": issuer,
            "algorithm": "SHA1",
            "digits": DIGITS,
            "period": PERIOD_SECONDS,
        }
    )
    return f"otpauth://totp/{label}?{query}"


def _hotp(secret: str, counter: int) -> str:
    key = _decode_secret(secret)
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    truncated = digest[offset : offset + 4]
    code_int = (int.from_bytes(truncated, "big") & 0x7FFFFFFF) % (10**DIGITS)
    return str(code_int).zfill(DIGITS)


def current_step(*, at: float | None = None) -> int:
    """The RFC 6238 time step covering ``at`` (default: now)."""
    return int((time.time() if at is None else at) // PERIOD_SECONDS)


def generate_code(secret: str, *, at: float | None = None) -> str:
    """The code for the step covering ``at``. Test-only in this codebase --
    a real code always comes from the user's own authenticator app."""
    return _hotp(secret, current_step(at=at))


def verify_code(
    secret: str,
    code: str,
    *,
    last_accepted_step: int | None = None,
    at: float | None = None,
    window: int = DEFAULT_WINDOW,
) -> int | None:
    """Check ``code`` against the steps from ``now - window`` to
    ``now + window``, inclusive. Returns the matching step so the caller can
    persist it as the new ``last_accepted_step``, or ``None`` if nothing
    matched.

    Replay protection: a step at or before ``last_accepted_step`` never
    matches, even if the code is otherwise correct -- a code, once
    accepted, cannot be accepted again, and neither can an older one
    (design doc §7.3.5). Pass ``last_accepted_step=None`` only for a step
    that has genuinely never been checked before (a fresh enrollment's
    first confirmation code).
    """
    code = str(code or "").strip()
    if not code or not code.isdigit() or len(code) != DIGITS:
        return None
    if window < 0:
        raise ValueError("window must not be negative")
    now_step = current_step(at=at)
    for offset in range(-window, window + 1):
        step = now_step + offset
        if last_accepted_step is not None and step <= last_accepted_step:
            continue
        if hmac.compare_digest(_hotp(secret, step), code):
            return step
    return None
