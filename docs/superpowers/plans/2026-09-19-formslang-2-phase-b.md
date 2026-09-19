# FormsLang 2.0 Phase B Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver create/select/discover/analyze/progress/cancel/reopen through the real Workbench, HTTP and CLI using the Phase A project foundation.

**Architecture:** Extend ProjectService with focused discovery, analysis, jobs and
freshness collaborators. ProjectStore remains the only project state database;
existing parsers and Blueprint own reasoning. UI/API/CLI are adapters, not engines.

**Tech Stack:** Python >=3.10, stdlib/SQLite, existing HTML/JavaScript, Tauri 2,
pytest, Ruff, existing Node/CDP browser infrastructure.

**Spec:** `docs/superpowers/specs/2026-09-19-formslang-2-phase-b-design.md`

**Status:** approved by the project owner on 2026-09-19. Execution method: native.
No product code changed while preparing this plan.

## Global Constraints

- Base: `3f4d6914225a3a1df9e151d93e8669811261d753`; branch `codex/formslang-2-phase-b`.
- Product version remains **1.6.0**; no tag, release, automatic push or merge.
- No second project model, persistence backend, ownership registry or frontend framework.
- Keep Python >=3.10, stdlib runtime and existing HTML/JS/Tauri.
- Descriptor paths alone never grant access; source type is not authorization.
- Static mode needs no account locally, AI, DB credentials or Oracle installation.
- Human history is never rewritten as engine evidence.
- Frozen benchmark history stays unchanged; all new fixtures are synthetic/public-safe.
- No Phase C dashboard, generation, reporting, portfolio or incremental cache work.
- A backend-only milestone is not Phase B complete. All owner P0 items are gates.

## Review Focus

- Same-byte-size edit with restored mtime, or edit-and-restore during parsing: staged-byte evidence and hashes must agree (Tasks 2/5/6).
- A slow live CLI process while desktop opens the project: no timeout/PID-only orphan recovery (Task 4).
- Creation/relink succeeds in SQLite but mirror/registry write fails: recover without data loss or cross-user registration (Tasks 3/7).
- Discovery or job reply arrives after UI project switch, or auth membership is revoked mid-job: old context cannot mutate the new project or publish (Tasks 7/8/10).
- Packaged engine lacks Python fingerprint resources or demo files: desktop must not fail where source checkout succeeds (Task 11).

## Execution and verification conventions

Read spec and Phase A modules before Task 1. Do not reconstruct the architecture
or modify existing benchmark classifiers. Each task below has its own RED/GREEN
cycle and coherent commit; run listed commands from repository root. On this host
use `C:/Users/geefa/AppData/Local/Programs/Python/Python313/python.exe -B` as Python.
`rg` is unavailable here; use git ls-files / Select-String. Use apply_patch for edits.
Do not stage CLAUDE.md, docs/assessment, scratch evidence or local credentials.

After writing each listed test, run it before product implementation and observe
the intended failure. After GREEN run relevant regressions and `ruff check` on
changed Python files, then `git diff --check` before explicit-path staging/commit.
The final complete suite is Task 12; intermediate subsets do not replace it.

## Shared contracts (defined by the owning tasks below)

Use dictionaries at transport boundaries and frozen dataclasses for ingestion;
keep existing ProjectDescriptor, SourceCandidate, ManifestEntry and ProjectAccess.
Do not extend descriptor with live job state.

```python
# project_discovery.py (Task 1)
@dataclass(frozen=True)
class SourceDiagnostic:
    source_id: str
    relative_path: str
    stage: str
    error_code: str
    safe_message: str
    remediation: str

@dataclass(frozen=True)
class DiscoveredSource:
    candidate: SourceCandidate
    lifecycle: str
    support: str
    original_binary_id: str | None = None
    freshness_verified: bool = False

@dataclass(frozen=True)
class DiscoveryResult:
    entries: tuple[DiscoveredSource, ...]
    diagnostics: tuple[SourceDiagnostic, ...]
    inventory: dict

# project_jobs.py (Task 4)
class AnalysisCancelled(ProjectError): ...
# checkpoint: Callable[[], None]; raises AnalysisCancelled when cancelled
# progress: Callable[[dict], None]; no source bodies or unbounded error strings

# project_store.py (Task 3)
# configuration_revision is a persisted monotonically increasing integer.
# expected_revision always means current analysis revision (str | None).
# expected_configuration always means configuration_revision (int).
```

Inventory counts: candidate files, parseable XML, paired/unpaired FMB, unsupported
representations, parsed Forms, DB object counts by kind, unique package names,
failures and exclusions. Keep files distinct from objects and spec/body counts.
Manifest availability statuses remain Phase A's vocabulary. PARSED/FAILED belong
to discovery/run data, not an incompatible ManifestEntry.status change.

## Task 1: Authorized source discovery and bounded preview

