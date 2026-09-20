# FormsLang 2.0 Phase C Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the saved Phase B `ProjectAssessment` into a real Overview and bounded Inventory experience across ProjectService, HTTP, CLI and Workbench without reanalysis.

**Architecture:** Add one pure deterministic `project_projection.py` layer over the current assessment, descriptor and freshness projection. `ProjectService` remains the facade; HTTP, CLI and JavaScript consume the same bounded server-side read models. Use a store-scoped, revision-keyed in-memory LRU only; the scale test is a hard gate against adding persisted projection tables.

**Tech Stack:** Python >=3.10 standard library, SQLite-backed existing ProjectStore, existing HTML/JavaScript Workbench, pytest, Node-driven UI harness, headless Edge browser acceptance.

**Spec:** `docs/superpowers/specs/2026-09-20-formslang-2-phase-c-design.md`

## Global Constraints

- Start at `2c977ebe2d378e86028464399c85cde1335b8018` on `codex/formslang-2-phase-c`.
- Do not change the Phase A/B project model, persistence ownership, analysis engine or assessment publication contract.
- Do not add persisted projection/index tables in Phase C. Stop and report scale evidence before proposing them.
- Do not recompute risk, recommendation, intervention or modernization classification in frontend code.
- Missing/unrecognized risk, recommendation and intervention values remain `UNKNOWN`.
- A modernization unit is a persisted engine finding, not every Blueprint entity.
- Default page size is 50; maximum page size is 200.
- No AI, database connection or reanalysis is allowed for Overview/Inventory reads.
- Do not expose source bodies, credentials, raw exceptions or unrestricted absolute paths in new standard APIs.
- Preserve local/authenticated authorization, Host, Origin, CSRF, session, MFA and organization boundaries.
- Do not implement Phase D review redesign, Phase E generation or Phase F reports/exports.
- Do not change version 1.6.0, create a tag, publish a release or merge the branch.
- Keep all benchmark baseline and ground-truth history byte-identical.

## Review Focus

1. Two authorized stores reuse the same malicious project ID: cache scope must prevent cross-store projection leakage. Task 3 adds this regression.
2. Assessment changes between inventory pages: the second page must return conflict instead of mixing revisions. Tasks 2 and 4 add service and HTTP regressions.
3. Package spec/body and same-named objects from different roots: package totals must group only defensible identities and detailed totals must reconcile. Task 1 pins both cases.
4. Hostile project/source/finding labels: UI and API must render text without executing markup or leaking paths/source bodies. Tasks 4, 6 and 7 cover the boundary.
5. Late Project A responses after switching to Project B: neither Overview nor Inventory state may be overwritten. Task 7 adds an explicit asynchronous race test.

## Execution and verification conventions

- Use test-driven development for every task: write focused RED, run it, implement the smallest correct behavior, run GREEN, then run the neighboring regression set.
- Use `apply_patch` for source edits. Preserve unrelated working-tree changes.
- Python commands below use `python -B`; on this Windows host use the approved Python 3.13 executable if `python` is not on PATH.
- Keep commits coherent and limited to the task named in each section.
- Never record acceptance counts until the final command has actually completed.
- Browser evidence uses only the bundled/synthetic fixtures and loopback requests.

## Shared contracts

Task 1 owns these exact public names in `formslang/project_projection.py`:

```python
@dataclass(frozen=True)
class ProjectionKey:
    store_scope: str
    project_id: str
    analysis_revision: str
    review_revision: int
    target: tuple[str, str, str]
    freshness: str

@dataclass(frozen=True)
class PreparedProjection:
    key: ProjectionKey
    descriptor: dict
    assessment_meta: dict
    overview_data: dict
    rows: dict[str, tuple[dict, ...]]
    details: dict[tuple[str, str], dict]

def prepare_projection(descriptor: dict, assessment: dict, freshness: dict,
                       *, store_scope: str) -> PreparedProjection: ...
def overview(prepared: PreparedProjection) -> dict: ...
def inventory_page(prepared: PreparedProjection, category: str, *, query: str = "",
                   filters: dict | None = None, sort: str = "name",
                   offset: int = 0, limit: int = 50,
                   expected_revision: str | None = None) -> dict: ...
def inventory_detail(prepared: PreparedProjection, category: str, item_id: str,
                     *, expected_revision: str | None = None) -> dict: ...
```

