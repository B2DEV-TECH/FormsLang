# FormsLang 3.0 — Session handoff

## Current addendum — independent PR #24 audit, 28 September 2026

- Draft PR #24 (`codex/formslang-3-wp08`) remains stacked on Draft PR #22, which remains stacked on Draft PR #21. The independent review compared `9d08e1e..e94e7e6`; its confirmed new regression was an arbitrary table projection after an earlier source-local collision. Failing-first tests now guard both the direct merge and the project pipeline. The audit also corrected package member decoys, quoted member names, overloaded member projection, literal CREATE decoys, and package SHARING options. See [evidence-register.md](evidence-register.md) for exact red/green commands and limits.
- Final local verification on Windows/Python 3.13.15: 1967 passed, 5 skipped, 3 strict xfailed in 846.26 s; directed suites: 237 passed, 1 skipped, 3 xfailed; Python 3.12 directed subset: 100 passed, 3 xfailed. Ruff, diff check, and the WP-08 inventory comparison passed. PR #24 has zero CI checks because its base is #22, not `main`; no Oracle runtime was used.
- Three out-of-scope gaps are pinned as strict `xfail`: coverage warnings do not yet make an assessment incomplete, direct Blueprint `source_revision` hashes SQL file paths rather than bytes, and documented `CREATE PACKAGE IF NOT EXISTS` is not recognized. ADR-06/WP-04 remains necessary for schema-aware identities and call resolution. The project manifest path continues to bind source bytes; no historical project rows were migrated or rewritten.
- PR #23 remains instrumentation only. The historical Windows/Python 3.11 HTTP 500 has no proven cause and is distinct from issue #20 (`ProjectBusy`/409). Do not derive a fix from SQLite locking or a race hypothesis without a new sanitised `Project request failed [...]` reproduction. No 3.0 release gate is passed; no merge, tag, release, UI rewrite, WP-09, or WP-10 was done in this audit.
- After #24's audit evidence is published, review the dependency stack #21 → #22 → #24 before integration. The next **new** WP in the implementation plan is WP-05 (sanitisation probe of the local System Map JSON and `convert.build_prompt`), followed by WP-06. Do not start it as part of this audit.

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
- **`codex/formslang-3-wp08`**, from #22. **Draft PR #24**, not merged; audit correction commit `22751e8` and accompanying evidence are on that branch only.
- **Nothing is merged, tagged or released.** No 3.0 gate is passed.

## Specification and milestone

- **Specification:** FL3-MASTER-2026-09-25 revision 1.0 ([master-specification.md](master-specification.md)).
- **Active milestone:** **M0** (PR groups P01 and P02).

## Requirements

| State | Requirements |
|---|---|
| Completed | None at the requirement level. The M0 documents (DOC-01, AGENT-01..04) exist and await review. |
| In progress | SRC-11: package occurrences preserve owner and quoted names, and ambiguous bare projections are withheld; schema-aware identity remains ADR-06/WP-04. SRC-14: WP-08A/B/C handles multi-package sources, named header clauses, slash boundaries and lexical decoys; other DDL forms remain open. INV-07: per-source coverage is tested locally but its warnings do not yet determine assessment completeness or appear in a 3.0 reporting surface. G-01 and G-04 remain in progress, not passed. |
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
| G-SOURCE-REVISION | Direct `blueprint.build` uses database file paths, so changing SQL bytes at the same path retains its local `source_revision`. The project assessment path binds the manifest digest and remains content-sensitive. | Open; pinned strict `xfail`, ADR-02/WP-10 and WP-20. No WP-08 change to persisted project revisions |
| Quoted identifier resolution | `"MyPackage"` and `MYPACKAGE` are distinct, as in Oracle. #24's audit preserves quoted subprogram names in the package member inventory; full schema-aware identity remains open. | Partial on Draft PR #24; ADR-06/WP-04 still open |
| G-DDL-EXTRACT | WP-08A/B/C now inventories multiple packages, recognizes the named package clauses, and splits SQLcl slash boundaries. `GLOBAL TEMPORARY TABLE`, `FORCE VIEW`, quoted table/view/sequence names and documented `CREATE PACKAGE IF NOT EXISTS` still yield explicit `not_extracted` coverage. | Partial on Draft PR #24; future DDL work remains |
| G-SCHEMA-COLLIDE | #24 retains same-name package occurrences from different owners and withholds ambiguous bare-name projections. It also withholds colliding table/view/sequence projections; no schema-aware entity identity or qualified call resolution exists yet. | Partial safety boundary on Draft PR #24; ADR-06/WP-04 remains open |
| HTTP 500 on `main` `1d9cb47` | CI run 36135896101, `pytest (windows-latest, py3.11)`: a job-status `GET` returned 500. It was not reproduced locally (40/40) nor in the CI of Draft PR #23 (run 36176591379, the same job: 1871 passed, 0 failed). The cause is unknown. | Open, not reproduced. The instrumentation on #23 names the exception type, code and frames if it recurs. No fix without that evidence |
| Windows lock contention | CI repetition run 36084327274: 4/400 failures at `ce2cfdd`. | Open; issue #20 |

## Next bounded task

1. Complete the independent review evidence on Draft PR #24. Then review the
   #21 → #22 → #24 dependency stack, diffs, conflicts, and available checks
   before any integration decision. Do not treat local tests as a CI matrix.
2. The next new planned work package is WP-05, the sanitisation probe. WP-06
   follows it in M0; WP-10 depends on WP-06. WP-04 still waits for ADR-06.
   None of these work packages starts in the PR #24 audit.
3. If a future execution produces `Project request failed [...]`, preserve the
   complete sanitised log and pause the current work to derive a causal
   regression for the HTTP 500. Until then, #23 is instrumentation only.

The original `inventory-2.2.json` remains the historical baseline; each later
engine has its own current characterization snapshot.

## Environments not available

- Oracle Database, APEX and SQLcl were not used in M0.
- Local Python installations available for this audit are 3.12 and 3.13. The stacked #24 has no CI checks because `ci.yml` targets pull requests to `main`.
- No human usability sessions have been run.

## Claims that must not appear yet in the README, UI or release notes

- Any FormsLang 3.0 capability: repository checkpoints, the `.flm` decision language, the new Workbench, CLI parity, the report catalog.
- Schema-aware identity. DDL-export package headers are handled only on the unmerged `codex/formslang-3-wp07` branch.
- A fixed or stable Windows concurrency.
- Saving rows (DML) in generated APEX pages, rules beyond those already verified, and layout fidelity against the Forms runtime.
- That any 3.0 gate has passed.
