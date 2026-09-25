# FormsLang 3.0 — Implementation plan

Status: **M0.** This is the only 3.0 roadmap in the repository. Its work
packages (WP) are ordered by dependency, and none of them is a
wholesale rewrite. Requirement IDs refer to [master-specification.md](master-specification.md)
and [requirements-matrix.md](requirements-matrix.md). ADRs refer to
[adr-index.md](adr-index.md). Results are recorded in
[evidence-register.md](evidence-register.md), not here.

Planning baseline: `main` at `1d9cb47` ([baseline-audit.md](baseline-audit.md)).
Every package keeps the supported 2.2 path working: parse, assess, review,
generate APEXlang, validate offline, and write revision-fenced reports.

## Working rules for every package

- Work happens on a feature branch. The baseline for M0 is `codex/formslang-3-m0`.
- A behaviour change starts with a failing test and ends with focused tests,
  the relevant suites, `python -m ruff check .` and the full `python -m pytest -q`.
- If a change alters extraction output, it also bumps the extractor or engine
  version and updates any committed inventory or fixture that records that
  output, in the same change.
- A pinned gap test (`test_gap_*`) becomes a positive test only in the change
  that fixes the gap. The gap document is updated in that same change.
- Races are not fixed with sleeps, longer timeouts alone, or skipped tests.
  A Windows stability claim needs the repeated-run protocol: N runs per Python
  version in CI, with the counts recorded.
- A package does not change the persistence format until the ADR that governs
  it (ADR-01/02/03/12) is accepted.
- Nothing is pushed, merged, tagged or released without the owner's explicit
  authorization for that specific operation.

## M0 — Establish the real baseline (PR group P01, P02)

| WP | Scope | Requirements | Depends on | Tests / exit evidence |
|---|---|---|---|---|
| **WP-01** | Place the spec; write the baseline audit, requirements matrix, ADR index, this plan, the evidence register and the session handoff | DOC-01, AGENT-01..04, G-01 (in progress) | — | Documents are commit-pinned, and the spec hash matches the delivered package |
| **WP-02** | Read-after-open lock errors at the HTTP boundary. The `1d9cb47` Windows job-status `GET` returned 500, and the cause is unknown because the boundary logs no traceback. First step: log the exception type on the sanitised 500 path so CI can name the cause, then reproduce it. Only if the cause is a `sqlite3.OperationalError('database is locked')` escaping outside `ProjectBusy`: map it to 409 `PROJECT_CONFLICT` with a failing test first. | API-02 | — | Repeated-run evidence on Windows. No claim without a traceback. Issue #20 stays the umbrella for starvation. |
| **WP-03** | **G-SCHEMA-BODY:** a schema-qualified `CREATE PACKAGE BODY S.P` keeps its subprograms | SRC-11 (partial), SRC-14 | — | **Done locally in `e104b33`.** The pinned `test_gap_case_c_schema_qualified_package_body_loses_its_subprograms` turns positive and fails before the fix. Case C bodies yield `SUBPROGRAM_BODY` entities. G-SCHEMA-COLLIDE stays pinned. Inventory and gap document are updated. |
| **WP-04** | **G-SCHEMA-COLLIDE:** schema-aware identity for specs, bodies, tables, views and sequences. Same-named objects in two schemas stay distinct. A qualified call resolves to the right one, and an unqualified call with several candidates is recorded as ambiguous. | SRC-11, SRC-12, AC-04, INV-07 | WP-03; ADR-06 (entity identity) accepted for the identity key | Case C: two `ORDER_API` packages are kept apart, `SALES_OWNER.ORDER_API.SUBMIT` and `BILLING_OWNER.ORDER_API.SUBMIT` resolve, bare `ORDER_API.SUBMIT` stays `AMBIGUOUS`. The engine version is bumped, and `LEGACY_RESOLVED` lifts only for this engine. |
| **WP-05** | Sanitisation probe of the two paths not yet probed: the local System Map JSON, and `convert.build_prompt` under the egress policy. The probe finds out what they disclose. Any fix is a separate, tested change. | SEC-05, SEC-06, AI-* | — | A probe test with synthetic secrets and host paths. Findings go to the register. |
| **WP-06** | Inventory of reads that write: `ProjectStore.open` publication and migration, `Store.__init__`, job recovery, and freshness job rows through the CLI. Each one is classified as a migration, recovery or cache step. | INV-05, API-03 | — | An inventory table feeding ADR-01. No behaviour change in M0. |
| **WP-07** | **G-DDL-HEADER** (found in WP-03): package spec and body headers written by DDL exports (`EDITIONABLE`/`NONEDITIONABLE`, `"SCHEMA"."NAME"`, spaces around the dot) are dropped without a trace. Parse those headers. An unquoted name is upper-cased and a quoted name keeps its exact case. A database file that yields no object records that as an explicit coverage limit instead of staying silent. Identity keys are unchanged (bare name), because WP-04 owns them. | INV-07, SRC-11 (quoted identifiers), SRC-14 | WP-03 | **Draft PR stacked on #21 (`codex/formslang-3-wp07`); not merged.** Positive and negative header tests in `tests/test_database_headers.py` (the pinned gap test turned positive). `DatabaseProject.coverage` gives every supplied source a status (`PARSED`, `PARSED_WITH_WARNINGS`, `NO_RECOGNIZED_OBJECTS`, `REJECTED_OR_UNREADABLE`) and lists the CREATE statements that yielded no object: a supported kind is a `WARNING`, an unmodelled kind (`CREATE INDEX`) is `INFO` and leaves the status alone; `None` means not computed (unknown). The Blueprint carries it as `database.source_coverage`, and the project pipeline records rejected and zero-object sources with logical paths. Tests in `tests/test_database_coverage.py`. Engine `blueprint-analysis/3`. No reporting UI. |
| WP-08 | *Proposed (found in WP-07), not scheduled.* **G-DDL-EXTRACT:** CREATE statements that coverage now reports as `not_extracted`: a clause before `AS` (`AUTHID`, `ACCESSIBLE BY`, ...), more than one package per file, a statement after `/`, `GLOBAL TEMPORARY TABLE`, `FORCE VIEW`, quoted table, view and sequence names. | SRC-14, INV-07 | WP-07 | Each case extracted, with its coverage entry moving from `not_extracted` to `objects`; the pinned `test_gap_spec_header_with_a_clause_before_as_is_not_recognised` turns positive. |

