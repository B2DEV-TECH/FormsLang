# FormsLang 2.0 Phase A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a tested, portable modernization-project foundation that can reopen persisted assessment and safely import 1.x sessions without changing the existing user experience.

**Architecture:** Extend the existing Store and project authorization boundary; introduce small domain, fingerprint, persistence, migration and service modules. Reuse Blueprint analysis and review rather than creating a second engine. SQLite owns state; an allowlisted descriptor is an atomically repaired mirror.

**Tech Stack:** Python >=3.10, standard library, SQLite, pytest, Ruff; existing Tauri/HTML/JavaScript remain unchanged in this phase.

**Spec:** [Approved product architecture](../../formsLang-2-product-architecture.md), especially sections 3, 5, 6, 9, 16, 18 and 20. [Current-state audit](../../formsLang-2-current-state-audit.md) records the starting evidence.

**Status:** Approved for native execution on 2026-09-19. Tasks 1-6 are implemented;
Task 7 acceptance and documentation are implemented, with final verification and
independent branch review in progress. This is Phase A, not a 2.0 release.

## Execution record

| Task | Commit | Focused verification |
|---|---|---|
| 1: model | `ac668d5` | 26 passed |
| 2: fingerprints | `8dff416` | 40 passed, 1 OS symlink skip (includes model) |
| 3: persistence | `3b70ac8` | 54 passed |
| 4: assessment binding | `2bb9b0f` | 138 passed, 1 skipped |
| 5: migration | `0b6b406` | 96 passed, 1 skipped |
| 6: service/access | `33e93d9` | 153 passed, 2 skipped |
| 7: foundation acceptance | this milestone | 2 passed, including two-process publication |

Execution rulings: engine identity also fingerprints assess/depgraph/behavior;
source revision includes intake options while analysis revision includes all options
and the reserved target; assessment publication landed with its validator in Task 4;
exclusive directory reservation plus no-overwrite hardlink publication replaces
POSIX directory rename, which can overwrite an empty destination. Hardlink support
is therefore required for this foundation. Original sessions and benchmark history
are unchanged. The original task checklists below retain the implementation recipe;
the execution record is the completion/evidence index.

## Global Constraints

- Preserve Python >=3.10, stdlib-only runtime, the Tauri shell, offline assets, existing visual tokens, adjustable panes and authentication overlay.
- Static assessment needs no account, AI provider, database credentials, Oracle installation when XML is available, or CLI setup.
- SQLite is authoritative for analysis/review/artifact state; JSON mirrors the current revision for portability.
- No credentials, prompt bodies or source text belong in the descriptor.
- A stale source, engine or relevant target decision invalidates generation and review applicability, not history.
- Architecture approval does not approve PL/SQL.
- No P0 remote/team-server exposure.
- Do not bump versions during architecture work.
- Existing frozen v1/v2/v3 baselines and ground truth stay immutable.
- No source, original session, manually edited export, config or credential-store data may be overwritten during migration.

## Scope and subsequent plans

This is an executable plan for **Phase A**, not a claim to specify all implementation details for A-H before the first interfaces exist. The approved architecture explicitly requires one concrete plan per phase. The delivery sequence below retains the entire P0 scope; later plans will consume the implemented, tested Phase A interfaces.

| Phase | Next deliverable | Existing implementation to reuse | Gate |
|---|---|---|---|
| A, this plan | Project model, revisions, persistence, migration, access-aware service | Store, projects, Blueprint | Tasks 1-7 below |
| B | Discovery, background orchestration, four-step onboarding, demo | parser, database, oracle, Workbench handler, UI shell/projects | Local zero-config analysis, failures/cancel/reopen, project-isolated jobs |
| C | Overview, inventory, bounded search/filter projections | Blueprint graph, risk and strategy evidence | Counts reconcile; unknown and incomplete remain visible |
| D | Priority review, evidence, history, annotations and critical override | Store Blueprint reviews, review UI | Stale/conflicting writes rejected; architectural/code approval remain separate |
| E | Target planning, eligible partial APEXlang generation, validation | apexlayout, apexlang, apeximport | Unsafe pages blocked; stable output; validation bound to hashes |
| F | Executive/technical reports, backlog, delivery package | persisted assessment, report/export utilities | Safe HTML/CSV, executive redaction, deterministic snapshot provenance |
| G | Product E2E, scale, accessibility, documentation and five-persona review | browser/CLI harnesses, desktop packaging | Full product/security suite, measured 100/500-form results, real UI evidence |
| H | 2.0 version, CI and Windows installers, upgrade, release | releasing.md, installer workflows | Exact candidate passes all gates, including 1.6.0 upgrades on NSIS/MSI |

P1 incremental parsing, safe bulk review, richer module assessment/search, portfolio and snapshots must not displace P0. P2 integrations/server/marketplace remain outside these plans. Do not add an empty implementation of a later-phase method to claim coverage.

## Review Focus

1. Two identical module names in different roots must not share task history: Task 2 identity test and Task 5 duplicate import test.
2. A DB-only edit or modernization-rules update must invalidate applicable review without deleting it: Tasks 2 and 4.
3. Power loss between SQLite commit and descriptor replacement must leave a reopenable project: Task 3 fault-injection test.
4. A live WAL-backed legacy session must import committed decisions, not merely the main file's bytes: Task 5 backup test.
5. A descriptor path, symlink/junction or revoked tenant membership must not grant filesystem access: Tasks 1 and 6.