**Files:** create `formslang/project_discovery.py`,
`tests/test_project_discovery.py`; extend `tests/conftest.py` with `project_sources`
(temporary `forms` and `database` folders, real `sample_xml` copied as orders.xml,
and a synthetic CREATE TABLE source). Modify `project_service.py` only for facade
delegation after the pure contract works.

**Interfaces:** `discover_sources(access: ProjectAccess, descriptor: ProjectDescriptor,
*, checkpoint: Callable[[], None], progress: Callable[[dict], None],
preview: bool = True) -> DiscoveryResult`. Pure traversal must also be reusable by
freshness with preview=False (no parser calls). Resolve authority before traversal.

- [ ] Write paired FMB preview regression, then run the new test file (RED):

```python
def test_pair_prefers_xml_without_claiming_binary_freshness(tmp_path, sample_xml):
    root = tmp_path / 'forms'
    root.mkdir()
    (root / 'orders.fmb').write_bytes(b'synthetic-not-an-oracle-binary')
    (root / 'orders_fmb.xml').write_bytes(sample_xml.read_bytes())
    access = local_project_access(tmp_path / 'project', approved_roots=(root,))
    descriptor = ProjectDescriptor(id='a'*32, name='Orders',
        source_roots=(SourceRoot('forms', 'forms', str(root)),))
    result = discover_sources(access, descriptor, checkpoint=lambda: None,
                              progress=lambda event: None)
    chosen = [e for e in result.entries if e.candidate.selected]
    assert len(chosen) == 1
    assert chosen[0].candidate.representation == 'xml'
    assert chosen[0].original_binary_id
    assert not chosen[0].freshness_verified
```

- [ ] Implement deterministic os.scandir traversal, lstat/reparse/containment
checks, sorted entries, root overlap rejection, physical identity deduplication,
size limits and traversal depth/file-count bounds with diagnostics when exceeded.
Do not silently return a complete inventory after a traversal limit/error.

```python
FORM_EXTENSIONS = frozenset({'.xml', '.fmb', '.pll', '.mmb', '.olb'})
DB_EXTENSIONS = frozenset({'.sql', '.pks', '.pkb', '.prc', '.fnc', '.trg', '.vw'})
# Each iteration: checkpoint(), verify authorized containment, then inspect.
# Pair only within root+directory; ambiguity is a diagnostic, not guessed pairing.
```

- [ ] Add parameterized tests for every extension, unsupported XML root, malformed
XML, PKS/PKB content, unknown SQL, binary-only and ambiguous pairs; duplicate/overlap
roots; same basename in distinct roots; hardlink alias; omitted output/.git/build/
.formslang; explicit safe benchmark-output root; permission errors; symlink escape,
loop and real Windows junction using Phase A test pattern. No platform skip for
junctions on supported NTFS. A cancelled traversal must stop before reading next file.
- [ ] GREEN: `python -m pytest -q tests/test_project_discovery.py tests/test_project_manifest.py`.
- [ ] Commit: `feat(project): discover authorized sources and disclose representation support`.

## Task 2: Staged exact-byte parsing and conflict-safe DB composition

**Files:** create `formslang/project_sources.py`, `tests/test_project_sources.py`.
Reuse parser.py, database.py and Phase A manifest without changing classifier logic.

**Interfaces:** `stage_sources(access, descriptor, discovery, *, checkpoint)`, a
context manager yielding `StagedSources(manifest, paths)` where paths maps source ID
to temporary Path; `parse_staged(descriptor, discovery, staged, *, checkpoint,
progress) -> ParsedSources(modules, source_keys, database, diagnostics, inventory)`.
Define these frozen dataclasses in project_sources; manifest is tuple[ManifestEntry,
...], database is existing DatabaseProject, and modules are existing FormModule.

- [ ] RED test exact-byte preservation:

```python
def test_parser_uses_staged_bytes(project_sources):
    access, descriptor, xml = project_sources
    discovery = discover_sources(access, descriptor, checkpoint=lambda: None,
                                 progress=lambda e: None, preview=False)
    original = xml.read_bytes()
    with stage_sources(access, descriptor, discovery, checkpoint=lambda: None) as staged:
        xml.write_text('<broken>', encoding='utf-8')
        parsed = parse_staged(descriptor, discovery, staged,
                              checkpoint=lambda: None, progress=lambda e: None)
        assert len(parsed.modules) == 1
        assert next(p for p in staged.paths.values() if p.suffix == '.xml').read_bytes() == original
```

- [ ] Implement bounded copy + digest equality before parse. Missing/changed/
unreadable input is a structured failure, not a raw exception. Stage under validated
project run storage and clean only the owned staging directory. Normalize module
source_path and all nested database source_file/files to root-ID/relative names.
Do not persist temporary paths. Invoke existing parse_xml/parse_database_file.

