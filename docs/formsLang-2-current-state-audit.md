# FormsLang 2.0 current-state audit

Date: 2026-09-19. Source inspected: `d592998` on `main`, after the published
`v1.6.0` tag (`7563431792e4f6e4d1360e32328be5cbec69e113`).

This is a repository audit and a fresh local baseline, not 2.0 acceptance.
The proposed design is [FormsLang 2.0 product architecture](formsLang-2-product-architecture.md).
No product behavior or version declaration changed during this audit.

## Conclusion

Reuse the current Workbench, deterministic engine, Blueprint, review storage,
APEXlang exporter, validation adapters and desktop distribution. The missing
foundation is a persistent modernization-project application service shared by
GUI, CLI and local API. Building another shell or another classifier would not
address the principal product gap.

Today, the conversion workflow is primarily module/session-oriented. Blueprint
can reason over multiple modules and database sources, but this capability is
not a complete project lifecycle in the UI. Existing authenticated project
registration is an authorization/storage registry, not that lifecycle.

## Inspection scope

The audit covered repository history and file inventory, the requested README,
CHANGELOG, SPEC, methodology, modernization-blueprint, risk-model,
layout-mapping-matrix, apex-import-verification, auth-multitenancy-design,
phase4-product-experience documents, quality-acceptance and releasing guidance.
It traced the relevant implementations under `formslang/`, UI composition,
desktop startup, packaging, workflows and representative tests/acceptance harnesses.
This is a cross-layer architecture inspection, not a claim that every line in
every test or generated asset received an independent security review.

## Architecture and reuse map

| Area | Current implementation | Reuse and 2.0 gap |
|---|---|---|
| Workbench | `formslang/workbench.py`, `formslang/ui/` | Preserve corporate styling, panels, keyboard behavior and progressive evidence. Add project-first entry and service-backed views. |
| Frontend | Python-composed HTML/CSS/JavaScript in `ui/__init__.py` and feature modules | No replacement SPA framework is needed. Existing all-task state responses must not become the large-estate listing API. |
| Desktop | `desktop/src-tauri/src/main.rs`, Tauri configuration/capabilities | Thin shell starts a loopback sidecar, opens native report windows and owns process shutdown. Preserve it; add project onboarding within the existing UI. |
| Distribution | `packaging/`, desktop manifests, release workflows | Frozen Python sidecar and Windows installers already exist. Bundle public-safe demo data and prove the 1.6.0 upgrade path. |
| Local API | Workbench request handler and feature routes | Existing Host/content-type/auth checks are assets. Introduce versioned project APIs with pagination and consistent authorization. |
| Project registry | `projects.py`, `authstore.py` | Existing external/adopted session registration is tied to authenticated usage. Local no-account modernization projects still need a domain model. |
| Session persistence | `store.py` | SQLite stores tasks, proposals, decisions, Blueprint state/reviews, settings and job information. Preserve histories and compatibility; add explicit project/revision boundaries. |
| Forms ingestion | CLI collection, parsers, `blueprint_io.py` | Reuse parsing and parse-failure handling. New UI must discover sources and explain binary/XML conversion rather than require CLI preparation. |
| Database ingestion | `database.py` | Existing SQL package/table/view context is valuable. Extend discovery honestly; unsupported semantics must remain explicit. |
| Reasoning | analysis/risk modules, `blueprint.py`, `modernization.py` | Deterministic cross-layer reasoning already exists. Orchestrate it once per project, not through frontend business logic. |
| Blueprint | `blueprint_view.py`, explorer APIs and UI | Reuse bounded evidence, dependencies and architectural review. Add project-level target planning and risk-first navigation. |
| Conversion review | Store decisions and review/conversion UI | Existing code review is distinct from Blueprint architecture review. Neither is an automatic substitute for the other. |
| APEXlang | `apexlang.py`, `apexlayout.py` | Existing deterministic export and structural preview are foundations. Add project composition, scoped eligibility and explicit blockers. |
| Validation/import | `apeximport.py`, validation UI/CLI | Preserve SQLcl validation and explicit import separation. Bind validation results to exact artifacts. |
| Credentials/AI | secret-store, policy/provider and context mechanisms | Preserve OS-backed secret storage and optional AI. Static assessment must not require provider configuration. |
| Authentication | `authstore.py` and Workbench auth routes | Existing tenant membership, roles, sessions, MFA and rate-limit controls must survive project APIs. Local use need not become account-gated. |
| Tests | `tests/`, `examples/verify/`, CI workflows | Extend existing layers, including browser and installer acceptance, rather than replace the infrastructure. |

## Important observed boundaries

### Project and concurrency

Workbench holds a current Store/module and process-local job/provider state.
Some conversion jobs have persistent records, while optional Blueprint AI jobs
are process-memory work. This is not proof that every job survives app exit.
The new service needs explicit ownership, cancellation, interrupted-job recovery
and per-project locking. Session Store and auth storage have different connection
and locking behavior; background workers must not casually share SQLite handles.

Blueprint results are cached with database change indicators, and historical
decisions already have stale-state concepts. These are reusable, but cache
invalidation must also account for source content and engine/rule revisions.

### Discovery versus parsing

Database directory ingestion currently selects `.sql`, `.pks` and `.pkb`.
Recognizing `.prc`, `.fnc`, `.trg` or `.vw` in a new inventory is not equivalent to
implementing their semantics. Standalone routine/trigger handling needs explicit
support and tests before coverage claims. Package/table/view parsing is already
useful and should be retained.