## File map and ownership

Follow the repository's existing flat-module convention. New files are narrow responsibilities, not a replacement framework.

| File | Responsibility |
|---|---|
| `formslang/project_model.py` | Immutable validated descriptor, target, source and assessment contracts; canonical serialization and typed errors |
| `formslang/project_manifest.py` | Root-relative identities, bounded byte fingerprints, source/analysis revisions |
| `formslang/project_store.py` | Project SQL tables, transactions, module links, descriptor mirror; composes existing Store |
| `formslang/project_assessment.py` | Bind an existing Blueprint to complete project provenance; persist/load without reanalysis |
| `formslang/project_migration.py` | Read-only legacy inspection, SQLite backup, verified staged import and provenance |
| `formslang/project_service.py` | Access-aware create/open/import/current-assessment facade; no HTTP or UI logic |
| `formslang/projects.py` | Preserve registry; add modernization-project access resolution |
| `formslang/store.py` | Add keyword-only opt-out of legacy job reconciliation, preserving default behavior |
| `tests/test_project_*.py` | New isolated unit/integration tests specified in each task |
| `docs/project-model.md`, `docs/architecture-2.md` | Implemented Phase A contracts and boundaries, not future-product claims |

All test data use `tmp_path`, `sample_xml` and the existing isolated config/secret fixture. No customer sources or host configuration are used.

## Execution discipline

At execution time, use the worktree skill to establish isolation. Do not discard or move the user's existing changes. Run each red test before product edits, then green tests, then the listed compatibility tests. A failing assertion should establish missing behavior, not an unrelated environment error.

Commands below use `python` for portability. In this workstation's current environment the discovered executable is `C:/Users/geefa/AppData/Local/Programs/Python/Python313/python.exe`; PowerShell invocation uses `&`. Tests on Python 3.10-3.13 and both supported CI operating systems still belong to CI, not an assumption based on the local interpreter.

Use explicit file lists for milestone commits. The code blocks below define contract-level examples and core algorithms; they are not permission to skip the additional named failure tests.

### Task 1: Validated, portable project contracts

**Files:** Create `formslang/project_model.py`, `tests/test_project_model.py`.

**Interfaces:**

```python
# project_model.py: frozen dataclasses; tuples avoid mutable defaults.
@dataclass(frozen=True)
class TargetProfile:
    platform: str = "Oracle APEX"
    version: str = "26.1"
    representation: str = "APEXlang"

@dataclass(frozen=True)
class SourceRoot:
    id: str
    kind: str  # forms | database | supporting
    path: str  # relative to the project root, not .formslang

@dataclass(frozen=True)
class ProjectDescriptor:
    id: str
    name: str
    source_roots: tuple[SourceRoot, ...] = ()
    description: str = ""
    client_label: str = ""
    target: TargetProfile = TargetProfile()
    project_version: str = "formslang-project/1"
    store: str = "project.session.db"
    analysis_revision: str | None = None
    engine_version: str | None = None

class ProjectError(ValueError):
    pass

class RevisionConflict(ProjectError):
    pass

class ProjectBusy(ProjectError):
    pass

def descriptor_to_dict(value: ProjectDescriptor) -> dict: ...
def descriptor_from_dict(payload: dict) -> ProjectDescriptor: ...
def validate_descriptor(value: ProjectDescriptor) -> None: ...
def canonical_json(value: object) -> str: ...
```

The signature notation above specifies interfaces, not empty functions to commit. Serialized target keys are the approved flat `target_platform`, `target_version`, `target_representation`; never serialize an extra competing nested target. Serialization validates too. `canonical_json` uses UTF-8, sorted keys, compact separators and `allow_nan=False`.

- [ ] **Step 1 — write the red tests.** Include this complete round-trip case:

```python
from dataclasses import replace
import pytest
from formslang.project_model import (
    ProjectDescriptor, ProjectError, SourceRoot,
    descriptor_from_dict, descriptor_to_dict,
)

def test_descriptor_round_trip_and_target_defaults():
    project = ProjectDescriptor(
        id="a" * 32, name="Orders",
        source_roots=(SourceRoot("forms", "forms", "../legacy"),),
    )
    payload = descriptor_to_dict(project)
    assert payload["target_version"] == "26.1"
    assert payload["target_representation"] == "APEXlang"
    assert "target" not in payload
    assert descriptor_from_dict(payload) == project
    for bad in ("", " "):
        with pytest.raises(ProjectError):
            descriptor_to_dict(replace(project, name=bad))
    for store in ("../outside.db", "C:/outside.db", "nested/session.db"):
        with pytest.raises(ProjectError):
            descriptor_to_dict(replace(project, store=store))
    with pytest.raises(ProjectError):
        descriptor_from_dict({**payload, "password": "do-not-persist"})
```

Add parametrized tests for future project format, unsupported target, duplicate root IDs, invalid kind, non-string values, embedded NUL and unknown nested keys. Unknown target values remain inspectable as errors, not silently normalized to 26.1. Test Unicode names and relative paths containing spaces.

