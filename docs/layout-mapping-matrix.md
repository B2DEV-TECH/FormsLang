# Layout mapping: a Forms screen as native APEX components

FormsLang converts the *layout* of a Forms module - windows, canvases,
frames, tab pages, blocks, items, buttons - into native Oracle APEX 26.1
components through APEXlang: regions and sub-regions, page items, buttons,
Interactive Grids, Universal Theme templates and template options, and the
12-column grid properties of each one. Nothing is drawn: no canvas, no
screenshot, no HTML region holding the whole screen, no absolute
positioning, no JavaScript and no CSS of FormsLang's own. Every component
is a normal, individually editable Page Designer component, so the result
is a faithful *starting point* that keeps the structure of the Forms screen
and leaves the redesign decisions to the developer.

One layout model feeds everything: `apexlayout.build_layout()` resolves the
Forms geometry into a tree of regions with their items, columns and grid
placement; `apexlang` writes that tree as the page file; `formui` draws the
same tree as the "planned APEX layout" half of the preview; and
`apexlayout.layout_report()` turns it into the per-element mapping report
the export writes next to the ZIP, in `<alias>-review/apexlang-manifest.json`
under `layout.mapping_report`.
There is no second mapping for the preview.

## Viewport

The placement is resolved for one documented viewport, and the report
states it:

> desktop, 1280 CSS px wide, Universal Theme Standard page template,
> 12-column grid; on narrow screens Universal Theme stacks the cells of a
> row, one per line

Responsive behaviour is Universal Theme's own: a row of grid cells stacks
one cell per line under the theme's breakpoints. FormsLang does not add
breakpoints, media queries or resize code.

## How geometry becomes grid placement

Forms positions are absolute (x, y, width, height in the module's
coordinate units); APEX places components in rows of a 12-column grid.
The translation, per parent group (canvas, tab page, frame):

1. **Rows.** Items are sorted top to bottom; items whose vertical extents
   overlap within a tolerance of a few units form one row, so fields whose
   baselines differ by a pixel or two still share a row. Each row starts
   with `startNewRow: true`.
2. **Columns from x.** One grid column is a twelfth of the parent's
   width. A control starts on the column its left edge maps to
   (`round((x - parent x) / column) + 1`) and spans the columns its width
   covers, at least one - so a field keeps the horizontal position Forms
   drew it at, and the whitespace before it stays an empty column
   (Universal Theme pads a skipped column, a leading one included). A
   field with a prompt beside it gets at least two columns, one for the
   label. Three concessions, each recorded on the control in the report:
   when two controls round onto the same column the second moves right to
   the first free one (`pushed`); a control left with less than half its
   columns continues on the next grid row (`wrapped`), and the controls
   after it in the Forms row follow it there, keeping their distance from
   it; a control reaching past the twelfth column is narrowed to the
   columns that remain (`shrunk`).
3. **Label space.** A caption drawn left of the field takes
   `labelColumnSpan` of the field's own columns - in grid columns, from the
   room the prompt takes in Forms (its characters times the module's
   character cell, plus the attachment offset), rounded, and always fewer
   than the `columnSpan` - `LABEL_COLUMN_SPAN_TOO_BIG` is a render-time
   error that neither `apex validate` nor `apex import` sees, so the cap is
   covered by a regression test and checked in the APEX dictionary after
   import. Labels are settled per row: a label narrower than its room
   because the field's cell has no more columns to give is `label-narrow`;
   a row that cannot give even one of its labels a column puts every label
   of the row above its field (`label-above`) - one rhythm per row, the
   way a person would redraw it. A caption above the field uses the
   `-above` label template, aligned as Forms aligns the prompt; a caption
   the theme has no side for (right, below) becomes a label above too, and
   the report records that as an approximation. A check box keeps its
   label on the control (`-floating`, which Universal Theme places next to
   the box). An item with no caption gets a hidden label with
   `labelColumnSpan: 0`.
4. **Nested groups.** A frame becomes a sub-region of its canvas region
   (slot `subRegions`); a frame inside a frame nests the same way. Items
   drawn beside a frame, in the parent group, go to a derived row region
   (`<parent>-row-N`, `blank-with-attributes`, no header) placed in the
   cell next to the frame's, with their columns resolved inside that cell;
   items drawn below a frame go to a derived row region that spans the
   parent, keeping their columns on the parent. The vertical order of the
   screen survives either way; the report lists derived regions but does
   not count them as Forms groups.
