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

### UI layer

`formslang/ui/modernization_visual.py` is loaded after the 2.1 project bundle.
The 2.1 screens reach it only through `typeof` guards, so they still run
without it. It defines:

- design tokens (`--fl-*`), mapped onto the corporate theme variables, so light
  and dark themes keep working;
- the presentation mode, stored in `sessionStorage` under
  `formslang.presentationMode`. A blocked storage leaves the mode in memory for
  the page;
- the Overview command center: an assessment record with the mode toggle and
  one primary action, Estate at a Glance, Source Coverage, Architecture
  Attention, the Modernization Journey and the Investigation Board.

The static half of the command center renders from the 2.1 `overview`
payload. The estate, journey and board are filled from `overview/visual`.
That response is keyed by project, analysis revision, review revision and
freshness: a review decision refetches it without re-analysis, and a
presentation-mode switch reuses it. A count the server did not send is shown
as "Not observed", never as zero. If the visual request fails, the saved
Overview stays usable and says why.

### System Map

The System Map moved from the 2.1 project bundle into the visual layer. It
opens on the whole estate by lane. A search result, a drawer or a hotspot
opens the focus view on any node, not only a Form. Coordinates, lanes and
labels come from the server layout. The browser does not compute its own
positions: a response without a layout is placed in lane columns in the order
it arrived.

- Toolbar: find in this view, view mode, focus Form, depth (focus view only),
  lens, relationship filter, layer filter, Fit, Reset, Legend, Refresh and the
  presentation mode.
- Lenses (Architecture, Data access, Shared logic, Hotspots, Review), the
  highlighted lane and the in-map search only dim what they do not select.
  None of them calls the server or hides a returned node.
- Pan and zoom: the canvas scrolls, dragging pans, and there are buttons for
  zoom and for pan in each direction. Only Ctrl or Cmd with the mouse wheel
  zooms; the wheel alone scrolls the page. Smooth panning is off under
  `prefers-reduced-motion`. A minimap shows the visible part.
- Keyboard: every node is a tab stop. Arrow keys move within a column or to
  the nearest node in the next one, and Enter inspects. The relationship table
  lists the same content for keyboard and screen-reader review.
- Inferred relationships are drawn dashed and labelled as candidates.
  Unresolved references are drawn dashed in their own colour. Hotspot links
  and the node badge say "candidate", and the drawer says candidates are not
  verdicts.
- The drawer has six sections: Identity, Architecture, Modernization
  attention, Review, Evidence and Actions. Detail comes from
  `system-map/node`. It is bound to the project, the analysis revision and the
  selected node, so a late answer for another node is discarded. It lists
  findings by name and never shows source text.
- Truncation says what is shown and how to reach the rest, with thousands
  separators: "Showing 100 of 4,812 nodes in this view. Refocus, search or
  filter to explore the rest."

### Module 360, Hotspot Explorer and return context

- `GET …/module-360` takes exactly one of `module`, `node` or `finding` and
  returns one module-level node: identity, fan-in and fan-out, up to 20
  neighbours per direction with their status, composition, risk and
  recommendation distributions, review summary, up to 20 findings and up to
  20 hotspot candidates. It never returns source text. The page has six
  panels (Identity, Modernization attention, Architecture, Review, Evidence,
  Actions) and ends with its boundary note. A late answer for another
  selector is discarded.
- `GET …/hotspots` pages hotspot candidates (at most 50 per page) with
  `type`, `severity` and `module` filters. Every card says why FormsLang
  noticed it (the observed signals) and what it does not prove (the
  uncertainty and the next step). Each card is marked Candidate. The
  modules × type matrix shades cells in three buckets through a `data-level`
  attribute, never an inline style, and a cross-module candidate sits in the
  "Across modules" row. An estate with no candidates says it is not a clean
  bill of health.
- Review detail shows an architecture context line for the finding's module
  (relationships in and out, hotspot candidates, decided findings) with
  links to Module 360 and to the map. If that request fails, the review
  stays usable and says the context is unavailable.
- Cross-navigation keeps a return context of at most 8 steps. Back reopens
  the same map focus, the same review item, the same hotspot filters or the
  same module. Choosing a section in the navigation clears it.
- Search results placed on the map carry a Map button, and Alt+Enter opens
  the map focused on the result.

### Report visuals

The executive and technical reports carry two static inline SVG figures,
built from the saved report snapshot after its literal-named entities were
renamed: the estate by lane (at most 60 modules and 120 relationships,
ordered by observed attention, with the omitted counts in the caption) and
the modules × hotspot-type matrix. The figures contain no script, no link, no
`foreignObject`, no inline style and no URL other than the SVG namespace.
Identifiers are derived from position, every text value is escaped, and the
same snapshot produces the same bytes. Each figure has a `<title>` and a
caption, and the tables that follow list the same content as text. The
figure keeps its own light panel so it reads the same on screen and on paper.

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
| B | Overview command center, Exec/Tech view | done: `formslang/ui/modernization_visual.py` (tokens, mode, command center), `tests/test_visual_ui_behavior.py` (9 cases) |
| C | System Map 2.2 | done: System Map moved into `modernization_visual.py` (estate view, lenses, pan/zoom, minimap, keyboard, six-section drawer), `tests/test_visual_ui_behavior.py` (+12 cases), 2.1 Edge acceptance rerun |
| D | Module 360, Hotspot Explorer, investigation board, review context, cross-navigation | done: `module-360` and `hotspots` routes, UI in `modernization_visual.py`, `tests/test_visual_ui_behavior.py` (+12 cases), estate Edge acceptance 82 of 82 |
| E | Report visuals (static SVG) | done: executive and technical reports, `tests/test_generic_assessment_journey.py::test_report_visuals_are_static_redacted_and_deterministic` (canaries, no script or URL, determinism across reopen) |
| F | Lab walkthrough | not started |
| G | Hardening, Edge acceptance, measurements, docs | not started |

## Measurements

Only measured results are written here.

- Baseline before any change: `python -m pytest -q` on `b54934b` gave 1761
  passed, 5 skipped in 876 s. Environment: Windows 11 Pro 10.0.26200, Python
  3.12.10.