- [ ] **Step 2 — run** `python -m pytest tests/test_project_model.py -q`. Expected: missing new module before implementation.
- [ ] **Step 3 — implement** the dataclasses and explicit field allowlists. Require project IDs as 32 lowercase hex characters, root IDs as nonempty ASCII letters/digits/underscore/hyphen, name after trimming nonempty, and the exact store basename. Resolve no filesystem paths in this pure module. Descriptor unknown fields fail with a field-name-only error, never a value/secret dump.

```python
def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)

def validate_target(target: TargetProfile) -> None:
    if (target.platform, target.version, target.representation) != (
        "Oracle APEX", "26.1", "APEXlang",
    ):
        raise ProjectError("Unsupported target profile")
```

`validate_target` is a private validation helper within this task, not an external adapter. Limits: descriptor <=1 MiB at the I/O boundary; name <=200 characters, description <=4000, client label <=200, roots <=128. Reject over-limit values rather than truncate identity.

- [ ] **Step 4 — run** the new tests and `python -m ruff check formslang/project_model.py tests/test_project_model.py`.
- [ ] **Step 5 — commit** those two files as `feat(project): define portable project and target contracts`.

### Task 2: Content manifests and complete analysis identity

**Files:** Create `formslang/project_manifest.py`, `tests/test_project_manifest.py`.

**Consumes:** `SourceRoot`, `canonical_json`, `ProjectError` from Task 1.

**Produces:**

```python
@dataclass(frozen=True)
class SourceCandidate:
    root_id: str
    relative_path: str
    representation: str  # xml | binary | database | supporting
    selected: bool = True

@dataclass(frozen=True)
class ManifestEntry:
    source_id: str
    root_id: str
    relative_path: str
    representation: str
    selected: bool
    status: str  # available | missing | unreadable | too_large | changed | blocked
    size_bytes: int | None
    sha256: str | None

def source_id(root_id: str, relative_path: str) -> str: ...
def fingerprint_sources(
    project_root: Path, roots: tuple[SourceRoot, ...],
    candidates: tuple[SourceCandidate, ...], *, max_bytes: int = 268435456,
) -> tuple[ManifestEntry, ...]: ...
def source_revision(entries: tuple[ManifestEntry, ...], options: dict) -> str: ...
def engine_identity() -> dict[str, str]: ...
def analysis_revision(source: str, engines: dict[str, str], options: dict) -> str: ...
```

This task accepts already-discovered candidates. Recursive discovery and representation selection are Phase B; do not introduce a second scanner here. Root authority is checked by Task 6 before these functions are called.

- [ ] **Step 1 — write the red tests**, starting with DB-only changes and relocation:

```python
from formslang.project_manifest import (
    SourceCandidate, fingerprint_sources, source_id, source_revision,
)
from formslang.project_model import SourceRoot

def test_db_bytes_change_revision_but_relocation_does_not(tmp_path):
    roots = (SourceRoot("db", "database", "db"),)
    candidates = (SourceCandidate("db", "api.pkb", "database"),)
    revisions = []
    for dirname in ("one", "two"):
        root = tmp_path / dirname
        (root / "db").mkdir(parents=True)
        (root / "db" / "api.pkb").write_bytes(b"BEGIN NULL; END;")
        revisions.append(source_revision(fingerprint_sources(root, roots, candidates), {}))
    assert revisions[0] == revisions[1]
    (tmp_path / "two/db/api.pkb").write_bytes(b"BEGIN COMMIT; END;")
    changed = fingerprint_sources(tmp_path / "two", roots, candidates)
    assert source_revision(changed, {}) != revisions[0]
    assert source_id("one", "ORDERS.xml") != source_id("two", "ORDERS.xml")
```

Add tests for changed DDL, empty files, ordering independence, changed selection/options, deleted files and a same-size edit preserving mtime. Test modernization.VERSION changes via `monkeypatch`, not a production module edit. Test `../`, absolute paths, Windows drive/UNC syntax, duplicate source IDs, symlink escape and stream-size overflow. On systems without symlink privileges use a clearly skipped OS test plus pure path-containment tests; never report skipped OS behavior as verified.

- [ ] **Step 2 — run** `python -m pytest tests/test_project_manifest.py -q` and confirm the expected red result.
- [ ] **Step 3 — implement** streaming SHA-256 (1 MiB chunks), sorted identities and explicit error entries. Hash raw bytes, including unsupported files; a hash does not imply parse support. Validate lexical relative paths before resolving, then resolved containment under the authorized root, and check file identity/size/mtime around reading. A detected concurrent change emits `changed`; Phase B additionally rechecks before publication. Never put absolute root paths, timestamps or durations into content revision.

```python
def source_id(root_id: str, relative_path: str) -> str:
    normalized = relative_path.replace("\\", "/")
    value = canonical_json([root_id, normalized])
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

def analysis_revision(source: str, engines: dict[str, str], options: dict) -> str:
    payload = {"source": source, "engines": engines, "options": options}
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
```