5. **Widths and heights.** A `textarea` gets `width` and `height` in
   characters and rows from the item's box; grid columns get `width` in
   characters; every other item keeps its `columnSpan` as its width.
6. **Order.** Sequence numbers follow the reading order of the screen: the
   row, then the column inside the row.
7. **Toolbars** flow: no column arithmetic, since a toolbar's controls are
   read in order, not measured. Adjacent buttons share a grid cell
   (`newColumn: false`), as on the Forms toolbar; a field on the toolbar
   gets a cell of its own.
8. **Initial values.** A literal `InitializeValue` is the item's static
   default (`default { type: static staticValue }`, verified to fill the
   field on render, a display-only item included); a Forms expression
   (`$$DATE$$`, `:GLOBAL.x`, `&PARAM`, `:PARAMETER.x`, `:SYSTEM.x`) is not
   a value and is left as a note. On a radio group or select list the
   default is written only when it is one of the choices' return values:
   APEX adds an unknown value to the choices as an extra, selected one -
   a fourth button on a three-button group - which is not the Forms
   screen. A value that is a choice's *label* (the .fmb declares no return
   values and the names stand in) takes that choice's return value, and
   the report says so; a value that is neither leaves the item without a
   default, and the report says why.

## Mapping matrix

"Verified" means the APEXlang keywords were accepted by `apex validate`
on APEX 26.1.0, the package was imported into a dedicated development
application, the APEX dictionary showed the expected component, and the
rendered page was fetched and read (see *What was verified live*). No
keyword in this table was assumed from Page Designer.

