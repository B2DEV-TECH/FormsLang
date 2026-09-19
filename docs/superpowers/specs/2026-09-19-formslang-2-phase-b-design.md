# FormsLang 2.0 Phase B: onboarding and project analysis

Status: proposed implementation design, awaiting owner review. No Phase B
implementation or acceptance is claimed. The owner's Phase B brief is authoritative.

## Intent and verified starting point

Deliver the real local-first journey: create a project, select source roots,
discover, analyze, observe progress/errors, cancel, persist, close and reopen.
Desktop, browser, HTTP and CLI share the Phase A ProjectService and ProjectStore.
This is not Phase C or a FormsLang 2.0 release.

- Branch: `codex/formslang-2-phase-b`.
- Base: `3f4d6914225a3a1df9e151d93e8669811261d753`, merge of PR #5.
- Included Phase A head: `1fa086499a59c6678f91c278147115b39e7111a8`.
- Pre-change Windows / Python 3.13 verification: **83 passed, 2 skipped in 7.61s**.
  Command: `python -B -m pytest -q -rs -p no:cacheprovider` followed by
  `tests/test_project_model.py`, `test_project_manifest.py`, `test_project_store.py`,
  `test_project_assessment.py`, `test_project_migration.py`, `test_project_service.py`,
  `test_project_foundation_acceptance.py`, `test_project_review_regressions.py`
  (all under `tests/`).
- Skips: OS symlink privileges in manifest/service tests. The separate Windows
  NTFS junction regression passed.
- Frozen baseline/ground-truth tracked files hash-compared with Phase A head:
  unchanged. Product version remains 1.6.0. Full-suite verification is a later gate.

## Approach and component boundaries

Extend the approved application-service architecture, not the underlying project
model. A wizard chaining engine endpoints would move orchestration into JavaScript;
a separate worker service would add deployment overhead. Neither is selected.
Use local workers with dedicated connections and the same synchronous orchestrator
for CLI execution. Keep Python >=3.10, stdlib runtime and existing HTML/JS/Tauri.

| Component | Responsibility |
|---|---|
| `project_discovery.py` | Authorized traversal, candidates, pairing, content preview |
| `project_analysis.py` | Single orchestration operation, staged inputs, engine composition |
| `project_jobs.py` | Durable lifecycle, ownership, cancellation and recovery |
| `project_freshness.py` | Rediscovery/hash comparison and relink verification |
| `project_service.py` | Extend existing facade; never duplicate classifier logic |
| `project_store.py` | Additive tables/transactions in the existing project database |
| `projects.py` | Existing authorization boundary, intake and local locator handling |
| `project_http.py` | V2 HTTP adapter with safe, request-authorized projections |
| `project_cli.py` | Project subcommands wired into existing argparse CLI |
| `ui/modernization_project.py` | Existing shell's wizard, progress and saved summary |

The implementation plan may split focused support modules. No second project
model, persistence backend, ownership registry or frontend framework is introduced.

## Intake, locations and authorization

Local UI defaults to a project directory under the existing application data
directory, named by opaque ID rather than user-supplied project name. Advanced
location selection/Open Project support portable projects. Explicit local folder
selection grants source access under the OS-user trust model; no AuthStore starts.
CLI supplies explicit destination and approved roots. Descriptor paths alone
never grant access, including when opening a relocated or downloaded project.

Authenticated creation uses the existing organization registry and managed data
directory. Reserve the same opaque identity as the descriptor and make incomplete
initialization recoverable; do not publish a usable registry entry before storage
exists. Host-approved source areas are configured per organization outside portable
descriptors. The picker returns area IDs and relative children, not host paths.
With no approved areas, show host-setup guidance; do not fall back to arbitrary
filesystem browsing. Source type is not authorization.

Every request rechecks session, normal MFA scope, current membership, organization,
project and action through existing authorization. Use VIEW_PROJECT, CREATE_PROJECT
and RUN_CONVERSION as appropriate. Relink/conversion are writes. Foreign project
or job IDs follow non-disclosing 404 policy; insufficient role in a visible project
is 403. Workers recheck authorization before start and publication; revoked access
must not survive in a cached ProjectAccess. Each request/worker owns its connection.

Local recents persist locators only in the configuration area, not analysis state.
Names/counts come from descriptors/assessments. Local approved-root capabilities
are host-side metadata, not portable descriptor authority, and containment is
revalidated on use. Auth mode lists only its current organization's registry;
never combine it with local recents.

## Discovery and representation support

Retain root kinds forms/database/supporting and Phase A root-relative source IDs.
Reject duplicate/overlapping selected roots. Detect physical aliases and disclose
exclusion; identical content at distinct logical locations is disclosed rather
than silently conflated. Same basename across roots must remain distinct.

Traverse deterministically with bounded reads, visited directory identities and
cancellation checkpoints. Do not follow directory symlinks/junctions; reject
redirected roots and escaped file targets with safe diagnostics. Skip `.git`,
`.formslang`, caches/build/virtual environments and project-generated outputs.
Benchmark output folders are excluded unless deliberately selected as safe roots.
Project-owned storage is never an input, even when explicitly selected.

