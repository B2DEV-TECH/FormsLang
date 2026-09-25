# FormsLang 3.0 — Session handoff

Read this first, then verify the checkout (`git log --oneline -3`,
`git status --short`). Do not assume this summary is current without checking
(§30.7).

## Checkout

- **`codex/formslang-3-m0`**, from `main` at `1d9cb47` (PRs #18 and #19 merged). Pushed; **Draft PR #21**, not merged.
  - `e104b33` — fix: keep the subprograms of a schema-qualified package body (WP-03).
  - `70f8596` — the M0 documents, which add this folder.
- **`codex/formslang-3-wp07`**, from the head of `codex/formslang-3-m0` (`70f8596`). Pushed; **Draft PR #22, stacked on #21** (base `codex/formslang-3-m0`). Not to be merged on its own; once #21 merges, rebase or retarget it onto `main` and check that its diff holds only WP-07.
  - `bfbaf70` — DDL-export package headers and per-source database coverage.
  - `d550595` — unmodelled CREATE kinds (`CREATE INDEX`, ...) are informational and no longer make a source `PARSED_WITH_WARNINGS`.
  - A docs-only commit recording the PR numbers and the WP-02 evidence.
  - CI does not run on it (`ci.yml` triggers only for `main`).
- **`codex/formslang-3-wp02`**, from `main` at `1d9cb47`, independent of #21 and #22. Pushed; **Draft PR #23** against `main`, not merged.
  - `b83ade2` — fix: log the type, codes and frames of an unexpected project request failure (WP-02, instrumentation only).
- **Working tree:** clean apart from local-only files that are never committed.
- **Nothing is merged, tagged or released.** Each needs the owner's explicit authorization, and so does any further push.

## Specification and milestone

- **Specification:** FL3-MASTER-2026-09-25 revision 1.0 ([master-specification.md](master-specification.md)).
- **Active milestone:** **M0** (PR groups P01 and P02).

## Requirements

| State | Requirements |
|---|---|
| Completed | None at the requirement level. The M0 documents (DOC-01, AGENT-01..04) exist and await review. |
| In progress | SRC-11: G-SCHEMA-BODY and quoted package names are done; cross-schema identity remains (ADR-06). SRC-14: G-SCHEMA-BODY done; CREATE statements not extracted are now reported per source but not yet extracted (G-DDL-EXTRACT, WP-08). INV-07: the database-source part (G-DDL-HEADER, source coverage) is tested locally; no reporting surface shows it yet. G-01 and G-04: see [evidence-register.md](evidence-register.md). |
| Blocked | WP-04 (G-SCHEMA-COLLIDE) is blocked on ADR-06. Every persistence change is blocked on ADR-01/02/03/12. |
| Not started | All other requirements; see [requirements-matrix.md](requirements-matrix.md). |

## ADRs

- None has been accepted. See [adr-index.md](adr-index.md).
- Open owner questions: whether WAL may be used (ADR-01), and whether authenticated mode is in scope for 3.0 (ADR-11).

## Commands and outcomes

These are recorded in [evidence-register.md](evidence-register.md) (G-01 and
G-04), including the failing-first run, the related suites, lint, the inventory
check, the full suite and the local HTTP repetition.

## Known defects

| Defect | Reproduction | State |
|---|---|---|
| G-DDL-HEADER | `CREATE OR REPLACE EDITIONABLE PACKAGE BODY "S"."P" AS` parsed to nothing, silently. | Fixed on `codex/formslang-3-wp07` (`blueprint-analysis/3`), Draft PR #22, not merged |
| G-SOURCE-REVISION | A supplied source that yields no object is not in `files`, so it does not change `source_revision`. Invariant: "Two repository states with materially different supplied source sets must not silently appear identical merely because one source produced zero extracted objects." | Open; deliberately unchanged in WP-07. Owned by ADR-02 (WP-10, WP-20) |
| Quoted identifier resolution | `"MyPackage"` and `MYPACKAGE` are distinct, as in Oracle; nothing normalises them. Quoted subprogram names are not supported. | By design for names; quoted subprograms are separate work |
| G-DDL-EXTRACT | `CREATE OR REPLACE PACKAGE P AUTHID DEFINER AS ...` gives no spec; a second package in a file, a table after `/`, `GLOBAL TEMPORARY TABLE`, `FORCE VIEW` and quoted table names give no object. Each is now listed as `not_extracted` in the source's coverage. Pinned by `test_gap_spec_header_with_a_clause_before_as_is_not_recognised` and the coverage tests. | Open; proposed WP-08 |
| G-SCHEMA-COLLIDE | Case C: two `ORDER_API` packages in different schemas merge into one, and the last sorted file wins. Pinned by `test_gap_case_c_same_named_packages_in_two_schemas_collapse_into_one`. | Open; needs ADR-06 (WP-04) |
| HTTP 500 on `main` `1d9cb47` | CI run 36135896101, `pytest (windows-latest, py3.11)`: a job-status `GET` returned 500. It was not reproduced locally (40/40) nor in the CI of Draft PR #23 (run 36176591379, the same job: 1871 passed, 0 failed). The cause is unknown. | Open, not reproduced. The instrumentation on #23 names the exception type, code and frames if it recurs. No fix without that evidence |
| Windows lock contention | CI repetition run 36084327274: 4/400 failures at `ce2cfdd`. | Open; issue #20 |

## Next bounded task

WP-07 is on Draft PR #22 (stacked on #21) and WP-02 on Draft PR #23; both
await the owner's review. The order the owner set on 2026-09-25: WP-02
(instrumentation only; done, the failure did not reproduce), a status report,
then WP-08 in bounded, test-first slices, once the owner approves. Coverage reporting
waits, and when it comes it consumes the same coverage model; it never reads
source files on its own. The candidates:

1. **WP-08 (G-DDL-EXTRACT), after the owner's approval.** Extract the cases
   G-DDL-EXTRACT lists, one test-first slice each, in this order: several
   packages in one source; clauses before `AS`/`IS`; `/` boundaries; quoted
   table, view and sequence names; `GLOBAL TEMPORARY TABLE`; `FORCE VIEW`.
   Each moves from `not_extracted` to `objects` in its coverage entry. No
   schema-aware identity.
2. **WP-02 follow-up, only on new evidence.** If a 500 recurs, read the
   `Project request failed [...]` message it logs (types, codes, frames) and
   write a failing test for that cause before any fix.
3. **Reporting of coverage.** Show `database.source_coverage` in a report or the
   UI. Not started; the domain contract is in `formslang/database.py`
   (`SourceCoverage`, `DatabaseProject.coverage_summary`).

## Environments not available

- Oracle Database, APEX and SQLcl were not used in M0.
- Python 3.10 and 3.11 were not run locally, and 3.12 only for `tests/test_project_http.py`; the full suite runs on them only in CI, and CI does not run on the stacked #22.
- No human usability sessions have been run.

## Claims that must not appear yet in the README, UI or release notes

- Any FormsLang 3.0 capability: repository checkpoints, the `.flm` decision language, the new Workbench, CLI parity, the report catalog.
- Schema-aware identity. DDL-export package headers are handled only on the unmerged `codex/formslang-3-wp07` branch.
- A fixed or stable Windows concurrency.
- Saving rows (DML) in generated APEX pages, rules beyond those already verified, and layout fidelity against the Forms runtime.
- That any 3.0 gate has passed.
