# Quality acceptance for existing features

This page records, per release, what the automated checks proved and what
they did not. A passing test suite does not prove that every Oracle Forms
application can be migrated faithfully; each section says where real
Forms/APEX testing still has to happen. The release steps that produce
these sections are in [releasing.md](releasing.md).

## 2.0 Phase A foundation verification (2026-09-19)

This is a development milestone, **not a FormsLang 2.0 release**. Implementation
base: `7191ec8`; initial acceptance commit: `99e323c`. Product versions remain
1.6.0. No tag, remote publication, installer build or database import was performed.

- Windows / Python 3.13 full local suite: **1,214 passed, four skipped**, 139.52 s.
- Ruff: **all checks passed**. Git whitespace check passed.
- Existing Workbench browser acceptance: **101/101 checks**, 27 screenshots,
  local run `run-bce6a132b3d3` under `scratch_tmp/phase-a-browser/`.
  Its explanation provider is an explicitly synthetic offline stub, not a live AI.
- New foundation acceptance: real Forms XML parsing and Blueprint, committed
  architectural review, close/reopen, relocation and two-process publication race.
- Migration acceptance: original session preservation, complete legacy table
  comparison, committed WAL state, duplicate module identities, retry after
  interruption, injected migration failure and identical APEXlang export ZIP bytes.
- Frozen benchmark baselines and ground truth: **24 tracked files compared with
  implementation base, zero content differences**. No baseline was regenerated.

New OS symlink tests were skipped because this Windows account cannot create
symlinks; lexical traversal and invalid-path cases did execute. Do not treat those
OS skips as proof of junction/symlink behavior on other environments.

The implemented scope is a project application-library foundation, documented in
[project model](project-model.md) and [implementation architecture](architecture-2.md).
It does not yet include project onboarding UI, project HTTP/CLI commands, analysis
jobs, reports, project generation or live source freshness on reopen. Independent
branch review and resulting fixes are recorded below.
Installer upgrade from 1.6.0, clean-machine UX, frozen fingerprint resources,
100/500-form performance, and connected Oracle/APEX validation remain later gates.

### Independent Phase A review

A fresh-context read-only reviewer inspected `7191ec8..99e323c` and identified
three Important findings, with no Critical or Minor findings. The implementer
independently reproduced all three as failing tests before changing product code:

1. An ADOPTED registered path could hide a cross-tenant directory junction after
   the legacy resolver canonicalized it. The new project access boundary now
   validates the registered spelling before resolution. The regression uses a
   real Windows NTFS junction and ran successfully, not as a symlink skip.
2. Publication validated outer revisions but not each finding's binding. Findings
   now retain the original engine revision, and publication checks its derivation
   against the current project analysis revision before any transaction writes.
3. The engine identity omitted persisted readiness dependencies. Fingerprinting
   now includes dashboard, test specifications, model, sensitive-source analysis,
   Store/conversion dependencies and the project binding code; relevant public
   version constants also participate.

Final corrected-tree verification: **1,217 passed, four skipped**, 141.40 s;
Ruff and Git whitespace checks passed. All four skips were OS symlink-privilege
limitations; the new Windows junction security regression **passed**. Browser
acceptance was rerun after the fixes: **101/101 checks**, 27 screenshots, run
`run-4025b7d72189` under `scratch_tmp/phase-a-browser-final/`. All 24 frozen files
were compared again with the implementation base and remained unchanged.
No second reviewer pass is implied by the implementer's regression verification.

### Execution decisions and remaining boundaries

- Engine identity includes additional transitive dependencies: conservative
  invalidation is preferable to keeping approvals after changed reasoning.
- Intake options bind source revision; all analysis options and the target bind
  analysis revision. Consumers must preserve that distinction.
- Assessment publication and validation were delivered together in Task 4 rather
  than publishing a temporarily unvalidated storage API in Task 3.
- Exclusive directory reservation plus hardlink publication replaces POSIX
  directory rename, which can overwrite an empty destination. Filesystems without
  hardlink support fail explicitly; failed pre-publication reservations may need
  inspection. Existing user data is not overwritten to recover them.
- UI/API/CLI, discovery, jobs and generation remain later phases: they are not yet
  available through this foundation. Saved Current is not a live filesystem check.
- Authenticated contexts are request-scoped; later adapters must reauthorize each
  request. Caching one indefinitely would defeat membership revocation.
- Frozen fingerprint resources, installer upgrades, scale and full-product
  acceptance remain unverified release gates, not implied by unit acceptance.
- Instantaneous filesystem replacement by a compromised OS account remains outside
  the application isolation boundary. Pre-existing cross-tenant redirects are
  explicitly in scope and covered by the new real-junction test.

## 1.6.0 verification (2026-09-19, America/Sao_Paulo)

