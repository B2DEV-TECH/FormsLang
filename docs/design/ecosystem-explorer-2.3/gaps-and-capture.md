# Gaps in the 2.2 facts, and what phase 2 must capture

Status: **phase 1, measured.** Each entry below has a minimal reproduction in
the fixtures and a `test_gap_*` test in `tests/test_ecosystem_phase1.py`. Those
tests pin current behaviour. They do not endorse it. A later phase that
closes a gap on purpose changes the test and the committed inventory together.

Phase 1 changes nothing in `formslang/`. The engine defects in §1
predate 2.3 and ship in 2.2.0. The decisions taken at review close §1.

## 1. Engine defects found while measuring (pre-existing in 2.2.0)

### G-DML — `UPDATE` right after `THEN` is not recorded as a write

**Status: fixed in `plsql-evidence/2`** (separate 2.2.x pull request). The
description below is the 2.2.0 behaviour, kept as the record of the defect.

In 2.2.0, `formslang/plsql_evidence.py:127` accepted `UPDATE` as a write only when the
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
- **Test.** `test_case_b_update_right_after_then_is_recorded_as_a_write`
  (was `test_gap_case_b_update_right_after_then_is_not_recorded_as_a_write`).
- **Fix (applied).** The extractor tracks whether the current statement is a
  `MERGE`, from the `MERGE` keyword to the `;` that ends it. Inside a `MERGE`,
  the `UPDATE` and `DELETE` of its `WHEN MATCHED` branches are part of the one
  write to the `MERGE INTO` target, and are not counted again. Outside a
  `MERGE`, `UPDATE` after `THEN` is a write. Regression tests in
  `tests/test_blueprint.py` cover `IF`, `ELSIF`, `ELSE`, `EXCEPTION WHEN`,
  `CASE` and nested branches, a `MERGE` with `UPDATE`, `DELETE WHERE` and
  `INSERT` branches counted once, and a `MERGE` followed by an `UPDATE`.
- **Effect of the fix (Case B).** Both triggers now have a `WRITES` edge to
  `LOM_APPROVALS`, and two new `HIGH` `api_bypass` candidates appear for
  `LOM_APPROVALS`, with `LOM_APPROVAL_API.APPROVE` as the first potential
  owner. The existing `LOM_ORDERS` candidates keep their ids. The committed
  inventory changed only there and in the engine version string.
- **Existing assessments.** They are not rewritten. The engine identity
  changes with `plsql-evidence/2`, so a saved assessment is reported as made
  by an older engine; a new analysis produces the corrected facts.

### G-SCHEMA-BODY — a schema-qualified package body loses its subprograms

**Status: fixed in `blueprint-analysis/2`**, ahead of G-SCHEMA-COLLIDE (FormsLang
3.0 M0, work package WP-03). The description below is the 2.2.0 behaviour, kept
as the record of the defect.

In 2.2.0, `database.parse_package_body` took the name from a regex that accepts
`SCHEMA.NAME`. It then looked for the start of the body with
`tokens[i - 2] == "BODY"`. With `SCHEMA.NAME`,
the token two places before `AS` is `.`, not `BODY`. No subprogram is
parsed, so there is no `SUBPROGRAM_BODY` and no `IMPLEMENTS` edge.

- **Measured effect (Case C).** Both `CREATE OR REPLACE PACKAGE BODY
  SALES_OWNER.ORDER_API` and `BILLING_OWNER.ORDER_API` yield zero subprograms.
  The same `SALES_OWNER` body with the schema prefix removed yields its one
  subprogram, `SUBMIT`.
- **Test.** `test_schema_qualified_package_body_keeps_its_subprograms` and
  `test_case_c_schema_qualified_package_bodies_yield_their_subprograms`
  (was `test_gap_case_c_schema_qualified_package_body_loses_its_subprograms`).
- **Fix (applied).** Subprogram scanning starts at the first token after the
  `AS`/`IS` that the header regex matched, whatever the name looks like.
