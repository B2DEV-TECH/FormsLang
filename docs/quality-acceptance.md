# Quality acceptance for existing features

This page records, per release, what the automated checks proved and what
they did not. A passing test suite does not prove that every Oracle Forms
application can be migrated faithfully; each section says where real
Forms/APEX testing still has to happen. The release steps that produce
these sections are in [releasing.md](releasing.md).

## 1.2.1 verification

- Windows, Python 3.13: 945 tests passed; one symlink test skipped because
  this Windows token cannot create symlinks. Ruff passed.
- The showcase recovers both the package specification and body (59 review
  units) and reopens successfully.
- Chrome headless: header actions fit at 1100, 1280 and 1380 px; Doc and
  Preview open; the export dialog builds a ZIP; a manual approval survives
  page reload. No JavaScript page errors were observed.
- The frozen engine reports 1.2.1, exports the showcase and reproduces the
  same ZIP bytes when reopening the session.
- These checks do not certify a clean-machine installer upgrade or real
  Forms/APEX runtime equivalence. Those remain distinct acceptance tasks.

## 1.2.2 verification (2026-09-06)

Tested binary source: `6fc9f5c2f114244fa3b6b3742bb78a6b99debd91`. The
release-documentation commits that followed do not change the tested
binaries. The release is published for download and manual testing; real
Forms/APEX runtime validation is still pending, and nothing here claims
Forms/APEX equivalence.

