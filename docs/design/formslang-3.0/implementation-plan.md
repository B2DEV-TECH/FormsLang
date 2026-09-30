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

## Owner-approved re-sequencing (2026-09-30)

After installing 3.0.0-beta.1, the owner reported that the Workbench is too
complex. The causes were too many menus, no clear next step, and the 1.x module
flow mixed with the 2.x project flow. The owner chose to bring a UX-only slice
of M5 forward:

1. **ADR-08** (frontend stack) moves from *Proposed* to *Accepted*.
2. **WP-39a** adds the read-only journey status service.
3. **WP-41 slice 1** adds the journey shell that hosts the existing views.

The design is [journey-shell-design.md](journey-shell-design.md).

After those, the order resumes:

1. the rest of WP-11 (M2);
2. the WP-20 reconciliation of PRs #38 → #41 (M3);
3. M4;
4. WP-39b, WP-40 and the later WP-41 slices.

What does not change:

- The specification, its requirements and its release gates. §26 still places
  M5 after M2–M4, and the M5 exit still requires M2–M4.
- The scope and dependencies of every other work package, except that WP-39 is
  split into WP-39a and WP-39b and WP-41 gains slice 1 (see M5).
- The working rules above.

One consequence is that PRs #38 and #41 stay parked for longer, and they need a
new rebase onto `main` before they are reconciled.

## M0 — Establish the real baseline (PR group P01, P02)

| WP | Scope | Requirements | Depends on | Tests / exit evidence |
|---|---|---|---|---|
| **WP-01** | Place the spec; write the baseline audit, requirements matrix, ADR index, this plan, the evidence register and the session handoff | DOC-01, AGENT-01..04, G-01 (in progress) | — | Documents are commit-pinned, and the spec hash matches the delivered package |
| **WP-02** | Read-after-open lock errors at the HTTP boundary. The `1d9cb47` Windows job-status `GET` returned 500, and the cause is unknown because the boundary logs no traceback. Instrumentation only: the sanitised 500 path logs the exception types, safe codes and frames of the cause chain, the method and a data-free route, never the message; the response is unchanged. If CI does not reproduce the failure, report that and stop; no guessed fix. A fix waits for a logged cause and its failing test. | API-02 | — | **Instrumentation on Draft PR #23 (`codex/formslang-3-wp02`); not merged.** Its CI (run 36176591379) did not reproduce the 500. No fix. Issue #20 stays the umbrella for starvation. |
| **WP-03** | **G-SCHEMA-BODY:** a schema-qualified `CREATE PACKAGE BODY S.P` keeps its subprograms | SRC-11 (partial), SRC-14 | — | **Merged through PR #21 (`452262e`).** The pinned `test_gap_case_c_schema_qualified_package_body_loses_its_subprograms` turns positive and fails before the fix. Case C bodies yield `SUBPROGRAM_BODY` entities. G-SCHEMA-COLLIDE stays pinned. Inventory and gap document are updated. |
| **WP-04** | **G-SCHEMA-COLLIDE:** schema-aware identity for specs, bodies, tables, views and sequences. Same-named objects in two schemas stay distinct. A qualified call resolves to the right one, and an unqualified call with several candidates is recorded as ambiguous. | SRC-11, SRC-12, AC-04, INV-07 | WP-03; ADR-06 (entity identity) accepted for the identity key | Case C: two `ORDER_API` packages are kept apart, `SALES_OWNER.ORDER_API.SUBMIT` and `BILLING_OWNER.ORDER_API.SUBMIT` resolve, bare `ORDER_API.SUBMIT` stays `AMBIGUOUS`. The engine version is bumped, and `LEGACY_RESOLVED` lifts only for this engine. |
| **WP-05** | Sanitisation probe of the two paths not yet probed: the local System Map JSON, and `convert.build_prompt` under the egress policy. The probe finds out what they disclose. Any fix is a separate, tested change. | SEC-05, SEC-06, AI-* | — | **Merged through PR #29 (`ac33545`).** Synthetic probe found prompt disclosure and pins the desired no-disclosure behavior as a strict xfail; no production or provider behavior changed. The egress policy belongs to WP-47. |
| **WP-06** | Inventory of reads that write: `ProjectStore.open` publication and migration, `Store.__init__`, job recovery, and freshness job rows through the CLI. Each one is classified as a migration, recovery or cache step. | INV-05, API-03 | — | **Merged through PR #30 (`567085f`).** Inventory table feeds ADR-01. No production behavior or persistence format changed. |
| **WP-07** | **G-DDL-HEADER** (found in WP-03): package spec and body headers written by DDL exports (`EDITIONABLE`/`NONEDITIONABLE`, `"SCHEMA"."NAME"`, spaces around the dot) are dropped without a trace. Parse those headers. An unquoted name is upper-cased and a quoted name keeps its exact case. A database file that yields no object records that as an explicit coverage limit instead of staying silent. Identity keys are unchanged (bare name), because WP-04 owns them. | INV-07, SRC-11 (quoted identifiers), SRC-14 | WP-03 | **Merged through PR #22 (`8a7b4e`).** Positive and negative header tests in `tests/test_database_headers.py` (the pinned gap test turned positive). `DatabaseProject.coverage` gives every supplied source a status (`PARSED`, `PARSED_WITH_WARNINGS`, `NO_RECOGNIZED_OBJECTS`, `REJECTED_OR_UNREADABLE`) and lists the CREATE statements that yielded no object: a supported kind is a `WARNING`, an unmodelled kind (`CREATE INDEX`) is `INFO` and leaves the status alone; `None` means not computed (unknown). The Blueprint carries it as `database.source_coverage`, and the project pipeline records rejected and zero-object sources with logical paths. Tests in `tests/test_database_coverage.py`. Engine `blueprint-analysis/3`. No reporting UI. |
| WP-08A/B/C | **Merged through PR #24 (`b09be2d`).** Ordered package declaration inventory, collision boundary and source lines; `AUTHID`, `ACCESSIBLE BY`, `DEFAULT COLLATION`, `SHARING` headers; isolated SQLcl slash and adjacent CREATE boundaries. Colliding supported CREATEs are visible in source coverage. `GLOBAL TEMPORARY TABLE`, `FORCE VIEW`, and quoted table/view/sequence names remain separate G-DDL-EXTRACT gaps. | SRC-14, INV-07 | WP-07 | Focused tests in `test_database_wp08.py` and current characterization `inventory-wp08.json`; historical `inventory-2.2.json` retained. Oracle validation remains unverified. |