- **Effect of the fix (Case C).** The surviving `ORDER_API` body now has its
  `SUBPROGRAM_BODY ORDER_API.SUBMIT`, which `IMPLEMENTS` the declared
  subprogram and `WRITES` `SALES_OWNER.SALES_ORDERS`. That write stays a
  `SYMBOLIC_REFERENCE`: tables are keyed by bare name, so the qualified name is
  not resolved. Because G-SCHEMA-COLLIDE is still open, the two bodies collapse
  like the specs: only the `sales_*` body survives. The pinned collision test
  records this. The unqualified call still resolves to the declared subprogram,
  as before; no new resolution is made. The committed inventory changed only
  in Case C (one `SUBPROGRAM_BODY`, two `IMPLEMENTS`, one `WRITES`, one table
  reference, two findings) and in the engine version.
- **Existing assessments.** They are not rewritten. The engine identity
  changes to `blueprint-analysis/2`, so a saved assessment is reported as made
  by an older engine.
- **Why separately from G-SCHEMA-COLLIDE.** The 2026-09-24 review planned both
  fixes for phase 2. This one changes no identity key, and it restores the
  facts of an estate whose DDL carries one schema prefix, which is the common
  case. It makes a qualified body behave the way an unqualified one already
  did, collision included.

### G-DDL-HEADER — an exported package header is dropped without a trace

**Status: fixed in `blueprint-analysis/3`** (FormsLang 3.0 WP-07). Found while
fixing G-SCHEMA-BODY. `parse_package_spec` and `parse_package_body` accepted
only `CREATE [OR REPLACE] PACKAGE [BODY] name`, with an unquoted `name` of the
form `NAME` or `SCHEMA.NAME`. The headers that DDL exports usually write,
`CREATE OR REPLACE EDITIONABLE PACKAGE BODY "SCHEMA"."NAME"`, `NONEDITIONABLE`,
quoted names, and spaces around the dot, did not match. The package was not
parsed, and nothing recorded that the file was skipped: it was listed in
`DatabaseProject.files` with no object.

- **Fix.** One header pattern serves both parsers:
  `CREATE [OR REPLACE] [EDITIONABLE | NONEDITIONABLE] PACKAGE [BODY] [owner .] name AS|IS`,
  where each part may be quoted. A quoted name keeps its exact case; an
  unquoted one is folded to upper case, as Oracle does. The identity key is
  still the bare name (G-SCHEMA-COLLIDE is unchanged).
- **Stricter than before.** `S..P`, `S.P.Q` and `1P` were accepted, because the
  old pattern took the last dotted part of any run of name characters. They
  are now not recognised. A specification named `BODY_API` was dropped, and is
  now parsed.
- **Every source is now accounted for.** `DatabaseProject.coverage` gives each
  supplied source a status (`PARSED`, `PARSED_WITH_WARNINGS`,
  `NO_RECOGNIZED_OBJECTS`, `REJECTED_OR_UNREADABLE`) and lists the CREATE
  statements that yielded no object. A lexical scan finds them, independently
  of the extractors. The Blueprint carries it as `database.source_coverage`.
  When coverage was never computed it is `None`: unknown, not clean.
- **Warning versus information.** A statement of a supported kind that yields
  no object is listed under `not_extracted` with `severity: WARNING`,
  `reason: NOT_EXTRACTED`, and makes the source `PARSED_WITH_WARNINGS`. A
  statement of a kind FormsLang does not model (`CREATE INDEX`, `TRIGGER`,
  `TYPE`, ...) is listed under `unsupported` with `severity: INFO`,
  `reason: UNSUPPORTED_BY_MODEL`. It stays visible but does not by itself
  change the status: a source of tables and indexes is `PARSED`.
- **Quoted names are not resolved against unquoted ones.** `"MyPackage"` and
  `MYPACKAGE` are different objects, as in Oracle, and nothing normalises one
  into the other. Quoted *subprogram* names are separate, unstarted work.
