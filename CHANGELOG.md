# Changelog

All notable changes to FormsLang are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added — migration analysis

- **Migration risk** (`formslang/risk.py`). Every unit is scored
  LOW / MEDIUM / HIGH / CRITICAL from the constructs actually found in its
  body, deterministically, with the evidence behind every point. A different
  question from the conversion mode (*what does it cost?*) and from AI
  confidence (*how sure is the model about this draft?*). The scoring
  formula, weights and thresholds are published in `docs/risk-model.md` and
  printed on screen next to the score.
- **Behaviour classification** (`formslang/behavior.py`).
  PRESERVED / CHANGED / UNCERTAIN, next to the confidence indicator. Absence
  of evidence is never PRESERVED, and an AI opinion is accepted only when it
  moves the answer away from PRESERVED — the model can make this more
  conservative, never less.
- **Migration classes in the catalog** (`formslang/rules.py`): every entry
  now carries DIRECT_EQUIVALENT, SERVER_SIDE_REPLACEMENT,
  CLIENT_SIDE_REPLACEMENT, ARCHITECTURAL_REDESIGN, MANUAL_REVIEW,
  UNSUPPORTED or NOT_REQUIRED. `NOT_REQUIRED` is kept apart from
  `UNSUPPORTED` on purpose: `SYNCHRONIZE` disappearing is not a gap in APEX.
- **One analysis pass per unit** (`formslang/analysis.py`), stamped with an
  engine version that fingerprints the catalog rows and scoring weights.
  Change one risk number and every stored analysis is flagged stale rather
  than being served silently under older rules.
- **Dependency graph** (`formslang/depgraph.py`): forms, blocks, items,
  triggers, program units, packages, procedures, tables and views, LOVs,
  record groups, relations, alerts, timers, reports, menus, PL/SQL
  libraries, globals, parameters and external calls, with inbound and
  outbound edges, transitive reach, and risky dependencies highlighted.
  A structured explorer beside the code — `GET /api/deps`.
- **Test case generation** (`formslang/testspec.py`): specifications written
  from the *original Forms body*, not from the generated APEX — normal path,
  boundaries, null handling, transaction behaviour, side effects, exception
  paths and regression scenarios. Each case is marked FORMS_BEHAVIOR,
  MODERNIZATION or NEEDS_CONFIRMATION, and reviewed per case as accepted,
  rejected or needs-modification. Case ids are content-hashed, so a decision
  survives regeneration when the wording has not changed. FormsLang writes
  these specifications and does not run them; the screen says so.
  `GET /api/tests`, `POST /api/test-decision`, and a `tests.md` in the
  export.
- **Project view** (`formslang/dashboard.py`, `GET /api/dashboard`, key `d`):
  totals, conversion modes, decisions, risk and behaviour distributions,
  blockers, the highest-risk units, the Forms features APEX has no
  equivalent for and where the dependencies pile up. One readiness score,
  printed next to the exact arithmetic that produced it — five weighted
  components, each measured over *every* unit in the session, so a unit
  nobody analysed lowers the score instead of quietly leaving the
  denominator. Blockers are deliberately excluded from the score.
- `docs/risk-model.md`: the whole scoring model, weight by weight.

### Changed

- **FormsLang is now Open Source under the Apache License 2.0.** The
  previous source-available license is replaced by `LICENSE` (Apache-2.0)
  and `NOTICE`. Created by Geraldo Viana Jr; maintained under the
  B2DEV-TECH organization.
- The AI conversion prompt now requires English for every human-readable
  string (notes, open questions, code comments), regardless of the language
  of the source module.

### Added

- **Exports panel**: an `Exports` button in the workbench lists every
  APEXlang ZIP built so far (newest first) with a *Show in folder* action
  that selects the file in the OS file manager; the same panel opens
  automatically after each successful export. New endpoints
  `GET /api/exports` and `POST /api/exports/open`.
- Community files: `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md` (Contributor
  Covenant 2.1), `SECURITY.md` (private vulnerability reporting),
  `AUTHORS.md`, this `CHANGELOG.md`.
- A pre-flight check refuses to start a conversion run when the selected
  HTTP provider has no API key, with a message that says exactly how to
  fix it (open Settings, paste a key, or pick a CLI provider).
- **Progress you can watch.** A conversion through a CLI provider takes 15
  to 60 seconds per unit, and the screen now accounts for every second of
  it: a moving bar under the top bar, a strip naming the unit being read
  with the provider and elapsed time, a spinner on the queued units in the
  list, and an overlay on the APEX pane of the unit whose answer is about
  to land. A unit merely waiting in line keeps its editor and gets an
  "in queue · N ahead" tag instead — a run over fifty units must not lock
  fifty panes. `GET /api/job` reports `current`, `current_id`, `queue` and
  `provider` for it, in the same shape whether or not a run is live. A run
  started before the window was opened is picked up on load. Opening a
  module, building the export ZIP and testing a provider show their own
  busy state.

### Fixed

- Failed conversions are now counted and reported honestly: the job tracks
  `failed` and `last_error`, and the workbench toast says
  "N of M conversion(s) failed — [reason]" instead of claiming success.
- A refused POST (403 wrong host, 415 wrong content type) now drains the
  request body before answering. Without it the connection was reset on
  the way back and the client saw a dropped connection instead of the
  status it had just been sent.

### Security

- **API keys are no longer written to `config.json`.** The credential now
  goes to the operating system's own store — Windows Credential Manager,
  the macOS Keychain, or the Secret Service (libsecret) on Linux — through
  the new `formslang.secrets` module. No third-party package is involved:
  `ctypes` on Windows, and on the others the tool the platform already
  ships, given the secret on stdin so it never appears in a process
  listing.
- **No silent fallback to plaintext.** Where the platform offers no
  credential store, saving a key is refused with *"Secure credential
  storage is not available. Use an environment variable instead."* and
  nothing is written at all, so a refused save cannot leave a
  half-applied settings file. The Settings screen disables the key field
  and shows the same message before the user types anything.
- A key left in `config.json` by an earlier version is still honoured, so
  an upgrade locks nobody out; it is moved into the credential store and
  stripped from the file the first time the workbench starts.
- The README's privacy claims now match what the code does: AI conversion
  requests go only to the provider the user selected, and a new privacy
  notice states that proposals may include the selected Oracle Forms
  source code and that hosted API and CLI providers process it under
  their own account, retention, and data-processing policies.

## [0.1.0] — 2026-08-27

### Added

- First public release: Forms2XML parsing, conversion workbench (review
  UI with approve / reject / needs-work verdicts), AI-assisted conversion
  via API providers (Anthropic, OpenAI, Azure OpenAI, Google, Ollama) and
  CLI providers (Claude Code, Codex), offline Echo mode, APEXlang 26.1
  export ZIP, Windows desktop app (Tauri) with MSI and NSIS installers.

[Unreleased]: https://github.com/B2DEV-TECH/FormsLang/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/B2DEV-TECH/FormsLang/releases/tag/v0.1.0
