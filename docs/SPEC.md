# FormsLang — Product Specification

**Version 0.2 — "Settings & Flow"** · maintained by B2DEV TECH · status: implemented

This document is the contract for what FormsLang does and, just as
deliberately, what it refuses to do. Every behavioral claim here is backed
by a test in `tests/`.

---

## 1. North star

A senior Oracle developer opens a `.fmb`, reviews every trigger and program
unit against an AI-drafted APEX proposal (or writes the replacement by
hand), and leaves with an APEX 26.1 import ZIP — without the tool ever being
hard to use, and without a single line of your source code leaving the machine
unless they explicitly chose a model.

Five pillars, in priority order:

1. **Import a Forms module and convert it — with AI or without.**
   `.fmb`/`.mmb` through the user's own Oracle Forms2XML install, or a
   Forms2XML `.xml` with no Oracle install at all. A reviewer can always
   write the APEX replacement by hand in the editor and approve it; an AI
   proposal is an accelerant, never a requirement.
2. **Connect to AI the way an engineer already pays for it.** The Claude
   Code CLI and the Codex CLI are first-class providers — no API key, the
   subscription the user already has. API-key providers (Anthropic, OpenAI,
   Azure OpenAI, Google, local Ollama) are equal citizens.
3. **Review and edit in place.** Side-by-side Forms source and APEX
   proposal, editable right pane, approve / needs-work / reject with a full
   audit trail per unit.
4. **Export an APEX 26.1 import ZIP.** Only approved code enters the
   application; generated processes ship disabled until confirmed in Page
   Designer.
5. **Beautiful, usable, simple.** One screen, one dark theme, keyboard
   driven. Features come after these five work end to end.

## 2. What FormsLang is (and is not)

| Is | Is not |
|---|---|
| A local review workbench + conversion engine (Python stdlib only) | A cloud service — there is no server, no account, no telemetry |
| A driver for the user's own Oracle Forms2XML and their own AI credentials | A redistributor of Oracle software (none is shipped, ever) |
| Open Source under the Apache License 2.0 (created by Geraldo Viana Jr) | Unattributed — the LICENSE and NOTICE files travel with every copy |
| An accelerant for a migration a human still owns | An automatic migrator whose output goes to production unread |

## 3. Architecture

```
┌────────────────────────────┐      ┌──────────────────────────────────┐
│  Desktop app (Tauri 2)     │      │  Engine (Python, stdlib only)    │
│  webview → 127.0.0.1:port  │─────▶│  ThreadingHTTPServer, loopback,  │
│  sidecar = frozen engine   │      │  Host-header check on every call │
└────────────────────────────┘      │                                  │
   or plain `formslang serve`       │  oracle.py   Forms2XML driver    │
   in any browser                   │  parser.py   Forms XML → units   │
                                    │  convert.py  rules + prompts     │
                                    │  ai.py       provider layer      │
                                    │  config.py   settings file       │
                                    │  store.py    SQLite session      │
                                    │  apexlang.py APEX 26.1 export    │
                                    │  ui.py       one HTML document   │
                                    └──────────────────────────────────┘
```

The UI is a single self-contained HTML document served from the loopback
interface. No CDN, no external font, no framework — enforced by test
(`test_the_ui_carries_no_external_reference`).

## 4. The conversion flow

1. **Import.** Native file picker or drag-and-drop for `.fmb`/`.mmb`/`.xml`;
   the module is copied into FormsLang's own output directory and the
   original tree is never written to. An `.fmb` requires an Oracle Forms
   installation licensed to the user (Forms2XML); an `.xml` requires
   nothing.
2. **Convert — three equally supported routes per unit:**
   - **AI proposal:** the configured provider drafts APEX code with a
     confidence score, notes and open questions.
   - **Rule verdicts without AI:** the built-in catalog still classifies
     every trigger (AUTO / ASSISTED / MANUAL / DROP) and annotates
     built-ins; the offline `echo` provider produces an explicit
     placeholder, never a fake conversion.
   - **Hand-written:** the right pane is an editor whether or not a
     proposal exists. Type the replacement, approve it, done.
