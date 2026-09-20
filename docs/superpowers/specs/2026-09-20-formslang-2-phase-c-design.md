# FormsLang 2.0 Phase C: Overview and Inventory

Status: architecture approved by the project owner on 2026-09-20. This document
defines Phase C only. It does not claim implementation or acceptance, and it does
not authorize Phase D review redesign, Phase E project generation, Phase F reports,
a version change, tag, release or merge.

## Intent and verified starting point

Turn the immutable `ProjectAssessment` produced by Phase B into a fast, truthful
corporate assessment experience. A user opening a completed project must understand
its size, risk, modernization direction and highest-priority work within minutes,
without reanalysis, database access or AI.

- Branch: `codex/formslang-2-phase-c`.
- Base: `2c977ebe2d378e86028464399c85cde1335b8018`, merge of Phase B PR #7.
- Included Phase B head: `28b22f2721a56baf32269bf031d65ec0e1a2c6f6`.
- Pre-change Windows / Python 3.13 verification: **1,449 passed, 5 skipped in
  256.97 seconds**.
- Product version remains 1.6.0. No tag or release is created.
- Frozen benchmark and ground-truth history remains immutable.

The owner's Phase C brief is authoritative. Existing Phase A/B project identity,
authorization, persistence, assessment publication, freshness, jobs, CLI, HTTP and
Workbench onboarding remain the foundation and are not redesigned.

## Selected architecture

Phase C adds deterministic read projections over one saved assessment:

```text
ProjectAssessment + ProjectDescriptor + Freshness
                         |
                         v
               ProjectProjection service
                 /       |        \
          Overview   Inventory   Detail/Priority
              |          |             |
              +---- ProjectService ----+
                         |
                 HTTP / CLI / UI
```

The projection layer is pure: it does not parse source, call Blueprint build,
classify findings, contact a database, invoke AI or mutate reviews. It consumes the
assessment returned by `current_assessment`, so existing review overlays and stale
decision semantics stay authoritative.

Create `formslang/project_projection.py` with focused immutable read contracts and
projection functions. Extend `ProjectService` as the facade. HTTP and CLI call the
same service methods. Workbench JavaScript displays server projections and never
recomputes risk, recommendations, intervention or priority.

No persisted projection tables are introduced in Phase C. An in-process bounded
LRU may cache a prepared projection keyed by:

```text
project_id
analysis_revision
review_revision
target profile
freshness status
```

The cache is an optimization only. Its contents are disposable and never a source
of truth. The synthetic scale test is the gate for any future SQLite/indexed
projection proposal. A persisted projection requires separate measurements,
architecture review and a later scoped change; it must not appear opportunistically
inside Phase C.

## Public projection contracts

Use dictionary/JSON contracts consistent with the repository rather than a second
domain model. Internal typed helpers may use frozen dataclasses or named tuples, but
the public service output is bounded JSON-compatible data.

### Overview

`ProjectService.overview(freshness=None) -> dict | None` returns:

```json
{
  "project": {"id": "...", "name": "...", "target": {}},
  "assessment": {
    "status": "Current",
    "completion_state": "COMPLETE",
    "analysis_revision": "...",
    "source_revision": "...",
    "review_revision": 0,
    "assessment_timestamp": "...",
    "freshness": "CURRENT"
  },
  "inventory": {},
  "risk_distribution": {},
  "recommendation_distribution": {},
  "intervention_distribution": {},
  "automation_potential": {},
  "priority": {},
  "source_coverage": {},
  "warnings": [],
  "warning_summary": {"total": 0, "shown": 0, "truncated": false},
  "review_progress": {},
  "analysis_metadata": {}
}
```

There is no source body, absolute source path, credential, raw exception or
unbounded Blueprint payload in this response. If no assessment exists, the service
returns `None`; adapters render an honest Analyze empty state.

### Inventory page

`ProjectService.inventory(category, *, query="", filters=None, sort="name",
offset=0, limit=50, expected_revision=None) -> dict` supports:

```text
forms
libraries
packages
routines
views
tables
dependencies
business_rules
findings
```

The last category is necessary for clickable risk/recommendation/intervention and
priority summaries. It is a modernization-finding list, not a graph-node list.

