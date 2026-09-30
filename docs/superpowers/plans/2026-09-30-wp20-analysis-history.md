# WP-20 Saved Analysis History Implementation Plan

> **For agentic workers:** Use `superpowers:executing-plans` task by task. This is a bounded WP-20 read slice, not the repository `log` or a checkpoint.

**Goal:** Let a local user inspect which immutable project assessments were saved and which is currently selected, without scanning sources or writing storage.

**Architecture:** `ProjectService` queries the existing `project_assessment` rows through the read-only project store. The CLI opens a selected local locator with the existing read-only intake path and presents only revision hashes, saved timestamps, and current selection. Whole-project events, checkpoints, decisions and portable history remain WP-20 gaps.

**Tech Stack:** Python 3.10+, SQLite, argparse, pytest.

**Spec:** `docs/design/formslang-3.0/master-specification.md` §7, especially HIST-02/HIST-04. This slice deliberately does not claim either requirement complete.

## Global Constraints

- Do not mutate the project or locator registry on a history read.
- Do not claim that analysis rows represent the entire project event history.
- Keep source revisions and analysis revisions exact; do not derive display IDs.
- Return stable bounded rows and JSON suitable for CLI automation.

## Review Focus

- An unanalyzed project yields an empty list, not a fabricated revision.
- An older assessment remains visible after a new analysis becomes current.
- Identical timestamps still have deterministic ordering.
- A concurrent publication cannot mix the old current pointer with new rows.
- A dangling current pointer is an integrity error, unlike an unanalyzed project.
- A missing descriptor mirror does not reappear during history read.
- Requested pagination never changes which revision is current.

### Task 1: Persisted assessment query

**Files:** `formslang/project_service.py`, `tests/test_cli_project.py`.

**Interface:** `ProjectService.analysis_history(*, limit: int = 50, offset: int = 0) -> dict` returns `scope`, `current_analysis_revision`, `total`, and `rows` with exact persisted `analysis_revision`, `source_revision`, `analyzed_at`, `current`.

- [x] Add a real-project test that saves two assessments and verifies older and current rows.
- [x] Capture the missing-command RED and first GREEN.
- [x] Capture independent RED/GREEN for invalid bounds, concurrent publication and a dangling current pointer.
- [x] Read current pointer, count and rows in one SQLite snapshot, then close that snapshot.
- [x] Re-run the complete suite and commit only after green.

### Task 2: CLI read adapter

**Files:** `formslang/project_cli.py`, `tests/test_cli_project.py`.

**Interface:** `formslang project analysis-history <project> --json [--limit N] [--offset N]` uses `ProjectIntake.inspect_locator` and the same service method; local command is unavailable in authenticated mode as with other local project commands.

- [x] Add a CLI test that removes the descriptor mirror, calls the command, and verifies rows without mirror repair or a new job.
- [x] Run it red, add the minimal parser/dispatch, then run it green.
- [x] Run related tests, full pytest, Ruff, and `git diff --check`; record all failures honestly.

## Verification on the composed WP-20 branch

- Directed analysis-history tests: `9 passed in 20.71s`.
- Related CLI/service/freshness tests before the final edge cases: `46 passed, 1 skipped`.
- Final full suite: `2040 passed, 5 skipped, 4 xfailed in 968.98s`.
- `ruff check formslang/project_cli.py formslang/project_service.py tests/test_cli_project.py`: passed.
- `git diff --check`: passed.

The four expected xfails are pre-existing documented gaps. The complete
repository history and HIST-02/HIST-04 acceptance remain open.