- [CI run 34010752073](https://github.com/B2DEV-TECH/FormsLang/actions/runs/34010752073):
  949 tests passed in each of eight Windows/Linux and Python 3.10–3.13
  combinations; Ruff and deterministic showcase export also passed.
- [Installer acceptance 34010753174](https://github.com/B2DEV-TECH/FormsLang/actions/runs/34010753174):
  clean installation of 1.2.1 followed by upgrade to 1.2.2 passed separately
  for NSIS and MSI on disposable hosted Windows runners. Both retained
  the saved approval among 59 review units, preserved the source, produced
  repeatable exports and started the installed native window and engine.
  This does not exercise every interaction inside the native webview.
- The showcase `tests/fixtures/showcase/module.fmb` was converted with
  Oracle Forms 14.1.2. Comparison with the reference XML found
  record-spacing differences in three blocks, tracked in
  [issue #1](https://github.com/B2DEV-TECH/FormsLang/issues/1); runtime
  visual acceptance remains pending.
- Diff identifies package specification and body separately; three
  regression tests cover edits, removal and reordering of same-name units.
- Still pending: import into a separate, disposable APEX application and
  runtime comparison against the Forms module. Nothing was imported and no
  test user was created for this release.

Exact tested installer SHA-256 digests:

```text
FormsLang_1.2.2_x64-setup.exe
340CEC67C51FF9BBCC59704B4AA403B48671581AF5920BC589DD7AB841748D16
FormsLang_1.2.2_x64_en-US.msi
8E1F44C4057E9315041E1C4692DF4E125745AF9A6E0327F3AD41254F6069ED6E
```

## Import verification on `main` (2026-09-08)

The first execution of [APEX verification](apex-import-verification.md) on any
machine. Engine at commit `e8fe949`; `9327d87` on top changes documentation
only. Target: Oracle AI Database 26ai Free 23.26.3.0.0, APEX 26.1.0, SQLcl
26.2.2.0, ORDS on `localhost:8080`, local workspace `FORMSLANG`, disposable
application 190122. No customer artefact was involved. The import and
dictionary steps used the workspace's single existing account; the render and
submit steps each created one temporary end user and removed it in a
`finally`.

Source: `tests/fixtures/showcase/module.xml`, its six `WHEN-VALIDATE-ITEM` and
`WHEN-VALIDATE-RECORD` units approved with a `raise_application_error` body,
exported through `export_apexlang`. Package SHA-256
`a9241052afc885f8e074673af8557ddc915e11ab5c0540e5eb789cd59b17de8b`.

Steps 1 to 5 passed and step 6 has not been run. The authenticated render and
the browser submit were completed later the same day, against the same
application, and are recorded below.

- **Import (step 2).** `formslang apex import` reported `Importing application
  ID: 190122 into workspace: FORMSLANG`, `Import successful.` and `Result: OK`,
  with no `APEXlang Compile Errors`.
- **Dictionary (step 3).** Application 190122 holds 3 pages, 42 items, 32
  regions, 4 processes and **6 validations**. All six are of type `PL/SQL
  Error`, sequenced 10 to 60, with no condition and no button restriction —
  that is, enabled and evaluated on every submit. The four item-level rules
  carry the expected `associated_item` (`P1_VL_PRECO`, `P1_FK_CATEGORIA`,
  `P1_CD_BARRA`, `P1_FK_FORNECEDOR`) and display
  `INLINE_WITH_FIELD_AND_NOTIFICATION`; the two record-level rules carry no
  item and display `INLINE_IN_NOTIFICATION`. The stored code shows the page
  prefix rewritten from `:P0_` to `:P1_`.
- **Label span (step 3).** The `grid_label_column_span >=
  nvl(grid_column_span, 12)` query returned no rows.
- **Rule execution (step 5, in the database).** In a session opened with
  `apex_session.create_session(190122, 1, 'FORMSLANG')`, the code as stored in
  `apex_application_page_val` for `P1_VL_PRECO` was executed twice through
  `apex_exec.execute_plsql`. With the item empty it raised `ORA-20001:
  VL_PRECO e obrigatorio (regra vinda do Forms).`; with the item set to
  `19.90` it completed silently. The rule that came from the Forms trigger
  rejects and accepts, in APEX, the same values it rejected and accepted in
  Forms.
- **Render (step 4).** ORDS answered both `f?p=190122:1` and
  `/ords/r/formslang/formslang-a4/` with HTTP 200 and served the application's
  own login page (`flow: 190122`, no `ORA-` and no `ERR-`); the authentication
  scheme is `Oracle APEX Accounts`.
  `examples/verify/apex_render_check.py` then created a temporary end user in
  the workspace, logged in through `wwv_flow.accept` the way the browser does,
  fetched page 1 with the session cookie and removed the user again. The page
  came back **HTTP 200, 88,885 bytes** (`render190122_p1.html`): nine
  `t-Region`s, three Interactive Grids with their headings in Forms order, 37
  form fields, 3 Date Pickers, 15 Number Fields and two textareas, with **no**
  error banner, no `LABEL_COLUMN_SPAN` error, no `ORA-`, no absolute
  positioning and no layout script of FormsLang's own.
- **Browser submit (step 4, continued).**
  `examples/verify/apex_submit_check.py` posted that page back to
  `wwv_flow.accept` on the same session, the way the browser's own submit does
  — `p_json` carrying every page item, each protected item with its own
  checksum. With `P1_VL_PRECO` empty, APEX's page-processing engine ran the
  exported validations and **rejected the submit**: the four item-level rules
  rendered **inline beside their fields** — `<div id="P1_VL_PRECO_error">`
  inside the item's `t-Form-error`, with `aria-invalid="true"`,
  `aria-describedby` and `apex-page-item-error` on the input — and again in
  the notification region; the two record-level rules rendered in the
  notification only. That is `inlineWithFieldAndInNotification` and
  `inlineInNotification` behaving on screen as they were exported.
  Submitting the same page with `P1_VL_PRECO = 19.90` removed that rule's
  message from both places and left the other five — the negative control.
  The same run against `P1_CD_BARRA` with a valid EAN-13 (`7891234567895`)
  behaved identically. Saved as `submit190122_p1_empty.html` and
  `submit190122_p1_valid.html`.
- **What the user reads is the validation's own message.** The text on screen
  is the validation's `errorMessage`, which FormsLang emits as a placeholder
  (`Forms validation <unit> failed. Replace this text with the message your
  users should see.`, `formslang/apexlang.py`), **not** the message inside the
  rule's `raise_application_error`. A converted application therefore shows
  placeholder text to end users until each validation's message is reworded.
  Observed, not inferred.

What this does not prove:

- Anything about save behaviour. Nothing was written to a table: the page has
  no bound form region, so there is no fetch and no DML to exercise.
- Anything about a rule outside the six approved for this exercise, or about a
  module other than the synthetic showcase.
- Anything about tab order or layout fidelity against the Forms runtime. The
  page renders cleanly; it was not compared field by field with Forms.

Application 190122 remains installed in workspace `FORMSLANG`. It is
disposable and may be deleted; step 6 is the only step still open. The
temporary end user both scripts create is removed in a `finally`, so no test
account survives a run — including a failed one.

## Acceptance layers

| Layer | Required evidence | Boundary |
|---|---|---|
| Review integrity | Short bodies at every scope, recovery into an older session, unchanged decisions, refusal of changed source before insertion | Synthetic source regression tests |
| Source preservation | Invalid or changed same-name uploads leave the active source and review intact | Local HTTP integration tests |
| Failure recovery | Cancellation, failed providers, saved progress and crashed-job reconciliation | Existing store, workbench and AI tests; not a power-loss certification |
| Desktop usability | Reachable header actions at 1100, 1280 and 1380 px; review, reload, Doc, Preview and export | Browser checks plus packaged-engine smoke; native installer acceptance is separate |
| Reproducible export | Same session and configuration produce byte-identical ZIPs | Does not prove imported pages render or behave correctly |
| Import, render and rule execution | Package imports into a disposable application with no compile errors; the APEX dictionary matches what was exported; the page renders with no error banner; a real browser submit runs the exported validations, shows the item-level ones inline beside their fields, and a valid value clears the message | Done once, 2026-09-08, for six validations on one page; no DML was exercised, and no rule outside those six |
| Real migration | Approved private corpus, Forms runtime reference, APEX render and functional comparison | Pending; synthetic showcase is not a production corpus |

## Upgrade and recovery

1. Keep the existing session database and original source.
2. Reopen the unchanged XML/FMB using the existing output directory. Short
   executable units omitted by earlier versions are added as pending work;
   existing decisions are preserved. Repeating this does not duplicate tasks.
3. Opening a session database alone does not rescan source. If source has
   changed, use a separate output directory (`-o`) and review that revision.
4. A source conflict or malformed upload leaves the active review available.
   Do not delete the previous session to dismiss a conflict.

## Real corpus and visual comparison

Select authorized modules representing single-record entry, master/detail,
tabs and multiple canvases, dense toolbars, LOVs, and short key triggers.
Keep private source and captures outside Git. Record the source digest,
Forms version, viewport, export configuration and application id.

For each module, account for every executable body and every visible control.
Compare the Forms runtime with the actual imported APEX page, not only with
FormsLang's reconstructed preview. Check labels, defaults, required fields,
tab order, navigation and actions. Record approximations and unsupported
behaviour explicitly. Follow [APEX verification](apex-import-verification.md)
for validation and rendering; database actions require an authorized target.

Release claims must name which layers passed. A green synthetic suite,
successful ZIP validation or a working demo must not be described as full
production or visual equivalence.
