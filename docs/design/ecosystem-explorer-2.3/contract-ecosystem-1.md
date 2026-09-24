# `ecosystem/1` — contract for the 2.3 ecosystem explorer

Status: **phase 1 draft, frozen for review.** Nothing in this document is
implemented. It fixes the vocabulary, identities, families, certainty states,
bounds and compatibility rules that phases 2–4 must implement, and it states
which parts rest on facts the 2.2 engine already records and which do not.
Every "2.2 records" statement below is backed by the measured inventory
([`inventory-2.2.json`](inventory-2.2.json), produced by
`examples/verify/ecosystem_inventory.py`) and pinned by
`tests/test_ecosystem_phase1.py`.

The contract is additive. It does not change the Blueprint schema
(`blueprint/1`), the 2.2 System Map API or any saved assessment.

## 1. What a "screen" is

A **screen** is a navigation concept of the product, not a new analysed
entity. The entry point is always a `FORM`. Inside it, a *visual surface* is a
`WINDOW` or `CANVAS` whose placement is known from the source.

- A canvas is shown inside a window **only** when the source declares the link
  (`Canvas.WindowName` or `Window.PrimaryCanvas`). Otherwise the explorer says
  "Canvas sem janela identificada" and chooses no window.
- An item is shown on a canvas/tab **only** when the source declares
  `CanvasName`/`TabPageName` and the target is declared in the same Form.
  Otherwise it is listed under "Componentes sem canvas identificado". The item
  keeps its logical owner (`BLOCK CONTAINS ITEM`); the visual and logical
  trees point to the **same item identity**.
- A screen is never a runtime journey. Nothing in `ecosystem/1` says what the
  operator saw, in which order, or whether a canvas was ever displayed.

## 2. Identities

| Element | Identity in `ecosystem/1` | Source |
|---|---|---|
| Node | The Blueprint entity `id` (e.g. `trigger:…`, `routine_reference:…`), opaque. | 2.2 records it. |
| Edge | The Blueprint edge `id`, opaque. An aggregated edge carries the list of raw edge ids and their real total. | 2.2 records it. |
| Evidence | The Blueprint evidence `id`; its text is disclosed only under the existing source-read policy. | 2.2 records it. |
| `TAB_PAGE` | New in phase 2. Derived with the engine's hashing from Form source key + canvas + tab page name. | **Not recorded in 2.2** (`tab_page_entities` = 0 in every corpus). |

Rules:

1. Ids are not file paths and never contain one. The inventory checks that no
   absolute or Windows path appears in its output.
2. **Homonyms are never merged.** Case C measured three call sites —
   `SALES_OWNER.ORDER_API.SUBMIT`, `BILLING_OWNER.ORDER_API.SUBMIT` and
   `ORDER_API.SUBMIT` — as three distinct `ROUTINE_REFERENCE` ids. The contract
   keeps them apart. It does **not** inherit the 2.2 database-side collapse
   described in [gaps G-SCHEMA-COLLIDE and G-SCHEMA-BODY](gaps-and-capture.md).
3. An id is valid for one `analysis_revision`. A response never mixes
   revisions; a stale `expected_revision` is an explicit conflict.

## 3. Relation record

Every relation the explorer returns has:

| Field | Meaning |
|---|---|
| `id` | Edge id, or aggregate id with `edge_ids[]` and `occurrences` (real total). |
| `from`, `to` | Node ids. `to` may be a reference node whose resolution is unknown. |
| `family` | One of the seven families in §4. |
| `type` | Normalised relation (e.g. `OPENS_FORM`, `CANVAS_IN_WINDOW`, `ITEM_PLACED_ON_CANVAS`). |
| `raw_type` | The Blueprint edge type exactly as saved (e.g. `REFERENCES`). Never rewritten. |
| `level` | Certainty of the **relation**: `OBSERVED` or `INFERRED` (§5). |
| `resolution` | Certainty of the **target**: `RESOLVED`, `UNRESOLVED` or `NOT_APPLICABLE` (§5). |
| `evidence_ids` | Evidence ids. A relation without usable evidence is never shown as `OBSERVED`. |
| `analysis_revision`, `engine_version` | Of the snapshot that produced it. |

## 4. Families, mapped from the 2.2 edge types

The 2.2 Blueprint has 19 edge types across the four corpora. Each maps to one
family; the mapping depends only on the saved edge (type, level, source and
target entity types, evidence text), never on re-reading the source.