`engine_identity()` includes existing analysis, lexical, modernization, risk/catalog/Blueprint versions when present and SHA-256 of the installed parser/database/analysis/PLSQL/lexical/rules/risk/modernization/Blueprint module files. Use `importlib.resources.files("formslang")` for byte access, not checkout-relative paths. Frozen packaging must explicitly retain these fingerprint resources in Phase G. Missing resources fail as `ENGINE_IDENTITY_UNAVAILABLE`, not an empty stable version; test with a monkeypatched resource reader. This conservative code digest closes gaps where modules currently lack version constants without bumping published engine versions or changing frozen baseline output.

- [ ] **Step 4 — run** manifest/model tests and Ruff on the four new files.
- [ ] **Step 5 — commit** `feat(project): fingerprint source content and complete engine identity`.

### Task 3: Transactional project storage and repairable descriptor

**Files:** Create `formslang/project_store.py`, `tests/test_project_store.py`; modify `formslang/store.py:Store.__init__` and `tests/test_store.py`.

**Consumes:** Task 1 descriptor and errors; Task 2 manifest entries.

**Produces:** `ProjectStore.create(root: Path, descriptor: ProjectDescriptor) -> ProjectStore`, `ProjectStore.open(root: Path) -> ProjectStore`, `close() -> None`, `descriptor() -> ProjectDescriptor`, `sync_descriptor() -> None`, `save_assessment(assessment: dict, *, expected_revision: str | None) -> None`, `load_assessment() -> dict | None`, `add_module_session(source_id: str, revision: str, relative_store: str, provenance: dict) -> None`, `module_sessions() -> list[dict]`. Expose `session: Store` only to domain adapters, not HTTP clients.

`Store(path, *, reconcile_jobs: bool = True)` preserves old behavior by default; project storage and staged migration use `False`. Neither opening a project nor inspecting a staged copy may mark another process's active job crashed.

- [ ] **Step 1 — write red tests** for durable create/reopen, descriptor mismatch, stale writes and two connections:

```python
import json
from formslang.project_model import ProjectDescriptor
from formslang.project_store import ProjectStore

def test_sqlite_repairs_a_stale_descriptor(tmp_path):
    root = tmp_path / "project"
    saved = ProjectStore.create(root, ProjectDescriptor(id="b" * 32, name="Orders"))
    expected = saved.descriptor()
    saved.close()
    mirror = root / ".formslang/project.json"
    payload = json.loads(mirror.read_text(encoding="utf-8"))
    payload["name"] = "uncommitted edit"
    mirror.write_text(json.dumps(payload), encoding="utf-8")
    reopened = ProjectStore.open(root)
    try:
        assert reopened.descriptor() == expected
        assert json.loads(mirror.read_text(encoding="utf-8"))["name"] == "Orders"
    finally:
        reopened.close()
```

Add fault injection of `os.replace` specifically when publishing `project.json`: after SQL commit, open must recover from missing/stale mirror using the fixed DB basename. Add foreign JSON project-ID mismatch rejection, unsupported descriptor schema, corrupt JSON with valid DB recovery, malformed DB rejection before Store can initialize it, duplicate create rejection without overwriting, and read-only mirror failure as a structured error leaving SQLite intact. Test `Store(..., reconcile_jobs=False)` leaves existing job rows unchanged while the default behavior remains tested.

- [ ] **Step 2 — run** `python -m pytest tests/test_project_store.py tests/test_store.py -q`; confirm new behavior fails and legacy tests still run.
- [ ] **Step 3 — implement** additional project tables through `project_store.py`, using the existing Store connection. Store is the persistence engine, not a second independently opened competing DB.

```sql
CREATE TABLE IF NOT EXISTS modernization_project (
    id INTEGER PRIMARY KEY CHECK(id=1),
    schema_version TEXT NOT NULL,
    descriptor_json TEXT NOT NULL,
    analysis_revision TEXT,
    review_revision INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS project_assessment (
    revision TEXT PRIMARY KEY,
    source_revision TEXT NOT NULL,
    analyzed_at TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS project_module_session (
    source_id TEXT NOT NULL,
    revision TEXT NOT NULL,
    relative_store TEXT NOT NULL UNIQUE,
    provenance_json TEXT NOT NULL,
    PRIMARY KEY(source_id, revision)
);
CREATE TRIGGER IF NOT EXISTS project_blueprint_review_revision
AFTER INSERT ON blueprint_review
BEGIN
    UPDATE modernization_project
    SET review_revision = review_revision + 1 WHERE id = 1;
END;
```

The trigger exists only in project storage, not original module sessions. Add a test with two existing Store review inserts and assert committed review_revision increases twice; rolling back an insert must not increment it. This keeps existing review writers visible to project caches. Phase D extends the same sequence to annotations and target changes.

Use `BEGIN IMMEDIATE` and SQL NULL-safe compare-and-swap on the previous analysis revision. Save assessment, current metadata and `blueprint_snapshot` in one transaction; do not call existing auto-committing Store methods from inside it. Roll back all three on failure. Retain old assessment rows. Limit busy timeout and translate contention to `ProjectBusy`; no infinite retry. Always close worker-owned connections.

Create under a unique staging directory inside the destination parent, validate it, then publish `.formslang` only if absent using a no-replace directory rename. On Windows/POSIX test destination-race behavior; never use a replace operation that can overwrite an existing project's directory. Mirror writes use a temporary file in `.formslang`, flush/fsync, then `os.replace`. Verify resolved containment before opening project DB or module links, regardless of descriptor claims. Only the fixed DB location is authoritative; JSON cannot redirect it.

