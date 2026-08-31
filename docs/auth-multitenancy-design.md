# FormsLang — Authentication & Multi-Tenant Isolation (Design Proposal)

**Status: architecture conceptually approved (2026-08-31), revised per
review, awaiting re-approval before implementation.** Nothing in this
document is implemented. It is the contract to review before Phase 1
(§11) starts. No code, no commit, no push.

This proposal is independent of, and does not replace, the in-flight
Security & Compliance work (`formslang/sensitive.py`, the sensitive-data
scanner, and the planned `formslang/policy.py`, the AI-provider egress
gate). Those two modules answer *"is this code safe to hand to a cloud
model?"* inside a single project's analysis; they carry no concept of a
user or an organization today. This document answers a different question
— *"who is allowed to open this project at all?"* — and is the layer those
two modules will eventually sit inside of. Building that connection is out
of scope here; this proposal stands on its own and changes nothing about
the scanner or the policy gate.

## 0. Revision note (2026-08-31)

The architecture is approved conceptually. This revision resolves four
open decisions and twelve required corrections raised in review. Nothing
below is a new idea introduced by this revision — everything is either a
decision the review made explicitly, or a fix to an internal
contradiction the review caught. Map:

| # | Review item | Where it landed |
|---|---|---|
| D1 | scrypt approved, with salt/params/versioning/rehash requirements | §4 (`user` table), §7.2, §10 |
| D2 | assisted reset approved, with cross-role restrictions | §5, §7.5, §10 |
| D3 | SQLite-backed rate limiting, survives restart | §6, §10 |
| D4 | no non-loopback bind in v1; reverse proxy only | §2.4, §6 |
| 1 | MFA key moves out of the data dir into the OS credential store | §2.3, §4, §10 |
| 2 | session gets an explicit `active_org_id`, revalidated every request | §2.2, §4, §7.2a |
| 3 | explicit `project_permission` table for Viewer export grants | §4, §5 |
| 4 | scoped bootstrap session, no reusable bootstrap flag | §7.1 |
| 5 | `auth.db` created lazily, never on a plain local-mode upgrade | §2.4, §7.1, §9 |
| 6 | explicit CSRF token + Origin validation, on top of the existing gate | §6, §12 |
| 7 | legacy external paths vs. team-mode "adoption" — contradiction resolved | §8, §9 |
| 8 | migration/adoption idempotency, path normalization, FK pragmas | §4, §9 |
| 9 | QR code generation — no stdlib QR, no external service | §7.3, §10 (D5) |
| 10 | session rotation events, per-user session limit, cleanup | §7.6 |
| 11 | `auth.db` operational hardening (pragmas, indexes, constraints, backup) | §4 |
| 12 | four-phase delivery, team mode gated on the first three being green | §11 |

---

## 1. Current state (what this proposal builds on)

FormsLang today has **no concept of a user**. Confirmed by reading the
code, not assumed:

- `formslang/workbench.py` binds loopback only — `serve()` raises
  `ValueError` unconditionally for any host other than
  `127.0.0.1`/`localhost`/`::1` (`workbench.py:862-866`). This proposal
  **does not change that** — see D4 in §2.4.
- A "project" is one SQLite file, `<name>.session.db`, opened directly by
  `Store(path)` (`store.py:177`), wherever the CLI or the user pointed it
  (`cli.py:260-263`). There is no registry of projects anywhere.
- Settings are one global `config.json`. The only secret handling that
  exists is the AI provider API key, kept in the OS credential store via
  `formslang/secrets.py` (Windows Credential Manager / macOS Keychain /
  Secret Service) — **this proposal now reuses that exact mechanism for
  MFA key material** instead of inventing a parallel file-based one (§2.3,
  §4).
- **FormsLang runs on the Python standard library alone, by explicit,
  documented design** (`pyproject.toml`: `dependencies = []`). D1 (scrypt)
  and D4 (no bind change) both preserve this principle without exception.
  D5 (§10) flags the one place a real dependency question remains open:
  rendering a QR code.
- **A full compromise of the OS account FormsLang runs as is explicitly
  out of this application's defense capability.** This was stated as a
  limitation in the prior draft; the review asked for it to be elevated
  into the threat model itself, not left as a footnote — done in §3. No
  design in this document claims to defend against an attacker who
  already controls the host.

---

## 2. Architecture

### 2.1 Model

```
Organization
  └── Membership (User × Role)
      └── Project  (registry row: org_id, storage_mode, path)
          ├── project_permission (per-user, per-project grants — e.g.
          │   a Viewer authorized to export a specific project; see §5)
          └── <project's own .session.db>  (unchanged: forms, tasks,
              proposals, decisions, unit_analysis, test_case — the
              Security & Compliance work reads/writes here exactly as it
              does today, untouched by this proposal)
```

A **new control-plane database**, separate from every project's
`.session.db`, holds identity and authorization: `Organization`, `User`,
`Membership`, `Project`, `ProjectPermission`, `SessionToken`, `MfaSecret`,
`MfaRecoveryCode`, `AuditLog`, `PasswordResetToken`, `SchemaMigration`. See
§4 for the full schema.

### 2.2 Process model, and the active-organization fix

Still one Python process, `http.server.ThreadingHTTPServer`, stdlib only.
A gate runs at the top of `do_GET`/`do_POST`, before the existing
`if/elif` route chain, resolving the session cookie.

**Correction resolved (review item 2):** the prior draft said the session
resolves `(user_id, org_id, role)` but the schema never actually carried
an `org_id`. Fixed by making the organization an explicit, first-class
part of the session, not something inferred per request:

- `session_token` carries `active_org_id` (nullable only for a bootstrap
  session — §7.1).
- **Every request re-validates `Membership(user_id, active_org_id)`
  server-side** — the session caches *which* org is active, never *that*
  the user is still authorized in it. A membership removed mid-session is
  denied on the very next request, not after the session expires.
- **The client never supplies an organization id that is trusted on its
  own.** A request naming a project implies an org through that project's
  `org_id`; the server checks that org against the session's
  `active_org_id` and the live `Membership` row — never the reverse.
