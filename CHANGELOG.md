# Changelog

All notable changes to FormsLang are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] — 2026-09-04

The first stable release. Everything a Forms team needs to convert,
document, diff and version its modules -- and to hand the result to a
pipeline -- is in, and the shapes that matter (the CLI, the session file,
the export layout, the HTTP API of the local workbench) are now promised
stable within 1.x: what changes from here is additive, and every visible
change keeps landing in this file.

### Added

- **`formslang export <session.db>`** -- the headless twin of the
  workbench's *Export APEX 26.1* button: same exporter, same choices, same
  bytes. Deployment choices (`--app-id`, `--alias`, `--name`,
  `--workspace`, `--schema`, `--page`) are remembered on the session, so a
  second run with no flags rebuilds exactly what was reviewed; a flag
  overrides only what it names. Accepts a `.fmb`/`.xml` too, creating the
  session beside it like every other command. `--json` for tooling.
- **`formslang apex validate <zip>` / `formslang apex import <zip>`** --
  SQLcl driven from the command line, for CI. Target from `--connect` /
  `--user`, `FORMSLANG_APEX_CONNECT` / `FORMSLANG_APEX_USER`, or the
  workbench's Settings; password from `FORMSLANG_APEX_PASSWORD`, the
  connection saved from the workbench (OS credential store), or a hidden
  prompt -- never a command-line argument, and a runner with no password
  and no terminal fails at once instead of hanging on a prompt. Exit 0 on
  success, 1 when SQLcl fails *or* prints `APEXlang Compile Errors` with
  exit 0 (nothing imported), 2 when the command could not run. `--sqlcl`
  and `--timeout` for runners that just unpacked SQLcl.
- **Deterministic exports.** Two exports of the same session are now
  byte-identical, ZIP included: entries are written in name order with a
  fixed 1980-01-01 timestamp and one permission mask, and the
  application's session-state checksum salt is drawn once per session
  (from the OS CSPRNG) and kept, instead of once per export. This is what
  lets a pipeline rebuild what was reviewed, cache it, and diff two
  exports as two reviews rather than two clocks. Sessions carry a small
  `session_setting` table for this and for the last export's choices.
- **The export dialog shows the command line that reproduces it** --
  `formslang export <session> --app-id … --alias …`, kept in step with the
  fields as they are typed -- and pre-fills the previous export's choices;
  the Import dialog names the `formslang apex validate|import` twins and
  where the password goes. The manifest (`apexlang-manifest.json`) carries
  the same three commands under `cli` and a `reproducible: true` flag.
- **`docs/ci-cd.md`** and **`examples/ci/formslang-apex.yml`**: the
  pipeline shape (export → validate → import on `main`), what to commit,
  the exit codes, the secrets, the runner prerequisites and the known
  SQLcl gotchas -- the ground for the SQLcl `project`-based promotion
  flow that comes next.
- **`MultiLine="true"` Text Items export as `textarea`** (the keyword
  already verified live for Bean Areas) instead of a one-line
  `textField`; the parser now reads `MultiLine` into `Item.multi_line`.
  `Date`/`Number` items deliberately stay `textField` until
  `datePicker`/`numberField` have been through a live `apex validate`,
  because one unknown keyword fails the whole import.
- **Oracle Forms homes named by the installer are found.** After the fixed
  list, any child of `C:\Oracle` that carries a `jlib` folder is tried, in
  name order -- so a `C:\Oracle\FR1412` (Forms 14c) is detected with no
  `ORACLE_HOME` and no `--oracle-home`.
- **Multi-user mode as a saved setting.** The Settings screen carries an
  *Authentication* switch (`auth_enabled` in `config.json`, read once at
  start; `FORMSLANG_AUTH` still wins when set) with the status of the
  first Owner and an *Open terminal…* shortcut for `formslang auth
  bootstrap-owner`.
- **`docs/apex-import-verification.md`**: the repeatable procedure for
  proving an export on a live APEX 26.1 through ORDS -- the class of
  render-time defect `apex validate`/`apex import` cannot see.

### Changed

- The README is rewritten for 1.0: a CLI reference for every command, the
  versioning workflow for Forms *and* APEXlang in git, the CI/CD section,
  the complete environment-variable table and an architecture map that
  matches the package as it is.
- `formslang doc` in the README used a stale flag; every documented
  command line is now the one the parser accepts.
- The Settings hint for creating the first Owner used `--email`; the
  command takes the address positionally.

### Fixed