Published [FormsLang 1.6.0](https://github.com/B2DEV-TECH/FormsLang/releases/tag/v1.6.0).
Binary source: annotated tag `v1.6.0`, commit
`7563431792e4f6e4d1360e32328be5cbec69e113`. This acceptance record is a later
documentation-only change.

- Local full suite: **1,134 passed, two skipped** (local symlink permissions),
  Python 3.13.
- [CI 35442199131](https://github.com/B2DEV-TECH/FormsLang/actions/runs/35442199131):
  **11 of 12 jobs passed; `ruff` failed.** All eight Windows/Ubuntu and Python
  3.10-3.13 test combinations passed, as did deterministic export, SQLcl offline
  APEX validation and the Edge browser acceptance. The lint job reported eight
  errors -- three `SIM102`, one `SIM114`, one `PIE810`, one `I001`, one `F841`
  for a variable assigned and never read inside a function that had no caller,
  and one `EXE001` for a shebang on a file without the executable bit. The
  eighth is invisible on Windows, where ruff cannot evaluate that bit, so a
  clean local `ruff check` is not evidence that the lint job will pass; only
  Linux CI settles it. All eight came from the modernization-lab commits of
  2026-09-18 and were inherited by the release commit; `main` had been red on
  this job since
  `feat(examples): add Legacy Order Management modernization lab`. They are
  fixed in a follow-up commit, not in the tagged one: the fixes are
  behaviour-preserving, and re-running the benchmark with them applied produced
  predictions identical to the frozen v3 baseline in every scored field, with
  only `forms_lang_version`, `generated_at` and `source_commit` differing. The
  release was published from the tag as-is rather than re-tagged, so the
  published binaries are exactly the ones acceptance tested.
- [Installer acceptance 35442203266](https://github.com/B2DEV-TECH/FormsLang/actions/runs/35442203266):
  all three jobs passed. The NSIS and MSI installers passed clean installation
  and upgrade from 1.5.0 on separate Windows runners. The saved approval, the
  source session and the deterministic export survived the upgrade, with the
  export SHA-256 unchanged at
  `18286b139f384591db58a325d97d962825cb1d5a2414607fe32b9555a42e1d7a` before and
  after. Published installers came from this run's `installers-1.6.0` artifact;
  downloaded file hashes matched the build log.
- Modernization benchmark: baseline v3 was generated once and frozen in the same
  command, and the run verified the ground-truth SHA-256 unchanged
  (`4b43e879e6124c7b2821ffedfc64c3ff19a825f61b39d7b911d9da209ce69615`). All
  sixteen files of `baselines/v1`, `baselines/v2` and the ground-truth registry
  were re-hashed after the release work: sixteen identical, zero divergent.
- Oracle fixtures: the lab's SQL was installed, seeded, verified and reset in a
  disposable schema on Oracle AI Database 26ai Free 23.26.3.0.0. Fifty-four
  objects were created, all `VALID`, with 6/6 fixture assertions `OK`. This
  validates the fixtures, not the predictions: no engine output was checked
  against a running database.

Published installer SHA-256 values, verified against GitHub asset digests:

| Asset | SHA-256 |
|---|---|
| `FormsLang_1.6.0_x64-setup.exe` | `7f3637c648dec20b544e38940dee553d83299d5b5e1676ccc6a5c21be25d812c` |
| `FormsLang_1.6.0_x64_en-US.msi` | `ad691ddbdb3f1d1a38cd88360839a9e90ae16625bf19010b8a0afe51507f58b9` |

This release changes modernization reasoning and adds standalone database
ingestion. The benchmark figures it reports were measured on the synthetic
Legacy Order Management lab that ships in this repository, under the protocol
in `examples/modernization-lab/benchmark/protocol.md`. They are a
project-owned reproducible measurement and establish neither Oracle
Forms/APEX runtime fidelity nor migration correctness for any real
application. No customer application was used. Four cases the previous
baseline classified correctly are now wrong, and one concurrency finding is
emitted without a risk grade; both are recorded in
`examples/modernization-lab/benchmark/baselines/v3/comparison-v1-v2-v3.md`.

## 1.5.0 verification (2026-09-12, America/Sao_Paulo)

Published [FormsLang 1.5.0](https://github.com/B2DEV-TECH/FormsLang/releases/tag/v1.5.0).
Binary source: annotated tag `v1.5.0`, commit
`95a5537d7a32ecd7c797ee7590f6bc64d61ae6ea`. This acceptance record is a later
documentation-only change.

- Local full suite: **1,085 passed, two skipped** (local symlink permissions),
  Python 3.12. Ruff passed. After integration into the source repository, the
  version and JavaScript behavior tests passed again: 27 tests, with Ruff clean.
- Local Chromium acceptance: **101 checks passed**, with 27 screenshots.
  The checks exercise real divider drags and keyboard resizing, navigation
  collapse, layout reset and persistence, corrupt and unavailable browser storage,
  code focus and modal focus restoration, draft retention, viewport constraints,
  editor/highlight alignment, themes, Blueprint and conversion reviews. A real
  offline export produced a ZIP and marked the new entry in Exports without a
  JavaScript exception. No database import or cloud model was used.
- Independent visual acceptance: **19 checks passed**, including the user's
  1360x695 viewport with the synthetic `KEY-CLRFRM` unit. With the offline setup
  banner visible, the editable code area measured 314 pixels tall in the default
  layout and 516 pixels in Focus. Sticky review controls stayed in reach at
  1360x695, 1100x695, 901x600, 768x600, 390x740 and 1360x480. At small sizes with
  every supporting section and both banners open, scrolling the workspace or
  using Focus is necessary to read more code. First-run acceptance passed seven
  additional checks in dark/light themes at desktop and phone widths.
- Browser-tested HTML SHA-256:
  `c106423fac97d326d466254e53ea8c5f0028bb41fbe9e89c31e2fae9a0815693`.
  The committed source produces identical HTML. README's current Workbench,
  Blueprint, onboarding, project, settings, evidence and export screenshots are
  real browser captures from these isolated synthetic runs. The hand-authored
  proposal shown in the review images is explicitly identified as a test draft.
- [CI 34702752930](https://github.com/B2DEV-TECH/FormsLang/actions/runs/34702752930):
  all 12 jobs passed: eight Windows/Ubuntu and Python 3.10-3.13 test combinations,
  Ruff, deterministic export, SQLcl offline APEX validation with negative controls,
  and the 101-check Edge browser acceptance. Ubuntu 3.12, Windows 3.12 and Windows
  3.13 logs each recorded 1,087 passed tests. Edge tested the same HTML hash as the
  local run, without page exceptions or external requests. No workflow rerun was
  needed.
- [Installer acceptance 34702763575](https://github.com/B2DEV-TECH/FormsLang/actions/runs/34702763575):
  all three jobs passed. The NSIS and MSI installers passed clean installation
  and upgrade from 1.4.0 on separate Windows runners. The saved review, source
  session and deterministic export survived, and the native desktop started
  its frozen engine. Published installers came from this run's
  `installers-1.5.0` artifact; downloaded file hashes matched the build log.

Published installer SHA-256 values, verified against GitHub asset digests:

| Asset | SHA-256 |
|---|---|
| `FormsLang_1.5.0_x64-setup.exe` | `acbb0974ca84c4caf4ed448f70a3b2ea427ef2c30c34a4b1d402b6111e83cd48` |
| `FormsLang_1.5.0_x64_en-US.msi` | `628260c00289a6747342a6d8482ef17990305f615f6834d3ba963b429b6e7a43` |

This release changes workspace usability and export dialog behavior. These
checks do not establish additional Oracle Forms/APEX runtime fidelity,
production-scale performance or migration correctness. No customer application
was used for this UI acceptance.

## 1.4.0 verification (2026-09-12, America/Sao_Paulo)

Published [FormsLang 1.4.0](https://github.com/B2DEV-TECH/FormsLang/releases/tag/v1.4.0).
Binary source: annotated tag `v1.4.0`, commit
`3b3516d7ff1eb9991fd6de8339485c11559e18e9`. This acceptance record is a later
documentation-only change.

- Local full suite on the updated source checkout: **1,085 passed, two skipped**
  (local symlink permissions), Python 3.12. Ruff passed. The UI behavior harness
  now supplies the document body used to apply the first-run layout; its existing
  draft retention and request isolation assertions were preserved.
- Local Chromium acceptance: **53 checks passed**, including conversion and
  Blueprint workflows, persisted review decisions, theme selection and persistence,
  keyboard focus in dialogs and mobile navigation, source filtering, reduced
  motion, navigation after an API failure and focus after a viewport change.
  No page JavaScript exceptions or requests outside the isolated Workbench.
  `examples/verify/workbench_browser_check.py` and its `.mjs` companion reproduce
  these checks using the synthetic showcase and a deterministic offline provider.
- Additional local visual acceptance: **54 checks passed**, dark/light themes at
  1920, 1600, 1280, 768 and 390 pixels, including the wide evidence panel, settings,
  navigation and unit drawers. First-run acceptance passed seven checks. Text
  contrast samples were at least 4.91:1 in light mode and 6.08:1 in dark mode;
  these are sampled checks, not an exhaustive accessibility certification.
- Browser-tested HTML SHA-256:
  `6f474f323aebbea33925ab4899f97fbb5b252e7748479c9a6b825a24088ba4a7`.
  The source checkout that was committed produced the same HTML bytes. README
  screenshots were refreshed from that synthetic browser run.
- [CI 34700126723](https://github.com/B2DEV-TECH/FormsLang/actions/runs/34700126723):
  all 12 jobs passed, including eight Windows/Ubuntu and Python 3.10-3.13 test
  combinations, Ruff, deterministic showcase export, SQLcl offline APEX validation
  with negative controls, and the 53-check Edge browser acceptance. Ubuntu 3.12,
  Windows 3.12 and Windows 3.13 logs each recorded 1,087 passed tests. No workflow
  rerun was needed.
- [Installer acceptance 34700126573](https://github.com/B2DEV-TECH/FormsLang/actions/runs/34700126573):
  NSIS and MSI passed clean installation and upgrade from 1.3.2 on separate
  Windows runners. The saved review, source session and deterministic export
  survived, and the installed desktop opened its native window and started the
  frozen engine. Published binaries came from this run's `installers-1.4.0`
  artifact; their local hashes matched the build log.

Published installer SHA-256 values, verified against GitHub asset digests:

| Asset | SHA-256 |
|---|---|
| `FormsLang_1.4.0_x64-setup.exe` | `4f32bd240cbfea80f4f086cc79690074f2cdf183ef8390741d0c7e4dcd3d07f0` |
| `FormsLang_1.4.0_x64_en-US.msi` | `3701a52708a73d30c6e97f21fb28731ac7c15835cc8982ad212c0a85882bfe06` |

This release changes the Workbench interface. It does not establish additional
Oracle Forms/APEX runtime fidelity, production-scale performance or migration
correctness. The browser and installer checks use synthetic fixtures; no cloud
model or customer application was used for this UI acceptance.

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

## 2026-09-19 — FormsLang 2.0 Phase B development acceptance

Branch `codex/formslang-2-phase-b`, based on merged Phase A
`3f4d6914225a3a1df9e151d93e8669811261d753`. Application implementation tested at
`e52ffda939c53c84e76ee1e585020807630a59c3`; the subsequent acceptance commit adds
test harnesses and documentation, not production behavior. Version remains 1.6.0.
This is not 2.0 release acceptance or permission to merge/publish.

Platform: Windows 11 build 26200, Python 3.13.15, installed Node and headless Edge.
All project inputs are disposable public-safe synthetic fixtures. Commands run from
the repository root with Python `-B`; no Oracle credentials or AI provider used.

### Real application and compatibility checks

- `python -B -m pytest -q -rs -p no:cacheprovider`: **1,438 passed, 5 skipped in
  238.88s**, including Phase A/B, auth/security, CLI/API and Node-driven tests.
  Skips are Windows-account symlink permissions at `test_blueprint.py:388`,
  `test_path_safety.py:92`, `test_project_discovery.py:248`,
  `test_project_manifest.py:83`, `test_project_service.py:89`. Actual Windows NTFS
  junction cases execute and pass; no missing-browser/Node skip is hidden.
- `python -B examples/verify/project_browser_check.py --output scratch_tmp/phase-b-final-browser`:
  **21/21**, five screenshots, no browser exceptions. Evidence
  `run-16d83002bc1e/result.json`. Real HTTP/service/SQLite/engine, no fake assessment
  responses. Browser onboarding, source picker/preview, default target, analysis,
  persisted summary; server process replaced (PID 27616 → 35612), recent reopen
  retains revision; altered source → Stale; missing source → Missing Source;
  same-content relink → Current; malformed XML → Incomplete with valid input retained;
  250-module cancellation publishes no assessment; project switch, normal demo,
  tablet width, reduced-motion preference and loopback-only application requests.
- `python -B examples/verify/workbench_browser_check.py --output scratch_tmp/phase-b-final-legacy-browser`:
  **101/101**, 27 screenshots, evidence `run-0ff4263a6010/result.json`. Existing
  Blueprint, conversion/review, source evidence, layout, theme, contrast and keyboard
  regression checks remain green.
- `python -B -m pytest -q -p no:cacheprovider tests/test_project_ui_behavior.py tests/test_blueprint_ui_behavior.py tests/test_review_ui_behavior.py`:
  **44 passed in 3.02s**, including Node-driven UI behavior tests. New real-browser
  checks verify labels/error association, keyboard Tab/focus, live status and
  labelled progress. This is not a manual screen-reader audit or native Tauri UI test.
- `python -B -m pytest -q -p no:cacheprovider tests/test_project_acceptance.py`:
  **1 passed in 5.40s**. Review history, timestamp and findings survive a new service
  instance. A trap proves reopen/freshness does not call Blueprint analysis.
- `python -B -m ruff check . --no-cache` and `git diff --check`: clean.
- Compared canonical Git blob hashes of all **24** frozen baseline/ground-truth
  files against the Phase A base: **zero differences**. Version declarations are
  unchanged; `pyproject.toml` only adds bundled demo package-data entries.

### Packaged engine and deterministic content

`python -B -m PyInstaller --noconfirm --distpath scratch_tmp/phase-b-engine-green/dist --workpath scratch_tmp/phase-b-engine-green/build packaging/formslang-engine.spec`
then `python -B examples/verify/project_engine_check.py --engine scratch_tmp/phase-b-engine-green/dist/formslang-engine.exe --output scratch_tmp/phase-b-engine-green/acceptance`:
**6/6** actual frozen-executable checks (`run-36ebe9f12637/result.json`). Includes
normal demo, analysis, fresh reopen, bundled fingerprint resources and repeat
determinism. EXE SHA-256
`aa04f00a5fcce787b6c40aec555f9528c21d408be45e12dd0c74c7d6ad35fe54`.
The pre-fix actual executable reproduced `ENGINE_IDENTITY_UNAVAILABLE`; including
Python data resources fixed the fingerprint failure rather than bypassing it.

`python -B -m pip wheel --no-deps --no-build-isolation --no-index --wheel-dir scratch_tmp/phase-b-wheel .`
and isolated `--target scratch_tmp/phase-b-wheel/site` install also passed a normal
demo/analysis with Python `-I` and an asserted installed-module path. Wheel SHA-256
`b22422b29699e2304eccfcdd20fd99df000ec17d008b7fa0074527e551268028`.
No network dependency installation or published binaries. Wheel and frozen engine
both produced analysis revision
`bc6c52ac8e7f02a3712553cdb567b9e5a81ed54553c05a780bc0a4c62a5d881c`.

### Small-fixture timing baseline (not a scale claim)

`python -B examples/verify/project_performance_check.py --output scratch_tmp/phase-b-performance`,
evidence `run-df3425e81db5/result.json`: five files, two Forms, two tables, one package
specification/body. Source revision
`5519a4d9b6f3167335f1029991bed75a33cde7349c9721984ffc23f63e3a5dd4`.
Discovery preview 1,011.600 ms. Traced analysis total 4,572.343 ms; measured phase
times: discovery 1,923.608; Forms parsing 472.810; DB parsing 669.369; Blueprint
213.682; assessment 151.976; persistence 1,013.168 ms. Phase times include safe-boundary
checks. Python allocation peak 2,670,130 bytes (tracemalloc, not RSS). Repeated real
analysis matched the frozen/wheel revision above. Tracing overhead and one tiny
synthetic run preclude estate-scale or analyst-productivity conclusions.

### Explicit boundaries

No native installer/upgrade acceptance, new live Oracle/SQLcl/APEX validation,
customer corpus, functional parity or human productivity experiment was performed
for Phase B. Forms2XML tool execution is tested at a controlled mocked boundary,
not an installed proprietary Oracle tool. Existing historical Oracle acceptance
above is not new evidence for this phase. Full dashboard, inventory visualization,
priority-review UI, project-level generation and reports remain Phase C+.

### Final independent review and corrected acceptance

The independent whole-branch review of `3f4d691..c90899f` identified three Important
issues, no Critical or Minor issues. It independently ran eight focused safety
tests; the complete suite/browser/build evidence remains the implementer's record.
One fix pass was completed in **`bff32f06db6688b06b9c0009fdaf1517603ca417`**:

1. Demo continuation is bound to the successfully opened project and view generation.
   A deferred response can no longer start analysis of another project after navigation.
   `test_demo_pending_open_cannot_start_analysis_of_switched_project` reproduced RED
   (an unwanted `/projects/b/analyze` request), then passed.
2. Explicit same-user open recovers a moved project's locator only when the old
   directory is missing, without carrying source authority. The relocation test
   reproduced RED; live-clone replacement and another-actor adoption remain rejected.
3. Local creation now reserves the locator and initialization owner before SQLite
   publication. Mirror and final locator-write failures resume the same DB on retry.
   Four cases (default/explicit destination × mirror/locator failure) reproduced RED
   and passed after the fix. No second persistence model was introduced.

Final commands against that implementation (before its unchanged commit):

- `python -B -m pytest -q -rs -p no:cacheprovider`: **1,446 passed, 5 skipped,
  245.29s**. Same five Windows symlink-permission skips listed above. This supersedes
  the pre-review count; all Phase A/B, API/CLI, authorization and regression tests pass.
- Focused intake/UI/HTTP/CLI/demo: **85 passed in 75.29s**. UI/Blueprint/review JS
  scope: **45 passed in 3.01s**. Ruff and `git diff --check`: clean.
- Project browser: **21/21**, zero exceptions, five screenshots,
  `scratch_tmp/phase-b-review-browser/run-2dbcf9509616/result.json`.
- Legacy browser: **101/101**, 27 screenshots,
  `scratch_tmp/phase-b-reviewed-legacy-browser/run-0df4354113a3/result.json`.
- Rebuilt actual frozen executable: **6/6**,
  `scratch_tmp/phase-b-review-engine/acceptance/run-fa483cbca4e2/result.json`.
  Build/acceptance commands are the same as above with `phase-b-review-engine` paths.
  Final EXE SHA-256:
  `dfb892e9438aa4ec5f28fd60493dd376e0c35a328bddeef353931030df18fda7`.
- Rebuilt wheel using the same offline pip commands under
  `scratch_tmp/phase-b-reviewed-wheel`: isolated installed-module demo/analyze passed
  with Python `-I`, two Forms and the same deterministic analysis revision as above.
  Final wheel SHA-256:
  `8be5b4d0a21274dbc76eb93c600531587bcae3aa29fa0511bbdd5cffea6d27a0`.
- All **24** frozen baseline/ground-truth blob hashes rechecked: unchanged. Version
  declarations remain **1.6.0**. No push, merge, tag, release or installer publication.

The final documentation commit records this tested parent, avoiding a fictitious
self-referential commit hash. No second reviewer was used; each material fix has
RED/GREEN coverage and the full suite was rerun. There are no deferred Minor review
findings. The explicit Oracle/runtime, scale, installer and later-phase limitations
above remain unchanged; this closes Phase B only, not FormsLang 2.0.

### PR #7 polling blocker investigation (2026-09-19, Windows)

Starting head: `426e4e2d27ff109e5055d3febc7ad87e9d5355af`. All **12/12** remote
checks in run `35480445618` completed successfully before local stress began.
This entry records the subsequent descriptor synchronization patch; it does not
claim that the original head was free of the intermittent polling defect.

Environment: Windows 11 build 26200, CPython 3.13.15. Synthetic sources only.
The original `test_analysis_is_accepted_then_persisted` passed **50/50** fresh
Python processes before the fix. A separate concurrent-read/publication stress
then reproduced the same `Project descriptor cannot be read` failure at
`ProjectStore.open` / `Path.read_text(project.json)`. The preserved original cause
was **`PermissionError: [Errno 13] Permission denied`**. Its `winerror` attribute
was absent; no specific Win32 error, antivirus involvement, or environmental cause
is claimed. The earlier full-suite occurrence did not retain its OS exception.

Root cause demonstrated: descriptor validation/read and atomic mirror replacement
were not mutually synchronized. Separate connections could read during replacement
and independently reconcile the same mirror. The controlled regression
`test_open_does_not_read_descriptor_during_replacement` failed RED on the original
implementation. The initial real concurrency pilot reported **1 failed, 2 passed**.
Diagnostics retained both read-path and sync-path PermissionError tracebacks in
`scratch_tmp/polling-concurrency-pilot/001-exceptions.jsonl`.

The minimal production patch is confined to `project_store.py`: use the existing
SQLite `BEGIN IMMEDIATE` ownership for descriptor validation/read and mirror
reconciliation/publication, obtaining the authoritative payload inside the lock.
The initial validation transaction does not modify database contents. Lock
contention is reported as ProjectBusy. Identity/path validation and corrupt/missing
mirror recovery remain enforced. No new persistence layer, read retry, HTTP retry,
or swallowed exception was added. The pre-existing bounded Windows replace retry
for external file readers is unchanged; it is not the synchronization mechanism.

Post-fix verification:

- Controlled RED to GREEN plus Store/jobs/HTTP: **55 passed in 46.20s**.
- Original HTTP test: another **50/50** fresh processes passed; **100 explicit
  repetitions total**, excluding ordinary suite runs and the previous investigation.
- Concurrent descriptor/Store and HTTP completion/cancellation stress: **10/10**
  fresh processes, **30/30 test cases**, no descriptor exception. These exercised
  4,000 concurrent Store opens against 500 descriptor publications, plus 1,000 job
  status GETs and 1,000 additional Store reopens across completion/cancellation.
- Cancellation before publication, completion before cancellation, analysis phase
  boundaries and freshness/reopen: **10/10** processes, **70/70 cases**.
- Committed regression coverage additionally includes two spawned reader processes
  against descriptor publication, not just threads in one interpreter.
- `python -B -m pytest -q -rs -p no:cacheprovider`: **1,449 passed, 5 skipped,
  268.12s**. Same five Windows symlink-permission skips above.
- `python -B -m ruff check . --no-cache` and `git diff --check`: clean.
- `python -B examples/verify/project_browser_check.py --output scratch_tmp/polling-fix-browser`:
  **21/21**, zero browser exceptions, five screenshots; `run-08c75ddf523f/result.json`.
- `python -B examples/verify/workbench_browser_check.py --output scratch_tmp/polling-fix-legacy-browser`:
  **101/101**, 27 screenshots; `run-74a6e56aeeca/result.json`.
- All **24** baseline/ground-truth canonical Git blob hashes match `3f4d691`.

Detailed repetition logs and results are retained in `scratch_tmp/polling-original-50`,
`polling-fixed-50`, `polling-concurrency-green`, and `polling-boundaries-10`.
The diagnostic wrapper only records and rethrows exceptions; it never retries.
Stress is finite evidence, not a guarantee against arbitrary external filesystem
interference. No Phase C work, version change, tag, release or automatic merge.

Independent read-only patch review found no Critical or Important issues and
recommended merge. One Minor test limitation remains explicit: the controlled
overlap regression uses a 250 ms observation window, so extreme reader scheduling
delay could false-pass the old implementation. Its observed RED is supplemented
by real threaded/multiprocess stress; it is not claimed to be schedule-independent.
The reviewer could not run Python in its tool environment and did not independently
rerun the recorded acceptance; it inspected code/call paths and passed diff-check.

## 2026-09-20 — FormsLang 2.0 Phase C development acceptance

Branch `codex/formslang-2-phase-c`, based on merged Phase B
`2c977ebe2d378e86028464399c85cde1335b8018`. The implementation and acceptance
harnesses are present through `8d594d2b855b26f6134aee0fefa25e5d8a5001cf`; architecture
semantics are recorded in `70c83130606521b9188530f9bc41523a6f7ac268`; review corrections
are in `579048771cf96d99aeec86d7a0d21b0a69f4e2cd`,
`727551762b1be95784d06b7615f01dcbeb2cc965` and
`fd599c56c0415620fdaea8a5a0f4bfb07ddbcb0f`. PR #8 CI follow-up is in
`7c9868f`.
Version remains 1.6.0. This closes only Phase C Overview + Inventory; it is not
FormsLang 2.0 release acceptance and creates no tag, release or installer.

Platform: Windows 11 build 26200, Python 3.12.10, Node 22.16.0 and headless Edge.
Inputs are bundled/disposable public-safe synthetic fixtures. Static reads used no
Oracle credentials, AI provider, external telemetry or customer source.

### Read-model and application checks

- `python -B -m pytest -q -rs -p no:cacheprovider`: **1,497 passed, 5 skipped in
  327.06s** after the PR #8 CI regression was added. The originally requested
  `903724f` head recorded **1,496 passed, 5 skipped**. The five skips are
  the existing Windows-account symlink-permission cases; real NTFS junction coverage
  remains active. This run includes Phase A/B regressions, projection reconciliation,
  API/CLI parity, authorization, XSS/race behavior, Demo reopen/stale and scale tests.
- Focused Phase C projection/service/HTTP/CLI/demo/UI/scale plus intake regressions:
  **138 passed, 1 skipped in 167.16s**. Final Node-driven
  project/Blueprint/review JavaScript behavior: **65 passed in 4.37s**. The
  full-suite count above is authoritative.
- `python -B examples/verify/project_browser_check.py --output scratch_tmp/phase-c-pr8-ci-fix-browser-green`:
  **29/29**, no page exceptions or external requests, five screenshots; evidence
  `run-60ba829978ca/result.json`. Real HTTP/service/SQLite/engine; no mocked assessment
  response. It covers onboarding, real Overview, risk filtering, detail/focus,
  dependency inventory, real server-process replacement, persisted reopen, Stale,
  Missing Source/relink, partial failure, cancellation, project switch, Demo Critical,
  package search, dependency detail, responsive layout and reduced motion.
- `python -B examples/verify/workbench_browser_check.py --output scratch_tmp/phase-c-pr8-ci-fix-legacy-browser`:
  **101/101**, 27 screenshots; evidence `run-52a7f0f23035/result.json`. Existing
  Blueprint, conversion/review, source evidence, layout, theme, contrast and keyboard
  workflows remain green.
- `ruff check .` and `git diff --check`: clean at the implementation gate.

Browser findings received focused RED/GREEN fixes rather than retries:

1. A completed freshness job returned to the Phase B summary. The new transition
   regression failed RED, then passed after polling explicitly reloaded the saved
   Overview for terminal freshness jobs.
2. Engine identities containing reserved path characters were percent-encoded by the
   browser but compared before decoding, producing 404 detail reads. A real HTTP test
   failed RED. The adapter now decodes the single opaque identity only after route
   segmentation and after project authorization; malformed/NUL encodings fail safely.
3. Dependency rows opened a generic detail that omitted the observed source,
   relationship and target. A focused Node test failed RED; the detail now names all
   three and the real-browser flow opens and verifies it.

### Independent review and correction pass

The first independent whole-branch review recommended **HOLD** with no Critical
findings, eight Important findings and three Minor findings. Verified findings were
  fixed in `5790487`, `7275517` and `fd599c5` with focused RED/GREEN coverage:

- stale Overview refresh no longer dereferences a summary-only button;
- Priority Review uses unresolved Critical/High/Manual counts consistently;
- an Inventory `409` refreshes Overview and Inventory to the same revision before
  page-one reload;
- priority evidence factors derive from real statement codes and Blueprint edges,
  rather than fabricated classifications;
- selected Forms representations no longer count unsupported/unselected binaries;
- package findings, highest risk and dependencies include package spec/body and
  subprogram members without exposing internal membership IDs;
- Overview warnings are capped at 50 with total/shown/truncated metadata;
- priority filters survive search/filter changes;
- the project-scoped priority bridge carries project/finding/filter/revision and
  opens the first eligible evidence detail without writing into the unrelated legacy
  Blueprint store;
- pagination/filter focus, keyboard tab navigation and dependency detail were
  tightened without starting the Phase D decision workflow.

The first full-suite rerun also reproduced a pre-existing Windows locator-index
race twice in 20 fresh processes: `PermissionError: [Errno 13]` while a reader
opened `locators.json` during atomic publication. The regression was not hidden by
retry. A deterministic RED proved that readers were outside the publication lock;
`fd599c5` serializes locator readers and writers while preserving same-thread nested
reads of the last committed snapshot. The original multiprocess test then passed
**50/50** fresh-process repetitions, and committed tests cover the cross-thread wait
and reentrant snapshot contract.

The first PR #8 CI run (`35539796294`) then exposed a separate descriptor Store
contention on Windows Python 3.10: one process opened an already-current project,
entered a redundant second `BEGIN IMMEDIATE` in `sync_descriptor()` and was starved
by 50 legitimate publications until SQLite returned `database is locked`, surfaced
as `ProjectBusy`. The job recorded **1 failed / 1,500 passed**. A deterministic RED
proved that an already-current mirror requested the second writer transaction.
`7c9868f` now records canonical DB+mirror equality during the existing locked
validation and skips only that redundant publication; missing, corrupt and stale
mirrors still repair under the writer lock. The exact failing multiprocess test then
passed **50/50** clean-process repetitions. No automatic product retry was added.

One post-fix browser run also exposed that the acceptance harness compared a raw
underscore relationship enum against intentionally humanized UI text. The harness
now derives the same user-facing label as the product; the focused relationship test,
Phase C browser and legacy browser all pass with no product-behavior relaxation.

The original reviewer suggestion to route project review directly into the legacy
session Blueprint was not applied: that workspace does not consume the persisted
`ProjectAssessment` or its authorization context. Adopting project data there would
create unsafe split state and Phase D scope. The formal design now documents the
read-only revision-bound bridge and the Phase D boundary.

Follow-up reviews found the package-subprogram aggregation omission and a same-thread
deadlock in the first locator-lock correction. Both were reproduced before repair.
The final independent review of `fd599c5` reports **MERGE**, with no Critical or
Important findings, and independently confirms clean diff-check plus the absence of
persisted projection tables and Phase D/E/F scope creep. The reviewer could not run
Python in its tool environment; the execution results in this section are therefore
executor evidence, not an independently repeated Python run.

### 500-Form projection scale gate

`python -B examples/verify/project_overview_performance_check.py --output
scratch_tmp/phase-c-final-performance-verified`, evidence
`run-cba12adc2afe/result.json`.
The deterministic fixture contains **500 Forms, 5,000 findings and 5,000
non-structural dependencies**. All summary/detail denominators reconcile.

| Operation | Iterations | Median | Maximum |
|---|---:|---:|---:|
| Cold Overview (with tracemalloc) | 5 | 4,185.630 ms | 4,298.243 ms |
| Inventory first page | 5 | 1.229 ms | 1.297 ms |
| Combined filter | 5 | 7.708 ms | 8.563 ms |
| Search | 5 | 6.268 ms | 6.977 ms |
| Persisted JSON reopen + Overview | 5 | 3,367.683 ms | 3,411.294 ms |
| Warm cache Overview | 5 | 0.010 ms | 0.026 ms |

Tracemalloc peak: **11,350,347 bytes** (Python allocations, not RSS). This is a
synthetic read-model gate, not engine throughput, browser-rendering, estate or ROI
evidence. The result supports the approved bounded in-memory projection/cache. **No
persisted projection tables were added.** A future storage optimization requires a
new failing scale gate rather than architectural speculation.

### Immutability, security and explicit boundaries

Canonical Git blob IDs for all **24** frozen v1/v2/v3 baseline and ground-truth
artifacts match the Phase B base: zero changes. Version/packaging declarations are
unchanged. No push, merge, tag, release, installer build, live Oracle/APEX validation
or customer corpus was used for Phase C.

Overview returns no source bodies or unrestricted absolute paths. Inventory/detail
reauthorize the opaque project on every request, keep rows bounded, carry assessment
revision and do not combine mismatched pages. Hostile project/warning/item text has
an XSS regression. Local source paths remain governed by Phase A/B capabilities.

Known limitations: the first uncached read can take a few seconds at the named
synthetic scale; browser accessibility is automated keyboard/semantics/contrast and
reduced-motion evidence, not a manual screen-reader audit; source coverage reports
observed counts, not estate completeness; static analysis cannot infer undocumented
business intent or runtime parity. Phase D review redesign, Phase E project-level
APEXlang generation and Phase F reports/packages remain explicitly deferred.

## FormsLang 2.0 Phase D — modernization review (2026-09-20)

Implementation: `8aa534b574bbc868e6b2a119de1051ede1cea9d8`, branch
`codex/formslang-2-phase-d`, base `262361e263ec3b3c4b74b607f3e2f8a7c7a1fa09`.
This closes the review phase, not FormsLang 2.0 or its release gates. Version remains
1.6.0. No release, tag, deployment, main integration or installer acceptance occurred.

### Verification

Windows 11 Pro 10.0.26200 x64, Intel Core i7-9700KF 3.60 GHz, Python 3.12.

- `python -B -m pytest -q -p no:cacheprovider`: **1,531 passed / 5 skipped**, 518.90s.
  The existing five Windows symlink-permission skips remain; junction coverage runs.
- Focused `tests/test_project_review.py tests/test_project_review_scale.py
  tests/test_project_review_ui.py tests/test_project_http.py tests/test_cli_project.py`
  with the same pytest flags: **70 passed**, 287.89s.
- Node/DOM `test_blueprint_ui_behavior.py test_project_ui_behavior.py
  test_review_ui_behavior.py test_project_review_ui.py`: **71 passed**, 4.97s.
- `python -B -m ruff check .`: clean. `git diff --check`: clean.
- `python -B examples/verify/project_browser_check.py --output
  out/phase-d-browser-accessibility`: **41/41**, including 29 prior project checks
  and 12 Phase D checks. Evidence `run-2a4a92a2c79e/result.json`, six screenshots.
  Real API/SQLite/demo; critical confirmation keyboard focus, return context,
  approval/override, inert annotation, stale-client conflict, bulk and reopen.
- `python -B examples/verify/workbench_browser_check.py --output
  out/phase-d-legacy-browser`: **101/101**, 27 screenshots, evidence
  `run-be050250c6bb/result.json`.

The first full run found the structural DOM test did not include new dynamic
templates: 1 failed / 1,520 passed / 5 skipped. Its declaration inspection now
includes actual Review templates/factory IDs, not an exempted ID prefix. Real
browser testing also found stale client Overview counts after review; mutation
invalidates that cache and navigation fetches the current shared projection.

### Independent review and concurrency

Separate-context high-reasoning reviews found and drove RED→GREEN repairs for:
unsupported recommendation approval; excessive bulk exclusions; unsafe co-occurring
LOCK_RECORD despite LOW/AUTO; missing annotation provenance/context; annotation
snapshot races; unsafe string/comment redaction; incoming cross-module bulk impact;
and queue state lost on return navigation. Structural excerpts now use existing
lexical tokens, never regex comment stripping as a privacy mechanism. UI conflicts
preserve the typed draft and require a new submission, not an automatic replay.

The final independent code-review verdict is **MERGE**, with no Critical/Important
findings, conditional on execution gates. Those gates passed above. The reviewer
independently probed redaction, cross-module policy, navigation and history paging;
it did not independently rerun the complete Python/browser suites.

Regression evidence covers simultaneous reviewers (one winner), stale clients,
analysis-worker exclusion, changed source during a review (rollback), exact bulk
preview revisions, injected second-append failure (whole transaction rollback),
foreign project bindings, viewer/revoked authorization, reopen and retained history.
No product retry or sleep was added to conceal a race.

### Synthetic review scale

Fixture: **500 synthetic Forms nodes, 5,000 findings, 5,000 dependencies, 5,001
review events** before the measured bulk commit. This is persisted read-model scale,
not a 500-source-file engine/freshness benchmark; the authorized source manifest is
the compact demo. A 50-item commit finishes with 5,051 events. Single samples from
the focused run, alongside other acceptance processes:

| Operation | Time |
|---|---:|
| Queue first page | 1,534.524 ms |
| Detail | 1,529.275 ms |
| Queue with 5,001 reviews | 2,158.670 ms |
| Priority filter | 2,365.178 ms |
| History/detail | 2,084.166 ms |
| Single mutation | 1,089.871 ms |
| Bulk preview, 50 items | 1,376.392 ms |
| Bulk commit, 50 items | 1,320.637 ms |

An initial entity-by-edge scan measured roughly 4.5–5.4 seconds per read. Replacing
it with one dependency counter reduced the measured cost without changing counts,
classification or persistence. No projection tables were introduced. These are local
synthetic observations, not customer performance or measured analyst savings.

### Boundaries and limitations

All **24 frozen baseline/ground-truth Git blob hashes** match the phase base.
Engine classification and version declarations are untouched. Critical overrides
require rationale/explicit confirmation; AUTO is insufficient for bulk acceptance.
Accepted/Changed resolve review only, not code approval or generation authorization.

Known limitations: conservative bulk policy; UI defaults to priority (other sorting
is available through API/CLI); excerpts start at the first 80 lines and exact source
values require authorized local inspection; critical confirmation uses a generic
control-risk explanation. Non-current assessments reject mutations until refresh.
Automated keyboard/semantics/responsive checks are not a manual screen-reader audit
or human productivity study. Phase E generation and Phase F deliverables are next,
not implied by Phase D acceptance. No live Oracle/APEX validation was performed here.
