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

Design reference: ``docs/auth-multitenancy-design.md``. This module is
Phase 1/2 of that document's §11 phased delivery -- schema, scrypt hashing,
sessions, RBAC role constants, and the scoped bootstrap flow. MFA, assisted
password reset, and the full audit trail are Phase 3 and are deliberately
not implemented here; the tables they will use already exist below (a
Phase 1 deliverable is the complete schema), but nothing yet reads or
writes ``mfa_secret``, ``mfa_recovery_code`` or ``password_reset_token``.

One consequence worth stating plainly, not burying in a docstring nobody
reads: because MFA enrollment does not exist yet, :meth:`AuthStore.login`
never issues the ``BOOTSTRAP_MFA`` or ``MFA_PENDING`` scopes the design
document's §7.1/§7.2 describe -- every session issued today is ``NORMAL``.
The schema and the ``scope`` column are ready for Phase 3 to wire in; the
mandatory-MFA-for-Owner/Admin enforcement itself is not live until then.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import hashlib
import os
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path

from . import authcrypto, config

AUTH_ENV = "FORMSLANG_AUTH"

OWNER, ADMIN, DEVELOPER, VIEWER = "OWNER", "ADMIN", "DEVELOPER", "VIEWER"
ROLES = (OWNER, ADMIN, DEVELOPER, VIEWER)

NORMAL, MFA_PENDING, BOOTSTRAP_MFA = "NORMAL", "MFA_PENDING", "BOOTSTRAP_MFA"
SCOPES = (NORMAL, MFA_PENDING, BOOTSTRAP_MFA)

EXTERNAL_LEGACY, ADOPTED = "EXTERNAL_LEGACY", "ADOPTED"
STORAGE_MODES = (EXTERNAL_LEGACY, ADOPTED)

SESSION_TTL_SECONDS = 12 * 60 * 60
MAX_SESSIONS_PER_USER = 5

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


def auth_enabled() -> bool:
    """Whether the auth subsystem is active for this process.

    Mirrors ``FORMSLANG_SECRET_BACKEND``'s reading convention in
    ``secrets.py``: empty or unset is off, and off is the only default that
    keeps every existing local install behaving exactly as it did before
    this module existed.
    """
    return os.environ.get(AUTH_ENV, "").strip().lower() in {"1", "true", "on", "yes"}


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


class AuthStore:
    """The control-plane database: one file, ``auth.db``, per FormsLang install."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, isolation_level=None, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.execute("PRAGMA journal_mode = WAL")
        self.db.execute("PRAGMA busy_timeout = 5000")
        self.db.executescript(SCHEMA)
        self._migrate()
        self._record_schema_version()
        # One sqlite3.Connection, shared by every thread of a ThreadingHTTPServer
        # (workbench.py). SQLite itself only ever has one transaction in flight
        # per connection; two threads racing BEGIN IMMEDIATE on it would hit
        # "cannot start a transaction within a transaction" instead of queuing
        # behind PRAGMA busy_timeout (that PRAGMA only arbitrates separate
        # connections/processes, not two threads sharing this one). This lock
        # is what actually serializes them.
        self._write_lock = threading.Lock()

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
            self._revoke_sessions_no_commit(user_id, org_id=org_id)

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
    ) -> tuple[str, dict]:
        if scope not in SCOPES:
            raise ValueError(f"unknown scope {scope!r}")
        raw_token = authcrypto.new_token()
        session_id = _new_id()
        now_dt = dt.datetime.now().replace(microsecond=0)
        now_s = now_dt.isoformat(sep=" ")
        expires_at = (now_dt + dt.timedelta(seconds=SESSION_TTL_SECONDS)).isoformat(sep=" ")
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
            "ORDER BY created_at DESC",
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
        (an expired token is already rejected by :meth:`get_session`) -- just
        keeps ``auth.db`` from growing without bound.
        """
        now = _now()
        cur = self.db.execute("DELETE FROM session_token WHERE expires_at <= ?", (now,))
        self.db.execute("DELETE FROM password_reset_token WHERE expires_at <= ?", (now,))
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

        # MFA is Phase 3 -- see the module docstring. Every session issued
        # here is NORMAL until MFA enrollment exists to gate it.
        raw_token, _session = self.create_session(
            user["id"], chosen["org_id"], scope=NORMAL, user_agent=user_agent, ip=ip,
        )
        return LoginResult(
            ok=True, user_id=user["id"], session_token=raw_token,
            scope=NORMAL, active_org_id=chosen["org_id"],
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
        target_id: str = "", ip: str = "",
    ) -> None:
        """One row. Phase 2 writes exactly one event type (``PROJECT_ADOPTED``,
        from adoption) -- see the module docstring for why a full audit trail
        is Phase 3, not built out here."""
        self.db.execute(
            "INSERT INTO audit_log (id, at, org_id, user_id, actor_email_snapshot, "
            "event_type, target_type, target_id, outcome, ip_hash, detail_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)",
            (
                _new_id(), _now(), org_id, user_id, actor_email.strip().lower(),
                event_type, target_type, target_id, outcome, _fingerprint(ip),
            ),
        )
