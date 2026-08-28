# Changelog

All notable changes to FormsLang are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

## [0.1.0] — 2026-08-27

### Added

- First public release: Forms2XML parsing, conversion workbench (review
  UI with approve / reject / needs-work verdicts), AI-assisted conversion
  via API providers (Anthropic, OpenAI, Azure OpenAI, Google, Ollama) and
  CLI providers (Claude Code, Codex), offline Echo mode, APEXlang 26.1
  export ZIP, Windows desktop app (Tauri) with MSI and NSIS installers.

[Unreleased]: https://github.com/B2DEV-TECH/FormsLang/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/B2DEV-TECH/FormsLang/releases/tag/v0.1.0
