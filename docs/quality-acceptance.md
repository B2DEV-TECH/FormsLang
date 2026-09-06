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

## Acceptance layers

| Layer | Required evidence | Boundary |
|---|---|---|
| Review integrity | Short bodies at every scope, recovery into an older session, unchanged decisions, refusal of changed source before insertion | Synthetic source regression tests |
| Source preservation | Invalid or changed same-name uploads leave the active source and review intact | Local HTTP integration tests |
| Failure recovery | Cancellation, failed providers, saved progress and crashed-job reconciliation | Existing store, workbench and AI tests; not a power-loss certification |
| Desktop usability | Reachable header actions at 1100, 1280 and 1380 px; review, reload, Doc, Preview and export | Browser checks plus packaged-engine smoke; native installer acceptance is separate |
| Reproducible export | Same session and configuration produce byte-identical ZIPs | Does not prove imported pages render or behave correctly |
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
