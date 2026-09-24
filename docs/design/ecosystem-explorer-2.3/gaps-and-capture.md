# Gaps in the 2.2 facts, and what phase 2 must capture

Status: **phase 1, measured.** Each entry below has a minimal reproduction in
the fixtures and a `test_gap_*` test in `tests/test_ecosystem_phase1.py`. Those
tests pin current behaviour. They do not endorse it. A later phase that
closes a gap on purpose changes the test and the committed inventory together.

Phase 1 changes nothing in `formslang/`. The three engine defects in §1
predate 2.3 and ship in 2.2.0. They are reported here for a separate
decision.

## 1. Engine defects found while measuring (pre-existing in 2.2.0)

### G-DML — `UPDATE` right after `THEN` is not recorded as a write

`formslang/plsql_evidence.py:127` accepts `UPDATE` as a write only when the
previous token is not `FOR`, `THEN`, `BEFORE` or `AFTER`. `THEN` is in that
set to skip the `WHEN MATCHED THEN UPDATE` clause of a `MERGE`. The side
effect is that an ordinary `UPDATE` that begins an `IF … THEN`, `ELSIF … THEN`
or `EXCEPTION WHEN … THEN` branch is lost. `INSERT`, `DELETE`, `SELECT` and
calls in the same position are captured.

- **Measured effect (Case B).** `APPROVALS` `BT_APPROVE` and `BT_REJECT` both run
  `UPDATE lom_approvals` inside `IF … THEN`. The Blueprint records only the
  `LOM_ORDERS` write. The `api_bypass` candidate therefore covers `LOM_ORDERS`
  only; a write to `LOM_APPROVALS` is invisible to the hotspot and to the
  future explorer.
- **Severity.** This is a correctness defect in extracted facts: writes are
  under-reported, and the report looks complete.
- **Test.** `test_gap_case_b_update_right_after_then_is_not_recorded_as_a_write`.
- **Fix direction (not applied).** Exclude `THEN` only inside a `MERGE`
  statement, as the `USING` branch two lines above already does.

### G-SCHEMA-BODY — a schema-qualified package body loses its subprograms

`database.parse_package_body` takes the name from a regex that accepts
`SCHEMA.NAME`. It then looks for the start of the body with
`tokens[i - 2] == "BODY"` (`formslang/database.py:426`). With `SCHEMA.NAME`,
the token two places before `AS` is `.`, not `BODY`. No subprogram is
parsed, so there is no `SUBPROGRAM_BODY` and no `IMPLEMENTS` edge.

- **Measured effect (Case C).** Both `CREATE OR REPLACE PACKAGE BODY
  SALES_OWNER.ORDER_API` and `BILLING_OWNER.ORDER_API` yield zero subprograms.
  The same `SALES_OWNER` body with the schema prefix removed yields its one
  subprogram, `SUBMIT`.
- **Test.** `test_gap_case_c_schema_qualified_package_body_loses_its_subprograms`.

### G-SCHEMA-COLLIDE — same-named packages in two schemas collapse into one

`DatabaseProject.package_specs` and `package_bodies` are keyed by bare name
(`formslang/database.py:654`, `:660`). Two `ORDER_API` packages in different
schemas become one, and the last file parsed wins. With sorted paths that is
the `sales_*` file.

- **Measured effect (Case C).** One `PACKAGE_SPEC ORDER_API`. The call without
  a schema, `ORDER_API.SUBMIT`, is `RESOLVED_TO_DATABASE_OBJECT` to that single
  survivor, and nothing marks the ambiguity. The schema-qualified calls stay
  `SYMBOLIC_REFERENCE`, so they do resolve to the right place: nowhere.
- **Consequence for the contract.** The spec requires that "aresta ambígua
  exibe alternativas sem se fixar numa delas". The explorer cannot meet this
  from 2.2 facts. It must not present the 2.2 resolution of an unqualified
  name as resolved, whenever a same-named object may exist in another schema.
  It shows the call site as observed and the target as not verifiable.
- **Test.** `test_gap_case_c_same_named_packages_in_two_schemas_collapse_into_one`.

**Recommendation.** Decide G-DML separately from 2.3, as a 2.2.x candidate. It
affects the existing hotspot output, not only the explorer. G-SCHEMA-BODY and
G-SCHEMA-COLLIDE belong to phase 2, where resolution with schema becomes part
of the contract.

## 2. Contract gaps (facts 2.2 does not record)