Existing database dictionaries can overwrite colliding names, and qualification
handling needs attention for multi-schema estates. Do not silently combine two
objects because their short names match.

Current collection prefers binaries over paired XML in the legacy path. The
project-first path should make usable Forms2XML exports easy to select, report
unverified pairing/freshness, and preserve CLI compatibility. Binary libraries,
menus and object libraries must not be counted as fully analyzed solely because
their extensions were discovered.

The Blueprint UI path does not currently expose the database-source intake that
the underlying analysis path supports. This is a product integration gap, not a
reason to create a second database engine.

### Reproduced source-revision gap

An in-memory synthetic probe built the same Forms module twice against a package
body at the same `db/api.pkb` path. The routine body changed from `NULL;` to
`COMMIT;`. The Blueprint payload changed but `source_revision` did not.

Observed output:

```text
source_revision_equal: True
full_payload_equal: False
engine_includes_modernization_version: False
```

The current Blueprint revision incorporates database file names rather than a
complete content manifest. Its engine-version composition also does not include
the modernization rules version. Individual finding fingerprints may still change;
this probe does not establish that every prior review survives incorrectly.
It establishes that the global revision is insufficient for the 2.0 provenance
and dependency-sensitive revalidation contract. Add failing regression tests,
then content fingerprints and complete engine identity in Phase A/B.

### Review and generation

Blueprint keeps append-only architectural review and stale overlays. Conversion
review separately approves executable proposals. Preserve both histories and
their meanings; accepting an architectural recommendation must not silently
approve executable code.

The exporter currently builds a module/page-oriented artifact using the existing
layout model. It has deterministic packaging and explicit handling of approved
components, but not a complete estate-level generation eligibility service.
An exportable structural skeleton is not proof that all Forms business behavior
has been preserved. Existing mappings have deliberate limits, including navigation,
dynamic LOV behavior, editable grids and DML-key prerequisites.

Current export replaces its generated output directories. Project generation
should instead produce identifiable artifact revisions and preserve manually
edited `.apx` files. Multi-module page IDs and shared-component collisions need
stable allocation and tests.

### Security and trust

Static analysis can remain offline. Existing provider policies and source-context
limits should be reused, with explicit disclosure of what optional AI receives.
Local telemetry is not a mandate for external analytics.

New mutation APIs need exact origin/port validation, authenticated project scope,
approved filesystem roots, safe rendering and bounded requests. Existing origin
checks include hostname-based behavior; do not assume that is the complete new
API contract. Preserve loopback cookie protections without pretending a local HTTP
cookie has an HTTPS transport guarantee. The current desktop CSP configuration
also merits a targeted review, not an unsupported claim of complete hardening.

Credentials belong in the existing secure backend, never project JSON, SQLite
project metadata, reports or diagnostics. Executive reports should omit source,
absolute paths and private review notes by default.

## P0 implementation dependencies

1. Define the persistent project/assessment model, complete source manifest,
   revision contracts, safe migration and project authorization boundary.
2. Add source discovery and a single analysis orchestrator with progress,
   partial failures, cancellation and durable results.
3. Expose service-derived summaries, inventory and priority review through
   bounded APIs; preserve evidence and existing review histories.
4. Connect review state to generation eligibility without conflating architectural
   decisions, code approval, syntax validation and runtime equivalence.
5. Produce reports/backlog/package from persisted assessment, then prove reopen,
   legacy migration, scale behavior and installer upgrades.

The architecture document specifies phases A-H and keeps incremental processing,
bulk review, portfolio and snapshots behind the P0 single-project workflow.

## Documentation drift

Some existing documentation describes earlier milestones rather than the current
implementation: README status language, SPEC details, methodology limitations
about layout/database context, and authentication design status require alignment.
The historical methodology also includes assumed effort factors; these must not
become invented hours/cost estimates in the new product dashboard.
Update public claims as each capability is actually implemented, not in advance.

## Fresh verification performed

Environment: Windows, Python 3.13. Commands ran against the unmodified product
code at the audited revision; only these proposed documentation files were added.

| Check | Actual result |
|---|---|
| `python -B -m pytest -q -p no:cacheprovider --basetemp <isolated-audit-directory>` | **1,134 passed, 2 skipped**, 132.74 seconds |
| `python -B -m ruff check . --no-cache` | **All checks passed** |
| `python -B examples/verify/workbench_browser_check.py --output <isolated-audit-directory>` | **101/101 checks passed**, 27 screenshots |
| Synthetic database content/revision probe | Revision gap reproduced as described above; no repository fixture modified |
| Frozen baseline/ground-truth content comparison with HEAD | 24 tracked files checked, zero differences |

Browser evidence directory for this local run ends in `run-fbc444983d17` and
contains `result.json` plus screenshots. The harness identifies its provider as
an offline synthetic stub: **no AI model ran**. Its keyboard, theme, contrast,
responsive/panel and workflow checks are evidence for the existing UI, not a
certification of the proposed 2.0 experience.

Not performed in this audit: a new benchmark prediction run, fresh Windows
installer build/install, 1.6.0-to-2.0 upgrade, connected Oracle/APEX validation,
new SQLcl validation, 100/500-form performance measurements, human productivity
experiments, or a 2.0 release. Historical acceptance in `quality-acceptance.md`
must not be represented as newly executed evidence.

## Delivery status

The audit and proposed architecture are ready for design review. Product code,
version numbers, published tags, benchmark history and release assets remain
unchanged. FormsLang 2.0 is not implemented or release-ready at this milestone.