Task 3 owns the cache and facade methods:

```python
class ProjectionCache:
    def __init__(self, max_entries: int = 8): ...
    def get_or_build(self, key: ProjectionKey,
                     factory: Callable[[], PreparedProjection]) -> PreparedProjection: ...
    def clear_project(self, store_scope: str, project_id: str) -> None: ...

class ProjectService:
    def overview(self, *, freshness=None) -> dict | None: ...
    def inventory(self, category: str, *, query="", filters=None, sort="name",
                  offset=0, limit=50, expected_revision=None) -> dict: ...
    def inventory_detail(self, category: str, item_id: str, *,
                         expected_revision=None) -> dict: ...
```

### Task 1: Deterministic projection semantics and reconciliation

**Files:**
- Create: `formslang/project_projection.py`
- Create: `tests/test_project_projection.py`
- Modify: `formslang/project_manifest.py` only to add its hash to engine identity if the new projection module must be fingerprinted; do not change analysis behavior

**Interfaces:**
- Consumes: Phase B assessment dictionaries from `current_assessment`, descriptor dictionaries from `asdict(ProjectDescriptor)`, and freshness dictionaries.
- Produces: `ProjectionKey`, `PreparedProjection`, `prepare_projection()` and `overview()` from Shared contracts.

- [ ] **Step 1: Write failing fixtures and distribution tests**

Create a small assessment factory containing FORM/TRIGGER/PACKAGE_SPEC/
PACKAGE_BODY/TABLE entities, non-CONTAINS edges and findings with known plus missing
values. Assert exact buckets and that modernization total equals finding count:

```python
def test_overview_uses_findings_and_keeps_unknown_visible(assessment_fixture):
    prepared = prepare_projection(DESCRIPTOR, assessment_fixture, CURRENT,
                                  store_scope="store-a")
    result = overview(prepared)
    assert result["inventory"]["modernization_findings"] == 4
    assert result["risk_distribution"] == {
        "CRITICAL": 1, "HIGH": 1, "MEDIUM": 0, "LOW": 0, "UNKNOWN": 2,
    }
    assert result["recommendation_distribution"]["UNKNOWN"] == 1
    assert result["intervention_distribution"]["UNKNOWN"] == 1
```

- [ ] **Step 2: Write failing identity/count reconciliation tests**

Assert a package spec/body named `CUSTOMER_API` groups into one package while their
spec/body counts remain one each. Add two same-name Forms with different stable IDs
and assert both remain. Assert non-CONTAINS edges equal dependency row count.

```python
assert summary["database_packages"] == 1
assert summary["package_specs"] == 1
assert summary["package_bodies"] == 1
assert len(prepared.rows["forms"]) == 2
assert summary["dependencies"] == len(prepared.rows["dependencies"])
```

- [ ] **Step 3: Run the focused tests to establish RED**

Run: `python -B -m pytest -q tests/test_project_projection.py -p no:cacheprovider`

Expected: collection fails because `formslang.project_projection` does not exist.

- [ ] **Step 4: Implement canonical buckets, identities and overview preparation**

Use fixed ordered constants and safe normalizers:

```python
RISK_LEVELS = ("CRITICAL", "HIGH", "MEDIUM", "LOW", "UNKNOWN")
RECOMMENDATIONS = ("PRESERVE", "CONVERT", "REFACTOR", "MOVE_TO_PLSQL_API",
                   "REPLACE_WITH_APEX_NATIVE", "MANUAL_REVIEW", "DROP", "UNKNOWN")
INTERVENTIONS = ("AUTO", "ASSISTED", "MANUAL", "UNKNOWN")

def _bucket(value, allowed):
    normalized = value.strip().upper() if isinstance(value, str) else ""
    return normalized if normalized in allowed else "UNKNOWN"
```

Index entities/findings/edges by their stable IDs. Derive finding risk from its
associated entity's persisted `attributes.risk.level`. Deduplicate findings and
edges by stable ID. Exclude `CONTAINS` from dependency rows. Build all overview
counts from the same row tuples later used by Inventory.

- [ ] **Step 5: Implement package/library/routine/business-rule semantics**