- **A hidden-label item 1 or 2 grid columns wide still failed to render**
  with `WWV_FLOW_GRID_LAYOUT.LABEL_COLUMN_SPAN_TOO_BIG` (`P1_ID_INTERNO`
  in the Demo All Elements showcase), even after 0.1.13. The exporter
  omitted `labelColumnSpan` for the `hidden` label template on the theory
  that a hidden label needs no room -- but Universal Theme's `Hidden`
  template still lays its (invisible) label out on the grid
  (`col col-#LABEL_COLUMN_SPAN_NUMBER#`), and APEX fills an unset
  `labelColumnSpan` from the page template's default (2 on every built-in
  Universal Theme page template) before checking it against `columnSpan`.
  A hidden label on a field spanning 1 or 2 columns therefore collided
  with that default exactly like an oversized real one. `_item_chunk` in
  `apexlang.py` now writes `labelColumnSpan: 0` for every hidden-label
  item -- a value the item-level column accepts -- which renders as
  `col-0` with the field at its full `columnSpan`. Verified by rendering
  every `{template, columnSpan, labelColumnSpan}` shape on a live APEX
  26.1 through ORDS, not just `apex validate`/`apex import`, which never
  catch this class of error. Side benefit: hidden-label fields no longer
  silently lose two grid columns to an invisible label.

## [0.1.13] — 2026-09-04

### Fixed

- **A page item could still export with `labelColumnSpan >= columnSpan`**,
  which APEX rejects only at render time (`WWV_FLOW_GRID_LAYOUT
  .LABEL_COLUMN_SPAN_TOO_BIG`) -- never caught by `apex validate` or
  `apex import`. `_reconcile_label` in `apexlayout.py` already caps this
  after `_place_row` settles an item's real grid span, but the exporter
  trusted `Placed.label_span` unconditionally at the point it wrote
  `labelColumnSpan`. `_item_chunk` in `apexlang.py` now re-clamps the
  span against the item's actual `columnSpan` right where it emits it,
  closing the invariant regardless of which upstream layout path set it.

## [0.1.12] — 2026-09-04

### Fixed

