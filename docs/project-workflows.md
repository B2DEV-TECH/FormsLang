# Modernization project workflows — Phase B development

Unreleased 2.0 development, still versioned 1.6.0 until release acceptance. Phase B
adds onboarding and persistent assessment, not the Phase C dashboard or later
project-level generation/review UI.

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
   cancel. The completion summary uses real persisted counts.

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

The demo creates a normal project from compact bundled synthetic files and runs
the unchanged engine, not a frontend simulation or the Modernization Lab benchmark.
Full Overview/inventory visualization, priority-review UI, project generation gates,
reports and delivery packages are later phases. Phase B does not claim 2.0 release
acceptance, runtime parity, automatic deployment or completed migration.