M0 exits when WP-01 is committed, the §3.3 concerns have been verified, and one
bounded foundation defect (WP-03) has been fixed with failing-then-passing
evidence. Order for the remaining M0/P02 packages: WP-07 (first slice tested locally), then
WP-02 (instrumentation first; a fix only once a traceback exists), then WP-05 and
WP-06. WP-08 is the owner's call. WP-04 waits for ADR-06.

## M1 — Prove repository semantics (P03)

| WP | Scope | Requirements | Depends on | Exit evidence |
|---|---|---|---|---|
| WP-10 | Write ADR-01, ADR-02 and ADR-03. Build a transactional object and checkpoint **spike** outside the product path, with failure injection (crash between object write and publication, interrupted fsync, concurrent publishers) and a portable-state schema draft. | REP-*, OBJ-*, TX-*, INV-01/05 | WP-06 | Crash and recovery matrix, no split authority, deterministic manifests, golden byte examples |
| WP-12 | Early **read-only** UX task prototype against verified fixtures: find a Form, see its relationships and evidence, find what blocks generation. It does not choose the persistence model. | UX-02, UX-03 | M0 | Recorded task observations (not a usability-study pass) |

## M2 — Stabilize facts and exploration queries (P05)

| WP | Scope | Requirements | Depends on | Exit evidence |
|---|---|---|---|---|
| WP-11 | Placement provenance (G-VIS-ATTR, G-VIS-TAB, G-VIS-ORIGIN, G-VIS-GHOST). Bounded focus, path and search services. `LEGACY_RESOLVED` emitted by product code. | SRC-08..10, GRAPH-01..06 | WP-04; WP-10 contracts where persistence changes | Positive and negative fixtures, a connected focal view at 500 Forms (addresses G-ESTATE-EMPTY), query limits, and 100/500-Form measurements |

## M3 — Whole-repository history and exchange (P04, P11 slice)

