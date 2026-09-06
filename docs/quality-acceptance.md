# Quality acceptance for existing features

Version 1.2.1 corrects review integrity, source preservation and header
usability. It does not add product features or claim that a passing test
suite proves every Oracle Forms application can be migrated faithfully.

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
