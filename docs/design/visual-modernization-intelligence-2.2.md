# Visual Modernization Intelligence (2.2) — design record

Status: **in development** on branch `codex/formslang-2.2-visual-intelligence`
(from `main` `b54934b`, FormsLang 2.1.0). This document is kept truthful while
the work proceeds: a section describes what exists in the branch, and anything
not yet built or not yet verified is labelled so.

## Purpose

FormsLang 2.1 already knew the estate: inventory, module-level relationships,
hotspot candidates, investigation groups and human review. 2.2 makes that
knowledge navigable. It adds no new analysis. Every visual is a
**presentation of the saved assessment**; nothing a visual shows is inferred
by the visual layer itself.

## Baseline (audited before any change)

| Surface | 2.1 state |
|---|---|
| Overview | Panels for inventory, distributions, Start Here, hotspots, coverage and warnings (`renderProjectOverview`). |
| System Map | SVG with four fixed columns and a Form-only focus selector. Server-side node, edge and selector budgets are reported in `truncation`. No pan, zoom, estate view or lens. |
| Search | Ctrl+K dialog, bound to project, revision and request. Forms open the map; other results open Inventory. |
| Reports | Deterministic HTML/Markdown/JSON/CSV with no visuals. Literal-named integration targets are renamed for delivery. |
| Projection | `_architecture_graph` was rebuilt on every map request. |

## Architecture

- `formslang/project_visualization.py` is a **pure** projection module. It does
  no parsing, no I/O and no persistence. It provides:
  - semantic lanes: Application, Shared logic and state, Data, Integration and
    unresolved;
  - Technical and Executive labels for node types and relationships;
  - epistemic statuses;
  - deterministic layouts;
  - Overview aggregates;
  - static SVG for reports.
- `project_projection.py` memoizes the module-level architecture graph on the
  `PreparedProjection`. That object is keyed by project, analysis revision,
  review revision, target and freshness, so a review decision yields a new
  projection. Review overlays refresh without re-analysis, and the graph
  itself is never mutated.
- Coordinates are computed per response and never persisted.

### API additions (all read-only, all bounded)

| Route | Purpose |
|---|---|
| `GET …/system-map?view=estate` | Whole-estate lane view. Without `view` (or with `view=focus`) the 2.1 focus behaviour is unchanged. When the view exceeds its node budget, nodes are admitted in observed-attention order: hotspot candidates, highest finding risk, relationship count, then name and identity. That is a viewing order, not an importance score. |
| `GET …/system-map?focus=<id or name>` | The focus can be any module-level node, not only a Form. `focus=form:…` keeps working. |
| `GET …/system-map/node?id=` | Drawer detail: relationship counts by direction and type, up to 20 hotspot candidates and up to 20 findings (name, risk, recommendation, intervention, review state). No source text. |
| `GET …/overview/visual` | Command-center aggregates: estate by lane, relationship counts, modules × hotspot-type matrix (at most 15 modules), investigation board (at most 8 modules per group) and the journey stages. The 2.1 `overview` payload is unchanged, so CLI `project summary` still equals it. |

Every System Map response also carries `layout` (positions, columns, size,
`cycle_nodes`) and `labels` (Technical and Executive names). Nodes add
`presentation_type`, `lane`, `status`, `unresolved`, `dependency_count` and
`review_summary`. Edges add `presentation_label`, `status` and `evidence_refs`.
Every 2.1 field is kept. Search results add `map_focus`: the module-level
node a result folds into, when there is one.

### Layout (deterministic, no force simulation)

- **Estate mode.** Nodes go into the four semantic lanes. Lane order within a
  lane comes from two barycenter sweeps: left-to-right, then right-to-left,
  using exact rational means of neighbour rows. Ties break on case-folded
  name, then identity. A lane taller than `MAX_ROWS` wraps into
  sub-columns, so large estates grow wide rather than tall.
- **Focus mode.** The focus sits in the centre column. Nodes reached by
  following relationships forward from the focus go to the right (column =
  forward distance). Nodes that reach the focus go to the left (column =
  backward distance). A node reachable both ways sits on the side with the
  shorter distance, the right on a tie, and is flagged `cycle`. Nodes
  connected only indirectly take the side of the neighbour that reached them.
  Each column is ordered by barycenter against the column nearer the focus,
  then by name and identity.
- The same input produces the same output independent of `PYTHONHASHSEED`
  and input order. Tests cover this.

### Epistemic statuses

`OBSERVED` (a relationship the engine recorded as fact), `CANDIDATE` (an
inferred relationship or a hotspot candidate), `PROPOSED` (engine
recommendation), `DECIDED` (human decision) and `UNRESOLVED` (a reference not
found in the supplied sources). Each has its own text label and its own
visual treatment (line style, badge), not only a colour.

### Terminology

The Executive view renames presentation labels only; identities, counts and
evidence are identical.

| Technical | Executive |
|---|---|
| FORM | Application module |
| PACKAGE | Shared PL/SQL service |
| TABLE / VIEW | Data object |
| CALLS | Uses service |
| READS | Reads data |
| WRITES | Changes data |
| OPENS_FORM | Opens module |
| SHARES_STATE | Shares global state |
| DUPLICATES_LOGIC | Similar logic observed |
| UNRESOLVED | Unresolved reference |

The view mode is remembered for the browser session (`sessionStorage`) and is
never stored in the project database.

## Boundaries (non-negotiable)

- Investigation groups organize review work. They are not migration waves,
  dependency order, effort estimates or readiness claims.
- No health scores, migration percentages, completion dates, ROI, cost,
  schedule, "easy migration" labels or business-criticality claims.
- No domain meaning inferred from names, and no LLM-invented relationships.
  Everything works without an AI provider.
- An observed dependency path is not a business process.
- Exported material (reports, SVG `<title>`, embedded JSON, archive members)
  never carries HOST/URL/connect-string literals. The authorized local UI may
  show them, as in 2.1.
- Source bodies never become globally visible. Existing disclosure rules
  apply in both view modes.

## Implementation log

The log is updated per phase with the commit and what was verified.

| Phase | Scope | State |
|---|---|---|
| A | Visual projection, labels, layout, graph memo, tests | done: `tests/test_project_visualization.py` (19 cases) plus HTTP route coverage |
| B | Overview command center, Exec/Tech view | not started |
| C | System Map 2.2 | not started |
| D | Module 360, Hotspot Explorer, investigation board, review context, cross-navigation | not started |
| E | Report visuals (static SVG) | not started |
| F | Lab walkthrough | not started |
| G | Hardening, Edge acceptance, measurements, docs | not started |

## Measurements

Only measured results are written here.

- Baseline before any change: `python -m pytest -q` on `b54934b` gave 1761
  passed, 5 skipped in 876 s. Environment: Windows 11 Pro 10.0.26200, Python
  3.12.10.