The #21 → #22 → #24 foundation stack is merged. WP-02 instrumentation remains
separate on Draft PR #23; a fix waits for a logged cause. WP-08's independent
audit corrected a collision merge regression, lexical decoys, quoted member
loss and invalid package `SHARING` options; see the evidence register. Three
strict xfails remain visible, including the supported-CREATE/assessment gap.
ADR-06 is accepted for architecture after independent probe review. The separate
WP-04 product branch implements the package-only Case C slice with typed
candidates, explicit byte capture and project analysis binding; tables, views,
sequences and the remaining product exit/G-04 stay open. See the
[product plan](../../superpowers/plans/2026-09-29-wp04-product.md) for red/green
evidence and limits. This is not a completed WP-04 or gate result.
The post-merge `main` CI had an intermittent
Windows/Python 3.13 HTTP 500 in a job-status read; its cause is unknown and it
does not prove an issue #20 `ProjectBusy`/409 mechanism.

## M1 — Prove repository semantics (P03)

| WP | Scope | Requirements | Depends on | Exit evidence |
|---|---|---|---|---|
| WP-10 | Write ADR-01, ADR-02 and ADR-03. Build a transactional object and checkpoint **spike** outside the product path, with failure injection (crash between object write and publication, interrupted fsync, concurrent publishers) and a portable-state schema draft. | REP-*, OBJ-*, TX-*, INV-01/05 | WP-06 | Crash and recovery matrix, no split authority, deterministic manifests, golden byte examples |
| WP-12 | Early **read-only** UX task prototype against verified fixtures: find a Form, see its relationships and evidence, find what blocks generation. It does not choose the persistence model. | UX-02, UX-03 | M0 | Recorded task observations (not a usability-study pass) |

ADR-01/02/03 acceptance authorizes an implementation contract, not the spike's
example schema as a shipped format and not a repository-integrity or portability
gate. Product migration, closure, recovery and reopen tests belong to WP-20's
exit evidence. This separates the pre-WP-20 ADR decision from the product proof
that only WP-20 can produce.

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

ADR-04 and ADR-07 must be accepted as architecture contracts before WP-20
implements exchange import or Git reconciliation. Their Draft texts select
trust and synchronization boundaries; they do not supply WP-20's product
tests or pass G-02/G-03/G-05. WP-20 must prove the import, two-worktree,
conflict, recovery and no-forged-approval cases listed in those ADRs.

## M4 — Decision language and lifecycle (P06, P07)

| WP | Scope | Requirements | Depends on | Exit evidence |
|---|---|---|---|---|
| WP-30 | `.flm` parser, serializer and diagnostics (ADR-05) | DSL-* | M2–M3 | Round trips, fuzzing, deterministic snapshots |
| WP-31 | Decision lifecycle, applicability and eligibility. Preview, apply, approve, supersede. Migration of `blueprint_review` and `decision` history. | DEC-* | WP-30, WP-22 | Stale-binding and conflict tests, bulk atomicity, legacy history preserved |

## M5 — New Workbench and CLI parity (P08, P09)