3. **Review.** Approve (`a`), needs-work (`w`), reject (`r`), convert
   (`p`), navigate (`j`/`k`), search (`/`). Every decision is versioned in
   the session SQLite file with reviewer name and timestamp.
   A conversion run is never silent: while it runs the screen names the
   unit the model is reading, how long it has been reading it, which units
   are still queued and which pane is still waiting for an answer. A CLI
   provider takes 15 to 60 seconds per unit, and waiting without a signal
   is indistinguishable from a hang.
4. **Export.** APEXlang project + import ZIP for APEX 26.1. Approved code
   only. `approved.sql` and `session.json` document who approved what,
   against which model answer.

## 5. Settings (in-app configuration)

The reason this spec exists: configuring AI must not require setting
environment variables in a terminal before launch.

### 5.1 The settings file

- **Location:** `%APPDATA%\FormsLang\config.json` on Windows,
  `$XDG_CONFIG_HOME/formslang/config.json` (default
  `~/.config/formslang/config.json`) elsewhere. `FORMSLANG_CONFIG_DIR`
  overrides the directory (also how tests isolate themselves).
- **Contents:** only these keys — `provider`, `model`, `base_url`,
  `deployment`, `api_version`. `api_key` is **not** among them: the
  credential lives in the OS store (§5.2), never in this file. Unknown keys
  are dropped on load and on save. Written atomically (temp file + rename),
  owner-only permissions where the OS supports it — a best-effort measure
  that is not equivalent protection on every operating system, which is
  exactly why no secret is kept here.
- **Precedence:** environment variables **always win** over the file. The
  file is what the Settings screen writes; the environment stays the
  power-user and CI override. The UI labels any setting that an
  environment variable is currently overriding.

### 5.2 The API key rules (non-negotiable)

1. The key travels browser → server once, when the user saves or tests it.
   It **never** travels server → browser: `GET /api/settings` reports
   `has_key: true|false` and the key's source (`env` or `config`), never
   the value.
2. The key is never logged, never echoed in an error message, never part
   of `describe()`. Enforced by test.
3. Saving an empty key deletes the stored one ("forget key").
4. CLI providers need no key at all — credentials stay wherever the CLI
   keeps them; FormsLang neither reads nor stores them.
5. The key is **never written to `config.json`**. It is stored in the
   operating system's credential store — Windows Credential Manager, the
   macOS Keychain, the Secret Service (libsecret) on Linux — through
   `formslang.secrets`. Enforced by test.
6. There is **no fallback to plaintext**. When the platform offers no
   credential store, saving fails with *"Secure credential storage is not
   available. Use an environment variable instead."* and nothing at all is
   written, so a refused save never leaves a half-applied settings file.
   `FORMSLANG_AI_KEY` is the documented route in that case, and the
   Settings screen says so before the user types anything.
7. The secret never travels on a command line. The Unix backends are given
   it on stdin, so it cannot surface in a process listing; the Windows
   backend calls `advapi32` directly. No third-party package is involved on
   any platform — the analysis core keeps its zero-dependency rule.
8. A key left in `config.json` by an earlier version is still honoured, so
   an upgrade locks nobody out. It is moved into the credential store and
   stripped from the file the first time the workbench starts; if there is
   no store to move it to, the file is left untouched rather than losing
   the user's key, and the UI reports the key as living in the old file.

### 5.3 HTTP API

