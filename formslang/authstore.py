"""Control-plane database: organizations, users, memberships, sessions.

New file, ``auth.db``, sibling to the per-project ``.session.db`` files
``store.py`` manages -- but not the same kind of file. A ``.session.db`` is
one reviewer's conversion session and gets copied, zipped and deleted
freely; ``auth.db`` is shared identity state for every project and every
member of an organization, created lazily (:func:`default_db_path` is never
touched unless something explicitly asks for it) and never bundled into an
export.

Follows ``store.py``'s conventions -- ``CREATE TABLE IF NOT EXISTS``, the
``_ADDED_COLUMNS``/``_migrate()`` pattern for later additions, ``sqlite3.Row``
rows returned as plain ``dict`` -- with two deliberate departures, both
because identity data has different durability and concurrency needs than a
session file:

- **WAL, not the default journal mode.** ``store.py`` avoids WAL because a
  session file is routinely copied, moved or deleted while the desktop tool
  runs, and WAL keeps auxiliary file handles open on Windows in a way that
  gets in the way of that. ``auth.db`` is never casually moved during normal
  operation (only project *files* are copied, during adoption -- see
  ``formslang/projects.py``), so WAL's better concurrent-read behaviour is a
  clear win with none of the downside that ruled it out for sessions.
- **Explicit ``BEGIN IMMEDIATE`` transactions**, not the module-default
  autocommit-with-manual-``commit()`` that ``store.py`` uses. A single-user
  desktop tool editing one session file doesn't need transaction isolation
  from itself; a "can this user be removed" check racing a second removal
  request does. The connection is opened with ``isolation_level=None`` so
  every write is either its own implicit transaction or explicitly wrapped
  by :meth:`AuthStore._immediate`.

Design reference: ``docs/auth-multitenancy-design.md``. This module covers
Phases 1-3 of that document's §11 phased delivery: schema, scrypt hashing,
sessions, RBAC role constants, the scoped bootstrap flow, and -- Phase 3 --
TOTP MFA (§7.3), recovery codes, assisted password reset (§7.5) and the
structured audit trail. The raw TOTP secret never touches this database:
per D6 (§2.3) it lives in the OS credential store, one entry per user
(``FormsLang:mfa-totp:<user_id>``, via :mod:`formslang.secrets`), and
``mfa_secret`` here holds enrollment metadata only.

Scope enforcement (§7.1/§7.2): :meth:`AuthStore.login` issues
``MFA_PENDING`` for a user with confirmed MFA (completed by
:meth:`complete_mfa_login`), ``BOOTSTRAP_MFA`` for an Owner/Admin who has
not confirmed MFA yet (mandatory enrollment -- the session can only reach
the MFA enroll/confirm routes), and ``NORMAL`` otherwise.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import hashlib
import json
import os
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path

from . import authcrypto, config, totp
from . import secrets as vault

AUTH_ENV = "FORMSLANG_AUTH"

OWNER, ADMIN, DEVELOPER, VIEWER = "OWNER", "ADMIN", "DEVELOPER", "VIEWER"
ROLES = (OWNER, ADMIN, DEVELOPER, VIEWER)

NORMAL, MFA_PENDING, BOOTSTRAP_MFA = "NORMAL", "MFA_PENDING", "BOOTSTRAP_MFA"
SCOPES = (NORMAL, MFA_PENDING, BOOTSTRAP_MFA)

EXTERNAL_LEGACY, ADOPTED = "EXTERNAL_LEGACY", "ADOPTED"
STORAGE_MODES = (EXTERNAL_LEGACY, ADOPTED)

SESSION_TTL_SECONDS = 12 * 60 * 60
MAX_SESSIONS_PER_USER = 5

# Phase 3 (§7.1-§7.5): restricted-session lifetimes, enrollment expiry,
# recovery codes and reset tokens. All deliberately short -- each of these
# is a stepping stone toward a NORMAL session, never a resting state.
MFA_PENDING_SESSION_TTL_SECONDS = 5 * 60
MFA_ENROLLMENT_SESSION_TTL_SECONDS = 15 * 60
MFA_ENROLLMENT_TTL_SECONDS = 15 * 60
MFA_RECOVERY_CODE_COUNT = 10
PASSWORD_RESET_TTL_SECONDS = 15 * 60

# Persisted rate limiting (D3): a lockout survives a process restart because
# it lives here, not in a module-level dict.
_RL_THRESHOLD = 5
_RL_BASE_LOCK_SECONDS = 60
_RL_MAX_LOCK_SECONDS = 30 * 60
_RL_WINDOW_SECONDS = 15 * 60

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_migration (
    version     INTEGER PRIMARY KEY,
    applied_at  TEXT NOT NULL,
    description TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS organization (
    id         TEXT PRIMARY KEY,
    slug       TEXT UNIQUE NOT NULL,
    name       TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user (
    id                       TEXT PRIMARY KEY,
    email                    TEXT UNIQUE NOT NULL,
    username                 TEXT UNIQUE,
    password_hash            TEXT NOT NULL,
    password_salt            TEXT NOT NULL,
    password_algo            TEXT NOT NULL DEFAULT 'scrypt',
    password_params_version  INTEGER NOT NULL,
    must_rehash              INTEGER NOT NULL DEFAULT 0,
    disabled_at              TEXT,
    created_at               TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS membership (
    id         TEXT PRIMARY KEY,
    org_id     TEXT NOT NULL REFERENCES organization(id),
    user_id    TEXT NOT NULL REFERENCES user(id),
    role       TEXT NOT NULL CHECK (role IN ('OWNER','ADMIN','DEVELOPER','VIEWER')),
    created_at TEXT NOT NULL,
    UNIQUE (org_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_membership_user ON membership(user_id);
CREATE INDEX IF NOT EXISTS idx_membership_org ON membership(org_id);

CREATE TABLE IF NOT EXISTS project (
    id              TEXT PRIMARY KEY,
    org_id          TEXT NOT NULL REFERENCES organization(id),
    name            TEXT NOT NULL,
    storage_mode    TEXT NOT NULL CHECK (storage_mode IN ('EXTERNAL_LEGACY','ADOPTED')),
    external_path   TEXT,
    session_db_path TEXT,
    created_by      TEXT NOT NULL REFERENCES user(id),
    created_at      TEXT NOT NULL,
    deleted_at      TEXT,
    adopted_at      TEXT,
    CHECK (
        (storage_mode = 'EXTERNAL_LEGACY' AND external_path IS NOT NULL AND session_db_path IS NULL)
        OR
        (storage_mode = 'ADOPTED' AND session_db_path IS NOT NULL)
    )
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_project_external_path ON project(external_path)
    WHERE external_path IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_project_org ON project(org_id);

CREATE TABLE IF NOT EXISTS project_permission (
    id          TEXT PRIMARY KEY,
    project_id  TEXT NOT NULL REFERENCES project(id),
    user_id     TEXT NOT NULL REFERENCES user(id),
    permission  TEXT NOT NULL CHECK (permission IN ('EXPORT')),
    granted_by  TEXT NOT NULL REFERENCES user(id),
    created_at  TEXT NOT NULL,
    UNIQUE (project_id, user_id, permission)
);

CREATE TABLE IF NOT EXISTS session_token (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL REFERENCES user(id),
    active_org_id   TEXT REFERENCES organization(id),
    scope           TEXT NOT NULL CHECK (scope IN ('NORMAL','MFA_PENDING','BOOTSTRAP_MFA')),
    token_hash      TEXT UNIQUE NOT NULL,
    csrf_secret     TEXT NOT NULL,
    user_agent_hash TEXT,
    ip_hash         TEXT,
    created_at      TEXT NOT NULL,
    last_seen_at    TEXT NOT NULL,
    expires_at      TEXT NOT NULL,
    revoked_at      TEXT
);
CREATE INDEX IF NOT EXISTS idx_session_token_hash ON session_token(token_hash);
CREATE INDEX IF NOT EXISTS idx_session_user ON session_token(user_id);

-- D6 (design doc §2.3, §4): the raw TOTP secret lives ONLY in the OS
-- credential store, one entry per user (FormsLang:mfa-totp:<user_id>,
-- see formslang/secrets.get_secret/set_secret). This table never holds
-- the secret in any form, plaintext or encrypted -- enrollment/confirmation
-- metadata only.
CREATE TABLE IF NOT EXISTS mfa_secret (
    user_id             TEXT PRIMARY KEY REFERENCES user(id),
    enrolled_at         TEXT NOT NULL,
    confirmed_at        TEXT,
    last_accepted_step  INTEGER,
    created_at          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS mfa_recovery_code (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES user(id),
    code_hash  TEXT NOT NULL,
    used_at    TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS password_reset_token (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES user(id),
    issued_by  TEXT NOT NULL REFERENCES user(id),
    token_hash TEXT UNIQUE NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    used_at    TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
    id                   TEXT PRIMARY KEY,
    at                   TEXT NOT NULL,
    org_id               TEXT,
    user_id              TEXT,
    actor_email_snapshot TEXT,
    event_type           TEXT NOT NULL,
    target_type          TEXT,
    target_id            TEXT,
    outcome              TEXT NOT NULL,
    ip_hash              TEXT,
    detail_json          TEXT
);
CREATE INDEX IF NOT EXISTS idx_audit_org_at ON audit_log(org_id, at);
CREATE INDEX IF NOT EXISTS idx_audit_user_at ON audit_log(user_id, at);

CREATE TABLE IF NOT EXISTS rate_limit_bucket (
    key               TEXT PRIMARY KEY,
    failures          INTEGER NOT NULL DEFAULT 0,
    window_started_at TEXT NOT NULL,
    locked_until      TEXT
);
"""