| WP | Scope | Requirements | Depends on | Exit evidence |
|---|---|---|---|---|
| WP-39a | Read-only journey status service (`formslang/project_journey_status.py`): the per-Form and project state of the Understand/Decide/Build/Validate steps, composed from existing freshness, review, generation-blocker, artifact and validation facts, served by `GET /api/v2/projects/{pid}/journey` and `formslang project journey`. No new table, persistence authority or domain rule. Design: [journey-shell-design.md](journey-shell-design.md) §2. | SURF-01 (partial), ARCH-01..04 | Existing services only; one shared definition of `RESOLVED_REVIEWS` | State-rule and exhaustiveness tests (24 generation blocker codes, freshness, review and validation values); Decide count equals the `UNRESOLVED_REVIEW` scope; CLI/HTTP equality; 500-Form gate (cold journey median ≤ 1.5× the cold Overview median of the same run) recorded in the evidence register |
| WP-39b | The remainder of the original WP-39: a typed application-service slice for pinned context, structured search, evidence and blocker inspection, and decision preview. Keep existing `ProjectService` behavior and public adapters compatible; no new persistence authority. | SURF-01, SURF-04, ARCH-01..04 | WP-39a, WP-11, WP-20, WP-31; ADR-13 for public error/schema mapping | Same fixture/context returns matching identities, evidence, omissions, budgets and domain errors through service, CLI and HTTP; stale/denied requests stay controlled |
| WP-40 | CLI envelope with `schema` and warnings, exit codes 3–10, idempotency keys, cursors (ADR-13); complete the first supported headless journey using WP-39a/39b, keeping old commands or documented aliases. | CLI-*, API-*, SURF-02 | WP-39a, WP-39b; M3–M4 | Old-command compatibility, JSON/stdout/stderr tests, offline no-browser journey and CLI/HTTP equality |
| WP-41 slice 1 | Journey shell (ADR-08): a top bar and a rail labelled Explore · Decisions · Build · Validate (the Understand/Decide/Build/Validate steps) that is a state map in project and Form scope, plus Reports, History and Advanced. The existing views are hosted per step. The former navigation leaves the primary path, and every task it supported stays reachable. Design: [journey-shell-design.md](journey-shell-design.md) §1 and §3. | UX-01/02/03 (partial), ARCH-01/02 | ADR-08 Accepted, WP-39a, WP-12 findings | Edge acceptance of the three shell states in both scopes; navigation inventory test; keyboard operation of the shell controls; no regression at 390/720/1366 px; installed journeys updated with check accounting; Installer acceptance before merge |
| WP-41 later slices | New shell and design system completed: Explore, Decisions, Build, Validate, Reports and History workspaces redesigned, with a shared evidence inspector. The legacy routes move over journey by journey. | UX-*, ARCH-01/02, SURF-01 | WP-41 slice 1, WP-12 findings, WP-39b, WP-40 | Installed-browser journeys, keyboard, narrow-screen and error states, UI/CLI equality |
| WP-42 | Opt-in local MCP foundation: pinned protocol/local stdio transport, allowlisted read-only discovery, structured search, object/evidence and status tools over WP-39a/39b. No writes, remote server or agent runtime. | SURF-03, SURF-04 | WP-39b, WP-20; ADR-13 compatibility contract; WP-06 read/write inventory | Protocol and adapter tests prove context/permission isolation, no writes on read paths, bounded responses, stale-context denial, and service/CLI/MCP equality. Record actual installed integration evidence separately. |

WP-42 can follow WP-40/41 independently after WP-39b. It does not unblock
WP-48; the optional execution loop calls the application service directly.
The WP-48 contract was merged through PR #33; WP-39, WP-42 and the shared
surface contracts in this PR are specification only, not implemented commands
or an installed MCP server.

### Later optional surface extension

| WP | Scope | Requirements | Depends on | Exit evidence |
|---|---|---|---|---|
| WP-43 (optional, later) | Evaluate a policy-scoped semantic candidate index after structured search; implement only if measured retrieval value justifies it. | SURF-05 | WP-39b, WP-11, WP-05 disclosure findings | If offered: cited source hits, model/index provenance, stale-index and no-index fallback, and disclosure tests. Not an M5 exit dependency or 3.0 release gate. |

## M6 — Plan, build, and validate (P10)

| WP | Scope | Requirements | Depends on | Exit evidence |
|---|---|---|---|---|
| WP-45 | Neutral IR and adapter hardening (ADR-10): plan object, scope closure, generation manifest | BUILD-* | M3–M5 | Deterministic supported output; blocked cases fail honestly |
| WP-46 | Validation records and applicability (ADR-15) | VAL-* | WP-45 | Real tool evidence where it is available; an exact target and version matrix |
| WP-47 | AI assistance boundaries | AI-* | WP-05, WP-45 | Egress-policy tests; the core works without AI |
| WP-48 | One optional modernization execution loop over the shared project services and durable decision history; first journey pins a Form revision, inspects evidence and a blocker, presents a proposal for explicit human disposition, then recalculates eligibility. No new parser, target generator or multi-agent framework. | RUN-01..06 | WP-20, WP-31, WP-39, WP-40, WP-45, WP-46, WP-47; WP-12 task findings | One real synthetic journey through the product service boundary, persisted/reopened step and decision evidence, stale-context/denied-action tests, offline no-AI path, and UI/CLI agreement |

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
