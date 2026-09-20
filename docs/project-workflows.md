# Modernization project workflows — Phase C development

Unreleased 2.0 development, still versioned 1.6.0 until release acceptance. Phase C
adds Overview and Inventory on the persisted Phase B assessment. It does not add the
Phase D decision workflow, Phase E project generation or Phase F reports.

## First assessment

Launch the existing desktop or local browser Workbench. An empty session opens
**New Project**, **Explore Demo Project** and recent projects. Existing sessions
remain accessible through **Open Existing Session**.

1. Enter a name; description and client label are optional.
2. Choose Forms and/or database folders. The local folder browser accepts a path
   and directory navigation; it does not require a Tauri-only picker. Discovery
   immediately shows actual inventory and representation warnings.
3. Confirm Oracle APEX / 26.1 / APEXlang. No credentials, local account, AI provider,
   API key or YAML configuration is required for static analysis.
4. Select **Analyze Project**. Observe phases/counts, warnings and elapsed time, or
   cancel. Completion opens the real persisted Overview.

## Overview and Inventory

Opening an analyzed project loads its saved assessment immediately and checks source
freshness without rerunning analysis. Overview answers scope, risk, recommendation,
intervention, priority and source-coverage questions using deterministic server-side
projections. Counts are not reconstructed in JavaScript. `UNKNOWN` remains visible;
`AUTO` means a mechanical intervention category, not generation readiness.

Risk and recommendation metrics open the server-filtered Findings inventory. **Start
Priority Review** opens unresolved findings in the documented deterministic priority
order; Phase D will extend the decision workspace, not replace this read path.
Inventory categories are Forms, Libraries, Packages, Routines, Views, Tables,
Dependencies, Business Rules and Findings. Search/filter changes replace page state.
Every later page carries the assessment revision; a 409 resets to page one rather
than mixing revisions. Detail is bounded and restores focus to its originating row.

Stale, Incomplete, Missing Source and Unverified remain prominent while saved metrics
stay viewable. A missing root links to Phase B relink. No DB source produces an honest
cross-layer-evidence limitation instead of fabricated completeness. See
[Overview semantics](project-overview.md).

Malformed files produce source-relative diagnostics and remediation. Failed
material inputs make coverage Incomplete; successful files still contribute. If
there is no supported input, analysis fails honestly. Cancellation waits for the
next safe file/phase boundary and preserves the previous assessment; an opaque
Blueprint stage cannot be interrupted midway. Work does not continue after exit.
Reopen recovers orphaned jobs as `PROCESS_INTERRUPTED` only if their OS lock is free.

## Reopen, relink and storage

Recent Projects stores locators, not another project database. Open loads saved
evidence, then checks hashes without rerunning analysis. **View Saved Assessment**
works with stale/missing sources; **Refresh Analysis** is explicit. **Relink** checks
the replacement tree's fingerprint, not its directory name. Changed source removes
current approval overlays, never review history. See [project model](project-model.md).

If the project directory itself moved, use **Open Project** on its new descriptor.
For the same local OS user, this updates a known locator only when its old directory
is missing; a live copy or another user's locator cannot be replaced. Source grants
are cleared on relocation, so explicitly relink before treating evidence as Current.
Creation reserves its locator before SQLite publication. Retrying the same request
after mirror/index failure resumes the same project instead of creating a duplicate.

Windows defaults to `%APPDATA%/FormsLang`; other systems follow
`XDG_CONFIG_HOME/formslang` or `~/.config/formslang`. Existing `FORMSLANG_CONFIG_DIR`
and `FORMSLANG_DATA_DIR` overrides are optional. UI projects live under
`data/projects/<id>`, authenticated ones under `data/orgs/<org>/projects/<id>`.
CLI creation can choose a directory. `.formslang/project.session.db` contains
assessments/jobs/reviews; `config/project-intake/.formslang/locators.json` contains
locators/capabilities only. Back up project storage and configuration. Upgrade must
not delete them; native installer upgrade acceptance remains a release gate.

## Discovered does not mean parsed

Forms discovery recognizes `.xml`, `.fmb`, `.pll`, `.mmb`, `.olb`. Semantic Forms
analysis uses supported Forms2XML; binaries are unsupported representations. A
same-folder `name.xml` or `name_fmb.xml` can represent `name.fmb`. Ambiguous matches
are warned; name matching never proves XML freshness.