Group package spec/body only by available persisted database identity. Prefer a
qualified persisted name; otherwise use the normalized engine package name and
retain every contributing stable entity ID. Derive libraries from manifest entry
suffixes `.pll`, `.mmb`, `.olb`, keeping supported/unrepresented state separate.
Use engine-emitted routine types only. Treat business rules as candidates when
persisted classification/evidence says `BUSINESS_RULE`; deduplicate by finding ID.

- [ ] **Step 6: Add safety assertions for bounded public overview data**

Walk the serialized overview and assert that injected `source_text`, raw absolute
paths and a sentinel credential do not appear. Assert assessment/source/review
revisions and timestamp appear unchanged.

- [ ] **Step 7: Run GREEN and adjacent assessment regressions**

Run:

```text
python -B -m pytest -q tests/test_project_projection.py tests/test_project_assessment.py tests/test_project_demo.py -p no:cacheprovider
python -B -m ruff check formslang/project_projection.py tests/test_project_projection.py --no-cache
```

Expected: all selected tests pass; Ruff reports no issues.

- [ ] **Step 8: Commit the core projection**

```text
git add formslang/project_projection.py formslang/project_manifest.py tests/test_project_projection.py
git commit -m "feat(project): add deterministic assessment projections"
```

### Task 2: Inventory paging, filters, details and transparent priority

**Files:**
- Modify: `formslang/project_projection.py`
- Modify: `tests/test_project_projection.py`

**Interfaces:**
- Consumes: `PreparedProjection` from Task 1.
- Produces: `inventory_page()` and `inventory_detail()` from Shared contracts, plus priority fields inside `overview()`.

- [ ] **Step 1: Write failing pagination and revision tests**

Create 205 finding rows and assert default 50, maximum 200, stable identity tie
breaks and revision continuity:

```python
first = inventory_page(prepared, "findings")
assert len(first["rows"]) == 50
assert first["total"] == 205
with pytest.raises(RevisionConflict):
    inventory_page(prepared, "findings", offset=50,
                   expected_revision="0" * 64)
with pytest.raises(ProjectError):
    inventory_page(prepared, "findings", limit=201)
```

- [ ] **Step 2: Write failing search/filter/sort tests**

Assert casefolded substring search across module/name/reason, AND-composed risk +
recommendation + module filters, unknown filter values rejected, and every allowed
sort has stable ID as final tie-breaker.

- [ ] **Step 3: Write failing priority reconciliation tests**

Build current APPROVE/MODIFY findings plus PENDING/STALE/REJECT/DEFER findings.
Assert unresolved Critical precedes High, MANUAL/stale/evidence/centrality factors
are returned, the top ID is stable, and summary counts equal the filtered findings
page totals.

```python
queue = inventory_page(prepared, "findings", filters={"priority": "unresolved"})
assert overview(prepared)["priority"]["total"] == queue["total"]
assert queue["rows"][0]["priority_factors"][0] == "UNRESOLVED_CRITICAL"
```

- [ ] **Step 4: Run RED**

Run: `python -B -m pytest -q tests/test_project_projection.py -p no:cacheprovider`

Expected: new paging/filter/detail/priority assertions fail.

- [ ] **Step 5: Implement validated inventory queries**

Add category/filter/sort allowlists. Reject booleans as integers. Apply filters with
AND semantics, search with `casefold()`, stable sort with item ID tie-breaker, then
slice. Return copied safe rows so a caller cannot mutate cached tuples.

- [ ] **Step 6: Implement bounded safe details**

Return identity/type/status/summary plus at most 100 incident dependencies and 100
related findings, with `*_total` fields. Omit source bodies/absolute paths. Unknown
category/item raises `LookupError`; revision mismatch raises `RevisionConflict`.

- [ ] **Step 7: Implement priority factors and overview summary**

Use an explicit risk rank and lexicographic tuple. Store human-readable factor codes
on finding rows; do not calculate a magic numeric score. The stable ID is the last
ordering element. Preserve exact review state in the response.

- [ ] **Step 8: Run GREEN and deterministic replay**

Run the focused file twice and compare canonical JSON from identical inputs:

```text
python -B -m pytest -q tests/test_project_projection.py -p no:cacheprovider
python -B -m pytest -q tests/test_project_projection.py -p no:cacheprovider
```