- **Tests.** `tests/test_database_headers.py`, `tests/test_database_coverage.py`.

### G-DDL-EXTRACT — CREATE statements that are recognised but not extracted

Found during WP-07; open. Coverage now reports each case as `not_extracted`,
so none is silent any more, but the object is still missing from the
Blueprint:

- **Clause before `AS`.** `AUTHID`, `ACCESSIBLE BY`, `DEFAULT COLLATION` and
  `SHARING` between the package name and `AS`/`IS`. Pinned by
  `test_gap_spec_header_with_a_clause_before_as_is_not_recognised`.
- **One package per file.** Only the first specification and the first body
  in a file are extracted.
- **After a `/`.** The statement splitter keeps the `/` at the head of the
  next statement, so a table after a `/`-terminated statement is not read. A
  view followed by `/` without `;` absorbs the next statement into its query
  text.
- **Variants.** `GLOBAL TEMPORARY TABLE`, `FORCE VIEW`, and quoted table,
  view and sequence names.

### G-SOURCE-REVISION — a zero-object source does not reach the revision

Found during WP-07; open, deliberately not changed there. `blueprint.build`
derives `source_revision` from `DatabaseProject.files`, and a source that
yields no object is not in `files`. Adding or removing such a source (a
trigger file, an index-only file, seed DML) leaves the revision unchanged,
although coverage lists it. The invariant to hold:

> Two repository states with materially different supplied source sets must not silently appear identical merely because one source produced zero extracted objects.

This belongs to repository and checkpoint identity (ADR-02, consumed by
WP-10 and WP-20), not to the DDL parser. The revision semantics are unchanged
until then.

### G-SCHEMA-COLLIDE — same-named packages in two schemas collapse into one

`DatabaseProject.package_specs` and `package_bodies` are keyed by bare name
(`formslang/database.py:654`, `:660`). Two `ORDER_API` packages in different
schemas become one, and the last file parsed wins. With sorted paths that is
the `sales_*` file. Tables and views are keyed the same way:
`parse_create_table` drops the schema prefix (`formslang/database.py:580`).

- **Measured effect (Case C).** One `PACKAGE_SPEC ORDER_API`. The call without
  a schema, `ORDER_API.SUBMIT`, is `RESOLVED_TO_DATABASE_OBJECT` to that single
  survivor, and nothing marks the ambiguity. The schema-qualified calls stay
  `SYMBOLIC_REFERENCE`: nothing wrong is claimed, but nothing is resolved.
- **Consequence for the contract.** The spec requires that "aresta ambígua
  exibe alternativas sem se fixar numa delas". The explorer cannot meet this
  from 2.2 facts. Because the collapse leaves no trace, the
  contract presents **every** 2.1/2.2 database resolution as
  `LEGACY_RESOLVED`, "não verificável quanto a schemas homônimos", until a
  schema-aware re-analysis
  ([contract §5.1](contract-ecosystem-1.md#51-legacy-database-resolution-2122-snapshots)).
  The call site stays observed.
- **Test.** `test_gap_case_c_same_named_packages_in_two_schemas_collapse_into_one`.

**Decisions (review of PR #17, 2026-09-24).**

- **G-DML** is fixed in a separate 2.2.x pull request, with regression tests
  for `UPDATE` after `THEN` and for `MERGE`. It is a correctness defect in
  hotspots that have already been published.
- **G-SCHEMA-BODY and G-SCHEMA-COLLIDE** are fixed in phase 2. The fix keeps
  the schema and records ambiguities. Existing assessments are not rewritten;
  they stay under the legacy-resolution rule. *Amended in FormsLang 3.0 M0:*
  G-SCHEMA-BODY was fixed on its own in `blueprint-analysis/2` because it
  changes no identity key; G-SCHEMA-COLLIDE still needs the schema-aware
  identity.

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