Every response includes category, applied filters, stable sort, offset, limit,
filtered total, rows, `analysis_revision`, `source_revision`, `review_revision`,
assessment timestamp and freshness. Default limit is 50; maximum is 200. Offset,
limit, category, sort and filter values are validated against explicit allowlists.

The first request may omit `expected_revision`. Clients must carry the returned
analysis revision on subsequent pages and details. A supplied mismatching revision
raises the existing conflict class and becomes HTTP 409. The browser discards its
current page and reloads rather than joining two assessment revisions.

### Inventory detail

`ProjectService.inventory_detail(category, item_id, *,
expected_revision=None) -> dict` returns safe identity, type, status, summary
metrics, bounded dependencies, related findings, risk and recommendations. It does
not return source bodies or unrestricted absolute paths. The detail can expose
evidence identifiers and a review/Blueprint deep link; the existing permissioned
evidence workspace remains responsible for source excerpts.

## Count and identity semantics

All rows use stable engine/source identities, never basename-only keys. Same-name
objects in different roots do not collide.

| Metric | Exact denominator and deduplication |
|---|---|
| Forms modules | Unique Blueprint `FORM` entity IDs; not XML/FMB representations |
| Forms representations | Selected manifest entries representing Forms source |
| Libraries | Manifest entries with PLL/MMB/OLB representations; semantic support is separate |
| Package specs | Unique `PACKAGE_SPEC` entity IDs |
| Package bodies | Unique `PACKAGE_BODY` entity IDs |
| Database packages | Normalized package identity grouped across spec/body, counted once |
| Procedures/functions | Unique routine/subprogram entities the engine actually emitted |
| Views | Unique `VIEW` entity IDs |
| Tables | Unique `TABLE` entity IDs |
| Triggers | Unique `TRIGGER` entity IDs |
| Program units | Unique engine-emitted program-unit/subprogram identities; label documents included types |
| Dependencies | Unique non-`CONTAINS` Blueprint edge IDs |
| Business-rule candidates | Unique findings/entities with observed business-rule evidence; never called verified rules |
| Modernization findings | `len(blueprint.findings)` after stable identity deduplication |

Summary counts and detailed category totals must reconcile for the same revision.
Where the engine has no defensible evidence for a field, omit it or return `null`;
never manufacture zero, a ratio or completeness percentage.

## Distributions and user-facing labels

Risk is read from the finding's associated entity evidence. Allowed buckets are:

```text
CRITICAL, HIGH, MEDIUM, LOW, UNKNOWN
```

Missing, null or unrecognized values map to `UNKNOWN`, never `LOW`.

Recommendation is read from each finding and keeps the machine value. Allowed
values and labels are:

```text
PRESERVE                 Preserve
CONVERT                  Convert
REFACTOR                 Refactor
MOVE_TO_PLSQL_API        Move to PL/SQL API
REPLACE_WITH_APEX_NATIVE Use Native APEX
MANUAL_REVIEW            Human Review
DROP                     Drop
UNKNOWN                  Unresolved
```

Missing or unrecognized values map to `UNKNOWN`.

Intervention is the finding's persisted `execution_verdict`:

```text
AUTO, ASSISTED, MANUAL, UNKNOWN
```

Missing or unrecognized values map to `UNKNOWN`. UI help explicitly states that
AUTO describes the modernization decision category and is not generation readiness
or proof of functional equivalence.

Automation potential is a count and percentage view over those same four buckets.
Its denominator is all modernization findings, including UNKNOWN. The UI says:
"Based on modernization decision categories, not effort or project-duration
estimation." No hours, cost or schedule is inferred.

## Priority Review

Priority is a deterministic stable ordering of findings. It is not an AI score and
does not emit a misleading aggregate percentage. A finding exposes the factors that
placed it in the queue.

The sort tuple, highest priority first, is:

1. unresolved CRITICAL finding;
2. unresolved HIGH finding;
3. other unresolved finding by risk rank;
4. MANUAL intervention;
5. stale review decision;
6. evidenced API bypass, duplicated logic or cross-module impact;
7. dependency centrality from incident non-CONTAINS edges;
8. stable finding/entity identity.

Existing review states are respected. `APPROVE` and `MODIFY` are resolved when
current. `PENDING`, `STALE`, `REJECT`, `DEFER` and unknown states remain unresolved
for prioritization, while the response preserves their exact machine values. No
Phase D status redesign occurs.