- **Switching organizations rotates the session** (new token issued, old
  one revoked) rather than mutating `active_org_id` on the existing row —
  see the new flow in §7.2a. This keeps "one session token = one fixed
  org for its whole life," which is easier to reason about and to audit
  than a session whose scope can silently change underneath it.

### 2.3 Storage layout — MFA secret moved out of the data directory (revised D6, 2026-08-31)

**Correction resolved (review item 1):** the prior draft proposed
`<data_dir>/.keys/mfa.key` protected by `chmod 600`. Rejected in review,
correctly: a mode bit is not a real boundary, especially not on Windows,
and a key sitting next to the database it protects means a single
directory copy — a backup, a stolen drive, a misconfigured sync tool —
exfiltrates both the ciphertext and the key together.

**Revised design (D6, supersedes the envelope-encryption design below
this note originally described):** each user's raw TOTP secret is stored
as **one entry per user, directly in the OS credential store**, using
**the exact mechanism `secrets.py` already implements and this project
already trusts** for the AI provider API key (`ctypes`/Windows Credential
Manager, `security` on macOS, `secret-tool`/Secret Service on Linux, no
silent plaintext fallback) — `secrets.py` is parameterized from its
current single hardcoded `(service, account)` pair to accept a caller-
supplied account name, and MFA uses `FormsLang:mfa-totp:<user_id>` (one
opaque entry per user; `<user_id>` is an internal UUID, never the email).
`auth.db` never holds a TOTP secret in any form, plaintext or encrypted —
only enrollment/confirmation metadata (§4).

The original design here specified **envelope encryption**: a single
Key Encryption Key (KEK) in the OS store wrapping every user's secret,
with ciphertext+nonce+key-version in `auth.db`. That was rejected in
Phase 3 planning (2026-08-31): it requires a real, audited AEAD
implementation, which under this project's crypto rules means either a
new third-party dependency or hand-rolled AES-GCM/ChaCha20 — the
one-entry-per-user design needs neither. It also removes a shared-fatal
point: a KEK compromise would have exposed every user's secret at once;
per-user entries mean compromising one user's secret does not touch any
other's, and there is no key-rotation maintenance operation to get
wrong. The trade accepted in return: N credential-store entries instead
of 1 (irrelevant at FormsLang's scale — no vault backend here has a
practical entry-count limit that matters).

```
<data_dir>/
  auth.db                          # organization, user, membership, project,
                                    # project_permission, session_token,
                                    # mfa_secret (enrollment/confirmation
                                    # metadata only — never the secret
                                    # itself, see §4), mfa_recovery_code,
                                    # audit_log, password_reset_token,
                                    # schema_migration
  orgs/
    <org_id>/
      projects/
        <project_id>/
          main.session.db          # exactly today's Store schema, untouched
          exports/
```

No file under `data_dir` can ever reveal a TOTP secret on its own — a
copy of `auth.db` alone, without the matching OS credential store entry
for that specific user, is worthless for MFA bypass (see §10 for the
honest limits of this: it also means a disaster-recovery restore of
`auth.db` to a different machine leaves every user's MFA undecryptable
unless each user's OS-store entry is separately re-provisioned or the
user re-enrolls).

**Fail-closed, always:** if the OS credential store is unavailable when
enrollment or TOTP verification needs it, the operation fails with an
actionable error — the same `SecureStorageUnavailable` posture
`secrets.py` already uses — never a silent fallback to a weaker
mechanism. On Linux without a running Secret Service daemon (headless
server, container, CI) this means MFA enrollment is refused outright,
documented as a known limitation (§10), not silently degraded.

### 2.4 The two modes — D4: no non-loopback bind in v1

**D4 approved as stated: FormsLang itself never listens on anything but
`127.0.0.1` in this version, in either mode.** This replaces the prior
draft's plan to conditionally narrow `serve()`'s refusal for team mode.
That plan is withdrawn — it is not merely deferred, it is the wrong shape
for v1. The consequence is a genuine simplification: **`serve()`'s
existing hard loopback-only refusal (`workbench.py:862-866`) needs zero
code changes.** Team/server mode is a deployment topology, not a bind-time
condition:

```
Internet ──HTTPS──▶ nginx / Caddy (this host, public IP) ──HTTP──▶ FormsLang (127.0.0.1:port)
```