```python
# For each object family use grouped definitions, then omit conflicts:
conflicts = {key for key, definitions in grouped.items() if len(definitions) > 1}
# No merged.<family>.update(per_file.<family>) before duplicate detection.
```

- [ ] Tests: three valid XML + malformed + DB; zero usable source; DB duplicate
names across files/schema ambiguity; spec+body allowed; .vw parsed by content;
standalone procedure/trigger disclosed unsupported; same-content separate module
locations disclosed; huge input blocked; errors contain no absolute path/source body.
Test relocated/staged runs yield identical normalized Blueprint content.
- [ ] GREEN: `python -m pytest -q tests/test_project_sources.py tests/test_project_discovery.py`.
- [ ] Commit: `feat(project): stage exact source bytes and compose database evidence safely`.

## Task 3: Additive project run storage and configuration CAS

**Files:** extend `project_store.py`, `project_assessment.py`; create
`tests/test_project_phase_b_store.py`. Keep worker logic out of storage.

**Interfaces:** ProjectStore gets `configuration_revision() -> int`,
`replace_roots(roots, *, expected_configuration: int) -> ProjectDescriptor`,
`record_discovery(result: DiscoveryResult, *, run_id: str) -> None`,
`discovery(run_id: str | None, *, offset=0, limit=50) -> dict`.
Add job/run tables in existing SCHEMA. `save_assessment` remains backward-compatible
and supports internal optional `job_id`, `owner_token`, `expected_configuration`.
Publication and successful job terminal state share one transaction.

- [ ] RED migration test creates a Phase A project, publishes assessment/review,
drops only new Phase B tables/columns in the synthetic fixture to represent old
schema, then opens twice. Assert assessment/review bytes and IDs unchanged.
Keep an inline Phase A CREATE TABLE statement in the test rather than a binary DB.

```python
def test_relink_cas_does_not_overwrite_newer_config(project_store):
    store = project_store
    revision = store.configuration_revision()
    roots = (SourceRoot('forms', 'forms', '../new-source'),)
    store.replace_roots(roots, expected_configuration=revision)
    with pytest.raises(RevisionConflict):
        store.replace_roots((), expected_configuration=revision)
    assert store.descriptor().source_roots == roots
```

Define project_store fixture locally with existing ProjectStore.create and close
in finally. It is a storage test; source authorization is the service's gate.
- [ ] Implement idempotent migrations, append-only discovery/run rows, bounded
pagination (1..200, nonnegative offset), atomic configuration counter/mirror update.
Extend assessment validation for optional inventory/diagnostics/completion fields
without rejecting existing Phase A envelopes or changing revision semantics.
- [ ] Test rollback/mirror failure, identical assessment repeat retains timestamp,
different payload same revision rejection, pagination, failed parse => Incomplete,
and malformed diagnostics/completion mismatch rejected before insertion.
- [ ] GREEN: `python -m pytest -q tests/test_project_phase_b_store.py tests/test_project_store.py tests/test_project_assessment.py tests/test_project_migration.py`.
- [ ] Commit: `feat(project): persist discovery runs and revision-safe project configuration`.

## Task 4: Durable jobs, OS ownership and cancellation fencing

**Files:** create `project_jobs.py`, `project_lock.py`, `tests/test_project_jobs.py`;
extend storage job transaction methods in project_store.py.

**Interfaces:** `project_worker_lock(root: Path)` context manager (nonblocking
exclusive; ProjectBusy on contention); `ProjectJobManager(access, authorize)` where
authorize is a no-argument callable returning freshly verified ProjectAccess.
Methods `claim(operation, *, expected_revision, expected_configuration) -> JobLease`,
`get(job_id) -> dict`, `cancel(job_id) -> dict`, `recover() -> list[str]`.
JobLease context owns lock and worker connection, exposes `job_id`, `owner_token`,
`store`, `checkpoint()`, `progress(event)` and `finish(status, safe_failure=None)`.
Keep a claimed lease alive while transitioning queued to running; no unlocked
enqueue window that recovery could mistake for a dead worker.

- [ ] RED test safe cancellation before publication:

```python
def test_cancel_keeps_last_assessment(job_manager, saved_assessment):
    before = saved_assessment['analysis_revision']
    with job_manager.claim('ANALYZE', expected_revision=before,
                           expected_configuration=0) as lease:
        job_manager.cancel(lease.job_id)
        with pytest.raises(AnalysisCancelled):
            lease.checkpoint()
    assert job_manager.get(lease.job_id)['status'] == 'CANCELLED'
    assert ProjectStore.open(job_manager.access.root).load_assessment()['analysis_revision'] == before
```