Opening a missing or syntactically broken mirror can recover from a validated DB. A parseable mirror that requests another store, an unsupported project format or another project ID must fail with remediation rather than silently authorizing or disguising the mismatch. Stale safe metadata/revision fields are repaired from SQLite. Before a future on-disk schema migration, back up the authoritative DB; this phase creates schema /1 and rejects unsupported newer schemas.

- [ ] **Step 4 — run** project storage/model/manifest and all Store tests: `python -m pytest tests/test_project_store.py tests/test_project_model.py tests/test_project_manifest.py tests/test_store.py tests/test_store_analysis.py tests/test_store_compliance.py -q`.
- [ ] **Step 5 — commit** `feat(project): persist project state with atomic revision publication` using only this task's files.

### Task 4: Bind assessment and existing review to project revisions

**Files:** Create `formslang/project_assessment.py`, `tests/test_project_assessment.py`; extend `tests/test_project_store.py`.

**Consumes:** manifest/revision functions, `ProjectStore`, and existing `blueprint.build` output.

**Produces:** `bind_assessment(descriptor: ProjectDescriptor, manifest: tuple[ManifestEntry, ...], blueprint_payload: dict, *, engines: dict[str, str], options: dict, analyzed_at: str, status: str) -> dict`; `current_assessment(store: ProjectStore, *, expected_engines: dict[str, str]) -> dict | None`.

The assessment is a JSON-compatible versioned projection (`project-assessment/1`) with `project_id`, `source_manifest`, `source_revision`, `analysis_revision`, `engine_identity`, `analysis_options`, `target`, `status`, `analyzed_at`, and `blueprint`. Allowed publication status: `Current` or `Incomplete`. `Stale` is a read projection if the saved engines differ; Phase B adds live manifest freshness. It does not classify findings or recompute the engine.

- [ ] **Step 1 — write red tests** using the existing in-memory Forms model:

```python
from formslang import blueprint
from formslang.model import FormModule, Trigger
from formslang.project_assessment import bind_assessment
from formslang.project_manifest import ManifestEntry
from formslang.project_model import ProjectDescriptor

def test_db_only_manifest_edit_changes_finding_revision():
    module = FormModule(name="DEMO", triggers=[
        Trigger("WHEN-BUTTON-PRESSED", "AUDIT_API.save;", "form", ""),
    ])
    payload = blueprint.build([module])
    original_revision = payload["findings"][0]["revision"]
    project = ProjectDescriptor(id="c" * 32, name="Demo")
    assessments = []
    for digest in ("1" * 64, "2" * 64):
        entry = ManifestEntry("d" * 64, "db", "api.pkb", "database",
                              True, "available", 18, digest)
        assessments.append(bind_assessment(
            project, (entry,), payload, engines={"modernization": "v1"},
            options={}, analyzed_at="2026-09-19T12:00:00Z", status="Current",
        ))
    assert assessments[0]["analysis_revision"] != assessments[1]["analysis_revision"]
    assert (assessments[0]["blueprint"]["findings"][0]["revision"] !=
            assessments[1]["blueprint"]["findings"][0]["revision"])
    assert payload["findings"][0]["revision"] == original_revision
```

Add an integration test that publishes the first assessment, calls existing `store.session.review_blueprint` with APPROVE and rationale, publishes the second assessment with the correct expected revision, and checks `store.session.blueprint()` returns STALE plus the preserved history. Repeat for engine-only changes. Assert source revision remains stable when only engine changes. Ensure a review is not represented as conversion approval, input payload remains unmodified and same snapshot serialization is stable. Test current assessment reopen with the engine builder patched to raise: persisted reads must not analyze again.

- [ ] **Step 2 — run** `python -m pytest tests/test_project_assessment.py -q` to establish red tests.
- [ ] **Step 3 — implement** a deep-copy provenance overlay, leaving legacy `blueprint.build` output and existing benchmark protocols unchanged:

```python
bound = copy.deepcopy(blueprint_payload)
bound["source_revision"] = source_rev
bound["project_analysis_revision"] = analysis_rev
for finding in bound["findings"]:
    finding["revision"] = hashlib.sha256(canonical_json([
        "project-finding/1", analysis_rev, finding["revision"],
    ]).encode("utf-8")).hexdigest()
```

Here `source_rev` and `analysis_rev` are computed through Task 2 and target profile is included in analysis options under a reserved server-owned key. Reject conflicting user-supplied reserved keys. Preserve Blueprint engine_version so existing Store compatibility checks still work; the outer complete engine identity governs project freshness. Do not label legacy review snapshots applicable to this stronger new revision automatically. Retain raw legacy snapshots in migration.

`save_assessment` validates schema/project identity, manifest-derived revision and target before publication; a browser can never provide a trusted arbitrary assessment. `current_assessment` overlays current Store review history on a copy, computes stale-engine status and exposes review revision without mutating saved evidence. When the complete outer engine identity differs, mark reviewed findings STALE and remove applicable human_decision/coverage overlays even if legacy Blueprint engine_version still matches; preserve history and engine evidence. Test that condition explicitly. Phase D owns atomic project review mutations; no new approval API is added here.