| Forms source element | Native APEX target | Properties preserved | Verified | Fallback | Known differences |
|---|---|---|---|---|---|
| Primary window and module | One page (Standard page template), titled from the module | title, page number chosen at export | yes | - | one page per module; a module with several primary windows still becomes one page |
| Content canvas | `standard` region in the page body, titled from the canvas | title, order of canvases, items and frames inside | yes | - | - |
| Horizontal / vertical toolbar canvas | `blank-with-attributes` region; controls flow inline in their rows and order, adjacent buttons in one grid cell, a field in a cell of its own | order, rows, captions, buttons side by side | yes | - | *approximation*: controls keep order and rows, not exact positions |
| Stacked canvas | `inline-dialog` region holding its content | title, content, order | yes | - | *approximation*: shown on demand in Forms; opening the dialog needs a dynamic action the developer adds |
| Secondary window (its content canvas) | `inline-dialog` region | title, content, order | yes | - | same as the stacked canvas |
| Tab canvas | `tabs-container` region | order of tab pages | yes | - | - |
| Tab page | `standard` region in the `tabs` slot of its tab canvas, titled from the tab label | label, order, content | yes | - | - |
| Frame with caption | `standard` sub-region titled with the caption; `t-Form--stretchInputs` when it holds form items | caption (once, as the region title - never repeated as a label), nesting, content order, geometry | yes | - | - |
| Frame whose only content is one multi-record block | the block's Interactive Grid takes the frame's place and caption | caption, position | yes | - | no empty wrapper region is written |
| Boilerplate text | `blank-with-attributes` static content region with the text; a prompt-like text next to a field becomes that field's label | text, position | yes | - | *approximation* when a text is read as a field's prompt (reported) |
| Rectangle with a text inside | `standard` region titled with the text | text, position | yes | - | - |
| Text Item, single line | `textField` page item on the column its x maps to | label text, caption side (`optional`/`required` beside the field, `-above` above it), label room (`labelColumnSpan`, in grid columns), required, max length, position (`column`) and width (`columnSpan`), case restriction (`textCase`), enabled = false as `readOnly`, hint + tooltip as help text, literal initial value as the static default, format mask (in the comments) | yes | - | right/below captions become a label above; a row that cannot give every label a column puts all its labels above; a control pushed, wrapped or narrowed by a crowded row is reported |
| Text Item, MultiLine (or Text Editor / Text Area) | `textarea` page item | as above, plus `width` and `height` from the item box | yes | - | rows come from the box height in units |
| Text Item, data type Date / Datetime | `datePicker` page item with `formatMask` from the Forms format mask | as Text Item, plus the format mask as a native property | yes (renders as `<a-date-picker format="DD/MM/YYYY">`) | - | - |
| Text Item, data type Number | `numberField` page item with `formatMask`; `numberAlignment: end` when Forms right-justifies it | as Text Item, plus format mask and alignment as native properties | yes (renders with `data-format` and right alignment) | - | - |
| Display Item | `displayOnly` page item | label, side, position, width, help, literal initial value | yes | - | `valueRequired` is not a property of a display-only item |
| Check Box | `checkbox` page item; `useDefaults: false`, `checkedValue` / `uncheckedValue` from the item; label on the control | label, values, position, width, literal initial value | yes | - | *approximation* when required in Forms: a required APEX check box must be *checked*, Forms only meant "has a value", so it is left optional and the report says so |
| Radio Group | `radioGroup` page item fed by a shared static LOV built from the radio buttons; `noOfCols` from how Forms lays the buttons out; `displayNullValue: false`; static default when the initial value is one of the choices | labels, values, buttons per row, no extra empty choice, initial value | yes (three buttons, the default selected) | - | *approximation* when the .fmb declares no return values: the labels stand in and the report says so; an initial value matching a label takes that choice's return value (reported); one matching nothing leaves no default (reported) |
| List Item (poplist, T-list, combo box) | `selectList` page item fed by a shared static LOV from the list elements; static default when the initial value is one of the choices | labels, return values when the .fmb declares them, required, width, initial value | yes | - | a T-list or combo box renders as a select list; undeclared return values are flagged; a default that is none of the choices is dropped and reported |
| Item initial value (`InitializeValue`) | `default { type: static staticValue }` on the item | the literal | yes (fills the field on render) | none, with a note | a Forms expression (`$$DATE$$`, `:GLOBAL.x`, `&PARAM`) is not a value: a note asks for a computation or a default of another type |
| Item with a record-group LOV attached | the item's native type above; the Forms LOV is named in the item's comments | everything of the item type | yes | - | **no LOV query is generated** - binding a LOV is functional review, never invented |
| Push Button | `button` in the region, `@/text` template, at the row and column Forms draws it; `definedByDynamicAction` behaviour (renders as a plain button, not a submit) | label, order, position | yes | - | buttons on a toolbar flow inline (*approximation*); the trigger's code is a proposal, never wired as the button's action |
| Hidden item (Visible = No, or no canvas) | `hidden` page item in its block's region | name, database column | yes | - | listed in the report, not scored: nothing of it is visible |
| Single-record block | its items in the regions of their canvases and frames, one page item each | everything above | yes | - | - |
| Multi-record block on a table (Records Displayed > 1, database block with a query data source) | `interactiveGrid` region on `localDatabase` + the table; one `column` per item in the left-to-right order Forms draws the record; heading = prompt; native column types as above; `primaryKey: true` where Forms marks it; `width` in characters; required and max length; hidden database items as `hidden` columns; non-database items as `source { type: none }`; primary saved report with the column sequence; `t-IRR-region--hideHeader` when the block sits inside a captioned frame | column order, headings, widths, types, required, primary key, hidden columns, records displayed (in the comments) | yes (three grids rendered, headings in Forms order) | - | *approximation*: record rows, paging and row height are the grid's own; **editing is off** until the developer confirms which DML the block performs; no table binding is invented for a block without a query data source |
| Multi-record block that is a control block or has no query data source | its items placed once as page items, with a note on the region saying why no grid was built | order, captions | yes | one record's worth of items | *approximation*, stated in the region's note and in the report |
| Image, Bean Area, OLE, ActiveX, VBX, Sound, Tree, Chart, custom item | `textField` placeholder at the item's position, reported as *unsupported* | name, position | yes | placeholder | APEX has no native component for it; the report lists it under `unsupported`, never as mapped |

A visible control lands exactly once: the report's `controls_placed_twice`
list is empty by construction and asserted by the regression suite.

## The fidelity report

`layout.mapping_report` in `apexlang-manifest.json` carries, for every
visible Forms control (item, button, grid column):

- **source identity**: `BLOCK.ITEM`, the Forms item type, canvas and tab
  page, and the Forms geometry (x, y, width, height);
- **target**: the component kind (`pageItem`, `button`, `gridColumn`), its
  native type, the identifier the page file uses for it (`P1_DS_NOME`,
  `control-bt-salvar`, `SEQ_ITEM`), the region id, sequence, and either the
  grid placement (`startNewRow`, `column`, `columnSpan`, label side and
  `labelColumnSpan`) or the grid column index, plus `placement`: `rules`,
  or `ai` when the AI layout assistant chose the cell;
