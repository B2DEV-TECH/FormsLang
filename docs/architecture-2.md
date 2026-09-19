# FormsLang 2.0 implementation architecture

This page describes the implemented Phase A foundation, not the complete planned
2.0 product. For product scope and phases B-H see
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
| `project_service` | One authorized project connection, create/open/assessment/import operations |

The service does not parse source, implement classifiers or call a provider.
Phase B will add the single project analysis orchestrator and UI/API/CLI adapters.
The existing Workbench, parser, database analysis, Blueprint reasoning, conversion
review, APEXlang exporter, SQLcl adapter and desktop shell remain in place.
No new frontend framework or runtime dependency is introduced.

## Ownership and concurrency

Each service instance owns its Store connection. Do not share it between workers
or switch its project identity while an operation is running. Project creation
does not initialize AuthStore. Authenticated access goes through the existing
registry authorization check before its stored path is resolved; legacy registry
entries retain their legacy interface until explicit project migration.

Read projections use one SQLite read transaction. Assessment publication uses
compare-and-swap inside a write transaction, preventing competing analyses from
silently overwriting each other. Durable jobs, cancellation and process recovery
are Phase B work; this foundation does not claim background continuation.

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
- Future generation consumes revision-bound assessment/review/target state and
  must independently enforce eligibility; nothing here automatically deploys SQL.
- Unknown schema/target, partial analysis, stale evidence and unavailable source
  remain explicit states or errors, not success defaults.

## Testing layers

Pure model and manifest tests cover validation and deterministic identity.
Store integration covers recovery, transaction rollback, stale writes and history.
Migration tests compare full table content and actual deterministic APEXlang ZIP
bytes; WAL and injected failure cases use synthetic sessions. Service tests cover
offline initialization and the existing tenant/RBAC boundary. Foundation acceptance
composes the real parser and Blueprint and exercises multiple processes.

The full existing Python/JavaScript and browser suites remain compatibility gates.
Installer/upgrade, frozen fingerprint resources, corporate onboarding E2E,
accessibility of new screens and Oracle/APEX validation are subsequent phase gates,
not evidence implied by these foundation tests.