- [ ] **Step 4 — run** new tests plus `tests/test_blueprint.py`, `tests/test_blueprint_backend.py`, `tests/test_modernization.py` and `tests/test_store.py`.
- [ ] **Step 5 — commit** `feat(project): bind assessments and review applicability to source revisions`.

### Task 5: Non-destructive import of 1.x sessions

**Files:** Create `formslang/project_migration.py`, `tests/test_project_migration.py`.

**Consumes:** `ProjectStore`, `source_id`, `ProjectError`, existing Store with reconciliation disabled.

**Produces:** `import_legacy_session(project: ProjectStore, source: Path, *, source_key: str) -> dict`. Returned keys: `source_id`, `revision`, `relative_store`, `snapshot_sha256`, `already_imported`. `source_key` is an explicit root-relative logical identity, not a module title. Original location and migration version remain internal provenance in SQLite, not executive-facing descriptor fields.

- [ ] **Step 1 — write red tests** including a representative saved conversion decision:

```python
import hashlib
from formslang.convert import build_tasks
from formslang.parser import parse_xml
from formslang.project_migration import import_legacy_session
from formslang.project_model import ProjectDescriptor
from formslang.project_store import ProjectStore
from formslang.store import APPROVED, Store

def test_import_preserves_original_and_decisions(tmp_path, sample_xml):
    original = tmp_path / "legacy.session.db"
    legacy = Store(original)
    legacy.init_session("Orders", str(sample_xml))
    legacy.add_tasks(build_tasks(parse_xml(sample_xml)))
    task_id = legacy.task_ids()[0]
    legacy.set_decision(task_id, APPROVED, code="NULL;", reviewer="Analyst")
    history = legacy.history(task_id)
    legacy.set_setting("apex_checksum_salt", "A" * 64)
    legacy.close()
    before = hashlib.sha256(original.read_bytes()).hexdigest()
    root = tmp_path / "project"
    project = ProjectStore.create(root, ProjectDescriptor(id="e" * 32, name="Orders"))
    try:
        result = import_legacy_session(project, original, source_key="legacy/orders")
        copied = Store(root / ".formslang" / result["relative_store"], reconcile_jobs=False)
        try:
            assert copied.history(task_id) == history
            assert copied.setting("apex_checksum_salt") == "A" * 64
        finally:
            copied.close()
        assert hashlib.sha256(original.read_bytes()).hexdigest() == before
    finally:
        project.close()
```

The example uses the actual `apexlang.SETTING_SALT` key; also seed `apexlang.SETTING_EXPORT_CONFIG` with a valid export configuration and compare real deterministic export bytes. Seed Blueprint reviews, multiple changed conversion decisions, confirmed keys, proposals, test specifications/results and module metadata using their existing test patterns; compare every old table's rows before/after migration, excluding only explicitly documented schema-added defaults.

Test a live source connection in WAL mode with a committed review still in WAL, two equal basenames at different logical source keys, repeated import idempotency, changed source snapshot as a new revision, non-FormsLang SQLite rejection, corrupt DB, missing source, interruption before module-link commit, and a failing migration hook leaving original and project pointer intact. Old sessions lacking newer tables must remain importable if the base session/task identity is valid. Blueprint-only sessions are valid even with no tasks.

- [ ] **Step 2 — run** `python -m pytest tests/test_project_migration.py -q` and establish the expected red failures.
- [ ] **Step 3 — implement** read-only inspection before opening Store on a copy. Require known session table columns, exactly one nonempty session identity and known task or Blueprint structure; `PRAGMA quick_check` must return `ok`. SQLite objects/triggers/views outside the known FormsLang schema fail closed before migrations execute. No extension loading or submitted SQL.

```python
source_uri = source.resolve().as_uri() + "?mode=ro"
with sqlite3.connect(source_uri, uri=True) as original:
    with sqlite3.connect(staged_snapshot) as destination:
        original.backup(destination, pages=256)
```

`staged_snapshot` is an implementation-local unique file inside this project's staging directory. Add a monotonic deadline through the backup progress callback so a locked/live database cannot hang import forever; on expiry return `ProjectBusy` with retry guidance. Do not use `immutable=1` on live WAL input, raw `copy2`, or checkpoint the user's DB.

Keep the pre-migration backup under `.formslang/backups/<snapshot_sha256>.session.db`. Derive idempotency from a canonical digest of the consistent snapshot's table schemas/rows (including history), not an assumption that main-file bytes represent live WAL state. Store the actual snapshot file hash separately. Migrate a second staged copy with reconciliation disabled, compare preserved rows, atomically publish under `modules/<source-id>/<revision>.session.db`, then insert the module link. Unlinked crash remnants are not active project state; recovery may quarantine only task-owned remnants after path validation. Do not promote source-less imports to current project analysis.

Use `source_id("legacy", source_key)` for the import identity; reject absolute/traversing source keys using Task 2 validation. For the snapshot logical digest, order tables by name and rows by declared primary key (otherwise by canonical complete row), retaining SQLite scalar types; encode BLOBs as tagged base64. Do not incorporate backup file layout or observation time. Preserve sqlite_sequence/history IDs where present. Unknown triggers/views fail before copied code can run.