| Family | 2.2 raw edges | Notes |
|---|---|---|
| Composition and visual placement | `CONTAINS` (FACT); `ITEM REFERENCES CANVAS` when typed (below). Phase 2 adds `CANVAS_IN_WINDOW`, `WINDOW_PRIMARY_CANVAS`, `CANVAS_CONTAINS_TAB_PAGE`, `ITEM_ON_TAB_PAGE`. | Tree connectors. Never counted as a call or data dependency. |
| Navigation | `OPENS_FORM`, `NAVIGATES_TO`, `USES_LOV` | A literal target links to a supplied Form; a missing one ends in a `FORM_REFERENCE` (unresolved). |
| Code | `CALLS`, `USES_PROGRAM_UNIT`, `INVOKES_BUILTIN`, `DECLARES`, `IMPLEMENTS`, `REFERENCES` (INFERENCE) from a routine reference to its package reference | Call site, symbol and confirmed body are different claims. |
| Data | `READS`, `WRITES`, `REFERENCES` to sequence/table/bind/item references, `RELATES` (master-detail) | `REFERENCES` never becomes a write. |
| State and transaction | `COMMITS`, `EXECUTES_QUERY`, `REFERENCES` to `GLOBAL_REFERENCE` | Lexical/Forms evidence; no claim about effective order or isolation. |
| Integration | `DEPENDS_ON` to `INTEGRATION_POINT`, `RUNS`, `USES` to library/menu/alert/record group/timer | External targets may have no analysable body. Labels are protected. |
| Interpretive signal | `DUPLICATES_LOGIC` (INFERENCE), `CONTAINS` (INFERENCE) to `BUSINESS_RULE`, hotspot candidates, findings | A separate layer, linked to the facts that support it. |

**Typing `ITEM REFERENCES CANVAS`.** In 2.2 the raw type `REFERENCES` carries
both visual placement and data/bind references (the visual fixture has both).
The projection shows it as `ITEM_PLACED_ON_CANVAS` only when **all three**
hold: the source entity is an `ITEM`, the target entity is a `CANVAS`, and the
first evidence text starts with `CanvasName: `. The saved edge is not
rewritten and old snapshots are typed the same way. Every other `REFERENCES`
keeps its data or state family.

## 5. Certainty

| State | Comes from | May say | May not say |
|---|---|---|---|
| `OBSERVED` | Edge `level = FACT` | "The source contains this declaration/call/reference." | "Execution always visits it." |
| `INFERRED` / `CANDIDATE` | Edge `level = INFERENCE`; hotspot `classification = CANDIDATE` | "A deterministic rule inferred a possible link; here are its premises." | "The architecture is proven." |
| `UNRESOLVED` | Target is a `*_REFERENCE` with `resolution = SYMBOLIC_REFERENCE`, or no `resolution` and `missing` | "This source names a target that could not be resolved in the supplied sources." | "The target does not exist." |
| `PROPOSED` | Engine recommendations and findings | "The engine suggested this." | "It was accepted." |
| `DECIDED` | Review ledger (append-only) | "An identified reviewer recorded this decision for this revision." | "The decision guarantees runtime correctness." |

A `BUILTIN` target (`COMMIT`, `EXECUTE_QUERY`, …) is a known Forms built-in.
It carries `resolution = SYMBOLIC_REFERENCE` in 2.2 but has no body to
resolve, so the projection gives it `NOT_APPLICABLE`, never `UNRESOLVED`.
Local targets (`ITEM`, `ALERT`, `PROGRAM_UNIT` in the same Form) have no
resolution attribute and are also `NOT_APPLICABLE`.

The relation and the target are judged separately. An observed `CALLS` to an
unresolved routine is `level = OBSERVED, resolution = UNRESOLVED`; the pair is
not promoted to a resolved fact. The same holds for a literal `OPENS_FORM` to a
Form that was not supplied (`NOT_SUPPLIED` in the visual fixture).

**Resolution in 2.2 is an attribute, not an edge.** When a reference is
resolved (`resolution = RESOLVED_TO_DATABASE_OBJECT`), the database object is
named by `resolved_target` on the reference entity. The inventory counts zero
reference→database edges in every corpus. The projection shows the resolved
object as the target's resolution, with the reference's evidence, and does not
invent an edge.

**Path search** never crosses an `UNRESOLVED` target as if it were a confirmed
link. A path that reaches one ends there and is labelled partial.

## 6. Visual attributes: declared value versus default

The 2.2 parser fills defaults: a canvas with no `CanvasType` becomes
`"Content"`, and a canvas or item with no `Visible` becomes `True`. Once in the
model, a declared value and a default are the same value. The visual fixture
proves it: `CV_VISIBLE_DECLARED` (with `CanvasType="Content" Visible="true"`)
and `CV_DEFAULTS` (neither attribute) both parse as `Content` / `True`.

Therefore, in this revision:

| Value in the model | What the explorer may say | Origin |
|---|---|---|
| `Canvas.visible = False` | "Canvas declarado oculto" — a declaration, not a claim that it never appears at runtime. | Declared: the parser (`_b`) produces `False` only when the `Visible` attribute is present with a value other than `true`; Forms2XML writes `false`. |
| `Canvas.visible = True` | Nothing about visibility. | **Não verificável nesta revisão** — declared value or parser default. |
| `Canvas.canvas_type = "Content"` | "Tipo: Content (origem não verificável)". | **Não verificável nesta revisão** — declared value or parser default. |
| `Canvas.canvas_type` ≠ `"Content"` | The declared type. | Declared: `"Content"` is the parser's only default (also used for an empty `CanvasType=""`). |
| `Item.visible = True` / `False` | Same rule as the canvas: `False` is a declaration; `True` is not verifiable. | As above. |