Because every request FormsLang ever receives is still, physically, a
loopback connection, `_host_is_local()`'s protection against DNS
rebinding is preserved by construction for anything that isn't the
configured reverse proxy — but the proxy itself needs to forward a
`Host:` header carrying the public hostname, which today's allowlist
would reject. That is solved with an explicit, narrow trust mechanism,
**not** by trusting any `X-Forwarded-*` header at face value (review item
6/D4's own text: *"não confiar em X-Forwarded-Proto enviado por cliente
comum"*):

- `FORMSLANG_TRUSTED_PROXY_TOKEN` — a shared secret set identically in
  FormsLang's environment and in the reverse proxy's config (e.g. a
  Caddy/nginx directive adding `X-FormsLang-Proxy-Token: <value>` to every
  proxied request). Anyone else connecting to the loopback socket does not
  know this value.
- The renamed `_host_is_allowed()` accepts the loopback names exactly as
  today, **unconditionally**. It additionally accepts
  `FORMSLANG_PUBLIC_HOSTNAME` (operator-configured, one explicit value,
  never a wildcard) **only when** the proxy-token header is present and
  matches. No token, or a wrong one: the request is refused exactly as it
  is today for any foreign Host header — the local-mode behavior is
  unaffected by this feature existing.
- `X-Forwarded-Proto` / `X-Forwarded-For` are honored (for the `Secure`
  cookie flag decision and for the hashed-IP audit field) **under the
  same condition** — token present and matching. Otherwise FormsLang uses
  its own view: the raw socket peer (always loopback) and `http`, never
  trusting an unauthenticated claim of `https`.
- `0.0.0.0` / any other bind address stays refused, full stop, in this
  version — matching D4's explicit instruction.

Local single-user mode is unaffected by any of this: `127.0.0.1` bind,
loopback-only allowlist, `FORMSLANG_TRUSTED_PROXY_TOKEN` unset and
therefore inert.

**Local auth-off behavior (review item 5), stated precisely:** when
`FORMSLANG_AUTH=off` (the default in local mode), FormsLang does not
create `auth.db`, does not require an email/password, does not show a
login screen, and does not silently create any user. `auth.db` and the
first Owner are created **only** by one explicit, operator-initiated
action: running `formslang auth bootstrap-owner` (which itself creates
`auth.db` lazily if it doesn't exist yet), turning `FORMSLANG_AUTH=on`
and completing the bootstrap prompt it triggers, or starting a
multi-organization migration. A fresh v-next install that never touches
any of these behaves identically to today — no new file, no new prompt.

---

## 3. Threat model

**Assets:** Forms source, APEX export artifacts and `compliance.md`
reports, AI provider credentials, user credentials (password hashes, TOTP
secrets, recovery codes), session tokens, audit log.

**Actors:** an anonymous network attacker (team/server mode only); an
authenticated user of Organization A attempting to reach Organization B's
data; **an attacker who has already obtained OS-level control of the
account FormsLang runs as** (elevated to a first-class actor in this
revision, per review item 1 — see the row below); a malicious or
malformed project name/input attempting path traversal; a page on another
origin attempting CSRF or DNS-rebinding.

| Threat | Mitigation | Where it lives |
|---|---|---|
| **Full OS-level compromise of the FormsLang service account** | **Not fully defensible by the application — stated explicitly, not implied.** Such an attacker can read the OS credential store (including the MFA KEK) and impersonate the running process. Mitigations are OS-level, outside this document's code: least-privilege service account, disk encryption, endpoint protection, credential-store ACLs, host hardening. Nothing in §2–§9 claims otherwise. | Out of application scope, by design |
| IDOR — guessing/incrementing an org or project id | Every route re-derives access via `authorize_project_access(user, active_org_id, project_id)`, which joins through the live `Membership` row every time, never trusting a client-supplied org/project pairing on its own | `formslang/authstore.py` |
| Cross-org data leakage | `.session.db` paths are never client input, resolved only via `resolve_project_path(project_id)`, itself gated by the same chokepoint; a project belonging to another org is not merely denied, it is 404'd — existence is not leaked | Same module |
| Path traversal / symlink escape | Paths built from server UUIDs only; resolve symlinks first, then verify containment under `data_dir` | Same module |
| Credential stuffing / brute force | scrypt (D1) + progressive delay + rate limiting **persisted in SQLite** (D3), keyed by account and by IP independently, surviving a process restart | New |
| Session fixation / hijacking | Opaque token, stored **hashed**, rotated on login, on MFA success, on org switch, and on any privilege change (review item 10); `HttpOnly; Secure; SameSite=Lax` | New |
| CSRF | Existing strict Content-Type gate (`workbench.py:756-763`), **plus** an explicit per-session CSRF token required on every mutating request, **plus** strict `Origin` validation against the same allowlist `_host_is_allowed()` uses (review item 6) | Extends existing + new |
| DNS rebinding | `_host_is_allowed()` regression-tested to still refuse any foreign `Host:` header in local mode after the team-mode allowlist extension is added (§2.4) | Extends existing |
| MFA secret exposure | Envelope-encrypted, KEK in the OS credential store (§2.3), never returned after enrollment, no route can return another user's secret because the route does not exist | New |
| A legacy (unadopted) project opened while in team mode | Team mode refuses to list or open any `project.storage_mode = EXTERNAL_LEGACY` row — only `ADOPTED` projects are reachable there (review item 7) | §8, §9 |
| Privilege escalation via role tampering | Role is never embedded in the session token — always a fresh `Membership` lookup; MFA required for Owner/Admin before the role change even takes effect | New |
| Audit/app log leaking source code or secrets | `audit_log` has no free-text content column, only small allowlisted fields | New |
| Unsafe default exposure to the network | `serve()`'s loopback-only refusal is unchanged in this version (D4) | Unchanged |

---

## 4. Data model

New module `formslang/authstore.py`, new SQLite file `auth.db`, following
`store.py`'s existing conventions: `CREATE TABLE IF NOT EXISTS`, the
`_ADDED_COLUMNS` + `Store._migrate()` pattern for later additions.

**Operational hardening applied to every connection (review item 11),**
not left implicit:

```python
conn.execute("PRAGMA foreign_keys = ON")
conn.execute("PRAGMA journal_mode = WAL")
conn.execute("PRAGMA busy_timeout = 5000")
```

Membership changes and last-Owner enforcement run inside explicit
`BEGIN IMMEDIATE` transactions, not autocommit — the same statement that
checks "is this the last Owner?" and the statement that removes/demotes
them must be atomic against a concurrent second removal request.

```sql
CREATE TABLE schema_migration (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL,
    description TEXT NOT NULL
);

CREATE TABLE organization (
    id TEXT PRIMARY KEY,
    slug TEXT UNIQUE NOT NULL,     -- stable natural key, not just display name
    name TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE user (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    username TEXT UNIQUE,
    -- D1: scrypt, full parameter set stored alongside the hash
    password_hash TEXT NOT NULL,       -- scrypt output, base64
    password_salt TEXT NOT NULL,       -- random, per user, base64
    password_algo TEXT NOT NULL DEFAULT 'scrypt',
    password_params_version INTEGER NOT NULL,  -- indexes into a small in-code
                                                -- table of {N, r, p} presets,
                                                -- so tightening the cost later
                                                -- is a new version, not a
                                                -- schema change
    must_rehash INTEGER NOT NULL DEFAULT 0,    -- set when params_version is
                                                -- behind current; cleared by
                                                -- the automatic post-login rehash
    disabled_at TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE membership (
    id TEXT PRIMARY KEY,
    org_id TEXT NOT NULL REFERENCES organization(id),
    user_id TEXT NOT NULL REFERENCES user(id),
    role TEXT NOT NULL CHECK (role IN ('OWNER','ADMIN','DEVELOPER','VIEWER')),
    created_at TEXT NOT NULL,
    UNIQUE (org_id, user_id)
);
CREATE INDEX idx_membership_user ON membership(user_id);
CREATE INDEX idx_membership_org ON membership(org_id);

CREATE TABLE project (
    id TEXT PRIMARY KEY,
    org_id TEXT NOT NULL REFERENCES organization(id),
    name TEXT NOT NULL,                -- display only, never used to build a path
    storage_mode TEXT NOT NULL CHECK (storage_mode IN ('EXTERNAL_LEGACY','ADOPTED')),
    external_path TEXT,                -- set only for EXTERNAL_LEGACY: normalized,
                                        -- resolved, case-folded on Windows
    session_db_path TEXT,              -- set only for ADOPTED: server-generated,
                                        -- under data_dir/orgs/<org_id>/projects/<id>/
    created_by TEXT NOT NULL REFERENCES user(id),
    created_at TEXT NOT NULL,
    deleted_at TEXT,
    CHECK (
        (storage_mode = 'EXTERNAL_LEGACY' AND external_path IS NOT NULL AND session_db_path IS NULL)
        OR
        (storage_mode = 'ADOPTED' AND session_db_path IS NOT NULL)
    )
);
CREATE UNIQUE INDEX idx_project_external_path ON project(external_path)
    WHERE external_path IS NOT NULL;
CREATE INDEX idx_project_org ON project(org_id);

-- Review item 3: explicit per-project grant, never UI-only or buried in
-- a JSON blob.
CREATE TABLE project_permission (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES project(id),
    user_id TEXT NOT NULL REFERENCES user(id),
    permission TEXT NOT NULL CHECK (permission IN ('EXPORT')),
    granted_by TEXT NOT NULL REFERENCES user(id),
    created_at TEXT NOT NULL,
    UNIQUE (project_id, user_id, permission)
);

CREATE TABLE session_token (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES user(id),
    active_org_id TEXT REFERENCES organization(id),  -- NULL only for scope='BOOTSTRAP_MFA'
    scope TEXT NOT NULL CHECK (scope IN ('NORMAL','MFA_PENDING','BOOTSTRAP_MFA')),
    token_hash TEXT UNIQUE NOT NULL,   -- raw token never stored
    csrf_secret TEXT NOT NULL,         -- HMAC key for this session's CSRF tokens
    user_agent_hash TEXT,              -- hashed/truncated, not stored verbatim
    ip_hash TEXT,
    created_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    revoked_at TEXT
);
CREATE INDEX idx_session_token_hash ON session_token(token_hash);
CREATE INDEX idx_session_user ON session_token(user_id);

-- D6 (2026-08-31): the raw secret lives ONLY in the OS credential store,
-- one entry per user (FormsLang:mfa-totp:<user_id>). This table never
-- holds the secret in any form -- see SS2.3.
CREATE TABLE mfa_secret (
    user_id TEXT PRIMARY KEY REFERENCES user(id),
    enrolled_at TEXT NOT NULL,         -- when the OS-store entry was written
    confirmed_at TEXT,                 -- NULL until two consecutive codes verify
    last_accepted_step INTEGER,        -- replay protection (SS7.3.5)
    created_at TEXT NOT NULL
);

CREATE TABLE mfa_recovery_code (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES user(id),
    code_hash TEXT NOT NULL,
    used_at TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE password_reset_token (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES user(id),
    issued_by TEXT NOT NULL REFERENCES user(id),   -- the Owner/Admin who initiated it
    token_hash TEXT UNIQUE NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,          -- short-lived, minutes not hours
    used_at TEXT
);

CREATE TABLE audit_log (
    id TEXT PRIMARY KEY,
    at TEXT NOT NULL,
    org_id TEXT,
    user_id TEXT,
    actor_email_snapshot TEXT,
    event_type TEXT NOT NULL,
    target_type TEXT,
    target_id TEXT,
    outcome TEXT NOT NULL,             -- OK | DENIED | ERROR
    ip_hash TEXT,
    detail_json TEXT                   -- small allowlisted keys only, never free text
);
CREATE INDEX idx_audit_org_at ON audit_log(org_id, at);
CREATE INDEX idx_audit_user_at ON audit_log(user_id, at);

-- Rate limiting (D3): persisted, not in-process only.
CREATE TABLE rate_limit_bucket (
    key TEXT PRIMARY KEY,              -- e.g. "login:account:<user_id>" or "login:ip:<ip_hash>"
    failures INTEGER NOT NULL DEFAULT 0,
    window_started_at TEXT NOT NULL,
    locked_until TEXT
);
```

`Project.name` (what the user typed) never builds a path — `external_path`
and `session_db_path` are the only two path columns, and exactly one of
them is populated depending on `storage_mode` (enforced by the `CHECK`
constraint above, not just by convention).

---

## 5. RBAC matrix

Four roles: **Owner**, **Admin**, **Developer**, **Viewer**. Every check
runs server-side, from a fresh `Membership` row, every request.

| Action | Owner | Admin | Developer | Viewer |
|---|---|---|---|---|
| Rename / delete the organization | ✅ | ❌ | ❌ | ❌ |
| Transfer ownership | ✅ | ❌ | ❌ | ❌ |
| Invite / remove a member | ✅ | ✅ | ❌ | ❌ |
| Change a member's role up to Admin | ✅ | ✅ | ❌ | ❌ |
| Grant the Owner role | ✅ | ❌ | ❌ | ❌ |
| Create / delete a project | ✅ | ✅ | ✅ | ❌ |
| Open a project, run analysis, convert units | ✅ | ✅ | ✅ | 👁 read-only |
| Approve / reject an AI proposal | ✅ | ✅ | ✅ | ❌ |
| Export ZIP / `compliance.md` | ✅ | ✅ | ✅ | only with a matching `project_permission(EXPORT)` row |
| Grant/revoke a Viewer's export permission on a project | ✅ | ✅ | ✅ (own projects) | ❌ |
| "Adopt" a legacy external project (§8/§9) | ✅ | ✅ | ❌ | ❌ |
| Configure the AI provider / enterprise policy | ✅ | ✅ | ❌ | ❌ |
| View the audit log | ✅ | ✅ | ❌ | ❌ |
| Reset **their own** password / enable-disable **their own** MFA | ✅ | ✅ | ✅ | ✅ |
| Initiate an assisted password reset for another member (D2 restrictions apply — §7.5) | can reset any member, **never another Owner** | can reset Developer/Viewer only — **never an Owner, never another Admin** | ❌ | ❌ |
| View or reset **another user's** MFA secret | ❌ nobody — the route does not exist | | | |

Unchanged rules from the first draft: MFA mandatory for Owner/Admin
before promotion takes effect; the last Owner of an organization can
never be removed or demoted, enforced inside the same transaction that
would do it (§4).

---

## 6. Local mode vs. team/server mode

| | Local single-user | Team/server |
|---|---|---|
| FormsLang's own bind | `127.0.0.1` only, always, unconditionally (D4) | **Same — no change** |
| External exposure | None | Reverse proxy (nginx/Caddy) on the same host terminates TLS, forwards to `127.0.0.1:port` with `X-FormsLang-Proxy-Token` |
| Auth | Off by default; `auth.db` created lazily only on explicit action (§2.4) | Mandatory, cannot be turned off |
| `auth.db` / first Owner | Created only by an explicit operator action | Same, no self-service signup |
| TLS | N/A | Mandatory, terminated by the proxy — FormsLang itself never holds a certificate in v1 |
| MFA | Optional | Mandatory for Owner/Admin |
| Host / Origin allowlist | Loopback names only | Loopback names **plus** the one configured public hostname, accepted only alongside a valid proxy token (§2.4) |
| CSRF | Content-Type gate + CSRF token + Origin check (§3) | Same, unchanged — the mechanism doesn't care which mode it's in |
| Rate limiting | SQLite-backed (D3), applies regardless of mode | Same |
| Default credentials | None, ever | Same |

---

## 7. Flows

### 7.1 Bootstrap — scoped, non-reusable (review item 4)

Resolves a real ordering problem the first draft glossed over: the first
Owner has to exist before they can enroll MFA, but Owner/Admin require
confirmed MFA. Fixed with a **restricted session scope**, not an
exception to the MFA rule:

1. Operator runs `formslang auth bootstrap-owner` **on the host, via
   CLI** — this is not an HTTP route and never will be. It creates
   `auth.db` lazily if absent (§2.4), creates the default "Local"
   organization if absent, and creates the `user` row with a password the
   operator sets interactively. No MFA yet.
2. **The guard against re-running this is a live query, not a flag
   file**: the command refuses outright if any `Membership(role='OWNER')`
   already exists in that organization. There is no bootstrap flag on
   disk to leave lying around or replay — the review's "arquivo/flag de
   bootstrap não pode permanecer reutilizável" is satisfied by there being
   no such artifact at all.
3. That Owner's **first HTTP login** is issued a session with
   `scope = 'BOOTSTRAP_MFA'` and `active_org_id = NULL`. Every route
   except MFA enrollment (`POST /api/auth/mfa/enroll`, `.../confirm`)
   checks `scope = 'NORMAL'` and refuses otherwise — no project route, no
   admin route, nothing else is reachable.
4. On confirming MFA (two consecutive valid codes, §7.3), the bootstrap
   session is **revoked** and a fresh `scope = 'NORMAL'` session with
   `active_org_id` set to "Local" is issued. Bootstrap cannot be reopened
   remotely: step 2's guard means it can never run again for this org, and
   there is no HTTP path that grants `BOOTSTRAP_MFA` scope to anyone but
   this one first-login transition.

### 7.2 Login

1. `POST /api/auth/login` with email + password.
2. Server verifies via scrypt (constant-time compare on the derived key,
   never a manual `==`). **If `password_params_version` is behind the
   current default, mark `must_rehash`** — the rehash itself happens
   after MFA succeeds (or immediately, for an account with no MFA), never
   before the password is confirmed correct.
3. No confirmed MFA: issue a `NORMAL` session directly, with
   `active_org_id` set to the user's sole membership, or to a
   just-selected one if they have several (§7.2a).
4. Confirmed MFA: issue a short-lived `MFA_PENDING` session (distinct from
   `BOOTSTRAP_MFA` — this one belongs to an already-fully-enrolled user
   mid-login, not a brand-new Owner) usable only for step 5.
5. `POST /api/auth/mfa` with a TOTP or recovery code. On success: rotate
   into a `NORMAL` session, and if `must_rehash` was set, transparently
   recompute the password hash under the current parameters and clear the
   flag — the user never notices; their password never has to be typed
   twice for this.

Rate limiting and progressive delay apply at steps 1 and 5 independently,
by account and by IP, persisted in `rate_limit_bucket` (D3) so a process
restart does not reset an attacker's clock.

### 7.2a Switching the active organization (review item 2)

A user who belongs to more than one organization picks which one is
active for a given session — never per-request. `POST
/api/auth/switch-org {org_id}`:

1. Server checks `Membership(user_id, org_id)` exists — a client cannot
   switch into an org they don't belong to, and this check is against the
   live table, not anything cached in the old token.
2. On success: the current session is **revoked** and a new one is
   issued with the new `active_org_id` — a rotation, not a mutation. This
   keeps every session token's scope fixed for its whole lifetime, which
   is what makes the CSRF-token-per-session design (§6) and the audit
   trail both simpler to reason about.

### 7.3 MFA enrollment

1. `POST /api/auth/mfa/enroll` (any authenticated, non-bootstrap or
   bootstrap session) generates a random TOTP secret and writes it
   **directly to the OS credential store** as `FormsLang:mfa-totp:<user_id>`
   (D6, §2.3) — a new enrollment overwrites any prior unconfirmed one for
   that user. `auth.db` records only `enrolled_at`, **unconfirmed** (no
   `confirmed_at` yet). The response returns an `otpauth://` URI plus the
   raw secret as a manual-entry string — once, in this response only,
   never persisted anywhere in `auth.db` and never logged.
2. **QR code generation (review item 9):** the Python standard library
   cannot render a QR code, and no secret is ever sent to an external
   service to render one. The `otpauth://` URI is rendered into a QR
   image **in the browser**, client-side, by a small vendored (not
   CDN-loaded) JS QR-encoder shipped with the UI bundle — see Decision D5
   in §10 for the one open question this still leaves (which encoder, and
   how it gets audited in). The manual-entry key is always shown as text
   too, so a broken QR renderer is never a dead end.
3. The UI explains, plainly, that the two confirmation codes must be
   entered from two different TOTP windows — a user should not be
   surprised into thinking the form is broken when the second code is
   momentarily rejected as "same window, try again in a few seconds."
4. `POST /api/auth/mfa/confirm` with **two consecutive valid codes**
   marks it confirmed, generates single-use recovery codes, returns them
   once, stores only their hashes.
5. Replay protection: the most recently accepted TOTP step is recorded
   per user; that exact code cannot be accepted twice.

### 7.4 MFA disable

Requires re-authentication in the same request (password **and** a valid
TOTP or recovery code). Logged as `MFA_DISABLED`.

### 7.5 Password recovery — D2, approved with restrictions

No outbound email exists in FormsLang today. **Approved for v1: assisted
reset**, with the exact restrictions from review:

1. An Owner or Admin initiates `POST /api/auth/reset-issue {user_id}` for
   a member of their own organization.
2. **Cross-role restrictions, enforced server-side:**
   - An Admin can reset a Developer or Viewer, **never an Owner, never
     another Admin.**
   - An Owner can reset any member of their organization **except
     another Owner** — an Owner never resets another Owner's password
     through this route.
   - (There is deliberately no route for an Owner to reset *their own*
     password this way — that is ordinary self-service password change,
     already covered.)
3. Server issues a short-lived (minutes), single-use token, stored only
   as a hash in `password_reset_token`, tied to `issued_by`.
4. The target user redeems it and sets a new password.
5. **On redemption:** every existing session for that user is revoked
   (§7.6) — a reset is also an implicit "log out everywhere." MFA is
   **never** removed or bypassed by a password reset; if the account has
   confirmed MFA, the normal MFA login step still applies afterward.
6. Every step (issue, redeem, expire-unused) is written to `audit_log`.
7. No temporary password is ever generated or known outside this
   single-use token flow — there is no "known default" at any point.

**Recovery of the last Owner** (the one case an Admin/Owner-initiated
reset cannot cover, since no Owner can reset another Owner and no Admin
can reset an Owner at all) is **exclusively a CLI operation on the host**
— `formslang auth reset-owner`, mirroring `bootstrap-owner`'s trust
model: whoever can run a command on the machine FormsLang runs on already
has more access than this route would grant anyway.

### 7.6 Sessions — rotation, limits, cleanup (review item 10)

- Rotated on: login, MFA success, org switch (§7.2a), any privilege
  change (a role edit revokes and reissues the affected user's active
  sessions), password reset redemption.
- The bootstrap session (§7.1) is a distinct `scope`, never reused as a
  normal session.
- A configurable **per-user session limit** (default modest, e.g. 5) —
  exceeding it revokes the oldest active session rather than silently
  allowing unbounded concurrent sessions.
- `user_agent_hash`, not the raw header, is stored — enough to show a
  user "which sessions are mine" without keeping a verbatim client
  fingerprint at rest.
- A periodic cleanup pass deletes `session_token` and
  `password_reset_token` rows past `expires_at` — not required for
  correctness (expired tokens are already rejected on use), but keeps
  `auth.db` from growing unbounded and keeps audit queries fast.
- Logout revokes the exact token used to call it, checked on every
  request, so revocation is immediate, not eventually consistent.

---

## 8. File isolation strategy

**Correction resolved (review item 7):** the first draft contradicted
itself — §8 said nothing is ever read outside `data_dir`, while §9
registered existing projects at their original, external paths. Resolved
by making the distinction a first-class, explicit project attribute
(`storage_mode`, §4) instead of an implicit assumption:

- **Local mode may register a legacy project at its existing, external
  path**, explicitly marked `storage_mode = 'EXTERNAL_LEGACY'`. This is
  what lets an existing installation keep working immediately after
  upgrading, without forcing every user to relocate files on day one.
- **Team/server mode never opens an `EXTERNAL_LEGACY` project**, full
  stop — `resolve_project_path()` and the project-listing query both
  filter to `storage_mode = 'ADOPTED'` whenever the server is running in
  team mode. A legacy path being reachable at all depends on trusting
  whatever permissions already existed on that external location, which
  is exactly the guarantee team mode cannot make.
- **"Adoption"** is the one explicit, audited path from `EXTERNAL_LEGACY`
  to `ADOPTED`, required before a project can be used in team mode:
  1. Copy (never move) the external `.session.db` into a temp path under
     `data_dir`.
  2. Validate the copy: re-open it as a `Store`, run a sanity query.
  3. Install atomically: `os.replace()` the validated copy into
     `orgs/<org_id>/projects/<id>/main.session.db`.
  4. Flip `project.storage_mode` to `ADOPTED` and set `session_db_path`,
     in the same transaction as step 3's filesystem replace succeeding.
  5. **The original external file is never touched, moved, or deleted**
     by this process — adoption is additive only.
  6. Logged to `audit_log` as a distinct event; a rollback is exactly
     "leave `storage_mode` as `EXTERNAL_LEGACY`, discard the temp copy" —
     nothing destructive ever happens on the failure path.
- **One chokepoint, `resolve_project_path(project_id) -> Path`,** as in
  the first draft — every `Store`-opening call, export write, and
  download goes through it, and it is also where the
  `EXTERNAL_LEGACY`/team-mode check lives.
- **Containment check on every `ADOPTED` resolution**: resolve symlinks
  first, then verify containment under `data_dir` via
  `os.path.commonpath`.
- **Logs never carry content** — structural, via the `audit_log` schema
  (§4), same reasoning `sensitive.py`'s `Finding` already applies to
  scanned client code.
- **Org-scoped export & deletion**, two-step delete (soft-delete flag,
  then a background reaper after a grace period) — unchanged from the
  first draft.

---

## 9. Migration

**Precondition, non-negotiable:** back up (copy, not move) every
`.session.db` the process will touch, and `config.json`, before writing
anything new.

**Terminology, disambiguated (review item 8 surfaced that the first draft
overloaded "migration"):** *schema migration* means `auth.db`'s own
`schema_migration`-tracked DDL changes over time — ordinary and unrelated
to project data. *Bootstrap* (§7.1) means creating the first Owner.
*Adoption* (§8) means moving a project from `EXTERNAL_LEGACY` to
`ADOPTED`. What this section covers is **registering** existing
`.session.db` files as `EXTERNAL_LEGACY` projects — a fourth, distinct
operation, deliberately the least invasive of the four.

Because FormsLang cannot enumerate "all existing projects" on its own
(§1), registration is **operator-directed**: the operator points it at
one or more directories to scan for `*.session.db` files, or lists them
explicitly. Anything not found stays exactly as reachable the old way
until registered later — stated as a limitation, not hidden (§10).

**Idempotency (review item 8), concretely — not just "the name 'Local' and
a path string":**

- Each candidate path is **normalized and resolved**
  (`Path.resolve()`), and on Windows additionally **case-folded**
  (`os.path.normcase`) before being compared or stored — so
  `C:\Forms\x.session.db` and `c:\forms\X.SESSION.DB` are recognized as
  the same file.
- The `idx_project_external_path` unique index (§4) is the actual
  enforcement — not a convention the migration code has to remember.
- Where two *different* candidate strings might still resolve to the same
  underlying file (short 8.3 names, a mapped drive vs. a UNC path), the
  registration step additionally calls `os.path.samefile()` against
  already-registered paths as a belt-and-suspenders check before
  inserting.
- The whole check-then-insert per candidate runs inside one
  `BEGIN IMMEDIATE` transaction, so two concurrent registration runs (or
  a retried run after a crash) cannot both insert the same file —
  verified by a concurrency test (§12), not just asserted here.
- `PRAGMA foreign_keys = ON` (§4) is set on every connection FormsLang
  opens to `auth.db`, including during registration, so a partially
  written row referencing a not-yet-committed organization is rejected by
  SQLite itself, not caught later by application code.

Steps, otherwise unchanged from the first draft:

1. `auth.db` created lazily (§2.4), not on every startup.
2. Default "Local" organization created if absent (`slug` unique — a
   second run does not create a second "Local").
3. First Owner created via `bootstrap-owner` (§7.1) — interactive
   credentials, never a known default.
4. For each discovered `.session.db`: register as `EXTERNAL_LEGACY`,
   owned by the org from step 2, per the idempotency rules above.
5. The file itself is never touched in this phase — "do not alter
   original files during the analysis phase" applies exactly as it
   already does to `.fmb`/`.fmt` sources elsewhere in this codebase.

Adoption into `ADOPTED` (§8) remains a deliberately separate, later,
opt-in step — required only when team mode is being enabled for that
project.

---

## 10. Risks, limitations, and open decisions

**D1 — approved: `hashlib.scrypt`.** Implementation requirements carried
into §4/§7.2 as binding, not optional: individual random salt per user;
`N`/`r`/`p` stored alongside the hash via `password_params_version`
(never hardcoded, so tightening cost later is a version bump, not a
migration); constant-time verification; a hard length cap on the
submitted password *before* it reaches scrypt (protects against a
trivially cheap memory/CPU-exhaustion request); a test asserting hashing
stays within a bounded time/memory budget for both a normal and a
maximum-length input; automatic rehash-after-login when
`password_params_version` is behind current.

**D2 — approved: assisted reset,** with the cross-role restrictions in
§7.5 as binding, not advisory.

**D3 — approved: SQLite-backed rate limiting** (`rate_limit_bucket`,
§4), explicitly not designed to scale horizontally — consistent with "não
transforme o FormsLang em SaaS nesta rodada."

**D4 — approved: no non-loopback bind in v1.** `serve()` is unchanged;
team mode is a reverse-proxy deployment plus the trusted-proxy-token
mechanism in §2.4/§6.

**D5 — approved 2026-08-31: vendored client-side JS QR-encoder,**
no CDN, no network call, version and SHA-256 pinned, Apache-2.0-compatible
license recorded in-tree, manual-entry key always shown as a text
fallback. Exact headers required alongside it (Phase 3 scope, §11):
`Cache-Control: no-store`, `Referrer-Policy: no-referrer`,
`frame-ancestors 'none'`, CSP without `unsafe-eval`; the `otpauth://` URI
travels only in the authenticated response body, never in a URL, log, or
persisted storage; secret and QR are wiped from the DOM after confirm or
cancel.

**D6 — approved 2026-08-31: no KEK, one OS-credential-store entry per
user for the raw TOTP secret** (`FormsLang:mfa-totp:<user_id>`),
superseding this document's original envelope-encryption design in
§2.3/§4. `secrets.py` is parameterized to accept a per-call
`(service, account)` instead of its current hardcoded pair; no new
crypto code and no new dependency are introduced. Rationale and the
accepted trade are in §2.3.

Other limitations, stated rather than hidden:

- **OS-level compromise of the service account is out of scope**,
  elevated into the threat model itself in this revision (§3) — the MFA
  KEK living in the OS credential store does not survive an attacker who
  already controls that OS account.
- **Restoring `auth.db` alone does not restore MFA.** A disaster-recovery
  restore of `auth.db` to a different machine, without also
  re-provisioning each affected user's `FormsLang:mfa-totp:<user_id>`
  entry in that machine's OS credential store, leaves those users' MFA
  undecryptable — they would need to re-enroll. This is the direct,
  honest cost of moving secrets out of the data directory (§2.3, D6); it
  is the correct trade, but it needs to be in the backup/recovery runbook
  explicitly, not discovered during an actual incident.
- **Registration cannot discover every project with certainty** (§9).
- **WebAuthn/passkeys are out of scope for v1**, per the original request.
- **Real increase in attack surface.** Every line of auth/session/RBAC
  code here is new surface that did not exist before. An external
  security review before enabling team/server mode in any real
  deployment remains a reasonable bar, not a formality — unchanged from
  the first draft.

---

## 11. Phased delivery (review item 12 — four phases, strictly gated)

**Team/server mode does not start until Phases 1, 2, and 3 are fully
green.** This is a hard gate, not a suggestion — Phase 4 adds zero new
authorization logic of its own; it only exposes what the first three
phases already proved correct.

| Phase | Scope | New tests (representative — full list in §12) |
|---|---|---|
| **1** | `authstore.py` schema + `schema_migration`; scrypt (D1, full requirement set); sessions incl. `active_org_id`; RBAC constants; scoped bootstrap (§7.1); local-auth-off behavior (§2.4) unaffected | schema, scrypt params/rehash, bootstrap scope, RBAC constants |
| **2** | HTTP wiring in `workbench.py`: the auth gate ahead of routing, cookies, CSRF token + Origin check, SQLite-backed rate limiting (D3), project registry, `resolve_project_path`, `EXTERNAL_LEGACY` registration (§9) | sessions, CSRF, rate-limit persistence, IDOR, path traversal, symlink escape |
| **3** | MFA enrollment/verification/recovery codes (§7.3–7.4), assisted password reset (§7.5, D2 restrictions), audit log | MFA suite, reset restrictions, audit coverage |
| **4** | Team mode: reverse-proxy deployment docs, `FORMSLANG_TRUSTED_PROXY_TOKEN` handling, extended Host/Origin allowlist, adoption flow (§8) | server-mode guard, adoption, legacy-blocked-in-team-mode |

Phase 0 is this document.

## 12. Test plan

Every "TESTES OBRIGATÓRIOS" item, plus the additions from this review,
mapped to a concrete file and a representative test name, in the
project's existing style (pytest, plain functions, full-sentence names,
module-level fixtures):

| Requirement | File | Representative test name |
|---|---|---|
| Tenant isolation | `tests/test_tenant_isolation.py` | `test_a_user_of_org_a_cannot_open_a_project_of_org_b` |
| IDOR | `tests/test_idor.py` | `test_incrementing_a_project_id_in_the_url_is_refused_for_a_non_member` |
| Path traversal / symlink escape | `tests/test_path_safety.py` | `test_a_symlink_inside_the_data_dir_cannot_point_outside_it` |
| Brute force / rate limiting, persisted | `tests/test_auth_bruteforce.py` | `test_rate_limit_state_survives_a_process_restart` |
| Expired / revoked session | `tests/test_sessions.py` | `test_a_revoked_session_is_refused_immediately` |
| Session rotation events | `tests/test_sessions.py` | `test_switching_the_active_organization_rotates_the_session` |
| CSRF | `tests/test_csrf.py` | `test_a_csrf_token_is_required_for_every_mutating_request` |
| DNS rebinding regression | `tests/test_csrf.py` | `test_a_foreign_origin_is_refused_even_with_a_valid_session_cookie` |
| Improper role change | `tests/test_rbac.py` | `test_an_admin_cannot_grant_owner` |
| Last Owner protected | `tests/test_rbac.py` | `test_the_last_owner_of_an_organization_cannot_be_removed` |
| Viewer export requires explicit grant | `tests/test_rbac.py` | `test_a_viewer_without_an_explicit_project_permission_cannot_export` |
| Password reset cross-role restrictions | `tests/test_password_reset.py` | `test_an_admin_cannot_reset_an_owners_password` / `test_an_admin_cannot_reset_another_admins_password` |
| Reset revokes sessions, preserves MFA | `tests/test_password_reset.py` | `test_a_password_reset_revokes_every_existing_session` |
| scrypt parameters & rehash | `tests/test_password_hashing.py` | `test_rehash_happens_automatically_when_params_are_outdated` |
| Hashing input-abuse guard | `tests/test_password_hashing.py` | `test_an_overlong_password_is_rejected_before_hashing` |
| MFA correct/incorrect/replay/recovery | `tests/test_mfa.py` | `test_the_same_totp_code_is_rejected_on_replay` |
| MFA key fails closed | `tests/test_mfa.py` | `test_mfa_operations_fail_closed_when_the_os_credential_store_is_unavailable` |
| Bootstrap session cannot escape its scope | `tests/test_bootstrap.py` | `test_a_bootstrap_session_cannot_reach_any_project_route` |
| Bootstrap cannot be repeated | `tests/test_bootstrap.py` | `test_bootstrap_owner_refuses_to_run_when_an_owner_already_exists` |
| Secrets absent from logs | `tests/test_secrets_hygiene.py` | `test_no_log_line_ever_contains_a_password_totp_secret_or_session_token` |
| External bind without auth blocked | `tests/test_server_mode_guard.py` | `test_binding_a_non_loopback_host_is_always_refused` |
| Trusted-proxy header handling | `tests/test_server_mode_guard.py` | `test_untrusted_forwarded_headers_are_ignored_without_the_proxy_token` |
| Legacy project blocked in team mode | `tests/test_adoption.py` | `test_a_legacy_external_project_cannot_be_opened_in_team_mode` |
| Adoption leaves the original untouched | `tests/test_adoption.py` | `test_adopting_a_project_leaves_the_original_file_untouched` |
| Registration/adoption idempotency | `tests/test_migration.py` | `test_two_paths_resolving_to_the_same_file_are_not_registered_twice` |
| Concurrent access | `tests/test_migration.py` | `test_two_concurrent_registration_runs_do_not_duplicate_a_project` |
| Backup & rollback | `tests/test_migration.py` | `test_a_failed_registration_leaves_the_previous_state_intact` |
| Foreign-key integrity | `tests/test_authstore_schema.py` | `test_a_membership_referencing_a_missing_organization_is_rejected` |

---

## 13. Decision log

| Decision | Status |
|---|---|
| D1 — `hashlib.scrypt`, versioned params, salted, constant-time, rehash-on-login | **Approved 2026-08-31** |
| D2 — assisted password reset, cross-role restricted, session-revoking, MFA-preserving | **Approved 2026-08-31** |
| D3 — SQLite-backed rate limiting, no horizontal scaling this version | **Approved 2026-08-31** |
| D4 — no non-loopback bind in v1; team mode via reverse proxy + trusted-proxy token | **Approved 2026-08-31** |
| D5 — QR rendering: vendored client-side JS encoder, pinned version+hash, licensed, no CDN | **Approved 2026-08-31** |
| D6 — MFA secret storage: one OS-credential-store entry per user, no KEK, no envelope encryption (supersedes original §2.3/§4 design) | **Approved 2026-08-31** |
| WebAuthn/passkeys deferred past v1 | Matches the original request |
| No public self-service signup in team/server mode; bootstrap via CLI only | Confirmed, unchanged |