Discover XML/FMB/PLL/MMB/OLB and SQL/PKS/PKB/PRC/FNC/TRG/VW. Lifecycle, selection,
hash availability and semantic support are separate fields. Preview uses bounded
existing parsers for content verification. Non-FormModule XML and unsupported
libraries/menus/SQL remain visible with remediation. Zero objects from unsupported
SQL is not a successful semantic parse. No new general PL/SQL parser is in scope.

FMB pairs only with unambiguous same-root/same-directory expected-name or same-stem
XML. Prefer XML, retain original binary provenance, and set freshness_verified=false.
Do not silently convert when pairing is ambiguous or XML is malformed. Offer
existing XML selection, continue, and instructions based on the current adapter.
Explicit conversion reuses `oracle.convert_module` on staged copies with timeout;
never modify originals. Register generated XML as an explicitly selected derived
representation with binary/tool provenance, not an auto-discovered output tree.
Only parser-supported semantics count after conversion. No proprietary binary ships.

Parse database files independently using `parse_database_file`, not the current
last-writer-wins directory merge. Check duplicates before combining objects.
Package spec/body are compatible distinct kinds. Conflicting definitions of the
same parser identity are excluded from ownership reasoning with diagnostics.
Schema/overload ambiguity remains disclosed; do not invent qualified resolution.

## Analysis and immutable publication

One `ProjectService.analyze` delegates to `analyze_project` with progress and
cancellation. UI never schedules parser/risk/Blueprint calls itself:

1. Validate authority, descriptor, target and revision preconditions; claim job.
2. Discover candidates and publish provisional inventory for that run.
3. Fingerprint using Phase A contracts and stage selected bytes locally.
4. Verify staged hashes against the manifest; parse those exact bytes.
5. Collect file failures and conflict-safe database objects.
6. Call existing `blueprint.build` with unique logical source keys and DatabaseProject.
7. Bind the assessment using complete engine/options/target identity.
8. Rediscover/rehash inputs, including added/deleted candidates.
9. Recheck cancellation/authority/ownership/configuration and atomically publish.

Staging prevents edit-and-restore races from producing evidence inconsistent with
hashed inputs. Normalize staging paths to logical root-relative identities before
engine input/persistence. No source bodies in diagnostics. Temporary source copies
stay local, bounded and removable after terminal state.

Changed-during-run yields INCOMPLETE_SOURCE_CHANGED and leaves the previous current
assessment untouched. Cancelled/failed jobs also preserve it. Partial usable
results may publish an Incomplete assessment. No usable supported source fails
with remediation, not a reassuring empty assessment.

Extend the existing envelope additively with deterministic inventory, diagnostics
and completion state COMPLETE / COMPLETE_WITH_WARNINGS / INCOMPLETE. Keep Phase A
Current/Incomplete compatibility; freshness is a separate read projection. Material
failed/unsupported inputs imply coverage gaps; informational exclusions need not.
Old assessments remain readable without recomputation. Run IDs, times and durations
remain in run metadata. Unchanged engine/source/options reuse revision and original
assessment timestamp. Human history is never rewritten as engine evidence.

Engine identity includes discovery/orchestration semantic code. Frozen builds must
ship fingerprint resources and demo data. Verify packaged-engine behavior; browser
tests alone do not establish desktop distribution parity.

## Durable jobs and concurrency

Add discovery, source-entry, job and run metadata tables through transactional
additive ProjectStore migrations. Preserve Phase A reviews/assessments and existing
legacy conversion-job behavior. Live jobs never belong in project.json.

States: QUEUED, RUNNING, COMPLETED, COMPLETED_WITH_WARNINGS, FAILED, CANCELLED.
Store job/project IDs, requested analysis/configuration revision, phase, processed,
total, warning/error counts, started/finished times, cancellation request, safe
failure, owner token and heartbeat.

Use an in-process project lock, an OS-held worker lock and transactional SQLite
ownership/fencing token. OS lock release supplies process-death evidence: PID or
expired heartbeat alone cannot justify cancelling another process. Recovery must
acquire the worker lock and recheck ownership transactionally before marking an
orphan FAILED / PROCESS_INTERRUPTED. Unknown ownership stays busy rather than
guessed dead. Opening cannot cancel a slow live job.

Publication checks ownership, cancellation, configuration precondition and assessment
CAS in one write transaction. Cancellation after successful commit reports the
terminal outcome, not a fictitious rollback. Relink conflicts with active analysis.
No mutable global current-project service; job connections belong to workers.
Shutdown requests cancellation, with orphan recovery after unclean process exit.

Progress uses real boundaries: discovery, Forms parsing, database parsing, combined
Blueprint/reasoning, assessment and persistence. Do not fabricate per-edge progress
inside opaque engine calls. Cancellation checks between files/stages; disclose that
an active opaque engine call must return. No background-continuation promise.

## Reopen, freshness and relink

