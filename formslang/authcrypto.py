"""Password hashing and token primitives for the control-plane database.

Two rules carried over from :mod:`formslang.secrets`, applied here to a
different secret: **zero third-party dependencies** -- ``hashlib.scrypt``
is the standard library's own memory-hard KDF, so there is no ``argon2-cffi``
to install on a locked-down machine -- and **nothing is ever compared with
plain ``==``**, because a data-dependent early exit is a timing oracle.

scrypt's cost parameters (``N``/``r``/``p``) are versioned rather than
hardcoded. Raising the cost later is a new entry in ``_SCRYPT_PARAMS`` and a
bump of :data:`CURRENT_PASSWORD_PARAMS_VERSION`, not a schema change and not
a mass rehash -- existing rows keep the version they were hashed under until
the user's next successful login recomputes them (``authstore.login``).

A password is capped at :data:`MAX_PASSWORD_BYTES` *before* it reaches
scrypt. Without that cap, an attacker can hand the server an arbitrarily
long string and force it to spend real CPU and memory deriving a key from
it -- the length check is the whole defence, so it has to run first.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets as _stdlib_secrets

VERSION = "authcrypto/1"

# 128 * N * r bytes of memory per scrypt call, independent of p. Version 1
# is tuned for an interactive login on ordinary hardware (~16 MiB, well
# under the ceiling below) rather than for maximum resistance -- this is a
# control-plane login, not a file encrypted at rest for years.
_SCRYPT_PARAMS: dict[int, dict[str, int]] = {
    1: {"n": 2**14, "r": 8, "p": 1},
}
CURRENT_PASSWORD_PARAMS_VERSION = max(_SCRYPT_PARAMS)

# A future version bump must stay under this, or a single login could be
# turned into a memory-exhaustion request. ``hashlib.scrypt`` enforces it
# itself via ``maxmem`` -- raising a params version past the ceiling fails
# loudly at import time (see the assertion below), not at request time.
_MAX_SCRYPT_MEMORY_BYTES = 64 * 1024 * 1024
_SCRYPT_MAXMEM = _MAX_SCRYPT_MEMORY_BYTES

for _version, _params in _SCRYPT_PARAMS.items():
    _needed = 128 * _params["n"] * _params["r"]
    assert _needed <= _MAX_SCRYPT_MEMORY_BYTES, (
        f"password_params_version {_version} needs {_needed} bytes of scrypt "
        f"memory, over the {_MAX_SCRYPT_MEMORY_BYTES} byte ceiling"
    )
del _version, _params, _needed

#: Hard cap enforced before a single byte reaches scrypt.
MAX_PASSWORD_BYTES = 512

_SALT_BYTES = 16
_DERIVED_KEY_BYTES = 32

#: Opaque, URL-safe tokens for sessions, CSRF secrets and (later) reset
#: tokens. 32 bytes of ``secrets.token_bytes`` entropy, base64url-encoded.
TOKEN_BYTES = 32


class PasswordTooLong(ValueError):
    """The submitted password is longer than we will ever hash."""


def _params_for(version: int) -> dict[str, int]:
    try:
        return _SCRYPT_PARAMS[version]
    except KeyError:
        raise ValueError(f"unknown password_params_version {version!r}") from None


def _check_length(raw: bytes) -> None:
    if not raw:
        raise ValueError("password must not be empty")
    if len(raw) > MAX_PASSWORD_BYTES:
        raise PasswordTooLong(f"password must be at most {MAX_PASSWORD_BYTES} bytes")


def hash_password(
    password: str, *, params_version: int = CURRENT_PASSWORD_PARAMS_VERSION
) -> tuple[str, str, int]:
    """Hash ``password``. Returns ``(hash_b64, salt_b64, params_version)``.

    Raises :class:`PasswordTooLong` (a plain input-validation error, not a
    crypto failure) before scrypt ever runs.
    """
    raw = password.encode("utf-8")
    _check_length(raw)
    params = _params_for(params_version)
    salt = os.urandom(_SALT_BYTES)
    derived = hashlib.scrypt(
        raw, salt=salt, n=params["n"], r=params["r"], p=params["p"],
        dklen=_DERIVED_KEY_BYTES, maxmem=_SCRYPT_MAXMEM,
    )
    return (
        base64.b64encode(derived).decode("ascii"),
        base64.b64encode(salt).decode("ascii"),
        params_version,
    )


def verify_password(
    password: str, password_hash: str, password_salt: str, params_version: int
) -> bool:
    """Constant-time check. Never raises on a bad guess -- only on bad storage."""
    raw = password.encode("utf-8")
    if not raw or len(raw) > MAX_PASSWORD_BYTES:
        return False
    try:
        params = _params_for(params_version)
        salt = base64.b64decode(password_salt, validate=True)
        expected = base64.b64decode(password_hash, validate=True)
    except (ValueError, KeyError):
        return False
    derived = hashlib.scrypt(
        raw, salt=salt, n=params["n"], r=params["r"], p=params["p"],
        dklen=len(expected) or _DERIVED_KEY_BYTES, maxmem=_SCRYPT_MAXMEM,
    )
    return hmac.compare_digest(derived, expected)


def needs_rehash(params_version: int) -> bool:
    return params_version != CURRENT_PASSWORD_PARAMS_VERSION


def new_token(nbytes: int = TOKEN_BYTES) -> str:
    """A fresh opaque secret -- a session token, a CSRF secret, whatever needs one."""
    return _stdlib_secrets.token_urlsafe(nbytes)


def hash_token(token: str) -> str:
    """SHA-256 of a token, hex-encoded. What actually gets stored on disk.

    The raw token exists only in the client's cookie and in this one
    computation -- ``auth.db`` never holds anything an attacker who reads it
    could present back to the server.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def constant_time_eq(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)