Fixtures create/close real project stores; ensure final test closes its observer
(use try/finally around the last read). Do not rely on GC for Windows file cleanup.
- [ ] Implement platform locks: msvcrt.locking one owned byte on Windows;
fcntl.flock on POSIX, plus per-root in-process lock. Hold file handles through
terminal commit. Lock paths use Phase A containment, never follow redirected storage.
Store owner UUID/fence plus PID for diagnostics only; never use PID as authority.
- [ ] SQL claim/recovery and publication use BEGIN IMMEDIATE; validate fence,
configuration/revision and cancellation inside publish. Heartbeat only reports
activity. Recovery needs actual OS lock acquisition then transactional recheck.
- [ ] Multiprocessing tests: one active owner, a second reader/recovery doesn't
cancel it; forced worker exit permits recovery; fabricated live PID doesn't prevent
safe lock-based recovery; fabricated dead PID doesn't revoke an actually held lock;
cancel/commit race, old fence rejected, locked DB, duplicate cancel, terminal cancel,
connection-per-worker and active analysis blocks relink. Synchronize with Events,
not arbitrary sleeps. Safe job reads verify project/job ownership.
- [ ] GREEN: `python -m pytest -q tests/test_project_jobs.py tests/test_project_foundation_acceptance.py`.
- [ ] Commit: `feat(project): add durable cancellable jobs with fenced publication`.

## Task 5: One project analysis orchestrator and deterministic result

**Files:** create `project_analysis.py`, `tests/test_project_analysis.py`; extend
project_service.py, project_manifest.py (identity modules), project_assessment.py.

**Interfaces:** `analyze_project(access, *, expected_revision, expected_configuration,
authorize, progress=None, cancellation=None) -> dict` claims lease and returns
terminal job projection including analysis_revision/completion_state. Cancellation
is Callable[[], bool] or None. ProjectService constructor gains optional `authorize`
callback (local default rechecks local mode; authenticated writes require callback).
`service.analyze(...)` delegates only; `service.discover()` persists a discovery run;
`service.job(job_id)` and `service.cancel(job_id)` delegate to manager.

- [ ] RED reproducibility/zero-config test:

```python
def test_analysis_is_offline_and_repeatable(project_service, monkeypatch):
    def forbidden(*a, **k):
        raise AssertionError('external provider/tool must not be initialized')
    monkeypatch.setattr(ai, 'provider_from_env', forbidden)
    monkeypatch.setattr(oracle, 'detect_toolchain', forbidden)
    first = project_service.analyze(expected_revision=None, expected_configuration=0)
    saved = project_service.assessment()
    second = project_service.analyze(expected_revision=first['analysis_revision'],
                                     expected_configuration=0)
    assert second['analysis_revision'] == first['analysis_revision']
    assert project_service.assessment()['analyzed_at'] == saved['analyzed_at']
```

Define project_service fixture using project_sources, local_project_access and
ProjectService.create; always close it. Use actual sample XML and DB parsers.
- [ ] Implement discovery -> staging -> parse -> blueprint.build -> binding ->
rediscovery/hash -> fenced publication. Pass stable source_keys, normalized DB
provenance and sanitized failures. No speculative fine-grained progress inside
Blueprint. Persist measured phase times with job metadata, outside assessment.

```python
payload = blueprint.build(parsed.modules, title=descriptor.name,
    source_keys=parsed.source_keys, database_sources=parsed.database,
    failures=[asdict(d) for d in parsed.diagnostics])
# binder wraps this payload; it does not recompute risk/recommendations.
```

- [ ] Add tests for partial failures, all-unsupported failure, FMB paired/unpaired,
review invalidation, duplicate object gap, new/deleted/changed files during run,
same-size edit and restored timestamp, and edit/restore between staging and parse.
The last case must analyze staged original bytes, never mixed bytes. Cancellation
at each emitted phase preserves previous pointer. Reauthorization failure before
publication yields safe failure, unchanged pointer. Test two service processes.
- [ ] GREEN: `python -m pytest -q tests/test_project_analysis.py tests/test_project_jobs.py tests/test_project_assessment.py`.
- [ ] Commit: `feat(project): orchestrate deterministic estate analysis through one service`.

## Task 6: Freshness and authorized relink without reanalysis

**Files:** create `project_freshness.py`, `tests/test_project_freshness.py`; extend
project_service.py and project_assessment.py read projection only.

**Interfaces:** `check_freshness(access, descriptor, assessment, *, checkpoint) -> dict`
returns status/reasons/source_revision/checked_at. `service.freshness() -> dict` and
`service.relink(root_id, path, *, expected_configuration) -> dict` (descriptor and
freshness). `service.assessment()` still returns saved result without source scans;
optional freshness projection suppresses stale approval overlays, not history.

- [ ] RED test metadata cannot stand in for content:

```python
def test_same_size_and_mtime_change_is_stale(project_service, project_sources):
    xml = project_sources[2]
    project_service.analyze(expected_revision=None, expected_configuration=0)
    stat = xml.stat()
    raw = xml.read_bytes()
    changed = raw.replace(b'DEMO_ORDER', b'DEMO_OTHER', 1)
    assert len(changed) == len(raw) and changed != raw
    xml.write_bytes(changed)
    os.utime(xml, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    assert project_service.freshness()['status'] == 'STALE'
```

- [ ] Implement preview=False discovery plus hashes; no parser/AI/tool calls.
Match candidate additions/deletions and all relevant manifest fields/options, not
only saved paths. Missing roots -> MISSING_SOURCE; access/check failure -> UNVERIFIED;
material incomplete assessment remains INCOMPLETE when unchanged; changed engine
has explicit reason. Unknown is never displayed as Current.
- [ ] Relink validates server-approved roots, retains root IDs, obtains worker lock,
updates CAS configuration transaction, repairs mirror, then fingerprints replacement.
Test moved same-content tree Current, different same-name tree Stale, deleted root,
escaped relink, active job conflict, legacy assessment with no new fields, engine
change, saved timestamp/history unchanged and sources never parsed during reopen.
- [ ] GREEN: `python -m pytest -q tests/test_project_freshness.py tests/test_project_service.py`.
- [ ] Commit: `feat(project): verify source freshness and relink without losing saved evidence`.

## Task 7: Intake, recent locators, authorized source areas and conversion

**Files:** create `project_intake.py`, `project_conversion.py`,
`tests/test_project_intake.py`, `tests/test_project_conversion.py`; extend projects.py,
authstore.py and project_service.py minimally for trusted creation with supplied ID.

**Interfaces:** `ProjectIntake(data_dir, config_dir, *, identity=None)` identity is
server-side session identity, never raw client roles. Methods `select_source(path,
kind) -> dict` (local only), `browse(area_id, relative='') -> dict`,
`preview(selections) -> DiscoveryResult`, `create(name, selections, *, description='',
client_label='', destination=None) -> dict`, `open_locator(locator) -> dict`,
`list_recent() -> list[dict]`, `access(project_id, action) -> ProjectAccess`.
Selection DTO is `{root_id,kind,area_id,relative_path}`. Local selection returns an
opaque capability scoped to OS user; auth areas are host-configured per org.
Add `convert_selected(access, source_id, *, expected_configuration, confirmed: bool)
-> dict` using the existing converter and project job machinery.

- [ ] RED intake isolation test:

```python
def test_descriptor_does_not_grant_source_authority(tmp_path):
    intake = ProjectIntake(tmp_path/'data', tmp_path/'config')
    with pytest.raises(PermissionError):
        intake.create('Unsafe', [{'root_id':'f', 'kind':'forms',
            'area_id':'unissued', 'relative_path':'../../private'}])
    assert intake.list_recent() == []
```

- [ ] Implement local locator/capability JSON metadata with atomic write and
cross-process metadata lock (same lock primitive, separate path); no assessment
copies. Authorization rechecks exact identity/path per use. Open unknown descriptor
allows saved metadata inspection but requires source selection to grant reading.
- [ ] AuthStore narrow managed-project registration accepts server UUID already
used by descriptor, checks fresh membership, managed path and exists-before-visible.
Use a host-owned initialization marker for resumable failure before registration;
never claim cross-database atomicity. Retry verifies marker creator/org and existing
descriptor rather than reusing another user's directory. Existing IDs/migration
remain supported through registry resolution. Audit create/relink/conversion.
- [ ] Host source-area configuration at config_dir/project-source-areas.json maps
org IDs to opaque area IDs/absolute host roots; never exposed by settings save.
No configured area gives actionable refusal. Tests include revoked membership,
viewer write denial, other org, source-area redirection, case/path alias, recents
leak, interrupted registry/mirror write and concurrent locator updates.
- [ ] Explicit conversion: confirmed flag required, source selected by ID not raw
path, fresh authorization, temporary copy through oracle.convert_module. Persist
derived-source provenance in existing project DB, validate resulting FormModule,
and select generated XML explicitly outside recursive discovery. Include derived
content/tool identity in intake revision. Conversion failure retains prior selection.
Test original bytes unchanged, absent tool guidance, timeout/cancel and output
containment; mock converter only for orchestration tests, never claim Oracle validation.
- [ ] GREEN: `python -m pytest -q tests/test_project_intake.py tests/test_project_conversion.py tests/test_tenant_isolation.py tests/test_project_service.py`.
- [ ] Commit: `feat(project): add authorized intake recents and explicit staged conversion`.

## Task 8: Versioned HTTP adapter and asynchronous jobs

**Files:** create `project_http.py`, `tests/test_project_http.py`; modify workbench.py
only at constructor/route delegation and shutdown; use current auth guards.