- [ ] **Step 4 — run** migration tests plus `tests/test_migration.py`, `tests/test_path_safety.py`, `tests/test_store.py`, `tests/test_apexlang.py` and `tests/test_settings.py`.
- [ ] **Step 5 — commit** `feat(project): import legacy sessions through verified SQLite snapshots`.

### Task 6: Access-aware project service and compatibility boundary

**Files:** Create `formslang/project_service.py`, `tests/test_project_service.py`; modify `formslang/projects.py`; extend `tests/test_path_safety.py`, `tests/test_tenant_isolation.py`.

**Consumes:** Tasks 1-5, existing authstore/RBAC/project registry.

**Produces:** in `projects.py`, frozen `ProjectAccess(root: Path, actor: str, org_id: str | None, actions: frozenset[str], source_roots: tuple[Path, ...])`; `local_project_access(root: Path, *, approved_roots: tuple[Path, ...]) -> ProjectAccess`; `authorized_project_access(store: AuthStore, project_id: str, *, active_org_id: str, user_id: str, action: str, data_dir: Path, approved_roots: tuple[Path, ...]) -> ProjectAccess`.

In `project_service.py`, `ProjectService(access: ProjectAccess)`, `create(name: str, *, roots: tuple[SourceRoot, ...] = (), description: str = "", client_label: str = "") -> ProjectDescriptor`, `open() -> ProjectDescriptor`, `assessment() -> dict | None`, `import_session(source: Path, *, source_key: str) -> dict`, `close() -> None`. A service instance owns one ProjectStore connection and cannot switch projects. `create` assigns UUID hex internally. No new HTTP/CLI commands in this phase.

- [ ] **Step 1 — write red service tests**:

```python
from formslang.projects import local_project_access
from formslang.project_service import ProjectService

def test_local_project_create_reopen_without_provider_or_auth(tmp_path, monkeypatch):
    monkeypatch.setenv("FORMSLANG_AUTH", "0")
    root = tmp_path / "project"
    access = local_project_access(root, approved_roots=(tmp_path,))
    service = ProjectService(access)
    try:
        created = service.create("Orders")
        assert created.target.version == "26.1"
        assert service.assessment() is None
    finally:
        service.close()
    reopened = ProjectService(access)
    try:
        assert reopened.open() == created
    finally:
        reopened.close()
```

Patch provider construction, Oracle tool detection and AuthStore initialization to raise if called by this local test. Add rejection of local access when auth is enabled, unauthorized external source roots, symlink/junction replacement after access creation, empty approved roots with supplied sources, malicious descriptor store path, and mismatched descriptor/authorized registry project roots. Add a two-tenant test using existing `auth_store` fixture: foreign ID is indistinguishable from missing ID, export permission follows existing RBAC, revoked membership cannot create a new access context. Task B handlers must resolve a new authorized context on every request, not cache this object as perpetual authorization.

- [ ] **Step 2 — run** `python -m pytest tests/test_project_service.py -q` and confirm new contract failures.
- [ ] **Step 3 — implement** facade methods by delegating to prior tasks. Local actor comes from OS identity; authenticated actor from the validated auth context. `approved_roots` are host-supplied, never taken from project JSON or request bodies. Recheck resolved containment when opening/creating the DB and on every source import, even after access was created. Keep the existing registry's IDs and external/adopted paths untouched.

```python
def assessment(self) -> dict | None:
    if self._store is None:
        self.open()
    return current_assessment(self._store, expected_engines=engine_identity())
```

In this snippet `_store` is `ProjectStore | None`, initialized by the constructor and set by create/open. `close` closes it and resets to None. A missing descriptor/store raises a project-open error; assessment does not silently create an empty DB. Do not add fake `analyze`, `generate`, `report` or `snapshot` methods: those are delivered in their real phases.

Enforce `ProjectAccess.actions` inside every facade method: create requires `rbac.CREATE_PROJECT`, open/assessment require `rbac.VIEW_PROJECT`, import requires `rbac.ADOPT_PROJECT`; local contexts receive the local operator's action set. Add denied-action tests using a viewer context. Authenticated resolution supports only registry rows already pointing to a validated `.formslang/project.session.db`, with root derived from that registered location, never the descriptor. Legacy registry rows continue through the legacy interface until explicit migration. Authenticated project creation/registration intake is delivered together with the Phase B handlers; no new registration path is exposed in Phase A.

- [ ] **Step 4 — run** all `tests/test_project_*.py`, plus `tests/test_idor.py`, `tests/test_tenant_isolation.py`, `tests/test_path_safety.py`, `tests/test_rbac.py`, `tests/test_workbench.py` and `tests/test_cli_auth.py`.
- [ ] **Step 5 — commit** `feat(project): expose local and authorized project service boundaries`.

### Task 7: Phase A integration acceptance and developer documentation

**Files:** Create `tests/test_project_foundation_acceptance.py`, `docs/project-model.md`, `docs/architecture-2.md`; update this plan's checkboxes/results and `docs/quality-acceptance.md` only with actual new evidence.

**Consumes:** All Phase A public interfaces.

**Produces:** a reproducible foundation acceptance test and implemented-contract documentation, not a 2.0 product/release completion claim.