Expected: both runs pass; deterministic-output assertion matches byte for byte.

- [ ] **Step 9: Commit inventory and priority**

```text
git add formslang/project_projection.py tests/test_project_projection.py
git commit -m "feat(project): add bounded inventory and priority projections"
```

### Task 3: Revision-keyed cache and ProjectService facade

**Files:**
- Modify: `formslang/project_projection.py`
- Modify: `formslang/project_service.py`
- Modify: `tests/test_project_service.py`
- Create: `tests/test_project_projection_cache.py`

**Interfaces:**
- Consumes: Task 1/2 projection functions and existing `current_assessment()`.
- Produces: `ProjectionCache` and ProjectService overview/inventory/detail methods from Shared contracts.

- [ ] **Step 1: Write failing cache-key and eviction tests**

Use a factory counter. Assert a repeated identical key builds once; analysis,
review, target, freshness or store scope changes rebuild; ninth unique key evicts
the least-recently used entry when max is eight.

- [ ] **Step 2: Write the cross-store collision regression**

Construct two stores with the same project ID/revisions but different names and
findings. Share one cache and assert each service returns its own data. This pins
the internal resolved-store scope in `ProjectionKey`.

- [ ] **Step 3: Write service no-reanalysis and reopen tests**

Monkeypatch `blueprint.build`, parser and optional provider entry points to raise.
Call `service.overview()` and `service.inventory()` after reopen and assert saved
projection succeeds. Verify CLI/service freshness remains separate.

- [ ] **Step 4: Run RED**

Run:

```text
python -B -m pytest -q tests/test_project_projection_cache.py tests/test_project_service.py -p no:cacheprovider
```

Expected: missing cache/facade methods fail.

- [ ] **Step 5: Implement a thread-safe bounded LRU**

Use `threading.RLock` plus `collections.OrderedDict`. Do not hold the lock while the
factory performs project I/O; use a double-check on insertion. Cache only immutable
`PreparedProjection` objects and return newly built response dictionaries.

- [ ] **Step 6: Extend ProjectService without broadening authorization**

Accept optional `projection_cache` in the constructor. Each method calls `open()`,
loads the current assessment with supplied freshness, derives store scope from the
authorized resolved project storage identity, prepares/caches and delegates. A
missing assessment returns `None` only for Overview and raises a safe `ProjectError`
for Inventory/detail.

- [ ] **Step 7: Run GREEN and Phase A/B facade regressions**

Run:

```text
python -B -m pytest -q tests/test_project_projection_cache.py tests/test_project_service.py tests/test_project_foundation_acceptance.py tests/test_project_acceptance.py -p no:cacheprovider
```

Expected: all selected tests pass.

- [ ] **Step 8: Commit the facade/cache**

```text
git add formslang/project_projection.py formslang/project_service.py tests/test_project_projection_cache.py tests/test_project_service.py
git commit -m "feat(project): expose cached overview and inventory service"
```

### Task 4: Authorized HTTP Overview and Inventory API

**Files:**
- Modify: `formslang/project_http.py`
- Modify: `tests/test_project_http.py`

**Interfaces:**
- Consumes: ProjectService projection methods from Task 3.
- Produces: GET `/api/v2/projects/:id/overview`, `/inventory`, and `/inventory/:category/:item_id`.

- [ ] **Step 1: Write failing happy-path/no-assessment/state tests**

Use the real project server and storage. Assert Overview returns 200 after analysis,
returns `overview: null` before analysis, retains metrics while stale/incomplete,
and exposes current revision/timestamp/freshness.

- [ ] **Step 2: Write failing pagination/filter/revision tests**

Assert default/maximum pages, search and composed filters. Fetch page one, publish a
new assessment or supply a mismatched revision, then assert page two returns 409
with `PROJECT_CONFLICT` rather than rows.

- [ ] **Step 3: Write failing security tests**

Reuse local/authenticated fixtures to assert owner/member policy, foreign-project
non-disclosure, revoked/MFA-scoped denial and project-scoped detail IDs. Recursively
serialize Overview/detail and assert source body sentinel, credentials and absolute
source root are absent.

- [ ] **Step 4: Run RED**

Run: `python -B -m pytest -q tests/test_project_http.py -p no:cacheprovider`