The explorer never labels `True` or `"Content"` as "declarado" by inference.
Neither the 2.2 model nor the 2.2 Blueprint can tell the two cases apart, and
the Blueprint does not persist any canvas or window attribute
(`canvas_attributes_persisted` = []). Only the raw XML can, which is why the
inventory reads it (`visible_origin`, `canvas_type_origin`). That read is a
phase 1 measurement tool, not a query-time path: the explorer never reads the
source to answer a question about a saved snapshot.

What phase 2 must capture to make the origin verifiable is listed in
[gaps and capture inventory §3](gaps-and-capture.md#3-what-phase-2-must-capture).
Until it does, the origin of `True` and `"Content"` stays **not verifiable**,
including after a 2.3 re-analysis that does not capture it.

## 7. Frontiers

A frontier is where the static graph stops, stated with its reason. For each
kind, 2.2 records the following:

| Frontier | Reason code | 2.2 records |
|---|---|---|
| Routine/package/table not supplied | `TARGET_NOT_SUPPLIED` | Reference node with `SYMBOLIC_REFERENCE`; edge `FACT`. |
| Literal Form not supplied | `FORM_NOT_SUPPLIED` | `OPENS_FORM` FACT to `FORM_REFERENCE` with `SYMBOLIC_REFERENCE`. |
| Form chosen at runtime (`OPEN_FORM(:item)`) | `RUNTIME_TARGET` | **No node or edge.** Only a finding question ("Runtime target unresolved: OPEN_FORM") and risk factor `cross_module_unresolved`. |
| Dynamic SQL (`FORMS_DDL`, `EXECUTE IMMEDIATE`) | `DYNAMIC_SQL` | **No node or edge.** Only risk factor `dynamic_sql` and behavior `UNCERTAIN`. |
| Same name, several candidates | `AMBIGUOUS_TARGET` | **Not recorded**: 2.2 resolves an unqualified name to the one surviving package (G-SCHEMA-COLLIDE). |
| Undeclared canvas/tab named by an item | `VISUAL_TARGET_NOT_DECLARED` | **No trace**: no edge, no reference node (item `GHOST`). |

For the last four rows, the frontier cannot be drawn from saved facts in a
2.1/2.2 snapshot. The explorer lists them from finding questions and risk
factors, with their evidence, and says the link is not in the graph. Phase 2
must record them.

## 8. Bounds and truncation

- The server enforces all limits. The defaults follow the spec: a focus view
  of 80 nodes and 160 edges, paths with depth 4 (max 6) and at most 3 paths.
  The first render is smaller than the technical limit (4–8 groups).
- Every cut is reported as `{reason, shown, available}` with the reasons
  `NODE_BUDGET`, `EDGE_BUDGET`, `DEPTH_LIMIT`, `TIME_BUDGET`, `FILTERED`,
  `MISSING_SOURCE`, `UNRESOLVED_TARGET` and `SELECTOR_LIMIT`.
- **A bounded view reports how many relations it shows and how many exist.**
  This rule answers a measured 2.2 behaviour. On the 500-Form ecosystem fixture,
  the attention-ranked ESTATE map kept 100 of 531 nodes and **none of the 1,125
  relationships** ([performance record](performance-2.2-baseline.md)). The
  2.2 response does report `total_estate_edges`. The explorer is focus-first
  for that reason, and a view that shows zero of N relations must say so.
- Aggregated relations keep the real total; a page of instances is never
  presented as the whole list.

## 9. Revision compatibility

- A 2.3 assessment with visual links carries `visual_hierarchy_version: 1` in
  allowlisted metadata; `engine_version` is bumped; `schema_version` stays
  `blueprint/1` while the change is additive. None of this exists yet: the
  measured engine version is
  `blueprint-analysis/1+plsql-evidence/1+analysis/1+risk/1+behavior/1+sensitive/1+catalog:…`.
- The **absence** of the capability identifies a 2.1/2.2 snapshot. Opening it
  never re-parses, never writes to SQLite and never back-fills links. What the
  explorer can show for it is exactly what the inventory measured:
  `FORM CONTAINS WINDOW/CANVAS`, typed `ITEM REFERENCES CANVAS`, and the
  "Vínculo visual não disponível nesta revisão; reanalise para completar"
  notice.
- Re-analysis to obtain visual links is an explicit user action that creates a
  new revision under the current rules. Decisions are shown as valid for the
  new revision only where the current binding rule allows it.

## 10. Disclosure

Per spec §8, responses carry ids and generated labels by default. Evidence text
and source excerpts are returned on demand, under the existing source-read
permission. Integration labels (HOST, URL, connect strings) keep the delivery
redaction. No endpoint accepts a graph or free text from the browser. None of
this is new policy; the contract only requires every `ecosystem/1` endpoint to
apply it.
