# FormsLang 3.0 — Gate evidence register

This file records **actual** results only (§28.2). A gate is never marked passed
because a document says it should pass. A blocked Oracle or human gate is never
marked passed because the local unit tests are green. Planned work is in
[implementation-plan.md](implementation-plan.md), and requirement status is in
[requirements-matrix.md](requirements-matrix.md).

Specification: FL3-MASTER-2026-09-25 revision 1.0. Planning baseline: `main` at
`1d9cb47`. Active milestone: **M0**. Branch: `codex/formslang-3-m0`.

## Summary

| Gate | Status | Evidence so far |
|---|---|---|
| G-01 Baseline truth | **In progress** | Baseline audit written against `1d9cb47`, and the §3.3 concerns verified in code (see below) |
| G-02 Repository integrity | Not started | — (ADR-01..03 not written) |
| G-03 Portability and Git exchange | Not started | — |
| G-04 Facts and evidence | **In progress** | G-SCHEMA-BODY fixed with failing-then-passing tests. G-SCHEMA-COLLIDE and G-DDL-HEADER stay pinned as open defects. |
| G-05 Language and decisions | Not started | — |
| G-06 Workbench and CLI | Not started | — |
| G-07 Target delivery | Not started | 2.2 generator behaviour recorded in the baseline audit only |
| G-08 Validation | Not started | Offline SQLcl `apex validate` runs in CI for the 2.2 path; this is not a 3.0 gate result |
| G-09 Reporting | Not started | 2.2 revision-fenced reports recorded in the baseline audit only |
| G-10 Migration and packaging | Not started | — |
| G-11 Security | Not started | Two unprobed sanitisation paths are listed as WP-05 |
| G-12 Performance and usability | Not started | Windows lock contention is open (issue #20). Main CI failed on `1d9cb47` (see G-01). |
| G-13 Documentation | Not started | — |

No gate is **passed**. The full 3.0 release is not complete.

## G-01 — Baseline truth

- **Links:** DOC-01, AGENT-01..04; §30.2.
- **Scope:** the repository at `main` `1d9cb47` and branch `codex/formslang-3-m0`, local Windows 11 with Python 3.12 and 3.13, and GitHub Actions CI.
- **Implementation commits:** the M0 documents commit on `codex/formslang-3-m0` (see [session-handoff.md](session-handoff.md)).
- **Environment:** Windows 11 Pro 10.0.26200, Python 3.12 and 3.13. Oracle Database, APEX and SQLcl were **not used** in M0.
- **Commands and outcomes:**

  | Evidence | Command or source | Outcome |
  |---|---|---|
  | Specification identity | SHA-256 of `master-specification.md` against the delivered package | Identical (`60e1924a…401b29e`) |
  | CI on `main` `1d9cb47` | GitHub Actions run 36135896101 | **Failed**: `pytest (windows-latest, py3.11)` — 1 failed, 1867 passed. The job-status `GET` returned HTTP 500. All other jobs were green. |
  | Windows concurrency repetition | Run 36084327274 (100 runs × py3.10–3.13 of `tests/test_project_descriptor_concurrency.py`) | Previous `main` 19/400 failures; `ce2cfdd` 4/400 failures. Reduced, not eliminated (issue #20). |
  | Local reproduction of the 500 | `tests/test_project_http.py` repeated 20× each on py3.12 and py3.13 with a traceback-capture plugin | 40/40 runs passed (py3.12 20/20, py3.13 20/20). All 40 captured tracebacks come from `test_unknown_server_error_is_sanitized`, which raises on purpose. **The 500 was not reproduced locally.** |

- **Evidence locations:** [baseline-audit.md](baseline-audit.md) §2–§6, and the CI run pages.
- **Independent review:** none yet.
- **Known limitations:**
  - The cause of the `1d9cb47` 500 is **unknown**. The HTTP boundary sanitises the error without logging a traceback. WP-02 adds that logging before any fix.
  - Python 3.10 and 3.11 were not run locally.
- **Status:** in progress. **Owner/reviewer:** Geraldo Viana Jr, not yet reviewed.

## G-04 — Facts and evidence

- **Links:** SRC-11 (partial), SRC-14, INV-07; gaps G-SCHEMA-BODY, G-SCHEMA-COLLIDE and G-DDL-HEADER in [../ecosystem-explorer-2.3/gaps-and-capture.md](../ecosystem-explorer-2.3/gaps-and-capture.md).
- **Scope:** static database-source extraction (`formslang/database.py`) and blueprint analysis (`formslang/blueprint.py`), offline, on synthetic fixtures.
- **Implementation commits:** WP-03 commit `e104b33` on `codex/formslang-3-m0`. It is local and not pushed.
- **Fixtures:** the synthetic Case C corpus from the 2.3 ecosystem inventory and inline `tmp_path` sources. No customer source is used.
- **Commands and outcomes (Python 3.13, local):**

  | Step | Command | Outcome |
  |---|---|---|
  | Failing test first | `py -3.13 -m pytest -q tests/test_ecosystem_phase1.py -k "schema_qualified"` before the fix | 3 failed, 1 passed (the unqualified header already worked) |
  | After the fix | `py -3.13 -m pytest -q tests/test_ecosystem_phase1.py` | 29 passed |
  | Related suites | `py -3.13 -m pytest -q tests/test_database.py tests/test_blueprint.py tests/test_blueprint_backend.py tests/test_ecosystem_phase1.py tests/test_estate_hotspots.py tests/test_depgraph.py tests/test_modernization.py tests/test_project_analysis.py` | 206 passed, 1 skipped (symlinks unavailable to this Windows account) |
  | Inventory | `py -3.13 examples/verify/ecosystem_inventory.py --check docs/design/ecosystem-explorer-2.3/inventory-2.2.json` | Passes. The regenerated diff changes only the engine version in the four corpora, plus Case C: +1 `SUBPROGRAM_BODY`, +2 `IMPLEMENTS`, +1 `WRITES`, +1 symbolic table reference, and findings 22 → 24. |
  | Lint | `py -3.13 -m ruff check .` | All checks passed |
  | Full suite | `py -3.13 -m pytest -q -p no:cacheprovider` | 1868 passed, 5 skipped in 836 s at `e104b33`. The skip count matches the pre-M0 baseline; this run did not list the reasons. |

- **Behaviour now proven:** a `CREATE [OR REPLACE] PACKAGE BODY OWNER.NAME AS|IS` body keeps its subprograms, its `IMPLEMENTS` links, and its writes. The engine version is `blueprint-analysis/2`, so saved assessments from the previous engine are reported as stale.
- **Behaviour still not proven (open defects, pinned by `test_gap_*` tests):**
  - **G-SCHEMA-COLLIDE:** same-named objects in two schemas merge into one, and the last file wins. This needs ADR-06, then WP-04.
  - **G-DDL-HEADER (new, found in M0):** headers written by DDL exports (`EDITIONABLE`, `"S"."P"`, `S . P`) produce no spec and no body, and nothing reports the loss. This violates INV-07. It is the next slice (WP-07).
- **Independent review:** none yet.
- **Status:** in progress. **Owner/reviewer:** Geraldo Viana Jr, not yet reviewed.

## Gates not started

G-02, G-03, G-05, G-06, G-07, G-08, G-09, G-10, G-11, G-12 and G-13 have no 3.0
evidence yet. The 2.2 behaviour described in [baseline-audit.md](baseline-audit.md)
is a baseline, not a gate result.
