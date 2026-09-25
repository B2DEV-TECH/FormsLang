# FormsLang 3.0 — Architecture decision index

Status: **M0.** No 3.0 ADR has been written or accepted yet. The "Default"
column is the direction the [specification](master-specification.md#31-required-architecture-decision-records)
proposes. It is a starting hypothesis, and an accepted decision can differ from
it. A dependent work package ([implementation-plan.md](implementation-plan.md))
does not change the governed area until its ADR is **Accepted**, and the ADR
is accepted only with the evidence listed below.

Every ADR is written as `docs/design/formslang-3.0/adr/ADR-NN-<slug>.md` and
states the context, the alternatives, the selected decision, the consequences,
the implementation boundary, the tests and the compatibility. The rationale
cannot be that a choice is modern.

Status values: *Not started* → *Draft* → *Proposed* (evidence attached) →
*Accepted* / *Rejected* → *Superseded by ADR-NN*.

| ADR | Decision to close | Default in the specification | Evidence required before acceptance | Baseline facts at `1d9cb47` | Blocks | Status |
|---|---|---|---|---|---|---|
| ADR-01 | Repository authority and transaction boundary | SQLite coordinator + immutable objects + canonical explicit export | Crash/failure matrix, no split authority, short transactions, migration compatibility | `project.session.db` is authoritative. The `project.json` mirror is published inside the `BEGIN EXCLUSIVE` transaction (`ce2cfdd`). Rollback journal, `busy_timeout` 1 s. Reads that write exist (baseline-audit §3.3). Windows starvation is open as #20. | WP-10, WP-20, WP-22 | Not started |
| ADR-02 | Object identities and canonicalization | Versioned domain-separated SHA-256; raw source bytes preserved | Golden byte examples, duplicate/collision behaviour, Unicode/ordering tests, distinction from signatures | Content-addressed backups and derived XML by SHA-256. Report `snapshot_revision` digest. No general object store. | WP-10, WP-20 | Not started |
| ADR-03 | Checkpoint and portable-history schema | Whole-state manifests with acyclic references and declared closure | Clean-workspace reopen, history coverage, report/artifact publication acyclicity | No checkpoints. `blueprint_snapshot` is a single overwritten row. | WP-20, WP-21 | Not started |
| ADR-04 | Trust of imported history and approvals | Preserve provenance; no approval by imported text alone | Forged actor/state tests, trusted-backup versus untrusted-exchange behaviour | Actor derived on the server for review decisions. 1.x import has no product route. | WP-20, WP-22, WP-31 | Not started |
| ADR-05 | DSL grammar and versioning | Small strict `.flm` format with typed mappings | Parser/fuzz/round-trip tests, meaningful PR review exercises, schema compatibility | No `.flm`. Decisions are stored as rows in `blueprint_review` and `decision`. | WP-30, WP-31 | Not started |
| ADR-06 | Cross-revision entity identity | Exact immutable identity + explicit locator/correspondence model | Rename/move/schema/overload/root/engine-change fixtures; no silent rebind | Database objects keyed by bare name (G-SCHEMA-COLLIDE). Blueprint entity IDs derive from names. | **WP-04**, WP-11, WP-31 | Not started |
| ADR-07 | Git exchange synchronization | Explicit preview/apply; external-change detection; no native Git clone | Branch/worktree/checkout/conflict tests; origin-local revision handling | Nothing exists. `.formslang/` holds local databases. | WP-20 | Not started |
| ADR-08 | Frontend technology and component split | Reuse a lightweight maintainable stack unless a measured alternative wins | Bundle/offline/installer/security/accessibility/CI tradeoffs and real journey prototype | Server-rendered HTML/JS in Python strings, no build step, CSP `default-src 'none'`, one vendored library | WP-41 (WP-12 feeds it) | Not started |
| ADR-09 | Report definitions, metrics, and renderers | Shared domain data pipeline and versioned definitions | Reconciliations, complete authorized scope, safe offline HTML/PDF/CSV, packaging tests | Revision-fenced reports in HTML, Markdown, JSON, CSV and ZIP. No PDF, and no definitions stored as data. | WP-21, WP-50 | Not started |
| ADR-10 | APEX adapter and generation granularity | Existing supported module-scoped capabilities first | Native-component mapping, closure, deterministic output, exact Oracle/target evidence | `apexlang.export_apexlang`, module-scoped, deterministic ZIP. The `target_adapter` registry is test-only. | WP-45 | Not started |
| ADR-11 | Local versus supported team/server mode | Local-first; broader mode separately gated | Threat model, route/action matrix, cache isolation, proxy/configuration and operational tests | Loopback server. Authenticated mode with RBAC/MFA exists. | WP-60 | Not started |
| ADR-12 | Backup/restore/retention and migration | Consistent backup, explicit migration, verified restore, reachable-object protection | Interrupted upgrade/restore/GC tests and legacy data reconciliation | Content-addressed backups of session databases. Implicit table migration in `open`. | WP-22, WP-61 | Not started |
| ADR-13 | CLI/API compatibility and errors | Shared schemas, origin-aware fences, stable exit/error meanings | Old-command compatibility, JSON/stdout/stderr tests, cursor and conflict behaviour | CLI `--json` and exit codes 0/1/2/130. HTTP 409 `PROJECT_CONFLICT`. No idempotency keys. | WP-40, WP-02 (error mapping only) | Not started |
| ADR-14 | Performance and resource limits | Bounded queries and ratified fixture-specific budgets | Hardware/fixture baseline, p50/p95/memory, Windows stability, limit and cancellation tests | 2.2 baseline in `docs/design/ecosystem-explorer-2.3/performance-2.2-baseline.md`. Windows rate 4/400 (#20). | WP-11, WP-62 | Not started |
| ADR-15 | Validation applicability and acceptance | Artifact/case/environment-bound evidence; separate UAT | Changed-artifact/criteria tests, stale-run handling, human acceptance provenance | Validation records stored per artifact (offline SQLcl). Runtime acceptance is not claimed. | WP-46 | Not started |

## Decisions that M0 does not need

The M0 slices (WP-02, WP-03, WP-05, WP-06) change no persistence format, entity
identity or public contract. WP-03 restores subprogram extraction for one
statement form, and entity IDs for unqualified bodies do not change. WP-04 is
the first package that needs an ADR: ADR-06, because it changes how database
objects are keyed.

## Unresolved questions for the owner

None are blocking M0. These come up in M1:

- **ADR-01:** whether to adopt WAL for `project.session.db`. This is one of the
  options in #20. It interacts with portable export and with network drives.
- **ADR-11:** whether the authenticated mode that already exists is part of the
  3.0 supported boundary or stays separately gated.