**Interfaces:** `ProjectHTTP(workbench)` with `dispatch(method, path, query, body,
auth) -> tuple[int, dict]`; request builds fresh intake/access/service, closes them.
Background runner accepts only immutable project ID/identity/preconditions and
re-resolves authority; no request SQLite connection crosses threads.

- [ ] RED HTTP happy-path test (fixture uses real Handler/ThreadingHTTPServer like
test_workbench.py, isolated config/data and project_sources):

```python
def test_analysis_is_accepted_then_persisted(project_server):
    base, client, source_selection = project_server
    created = client.post('/api/v2/projects', {
        'name':'Orders', 'sources':[source_selection]})
    assert created.status == 201
    pid = created.json['project']['id']
    job = client.post(f'/api/v2/projects/{pid}/analyze', {
        'expected_revision':None, 'expected_configuration':0})
    assert job.status == 202
    result = client.wait_job(pid, job.json['job_id'])
    assert result['status'] in {'COMPLETED', 'COMPLETED_WITH_WARNINGS'}
    assert client.get(f'/api/v2/projects/{pid}/assessment').json['assessment']
```

Define the client helper in this test file with real urllib requests, status/body,
bounded wait and terminal-state handling; not a mocked service/transport.
- [ ] Implement spec's ten project routes, GET collection, plus these exact helpers:
`GET /api/v2/source-areas`, `POST /api/v2/source-selections` (local path selection),
`GET /api/v2/source-areas/:area_id/browse?relative=...`,
`POST /api/v2/discovery-preview`, `POST /api/v2/projects/open`,
`POST /api/v2/projects/demo`, `POST /:id/convert`, `POST /:id/freshness`,
`GET /:id/freshness` (last check). Preview returns inventory plus paginated entries
and diagnostics; preview requests repeat selected authorized roots, never raw trust.
Open takes locator only in local mode; auth resolves registry ID.
- [ ] Safe projections: GET /:id returns metadata, summary, configuration_revision,
last job and freshness; assessment route returns saved projection without blocking
on rehash. Freshness runs asynchronously with same owned-job conventions and no
assessment publication. Origin/JSON/CSRF/MFA gates precede every mutation, including
helper routes. Local v2 also explicitly rejects a provided foreign Origin.
- [ ] Errors map invalid input 400, session 401, role 403, foreign/missing 404,
revision/busy 409, analysis 202; unknown server errors are sanitized correlation ID.
Test all routes, pagination bounds, malformed JSON, foreign Host/Origin, missing
CSRF, MFA-only session, revoked membership, foreign job IDs, absolute-path absence
in authenticated responses, saved assessment immediate, A/B simultaneous requests.
- [ ] GREEN: `python -m pytest -q tests/test_project_http.py tests/test_workbench.py tests/test_workbench_mfa.py tests/test_tenant_isolation.py`.
- [ ] Commit: `feat(api): expose project onboarding and jobs through authorized v2 routes`.

## Task 9: First-class project CLI on the same service

**Files:** create `project_cli.py`, `tests/test_cli_project.py`; modify cli.py to
call `add_project_parser(subparsers)` in build_parser, no second pipeline.

**Interfaces/commands:** `project create DEST --name NAME [--forms PATH] [--database
PATH] [--supporting PATH] [--target-apex 26.1] [--json]`; repeatable source flags.
`project discover|analyze|status|info|open PROJECT [--json]` accepts project directory
or .formslang/project.json. `project relink PROJECT --root ID --path PATH --json`.
CLI uses local explicit user authority; in auth mode fail closed with API-session
guidance, never mint an unauthenticated authority. Existing commands unchanged.

- [ ] RED test through existing `cli.main`, not direct service only:

```python
def test_create_analyze_status_json(tmp_path, sample_xml, capsys):
    destination = tmp_path/'project'
    assert main(['project','create',str(destination),'--name','Orders',
                 '--forms',str(sample_xml.parent),'--json']) == 0
    assert json.loads(capsys.readouterr().out)['project']['target_version'] == '26.1'
    assert main(['project','analyze',str(destination),'--json']) == 0
    first = json.loads(capsys.readouterr().out)
    assert first['analysis_revision']
    assert main(['project','status',str(destination),'--json']) == 0
    assert json.loads(capsys.readouterr().out)['assessment']['analysis_revision'] == first['analysis_revision']
```

- [ ] Implement strict stdout JSON, progress stderr, safe errors and SIGINT flag
passed to same service cancellation. Exit 0 successful/with warnings, 1 failed,
2 invalid/conflict, 130 cancelled. `open` registers locator and prints summary;
it does not launch a browser unexpectedly. Status reports freshness/last job/gaps.
- [ ] Test API/CLI revision parity using identical logical roots/options, malformed
args, missing folders, auth-mode refusal, Ctrl-C cooperative cancellation (subprocess
when platform supports, direct handler test otherwise with explicit skip evidence),
no provider/database setup and legacy CLI parser regression.
- [ ] GREEN: `python -m pytest -q tests/test_cli_project.py tests/test_cli_export.py tests/test_cli_apex.py tests/test_cli_auth.py`.
- [ ] Commit: `feat(cli): add project create discover analyze and status workflows`.

