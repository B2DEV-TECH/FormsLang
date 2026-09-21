# FormsLang 2.0 implementation architecture

This page describes the FormsLang 2.0 foundation, assessment, review, gated generation
and snapshot delivery. Release acceptance remains separately recorded. For product scope see
[product architecture](formsLang-2-product-architecture.md). For storage and a
runnable example see [project model](project-model.md).

## Boundaries

| Module | Responsibility |
|---|---|
| `project_model` | Immutable metadata/target/source contracts; allowlisted serialization |
| `project_manifest` | Safe relative identities, bounded raw-byte hashing, engine/revision identity |
| `project_store` | Existing Store composition, project SQL transactions and descriptor recovery |
| `project_assessment` | Existing Blueprint provenance binding and consistent review projection |
| `project_migration` | Read-only validation, WAL-safe backup, verified legacy copy and provenance |
| `projects` | Existing registry and tenant/RBAC boundary; local/request-scoped access contexts |
| `project_service` | Shared façade: create/open/discover/analyze/freshness/relink/import |
| `project_intake` | Source capabilities, locators, tenant boundary and normal demo copies |
| `project_discovery`, `project_sources` | Bounded discovery, diagnostics, staged bytes and stable identities |
| `project_jobs`, `project_lock` | Durable jobs, process lock, cancellation and publication fencing |
| `project_analysis`, `project_freshness` | One analysis orchestrator and hash verification without reasoning |
| `project_conversion` | Explicit staged Forms2XML and hash-bound derived representations |
| `project_projection` | Deterministic, bounded Overview/Inventory read models and an in-memory revision cache |
| `project_http`, `project_cli` | Versioned HTTP and local CLI adapters; no second pipeline |
| `ui/modernization_project*` | Existing HTML/JS shell: onboarding, Overview, Inventory, progress and recovery |

The service delegates analysis; it does not implement classifiers or call a provider.
UI and CLI call the same service/orchestrator: discovery, staging/parsing, existing
Blueprint reasoning, assessment binding and atomic persistence. Opaque engine stages
are not presented as invented fine-grained progress.
The existing Workbench, parser, database analysis, Blueprint reasoning, conversion
review, APEXlang exporter, SQLcl adapter and desktop shell remain in place.
No new frontend framework or runtime dependency is introduced.

## Phase C read boundary

Phase C projects the current persisted `ProjectAssessment`; it never parses source,
runs Blueprint, calls AI, connects to Oracle or classifies findings on a read. The
server prepares one safe read model containing normalized rows and bounded summaries.
Overview, Inventory, CLI and HTTP use those same functions. Modernization units are
Blueprint findings/recommendations, not every entity or graph node.

Prepared projections are not persisted. A bounded, process-local LRU caches them by
store scope, opaque project id, analysis revision, review revision, target tuple and
freshness. Analysis publication, review revision, target changes or freshness changes
therefore select a different cache key; closing/restarting simply rebuilds from the
saved assessment. No projection table, search index or second source of truth exists.

The scale gate uses 500 synthetic Forms, 5,000 findings and 5,000 non-structural
dependencies. It reconciles all counts before timing. The measured cold/reopen cost
is a few seconds, while bounded pages, filters/search and warm-cache Overview are
small enough to retain the simpler architecture. See [project overview](project-overview.md)
and [acceptance evidence](quality-acceptance.md). A future optimization must rerun
that gate; evidence, not feature count, decides whether a persisted projection is
needed.

## Ownership and concurrency

Phase D adds `project_review` behind ProjectService. Queue and detail reuse Phase C
projections; decisions retain the existing append-only `blueprint_review` model.
An additive annotation table/trigger advances the same review revision. Worker lock,
SQLite revision fencing and pre/post source checks protect mutations. No projection
table or analysis logic is added. See [review contracts](modernization-review.md).

The measured 5,000-finding review gate exposed an entity-by-edge scan. A single
in-memory dependency counter replaces that quadratic pass while preserving counts.
The synthetic measurements and their limits are recorded in acceptance evidence.

Each service instance owns its Store connection. Do not share it between workers
or switch its project identity while an operation is running. Project creation
does not initialize AuthStore. Authenticated access goes through the existing
registry authorization check before its stored path is resolved; legacy registry
entries retain their legacy interface until explicit project migration.
The original registered spelling is checked for redirects before the legacy path
resolver canonicalizes it. A real Windows junction regression exercises this
boundary; checking only containment in the global data directory is insufficient.