The summary includes unresolved Critical, High, Manual and stale counts plus the
first eligible finding ID. `Start Priority Review` deep-links to the existing
project Findings/evidence read path with project ID, finding ID, filters and analysis
revision. The filtered queue count and Overview count must reconcile. This bridge is
read-only: the legacy session Blueprint cannot safely consume a persisted project
assessment, and adding project decision writes belongs to Phase D.

## Source coverage, warnings and state

Coverage uses persisted discovery/manifest/diagnostic evidence:

- Forms: discovered representations, parseable representations and analyzed
  modules remain distinct.
- Database: selected/analyzed/failed source counts are shown, plus defensible object
  counts; no database-completeness percentage is inferred.
- Libraries: discovered representations and those without semantic representation
  are shown as counts.
- Unsupported FMB/library/menu representations remain visible with remediation.

Warnings combine bounded, deduplicated safe diagnostics and derived project-state
warnings. Material examples are failed sources, unsupported representations,
incomplete completion state, stale/missing source and unresolved database
references when actually present. Each warning has code, severity, safe message,
count and a safe Inventory/Diagnostics target. Overview returns no more than 50 rows
and a total/shown/truncated summary. Source bodies and absolute paths are excluded.

Display current project truth prominently:

```text
CURRENT, STALE, INCOMPLETE, MISSING_SOURCE, UNVERIFIED
```

Saved metrics remain visible for stale/missing source, clearly labeled as the last
assessment. Refresh Analysis and View Saved Assessment remain separate actions.
Opening an assessment does not rerun analysis or call AI/database providers.

## Search, filtering and stable ordering

Search is deterministic Unicode casefolded substring matching over safe projected
fields: module, block, item, trigger, package, routine, table, view and finding
names/reasons. It is not semantic search.

Filters compose with AND semantics. Phase C supports risk, recommendation,
intervention, module, source type and review state where applicable. Each category
has an allowlisted stable sort. Every sort ends with stable identity as a tie-breaker.
The UI preserves category, filters, query, sort and page while opening/closing
detail and when navigating back.

## Cache and performance gate

Build a prepared in-memory index once per cache key. A small thread-safe bounded LRU
may be owned by the projection module or ProjectService factory. It is invalidated
naturally when any key revision/status changes and may be cleared explicitly after
writes. It must never hide a store/revision conflict.

Add a synthetic projection fixture containing approximately 500 Forms, thousands
of findings and thousands of dependency edges. Measure on the recorded Windows
environment:

```text
overview projection
inventory first page
combined filter
search
saved project reopen + overview
warm-cache projection
```

Record medians and maxima with fixture cardinality and command. Phase C has no
invented marketing target. If the bounded in-memory design is unusably slow, stop
and report evidence; do not silently introduce SQLite projection tables. Any such
optimization requires owner approval as a new architectural decision.

## HTTP surface and revision safety

Add under the existing guarded `/api/v2/projects/:id` dispatcher:

```text
GET /overview
GET /inventory
GET /inventory/:category/:item_id
```

Inventory query parameters are bounded and validated. `revision` carries the
expected analysis revision. Existing ProjectHTTP reauthorization, Host, Origin,
CSRF/session/MFA and non-disclosing project policy remain in force. Project-scoped
IDs never authorize access. Overview never includes source bodies. Inventory/detail
responses use logical names and stable IDs, not unrestricted absolute paths.

The existing full `/assessment` route remains for compatibility but the new UI does
not use it to build summary metrics. A future API migration can narrow it separately.

## CLI surface

Add:

```text
formslang project summary <project>
formslang project inventory <project> [--category ...] [--query ...]
    [--risk ...] [--recommendation ...] [--intervention ...]
    [--module ...] [--offset ...] [--limit ...] [--revision ...]
```

Both call the same `ProjectService` projection methods as HTTP. Existing JSON output
conventions are retained. For one assessment revision, CLI and HTTP data reconcile
exactly aside from adapter envelopes. No new analysis runs.

## Workbench experience

Extend the existing HTML/JavaScript Workbench; introduce no frontend framework or
chart dependency. After successful analysis and when opening a saved project, show
the real Overview.

Project navigation is compact:

```text
Overview | Inventory | Review | Blueprint | Generate | Reports | Project Settings
```

Overview and Inventory are implemented in Phase C. Review deep-links to the
revision-bound project Findings/evidence read path; the separate legacy Blueprint
remains available but is not treated as a project decision store. Generate and Reports are explicitly marked not yet
available at project level, without mock results. Project Settings retains current
source/refresh/relink actions.

Overview uses compact summary cards, CSS distribution bars and text/count tables.
All charts have an equivalent labeled count representation. Risk, recommendation
and intervention rows are links into filtered Findings inventory. Empty states use
explanatory language. Priority Review is prominent. Source coverage, warnings and
assessment metadata remain visible without overwhelming the executive surface.

Inventory uses category tabs, bounded server pages, composable filters, search and
a focused detail drawer/pane. Details restore keyboard focus to the invoking row.
HTML headings, form labels, table headers, live state, status text and dialog
semantics are accessible; color is never the only signal. Existing reduced-motion
and responsive rules remain. Desktop is primary; tablet remains usable; small
screens stack filters and details.

Every asynchronous request captures project ID, view generation and expected
revision. A late Project A response cannot update Project B. A 409 resets pagination
and reloads current projection. Dynamic user/source content is escaped or assigned
with `textContent`; no trusted HTML is built from project data.

## Demo and offline behavior

The existing compact synthetic Demo Project remains a normal project and real
analysis path. Its existing engine evidence already includes Forms/database
inventory, several recommendations, AUTO/ASSISTED/MANUAL evidence and Critical
risk. Phase C changes only the post-analysis destination to Overview and adds
assertions against real projections; it does not create display-only demo metrics.

Close the server, reopen the demo, and load Overview without analysis. Modify one
source and reopen: saved metrics stay visible with Stale state. The full experience
works offline with no AI, Oracle credentials or live database.

## Security and privacy

- Reauthorize every API request through existing project access boundaries.
- Preserve authenticated organization/member/MFA/action checks and local OS-user
  behavior.
- Never include source bodies in Overview.
- Do not return unrestricted absolute paths from standard projection APIs.
- Escape hostile project/client/source/finding labels; add stored-XSS regressions.
- Bound strings, row counts, filters and detail relationships in HTTP responses.
- Do not log source content; correlation remains project/job/request metadata only.
- Keep recent-project isolation and descriptor distrust unchanged.

## Verification and independent review

Implement test-first in coherent milestones: core semantics; inventory/priority;
service/cache; HTTP; CLI; Overview UI; Inventory UI; demo/browser/scale; docs and
acceptance. Each milestone starts with a failing focused test, becomes green and is
committed separately.

Required tests cover count reconciliation, duplicate package spec/body semantics,
same names across roots, missing/unknown values, priority reconciliation, no source
body/path leakage, local/auth/foreign authorization, no assessment, stale and
incomplete state, search/filter/sort/pagination, revision 409, project-switch races,
XSS, keyboard/focus, demo reopen, stale demo and CLI/HTTP parity.

Run the synthetic scale gate before considering any persistence optimization.
Perform a separate final review focused on count correctness/double counting,
stale-data mixing, authorization, XSS, pagination/revision races and priority
reconciliation. Fix material findings with RED/GREEN evidence.

Final verification includes full pytest, Ruff, Node-driven UI tests, real project
browser acceptance, legacy browser acceptance, `git diff --check`, deterministic
projection checks and canonical hash comparison for frozen benchmark/ground-truth
files. Record exact commands, counts, platform, skips, performance measurements and
known limits in `docs/quality-acceptance.md`.

## Explicitly deferred

Phase C does not include:

- redesigned review queue, review statuses, assignment or bulk decisions (Phase D);
- project-level APEXlang generation, generation gates or validation (Phase E);
- reports, CSV/backlog or modernization package export (Phase F);
- persisted projection/index tables without separate measured approval;
- semantic/vector search;
- portfolio aggregation;
- global readiness score, effort, cost or duration estimates;
- new classification/risk/recommendation logic;
- incremental engine analysis;
- version 2.0 declaration, tag, release or installer publication.

Phase C is complete only when real saved assessment data drives the Overview and
Inventory across service, HTTP, CLI and Workbench, all requested safety and scale
gates pass, and no Phase D/E/F capability is represented as complete.