## Task 10: Real Workbench onboarding, progress, reopen and relink

**Files:** create ui/modernization_project.py, ui/modernization_project_style.py,
tests/test_project_ui_behavior.py; modify ui/__init__.py and ui/shell.py narrowly.
Use existing api(), esc(), corporate styles, modal focus and context guards.

**Interfaces:** JS `projectUI` state contains view, draft, activeId, generation,
jobId and timer; `openProject(id)`, `newProject()`, `previewSources()`,
`startProjectAnalysis()`, `pollProjectJob()`, `relinkProjectRoot()` call v2 only.
DOM IDs prefix `project-`; four step headings use focusable h2. No engine imports.

- [ ] RED JS tests follow existing Node-in-pytest style: invalid/blank name inline;
step validation prevents Analyze; pending source preview then navigation discards
old response; active A job reply cannot update B. Core guard:

```javascript
const generation = projectUI.generation;
const projectId = projectUI.activeId;
const result = await api(`/api/v2/projects/${projectId}`);
if (generation !== projectUI.generation || projectId !== projectUI.activeId) return;
renderProjectSummary(result);
```

- [ ] Implement landing + existing-session escape hatch; four steps, persistent
in-app draft, authorized folder picker, source details paging, optional target
settings disclosures and final local-static summary. Target options read backend
TargetProfile; saved AI configuration never initiates project calls automatically.
- [ ] Analyze enqueues once, displays real progress/inventory/elapsed diagnostics,
Cancel and terminal summary. Open shows saved result before freshness check; stale
has Refresh/View Saved, missing root Relink. Recents retrieve actual persisted counts.
Avoid whole-tree DOM rendering. No invented risks, hours or Phase C navigation promises.
- [ ] Accessible controls: label/description/error associations, focus first invalid
field or next step heading, aria-live polite status (not every timer tick), keyboard
cancel/details/picker, no color-only state, reduced-motion and existing small-width
layout. API errors clear in-flight state and provide retry/remediation.
- [ ] Test draft preservation, HTML injection escaping, switched project writes
retain captured ID/preconditions, stale 409 refresh path, cancel terminal race,
pagination, unavailable auth roots and theme/keyboard/no-source empty state.
- [ ] GREEN: `python -m pytest -q tests/test_project_ui_behavior.py tests/test_blueprint_ui_behavior.py tests/test_review_ui_behavior.py`.
- [ ] Commit: `feat(workbench): deliver four-step project onboarding and saved assessment flow`.

## Task 11: Real demo and packaged-engine parity

**Files:** add `formslang/demo/modernization/{forms,database}` synthetic sources and
README; create `tests/test_project_demo.py`; extend project_intake.py demo method,
pyproject.toml package-data and packaging/formslang-engine.spec fingerprint resources;
add `examples/verify/project_engine_check.py`.

**Interfaces:** `ProjectIntake.create_demo() -> dict` copies package resources into
normal authorized local or managed-org project source roots, then uses normal
analyze job. No fixture-specific classifier. Packaged check accepts --engine PATH,
creates temporary config/data, invokes project CLI/demo and checks revision/result.

- [ ] RED demo integration test:

```python
def test_demo_runs_normal_pipeline(demo_intake):
    created = demo_intake.create_demo()
    service = ProjectService(demo_intake.access(created['project']['id'], rbac.RUN_CONVERSION))
    try:
        result = service.analyze(expected_revision=None, expected_configuration=0)
        assert result['status'] in {'COMPLETED', 'COMPLETED_WITH_WARNINGS'}
        bp = service.assessment()['blueprint']
        assert bp['findings'] and bp['database']['package_bodies'] >= 1
    finally:
        service.close()
```

- [ ] Author a small coherent example including preserve, native mapping, refactor,
API move, manual and critical control; assert actual taxonomy fields after reading
existing findings schema. If expectation is unsupported, improve generic fixture
realism or report the gap, never tune engine on fixture names. Add rename-invariance
test for classifications. Demo copied into normal sources, not special frontend data.
- [ ] Package required `.py` identity resources with collect_data_files include_py_files
or explicit same-resource list, plus demo data. Test installed wheel resources and
build PyInstaller engine using documented build recipe with unchanged version.
Execute project_engine_check against actual frozen executable; no source-checkout
fallback. If tooling unavailable, report desktop acceptance blocker, not completion.
- [ ] GREEN: `python -m pytest -q tests/test_project_demo.py tests/test_project_manifest.py tests/test_version.py` plus packaged smoke.
- [ ] Commit: `feat(project): bundle a real modernization demo and frozen project resources`.