- **A lone field below a frame always claimed the full 12-column grid**,
  regardless of its real proportion to the page. `_arrange`'s chrome-less
  wrapper group for loose items (drawn below a canvas's first frame) sized
  its column arithmetic against its own tight bounding box -- self-
  referential for a group holding a single item, which then rounded up to
  the group's whole width every time. `_arrange`/`_place_row` now thread
  the real ancestor container's `x`/`width` down through that recursion,
  so a field's `columnSpan` is always proportional to the page it is
  actually on.
- **Fields on the same row could leave a dead grid column between them, or
  overflow past column 12.** `_place_row` derived `column` from the item's
  literal Forms `x` position, which reproduces Forms' incidental
  whitespace as a gap in the APEX grid and, on a crowded row, could hand
  out columns beyond 12. Column is now purely a running total of the
  row's own previous spans: items pack left to right with no gap, and a
  row with more boxes than columns wraps onto as many 12-wide grid rows
  as it needs instead of clipping.
- **A window Forms declares `WindowStyle="Dialog" Modal="true"` now
  exports as an Inline Dialog region**, the same verified template already
  used for a stacked canvas raised on demand. Previously only the
  stacked-canvas heuristic triggered it, so a small popup window (a
  "reajuste de preço" prompt, a confirmation dialog) exported as a plain
  Standard region indistinguishable from the main page.
- **A Forms toolbar's second rank of buttons collapsed onto the same row
  as the first.** The toolbar's flow layout sorted every button by
  position but only ever marked the very first one `startNewRow`; buttons
  Forms actually docked a few points lower (a second visual row) now
  cluster onto their own row, the same vertical-overlap clustering used
  for every other region.
- **A text field's `width` (in characters) was never written for a Point-
  based module with no recorded character cell** -- `PageLayout.chars()`
  returned `None` outright, so Universal Theme's default 100%-of-cell
  stretch applied to every text field on the page. It now falls back to
  the same per-coordinate-unit character-width estimate `build_layout`
  already uses for prompt room, and only returns `None` when there is
  truly no width to convert.
- `Window.modal`/`Window.style` (parsed from `Modal`/`WindowStyle`) added
  to the model so the exporter can read what Forms itself declared about
  a window, rather than infer it.

## [0.1.11] — 2026-09-04

### Changed

- **Showcase fixture (`tests/fixtures/showcase/`) rebuilt into a full
  live demo**, on top of its existing role as the layout/rules test
  bench: module parameters, a third detail block (audit trail) and a
  summary block over an aggregate view, two window-modal reajuste flow,
  and `demo_schema.sql` to seed a real `FORMSLANG` schema. Compiles
  clean in Oracle Forms Builder 14c (61/61 units, no errors) and runs
  end to end against Oracle APEX 26.1 after export.
- Added a dedicated Frame (`FR_IDENTIFICACAO`) that reproduces
  `WWV_FLOW_GRID_LAYOUT.LABEL_COLUMN_SPAN_TOO_BIG` with a squeezed row of
  abbreviated-prompt items, as a standing regression case for the
  `labelColumnSpan` capping added in 0.1.9 -- this class of error only
  surfaces at APEX render time, never in `apex validate`/`apex import`.
- README documents the full Forms Builder compile recipe (`frmxml2f`,
  `frmcmp`) including two silent-failure gotchas: a malformed registry
  `NLS_LANG` makes the database logon fail with `ORA-12705` and no
  `module.err`, and `frmcmp.exe` is a GUI-subsystem executable that
  PowerShell does not wait on unless launched with `Start-Process -Wait`.

## [0.1.10] — 2026-09-03

### Fixed

- **Every item's LOV attachment was silently dropped.** The parser read the
  attribute as `LOVName`, but Forms2XML actually emits `LovName` -- the
  lookup is case-sensitive, so it matched nothing on every real export and
  left `item.lov_name` empty. This broke the LOV edge in the dependency
  graph and in generated docs for every module ever parsed. The test suite
  didn't catch it because its own sample fixture carried the identical
  typo, so the assertion passed against the bug rather than the schema.
  Fixed in the parser and in every test fixture, and added a regression
  test that checks the attribute by name against `forms.xsd`.
- Fixed several Forms2XML syntax inaccuracies in the showcase fixture,
  found by round-tripping it through Oracle Forms Builder's own XML-to-Forms
  tool: `ListItemElement` needs `Index`/`Name`/`Value`, not an invented
  `Label`; `LOVColumnMapping` needs `Name`, not `ColumnName`; `Relation` is
  only a valid child of `Block`, never of `FormModule` directly; and
  `CompoundText`/`TextSegment` both require a `Name` attribute. None of
  these touched `parser.py` -- they were fixture-accuracy fixes only.

## [0.1.9] — 2026-09-03

### Changed

- **The exported APEX page now follows the layout of the original form.**
  Until now every block became one Standard region with one item per row,
  so a dense Forms screen came out as a long, unrecognisable column. The
  export now reads the geometry the .fmb records and builds the page the
  way the screen was laid out, with what APEX 26.1's Universal Theme
  offers: each content canvas is a Standard region titled like its window;
  a horizontal toolbar is a chrome-less region above it whose buttons flow
  inline; a stacked canvas raised on demand (`Visible=false`) is an Inline
  Dialog; a tab canvas is a Tabs Container with a region per tab page;
  every frame -- and every rectangle with a text caption on its top edge,
  the hand-drawn group box -- is a sub-region nested by containment; items
  are clustered into rows by their vertical position and given a
  `column`/`columnSpan` on the 12-column grid proportional to where they
  sat, two narrow controls painted side by side sharing one cell; loose
  items drawn below a frame are grouped so their order against the frames
  survives. Prompts sit where Forms drew them: a prompt on the Start edge
  (the default) is a label left of the field that claims the room the
  prompt took on the canvas (`labelColumnSpan`), a prompt on the top edge
  a label above, one on the end or bottom edge a floating label; an item
  the screen captions with nothing gets the hidden label template instead
  of a label invented from its name; a Forms `Required` item gets the
  required template; a text field keeps its width in characters.
  Boilerplate text survives too: a text drawn right before or right above
  an uncaptioned field is read as its prompt (how screens were captioned
  before Forms had prompts), and any other text -- bold headings, help
  paragraphs, column headings spanning several fields -- becomes a
  chrome-less static region placed where it was drawn. List
  Items and Radio Groups are exported as `selectList`/`radioGroup` fed by
  shared static LOVs built from the .fmb's choices (`lovs.apx`), instead
  of falling back to text fields. Items without a canvas or hidden in
  Forms become Hidden items under their block's home region; WebUtil's own
  block and canvas are skipped. A block shown as several records keeps its
  first row laid out and says so in the region comment (an Interactive Grid
  on the block's table is the next stage). Every keyword the layout uses
  was accepted by `apex validate` on APEX 26.1 before it was used, and the
  layout tree is written into the review manifest.
- The **APEX preview** now draws exactly that tree -- regions per canvas
  and frame, rows and 12-column cells, labels left of the field with the
  prompt's share of the cell, above it or hidden, boilerplate text where
  it was drawn, inline dialogs, tab pages, hidden chips, static LOVs --
  from the same layout engine the export uses, so the two can never
  disagree. Radio Groups and List Items are no longer flagged as
  approximations.

### Fixed

- The Settings sheet now has a **SQLcl path** field, so the "SQLcl was not
  found on PATH" import error -- which has always told the user to "set its
  path in Settings" -- can actually be fixed there, instead of only via the
  `FORMSLANG_SQLCL_PATH` environment variable or a hand-edited
  `config.json`. The field shows whether SQLcl is currently found, and is
  disabled (with an explanation) when the environment variable is already
  overriding it.
- A Forms editor/multi-line item exported as an APEXlang page item with
  `type: textArea`, which real Oracle APEX 26.1 does not recognize as a
  native item type -- it tried to resolve it as a plugin instead and failed
  the whole import (`PLUGIN_NOT_FOUND`). The correct, Oracle-confirmed
  keyword is lowercase `textarea`.
- A Forms *Display Item* marked Required was exported with
  `validation { valueRequired: true }`, which APEX's compiler rejects on a
  `displayOnly` item (`INVALID_PROPERTY` -- Display Only has no "Value
  Required" in Page Designer either), again failing the whole import.
  `valueRequired` is now emitted only for editable item types; the Forms
  fact is preserved in the item's comment (`required in Forms`).
- An import whose package failed to compile was shown as a green **OK**:
  SQLcl prints an `APEXlang Compile Errors` table, imports nothing, and
  still exits 0. That output is now recognised and reported as a failure
  (`Failed (SQLcl reported errors; nothing was imported)`), so the result
  matches what the workspace actually contains.
- On a machine that also has an Oracle Database home on `PATH`, SQLcl
  picked its OCI ("thick") JDBC driver for a plain `host:port/service`
  target and the connection died before reaching the database
  (`no ocijdbc23 in java.library.path`, `Incompatible version of
  libocijdbc`). FormsLang now starts SQLcl with its documented `-thin`
  option, so the pure-Java driver SQLcl ships is always used and a plain
  `host:port/service` connection string works as advertised.
- A crowded row could export a left-side label wider than the field's own
  `columnSpan` (e.g. `columnSpan: 1, labelColumnSpan: 4`), which APEX
  rejects **at page-render time** with
  `WWV_FLOW_GRID_LAYOUT.LABEL_COLUMN_SPAN_TOO_BIG` -- neither
  `apex validate` nor `apex import` catch it, only actually opening the
  page does. The layout engine sizes a left label's share of the cell
  before the row's final crowding is known; it's now capped once the row
  is laid out, and when there's no room left for a separate label column
  the item falls back to a floating label instead of an invalid export.

## [0.1.8] — 2026-09-02

### Added — direct export + import into a live APEX instance

- The **Export Oracle APEX 26.1** dialog has an **"Import into APEX right
  after building"** option: tick it, fill the connection, and one click
  builds the ZIP and runs SQLcl non-interactively (`apex import -input`)
  against that instance. The same connection form backs the
  **"Import to database…"** action on every past export, with a
  **"Validate only"** dry run. Credentials are supplied at that moment,
  per user: the password never touches argv or `config.json` -- it
  travels only over SQLcl's own stdin for that one run, and reaches the
  OS credential store only if the user checks **Remember**.
- SQLcl's binary path is resolved from `FORMSLANG_SQLCL_PATH`, then
  `config.json`'s `sqlcl_path`, then `PATH`.

### Changed — the visual preview draws what Forms draws

- Geometry is converted from the module's own `<Coordinate>` unit
  (points for most real modules, 1pt = 1.33px) instead of being read as
  pixels, so canvases are no longer squeezed to three quarters of their
  size; each canvas is drawn at real size, clipped the way Forms clips a
  canvas, inside its own scrolling frame.
- Prompts are painted outside the field, on the edge the `.fmb` attaches
  them to and anchored there with CSS (not a guessed width), honouring
  `PromptAttachmentEdge` (default **Start**, i.e. to the left -- the
  previous preview wrongly defaulted to Top and painted labels over the
  field above), `PromptAlign`/`PromptAlignOffset` along that edge, and
  `PromptAttachmentOffset` as the gap from the field.
- A tabular block's items paint as many instances as `ItemsDisplay`
  states (falling back to the block's record count), so audit fields
  that Forms shows once no longer run one ghost copy per record over the
  neighbouring block.
- Each item is drawn in its own bevel, fill, font and colour -- straight
  off the `.fmb`, through its `VisualAttribute` when it names one, with
  the current record's own `RecordVisualAttributeGroupName` on its first
  instance -- instead of every control looking like flat, identical
  boxes.
- A canvas's boilerplate (frames with their title, rectangles, lines,
  text and image placeholders) is drawn under the items, in the same
  bevels, fonts and colours as the `.fmb`, instead of being invisible.
- Radio Group buttons are painted at each button's own recorded
  position, never as one box for the whole group; iconic toolbar buttons
  show a glyph, not their Forms label; disabled items are dimmed.
- A canvas that belongs to a window is wrapped in that window's title
  bar, with its horizontal toolbar canvas docked above the content
  instead of listed as an unrelated canvas of its own.
- Buttons, check boxes, radio groups and list items show their Forms
  `Label`/choices; items with `Visible="false"` are listed instead of
  drawn.
- The APEX side now looks like the Universal Theme page the export
  builds: one Standard region per block (collapsible), floating labels,
  buttons in the region header, hidden-in-Forms and tabular blocks
  called out with a note.

### Fixed

- APEX labels for buttons and check boxes now come from the Forms
  `Label` (the caption Forms actually paints) before falling back to the
  title-cased item name -- both in the exported APEXlang and the preview.
- Long underscored field labels (raw Forms prompts like
  `ATSF_101ENDERECO_COMPLEMENTO`) no longer blow out the fixed-width
  Doc/Diff comparison layout.

## [0.1.7] — 2026-09-02

### Added — syntax highlighting on the APEX side of the diff pane

- The APEX code pane in the review screen (`<textarea id="out">`) is no
  longer plain text. A transparent-text `<textarea>` now sits on top of a
  colorized `<pre>` fed by the same tokenizer already used for the
  read-only Forms pane (`hlLine`), kept in sync on every keystroke and on
  scroll. Both sides of the diff are colorized PL/SQL now, not just one.

### Added — read-only visual preview: Forms UI vs. APEX default mapping

- **`formslang preview`** (CLI) and a new **Preview** button in the
  workbench (`/api/preview`, `formslang/formui.py`) render a self-contained
  HTML page showing every Forms canvas as an absolutely-positioned mockup
  next to the APEX page it becomes, region by region, using the exporter's
  own `apexlang._item_type()` -- the same function `formslang export`
  uses, so the preview can never drift from what an actual export
  produces. A coverage summary calls out how many items have a confirmed
  mapping versus an approximated one (falls back to a text field), and
  which items have no recorded position or sit on an unknown canvas, so a
  reviewer can confirm the *whole* form -- interface included, not just
  its trigger logic -- is accounted for.
- By design there is no picker here: the preview shows only the automatic
  default mapping. Substituting a different APEX item type for a Forms
  object is a decision made later, in APEX Builder, after export.
- `formslang/model.py` now tracks item and canvas pixel geometry
  (`x`/`y`/`width`/`height` on `Item`, size/viewport on the new `Canvas`
  dataclass) -- read from the same Forms2XML attributes already ingested,
  used only to drive this preview. Font and color remain out of scope, as
  before.
- Confirmed one additional APEXlang keyword against the vendored 26.1
  template project: Forms Check Box now maps to `checkbox` instead of
  falling back to `textField`. Radio Group and List Item stay on the
  `textField` fallback -- no matching keyword could be confirmed in the
  templates, and guessing one risked shipping an export that fails to
  compile.

## [0.1.6] — 2026-09-01

### Added — HTML technical documentation and structural diff

- **`formslang doc` / `formslang diff`.** `formdoc` renders self-contained
  HTML technical documentation for one module (blocks, items, triggers,
  program units, LOVs, record groups, relations). `formdiff` compares two
  versions of the same module: added/removed/modified entities by name,
  property changes via reflection over the model dataclasses, and code
  changes as `SequenceMatcher` hunks (`autojunk=False`, so short repeated
  PL/SQL lines like `END IF;` are never dropped from the match).
- Wired into the workbench HTTP API (`/api/doc`, `/api/diff`) and the
  browser UI (**Doc** / **Diff** buttons in the header). The module
  picker gained an options object so it can be reused to pick a diff
  target without showing the upload dropzone meant for opening a module.
- v1 scope: name-only entity matching, no rename detection -- a renamed
  entity shows as remove+add. The report is read-only; an interactive
  hunk-by-hunk merge is not built yet.

### Added — per-test-case execute/pass/fail tracking

- Test cases now carry a `run_state` (`not_run`/`pass`/`fail`/`blocked`)
  alongside the existing reviewer accept/reject decision. The two are
  deliberately independent: a case can be accepted but never run, or run
  and failed while still pending review. `Store.record_test_run()`
  persists the result; the review screen gets a second Pass/Fail/Blocked
  row per case, and `testspec` reports executed/passed/failed counts
  alongside the reviewed/pending ones.

### Added — CI

- A GitHub Actions workflow now runs the full test suite on Linux and
  Windows across Python 3.10-3.13, plus a separate ruff lint job.

### Changed

- `formslang/ui.py` -- one ~1880-line raw string holding the whole
  workbench single-page app -- was split into `formslang/ui/{shell,auth,
  projects,conversion,review,validation,settings,shared,formdoc}.py`,
  one module per concern. Zero behaviour change: the reassembled page
  hashes byte-for-byte identical to the pre-split constant.
- `FORMSLANG_AUTH` still overrides multi-user mode outright when set,
  but with it unset the choice saved from the Settings screen now
  persists to `config.json` and survives a restart. The desktop toggle
  to flip this from the UI is still pending.

### Fixed

- A race in `AuthStore.rate_limit_record_failure`: two concurrent login
  failures for the same key could both read no existing row and both
  try to `INSERT`, tripping the unique constraint instead of recording
  the failure. It now uses the same immediate-transaction pattern as
  every other read-modify-write method in that file.
- Windows CI runners rewrote the vendored QR encoder's LF endings to
  CRLF on checkout, changing its bytes and failing the pinned-hash test
  on Windows only; `.gitattributes` now forces LF checkout everywhere.

## [0.1.5] — 2026-08-31

### Fixed

- **A converted trigger could carry an empty verdict.** A task's catalog
  verdict is now always one of `rules.VERDICT_ORDER` -- never the empty
  string -- closing a gap where an unexpected value could slip past
  `classify_trigger`/`classify_builtin` and show up unlabeled in the
  workbench and in every export.

### Added — wall-clock performance instrumentation

- **`formslang/telemetry.py`.** A stdlib-only `stage()` context manager
  records duration, item count and outcome for each pipeline stage
  (parse, task-build, convert, export). On failure it records only the
  exception's class name, never `str(exception)` -- an error message can
  quote source, a prompt or a stack frame, and none of that belongs in a
  timing log. `percentile()`/`summarize()` reduce a run's stage samples to
  p50/p95/count with no third-party dependency.

### Added — resumable, cancelable conversion runs

- A `convert` run now persists its progress to a `job_run` row in the
  session's own SQLite file as it goes, instead of only living in memory
  for the duration of one process. Reopening a session after a crash or a
  closed terminal picks the run back up where it left off instead of
  starting over; a new cancel endpoint stops a run in flight; and an
  orphaned run (the process that owned it is gone) is detected and
  reported rather than left silently "in progress" forever.

### Added — synthetic golden-corpus regression suite

- **`tests/fixtures/corpus/{tiny,small,medium,large,pathological}`.** Five
  versioned, 100% synthetic Oracle Forms fixtures -- no client data, no
  real Form, ever -- sized from a single trigger up to a 60-block, 480-edge
  dependency graph, plus a `pathological` tier purpose-built for a
  circular block dependency, an unresolvable dynamic `GO_BLOCK` target, a
  cp1252-mojibake `Prompt`, and a 200+ line PL/SQL body. `tiny`/`small`/
  `pathological` are hand-authored; `medium`/`large` are built by
  `tests/fixtures/generate_corpus.py` (no randomness, run once by hand) so
  a 200+ object fixture never silently drifts from what it claims to
  cover. Full layout in `tests/fixtures/README.md`.
- **`tests/golden.py`.** Runs each tier through the real pipeline --
  parse, task queue, dependency graph, an offline `EchoProvider` proposal,
  and a real `Store.export()` -- and reduces the result to deterministic
  JSON, stripping only the two fields that vary between two runs on two
  machines (an export timestamp and a session's `created_at`).
- **`tests/test_golden_corpus.py`.** Fails with a readable line-level diff
  the moment a tier's committed golden stops matching what the pipeline
  produces today -- verified by deliberately mis-classifying
  `WHEN-VALIDATE-ITEM` in `rules.py` and confirming the `small`/`medium`
  tiers failed with the exact verdict that moved, then reverting. A
  second test proves the pipeline is actually deterministic: the same
  tier built twice in one run is byte-identical.
- **`tests/update_golden.py`.** The only sanctioned way to change a golden
  file: always prints the diff first, always requires an interactive `y`
  (or an explicit `--yes`) before writing, is never imported by a test and
  never invoked by CI -- no CI configuration exists in this repository.

## [0.1.4] — 2026-08-31

### Added — sensitive-data scanning and enterprise egress policy

- **Sensitive-data scanner** (`formslang/sensitive.py`). Every unit is
  scanned deterministically -- no AI -- for credentials (`IDENTIFIED BY`,
  the Forms `LOGON(...)` built-in, `CONNECT user/pass@db`, a password
  assigned to a variable, API-key-shaped strings), CPF/CNPJ
  (check-digit-validated), contact details and financial data (card
  numbers Luhn-validated). CPF/CNPJ, contact and financial matches are only
  reported inside string literals or comments, where real client data
  actually lives; credentials are scanned everywhere, including comments.
  A finding never carries the value it matched -- only a redacted excerpt
  (first and last character, everything between masked) -- in the stored
  analysis, in `/api/state`, and in the new compliance export. Shown next
  to risk and behaviour in the workbench: a list-row marker, a header
  badge, and a "Sensitive data found" detail block.
- **Enterprise egress policy** (`formslang/policy.py`,
  `FORMSLANG_ENTERPRISE_MODE=1`). Classifies every provider's traffic as
  NONE / LOCAL / CLOUD by the effective host it would call -- not by
  whether its credential is CLI- or API-key-supplied, since that axis
  conflates the two (`claude_cli`/`codex_cli` are CLOUD, a loopback
  `ollama` is LOCAL). With enterprise mode on, a CLOUD-egress provider is
  refused outright at every point that could start a request: the
  provider picker marks it unavailable with the reason, saving Settings
  with one selected is refused, and starting a conversion run is refused
  -- enforced once, in `ai.build_provider()`, the chokepoint every
  production call path shares.
- **Compliance export** (`Store.export_compliance`). Every export now
  writes `compliance.md` beside `tests.md` in the review directory (never
  inside the APEX ZIP, which stays APEX-artifacts-only): session and
  timestamp, whether enterprise mode was active, the providers that
  answered a proposal and their egress class, totals of findings by
  category, and the per-unit findings with line and redacted excerpt.

Covered by `tests/test_sensitive.py`, `tests/test_policy.py`, and
`tests/test_store_compliance.py`.

## [0.1.3] — 2026-08-31

### Added — multi-user auth, RBAC and mandatory MFA

- **Organizations, roles and sessions** (`formslang/authstore.py`,
  `docs/auth-multitenancy-design.md`). Owner / Admin / Developer / Viewer
  roles, per-organization membership, scrypt password hashing, and
  session tokens with CSRF and Origin/DNS-rebinding protection on every
  mutating request. Single-user local mode (no `auth_store`) is untouched
  -- the served page is byte-for-byte identical to before when auth is
  off.
- **Project registry** (design doc §8-§9): registration, adoption and
  path containment so a session can only reach the `.session.db` files
  its organization actually owns -- a project id from another
  organization or one that does not exist both answer 404, never 403, so
  existence is never leaked across a tenant boundary.
- **Mandatory TOTP MFA** (design doc §7, RFC 6238). Every Owner and Admin
  account must confirm a TOTP enrollment before it reaches a normal
  session; the raw secret never touches the SQLite file -- it lives in
  one OS credential-store entry per user
  (`FormsLang:mfa-totp:<user_id>`), and verification fails closed if the
  vault is unreachable. Ten single-use recovery codes are issued once at
  confirmation and hashed at rest. A browser-side overlay
  (`formslang/authui.py`) drives enrollment (QR + manual key), the
  per-login code step, and the one-time recovery-code display, with a QR
  encoder vendored from `qrcode-generator` 1.4.4 (MIT, hash-pinned) so
  enrollment makes zero external network requests.
- **Assisted password reset** (design doc §7.5): an Admin may reset a
  Developer or Viewer, an Owner may reset anyone except another Owner --
  that path is `formslang auth reset-owner [--clear-mfa]`, a host-CLI-only
  command for when local machine access to the FormsLang install *is* the
  authentication. A reset token is single-use, expiring, and a bogus,
  expired, or already-spent one gets the same generic refusal, so a
  caller can never use it to enumerate accounts; redeeming one revokes
  every existing session for the account without starting a new one.
- **Response hardening**: every response now carries `Cache-Control:
  no-store`, `X-Content-Type-Options: nosniff`, `Referrer-Policy:
  no-referrer` and a CSP with no `unsafe-eval`.

Covered by 74 new tests (`tests/test_mfa.py`, `tests/test_password_reset.py`,
`tests/test_workbench_mfa.py`, additions to `tests/test_cli_auth.py`) on
top of the existing auth suite. One check has no automated form: a real
authenticator app scanning the real rendered QR code. That manual
two-device smoke test is documented as a checklist in
`docs/auth-multitenancy-design.md` §12a and has not been run against this
build yet -- the roadmap item in `README.md` stays unchecked until it has.

## [0.1.2] — 2026-08-31

### Fixed

- **A running batch no longer looks stalled.** The workbench polled
  `/api/job` every 700ms during a run but only re-read the real task and
  proposal state once the whole queue finished, so the header's
  "converted N/M" count and an already-selected unit's detail panel stayed
  frozen at their starting values for the entire run -- units that had
  already converted successfully still showed "No proposal yet". The
  screen now pulls the real state in as soon as the server reports another
  unit landing, not only at the end.

## [0.1.1] — 2026-08-31

### Added — migration analysis

- **Migration risk** (`formslang/risk.py`). Every unit is scored
  LOW / MEDIUM / HIGH / CRITICAL from the constructs actually found in its
  body, deterministically, with the evidence behind every point. A different
  question from the conversion mode (*what does it cost?*) and from AI
  confidence (*how sure is the model about this draft?*). The scoring
  formula, weights and thresholds are published in `docs/risk-model.md` and
  printed on screen next to the score.
- **Behaviour classification** (`formslang/behavior.py`).
  PRESERVED / CHANGED / UNCERTAIN, next to the confidence indicator. Absence
  of evidence is never PRESERVED, and an AI opinion is accepted only when it
  moves the answer away from PRESERVED — the model can make this more
  conservative, never less.
- **Migration classes in the catalog** (`formslang/rules.py`): every entry
  now carries DIRECT_EQUIVALENT, SERVER_SIDE_REPLACEMENT,
  CLIENT_SIDE_REPLACEMENT, ARCHITECTURAL_REDESIGN, MANUAL_REVIEW,
  UNSUPPORTED or NOT_REQUIRED. `NOT_REQUIRED` is kept apart from
  `UNSUPPORTED` on purpose: `SYNCHRONIZE` disappearing is not a gap in APEX.
- **One analysis pass per unit** (`formslang/analysis.py`), stamped with an
  engine version that fingerprints the catalog rows and scoring weights.
  Change one risk number and every stored analysis is flagged stale rather
  than being served silently under older rules.
- **Dependency graph** (`formslang/depgraph.py`): forms, blocks, items,
  triggers, program units, packages, procedures, tables and views, LOVs,
  record groups, relations, alerts, timers, reports, menus, PL/SQL
  libraries, globals, parameters and external calls, with inbound and
  outbound edges, transitive reach, and risky dependencies highlighted.
  A structured explorer beside the code — `GET /api/deps`.
- **Test case generation** (`formslang/testspec.py`): specifications written
  from the *original Forms body*, not from the generated APEX — normal path,
  boundaries, null handling, transaction behaviour, side effects, exception
  paths and regression scenarios. Each case is marked FORMS_BEHAVIOR,
  MODERNIZATION or NEEDS_CONFIRMATION, and reviewed per case as accepted,
  rejected or needs-modification. Case ids are content-hashed, so a decision
  survives regeneration when the wording has not changed. FormsLang writes
  these specifications and does not run them; the screen says so.
  `GET /api/tests`, `POST /api/test-decision`, and a `tests.md` in the
  export.
- **Project view** (`formslang/dashboard.py`, `GET /api/dashboard`, key `d`):
  totals, conversion modes, decisions, risk and behaviour distributions,
  blockers, the highest-risk units, the Forms features APEX has no
  equivalent for and where the dependencies pile up. One readiness score,
  printed next to the exact arithmetic that produced it — five weighted
  components, each measured over *every* unit in the session, so a unit
  nobody analysed lowers the score instead of quietly leaving the
  denominator. Blockers are deliberately excluded from the score.
- `docs/risk-model.md`: the whole scoring model, weight by weight.

### Changed

- **FormsLang is now Open Source under the Apache License 2.0.** The
  previous source-available license is replaced by `LICENSE` (Apache-2.0)
  and `NOTICE`. Created by Geraldo Viana Jr; maintained under the
  B2DEV-TECH organization.
- The AI conversion prompt now requires English for every human-readable
  string (notes, open questions, code comments), regardless of the language
  of the source module.

### Added

- **Exports panel**: an `Exports` button in the workbench lists every
  APEXlang ZIP built so far (newest first) with a *Show in folder* action
  that selects the file in the OS file manager; the same panel opens
  automatically after each successful export. New endpoints
  `GET /api/exports` and `POST /api/exports/open`.
- Community files: `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md` (Contributor
  Covenant 2.1), `SECURITY.md` (private vulnerability reporting),
  `AUTHORS.md`, this `CHANGELOG.md`.
- A pre-flight check refuses to start a conversion run when the selected
  HTTP provider has no API key, with a message that says exactly how to
  fix it (open Settings, paste a key, or pick a CLI provider).
- **Progress you can watch.** A conversion through a CLI provider takes 15
  to 60 seconds per unit, and the screen now accounts for every second of
  it: a moving bar under the top bar, a strip naming the unit being read
  with the provider and elapsed time, a spinner on the queued units in the
  list, and an overlay on the APEX pane of the unit whose answer is about
  to land. A unit merely waiting in line keeps its editor and gets an
  "in queue · N ahead" tag instead — a run over fifty units must not lock
  fifty panes. `GET /api/job` reports `current`, `current_id`, `queue` and
  `provider` for it, in the same shape whether or not a run is live. A run
  started before the window was opened is picked up on load. Opening a
  module, building the export ZIP and testing a provider show their own
  busy state.

### Fixed

- Failed conversions are now counted and reported honestly: the job tracks
  `failed` and `last_error`, and the workbench toast says
  "N of M conversion(s) failed — [reason]" instead of claiming success.
- A refused POST (403 wrong host, 415 wrong content type) now drains the
  request body before answering. Without it the connection was reset on
  the way back and the client saw a dropped connection instead of the
  status it had just been sent.

### Security

- **API keys are no longer written to `config.json`.** The credential now
  goes to the operating system's own store — Windows Credential Manager,
  the macOS Keychain, or the Secret Service (libsecret) on Linux — through
  the new `formslang.secrets` module. No third-party package is involved:
  `ctypes` on Windows, and on the others the tool the platform already
  ships, given the secret on stdin so it never appears in a process
  listing.
- **No silent fallback to plaintext.** Where the platform offers no
  credential store, saving a key is refused with *"Secure credential
  storage is not available. Use an environment variable instead."* and
  nothing is written at all, so a refused save cannot leave a
  half-applied settings file. The Settings screen disables the key field
  and shows the same message before the user types anything.
- A key left in `config.json` by an earlier version is still honoured, so
  an upgrade locks nobody out; it is moved into the credential store and
  stripped from the file the first time the workbench starts.
- The README's privacy claims now match what the code does: AI conversion
  requests go only to the provider the user selected, and a new privacy
  notice states that proposals may include the selected Oracle Forms
  source code and that hosted API and CLI providers process it under
  their own account, retention, and data-processing policies.

## [0.1.0] — 2026-08-27

### Added

- First public release: Forms2XML parsing, conversion workbench (review
  UI with approve / reject / needs-work verdicts), AI-assisted conversion
  via API providers (Anthropic, OpenAI, Azure OpenAI, Google, Ollama) and
  CLI providers (Claude Code, Codex), offline Echo mode, APEXlang 26.1
  export ZIP, Windows desktop app (Tauri) with MSI and NSIS installers.

[Unreleased]: https://github.com/B2DEV-TECH/FormsLang/compare/v0.1.8...HEAD
[0.1.6]: https://github.com/B2DEV-TECH/FormsLang/compare/v0.1.5...v0.1.6
[0.1.5]: https://github.com/B2DEV-TECH/FormsLang/compare/v0.1.4...v0.1.5
[0.1.4]: https://github.com/B2DEV-TECH/FormsLang/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/B2DEV-TECH/FormsLang/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/B2DEV-TECH/FormsLang/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/B2DEV-TECH/FormsLang/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/B2DEV-TECH/FormsLang/releases/tag/v0.1.0