Expected: new endpoints return 404 before implementation.

- [ ] **Step 5: Parse bounded read query parameters**

Reuse `_page(query)`. Add a helper that accepts only scalar strings for category,
query, sort, revision and allowlisted filters. Reject repeated/structured/unbounded
values with `ProjectError`; do not pass arbitrary query dictionaries to projection
code.

- [ ] **Step 6: Add routes inside the existing guarded project dispatcher**

Open with `VIEW_PROJECT`, obtain `_freshness(service)`, then call service methods.
Return `{"overview": result}` or the bounded page/detail. Inject one shared
`ProjectionCache` into request services from ProjectHTTP so repeated reads benefit
without global cross-Workbench state.

- [ ] **Step 7: Run GREEN plus origin/session regressions**

Run:

```text
python -B -m pytest -q tests/test_project_http.py tests/test_csrf.py tests/test_path_safety.py tests/test_rbac.py tests/test_authstore_schema.py -p no:cacheprovider
```

Expected: new endpoints and existing CSRF/path/RBAC/auth schema boundaries pass.

- [ ] **Step 8: Commit the API**

```text
git add formslang/project_http.py tests/test_project_http.py
git commit -m "feat(api): add project overview and inventory reads"
```

### Task 5: CLI summary/inventory parity

**Files:**
- Modify: `formslang/project_cli.py`
- Modify: `tests/test_cli_project.py`
- Modify: `tests/test_project_http.py`

**Interfaces:**
- Consumes: ProjectService methods from Task 3.
- Produces: `formslang project summary` and `formslang project inventory`.

- [ ] **Step 1: Write failing command/parser tests**

Assert `summary` accepts project and `--json`; `inventory` accepts category, query,
risk, recommendation, intervention, module, review, offset, limit and revision.
Assert invalid category/limit exits with safe code 2.

- [ ] **Step 2: Write failing CLI/API reconciliation test**

For one analyzed project/revision, call HTTP Overview and CLI JSON summary. Remove
only adapter envelopes and assert equality. Repeat for a filtered inventory page.

- [ ] **Step 3: Run RED**

Run:

```text
python -B -m pytest -q tests/test_cli_project.py tests/test_project_http.py -p no:cacheprovider
```

Expected: argparse rejects the new commands.

- [ ] **Step 4: Wire both commands through ProjectService**

Classify `summary` and `inventory` as VIEW_PROJECT operations. Compute freshness
once. Pass inventory options without a second implementation. Preserve JSON stdout
and keep diagnostics/errors on stderr.

- [ ] **Step 5: Run GREEN and legacy CLI regressions**

Run:

```text
python -B -m pytest -q tests/test_cli_project.py tests/test_cli.py tests/test_project_http.py -p no:cacheprovider
```

Expected: new parity tests and existing 1.x commands pass.

- [ ] **Step 6: Commit CLI parity**

```text
git add formslang/project_cli.py tests/test_cli_project.py tests/test_project_http.py
git commit -m "feat(cli): add project summary and inventory commands"
```

### Task 6: Real Workbench Overview

**Files:**
- Modify: `formslang/ui/modernization_project.py`
- Modify: `formslang/ui/modernization_project_style.py`
- Modify: `formslang/ui/nav_layout.py` if the current shell needs project subnavigation registration
- Modify: `tests/test_project_ui_behavior.py`

**Interfaces:**
- Consumes: HTTP Overview and existing freshness/analyze/relink/review/Blueprint routes.
- Produces: project Overview, compact project navigation and filtered Inventory links.

- [ ] **Step 1: Write failing JavaScript behavior tests**

Extend the existing Node harness with a real Overview payload. Assert inventory,
risk/recommendation/intervention including Unknown, priority, coverage, warnings,
timestamp and target render. Assert zero Critical uses explanatory copy rather than
only `0`.

- [ ] **Step 2: Write failing state/XSS/accessibility tests**

Supply `<img src=x onerror=...>` in project/source/finding labels and assert it is
rendered as text. Assert heading hierarchy, navigation labels, status text, button
names, distribution counts and `aria-live` warning/state region exist. Assert no
chart is the sole representation.

- [ ] **Step 3: Run RED**

Run:

```text
python -B -m pytest -q tests/test_project_ui_behavior.py -p no:cacheprovider
```