- **rule**: the sentence that says which mapping applied;
- **preserved**: the properties carried over;
- **approximations** and **unsupported**: what could not be carried as is
  - each concession of the placement rules in the words of the rule that
  made it ("moved right to the first free column: it rounded onto the same
  grid column as the control before it", "continues on the next grid row:
  its Forms row is too crowded for twelve columns", "prompt left of the
  field in Forms, label above it here: no column of ...");
- **missing**: source metadata the .fmb did not have (`geometry` for an item
  with no position);
- **status**: `faithful`, `approximation` or `unsupported`.

Groups (canvases, frames, tab pages, block grids, boilerplate) have the
same shape; hidden items are listed with their target but not scored.
Totals give explicit denominators - *n* of the *m* visible controls are
faithful - and no percentage or score is derived from them.

The showcase module (`tests/fixtures/showcase/module.xml`, synthetic):

| Denominator | Faithful | Approximation | Unsupported |
|---|---|---|---|
| 72 visible controls (items, buttons, grid columns) | 46 | 26 | 0 |
| 21 Forms groups (canvases, frames, tab pages, blocks, boilerplate) | 15 | 6 | 0 |

The 26 approximations are: 14 toolbar controls that flow inline; 5 fields
of the eight-field lot row that moved right to the first free column and
1 that continues on the next grid row (eight fields with prompts are
sixteen columns); 2 captions right of or below their field, now labels
above; 2 prompts read from boilerplate text next to the field; 1 radio
group whose .fmb declares no return values (and whose initial value is
therefore a label, matched to its choice); 1 required check box left
optional. The 6 group approximations are the toolbar canvas, the three
Interactive Grids (rows and paging are the grid's own, editing off) and
the two on-demand canvases turned inline dialogs. Six hidden items are
listed; four of them are hidden grid columns. Ten derived row regions keep
vertical order and are not counted as groups. `placed_by_ai` is 0: the
export was made without the assistant.

## Before and after on the showcase

Both applications were imported into the same local APEX 26.1.0 instance
(FREEPDB1, workspace FORMSLANG, Universal Theme) and page 1 was fetched
through ORDS after logging in as a temporary end user (no page was made
public). Application 100 is the 1.0.0 export; application 190 is this one.

| Rendered page 1 | 1.0.0 (app 100) | 1.1.0 (app 190) |
|---|---|---|
| Regions rendered | 10 (9 standard + 1 tabs) | 13 (9 standard + 3 Interactive Grid + 1 tabs) |
| Interactive Grids | 0 | 3 (BK_ITENS 5 + 1 hidden, BK_AUDIT 6 + 2 hidden, BK_RESUMO 6 + 1 hidden columns) |
| Page items rendered as fields | 50 | 33 + 3 date pickers (17 items became grid columns) |
| Number fields (`numberField`) | 0 (all text fields) | 15, right-aligned with their format mask |
| Date pickers (`datePicker`) | 0 (text fields) | 3, format DD/MM/YYYY from the Forms mask |
| Textareas | 4 rows, default width, twice | 5 rows x 84 chars and 6 rows x 120 chars, from the Forms boxes |
| Radio buttons of TP_STATUS | 4 (an extra empty choice) | 3 (`displayNullValue: false`) |
| Labels rendered | 50, one of them empty | 30 (grid headings replace the labels of grid columns; no empty label) |
| Template options | none | `t-Form--stretchInputs` on the form regions, `t-IRR-region--hideHeader` on the grids inside captioned frames |
| Tab pages | 5 (`Tab Geral` ... `Tab Resumo`) | 5 (`Geral`, `Itens`, `Comercial`, `Auditoria`, `Resumo por Categoria`) |
| Error banner, `LABEL_COLUMN_SPAN_TOO_BIG`, ORA- errors | none | none |
| Absolute positioning, layout JavaScript, custom CSS | none | none |

The 1.2.0 pass changed *where* the same components land. Application 100
is the 1.1.0 export of the showcase; application 191 is the 1.2.0 export,
imported and rendered the same way (counts read from the HTML of page 1):

| Rendered page 1 | 1.1.0 (app 100) | 1.2.0 (app 191) |
|---|---|---|
| Empty grid columns kept as whitespace (`apex-grid-nbsp`) | 0 (every row packed to the left) | 30 (gaps and leading space as on the canvas) |
| Labels beside their field (`t-Form-labelContainer col-N`) | 23 | 28 |
| Labels above their field (`--stacked`) | 5 | 7 (above-prompts, and the right/below captions) |
| Floating labels (`--floatingLabel`) | 9 (crowded rows, right/below captions) | 2 (the two check boxes only) |
| Buttons rendered as `type="button"` / `type="submit"` | 35 / 0 | 35 / 0 |
| Fields showing their Forms initial value on render | 0 | `TP_STATUS` radio selected, `TP_UNIDADE` preselected |
| Radio buttons of `TP_STATUS` | 3 | 3 (a default outside the choices would have made a fourth) |
| Required check boxes | 1 (`FL_ATIVO`, which could then never be unticked) | 0 |
| Error banner, `LABEL_COLUMN_SPAN_TOO_BIG`, ORA- errors | none | none |

## What was verified live

On APEX 26.1.0 (Oracle Database FREE 23ai, ORDS, SQLcl 26.2), with the
synthetic showcase module:

1. `formslang apex validate` on the export: "Validation successful", no
   warnings.
2. `formslang apex import` into a dedicated development application (190,
   `SHOWCASE_LAYOUT`) in the FORMSLANG workspace.
3. APEX dictionary (`apex_application_page_regions`, `_items`, `_buttons`,
   `_ig_columns`): three Interactive Grids with their columns in Forms
   order, headings, native column types, primary-key flags and hidden
   columns; native page item types (Number Field, Date Picker, Textarea,
   Display Only, Select List, Radio Group, Checkbox, Hidden); template
   options stored as the expected CSS classes; every label span smaller
   than its item's column span; 18 buttons.
4. The page rendered by APEX, fetched over HTTP after a login as a
   temporary workspace end user created for the check and removed after
   it: no error banner, the three grids initialised with their headings in
   Forms order, the date pickers as `<a-date-picker>` with the Forms format,
   the number fields with their format mask and right alignment, the
   textareas with the rows and columns above, the tabs region with its five
   pages, the two inline dialogs, and no absolute positioning, layout
   script or custom CSS anywhere in the HTML.

5. For 1.2.0, the same steps on a dedicated probe application (191): the
   package validated and imported; the rendered page showed the skipped
   grid columns as empty cells (a leading one included), the left labels
   in their own column (`col-1`) next to fields on the columns their x
   maps to, the labels of the eight-field row and of the right/below
   captions above their fields, every button as `type="button"`, the
   radio group with its three buttons and the Forms initial value
   selected, the select list preselected, the check box optional, and no
   error banner, `LABEL_COLUMN_SPAN_TOO_BIG` or ORA- error. The AI layout
   assistant was exercised against a scripted provider in the test suite
   (plan applied, cached and replayed in the preview; rejected, offline,
   error and enterprise-policy paths) - not against a hosted model on the
   showcase.

Not done, and not claimed: a pixel comparison of screenshots, a browser
run at a narrow viewport (Universal Theme's stacking is documented, not
measured here), and any check on a real customer module - the showcase is
synthetic by design.

## The AI layout assistant

The rules above resolve every screen on their own, and record each
concession they make. Some rows they cannot lay out the way a person
would: eight fields with prompts in one row are sixteen columns; two
prompts wider than their fields leave nothing for the fields. For those,
the export can ask the configured AI provider to redraw the region - the
way a front-end developer would be handed the screen - and it is opt-in
per export: the **Ask the AI provider to lay out the regions the rules
could not place cleanly** checkbox of the export dialog, or `--ai-layout`
on the command line (`--provider` overrides `FORMSLANG_AI_PROVIDER`).

- **What is sent.** Only the *hard regions*: those with a control the
  rules pushed, wrapped, narrowed or relabelled, or with a Forms row of
  five or more controls. Flow regions (toolbars) and grids are never sent.
  For each: the region's id, title and size; each control's name, Forms
  kind, APEX type, geometry relative to the region, caption and the side
  Forms draws it on, the room the prompt takes, and the placement the
  rules produced with its flags. No column names, no code, no data, no
  other region. The request is in `ailayout.request()`, the instructions
  in `ailayout._SYSTEM`.
- **What comes back** is a plan on the same 12-column grid - rows of
  cells, each with `column`, `columnSpan`, `labelColumnSpan` and the
  label's side - validated before it is used: every control of the region
  exactly once and no other; columns 1..12; cells left to right, never
  overlapping; `labelColumnSpan` below `columnSpan`, at least 1 for a
  label left of the field. A plan that fails one check is rejected whole.
- **What it changes**: the grid cell, label side, `labelColumnSpan` and
  label alignment of the controls of those regions, on the one layout
  model the exporter and the preview share; the sequence numbers follow
  the new reading order. Nothing else - types, templates, defaults,
  regions, order of regions - is the assistant's to change. Each control
  it placed carries `placement: ai` and an approximation line in the
  report; `totals.placed_by_ai` counts them.
- **Fallback**: the rules' placement, always. `layout.ai_layout` in the
  manifest says what happened: `applied`, `cached` (the plan of an earlier
  export replayed), `not-needed` (no hard region), `offline` (the Echo
  provider), `rejected` (with the validation errors), `error` (the
  provider failed; the message). The enterprise egress policy is checked
  before any request, and a violation fails the export rather than
  silently keeping the placement the user asked to improve.
- **Determinism**: the plan is cached on the session
  (`ai_layout_plan:<page>`), keyed by a digest of the request; an export
  with an unchanged layout replays it without a request, and the preview
  shows the same page (`formui.render_html(..., ai_plan=...)`). A changed
  layout changes the digest and the plan is asked for again.

## Known limitations and unsupported mappings

- **Positions are kept to the column, not the pixel.** Forms units become
  rows and twelfths of a row: a control starts on the column its x rounds
  to and spans the columns its width rounds to, so two fields less than
  half a column apart share a column and the second moves right.
- **A row wider than twelve columns** is redrawn as two grid rows (or, with
  the AI layout assistant, as the provider proposes); Forms has no such
  limit.
- **Toolbars** flow inline in their rows; the exact spacing between
  toolbar buttons is not reproduced.
- **Captions right of or below a field** become labels above it:
  Universal Theme has no label template on those sides.
- **Initial values that are Forms expressions** (`$$DATE$$`, `:GLOBAL.x`)
  are not turned into computations; a default that is none of a list's
  choices is dropped, with a note.
- **Stacked canvases and secondary windows** become inline dialogs, but the
  code that shows them in Forms is not turned into dynamic actions.
- **Interactive Grids** are read-only until the developer confirms the
  block's DML; row count, paging and row height are the grid's own;
  a multi-record block without a query data source is not turned into a
  grid and no table is invented for it.
- **LOVs backed by record groups** are named, never generated.
- **Image, Bean Area, OLE, ActiveX, VBX, Sound, Tree, Chart and custom
  items** have no native component; a text placeholder keeps their place
  and the report lists them as unsupported.
- **Fonts, colours and visual attributes** of Forms items are not carried:
  Universal Theme decides the look.

## Reproduce

From the repository root, with FormsLang installed (`pip install -e .`):

```
# 1. Regression suite of the layout model, exporter and preview
python -m pytest -q tests/test_apexlayout.py tests/test_apexlayout_fidelity.py tests/test_apexlayout_geometry.py tests/test_ailayout.py tests/test_apexlang.py tests/test_formui.py

# 2. The preview: Forms reconstruction next to the planned APEX layout
formslang preview tests/fixtures/showcase/module.xml -o out/preview

# 3. The export (a fresh session from the module; deterministic once the session exists)
formslang export tests/fixtures/showcase/module.xml -o out/showcase --app-id 190 --alias showcase-layout --json
#    ... and, with a provider configured, the AI layout assistant on the hard regions only
formslang export tests/fixtures/showcase/module.xml -o out/showcase-ai --app-id 190 --alias showcase-layout --ai-layout --json

# 4. Validate, then import into a dedicated development application
#    (password from FORMSLANG_APEX_PASSWORD or the saved connection - never an argument)
formslang apex validate out/showcase/export/showcase-layout.apex.zip
formslang apex import   out/showcase/export/showcase-layout.apex.zip

# 5. Read the mapping report (written next to the ZIP, in the review folder)
python -c "import json;m=json.load(open('out/showcase/export/showcase-layout-review/apexlang-manifest.json',encoding='utf-8'));print(json.dumps(m['layout']['mapping_report']['totals'],indent=1))"

# 6. Render the page through ORDS as a temporary end user and inspect the HTML
python examples/verify/apex_render_check.py out/render 190:1
```

Step 6 is described in [apex-import-verification.md](apex-import-verification.md).