- [ ] **Step 1 — write the acceptance test** that composes real interfaces rather than mocking persistence:

```python
from formslang import blueprint
from formslang.parser import parse_xml
from formslang.project_assessment import bind_assessment, current_assessment
from formslang.project_manifest import (
    SourceCandidate, engine_identity, fingerprint_sources,
)
from formslang.project_model import ProjectDescriptor, SourceRoot
from formslang.project_store import ProjectStore

def test_foundation_reopen_keeps_assessment_and_architectural_review(tmp_path, sample_xml):
    root = tmp_path / "project"
    forms = root / "forms"
    forms.mkdir(parents=True)
    xml = forms / "orders.xml"
    xml.write_bytes(sample_xml.read_bytes())
    descriptor = ProjectDescriptor(id="f" * 32, name="Orders",
        source_roots=(SourceRoot("forms", "forms", "forms"),))
    manifest = fingerprint_sources(root, descriptor.source_roots,
        (SourceCandidate("forms", "orders.xml", "xml"),))
    payload = blueprint.build([parse_xml(xml)], source_keys=["forms/orders.xml"])
    engines = engine_identity()
    assessment = bind_assessment(descriptor, manifest, payload, engines=engines,
        options={}, analyzed_at="2026-09-19T12:00:00Z", status="Current")
    store = ProjectStore.create(root, descriptor)
    store.save_assessment(assessment, expected_revision=None)
    finding = assessment["blueprint"]["findings"][0]
    store.session.review_blueprint(entity=finding["entity"], revision=finding["revision"],
        action="DEFER", reviewer="Synthetic reviewer", comment="Business owner input required")
    store.close()
    reopened = ProjectStore.open(root)
    try:
        saved = current_assessment(reopened, expected_engines=engines)
        assert saved["analysis_revision"] == assessment["analysis_revision"]
        found = next(f for f in saved["blueprint"]["findings"] if f["entity"] == finding["entity"])
        assert found["review_state"] == "DEFER"
        assert found["review_history"][0]["reviewer"] == "Synthetic reviewer"
    finally:
        reopened.close()
```

- [ ] **Step 2 — run** this test before any integration repair. If already green, it is acceptance of the composed units; do not manufacture a failure. Extend it with source relocation and a second Store reader observing a later committed assessment. Add two-process compare-and-swap contention as a separate test using `multiprocessing` spawn, with finite joins and guaranteed process cleanup.
- [ ] **Step 3 — write developer docs** with actual schemas/signatures, paths, authority rules, current/stale/incomplete meanings, import/recovery procedure, explicit missing-source behavior and remaining phases. Include a runnable Python create/open example from Task 6, and the distinction between baseline engine revision and the stronger project wrapper. README must not advertise the unimplemented wizard or generation workflow.
- [ ] **Step 4 — execute the release-independent Phase A gate**:

```text
python -m pytest -q
python -m ruff check .
python examples/verify/workbench_browser_check.py --output <isolated-evidence-directory>
git diff --check
git diff <implementation-base> -- examples/modernization-lab/benchmark/baselines
```

Choose actual isolated evidence path and base commit before running; record them, command versions and real results. Inspect the existing ground-truth file and compare its hash too. Browser checks protect legacy UI even though no UI change is planned. Do not reuse the audit's 1,134/101 results as new evidence. Run broader benchmark regression only if implementation changes engine classification; never regenerate frozen baselines as a convenience.

- [ ] **Step 5 — self-review** the five Review Focus cases against real tests; inspect the complete diff for secret/path leakage, unwanted schema mutation and hidden compatibility changes. Arrange the independent review prescribed by the selected execution method. Address material findings with regression tests.
- [ ] **Step 6 — commit** `test(project): record foundation acceptance and migration contracts`, listing exact new/changed files. Report Phase A status, tests and limitations; do not bump version, tag, push a release or claim 2.0 complete.

## Self-review of this written plan

- Scope: architectural sections 5/6/9/18 receive executable Phase A tasks; each remaining product section remains allocated to phases B-H, not silently omitted from 2.0.
- Shared interfaces: descriptor flat JSON keys, root-relative path base, fixed DB basename, manifest entries, assessment envelope and facade names are specified once and consumed consistently.
- Persistence: preserve Store as the SQLite engine; no competing JSON state; no auto-commits inside multi-table publication; no accidental job reconciliation during project reads/import.
- Source safety: raw DB bytes and engine modules participate in project revision; old benchmark formats and classifications remain untouched.
- Migration: WAL snapshot, row preservation, checksum salt and rollback are explicit; duplicate module names are not identities.
- Security: local mode does not initialize auth; auth mode does not turn descriptor paths into authority; no HTTP exposure ships before Phase B authorization tests.
- Review: the five failure classes above are assigned to explicit tests, with no claim that these tests have run yet.

## Execution handoff

Recommended execution method: **Native**. These seven tasks have tightly coupled storage/revision interfaces; keeping one implementer through them avoids repeated context transfer. A fresh independent whole-branch review follows implementation. The alternative is task-by-task implementation/review through subagents, with more independent checkpoints and higher context cost.

Owner must review this plan and choose the method before product implementation, per `writing-plans`. This checkpoint does not ask for the product scope again; it approves the concrete storage/migration contract and execution approach.