# Same shape as store.py's _ADDED_COLUMNS: empty today, the home for any
# column a later schema_migration adds to a table that already shipped.
_ADDED_COLUMNS: tuple[tuple[str, str, str], ...] = ()

# The only keys record_audit() will ever serialize into detail_json. An
# allowlist, not a blocklist: anything unlisted -- and so any secret --
# simply never lands in the audit table.
_AUDIT_DETAIL_KEYS = frozenset(
    {
        "scope", "reason", "via", "mfa_method",
        "old_role", "new_role",
        "sessions_revoked", "remaining_recovery_codes",
    }
)

_SCHEMA_VERSION = 1
_SCHEMA_DESCRIPTION = "initial control-plane schema (organization, user, membership, project, session)"


class AuthStoreError(Exception):
    """Base class for every error this module raises on purpose."""


class OrganizationNotFound(AuthStoreError, LookupError):
    pass


class UserNotFound(AuthStoreError, LookupError):
    pass


class SessionNotFound(AuthStoreError, LookupError):
    pass


class DuplicateEmail(AuthStoreError, ValueError):
    pass


class DuplicateSlug(AuthStoreError, ValueError):
    pass


class NotAMember(AuthStoreError, ValueError):
    pass


class LastOwnerError(AuthStoreError, ValueError):
    pass


class BootstrapAlreadyDone(AuthStoreError, ValueError):
    pass


class ProjectNotFound(AuthStoreError, LookupError):
    pass


class RateLimited(AuthStoreError):
    def __init__(self, retry_after_seconds: int):
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"rate limited, retry after {retry_after_seconds}s")


class MfaNotEnrolled(AuthStoreError, LookupError):
    pass


class MfaAlreadyConfirmed(AuthStoreError, ValueError):
    pass


class MfaEnrollmentExpired(AuthStoreError, ValueError):
    pass


class InvalidMfaCode(AuthStoreError, ValueError):
    """A TOTP or recovery code that did not verify. The message is safe to
    show the user: it hints at clock drift (the common benign cause) without
    ever widening the acceptance window to compensate."""

    def __init__(self, message: str = ""):
        super().__init__(
            message
            or "invalid code -- if it keeps failing, check that the device clock is in sync"
        )


@dataclass
class LoginResult:
    """What :meth:`AuthStore.login` decided. Never raises on a bad guess."""

    ok: bool
    reason: str = ""
    user_id: str | None = None
    session_token: str | None = None
    scope: str | None = None
    active_org_id: str | None = None
    organizations: list[dict] | None = None
    mfa_required: bool = False
    mfa_enrollment_required: bool = False


def auth_enabled() -> bool:
    """Whether the auth subsystem is active for this process.

    Mirrors ``FORMSLANG_SECRET_BACKEND``'s reading convention in
    ``secrets.py``: empty or unset is off, and off is the only default that
    keeps every existing local install behaving exactly as it did before
    this module existed.

    The environment variable wins outright, on or off. With it unset, the
    Settings screen's saved choice in ``config.json`` decides instead --
    that is what lets a reviewer turn multi-user mode on from the desktop
    app and have it survive a restart without ever touching an environment
    variable.
    """
    env = os.environ.get(AUTH_ENV, "").strip().lower()
    if env:
        return env in {"1", "true", "on", "yes"}
    saved = str(config.load_config().get("auth_enabled", "")).strip().lower()
    return saved in {"1", "true", "on", "yes"}


def default_db_path() -> Path:
    return config.data_dir() / "auth.db"


def _now() -> str:
    return dt.datetime.now().replace(microsecond=0).isoformat(sep=" ")


def _new_id() -> str:
    return uuid.uuid4().hex


def _fingerprint(value: str) -> str | None:
    """A stored proxy for a user-agent or IP -- never the raw value at rest."""
    value = (value or "").strip()
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:32]


def _normalize_recovery_code(code: str) -> str:
    """The canonical form a recovery code is hashed and compared in --
    tolerant of the dashes and spacing a person re-types."""
    return (code or "").strip().lower().replace("-", "").replace(" ", "")


class _FetchedRows:
    """A SELECT's result, fully drained while the statement lock was held.
    Quacks like the cursor for the read patterns this codebase uses
    (``fetchone``, ``fetchall``, iteration)."""

    def __init__(self, rows: list):
        self._rows = rows
        self._i = 0
        self.rowcount = -1  # what sqlite3 itself reports for a SELECT

    def fetchone(self):
        if self._i >= len(self._rows):
            return None
        row = self._rows[self._i]
        self._i += 1
        return row

    def fetchall(self) -> list:
        rows = self._rows[self._i :]
        self._i = len(self._rows)
        return rows

    def __iter__(self):
        while (row := self.fetchone()) is not None:
            yield row


class _SerializedConnection:
    """One ``sqlite3.Connection`` shared by every thread of a
    ThreadingHTTPServer (workbench.py), with every statement -- including
    the row fetch of a SELECT -- run under one re-entrant lock.

    Sharing the bare connection is not safe, even in a "serialized" SQLite
    build: two threads running the same SQL can step the same cached
    prepared statement concurrently (InterfaceError: "bad parameter or
    other API misuse"), and a bare write interleaved into another thread's
    open BEGIN IMMEDIATE lands inside that transaction and is swallowed by
    its rollback. ``AuthStore._immediate()`` holds this same lock for the
    whole transaction, which is what keeps a multi-statement transaction
    atomic against other threads (PRAGMA busy_timeout only arbitrates
    separate connections, never two threads sharing this one).
    """

    def __init__(self, real: sqlite3.Connection, lock: threading.RLock):
        self._real = real
        self._lock = lock

    def execute(self, sql: str, params=()):
        with self._lock:
            cur = self._real.execute(sql, params)
            if cur.description is None:
                return cur
            return _FetchedRows(cur.fetchall())

    def executemany(self, sql: str, seq):
        with self._lock:
            return self._real.executemany(sql, seq)

    def executescript(self, script: str):
        with self._lock:
            return self._real.executescript(script)

    def commit(self) -> None:
        with self._lock:
            self._real.commit()

    def rollback(self) -> None:
        with self._lock:
            self._real.rollback()

    def close(self) -> None:
        with self._lock:
            self._real.close()

    def __getattr__(self, name: str):
        return getattr(self._real, name)


