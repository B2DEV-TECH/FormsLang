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
2. **Columns.** Within a row, left-to-right order is the column order. An
   item's `columnSpan` is its share of the parent's width, in twelfths,
   at least one column; the row is normalised so its spans never exceed 12.
3. **Label space.** A caption drawn left of the field takes part of the
   item's own columns (`labelColumnSpan`), always fewer than the item's
   `columnSpan` - the class of defect `LABEL_COLUMN_SPAN_TOO_BIG` is covered
   by a regression test and checked in the APEX dictionary after import. A
   caption above the field uses the `-above` label template; a caption the
   theme has no side for (right, below) or a row too crowded to give the
   label its own columns uses the floating label template, and the report
   records that as an approximation. An item with no caption gets a hidden
   label with `labelColumnSpan: 0`.
4. **Nested groups.** A frame becomes a sub-region of its canvas region
   (slot `subRegions`); a frame inside a frame nests the same way. Items
   drawn beside or below a frame, in the parent group, go to a derived row
   region (`<parent>-row-N`, `blank-with-attributes`, no header) so the
   vertical order of the screen survives; the report lists derived regions
   but does not count them as Forms groups.
5. **Widths and heights.** A `textarea` gets `width` and `height` in
   characters and rows from the item's box; grid columns get `width` in
   characters; every other item keeps its `columnSpan` as its width.
6. **Order.** Sequence numbers follow the reading order of the screen: the
   row, then the column inside the row.

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
| Horizontal / vertical toolbar canvas | `blank-with-attributes` region; controls flow inline in their rows and order | order, rows, captions | yes | - | *approximation*: controls keep order and rows, not exact positions |
| Stacked canvas | `inline-dialog` region holding its content | title, content, order | yes | - | *approximation*: shown on demand in Forms; opening the dialog needs a dynamic action the developer adds |
| Secondary window (its content canvas) | `inline-dialog` region | title, content, order | yes | - | same as the stacked canvas |
| Tab canvas | `tabs-container` region | order of tab pages | yes | - | - |
| Tab page | `standard` region in the `tabs` slot of its tab canvas, titled from the tab label | label, order, content | yes | - | - |
| Frame with caption | `standard` sub-region titled with the caption; `t-Form--stretchInputs` when it holds form items | caption (once, as the region title - never repeated as a label), nesting, content order, geometry | yes | - | - |
| Frame whose only content is one multi-record block | the block's Interactive Grid takes the frame's place and caption | caption, position | yes | - | no empty wrapper region is written |
| Boilerplate text | `blank-with-attributes` static content region with the text; a prompt-like text next to a field becomes that field's label | text, position | yes | - | *approximation* when a text is read as a field's prompt (reported) |
| Rectangle with a text inside | `standard` region titled with the text | text, position | yes | - | - |
| Text Item, single line | `textField` page item | label text, caption side (`optional`/`required`, `-above`, `-floating`), required, max length, width (`columnSpan`), label share (`labelColumnSpan`), case restriction (`textCase`), enabled = false as `readOnly`, hint + tooltip as help text, format mask (in the comments) | yes | - | right/below captions float inside the field; a crowded row floats the label |
| Text Item, MultiLine (or Text Editor / Text Area) | `textarea` page item | as above, plus `width` and `height` from the item box | yes | - | rows come from the box height in units |
| Text Item, data type Date / Datetime | `datePicker` page item with `formatMask` from the Forms format mask | as Text Item, plus the format mask as a native property | yes (renders as `<a-date-picker format="DD/MM/YYYY">`) | - | - |
| Text Item, data type Number | `numberField` page item with `formatMask`; `numberAlignment: end` when Forms right-justifies it | as Text Item, plus format mask and alignment as native properties | yes (renders with `data-format` and right alignment) | - | - |
| Display Item | `displayOnly` page item | label, side, width, help | yes | - | `valueRequired` is not a property of a display-only item |
| Check Box | `checkbox` page item; `useDefaults: false`, `checkedValue` / `uncheckedValue` from the item | label, values, width, required | yes | - | - |
| Radio Group | `radioGroup` page item fed by a shared static LOV built from the radio buttons; `noOfCols` from how Forms lays the buttons out; `displayNullValue: false` | labels, values, buttons per row, no extra empty choice | yes | - | *approximation* when the .fmb declares no return values: the labels stand in and the report says so |
| List Item (poplist, T-list, combo box) | `selectList` page item fed by a shared static LOV from the list elements | labels, return values when the .fmb declares them, required, width | yes | - | a T-list or combo box renders as a select list; undeclared return values are flagged |
| Item with a record-group LOV attached | the item's native type above; the Forms LOV is named in the item's comments | everything of the item type | yes | - | **no LOV query is generated** - binding a LOV is functional review, never invented |
| Push Button | `button` in the region, `@/text` template, at the row and column Forms draws it | label, order, position | yes | - | buttons on a toolbar flow inline (*approximation*) |
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
  grid placement (`startNewRow`, `column`, `columnSpan`, label share) or the
  grid column index;
- **rule**: the sentence that says which mapping applied;
- **preserved**: the properties carried over;
- **approximations** and **unsupported**: what could not be carried as is;
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
| 72 visible controls (items, buttons, grid columns) | 48 | 24 | 0 |
| 21 Forms groups (canvases, frames, tab pages, blocks, boilerplate) | 15 | 6 | 0 |

The 24 approximations are: 14 toolbar controls that flow inline, 7 labels
that float inside their field (crowded row, or a right/below caption), 2
prompts read from boilerplate text next to the field, 1 radio group whose
.fmb declares no return values. The 6 group approximations are the toolbar
canvas, the three Interactive Grids (rows and paging are the grid's own,
editing off) and the two on-demand canvases turned inline dialogs. Six
hidden items are listed; four of them are hidden grid columns. Ten derived
row regions keep vertical order and are not counted as groups.

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

Not done, and not claimed: a pixel comparison of screenshots, a browser
run at a narrow viewport (Universal Theme's stacking is documented, not
measured here), and any check on a real customer module - the showcase is
synthetic by design.

## Known limitations and unsupported mappings

- **Exact positions are not kept.** Forms pixels become rows and twelfths
  of a row; two fields of different widths in the same row keep their
  relative widths, not their pixel widths.
- **Toolbars** flow inline in their rows; the exact spacing between
  toolbar buttons is not reproduced.
- **Captions right of or below a field** float inside the field:
  Universal Theme has no label template on those sides.
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
python -m pytest -q tests/test_apexlayout.py tests/test_apexlayout_fidelity.py tests/test_apexlang.py tests/test_formui.py

# 2. The preview: Forms reconstruction next to the planned APEX layout
formslang preview tests/fixtures/showcase/module.xml -o out/preview

# 3. The export (a fresh session from the module; deterministic once the session exists)
formslang export tests/fixtures/showcase/module.xml -o out/showcase --app-id 190 --alias showcase-layout --json

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