Expected: Overview-specific assertions fail against the Phase B placeholder.

- [ ] **Step 4: Replace the placeholder with request-safe Overview rendering**

Extend `projectUI` with `projectView`, `overview`, and `inventoryState`. Fetch
`/overview` in `openProject`; capture active project and generation before awaiting.
If either changed, discard the response. Render dynamic values through existing
`esc()` or DOM `textContent`; never concatenate trusted markup from project data.

- [ ] **Step 5: Add compact distributions and project navigation**

Use semantic buttons/links with text counts and CSS bars. Risk/recommendation/
intervention links call one function that switches to `findings` inventory with the
matching filter and returned revision. AUTO help contains the approved warning.
Generate/Reports display honest project-level deferred text; Review/Blueprint call
the current capability with project/finding/filter/revision parameters.

- [ ] **Step 6: Implement state and warning actions**

Show Current/Stale/Incomplete/Missing Source/Unverified as text plus icon. Stale and
missing state retain saved metrics with Refresh/View Saved/Relink actions. No
assessment shows Analyze Project. Do not automatically analyze.

- [ ] **Step 7: Add responsive/accessibility styles**

Use current corporate tokens. Keep cards compact, tables/text readable at tablet
width, stack at small width, preserve focus rings and reduced-motion media rules.

- [ ] **Step 8: Run GREEN and existing UI behavior suites**

Run:

```text
python -B -m pytest -q tests/test_project_ui_behavior.py tests/test_blueprint_ui_behavior.py tests/test_review_ui_behavior.py -p no:cacheprovider
```

Expected: all Node-driven behavior suites pass.

- [ ] **Step 9: Commit Overview UI**

```text
git add formslang/ui/modernization_project.py formslang/ui/modernization_project_style.py formslang/ui/nav_layout.py tests/test_project_ui_behavior.py
git commit -m "feat(workbench): add modernization project overview"
```

### Task 7: Inventory browser, detail, races and focus restoration

**Files:**
- Modify: `formslang/ui/modernization_project.py`
- Modify: `formslang/ui/modernization_project_style.py`
- Modify: `tests/test_project_ui_behavior.py`

**Interfaces:**
- Consumes: Task 4 Inventory/detail API and Task 6 project navigation/state.
- Produces: category tabs, search, filters, paging, detail pane and review deep links.

- [ ] **Step 1: Write failing inventory interaction tests**

Drive tabs Forms/Libraries/Packages/Routines/Views/Tables/Dependencies/Business
Rules/Findings. Assert search and risk+recommendation filters reach the API, paging
carries revision, detail opens, close/back restores the exact filters/page/focus.

- [ ] **Step 2: Write the late-response/project-switch regression**

Hold Project A Overview and Inventory promises, open Project B, then resolve A.
Assert B's name, rows, revision and detail remain unchanged. Also resolve an older
search after a newer query and assert stale rows are discarded.

- [ ] **Step 3: Write the 409 reset regression**

Return 409 on page two. Assert the UI clears rows/page/revision, announces that the
assessment changed, and reloads page one rather than appending mixed data.

- [ ] **Step 4: Run RED**

Run: `python -B -m pytest -q tests/test_project_ui_behavior.py -p no:cacheprovider`

Expected: Inventory functions do not yet exist.

- [ ] **Step 5: Implement one server-backed inventory state machine**

Keep `{category, query, filters, sort, offset, limit, revision, selectedId}` in
`projectUI.inventoryState`. Encode query parameters with `URLSearchParams`. One
request helper captures project/generation/request sequence. Replace rows on query/
filter/category changes; never append across revisions.

- [ ] **Step 6: Render semantic category tables and useful empty states**

Use `<table>`, `<caption>`, scoped `<th>`, accessible filter labels and keyboard
buttons. Columns vary by category using a fixed safe schema; missing evidence shows
“Not observed,” not fabricated zero. No database source explains the cross-layer
limitation.

- [ ] **Step 7: Implement bounded detail and review deep link**

Open detail in the existing dialog/pane pattern, label it, trap/restore focus using
current utilities and show identity/status/metrics/dependencies/findings/risk/
recommendations. Use only API text. Start Priority Review includes project, finding,
filters and analysis revision when opening the existing Blueprint/review workspace.