| Route | Verb | Behavior |
|---|---|---|
| `/api/settings` | GET | Redacted settings: provider, model, endpoint fields, `has_key`, key source (`env`, `keychain`, `file`, or none), credential-store availability, config path, active env overrides |
| `/api/settings` | POST | Save any subset of the six keys; validates the provider id first; rebuilds the live provider; returns the redacted state |
| `/api/settings/test` | POST | Round-trip test ("say ok") of the values in the form — nothing is saved; falls back to stored values for fields left blank |
| `/api/terminal` | POST | Open a **native** terminal window running a whitelisted CLI (`claude` or `codex`) so the user can sign in. The command comes from a fixed server-side table; no browser input ever reaches a command line |

### 5.4 UI

- **Gear button** in the header and the provider chip both open the
  Settings sheet.
- The sheet lists every provider with live availability (CLI installed?
  key present?), a model field with suggestions, a masked write-only API
  key field, endpoint fields where they apply (Ollama, Azure), a **Test**
  button with the round-trip result, and — for CLI providers — an **Open
  setup terminal** button.
- The key line names where the key actually is: the environment, the OS
  credential store, or the old config file awaiting migration. When the
  platform has no credential store the field is disabled and the sheet
  shows the environment-variable message instead of letting the user type
  a key it would have to refuse.
- **First-run banner:** when a module is open and the provider is still
  the offline stub, a single dismissible banner says conversions are
  placeholders and offers the Settings sheet. FormsLang never silently
  defaults to a cloud provider; choosing where code goes is always an
  explicit act.

## 6. Security & privacy model

| Promise | Mechanism | Test |
|---|---|---|
| Nothing leaves the machine by default | Default provider is the offline stub | `test_offline_provider_is_the_default` |
| The browser never sees a key | Redacted `/api/settings`, boolean-only catalog | `test_get_settings_never_leaks_the_key` |
| No remote access | Loopback bind + Host-header allowlist; `serve` refuses non-loopback hosts | `test_a_foreign_host_header_is_refused` |
| A page in another tab cannot forge a request | Strict Content-Type on every POST; the server never answers a CORS preflight | `test_a_cross_site_content_type_is_refused` |
| No external resources in the UI | Single self-contained document | `test_the_ui_carries_no_external_reference` |
| Terminal launch cannot be weaponized | Fixed whitelist, browser sends an id, never a command | `test_terminal_refuses_anything_not_whitelisted` |
| CLI providers can't wander into source trees | Subprocess runs in an empty scratch directory, prompt on stdin | `tests/test_cli_providers.py` |
| Oracle ships nothing with FormsLang | No Oracle jars, binaries or artwork in the repo or the packages | NOTICE + README Legal, repo audit |

## 7. Out of scope for this version (roadmap)

- **Embedded terminal** (xterm.js + PTY inside the app) — v2. The native
  terminal launch covers CLI sign-in today with a fraction of the attack
  surface.
- Multi-module portfolio dashboard in the workbench (the CLI already
  batch-assesses portfolios).
- Editable APEX page layout (regions/items designer). FormsLang converts
  logic; layout stays a Page Designer job.
- Windows keychain/DPAPI storage for the API key — candidate for v2;
  today the documented trade is a plain local config file with owner-only
  permissions, which is exactly how the majority of developer CLIs store
  tokens.

## 8. Decision log

| Decision | Why |
|---|---|
| Settings live in the engine, not the Tauri shell | Works identically in the browser (`formslang serve`) and the desktop app; the shell stays a dumb window |
| Env vars beat the config file | CI and power users keep working unchanged; a saved setting can never invisibly override an explicit export |
| Key stored in a local JSON file, write-only over HTTP | Simplest honest design; the alternative (env-only) is what made the product "hard to use". Documented in README and here |
| Native terminal window instead of embedded terminal | CLI sign-in is a one-time act; a PTY bridge inside the app is v2 complexity with v0 payoff |
| No silent default to any cloud provider | "Nothing is sent anywhere until you choose a provider on purpose" is a README promise; a first-run banner asks, it never assumes |
| Manual authoring is a first-class conversion route | A migration tool that *requires* AI is a weaker product and a weaker compliance story |
