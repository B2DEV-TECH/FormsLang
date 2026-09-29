# WP-06 — read paths with write side effects

Code audit against `main` at `b09be2d` (29 September 2026). This is an
inventory feeding ADR-01, not a behavior change or an accepted transaction
design. The operational authority remains `project.session.db`; `project.json`
is its mirror. “Read” below describes the caller's apparent action, not the
actual database operations.

| Apparent read and call path | Current write side effect | Classification | ADR-01 / API-03 obligation |
|---|---|---|---|
| `ProjectStore.open` → `Store(path, reconcile_jobs=False)` | `Store.__init__` runs `CREATE TABLE IF NOT EXISTS`, checks/possibly adds columns in `_migrate`, and commits even on an existing database. | Implicit schema migration, including a no-change schema transaction. | Separate format/version inspection from explicit, recoverable upgrade. An ordinary open must not be advertised as read-only until proven so. |
| `ProjectStore.open` → `_migrate_runs` | Missing project run tables trigger `RUN_SCHEMA` inside `BEGIN IMMEDIATE`. | Implicit schema migration. | Preview and backup old projects before migration; specify failure/rollback and concurrent-open behavior. |
| `ProjectStore.open` → `sync_descriptor` when `project.json` is absent/stale | Stages and fsyncs a file; takes `BEGIN EXCLUSIVE`; may replace the mirror. | Recovery of a derived projection, not a new authoritative event. | Define explicit repair/publication status and when reads may trigger it. Keep SQLite authoritative and do not silently import edited mirror bytes. |
| `ProjectService.open` with queued/running jobs | Calls `ProjectJobManager.recover`, which locks the project and updates those jobs to `FAILED`. | Job recovery. | Recovery must be idempotent and observable; a GET must not unexpectedly claim a successful no-write read. Preserve the distinction between recovered job failure and source analysis failure. |
| `ProjectJobManager.get` (including HTTP job-status GET) | Calls `ProjectStore.open`; all conditional open/migration/mirror side effects above still apply. | Read with conditional migration/recovery of storage projections. | Reuse an explicit no-mutation read mode where possible; test Windows concurrent job-status reads separately from the still-unexplained HTTP 500. |
| CLI `project status`, `summary`, `inventory` → `ProjectService.freshness` | `ProjectJobManager.claim('FRESHNESS')` inserts a queued job and updates progress/status/outcome. | Explicit freshness operation invoked implicitly by read commands; persisted job history, not merely a cache. | Decide which command explicitly requests a freshness scan. Separate last-known freshness from an on-demand operation; describe revisions and side effects in CLI/API contracts. |
| `ProjectIntake.open_locator` | `_remember` writes `locators.json` after opening the descriptor. | Explicit registration of a selected project locator. | Keep this as a named adopt/register action, not an incidental read; define rollback if locator publication fails. |
| `ProjectIntake.select_source` | `_metadata(write=True)` registers an area in `locators.json`. | Explicit source-area registration. | Selection/authorization changes should be named as writes, and preview reads must not adopt a source implicitly. |

`Store.__init__(reconcile_jobs=True)` also runs `reconcile_job_runs` for legacy
module sessions. `ProjectStore.open` passes `False`, so that legacy recovery is
not part of its open path. The distinction matters when specifying a common
read contract.

This audit classifies *where* writes occur. It does not claim that moving them
is safe without ADR-01's crash, concurrency, Windows and compatibility tests.
It does not explain the intermittent HTTP 500: no instrumented exception cause
has been observed. Issue #20 remains the separate `ProjectBusy`/409 case.

Local check: Windows 11, Python 3.13.15,
`py -3.13 -m pytest -q tests/test_project_store.py tests/test_project_jobs.py tests/test_project_service.py -p no:cacheprovider`
returned **43 passed, 1 skipped**. This verifies the existing tested behavior;
it does not make ordinary opens side-effect free.

## Minimum WP-10 checks derived from this inventory

1. An ordinary project query must not create a job, publish a mirror, or
   upgrade a schema without an explicit operation contract.
2. Explicit upgrade and recovery must preserve the previous accepted state on
   failure and be idempotent after interruption.
3. A committed database event and a failed mirror/checkpoint publication must
   be distinguishable to callers; no split authority or false success.
4. Concurrent readers, migrator, freshness job and publisher need a Windows
   and Linux matrix, with the observed error category retained.