| Id | Gap | Measured on | Contract consequence |
|---|---|---|---|
| G-VIS-ATTR | Canvas `window_name`, `canvas_type`, `visible`, `tab_pages` and window `primary_canvas` are parsed but not persisted: `canvas_attributes_persisted` = [], `window_attributes_persisted` = [] | all four corpora | No window→canvas→tab tree in any 2.2 snapshot. |
| G-VIS-TAB | No `TAB_PAGE` entity (0 everywhere), even though the showcase has 28 items on tab pages | showcase, visual | Tabs exist only after phase 2 re-analysis. |
| G-VIS-ORIGIN | Declared `Visible="true"` / `CanvasType="Content"` cannot be told from parser defaults, in the model or in the Blueprint | visual (`CV_VISIBLE_DECLARED` vs `CV_DEFAULTS`) | Origin "não verificável nesta revisão" ([contract §6](contract-ecosystem-1.md#6-visual-attributes-declared-value-versus-default)). |
| G-VIS-GHOST | An item on an undeclared canvas, and an item with no canvas, get no edge and no reference: they vanish from the visual graph | visual (`GHOST`, `NO_CANVAS`) | Listed from parser data only after phase 2; in 2.2 snapshots only "sem canvas identificado" by absence. |
| G-VIS-TYPE | `ITEM REFERENCES CANVAS` shares the raw type `REFERENCES` with data and bind references | all | Typed in projection by source/target/evidence ([contract §4](contract-ecosystem-1.md#4-families-mapped-from-the-22-edge-types)). |
| G-BRIDGE | Reference→database resolution is an attribute (`resolved_target`), not an edge: `database_bridge_edges` = 0 | all | The projection shows the resolution; it does not draw an edge. |
| G-FRONTIER | Dynamic `OPEN_FORM` and dynamic SQL produce no node or edge, only a finding question or risk factor | showcase (4 + 2), visual | Frontier listed with evidence; no drawn frontier in 2.2 snapshots. |
| G-CALL-LOCAL | `PKG_UTIL.P_MSG` stays symbolic although `PKG_UTIL` is a program unit of the same Form | Case A | Shown as unresolved; not linked by name. |
| G-CALL-EXPR | `PKG_UTIL.F_USUARIO` inside an expression produces no edge | Case A | Visible only in the source text of the trigger. |
| G-RISK-TEXT | Risk factor "Unresolved local calls" is emitted for `POST-COMMIT` although `P_CALC_TOTAL_ITENS` resolves by `USES_PROGRAM_UNIT` | Case A | The explorer shows edges, not that factor's wording, as the account of calls. |
| G-WIN-PRIMARY | No window in the modernization lab declares `PrimaryCanvas` | Case B | Surface of each lab Form rests on `Canvas.WindowName` alone. |
| G-ESTATE-EMPTY | The 2.2 ESTATE map can keep only nodes that share no relationship: 100 of 531 nodes, 0 of 1,125 relationships at 500 Forms (ecosystem profile) | scale fixture | Focus-first explorer; bounded views report relations shown/available ([contract §8](contract-ecosystem-1.md#8-bounds-and-truncation)). |

## 3. What phase 2 must capture

The table is the enrichment inventory for phase 2. "Raw presence" means the
attribute was present in the Forms2XML element, whatever its value. The
parser must record that alongside the value, because the value alone cannot
carry it.

| Datum | Captured today | Must capture | Why |
|---|---|---|---|
| `Canvas.WindowName` | value in model | value + raw presence, persisted as `CANVAS_IN_WINDOW` with proof; unresolved visual reference when the window is not declared (`CV_ORPHAN`) | window→canvas tree |
| `Window.PrimaryCanvas` | value in model | `WINDOW_PRIMARY_CANVAS` with proof; conflicts with `WindowName` kept as two declarations plus a diagnostic (`WIN_SIDE`/`CV_SHARED`) | never choose the "correct" one |
| `Canvas.CanvasType` | value, default `"Content"` | value + **raw presence** (tri-state: declared value / absent / empty) | declared-type label |
| `Canvas.Visible` | bool, default `True` | bool + **raw presence** (declared true / declared false / absent) | "declarado oculto" vs "não declarado" |
| `Item.Visible` | bool, default `True` | bool + **raw presence** | same rule for items |
| `Canvas.TabPage` list | names in model | one `TAB_PAGE` node each, `CANVAS_CONTAINS_TAB_PAGE` with proof; tab labels if present | tab tree |
| `Item.TabPageName` | value in model | `ITEM_ON_TAB_PAGE` only when canvas and tab reconcile; otherwise unresolved visual reference (`LOST_TAB_FIELD`) | no cross-canvas guessing |
| `Item.CanvasName` to undeclared canvas | nothing persisted | unresolved visual reference with proof (`GHOST`) | item must not vanish |
| Item with no canvas | nothing persisted | explicit "no canvas declared" fact or attribute (`NO_CANVAS`) | "Componentes sem canvas identificado" |
| Dynamic `OPEN_FORM` / `CALL_FORM` | finding question | frontier reference with reason `RUNTIME_TARGET` and proof | drawable frontier |
| Dynamic SQL | risk factor | frontier reference with reason `DYNAMIC_SQL` and proof | drawable frontier |
| Package schema | stripped | schema kept in identity and resolution; ambiguity recorded (G-SCHEMA-*) | Case C |
| Capability | — | `visual_hierarchy_version: 1` in allowlisted metadata; `engine_version` bump | Case D |

The parser already carries every value in the "Captured today" column (spec
§7.1 Layer A). The only parser change this table implies is **raw presence**
for `Visible` and `CanvasType`, which spec §7.1 allows only with an accepted
case, proof and its own test. The visual fixture is that case.