- [ ] **Step 8: Run GREEN and responsive behavior tests**

Run:

```text
python -B -m pytest -q tests/test_project_ui_behavior.py tests/test_formui.py tests/test_blueprint_ui_behavior.py -p no:cacheprovider
```

Expected: interaction, race, XSS, focus and existing shell tests pass.

- [ ] **Step 9: Commit Inventory UI**

```text
git add formslang/ui/modernization_project.py formslang/ui/modernization_project_style.py tests/test_project_ui_behavior.py
git commit -m "feat(workbench): add project inventory exploration"
```

### Task 8: Demo/reopen browser acceptance and scale gate

**Files:**
- Modify: `tests/test_project_demo.py`
- Create: `tests/test_project_projection_scale.py`
- Create: `examples/verify/project_overview_performance_check.py`
- Modify: `examples/verify/project_browser_check.py`
- Modify: `examples/verify/project_browser_check.mjs`

**Interfaces:**
- Consumes: completed API/CLI/UI projection path.
- Produces: real-stack browser evidence and reproducible read-scale measurements.

- [ ] **Step 1: Write failing demo projection/reopen tests**

Analyze the ordinary bundled demo, assert real Overview has Forms/database counts,
multiple recommendations, AUTO/ASSISTED/MANUAL/UNKNOWN and Critical risk. Close all
services, reopen, trap analysis functions and assert identical saved Overview.
Modify a demo source and assert Stale while saved metrics remain.

- [ ] **Step 2: Build the deterministic large persisted fixture**

Generate an assessment in memory/store with 500 unique FORM entities, at least
5,000 findings and 5,000 non-CONTAINS edges. Use stable synthetic IDs and fixed
timestamp. Assert detailed category totals reconcile before timing.

- [ ] **Step 3: Add measurable projection checks**

The verifier records fixture cardinality, Python/platform, iterations, median and
maximum milliseconds for cold Overview, first inventory page, combined filter,
search, reopen+Overview and warm cache. It writes JSON under caller-supplied output
and exits nonzero on semantic mismatch. It does not enforce an invented marketing
latency.

- [ ] **Step 4: Run the scale gate before any persistence optimization**

Run:

```text
python -B -m pytest -q tests/test_project_projection_scale.py -p no:cacheprovider
python -B examples/verify/project_overview_performance_check.py --output scratch_tmp/phase-c-performance
```

Decision rule: if the bounded in-memory projection is unusably slow or memory-heavy,
stop implementation and report the actual evidence to the owner. Do not add SQLite
projection tables. If acceptable, record measurements and continue.

- [ ] **Step 5: Extend real browser acceptance**

Exercise: open analyzed project; Overview counts; click Critical; filtered findings;
open/close item with focus restoration; switch Inventory category; search package;
open dependency; restart server; same Overview; modify source; Stale visible with
saved metrics. Use real HTTP/service/SQLite/engine, not mocked assessment responses.

- [ ] **Step 6: Run browser and demo GREEN**

Run:

```text
python -B -m pytest -q tests/test_project_demo.py tests/test_project_projection_scale.py -p no:cacheprovider
python -B examples/verify/project_browser_check.py --output scratch_tmp/phase-c-browser
python -B examples/verify/workbench_browser_check.py --output scratch_tmp/phase-c-legacy-browser
```

Expected: all tests/checks pass, no page exceptions, no external requests.

- [ ] **Step 7: Commit acceptance harnesses**

```text
git add tests/test_project_demo.py tests/test_project_projection_scale.py examples/verify/project_overview_performance_check.py examples/verify/project_browser_check.py
git add examples/verify/*.mjs
git commit -m "test(project): add overview scale and browser acceptance"
```

### Task 9: Documentation, independent review and final acceptance

**Files:**
- Modify: `docs/architecture-2.md`
- Modify: `docs/project-workflows.md`
- Modify: `docs/quality-acceptance.md`
- Create: `docs/project-overview.md`
- Modify: implementation/tests only when a material review finding has a RED/GREEN fix

**Interfaces:**
- Consumes: all implemented Phase C behavior and actual command evidence.
- Produces: truthful architecture/semantics/acceptance record and reviewed Phase C branch.

- [ ] **Step 1: Document implemented architecture and exact semantics**