Read projections use one SQLite read transaction. Assessment publication uses
compare-and-swap inside a write transaction, preventing competing analyses from
silently overwriting each other. A process-level file lock plus in-process lock,
SQLite ownership token and revision preconditions exclude competing CLI/UI writers.
Workers own their connection and reauthorize at checkpoints. HTTP acknowledges 202
after job claim. Recovery must acquire the OS lock: heartbeat age or PID alone
never proves a worker dead. Orphans become `FAILED / PROCESS_INTERRUPTED`; work
does not continue after process exit.

Cancellation is cooperative between files/phases, preserving the previous assessment.
Source and configuration are rechecked before publication. Run timings/job IDs stay
outside deterministic content. UI response/write guards bind to project identity
and view generation, preventing pending operations from targeting a new project.

Existing Store defaults are preserved. A new keyword-only `reconcile_jobs=False`
lets project readers and migration avoid marking a live legacy conversion job as
interrupted. Failed Store initialization closes its SQLite connection so Windows
can safely clean up staging files.

## Trust and extension rules

- Descriptor paths do not grant permission. Source reads/import require explicit
  host-approved roots; authenticated request contexts are re-derived per request.
- Keep credentials in the existing OS-backed secret store, not these models.
- Static project foundation performs no external AI, Oracle connection or telemetry.
- New assessment fields extend a versioned projection; do not rewrite engine
  evidence with human decisions or represent architecture approval as code approval.
- Project generation consumes revision-bound assessment/review/target state and
  must independently enforce eligibility; nothing here automatically deploys SQL.

## Project generation boundary (Phase E)

`ProjectService` delegates to `ProjectGenerationService` and one server-side
`project_generation_policy`. The existing module conversion Store, APEXlayout and
APEXlang exporter remain the only code approval and generation path. The existing
`project_module_session` registry binds a conversion session to source identity and
analysis revision. Additive target-plan, artifact and validation records live in
ProjectStore; no second project model or projection tables are introduced.

Architecture approval never implies code approval. An approved code event records
source/analysis/review/target binding in the existing append-only decision table.
Its revision includes event identity/provenance, not just code text or timestamps.
Project locking, module write locks, parent revision fences and source verification
protect publication. Parent and module SQLite files are not a distributed transaction:
interrupted target-key publication fails closed through key/plan mismatch detection.

Each selected independent module generates a versioned application and ZIP. All
files are hashed, read containment is checked, and edits invalidate applicability
of validation. Offline SQLcl validates an isolated copy; validation stores the tool,
mode, exact artifact hash and safe result, never claims functional equivalence.
See [generation contracts and limitations](project-generation.md).
- Unknown schema/target, partial analysis, stale evidence and unavailable source
  remain explicit states or errors, not success defaults.

## Testing layers

### Phase F delivery boundary

ProjectService delegates snapshot capture and export to ProjectReportService;
project_report_render contains pure HTML/CSV/JSON rendering. No additional Store
or projection tables exist. Export captures persisted assessment, review/annotation
history, plans and artifact metadata under revision fencing, then checks source
freshness before returning. Default deliverables exclude source bodies and human
notes. Artifact inclusion is explicit, read-only, revision/hash checked and records
exclusions. UI, CLI and authenticated HTTP use this same boundary, including EXPORT
authorization. See [report contracts](project-reports.md).

Pure model and manifest tests cover validation and deterministic identity.
Store integration covers recovery, transaction rollback, stale writes and history.
Migration tests compare full table content and actual deterministic APEXlang ZIP
bytes; WAL and injected failure cases use synthetic sessions. Service tests cover
offline initialization and the existing tenant/RBAC boundary. Foundation acceptance
composes the real parser and Blueprint and exercises multiple processes.

The full existing Python/JavaScript and browser suites remain compatibility gates.
Phase B adds service/API/CLI lifecycle and real-browser onboarding, server-process
restart, stale/missing/relink, partial failure and cancellation acceptance. Phase C
adds deterministic count reconciliation, revision-safe paginated reads, XSS-safe
Overview/Inventory rendering, response-race tests and 500-Form read-scale evidence. Frozen
executable and isolated-wheel checks exercise bundled demo and fingerprints.
Scripted accessibility checks are not a manual screen-reader audit. Installer/upgrade
and live Oracle/APEX validation remain release gates; a frozen engine is not a
native-installer acceptance. See [workflows](project-workflows.md) and
[acceptance evidence](quality-acceptance.md).
