# FormsLang 3.0 — Session handoff

Read this first, then verify the checkout (`git log --oneline -3`,
`git status --short`). Do not assume this summary is current without checking
(§30.7).

## Checkout

- **Branch:** `codex/formslang-3-m0`, created from `main` at `1d9cb47` (PRs #18 and #19 merged).
- **Commits on the branch (local, not pushed):**
  - `e104b33` — fix: keep the subprograms of a schema-qualified package body (WP-03).
  - The M0 documents commit, which adds this folder.
- **Working tree:** clean apart from local-only files that are never committed.
- **Nothing is pushed, merged, tagged or released.** Each of those needs the owner's explicit authorization.

## Specification and milestone

- **Specification:** FL3-MASTER-2026-09-25 revision 1.0 ([master-specification.md](master-specification.md)).
- **Active milestone:** **M0** (PR groups P01 and P02).

## Requirements

| State | Requirements |
|---|---|
| Completed | None at the requirement level. The M0 documents (DOC-01, AGENT-01..04) exist and await review. |
| In progress | SRC-11 and SRC-14: the G-SCHEMA-BODY part is done; quoted identifiers and cross-schema identity remain. INV-07: G-DDL-HEADER is open. G-01 and G-04: see [evidence-register.md](evidence-register.md). |
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
| G-DDL-HEADER | Run `parse_database_file` on a `.pkb` or `.pks` file whose header is `CREATE OR REPLACE EDITIONABLE PACKAGE BODY "S"."P" AS`. The result has no body and no spec, and nothing is reported. Pinned by `test_gap_exported_package_header_is_dropped_without_a_trace`. | Open; next slice (WP-07) |
| G-SCHEMA-COLLIDE | Case C: two `ORDER_API` packages in different schemas merge into one, and the last sorted file wins. Pinned by `test_gap_case_c_same_named_packages_in_two_schemas_collapse_into_one`. | Open; needs ADR-06 (WP-04) |
| HTTP 500 on `main` `1d9cb47` | CI run 36135896101, `pytest (windows-latest, py3.11)`: a job-status `GET` returned 500. It was not reproduced locally, and the cause is unknown because the boundary logs no traceback. | Open; WP-02 adds the logging first |
| Windows lock contention | CI repetition run 36084327274: 4/400 failures at `ce2cfdd`. | Open; issue #20 |

## Next bounded task

**WP-07, G-DDL-HEADER**, test-first:

1. Replace the pinned gap test with positive tests for `EDITIONABLE`/`NONEDITIONABLE`, `"S"."P"` and `S . P` headers on both specs and bodies. A quoted name keeps its exact case.
2. Add a negative test: a database file that yields no object is reported as a coverage limit, not dropped silently.
3. Change the header patterns in `formslang/database.py`. The identity key stays the bare name, because WP-04 owns identity.
4. Bump the engine version, then regenerate and check `docs/design/ecosystem-explorer-2.3/inventory-2.2.json`.
5. Update `gaps-and-capture.md`, the matrix and the evidence register.

## Environments not available

- Oracle Database, APEX and SQLcl were not used in M0.
- Python 3.10 and 3.11 were not run locally; they run only in CI.
- No human usability sessions have been run.

## Claims that must not appear yet in the README, UI or release notes

- Any FormsLang 3.0 capability: repository checkpoints, the `.flm` decision language, the new Workbench, CLI parity, the report catalog.
- Schema-aware identity, or support for DDL-export headers.
- A fixed or stable Windows concurrency.
- Saving rows (DML) in generated APEX pages, rules beyond those already verified, and layout fidelity against the Forms runtime.
- That any 3.0 gate has passed.