Describe the projection boundary, cache key/invalidation, no-persisted-table decision,
category/count denominators, UNKNOWN handling, priority tuple, source coverage,
revision-safe pagination, API/CLI surface, local-first behavior and Phase D/E/F
deferrals. Do not describe planned behavior as implemented.

- [ ] **Step 2: Run the independent review**

Ask a fresh reviewer to inspect the complete diff specifically for count correctness,
double counting, stale-data mixing, authorization, XSS, pagination/revision races,
priority reconciliation and Phase D/E/F scope creep. Require findings with file/
line evidence and severity. Do not accept stylistic expansion as Phase C scope.

- [ ] **Step 3: Fix material findings test-first**

For each real issue, add one focused failing regression, run it RED, apply the
smallest correction, run it GREEN and rerun the owning task suite. Commit fixes with
a message naming the corrected invariant. If no material findings exist, record
that fact without inventing changes.

- [ ] **Step 4: Verify benchmark immutability and version state**

Compare canonical Git blob hashes for every tracked file under frozen benchmark/
ground-truth paths against base `2c977ebe2d378e86028464399c85cde1335b8018`. Assert `pyproject.toml`, desktop
package metadata and Rust/Tauri declarations still say 1.6.0. Confirm no tag or
release operation occurred.

- [ ] **Step 5: Run focused Phase C verification**

Run:

```text
python -B -m pytest -q tests/test_project_projection.py tests/test_project_projection_cache.py tests/test_project_projection_scale.py tests/test_project_service.py tests/test_project_http.py tests/test_cli_project.py tests/test_project_ui_behavior.py tests/test_project_demo.py -p no:cacheprovider
python -B examples/verify/project_overview_performance_check.py --output scratch_tmp/phase-c-final-performance
```

Expected: all focused tests pass; performance JSON contains every required operation.

- [ ] **Step 6: Run full final verification**

Run:

```text
python -B -m pytest -q -rs -p no:cacheprovider
python -B -m ruff check . --no-cache
python -B examples/verify/project_browser_check.py --output scratch_tmp/phase-c-final-browser
python -B examples/verify/workbench_browser_check.py --output scratch_tmp/phase-c-final-legacy-browser
git diff --check origin/main...HEAD
```

Expected: full Python/Node-driven suite, Ruff, both browser acceptances and whitespace
check pass. Record exact counts, skips, durations, run IDs and screenshot counts.

- [ ] **Step 7: Append truthful quality acceptance**

Record branch/base/head, platform, exact commands and outputs, scale fixture size and
measurements, browser/accessibility scope, hash result, review findings/fixes and
known limitations. State explicitly that browser checks are not a screen-reader
certification and synthetic scale is not 500-Form engine performance.

- [ ] **Step 8: Commit documentation and final accepted state**

```text
git add docs/architecture-2.md docs/project-workflows.md docs/project-overview.md docs/quality-acceptance.md
git add formslang tests examples
git commit -m "docs(project): record Phase C overview acceptance"
```

- [ ] **Step 9: Verify branch scope and stop before integration**

Run:

```text
git status --short
git log --oneline origin/main..HEAD
git diff --stat origin/main...HEAD
git diff --name-only origin/main...HEAD
git tag --points-at HEAD
```

Expected: clean worktree; only Phase C files/commits; no version/release/tag changes.
Return the owner's 26-field Phase C report and ask how to integrate. Do not push,
merge, tag or release without a subsequent explicit instruction.

## Owner requirement coverage audit

- Overview, distributions, automation potential, priority, coverage and warnings:
  Tasks 1, 2, 3, 4 and 6.
- Inventory categories, count reconciliation, search/filter/pagination/detail:
  Tasks 1, 2, 4 and 7.
- Revision safety, stale project mixing, project-switch races and caching: Tasks 2,
  3, 4 and 7.
- CLI/API parity and local-first saved reopen: Tasks 3, 4, 5 and 8.
- Demo, stale/reopen, scale and real browser flow: Task 8.
- Authorization, source boundary, XSS and accessibility: Tasks 4, 6, 7 and 9.
- Documentation, independent review, benchmarks and final evidence: Task 9.
- Phase D/E/F and persisted projection tables remain explicitly deferred throughout.
