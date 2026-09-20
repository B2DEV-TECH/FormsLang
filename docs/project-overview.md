# Project Overview and Inventory semantics

This document specifies the unreleased FormsLang 2.0 Phase C read experience. All
values come from the current persisted `ProjectAssessment`. Reads work offline and
never rerun analysis, call AI or require an Oracle connection.

## One source of truth

`ProjectAssessment` remains authoritative. `project_projection` prepares bounded,
safe read models used identically by `ProjectService`, `/api/v2/projects`, the local
CLI and the existing HTML/JavaScript Workbench. Prepared projections are held only in
a bounded process-local cache. They are not written to SQLite and do not create a
second project model.

The cache identity is:

```text
store scope + project id + analysis revision + review revision
+ target (platform/version/representation) + freshness
```

An application restart rebuilds from the saved assessment. A changed key cannot
reuse another revision. Inventory pages return analysis/source/review revisions,
assessment timestamp and freshness; clients carry the analysis revision to later
pages/details. A mismatch is HTTP 409 and the browser discards its current page,
announces the change and reloads page one.

## Count denominators

| Overview value | Exact meaning |
|---|---|
| Forms Modules | Unique projected Blueprint entities whose type is `FORM`; same names in different roots remain distinct |
| Forms representations | Discovered Forms-related manifest representations; not synonymous with parsed modules |
| PL/SQL Libraries | Manifest `.pll`/library rows; semantic support is reported separately |
| Database Packages | Unique package name within a source-root scope, combining spec/body without merging same-name packages across roots |
| Package specs / bodies | Presence counts on the unique package rows |
| Views / Tables | Unique corresponding Blueprint entities |
| Triggers | Blueprint entities typed `TRIGGER` |
| Program Units | Supported routine/subprogram Blueprint entities |
| Dependencies | Non-`CONTAINS` Blueprint edges; structural containment is deliberately excluded |
| Business Rule Candidates | Findings whose existing classification includes `BUSINESS_RULE`; these are candidates, not human-verified rules |
| Modernization Findings | Engine findings/recommendations; this is the modernization-unit denominator |

Summary counts reconcile with the detailed category totals. Missing evidence is
shown as **Not observed**, not a fabricated zero. Package specs/bodies and unique
packages remain separate concepts.

## Distributions and labels

Risk buckets are exactly `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `UNKNOWN`. An absent or
future value maps to `UNKNOWN`, never `LOW`.

Recommendations retain machine values and use these UI labels:

| Machine value | UI label |
|---|---|
| `PRESERVE` | Preserve |
| `CONVERT` | Convert |
| `REPLACE_WITH_APEX_NATIVE` | Use Native APEX |
| `REFACTOR` | Refactor |
| `MOVE_TO_PLSQL_API` | Move to PL/SQL API |
| `MANUAL_REVIEW` | Human Review |
| `DROP` | Drop |
| unknown/future | Unresolved |

Intervention is separately bucketed as `AUTO`, `ASSISTED`, `MANUAL`, `UNKNOWN`.
Automation Potential is only the percentage distribution of those categories.
It is not an effort, cost, duration or generation-readiness estimate. In particular,
`AUTO` does not mean safe to generate without later eligibility gates.

## Priority order

Priority is a deterministic tuple, not an AI score. Unresolved findings sort by:

1. unresolved Critical;
2. unresolved High;
3. other unresolved findings by risk;
4. manual intervention;
5. stale decision;
6. evidenced API bypass, duplicated logic or cross-module impact;
7. higher dependency centrality;
8. stable finding identity.

Rows expose their factors such as `UNRESOLVED_CRITICAL`, `MANUAL_INTERVENTION`,
`API_BYPASS` and `DEPENDENCY_CENTRALITY`. Overview Priority counts reconcile with
the same filtered Findings list. Phase C links to that list; Phase D owns workflow
changes and bulk decision behavior.

## Source coverage and warnings

Coverage reports observable counts, not an estate-completeness percentage:

- Forms discovered, parseable and analyzed, plus representation count;
- database source files supplied and database inputs analyzed where known;
- libraries discovered and those without a semantic representation.

Diagnostics become bounded safe warnings with remediation. Freshness adds an explicit
warning for `STALE`, `INCOMPLETE`, `MISSING_SOURCE` or `UNVERIFIED`. Saved counts remain
visible but are labelled as prior evidence. Overview never contains source bodies or
unrestricted absolute paths. Inventory/detail are authorized per request and return
only bounded technical fields.

## HTTP and CLI

```text
GET /api/v2/projects/:id/overview
GET /api/v2/projects/:id/inventory?category=forms&offset=0&limit=50
GET /api/v2/projects/:id/inventory/:category/:opaque-item?revision=...

formslang project summary PROJECT --json
formslang project inventory PROJECT --category findings --risk HIGH --json
```

Inventory defaults to 50 rows and rejects limits above 200. Search is normalized
substring matching over safe identity/name/module/reason/relationship fields. Filters
compose with AND semantics. Engine identities are percent-encoded by the client and
decoded only after route segmentation, then resolved within the already-authorized
project and requested revision.

## Scale gate and deferred work

The repeatable verifier uses 500 Forms, 5,000 findings and 5,000 non-structural
dependencies. It records cold Overview, first page, combined filter, search,
reopen+Overview, warm-cache and Python allocation peak without imposing an invented
marketing target. Current evidence supports the in-memory projection architecture;
persisted projection tables remain deferred and require a future failing scale gate.

Phase C does not implement Phase D review redesign, Phase E APEXlang generation or
Phase F reports/CSV/modernization packages. Generation and validation readiness are
shown as not assessed rather than fake percentages.
