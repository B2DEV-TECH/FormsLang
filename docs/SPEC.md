# FormsLang — Product Specification

**Version 1.0 — "Release"** · maintained by B2DEV TECH · status: implemented

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
   or plain `formslang workbench`   │  oracle.py     Forms2XML driver  │
   in any browser                   │  parser.py     Forms XML → units │
                                    │  plsql.py      static analysis   │
   `formslang export` / `apex …`    │  rules.py      built-in catalog  │
   from a terminal or CI, same      │  risk.py       risk scoring      │
   functions, no server             │  behavior.py   PRESERVED/CHANGED │
                                    │  analysis.py   one pass per unit │
                                    │  depgraph.py   what breaks if... │
                                    │  testspec.py   test cases        │
                                    │  sensitive.py  data scan, redact │
                                    │  policy.py     egress gate       │
                                    │  dashboard.py  project counts    │
                                    │  formdoc.py    module reference  │
                                    │  formdiff.py   structural diff   │
                                    │  formui.py     canvas preview    │
                                    │  convert.py    rules + prompts   │
                                    │  ai.py         provider layer    │
                                    │  config.py     settings file     │
                                    │  secrets.py    OS credential st. │
                                    │  store.py      SQLite session    │
                                    │  apexlayout.py Forms → grid      │
                                    │  apexlang.py   APEX 26.1 export  │
                                    │  apeximport.py SQLcl driver      │
                                    │  authstore.py  users, orgs, MFA  │
                                    │  ui/           one HTML document │
                                    │  cli.py        every command     │
                                    └──────────────────────────────────┘
```

### 3.1 The layered pipeline

The order matters more than any single layer: **deterministic facts stay
deterministic**, and the model is reached only where genuine ambiguity is
left. Nothing is sent to an LLM that a rule can answer.

```
parse Forms metadata          parser.py     structure, code bodies, items, LOVs
  → static analysis           plsql.py      built-ins, SQL verbs, globals, literals
  → catalog classification    rules.py      migration class per construct
  → dependency detection      depgraph.py   inbound/outbound, direct and transitive
  → risk scoring              risk.py       LOW / MEDIUM / HIGH / CRITICAL, with evidence
  → behaviour classification  behavior.py   PRESERVED / CHANGED / UNCERTAIN
  → AI proposal               ai.py         only the code, never the risk
  → human review              store.py      the decision, versioned, with a name on it
  → test specification        testspec.py   written from the Forms body, not the output
  → project view and export   dashboard.py, apexlang.py
