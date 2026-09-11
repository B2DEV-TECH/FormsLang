# Quality acceptance for existing features

This page records, per release, what the automated checks proved and what
they did not. A passing test suite does not prove that every Oracle Forms
application can be migrated faithfully; each section says where real
Forms/APEX testing still has to happen. The release steps that produce
these sections are in [releasing.md](releasing.md).

## 1.3.2 verification (2026-09-11, America/Sao_Paulo)

Published [FormsLang 1.3.2](https://github.com/B2DEV-TECH/FormsLang/releases/tag/v1.3.2).
Binary source: annotated tag `v1.3.2`, commit
`7337d87877c15840ee192a06feef857ec5ab0067`.
[PR #4](https://github.com/B2DEV-TECH/FormsLang/pull/4) integrated the Blueprint and
conversion review improvements as `54ad1c30795bca796f36296c4428405a022a692d`.
The release tag and merge have identical trees;
this verification record is a later documentation-only change.

- [CI 34600760770](https://github.com/B2DEV-TECH/FormsLang/actions/runs/34600760770):
  1,087 tests passed in each of eight Windows/Linux and Python 3.10-3.13
  combinations. Ruff, deterministic showcase export and SQLcl offline APEX
  validation, including negative controls, passed.
- Local integrated suite: 1,085 passed; two symlink tests skipped under the local
  account's permissions. The final harness correction also passed all 26 UI tests locally.
  Ruff passed. The 43 new backend/JavaScript regressions
  cover asynchronous request ordering, draft retention, actor/session isolation,
  bounded AI context and compact dependency projections.
- The new CI Edge acceptance job passed 30 checks and retained screenshots and
  results in `workbench-browser-evidence`. It covers Blueprint navigation,
  source-unit links and history, asynchronous explanation reconnect, saved
  briefing download, review drafts/decisions, conversion views and edits, and
  1366/720/390px layouts. The page made no external requests and raised no
  JavaScript exceptions. Local final acceptance passed the same 30 checks.
- [Installer acceptance 34600775515](https://github.com/B2DEV-TECH/FormsLang/actions/runs/34600775515):
  NSIS and MSI upgraded 1.3.1 to 1.3.2 on separate disposable Windows runners.
  Approvals and all 59 showcase units survived, the source was unchanged,
  repeated export bytes matched, and native desktop/engine startup passed.
  The frozen engine generated the Blueprint, exposed selected source, retained
  an architecture review, rejected stale context without changing a finding,
  returned idle AI status without calling a provider, and omitted source bodies
  from unselected list rows.
- On the synthetic showcase, JSON for a 40-trigger explorer page with no selected
  component fell from 83,212 to 71,636 bytes (13.9%). This measures one projection,
  not whole-application speed or representative production performance.

The initial candidate hit a 15-second Node subprocess timeout on a slow Windows
Python 3.11 runner. The final test harness uses a bounded 60-second process watchdog
and requires explicit asynchronous completion as well as exit code zero. Its
functional assertions were retained. Four negative controls confirmed that both
harnesses reject unresolved awaited promises and deliberate JavaScript assertion
failures. The application code did not change for this harness correction; the
final tag nevertheless rebuilt and revalidated both installers.

Browser AI responses were explicitly labeled offline test fixtures; the conversion
screenshot contains a hand-authored synthetic draft. No live model was evaluated
for this release and no real Oracle runtime parity is implied. AI results remain
proposals, with eight requests/results in process memory; restarting the app clears
that cache. Discard suppresses a result without terminating its provider. Unsaved
review drafts are tab memory only and should be saved before reload.

Exact tested and uploaded installer SHA-256 digests:

```text
FormsLang_1.3.2_x64-setup.exe
FF0BAB924733A7318F1ECBE675F122155F7986CD313016917D4EB177C6E1EE39
FormsLang_1.3.2_x64_en-US.msi
DE9C9A659B07FD10FB7D59049BF4DF6D6563DC0C9F9BF846D3A7A262288F571E
```

## 1.3.1 verification (2026-09-10, America/Sao_Paulo)

Published [FormsLang 1.3.1](https://github.com/B2DEV-TECH/FormsLang/releases/tag/v1.3.1).
Binary source: annotated tag `v1.3.1`, commit
`00e71d9ec95175a01d023eb484822c14c4387468`.
[PR #3](https://github.com/B2DEV-TECH/FormsLang/pull/3) merged the guided Blueprint
and block-key confirmation UI as `b10d2eede057f3aaf275bbc40496e430d02520e7`;
the merge and release tag have identical trees.

- [CI 34547978567](https://github.com/B2DEV-TECH/FormsLang/actions/runs/34547978567):
  1,044 tests passed in each of eight Windows/Linux and Python 3.10-3.13
  combinations. Ruff, deterministic showcase export and offline SQLcl APEX
  validation, including negative controls, passed.
- Local integrated suite: 1,042 passed, two symlink tests skipped under the local
  account's permissions. Ruff passed.
- [Installer acceptance 34548002690](https://github.com/B2DEV-TECH/FormsLang/actions/runs/34548002690):
  both NSIS and MSI upgraded 1.3.0 to 1.3.1 on disposable Windows runners.
  Existing approvals survived, source remained unchanged and exports remained
  repeatable. The frozen candidate also built the Blueprint reading guide,
  exposed decoded PL/SQL context and saved/retrieved a DEFER architecture review.
  Native desktop/engine startup checks passed.
- Headless Edge on the integrated source: guided navigation, rule filtering,
  progressive review, saved DEFER decision and application AI briefing/link
  rendering passed without JavaScript exceptions. Blueprint fit 720px and 390px
  viewports. AI rendering used a synthetic provider response for repeatability.
- A separate real Claude CLI request on the anonymized synthetic showcase graph
  returned four valid, component-linked proposal sections. Findings remained
  unchanged. This is one integration smoke test, not an evaluation establishing
  general model accuracy or the validity of every architecture suggestion.

Arrows describe static references, not runtime sequence. AI only receives the
bounded anonymized structural graph and cannot establish business semantics.
Briefings remain proposals and are saved separately from deterministic reports.
Real Oracle application/runtime validation remains outside these checks.

Exact CI artifact and published asset SHA-256 digests:

```text
FormsLang_1.3.1_x64-setup.exe
6DEBF53AA6DE2AC57E7A687E4AD5AD0969E6FDF11458963F9FCB95519FB03B39
FormsLang_1.3.1_x64_en-US.msi
4DC2E3BB2B79C4B28CBA4B49A3F8D539AEFA3C47833872DA777EBE60D31F7BD8
```

## 1.3.0 verification (2026-09-10, America/Sao_Paulo)

Published [FormsLang 1.3.0](https://github.com/B2DEV-TECH/FormsLang/releases/tag/v1.3.0).
The annotated tag points to `88c3ae7315c21342a5f2966012dec152aa6f9465`.
[PR #2](https://github.com/B2DEV-TECH/FormsLang/pull/2) merged it as
`daad53a3898a7e8c14c82778acad5d7b969d98ae`; the tag and merge have identical
trees. This documentation record does not change the tested binaries.

- [CI 34544274520](https://github.com/B2DEV-TECH/FormsLang/actions/runs/34544274520):
  1,031 tests passed in each of eight Windows/Linux and Python 3.10-3.13
  combinations. Ruff, deterministic showcase export and the offline SQLcl
  APEX validation job passed, including its negative controls.
- Local Windows/Python 3.13: 1,029 tests passed and two symlink tests were
  skipped under the local account's permissions. Ruff passed.
- [Installer acceptance 34544756403](https://github.com/B2DEV-TECH/FormsLang/actions/runs/34544756403):
  the same tag built both installers, then separate disposable Windows runners
  installed 1.2.2, saved a review and upgraded to 1.3.0. NSIS and MSI checks
  passed for review retention, repeatable export and native desktop/engine
  startup. The release assets are those exact CI artifacts; published SHA-256
  digests match the downloaded artifacts.
- Blueprint's five-module synthetic corpus and headless Edge checks exercised
  dependency filtering, source evidence and persisted DEFER review. This was
  source-mode browser validation, not exhaustive native-webview testing.

Blueprint limits: rule candidates use conservative lexical heuristics, not
control-flow or business-semantics proof. Dynamic SQL, unavailable package
bodies, external callers and symbol resolution can remain unknown. API ranking
measures observed reuse, not suitability or safety. Coverage records human
decisions and supplied implementation evidence; it does not verify runtime
functional parity. No live Oracle application/database validation was performed
for the new Blueprint capability. Earlier APEX runtime checks below concern
their explicitly identified revisions and fixtures.

Exact tested and published installer SHA-256 digests:

```text
FormsLang_1.3.0_x64-setup.exe
FE1C2C71BBCFB6AC5DA6D0CEEC278C977D29FBEE998D03A1F609A59287F0DCBC
FormsLang_1.3.0_x64_en-US.msi
2DD4A2B54F25B2FF0E58BB0DFC731AB5256C90B233A583640751D2EF93F74CEE
```

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
  Observed, not inferred. This finding became card **A7**; the section below
  records the same page after it was addressed.

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

## Message provenance on screen (2026-09-09)

The same disposable application **190122**, re-imported after the change that
fills a validation's `errorMessage` from the sentence the rule already has.
Package SHA-256 `6f1be7de144fed81c1be0ca90d83dc2dda7a4b6657e963145218ab359b3b3b22`
(34,313 bytes), built from `tests/fixtures/showcase/module.xml` with the same
six units approved — but this time two of them (`FK_CATEGORIA`,
`BK_ITENS.WHEN-VALIDATE-RECORD`) approved as code that raises **without saying
anything** (`raise value_error;`), so both message sources are exercised in one
package. `apex validate --offline` returned `Validation successful.`;
`apex import` reported `Importing application ID: 190122 into workspace:
FORMSLANG` and `Import successful.`, with no `APEXlang Compile Errors`.

- **Dictionary (step 3).** All six rows of `apex_application_page_val` carry a
  real sentence in `validation_failure_text` — the placeholder appears nowhere.
  Four came from the approved code (for example `P1_VL_PRECO`: *Valor unitario
  e obrigatorio (regra vinda do Forms).*), two from the `MESSAGE()` of the
  Forms trigger the silent rule came from (`P1_FK_CATEGORIA`: *Categoria
  inexistente. Use a lista (F9).*; `BK_ITENS`: *Valor unitario nao pode ser
  negativo.*). Display locations are unchanged:
  `INLINE_WITH_FIELD_AND_NOTIFICATION` for the four item rules,
  `INLINE_IN_NOTIFICATION` for the two record rules.
- **Browser submit (step 4).** `examples/verify/apex_submit_check.py` against
  `--app 190122 --page 1 --item P1_VL_PRECO --good 19.90`, same temporary end
  user, same login. With the item empty the page came back 92,616 bytes and
  each item rule rendered **its own sentence** inline beside its field —
  `P1_VL_PRECO` *Valor unitario e obrigatorio (regra vinda do Forms).*,
  `P1_FK_CATEGORIA` *Categoria inexistente. Use a lista (F9).*, `P1_CD_BARRA`
  *Codigo de barras invalido: informe um EAN-13.*, `P1_FK_FORNECEDOR` *Informe
  o fornecedor antes de gravar.* — with both record-level sentences in the
  notification region. Resubmitting with `19.90` removed the `P1_VL_PRECO`
  message and its `<div id="P1_VL_PRECO_error">` entirely and left the others:
  the same negative control as 2026-09-08.
- **The placeholder is gone, and the `ORA-` never was there.** Neither saved
  response contains `Replace this text with the message`, and neither contains
  any `ORA-` at all — including the `ORA-20001` the approved code raises. That
  is the point of the change: APEX prints the validation's own message and
  never the error the code raised, so the sentence had to be carried into that
  field. Saved as `submit190122_p1_empty.html` and `submit190122_p1_valid.html`.

What this adds to the 2026-09-08 record is the wording only. It does not
enlarge anything else: still six rules, still one synthetic module, still no
DML, still no comparison against the Forms runtime.

## Acceptance layers

| Layer | Required evidence | Boundary |
|---|---|---|
| Review integrity | Short bodies at every scope, recovery into an older session, unchanged decisions, refusal of changed source before insertion | Synthetic source regression tests |
| Source preservation | Invalid or changed same-name uploads leave the active source and review intact | Local HTTP integration tests |
| Failure recovery | Cancellation, failed providers, saved progress and crashed-job reconciliation | Existing store, workbench and AI tests; not a power-loss certification |
| Desktop usability | Reachable header actions at 1100, 1280 and 1380 px; review, reload, Doc, Preview and export | Browser checks plus packaged-engine smoke; native installer acceptance is separate |
| Reproducible export | Same session and configuration produce byte-identical ZIPs | Does not prove imported pages render or behave correctly |
| Import, render and rule execution | Package imports into a disposable application with no compile errors; the APEX dictionary matches what was exported; the page renders with no error banner; a real browser submit runs the exported validations, shows the item-level ones inline beside their fields with the sentence the rule already had, and a valid value clears the message | Done 2026-09-08 (firing and placement) and 2026-09-09 (the wording each rule shows), for six validations on one page; no DML was exercised, and no rule outside those six |
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