| WP | Scope | Requirements | Depends on | Exit evidence |
|---|---|---|---|---|
| WP-20 | Context pinning, checkpoints, `status/log/show/diff`, baselines, object verification, full and review exports, clean-workspace reopen | HIST-*, REP-*, OBJ-* | WP-10 (ADR-01..03 accepted), ADR-04, ADR-07 | Portability and closure tests, import conflicts, no forged approval, detection of external Git changes |
| WP-21 | First report dataset and the metric-definition slice. It reuses the revision-fenced report capture. | RPT-01..04, MET-01..03 | WP-20 | Reconciled counts between the report, the CLI and the UI |
| WP-22 | Legacy migration: 2.x project database and 1.x sessions into 3.0 state, preserving review history | MIG-01..05 | WP-20, ADR-12 | Migration of real 2.2 fixture projects, a backup-and-restore proof, and history preserved |

## M4 — Decision language and lifecycle (P06, P07)

| WP | Scope | Requirements | Depends on | Exit evidence |
|---|---|---|---|---|
| WP-30 | `.flm` parser, serializer and diagnostics (ADR-05) | DSL-* | M2–M3 | Round trips, fuzzing, deterministic snapshots |
| WP-31 | Decision lifecycle, applicability and eligibility. Preview, apply, approve, supersede. Migration of `blueprint_review` and `decision` history. | DEC-* | WP-30, WP-22 | Stale-binding and conflict tests, bulk atomicity, legacy history preserved |

## M5 — New Workbench and CLI parity (P08, P09)

| WP | Scope | Requirements | Depends on | Exit evidence |
|---|---|---|---|---|
| WP-40 | CLI envelope with `schema` and warnings, exit codes 3–10, idempotency keys, cursors (ADR-13) | CLI-*, API-* | M3–M4 | Old-command compatibility, JSON/stdout/stderr tests |
| WP-41 | New shell and design system (ADR-08): Explore, Decisions, Build, Validate, Reports, History, with a shared evidence inspector. The legacy routes move over journey by journey. | UX-*, ARCH-01/02 | WP-12 findings, WP-40 | Installed-browser journeys, keyboard, narrow-screen and error states, UI/CLI equality |

## M6 — Plan, build, and validate (P10)

| WP | Scope | Requirements | Depends on | Exit evidence |
|---|---|---|---|---|
| WP-45 | Neutral IR and adapter hardening (ADR-10): plan object, scope closure, generation manifest | BUILD-* | M3–M5 | Deterministic supported output; blocked cases fail honestly |
| WP-46 | Validation records and applicability (ADR-15) | VAL-* | WP-45 | Real tool evidence where it is available; an exact target and version matrix |
| WP-47 | AI assistance boundaries | AI-* | WP-05, WP-45 | Egress-policy tests; the core works without AI |

## M7 — Complete reporting (P12)

| WP | Scope | Requirements | Depends on | Exit evidence |
|---|---|---|---|---|
| WP-50 | The full catalog (RC-01..25), a PDF renderer (ADR-09), baseline comparison and disclosure | RPT-*, MET-* | WP-21, M4–M6 data | Reconciled counts, inspected PDF, safe offline exports |

## M8 — Product hardening and acceptance (P13)

| WP | Scope | Requirements | Depends on | Exit evidence |
|---|---|---|---|---|
| WP-60 | Security: the threat model and ADR-11 | SEC-* | M1–M7 | Adversarial tests, and privacy across all projections |
| WP-61 | Migration and installer: upgrade from 2.2, restore | MIG-06, G-10 | WP-22 | `installer-acceptance.yml` runs and restores |
| WP-62 | Performance and Windows stability (ADR-14, issue #20) | G-12, §25.4 | M1–M7 | p50/p95/memory measurements on ratified fixtures, and repeated-run Windows evidence |

## M9 — Release preparation (P14)

| WP | Scope | Requirements | Depends on | Exit evidence |
|---|---|---|---|---|
| WP-70 | README, docs, examples, capability table, changelog, same-commit assets | DOC-*, G-13 | M8 | Every required gate is evidenced, plus owner authorization for the version, tag and release |

## Minimum vertical slice (§26.3)

The slice crosses WP-04 → WP-10 → WP-20 → WP-30/31 → WP-40 → WP-45/46 →
WP-21. It is planned after WP-10 has accepted ADR-01..03, because it needs
checkpoints and `.flm`. It is not started in M0.

## Deliberate deferrals

- **README "3.0 direction" section (DOC-02):** deferred until a 3.0 capability
  exists on `main`, so that the README never presents intent as the current
  build.
- **CONTRIBUTING drift** (`serve` vs `workbench`, and 3.11 vs 3.10): a small
  documentation fix, to be scheduled with WP-70 or as a standalone change.