Return saved assessment immediately with freshness Checking, then rediscover and
hash asynchronously without analysis or external calls. States: CURRENT, STALE,
MISSING_SOURCE, INCOMPLETE; pending/unverifiable checks are explicitly UNVERIFIED.
Size/mtime alone never prove freshness. Engine changes are independently visible.
Changed/unavailable sources suppress current approval applicability, not history.

Relink requires authorized folder selection and configuration precondition, keeps
root IDs, and fingerprints the replacement. Same names alone cannot establish
equivalence. Update SQLite then repair the mirror in Phase A order. Missing roots
offer Relink and View Saved Assessment. Full incremental parsing remains deferred.

## API and CLI

Insert V2 dispatch after existing Host/Origin/CSRF/session guards, with sanitized
error handling instead of legacy raw exception strings. Keep `/api/projects` intact.
Required routes under `/api/v2/projects`:

```text
GET  /                         authorized recent/project locators
POST /                         create after validated wizard input
GET  /:id                      summary and configuration revision
GET  /:id/discovery            saved paginated discovery
POST /:id/discover             refresh discovery
POST /:id/analyze              202 plus durable job ID
GET  /:id/jobs/:job_id          project-scoped progress/result
POST /:id/jobs/:job_id/cancel   request cancellation for that exact job
GET  /:id/assessment           saved assessment and freshness projection
POST /:id/relink               authorized root replacement
```

Narrow supplementary routes handle source-area browsing, draft discovery before
creation, explicit conversion, freshness, Open Project and demo creation. Draft
preview is not a persisted project. Paginate lists: default 50, maximum 200.
Configuration/analysis preconditions return 409 for stale writes. Safe messages
include source_id, relative_path, stage, error_code and remediation, no stack trace.
Authenticated responses use relative names and never unrestricted absolute paths.

CLI adds project create/discover/analyze/status/info/open/relink via the same
service. Create takes name, destination, source roots and target 26.1. JSON stdout
is separate from stderr progress. SIGINT requests cooperative cancellation.
Auth-enabled CLI cannot bypass ownership via local access; require authorized
identity or fail with guidance. Preserve existing 1.x commands and collection rules.

## UI and demo

Extend the current Workbench shell: New Project, Explore Demo Project, Recent
Projects, Open Existing Session. Four steps: Project, Sources, Target, Analyze.
Draft memory survives ordinary intra-app navigation, without browser-stored secrets.
Local folder browsing works in both browser and Tauri; native picker is optional.
Source preview has real counts, unsupported representations and per-file diagnostics.
Target values come from TargetProfile. Local static analysis never initializes
saved AI/DB connections; optional configuration is secondary and defaults to Skip.

Show provisional inventory, phase/counters/elapsed time, warnings and Cancel.
Completion opens saved summary with real modules/DB objects/findings, coverage,
timestamp, freshness and Refresh/Relink. No hardcoded dashboard or effort estimates.
Use request/context generation guards so delayed A responses cannot update B.
Preserve draft state and verify pending writes never mutate the newly selected project.
Require labels, inline error associations, step focus, aria-live progress, keyboard
navigation and reduced-motion compatibility.

Bundle a compact public-safe demo as package data, distinct from benchmark LOM.
Copy into a normal project and run the real service. Include shared DB API,
duplicated validation, navigation, native APEX opportunity, refactor and critical
manual control. Assert actual engine evidence, never fixture-name special cases.

## Verification, review and delivery

Sequence: discovery/staging; jobs/publication; freshness/relink/intake; API/CLI;
wizard/demo; acceptance. Each coherent milestone has failing tests first and a
focused commit. Implementation plan will define exact interfaces and test cases.

Cover all requested source types; pairing; malformed/unsupported input; duplicate
roots/objects/physical aliases; same basenames; excluded outputs; symlink/junction
escapes; cancellation at all boundaries; live/dead worker and PID reuse; two-process
analysis; mid-run edits including edit-and-restore/new files; deterministic rerun;
reopen/relink; revoked users; foreign jobs; recent leakage; Host/Origin/CSRF; HTTP
400/403/404/409/202 and pagination; CLI/API parity; project-switch races.

Browser acceptance runs the real stack on synthetic folders: launch, wizard,
preview, target, Analyze/progress/completion, close/restart/reopen, stale source,
relink, cancel and demo. Preserve existing browser/JS/auth/security tests. Add
packaged-engine fingerprint/demo smoke. No Oracle/customer environment is required.
Measure discovery/parsing/reasoning/persistence durations on named fixtures and
memory where available; no invented scale thresholds or human productivity results.

Conduct security, concurrency and product reviews; fix material findings. Update
project-model.md, project-workflows.md, architecture-2.md, forms-to-apex.md and
quality-acceptance.md with implemented/future boundaries and exact evidence.
Final checks: full Python, Ruff, JS/browser, Phase A/B and auth tests, deterministic
rerun, frozen baseline hashes and git diff --check. Preserve stable README claims.

Phase C dashboard/visualization, priority review, project generation, reports,
portfolio and incremental caching are deferred. All Phase B P0 items remain gates;
a backend-only milestone is not completion. No version bump, tag or release.
Return the owner's 32-field report only after acceptance, then ask how to integrate.
Do not automatically push or merge.