Database discovery recognizes `.sql`, `.pks`, `.pkb`, `.prc`, `.fnc`, `.trg`, `.vw`.
The existing parser extracts supported tables, views, sequences and package
specifications/bodies from content. Standalone procedures/functions/triggers and
unknown SQL can remain unsupported. Conflicting qualified objects produce warnings,
not silent last-file-wins behavior.

Traversal excludes generated/build/cache/`.git`/`.formslang` paths and rejects
redirected roots, duplicates and overlaps. Symlink/junction entries are not followed.
Limits: 100,000 traversal entries, depth 64, 256 MiB per source. Preview checks
content, not merely extensions, and can take time on large estates.

Unpaired FMB diagnostics offer instructions and **Convert**. Only explicit
confirmation invokes configured Oracle Forms2XML tooling on staged copies. Original
FMBs remain unchanged. Derived XML is bound to original/output hashes. No Oracle
binary is bundled. Without tooling, supply XML or continue with available source;
see existing conversion-tool setup in Settings.

## Local CLI

```bash
formslang project create ./assessment --name "Order assessment" --forms ./forms --database ./db --target-apex 26.1
formslang project discover ./assessment --json
formslang project analyze ./assessment --json
formslang project status ./assessment --json
formslang project info ./assessment
formslang project summary ./assessment --json
formslang project inventory ./assessment --category findings --risk HIGH --json
formslang project relink ./assessment --root ROOT_ID --path ./moved-forms
formslang project demo ./demo-assessment
formslang project analyze ./demo-assessment
```

Directory or `.formslang/project.json` is accepted. `open` registers/opens a locator;
`status` verifies freshness. JSON is stdout; progress is stderr. Analyze exit codes:
0 completed (possibly warnings), 1 failed, 2 invalid/conflicting request, 130 cancelled.
Control-C requests cooperative cancellation. Authenticated mode rejects the local
project CLI: use an authorized Workbench session/API. Legacy CLI commands remain.

## Authenticated host setup and API

Administrators configure `config/project-source-areas.json`, for example:

```json
{"organizations":{"ORG_ID":{"legacy":"C:/approved/legacy"}}}
```

Only approved areas are browsable; missing config grants no arbitrary filesystem
access. Clients use opaque IDs and relative paths. A descriptor does not authorize
its source paths. Synthetic demo copies use the reserved organization-scoped
`built-in-demo` area; that name cannot be used in host configuration.

The `/api/v2` routes preserve Host/Origin/CSRF, session, MFA, membership and RBAC
checks on every request and repeat authorization in workers. `/api/projects` is
unchanged.

| Route under `/api/v2` | Method / purpose |
|---|---|
| `/projects` | GET authorized recents; POST create |
| `/projects/open`, `/projects/demo` | POST locator open / real demo creation |
| `/source-areas`, `/source-areas/:area/browse` | GET available folders |
| `/source-selections`, `/discovery-preview` | POST explicit local selection / preview |
| `/projects/:id` | GET saved summary and last job |
| `/projects/:id/discover`, `/projects/:id/discovery` | POST discovery / GET results |
| `/projects/:id/analyze` | POST analysis, 202 after job claim |
| `/projects/:id/jobs/:job` | GET scoped progress/status/diagnostics |
| `/projects/:id/jobs/:job/cancel` | POST cancellation |
| `/projects/:id/assessment` | GET saved assessment |
| `/projects/:id/overview` | GET bounded persisted-assessment summary |
| `/projects/:id/inventory` | GET revision-safe filtered/paginated rows |
| `/projects/:id/inventory/:category/:item` | GET bounded authorized detail |
| `/projects/:id/freshness` | POST check job / GET latest check |
| `/projects/:id/relink`, `/projects/:id/convert` | POST explicit source operations |

Mutations carry `expected_revision` and/or `expected_configuration` as appropriate;
stale state returns 409. Discovery lists default to 50, maximum 200 per page. Jobs
are durable, not resumable after process exit. Safe errors omit tracebacks, source
bodies and credentials.

## Privacy and scope

Static project analysis sends no source to AI or a database. Existing AI settings
do not initiate provider calls here. No external telemetry is sent. Assessment
evidence may contain sensitive source: protect storage with OS permissions; no new
project-specific encryption layer is claimed. Credentials stay in the existing
secret-store mechanism, never project metadata.

The demo creates a normal project from compact bundled synthetic files, runs the
unchanged engine and opens the same Overview/Inventory used by other projects. It is
not a frontend simulation or the Modernization Lab benchmark. Phase D review changes,
Phase E generation gates and Phase F reports/delivery packages remain later phases.
Phase C does not claim 2.0 release
acceptance, runtime parity, automatic deployment or completed migration.