class AuthStore:
    """The control-plane database: one file, ``auth.db``, per FormsLang install."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Re-entrant on purpose: _immediate() holds it for a whole
        # transaction while every statement inside re-acquires it.
        self._write_lock = threading.RLock()
        raw = sqlite3.connect(self.path, isolation_level=None, check_same_thread=False)
        raw.row_factory = sqlite3.Row
        self.db = _SerializedConnection(raw, self._write_lock)
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.execute("PRAGMA journal_mode = WAL")
        self.db.execute("PRAGMA busy_timeout = 5000")
        self.db.executescript(SCHEMA)
        self._migrate()
        self._record_schema_version()

    def _migrate(self) -> None:
        for table, column, decl in _ADDED_COLUMNS:
            rows = self.db.execute(f"PRAGMA table_info({table})").fetchall()
            if not rows:
                continue
            if column in {r["name"] for r in rows}:
                continue
            self.db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")

    def _record_schema_version(self) -> None:
        self.db.execute(
            "INSERT OR IGNORE INTO schema_migration (version, applied_at, description) "
            "VALUES (?, ?, ?)",
            (_SCHEMA_VERSION, _now(), _SCHEMA_DESCRIPTION),
        )

    def close(self) -> None:
        self.db.close()

    @contextlib.contextmanager
    def _immediate(self):
        """An explicit ``BEGIN IMMEDIATE`` transaction -- see the module docstring.

        Guarded by ``self._write_lock`` so at most one thread is ever inside
        a transaction on this connection at a time (see the comment in
        ``__init__``).
        """
        with self._write_lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                yield
            except Exception:
                self.db.rollback()
                raise
            else:
                self.db.commit()

    # -- organizations ----------------------------------------------------

    def create_organization(self, slug: str, name: str) -> str:
        org_id = _new_id()
        try:
            self.db.execute(
                "INSERT INTO organization (id, slug, name, created_at) VALUES (?, ?, ?, ?)",
                (org_id, slug, name, _now()),
            )
        except sqlite3.IntegrityError as e:
            raise DuplicateSlug(slug) from e
        return org_id

    def get_organization(self, org_id: str) -> dict | None:
        row = self.db.execute("SELECT * FROM organization WHERE id = ?", (org_id,)).fetchone()
        return dict(row) if row else None

    def get_organization_by_slug(self, slug: str) -> dict | None:
        row = self.db.execute("SELECT * FROM organization WHERE slug = ?", (slug,)).fetchone()
        return dict(row) if row else None

    def get_or_create_organization(self, slug: str, name: str) -> dict:
        row = self.get_organization_by_slug(slug)
        if row is not None:
            return row
        try:
            org_id = self.create_organization(slug, name)
        except DuplicateSlug:
            row = self.get_organization_by_slug(slug)
            if row is not None:
                return row
            raise
        return self.get_organization(org_id)

    # -- users --------------------------------------------------------------

    def create_user(self, email: str, password: str, username: str = "") -> str:
        user_id = _new_id()
        password_hash, password_salt, params_version = authcrypto.hash_password(password)
        try:
            self.db.execute(
                "INSERT INTO user (id, email, username, password_hash, password_salt, "
                "password_algo, password_params_version, must_rehash, created_at) "
                "VALUES (?, ?, ?, ?, ?, 'scrypt', ?, 0, ?)",
                (
                    user_id, email.strip().lower(), username or None,
                    password_hash, password_salt, params_version, _now(),
                ),
            )
        except sqlite3.IntegrityError as e:
            raise DuplicateEmail(email) from e
        return user_id

    def get_user(self, user_id: str) -> dict | None:
        row = self.db.execute("SELECT * FROM user WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None

    def get_user_by_email(self, email: str) -> dict | None:
        row = self.db.execute(
            "SELECT * FROM user WHERE email = ?", (email.strip().lower(),)
        ).fetchone()
        return dict(row) if row else None

    # -- membership -----------------------------------------------------------

    def create_membership(self, org_id: str, user_id: str, role: str) -> str:
        if role not in ROLES:
            raise ValueError(f"unknown role {role!r}")
        membership_id = _new_id()
        try:
            self.db.execute(
                "INSERT INTO membership (id, org_id, user_id, role, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (membership_id, org_id, user_id, role, _now()),
            )
        except sqlite3.IntegrityError as e:
            if "UNIQUE" in str(e):
                raise ValueError(f"{user_id} is already a member of {org_id}") from e
            raise
        return membership_id

    def get_membership(self, org_id: str, user_id: str) -> dict | None:
        row = self.db.execute(
            "SELECT * FROM membership WHERE org_id = ? AND user_id = ?", (org_id, user_id)
        ).fetchone()
        return dict(row) if row else None

    def list_memberships_for_org(self, org_id: str) -> list[dict]:
        rows = self.db.execute(
            "SELECT * FROM membership WHERE org_id = ? ORDER BY created_at", (org_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def list_memberships_for_user(self, user_id: str) -> list[dict]:
        rows = self.db.execute(
            "SELECT * FROM membership WHERE user_id = ? ORDER BY created_at", (user_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def count_owners(self, org_id: str) -> int:
        row = self.db.execute(
            "SELECT COUNT(*) AS n FROM membership WHERE org_id = ? AND role = ?", (org_id, OWNER)
        ).fetchone()
        return row["n"]

    def update_membership_role(self, org_id: str, user_id: str, new_role: str) -> None:
        """Change a member's role. Refuses to demote the organization's last Owner.

        Runs the "is this the last Owner?" check and the role change itself
        inside one ``BEGIN IMMEDIATE`` transaction, so a second concurrent
        demotion of a different Owner cannot both succeed and leave the
        organization with none.
        """
        if new_role not in ROLES:
            raise ValueError(f"unknown role {new_role!r}")
        with self._immediate():
            row = self.db.execute(
                "SELECT role FROM membership WHERE org_id = ? AND user_id = ?", (org_id, user_id)
            ).fetchone()
            if row is None:
                raise NotAMember(f"{user_id} is not a member of {org_id}")
            if row["role"] == OWNER and new_role != OWNER:
                owners = self.db.execute(
                    "SELECT COUNT(*) AS n FROM membership WHERE org_id = ? AND role = ?",
                    (org_id, OWNER),
                ).fetchone()["n"]
                if owners <= 1:
                    raise LastOwnerError("the last Owner of an organization cannot be demoted")
            self.db.execute(
                "UPDATE membership SET role = ? WHERE org_id = ? AND user_id = ?",
                (new_role, org_id, user_id),
            )
            revoked = self._revoke_sessions_no_commit(user_id, org_id=org_id)
            self.record_audit(
                event_type="ROLE_CHANGED", org_id=org_id, user_id=user_id,
                target_type="membership", target_id=user_id,
                detail={
                    "old_role": row["role"], "new_role": new_role,
                    "sessions_revoked": revoked,
                },
            )

    def remove_membership(self, org_id: str, user_id: str) -> None:
        """Remove a member. Refuses to remove the organization's last Owner."""
        with self._immediate():
            row = self.db.execute(
                "SELECT role FROM membership WHERE org_id = ? AND user_id = ?", (org_id, user_id)
            ).fetchone()
            if row is None:
                raise NotAMember(f"{user_id} is not a member of {org_id}")
            if row["role"] == OWNER:
                owners = self.db.execute(
                    "SELECT COUNT(*) AS n FROM membership WHERE org_id = ? AND role = ?",
                    (org_id, OWNER),
                ).fetchone()["n"]
                if owners <= 1:
                    raise LastOwnerError("the last Owner of an organization cannot be removed")
            self.db.execute(
                "DELETE FROM membership WHERE org_id = ? AND user_id = ?", (org_id, user_id)
            )
            self._revoke_sessions_no_commit(user_id, org_id=org_id)

    # -- sessions -------------------------------------------------------------

    def create_session(
        self, user_id: str, active_org_id: str | None, *,
        scope: str = NORMAL, user_agent: str = "", ip: str = "",
        ttl_seconds: int = SESSION_TTL_SECONDS,
    ) -> tuple[str, dict]:
        if scope not in SCOPES:
            raise ValueError(f"unknown scope {scope!r}")
        raw_token = authcrypto.new_token()
        session_id = _new_id()
        now_dt = dt.datetime.now().replace(microsecond=0)
        now_s = now_dt.isoformat(sep=" ")
        expires_at = (now_dt + dt.timedelta(seconds=ttl_seconds)).isoformat(sep=" ")
        # One transaction for insert + limit enforcement: on this shared
        # connection, a bare INSERT interleaved into another thread's open
        # BEGIN IMMEDIATE would be swallowed by that thread's rollback.
        with self._immediate():
            self.db.execute(
                "INSERT INTO session_token (id, user_id, active_org_id, scope, token_hash, "
                "csrf_secret, user_agent_hash, ip_hash, created_at, last_seen_at, expires_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    session_id, user_id, active_org_id, scope, authcrypto.hash_token(raw_token),
                    authcrypto.new_token(), _fingerprint(user_agent), _fingerprint(ip),
                    now_s, now_s, expires_at,
                ),
            )
            self._enforce_session_limit(user_id)
        session = self.get_session(raw_token)
        assert session is not None
        return raw_token, session

    def get_session(self, raw_token: str) -> dict | None:
        """A live session, or ``None`` if it is missing, expired or revoked.

        Touches ``last_seen_at`` on every successful lookup -- this is the
        one place that happens, so callers never need to remember to.
        """
        token_hash = authcrypto.hash_token(raw_token)
        row = self.db.execute(
            "SELECT * FROM session_token WHERE token_hash = ?", (token_hash,)
        ).fetchone()
        if row is None:
            return None
        session = dict(row)
        if session["revoked_at"] is not None:
            return None
        if session["expires_at"] <= _now():
            return None
        now = _now()
        self.db.execute(
            "UPDATE session_token SET last_seen_at = ? WHERE id = ?", (now, session["id"])
        )
        session["last_seen_at"] = now
        return session

    def revoke_session(self, raw_token: str) -> None:
        token_hash = authcrypto.hash_token(raw_token)
        self.db.execute(
            "UPDATE session_token SET revoked_at = ? WHERE token_hash = ? AND revoked_at IS NULL",
            (_now(), token_hash),
        )

    def _revoke_sessions_no_commit(self, user_id: str, *, org_id: str | None = None) -> int:
        now = _now()
        if org_id is None:
            cur = self.db.execute(
                "UPDATE session_token SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL",
                (now, user_id),
            )
        else:
            cur = self.db.execute(
                "UPDATE session_token SET revoked_at = ? "
                "WHERE user_id = ? AND active_org_id = ? AND revoked_at IS NULL",
                (now, user_id, org_id),
            )
        return cur.rowcount

    def revoke_sessions_for_user(self, user_id: str, *, org_id: str | None = None) -> int:
        """Log the user out everywhere (or out of one organization)."""
        return self._revoke_sessions_no_commit(user_id, org_id=org_id)

    def _enforce_session_limit(self, user_id: str, limit: int = MAX_SESSIONS_PER_USER) -> None:
        rows = self.db.execute(
            "SELECT id FROM session_token WHERE user_id = ? AND revoked_at IS NULL "
            "ORDER BY created_at DESC, rowid DESC",
            (user_id,),
        ).fetchall()
        if len(rows) <= limit:
            return
        now = _now()
        self.db.executemany(
            "UPDATE session_token SET revoked_at = ? WHERE id = ?",
            [(now, r["id"]) for r in rows[limit:]],
        )

    def switch_organization(
        self, raw_token: str, new_org_id: str, *, user_agent: str = "", ip: str = "",
    ) -> tuple[str, dict]:
        """Rotate the caller's session into a different organization (§7.2a).

        A revoke-then-reissue, never an in-place mutation of ``active_org_id``
        -- every session token keeps one fixed scope and organization for its
        whole lifetime.
        """
        session = self.get_session(raw_token)
        if session is None:
            raise SessionNotFound("session is invalid or expired")
        if session["scope"] != NORMAL:
            raise ValueError("only a NORMAL session can switch organizations")
        if self.get_membership(new_org_id, session["user_id"]) is None:
            raise NotAMember(f"{session['user_id']} is not a member of {new_org_id}")
        self.revoke_session(raw_token)
        return self.create_session(
            session["user_id"], new_org_id, scope=NORMAL, user_agent=user_agent, ip=ip,
        )

    def cleanup_expired_sessions(self) -> int:
        """Delete rows already past ``expires_at``. Not required for correctness
        (an expired token is already rejected by :meth:`get_session`, an
        expired reset token by :meth:`redeem_password_reset`, an expired
        enrollment by :meth:`mfa_confirm`) -- just keeps ``auth.db`` from
        growing without bound. Expiring an unused reset token is audited
        (§7.5.7), and an expired unconfirmed enrollment's vault entry is
        removed along with its row.
        """
        now = _now()
        cur = self.db.execute("DELETE FROM session_token WHERE expires_at <= ?", (now,))
        for row in self.db.execute(
            "SELECT id, user_id FROM password_reset_token "
            "WHERE expires_at <= ? AND used_at IS NULL",
            (now,),
        ).fetchall():
            self.record_audit(
                event_type="PASSWORD_RESET_EXPIRED", user_id=row["user_id"],
                target_type="password_reset_token", target_id=row["id"],
            )
        self.db.execute("DELETE FROM password_reset_token WHERE expires_at <= ?", (now,))
        cutoff = (
            dt.datetime.now() - dt.timedelta(seconds=MFA_ENROLLMENT_TTL_SECONDS)
        ).replace(microsecond=0).isoformat(sep=" ")
        with self._immediate():
            # Select and delete inside one transaction, so an enrollment
            # confirmed between the two cannot be swept away.
            for row in self.db.execute(
                "SELECT user_id FROM mfa_secret "
                "WHERE confirmed_at IS NULL AND enrolled_at <= ?",
                (cutoff,),
            ).fetchall():
                self._mfa_delete_all_no_commit(row["user_id"])
        return cur.rowcount

    # -- rate limiting (D3) -----------------------------------------------------

    def rate_limit_check(self, key: str) -> None:
        """Raise :class:`RateLimited` if ``key`` is currently locked out."""
        row = self.db.execute(
            "SELECT locked_until FROM rate_limit_bucket WHERE key = ?", (key,)
        ).fetchone()
        if row is None or not row["locked_until"]:
            return
        if row["locked_until"] > _now():
            remaining = (
                dt.datetime.fromisoformat(row["locked_until"]) - dt.datetime.now()
            ).total_seconds()
            raise RateLimited(max(1, int(remaining)))

    def rate_limit_record_failure(self, key: str) -> None:
        now_dt = dt.datetime.now().replace(microsecond=0)
        now = now_dt.isoformat(sep=" ")
        row = self.db.execute(
            "SELECT failures, window_started_at FROM rate_limit_bucket WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            self.db.execute(
                "INSERT INTO rate_limit_bucket (key, failures, window_started_at, locked_until) "
                "VALUES (?, 1, ?, NULL)",
                (key, now),
            )
            return
        window_started = dt.datetime.fromisoformat(row["window_started_at"])
        if (now_dt - window_started).total_seconds() > _RL_WINDOW_SECONDS:
            failures, window_started_at = 1, now
        else:
            failures, window_started_at = row["failures"] + 1, row["window_started_at"]
        locked_until = None
        if failures >= _RL_THRESHOLD:
            lock_seconds = min(
                _RL_BASE_LOCK_SECONDS * (2 ** (failures - _RL_THRESHOLD)), _RL_MAX_LOCK_SECONDS
            )
            locked_until = (now_dt + dt.timedelta(seconds=lock_seconds)).isoformat(sep=" ")
        self.db.execute(
            "UPDATE rate_limit_bucket SET failures = ?, window_started_at = ?, locked_until = ? "
            "WHERE key = ?",
            (failures, window_started_at, locked_until, key),
        )

    def rate_limit_record_success(self, key: str) -> None:
        self.db.execute("DELETE FROM rate_limit_bucket WHERE key = ?", (key,))

    # -- login ------------------------------------------------------------------

    def login(
        self, email: str, password: str, *, org_id: str | None = None,
        user_agent: str = "", ip: str = "",
    ) -> LoginResult:
        """Verify credentials and, on success, issue a session.

        Rate-limited independently by account and by IP (D3), persisted so a
        process restart does not reset an attacker's clock. A nonexistent
        email is charged against the IP bucket exactly like a wrong password
        would be, so probing for valid emails is not free.
        """
        email_key = f"login:account:{email.strip().lower()}"
        ip_key = f"login:ip:{authcrypto.hash_token(ip)[:16]}" if ip.strip() else None
        for key in (k for k in (email_key, ip_key) if k):
            self.rate_limit_check(key)

        def _fail(reason: str) -> LoginResult:
            self.rate_limit_record_failure(email_key)
            if ip_key:
                self.rate_limit_record_failure(ip_key)
            self.record_audit(
                event_type="LOGIN_FAIL", outcome="fail", ip=ip, detail={"reason": reason},
            )
            return LoginResult(ok=False, reason=reason)

        user = self.get_user_by_email(email)
        if user is None or user["disabled_at"] is not None:
            return _fail("invalid_credentials")
        if not authcrypto.verify_password(
            password, user["password_hash"], user["password_salt"], user["password_params_version"]
        ):
            return _fail("invalid_credentials")

        self.rate_limit_record_success(email_key)
        if ip_key:
            self.rate_limit_record_success(ip_key)

        if authcrypto.needs_rehash(user["password_params_version"]):
            new_hash, new_salt, new_version = authcrypto.hash_password(password)
            self.db.execute(
                "UPDATE user SET password_hash = ?, password_salt = ?, "
                "password_params_version = ?, must_rehash = 0 WHERE id = ?",
                (new_hash, new_salt, new_version, user["id"]),
            )

        memberships = self.list_memberships_for_user(user["id"])
        if not memberships:
            return LoginResult(ok=False, reason="no_organization", user_id=user["id"])

        if org_id is not None:
            chosen = next((m for m in memberships if m["org_id"] == org_id), None)
            if chosen is None:
                raise NotAMember(f"{user['id']} is not a member of {org_id}")
        elif len(memberships) == 1:
            chosen = memberships[0]
        else:
            return LoginResult(
                ok=False, reason="organization_required",
                user_id=user["id"], organizations=memberships,
            )

        # §7.1/§7.2: a confirmed-MFA user gets a short-lived MFA_PENDING
        # session (completed by complete_mfa_login); an Owner/Admin who has
        # never confirmed MFA gets a BOOTSTRAP_MFA session that can only
        # reach the enroll/confirm routes -- mandatory enrollment, applying
        # to pre-existing Owner/Admin accounts on their next login too.
        scope, ttl = NORMAL, SESSION_TTL_SECONDS
        mfa_required = enrollment_required = False
        if self.has_confirmed_mfa(user["id"]):
            scope, ttl, mfa_required = MFA_PENDING, MFA_PENDING_SESSION_TTL_SECONDS, True
        elif chosen["role"] in (OWNER, ADMIN):
            scope, ttl = BOOTSTRAP_MFA, MFA_ENROLLMENT_SESSION_TTL_SECONDS
            enrollment_required = True

        raw_token, _session = self.create_session(
            user["id"], chosen["org_id"], scope=scope, user_agent=user_agent, ip=ip,
            ttl_seconds=ttl,
        )
        self.record_audit(
            event_type="LOGIN_OK", org_id=chosen["org_id"], user_id=user["id"], ip=ip,
            detail={"scope": scope},
        )
        return LoginResult(
            ok=True, user_id=user["id"], session_token=raw_token,
            scope=scope, active_org_id=chosen["org_id"],
            mfa_required=mfa_required, mfa_enrollment_required=enrollment_required,
        )

    # -- bootstrap (§7.1) ---------------------------------------------------------

    def bootstrap_owner(
        self, email: str, password: str, *, org_slug: str = "local", org_name: str = "Local",
    ) -> dict:
        """Create the very first Owner of ``org_slug``. CLI-only, by design.

        The guard against re-running this is a live query against
        ``membership``, re-checked inside the same ``BEGIN IMMEDIATE``
        transaction that inserts the new Owner -- there is no on-disk
        bootstrap flag to leave behind or replay.
        """
        org = self.get_or_create_organization(org_slug, org_name)
        if self.count_owners(org["id"]) > 0:
            raise BootstrapAlreadyDone(
                f"organization {org_slug!r} already has an Owner; bootstrap refuses to run twice"
            )
        with self._immediate():
            owners = self.db.execute(
                "SELECT COUNT(*) AS n FROM membership WHERE org_id = ? AND role = ?",
                (org["id"], OWNER),
            ).fetchone()["n"]
            if owners > 0:
                raise BootstrapAlreadyDone(
                    f"organization {org_slug!r} already has an Owner; "
                    "bootstrap refuses to run twice"
                )
            password_hash, password_salt, params_version = authcrypto.hash_password(password)
            user_id = _new_id()
            try:
                self.db.execute(
                    "INSERT INTO user (id, email, username, password_hash, password_salt, "
                    "password_algo, password_params_version, must_rehash, created_at) "
                    "VALUES (?, ?, NULL, ?, ?, 'scrypt', ?, 0, ?)",
                    (
                        user_id, email.strip().lower(), password_hash, password_salt,
                        params_version, _now(),
                    ),
                )
            except sqlite3.IntegrityError as e:
                raise DuplicateEmail(email) from e
            self.db.execute(
                "INSERT INTO membership (id, org_id, user_id, role, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (_new_id(), org["id"], user_id, OWNER, _now()),
            )
        return {
            "organization_id": org["id"],
            "organization_slug": org_slug,
            "user_id": user_id,
            "email": email.strip().lower(),
        }

    # -- MFA: TOTP enrollment and verification (§7.3, §7.4, D6) ------------------

    @staticmethod
    def _mfa_vault_account(user_id: str) -> str:
        """The per-user OS-credential-store entry name (D6): an opaque
        internal id, never the email."""
        return f"mfa-totp:{user_id}"

    def get_mfa(self, user_id: str) -> dict | None:
        row = self.db.execute(
            "SELECT * FROM mfa_secret WHERE user_id = ?", (user_id,)
        ).fetchone()
        return dict(row) if row else None

    def has_confirmed_mfa(self, user_id: str) -> bool:
        row = self.db.execute(
            "SELECT 1 FROM mfa_secret WHERE user_id = ? AND confirmed_at IS NOT NULL",
            (user_id,),
        ).fetchone()
        return row is not None

    def count_unused_recovery_codes(self, user_id: str) -> int:
        return self.db.execute(
            "SELECT COUNT(*) AS n FROM mfa_recovery_code WHERE user_id = ? AND used_at IS NULL",
            (user_id,),
        ).fetchone()["n"]

    def mfa_enroll(self, user_id: str, *, ip: str = "") -> dict:
        """Start (or restart) TOTP enrollment.

        The raw secret goes straight into the OS credential store -- if that
        store is unavailable this raises :class:`~formslang.secrets.SecureStorageUnavailable`
        and no enrollment exists at all (fail closed, never a plaintext
        fallback). A previous *unconfirmed* enrollment is silently replaced;
        a *confirmed* one is refused (§7.3: disable first, then re-enroll --
        and no endpoint ever returns a confirmed secret again).

        Returns ``{"secret", "otpauth_uri"}`` -- the only moment the raw
        secret ever leaves the process, and only in the response body of the
        authenticated enrollment call. Never log or persist either value.
        """
        user = self.get_user(user_id)
        if user is None:
            raise UserNotFound(user_id)
        secret = totp.generate_secret()
        with self._immediate():
            row = self.db.execute(
                "SELECT confirmed_at FROM mfa_secret WHERE user_id = ?", (user_id,)
            ).fetchone()
            if row is not None and row["confirmed_at"] is not None:
                raise MfaAlreadyConfirmed(
                    "MFA is already confirmed for this account; disable it before re-enrolling"
                )
            vault.set_secret(vault.SERVICE, self._mfa_vault_account(user_id), secret)
            now = _now()
            self.db.execute(
                "INSERT INTO mfa_secret (user_id, enrolled_at, confirmed_at, "
                "last_accepted_step, created_at) VALUES (?, ?, NULL, NULL, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET "
                "enrolled_at = excluded.enrolled_at, confirmed_at = NULL, "
                "last_accepted_step = NULL",
                (user_id, now, now),
            )
        self.record_audit(event_type="MFA_ENROLL_STARTED", user_id=user_id, ip=ip)
        return {
            "secret": secret,
            "otpauth_uri": totp.provisioning_uri(secret, account_name=user["email"]),
        }

    def _load_mfa_secret(self, user_id: str) -> str:
        """The raw secret from the OS vault, for a user with an ``mfa_secret``
        row. Fail closed: a row without a vault entry (auth.db copied to a
        different machine, vault wiped) is an error, never a bypass."""
        secret = vault.get_secret(vault.SERVICE, self._mfa_vault_account(user_id))
        if not secret:
            raise vault.SecureStorageUnavailable(
                "the MFA secret for this account is not in this machine's credential store"
            )
        return secret

    def mfa_confirm(self, user_id: str, code1: str, code2: str, *, ip: str = "") -> list[str]:
        """Confirm enrollment with two codes from *consecutive* time steps
        (§7.3.4) and return the plaintext recovery codes -- shown exactly
        once, only their hashes are stored.

        Runs inside one ``BEGIN IMMEDIATE`` transaction, so two concurrent
        confirmations cannot both validate the same codes. An enrollment
        older than ``MFA_ENROLLMENT_TTL_SECONDS`` is expired: it is removed
        and the caller must start again.
        """
        key = f"mfa:account:{user_id}"
        ip_key = f"mfa:ip:{authcrypto.hash_token(ip)[:16]}" if ip.strip() else None
        for k in (k for k in (key, ip_key) if k):
            self.rate_limit_check(k)
        expired = False
        codes: list[str] = []
        try:
            with self._immediate():
                row = self.db.execute(
                    "SELECT * FROM mfa_secret WHERE user_id = ?", (user_id,)
                ).fetchone()
                if row is None:
                    raise MfaNotEnrolled(user_id)
                if row["confirmed_at"] is not None:
                    raise MfaAlreadyConfirmed("MFA is already confirmed for this account")
                enrolled = dt.datetime.fromisoformat(row["enrolled_at"])
                if (dt.datetime.now() - enrolled).total_seconds() > MFA_ENROLLMENT_TTL_SECONDS:
                    # Delete, let the transaction COMMIT, and only then raise
                    # below -- raising from in here would roll the delete back.
                    self._mfa_delete_all_no_commit(user_id)
                    expired = True
                else:
                    secret = self._load_mfa_secret(user_id)
                    step1 = totp.verify_code(secret, code1)
                    step2 = totp.verify_code(secret, code2, last_accepted_step=step1)
                    if step1 is None or step2 != step1 + 1:
                        raise InvalidMfaCode(
                            "enter two consecutive codes: the current one, then the "
                            "next one the app shows -- if it keeps failing, check "
                            "that the device clock is in sync"
                        )
                    codes = self._replace_recovery_codes_no_commit(user_id)
                    self.db.execute(
                        "UPDATE mfa_secret SET confirmed_at = ?, last_accepted_step = ? "
                        "WHERE user_id = ?",
                        (_now(), step2, user_id),
                    )
        except InvalidMfaCode:
            self.rate_limit_record_failure(key)
            if ip_key:
                self.rate_limit_record_failure(ip_key)
            self.record_audit(
                event_type="MFA_FAILED", outcome="fail", user_id=user_id, ip=ip,
                detail={"via": "confirm"},
            )
            raise
        if expired:
            raise MfaEnrollmentExpired("this enrollment has expired; start enrollment again")
        self.rate_limit_record_success(key)
        if ip_key:
            self.rate_limit_record_success(ip_key)
        self.record_audit(event_type="MFA_CONFIRMED", user_id=user_id, ip=ip)
        return codes

    def _mfa_delete_all_no_commit(self, user_id: str) -> None:
        self.db.execute("DELETE FROM mfa_secret WHERE user_id = ?", (user_id,))
        self.db.execute("DELETE FROM mfa_recovery_code WHERE user_id = ?", (user_id,))
        vault.delete_secret(vault.SERVICE, self._mfa_vault_account(user_id))

    def _replace_recovery_codes_no_commit(self, user_id: str) -> list[str]:
        """Fresh recovery codes (hashes stored, plaintext returned once);
        every previous code, used or not, is revoked. 128 bits each."""
        self.db.execute("DELETE FROM mfa_recovery_code WHERE user_id = ?", (user_id,))
        codes = []
        now = _now()
        for _ in range(MFA_RECOVERY_CODE_COUNT):
            raw = os.urandom(16).hex()
            code = "-".join(raw[i : i + 4] for i in range(0, len(raw), 4))
            codes.append(code)
            self.db.execute(
                "INSERT INTO mfa_recovery_code (id, user_id, code_hash, created_at) "
                "VALUES (?, ?, ?, ?)",
                (_new_id(), user_id, authcrypto.hash_token(_normalize_recovery_code(code)), now),
            )
        return codes

    def _check_totp_no_commit(self, user_id: str, code: str) -> None:
        """Verify a TOTP code for a *confirmed* enrollment and advance the
        replay watermark. Must run inside ``_immediate()`` -- the read of
        ``last_accepted_step`` and its update are what make two concurrent
        validations of the same code impossible."""
        row = self.db.execute(
            "SELECT * FROM mfa_secret WHERE user_id = ? AND confirmed_at IS NOT NULL",
            (user_id,),
        ).fetchone()
        if row is None:
            raise MfaNotEnrolled(user_id)
        secret = self._load_mfa_secret(user_id)
        step = totp.verify_code(secret, code, last_accepted_step=row["last_accepted_step"])
        if step is None:
            raise InvalidMfaCode()
        self.db.execute(
            "UPDATE mfa_secret SET last_accepted_step = ? WHERE user_id = ?", (step, user_id)
        )

    def _consume_recovery_code_no_commit(self, user_id: str, code: str) -> int:
        """Single-use, atomically consumed (§7.3.4): the row flips to used
        inside the caller's ``BEGIN IMMEDIATE`` transaction, so a second
        concurrent attempt with the same code finds it already spent.
        Returns how many unused codes remain."""
        wanted = authcrypto.hash_token(_normalize_recovery_code(code))
        rows = self.db.execute(
            "SELECT id, code_hash FROM mfa_recovery_code WHERE user_id = ? AND used_at IS NULL",
            (user_id,),
        ).fetchall()
        matched_id = None
        for r in rows:  # constant-time per comparison, no early exit
            if authcrypto.constant_time_eq(r["code_hash"], wanted):
                matched_id = r["id"]
        if matched_id is None:
            raise InvalidMfaCode("invalid recovery code")
        cur = self.db.execute(
            "UPDATE mfa_recovery_code SET used_at = ? WHERE id = ? AND used_at IS NULL",
            (_now(), matched_id),
        )
        if cur.rowcount != 1:
            raise InvalidMfaCode("invalid recovery code")
        return self.count_unused_recovery_codes(user_id)

    @staticmethod
    def _looks_like_totp(code: str) -> bool:
        cleaned = (code or "").strip()
        return cleaned.isdigit() and len(cleaned) == totp.DIGITS

    def complete_mfa_login(
        self, raw_token: str, code: str, *, user_agent: str = "", ip: str = "",
    ) -> LoginResult:
        """Exchange an ``MFA_PENDING`` session for a ``NORMAL`` one (§7.2.5).

        ``code`` is a 6-digit TOTP code or a recovery code, told apart by
        shape. Rate-limited independently of the password step. A recovery
        code, once accepted, revokes every existing session for the user
        before the fresh one is issued (§7.3: a used recovery code means
        the second factor may be compromised).
        """
        session = self.get_session(raw_token)
        if session is None:
            raise SessionNotFound("session is invalid or expired")
        if session["scope"] != MFA_PENDING:
            raise ValueError("this session has no pending MFA step")
        user_id = session["user_id"]
        key = f"mfa:account:{user_id}"
        ip_key = f"mfa:ip:{authcrypto.hash_token(ip)[:16]}" if ip.strip() else None
        for k in (k for k in (key, ip_key) if k):
            self.rate_limit_check(k)

        used_recovery = not self._looks_like_totp(code)
        remaining = None
        try:
            with self._immediate():
                if used_recovery:
                    remaining = self._consume_recovery_code_no_commit(user_id, code)
                else:
                    self._check_totp_no_commit(user_id, code)
        except InvalidMfaCode:
            self.rate_limit_record_failure(key)
            if ip_key:
                self.rate_limit_record_failure(ip_key)
            self.record_audit(
                event_type="MFA_FAILED", outcome="fail",
                org_id=session["active_org_id"], user_id=user_id, ip=ip,
                detail={"via": "login"},
            )
            raise
        self.rate_limit_record_success(key)
        if ip_key:
            self.rate_limit_record_success(ip_key)

        if used_recovery:
            revoked = self.revoke_sessions_for_user(user_id)
            self.record_audit(
                event_type="MFA_RECOVERY_USED", org_id=session["active_org_id"],
                user_id=user_id, ip=ip,
                detail={"remaining_recovery_codes": remaining, "sessions_revoked": revoked},
            )
        else:
            self.revoke_session(raw_token)

        new_token, _new_session = self.create_session(
            user_id, session["active_org_id"], scope=NORMAL, user_agent=user_agent, ip=ip,
        )
        self.record_audit(
            event_type="LOGIN_OK", org_id=session["active_org_id"], user_id=user_id, ip=ip,
            detail={"scope": NORMAL, "mfa_method": "recovery" if used_recovery else "totp"},
        )
        return LoginResult(
            ok=True, user_id=user_id, session_token=new_token,
            scope=NORMAL, active_org_id=session["active_org_id"],
        )

    def mfa_regenerate_recovery_codes(
        self, user_id: str, code: str, *, ip: str = "",
    ) -> list[str]:
        """Fresh recovery codes for a confirmed enrollment, proven by a
        valid TOTP code (not a recovery code -- regeneration is a
        convenience, not a break-glass path). Every previous code is
        revoked."""
        key = f"mfa:account:{user_id}"
        ip_key = f"mfa:ip:{authcrypto.hash_token(ip)[:16]}" if ip.strip() else None
        for k in (k for k in (key, ip_key) if k):
            self.rate_limit_check(k)
        try:
            with self._immediate():
                self._check_totp_no_commit(user_id, code)
                codes = self._replace_recovery_codes_no_commit(user_id)
        except InvalidMfaCode:
            self.rate_limit_record_failure(key)
            if ip_key:
                self.rate_limit_record_failure(ip_key)
            self.record_audit(
                event_type="MFA_FAILED", outcome="fail", user_id=user_id, ip=ip,
                detail={"via": "regenerate"},
            )
            raise
        self.rate_limit_record_success(key)
        if ip_key:
            self.rate_limit_record_success(ip_key)
        self.record_audit(event_type="MFA_RECOVERY_REGENERATED", user_id=user_id, ip=ip)
        return codes

    def mfa_disable(self, user_id: str, password: str, code: str, *, ip: str = "") -> int:
        """Disable MFA: requires the password *and* a valid TOTP or recovery
        code in the same call (§7.4), removes the vault entry and every
        recovery code, and revokes every session. Returns how many sessions
        were revoked."""
        user = self.get_user(user_id)
        if user is None:
            raise UserNotFound(user_id)
        key = f"mfa:account:{user_id}"
        ip_key = f"mfa:ip:{authcrypto.hash_token(ip)[:16]}" if ip.strip() else None
        for k in (k for k in (key, ip_key) if k):
            self.rate_limit_check(k)

        def _charge_and_audit() -> None:
            self.rate_limit_record_failure(key)
            if ip_key:
                self.rate_limit_record_failure(ip_key)
            self.record_audit(
                event_type="MFA_FAILED", outcome="fail", user_id=user_id, ip=ip,
                detail={"via": "disable"},
            )

        if not authcrypto.verify_password(
            password, user["password_hash"], user["password_salt"],
            user["password_params_version"],
        ):
            _charge_and_audit()
            raise InvalidMfaCode("invalid password or code")
        try:
            with self._immediate():
                if self._looks_like_totp(code):
                    self._check_totp_no_commit(user_id, code)
                else:
                    if not self.has_confirmed_mfa(user_id):
                        raise MfaNotEnrolled(user_id)
                    self._consume_recovery_code_no_commit(user_id, code)
                self._mfa_delete_all_no_commit(user_id)
                revoked = self._revoke_sessions_no_commit(user_id)
        except InvalidMfaCode:
            _charge_and_audit()
            raise
        self.rate_limit_record_success(key)
        if ip_key:
            self.rate_limit_record_success(ip_key)
        self.record_audit(
            event_type="MFA_DISABLED", user_id=user_id, ip=ip,
            detail={"sessions_revoked": revoked},
        )
        return revoked

    def mfa_disable_cli(self, user_id: str) -> int:
        """Break-glass MFA removal for ``formslang auth reset-owner --clear-mfa``
        -- CLI-only (local host access is the authentication), never routed
        over HTTP. Revokes every session."""
        with self._immediate():
            self._mfa_delete_all_no_commit(user_id)
            revoked = self._revoke_sessions_no_commit(user_id)
        self.record_audit(
            event_type="MFA_DISABLED", user_id=user_id,
            detail={"via": "cli", "sessions_revoked": revoked},
        )
        return revoked

    # -- assisted password reset (§7.5, D2) --------------------------------------

    def issue_password_reset(
        self, *, issued_by: str, target_user_id: str, org_id: str, ip: str = "",
    ) -> str:
        """A short-lived, single-use reset token for a member of the issuer's
        organization. Returns the raw token exactly once -- only its hash is
        stored, tied to who issued it.

        Role rules (§7.5): an Admin may reset Developers and Viewers only;
        an Owner may reset anyone in the organization except another Owner.
        Nobody resets an Owner over HTTP -- the last-Owner path is
        :meth:`reset_owner_password_cli`.
        """
        issuer = self.get_membership(org_id, issued_by)
        target = self.get_membership(org_id, target_user_id)
        if issuer is None or issuer["role"] not in (OWNER, ADMIN):
            raise PermissionError("only an Owner or Admin can issue a password reset")
        if target is None:
            raise UserNotFound(target_user_id)
        if target["role"] == OWNER:
            raise PermissionError(
                "an Owner's password cannot be reset over HTTP -- "
                "use `formslang auth reset-owner` on the host"
            )
        if issuer["role"] == ADMIN and target["role"] not in (DEVELOPER, VIEWER):
            raise PermissionError("an Admin can only reset Developers and Viewers")
        raw = authcrypto.new_token()
        now_dt = dt.datetime.now().replace(microsecond=0)
        expires = (now_dt + dt.timedelta(seconds=PASSWORD_RESET_TTL_SECONDS)).isoformat(sep=" ")
        with self._immediate():
            # One outstanding token per target: issuing again supersedes.
            self.db.execute(
                "DELETE FROM password_reset_token WHERE user_id = ? AND used_at IS NULL",
                (target_user_id,),
            )
            self.db.execute(
                "INSERT INTO password_reset_token (id, user_id, issued_by, token_hash, "
                "created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    _new_id(), target_user_id, issued_by, authcrypto.hash_token(raw),
                    now_dt.isoformat(sep=" "), expires,
                ),
            )
        self.record_audit(
            event_type="PASSWORD_RESET_ISSUED", org_id=org_id, user_id=issued_by,
            target_type="user", target_id=target_user_id, ip=ip,
        )
        return raw

    def redeem_password_reset(self, token: str, new_password: str, *, ip: str = "") -> str:
        """Set a new password from a reset token. Single-use, expiring, and
        deliberately narrow: every session is revoked, MFA is untouched
        (§7.5.5 -- the normal MFA login step still applies afterwards), and
        the user is *not* logged in by this call. Returns the user id.

        The failure message never says whether the token existed, whose it
        was, or why it failed -- no account enumeration through this route.
        """
        if not new_password:
            raise ValueError("password must not be empty")
        ip_key = f"reset:ip:{authcrypto.hash_token(ip)[:16]}" if ip.strip() else None
        if ip_key:
            self.rate_limit_check(ip_key)
        token_hash = authcrypto.hash_token(token or "")
        # Hashed before the transaction: the KDF is the expensive part and
        # must not run while the store-wide write lock is held -- and doing
        # it unconditionally keeps valid and invalid tokens on the same
        # timing path.
        password_hash, password_salt, params_version = authcrypto.hash_password(new_password)
        with self._immediate():
            row = self.db.execute(
                "SELECT * FROM password_reset_token WHERE token_hash = ?", (token_hash,)
            ).fetchone()
            if row is None or row["used_at"] is not None or row["expires_at"] <= _now():
                row = None
            else:
                self.db.execute(
                    "UPDATE user SET password_hash = ?, password_salt = ?, "
                    "password_params_version = ?, must_rehash = 0 WHERE id = ?",
                    (password_hash, password_salt, params_version, row["user_id"]),
                )
                self.db.execute(
                    "UPDATE password_reset_token SET used_at = ? WHERE id = ?",
                    (_now(), row["id"]),
                )
                revoked = self._revoke_sessions_no_commit(row["user_id"])
        if row is None:
            # Recorded only after the transaction is out of the way: a
            # failure written inside it would be rolled back by the very
            # exception it accompanies, and the limiter would never engage.
            if ip_key:
                self.rate_limit_record_failure(ip_key)
            raise ValueError("invalid or expired reset token")
        if ip_key:
            self.rate_limit_record_success(ip_key)
        self.record_audit(
            event_type="PASSWORD_RESET_COMPLETED", user_id=row["user_id"], ip=ip,
            detail={"sessions_revoked": revoked},
        )
        return row["user_id"]

    def reset_owner_password_cli(self, email: str, new_password: str) -> dict:
        """Last-Owner recovery (§7.5): set an Owner's password directly.
        CLI-only -- local host access is the authentication. Revokes every
        session and preserves MFA."""
        if not new_password:
            raise ValueError("password must not be empty")
        user = self.get_user_by_email(email)
        if user is None:
            raise UserNotFound(email)
        if not any(m["role"] == OWNER for m in self.list_memberships_for_user(user["id"])):
            raise PermissionError(
                "reset-owner is for Owner accounts only -- "
                "other members are reset by their Owner/Admin in the app"
            )
        password_hash, password_salt, params_version = authcrypto.hash_password(new_password)
        with self._immediate():
            self.db.execute(
                "UPDATE user SET password_hash = ?, password_salt = ?, "
                "password_params_version = ?, must_rehash = 0 WHERE id = ?",
                (password_hash, password_salt, params_version, user["id"]),
            )
            revoked = self._revoke_sessions_no_commit(user["id"])
        self.record_audit(
            event_type="PASSWORD_RESET_COMPLETED", user_id=user["id"],
            detail={"via": "cli", "sessions_revoked": revoked},
        )
        return {"user_id": user["id"], "email": user["email"], "sessions_revoked": revoked}

    # -- projects (§8, §9) -------------------------------------------------------

    def get_project(self, project_id: str) -> dict | None:
        row = self.db.execute("SELECT * FROM project WHERE id = ?", (project_id,)).fetchone()
        return dict(row) if row else None

    def list_projects_for_org(self, org_id: str) -> list[dict]:
        rows = self.db.execute(
            "SELECT * FROM project WHERE org_id = ? AND deleted_at IS NULL ORDER BY created_at",
            (org_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def register_external_project(
        self, org_id: str, name: str, external_path: str | Path, *, created_by: str,
    ) -> dict:
        """Idempotently register an existing ``.session.db`` as EXTERNAL_LEGACY (§9).

        The path is resolved and, on Windows, case-folded (``os.path.normcase``)
        before being compared or stored, so two different-looking candidate
        strings for the same file register once, not twice. The whole
        check-then-insert runs inside one ``BEGIN IMMEDIATE`` transaction, so
        two concurrent registration runs racing on the same file cannot both
        insert a row for it.
        """
        resolved = Path(external_path).expanduser().resolve()
        if not resolved.is_file():
            raise ValueError(f"not a file: {resolved}")
        key = os.path.normcase(str(resolved))
        with self._immediate():
            row = self.db.execute(
                "SELECT * FROM project WHERE external_path = ?", (key,)
            ).fetchone()
            if row is not None:
                return dict(row)
            # Belt-and-suspenders: a registration recorded under a different
            # string (a mapped drive, a UNC path, an 8.3 short name) that
            # resolves to the same file on disk is still the same project.
            for candidate in self.db.execute(
                "SELECT * FROM project WHERE storage_mode = ?", (EXTERNAL_LEGACY,)
            ).fetchall():
                try:
                    if os.path.samefile(candidate["external_path"], key):
                        return dict(candidate)
                except OSError:
                    continue  # that registration's file is gone -- not a match
            project_id = _new_id()
            self.db.execute(
                "INSERT INTO project (id, org_id, name, storage_mode, external_path, "
                "created_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (project_id, org_id, name, EXTERNAL_LEGACY, key, created_by, _now()),
            )
        return self.get_project(project_id)

    def mark_project_adopted(self, project_id: str, session_db_path: str | Path) -> None:
        """Flip a project from EXTERNAL_LEGACY to ADOPTED. Called once, by
        :func:`formslang.projects.adopt_project`, after the copy is installed."""
        self.db.execute(
            "UPDATE project SET storage_mode = ?, session_db_path = ?, "
            "external_path = NULL, adopted_at = ? WHERE id = ?",
            (ADOPTED, str(session_db_path), _now(), project_id),
        )

    def grant_project_permission(
        self, project_id: str, user_id: str, permission: str, *, granted_by: str,
    ) -> None:
        """Give a Viewer the one permission the matrix lets them hold (§5): EXPORT."""
        if permission != "EXPORT":
            raise ValueError(f"unknown project permission {permission!r}")
        try:
            self.db.execute(
                "INSERT INTO project_permission "
                "(id, project_id, user_id, permission, granted_by, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (_new_id(), project_id, user_id, permission, granted_by, _now()),
            )
        except sqlite3.IntegrityError:
            pass  # already granted -- idempotent

    def has_project_permission(self, project_id: str, user_id: str, permission: str) -> bool:
        row = self.db.execute(
            "SELECT 1 FROM project_permission WHERE project_id = ? AND user_id = ? "
            "AND permission = ?",
            (project_id, user_id, permission),
        ).fetchone()
        return row is not None

    # -- audit log ------------------------------------------------------------------

    def record_audit(
        self, *, event_type: str, outcome: str = "ok", org_id: str | None = None,
        user_id: str | None = None, actor_email: str = "", target_type: str = "",
        target_id: str = "", ip: str = "", detail: dict | None = None,
    ) -> None:
        """One structured row per security-relevant event (design doc §7,
        Phase 3 event list).

        ``detail`` is filtered through :data:`_AUDIT_DETAIL_KEYS` -- an
        allowlist, so no secret (password, TOTP code or secret, otpauth URI,
        recovery code, session/CSRF/reset token, project content) can reach
        ``detail_json`` even by accident. Actors are recorded as opaque IDs;
        ``actor_email`` stays supported for callers that truly need it but
        no Phase 3 event passes it.
        """
        detail_json = None
        if detail:
            filtered = {k: v for k, v in detail.items() if k in _AUDIT_DETAIL_KEYS}
            if filtered:
                detail_json = json.dumps(filtered, sort_keys=True)
        self.db.execute(
            "INSERT INTO audit_log (id, at, org_id, user_id, actor_email_snapshot, "
            "event_type, target_type, target_id, outcome, ip_hash, detail_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                _new_id(), _now(), org_id, user_id, actor_email.strip().lower(),
                event_type, target_type, target_id, outcome, _fingerprint(ip),
                detail_json,
            ),
        )

    def list_audit_events(
        self, *, org_id: str | None = None, user_id: str | None = None, limit: int = 100,
    ) -> list[dict]:
        where, params = [], []
        if org_id is not None:
            where.append("org_id = ?")
            params.append(org_id)
        if user_id is not None:
            where.append("user_id = ?")
            params.append(user_id)
        sql = "SELECT * FROM audit_log"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY at DESC, id DESC LIMIT ?"
        params.append(max(1, min(int(limit), 1000)))
        return [dict(r) for r in self.db.execute(sql, params).fetchall()]
