# WP-20 Explicit Freshness Read Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make local project status, summary and inventory inspect saved freshness without creating a job; provide an explicit CLI freshness check.

**Architecture:** Move the existing last-completed freshness lookup from the HTTP adapter into `ProjectService`, so HTTP and CLI share one interpretation. Keep the existing explicit `ProjectService.freshness()` job operation. This is a bounded WP-20 read-contract slice, not a whole-state checkpoint or a claim that `ProjectStore.open` is mutation-free.

The second bounded change adds a read-only storage open for the local CLI `status` query. Other project reads still require a separate no-write audit and migration contract.

**Tech Stack:** Python 3.10+, SQLite, argparse, pytest.

**Spec:** `docs/design/formslang-3.0/master-specification.md` §7.3 HIST-03; `docs/design/formslang-3.0/wp06-read-write-inventory.md`.

## Global Constraints

- Preserve 2.2 project/open/assessment semantics and existing HTTP freshness `GET`/`POST` behavior.
- Unknown freshness is `UNVERIFIED`, never `CURRENT` merely because a saved assessment exists.
- No new schema, no implicit review/decision write, no claimed release gate.

## Review Focus

- Analyzed project without a freshness job reports `UNVERIFIED`.
- Explicit check reports `CURRENT` only after executing the existing source check.
- Configuration or analysis revision changes invalidate a saved freshness result.
- Status, summary and inventory do not append freshness job rows.
- HTTP and CLI return the same last-known freshness state for one project.

### Task 1: Shared last-known freshness and explicit CLI action

**Files:** Modify `formslang/project_service.py`, `formslang/project_http.py`, `formslang/project_cli.py`, `tests/test_cli_project.py`; add a focused service test if adapter assertions do not cover revision invalidation.

**Interfaces:** `ProjectService.last_freshness() -> dict` returns the latest completed result only when its analysis and configuration binding still matches, otherwise `{status: 'UNVERIFIED', reasons: ['SOURCE_CHECK_REQUIRED'], analysis_revision: ...}`. Existing `freshness()` retains its explicit job behavior. `fl project freshness <project> [--json]` invokes that operation.

- [x] Write a minimal CLI test: after analysis, `status`, `summary` and `inventory` leave `project_job` row count unchanged and status is `UNVERIFIED`; explicit `freshness` creates exactly one job and subsequent `status` reports `CURRENT` without another write.
- [x] Run that test and record the expected failing assertion on current implicit job creation.
- [x] Implement `last_freshness()` using the existing HTTP SQL/binding rule, route HTTP `_freshness` through it, and replace the three CLI implicit checks. Add the explicit CLI command.
- [x] Run the focused CLI/HTTP/service tests, then full pytest, Ruff and `git diff --check`.
- [x] Record precise requirement scope and remaining `ProjectStore.open` mutation gap in evidence; commit the change on this branch.

### Task 2: No-write local status open

**Files:** Modify `formslang/project_store.py`, `formslang/project_service.py`, `formslang/project_intake.py`, `formslang/project_cli.py`, `formslang/project_jobs.py`, and `tests/test_cli_project.py`.

- [x] RED: a `status` query republishes a missing `project.json` mirror; `test_status_does_not_republish_missing_descriptor_mirror` failed at the mirror assertion.
- [x] GREEN: a local `status` query uses one read-only project connection and never registers the locator. A nested job detail read also uses read-only storage. The mirror test and adjacent freshness tests passed (3/3).
- [x] RED: with a missing run table, the read-only query returned generic exit 1; `test_status_requires_explicit_storage_upgrade_without_writing` expected a domain error and failed.
- [x] GREEN: read-only open reports an explicit migration-required domain error, with the existing `formslang project open <project>` remedy, without repairing the database or mirror. The test also verifies that explicit open migrates the missing run table and makes status usable again.
- [x] RED: a regression forced writable SQLite connections to fail and showed the read-only preflight still opened `mode=rw`.
- [x] GREEN: the read-only preflight now opens `mode=ro`; the writable open path retains `mode=rw`.
- [x] Focused CLI/store/service/jobs/intake/HTTP regression after the SQLite preflight correction: 122 passed, 1 skipped in 170.85 s. Ruff and diff check passed.
- [x] Full pre-reconciliation run: 1982 passed, 5 skipped, 4 xfailed, 1 failed in 1001.47 s. The sole failure was a Windows `PermissionError` in the unchanged concurrent locator lock path. Its single directed rerun passed; no mechanism or correction is claimed.
- [x] Rebased both own commits unchanged on the reconciled ADR-04/07 head; `range-diff` marks both equivalent. The composed CLI/store/service/jobs/intake/HTTP/WP-12 journey regression passed **131 tests, 1 skipped** in 197.17 s.
- [ ] Run the final composed full suite, Ruff/diff check and exact-head CI after the stacked ADR branches are integrated; require a green full run before merge.

This is a local CLI `status` boundary only. Other CLI/HTTP GET paths, authenticated intake and full WP-20 checkpoint/export/reopen work remain open. No HTTP 500 cause was established by this change.