```

Every deterministic result carries an engine version -- a fingerprint of the
catalog rows and scoring weights that produced it. Change one risk number and
every stored analysis is known to be stale, which is exactly the behaviour
this product needs: silently serving a score computed under older rules is
the kind of quiet drift it exists to prevent.

The scoring model is documented in full in [risk-model.md](risk-model.md):
every weight, every threshold, and the readiness formula that the workbench
prints on screen beside its own number.

The UI is a single self-contained HTML document -- assembled from the
`ui/` package (`shell`, `auth`, `projects`, `conversion`, `review`,
`validation`, `settings`, `formdoc`, `shared`) into one string -- served
from the loopback interface. No CDN, no external font, no framework —
enforced by test (`test_the_ui_carries_no_external_reference`).

Every operation the workbench offers is also a CLI command calling the
same function (`formslang doc` / `diff` / `preview` / `export` /
`apex validate` / `apex import`), so a pipeline reproduces what a reviewer
saw without a server, a browser or a second code path.

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
3. **Understand before deciding.** Every unit arrives already measured,
   offline, with no provider configured and nothing sent anywhere:
   - **Migration risk** — LOW / MEDIUM / HIGH / CRITICAL, scored from the
     constructs actually found, with the evidence behind every point.
     A different question from the conversion mode, and a different one
     again from AI confidence.
   - **Behaviour** — PRESERVED / CHANGED / UNCERTAIN. Absence of evidence
     is never PRESERVED.
   - **Dependencies** — what this unit uses and what uses it, direct and
     transitive, so *what else breaks if I change this?* has an answer
     before the change is made.
   - **Forms compatibility findings** — every built-in found, its migration
     class, and what APEX offers instead, straight from the catalog.
   - **Test cases** — written from the original Forms body, marked as
     inherited behaviour, modernization or something that needs
     confirmation; accepted, rejected or sent back per case. FormsLang
     writes them; it does not run them, and the screen says so.

   All of it lives in expandable sections beside the code comparison, which
   stays the focus of the screen.
4. **Review.** Approve (`a`), needs-work (`w`), reject (`r`), convert
   (`p`), navigate (`j`/`k`), search (`/`). Every decision is versioned in
   the session SQLite file with reviewer name and timestamp.
   A conversion run is never silent: while it runs the screen names the
   unit the model is reading, how long it has been reading it, which units
   are still queued and which pane is still waiting for an answer. A CLI
   provider takes 15 to 60 seconds per unit, and waiting without a signal
   is indistinguishable from a hang.
5. **The project view** (`d`, or the *Project* button). Totals, conversion
   modes, decisions, risk and behaviour distributions, what is in the way,
   the highest-risk units, the Forms features APEX has no equivalent for,
   and where the dependencies pile up. One readiness score, printed next to
   the exact arithmetic that produced it — weights, ratios and points, in a
   table on the same screen. No model contributes to any figure on that
   page, and a unit nobody analysed lowers the score rather than quietly
   leaving the denominator.
6. **Export.** APEXlang project + import ZIP for APEX 26.1. Approved code
   only. `approved.sql` and `session.json` document who approved what,
   against which model answer.
   - **Deterministic.** The same session exports the same bytes, ZIP
     included: name-ordered entries with a fixed timestamp, and the
     application's checksum salt drawn once per session and kept in the
     session file. Enforced by test
     (`test_the_same_session_exports_the_same_bytes`).
   - **Remembered.** The export's choices (application id, name, alias,
     workspace, schema, page) are written to the session, pre-filled in
     the dialog next time and read by `formslang export` when a flag is
     omitted -- the dialog shows the exact command line that reproduces
     what it is about to build.
7. **Validate and import.** `formslang apex validate|import <zip>` -- and
   the same buttons in the workbench -- drive the user's own SQLcl. The
   target comes from flags, `FORMSLANG_APEX_*` variables or Settings; the
   password from the environment, the OS credential store or a hidden
   prompt, and never from a command-line argument. Exit 1 when SQLcl
   prints `APEXlang Compile Errors` with exit 0, because that is a failed
   import. Full contract in [ci-cd.md](ci-cd.md).

## 5. Settings (in-app configuration)

The reason this spec exists: configuring AI must not require setting
environment variables in a terminal before launch.

### 5.1 The settings file

- **Location:** `%APPDATA%\FormsLang\config.json` on Windows,
  `$XDG_CONFIG_HOME/formslang/config.json` (default
  `~/.config/formslang/config.json`) elsewhere. `FORMSLANG_CONFIG_DIR`
  overrides the directory (also how tests isolate themselves).
- **Contents:** only these keys — the AI provider (`provider`, `model`,
  `base_url`, `deployment`, `api_version`), the APEX target (`sqlcl_path`,
  `apex_connect_string`, `apex_username`) and the multi-user switch
  (`auth_enabled`). `api_key` and the database password are **not** among
  them: credentials live in the OS store (§5.2), never in this file.
  Unknown keys are dropped on load and on save. Written atomically (temp file + rename),
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
| `/api/settings` | POST | Save any subset of the keys in §5.1; validates the provider id first; rebuilds the live provider; returns the redacted state |
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
| No remote access | Loopback bind + Host-header allowlist; `workbench --host` refuses non-loopback addresses | `test_a_foreign_host_header_is_refused` |
| A page in another tab cannot forge a request | Strict Content-Type on every POST; the server never answers a CORS preflight | `test_a_cross_site_content_type_is_refused` |
| No external resources in the UI | Single self-contained document | `test_the_ui_carries_no_external_reference` |
| Terminal launch cannot be weaponized | Fixed whitelist, browser sends an id, never a command | `test_terminal_refuses_anything_not_whitelisted` |
| CLI providers can't wander into source trees | Subprocess runs in an empty scratch directory, prompt on stdin | `tests/test_cli_providers.py` |
| Oracle ships nothing with FormsLang | No Oracle jars, binaries or artwork in the repo or the packages | NOTICE + README Legal, repo audit |
| A number on screen is never a model's opinion | Risk, behaviour, dependencies and readiness are computed by rules; the model may only enrich an explanation | `tests/test_risk.py`, `tests/test_behavior.py`, `tests/test_dashboard.py` |
| A prompt carries the unit, not the session | Only the code body and its catalog findings are sent; no credentials, no other units, no stored analysis | `tests/test_convert.py` |
| A finding never echoes the secret it matched | `formslang.sensitive.redact()` is the only place a matched value is formatted; findings carry a redacted excerpt everywhere they surface (analysis JSON, `/api/state`, `compliance.md`) | `tests/test_sensitive.py::test_a_finding_never_carries_the_secret_itself` |
| Enterprise mode blocks cloud egress outright, not just warns | `formslang.policy.check()` runs inside `ai.build_provider()` -- the one chokepoint every production call path shares -- and is also applied at the settings save and job-start preflight so the picker never offers a choice the call would refuse | `tests/test_policy.py` |
| Egress is classified by effective host, not by provider name | `claude_cli`/`codex_cli` are CLI-supplied credentials but CLOUD egress; `ollama` is HTTP-supplied but LOCAL when pointed at a loopback or private address. An unresolvable host fails closed to CLOUD | `tests/test_policy.py::test_a_remote_ollama_is_not_local` |

## 7. Out of scope for this version (roadmap)

- **Embedded terminal** (xterm.js + PTY inside the app) — v2. The native
  terminal launch covers CLI sign-in today with a fraction of the attack
  surface.
- **Cross-module portfolio dashboard.** The workbench now has a project
  view, but a session holds one form: "the forms with the highest dependency
  complexity" is answered inside a module, not across a portfolio. The CLI
  already batch-assesses portfolios; joining the two is v2.
- **Executing the generated test cases.** FormsLang writes specifications a
  person or a framework can run. It does not run them, and does not pretend
  to.
- Editable APEX page layout (regions/items designer). FormsLang converts
  logic; layout stays a Page Designer job.
- **Promotion across environments** on top of SQLcl `project`
  (`init/export/stage/release/deploy`): exporting the application *back*
  from APEX so the committed APEXlang tree round-trips, and one ZIP
  validated on DEV then imported on TEST and PROD with the workspace and
  schema resolved per deployment. The next phase; the ground for it --
  deterministic `formslang export`, `formslang apex validate|import`, the
  environment contract -- is 1.0 (see [ci-cd.md](ci-cd.md) §6).

## 8. Decision log

| Decision | Why |
|---|---|
| Settings live in the engine, not the Tauri shell | Works identically in the browser (`formslang serve`) and the desktop app; the shell stays a dumb window |
| Env vars beat the config file | CI and power users keep working unchanged; a saved setting can never invisibly override an explicit export |
| Risk and verdict are two columns, never one | `COMMIT_FORM` is cheap and dangerous. A single number would have to lie about one of them |
| Readiness counts every unit, including unanalysed ones | Excluding them would make the least finished session score the highest |
| Blockers stay out of the readiness score | A blocker is work to do; folding it into a percentage hides it behind arithmetic |
| Test cases are derived from the Forms body, not the generated APEX | A test written from generated code can only prove the generator agrees with itself |
| Key stored in the OS credential store, write-only over HTTP | The alternative (env-only) is what made the product "hard to use", and a plaintext file is not a defensible place for a credential. No fallback to plaintext: when no store exists, the save fails and the env var is the documented route. See 5.2 |
| Native terminal window instead of embedded terminal | CLI sign-in is a one-time act; a PTY bridge inside the app is v2 complexity with v0 payoff |
| No silent default to any cloud provider | "Nothing is sent anywhere until you choose a provider on purpose" is a README promise; a first-run banner asks, it never assumes |
| Manual authoring is a first-class conversion route | A migration tool that *requires* AI is a weaker product and a weaker compliance story |
| Egress classified by host, not by provider's `kind` axis | `kind` (`cli`/`http`) says how a credential is supplied; it conflates `claude_cli` (CLOUD) with `ollama` (can be LOCAL). A compliance gate needs the egress axis, not the credential axis |
| Egress policy sees the address, not what is behind it | An on-premise gateway at a private IP that forwards to a public model is invisible to a host check by design -- documented as a known limitation rather than solved with a network audit that does not exist yet |
| Compliance report is not blocked per unit | Enterprise mode already blocks cloud egress for the whole session; a third, per-unit intermediate behaviour would add surface without closing a gap the session-level block does not already close |
| Compliance report is not remediation | The product points out findings in client-owned source; it does not rewrite it |
| `compliance.md` sits beside `tests.md`, never inside the APEX export ZIP | The ZIP is deliberately APEX-artifacts-only (`tests/test_apexlang.py:83`); the compliance record is an audit artifact for the reviewer, not a deployable |
| The export is deterministic, down to the ZIP bytes | A pipeline that cannot rebuild what was reviewed cannot be trusted to deploy it; a ZIP that changes with the clock cannot be cached, compared or diffed. The one value that must be unpredictable (the checksum salt) is drawn once per session, not once per export |
| `formslang export` is the button, not a second exporter | Two code paths drift; one function called from two places cannot. The CLI reads the choices the dialog wrote to the session, and the dialog shows the command line the CLI would need |
| The database password never travels as an argument | `--password` would land in shell history, process listings and CI logs -- the same class of leak §5.2 refuses for the API key. Environment, credential store or a hidden prompt; a runner with neither fails at once rather than hanging |
| `APEXlang Compile Errors` with exit 0 is a failure | SQLcl reports a failed import in its output, not its exit code; a pipeline that trusts the code alone deploys nothing and reports success |
| `Date`/`Number` items export as `textField` | One unknown APEXlang keyword fails the whole import, and the item-type vocabulary lives in the target instance's plugins, not in the tool. Only keywords verified against a live 26.1 are emitted; a wider mapping follows a live `apex validate`, not a guess |