## Task 12: End-to-end acceptance, review and evidence

**Files:** create examples/verify/project_browser_check.py and its Node/CDP driver,
tests/test_project_acceptance.py; update docs/project-model.md, docs/project-workflows.md,
docs/architecture-2.md, docs/forms-to-apex.md, docs/quality-acceptance.md.
Reuse browser_path/process cleanup/isolation patterns from workbench_browser_check.py.

- [ ] Write full integration acceptance assertions before declaring completion:

```python
# Real service lifecycle; helper creates ordinary project and synthetic sources.
assert before_close['analysis_revision'] == reopened['analysis_revision']
assert before_close['analyzed_at'] == reopened['analyzed_at']
assert before_close['blueprint']['findings'] == reopened['blueprint']['findings']
assert saved_review_history == reopened_review_history
assert modified_sources_freshness['status'] == 'STALE'
```

- [ ] Browser harness starts real empty Workbench, selects temporary folders through
picker UI, verifies preview, defaults, progress and persisted summary. Stops/restarts
server with same temporary data before recent reopen. Exercises malformed source,
stale/relink, cancellation, project switching and demo. CDP controls browser only;
do not replace service responses with fake assessment. Record screenshots/checks
under ignored scratch_tmp with run IDs, failure details and bounded deadlines.
- [ ] Run keyboard/tab/focus/error-label/live-progress/reduced-motion checks on the
new wizard and existing responsive/contrast regression harness. Distinguish scripted
accessibility checks from a manual screen-reader audit, which is not implied.
- [ ] Measure discovery/parsing/reasoning/persistence time for named synthetic input
counts. Record run/platform/input hash and tracemalloc peak where feasible; keep
measurements out of deterministic output and do not extrapolate analyst ROI.
- [ ] Security review: host areas/descriptor trust, junctions, org/job/recents leakage,
revocation, CSRF, safe logs. Concurrency review: live/dead owner, cancellation/CAS,
relink races and staged source changes. Product review: zero-config, error recovery,
first useful summary. Native execution uses one independent final reviewer per
executing-plans; reproduce material findings as failing tests and fix before done.
- [ ] Run final commands and record real counts, not expected estimates:

```text
python -B -m pytest -q -rs -p no:cacheprovider
python -B -m ruff check . --no-cache
python -B examples/verify/workbench_browser_check.py --output scratch_tmp/phase-b-legacy-browser
python -B examples/verify/project_browser_check.py --output scratch_tmp/phase-b-project-browser
git diff --check
```

Full pytest includes existing Node-driven JS tests, Phase A/B, CLI/API and auth
regressions. Missing Node/browser is a blocker, not a silent acceptance skip.
Hash all 24 frozen baseline/ground-truth tracked files against the base; compare
version declarations too. Run deterministic twice on real project pipeline.
Retain logs for packaged engine and browser; record skipped tests with reasons.
- [ ] Docs accurately describe supported/discovered differences, binary conversion,
privacy, host-area setup, interruption/cancellation latency, freshness, local data
paths, API/CLI commands and Phase C boundaries. Stable README must not claim release.
Acceptance record names the tested implementation commit, command/count/platform
and evidence paths; docs-only final commit can refer to its tested parent without
inventing a self-referential final hash.
- [ ] Final commit: `test(project): verify Phase B onboarding analysis and reopen acceptance`.
- [ ] Verify clean tree and return owner's 32-field report. If any P0 missing,
explicitly label Phase B incomplete. If all pass, use finishing-a-development-branch
and ask how to integrate; no automatic merge or external publication.

## Owner requirement coverage audit

| Phase B brief sections | Tasks |
|---|---|
| 1-3 base, foundation, architecture | verified base + all tasks |
| 4-14 pipeline/discovery/FMB/target | 1-5, 7 |
| 15-22 zero-config/wizard/parity/picker | 7-11 |
| 23-33 jobs/leases/cancel/publication | 3-5 |
| 34-42 reopen/freshness/relink/recents | 6-8, 10 |
| 43-44 demo | 11-12 |
| 45-49 API/auth/revisions/pagination | 7-8 |
| 50-53 CLI | 9 |
| 54-62 UI/progress/summary | 10 |
| 63-73 service/storage/identities/determinism | 1-7 |
| 74-81 performance/diagnostics/security | 5, 7-8, 12 |
| 82-101 automated acceptance/accessibility/demo | tests in 1-12 |
| 102-110 docs/reviews/gates/commit/report | 12 |

Self-review: owner P0s retained; no backend-only completion; existing project/schema
contracts preserved; five review-focus cases assigned tests; deferred work limited
to explicitly later phases. Runtime duration and resource ceilings remain safety
limits, not invented performance claims. Implementation must report any discovered
contract change before expanding scope.
