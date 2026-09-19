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
