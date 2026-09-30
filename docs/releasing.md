# Releasing FormsLang

One version number declared in seven files, one annotated tag, one GitHub
release whose assets are the exact binaries the acceptance workflow
tested. The steps, in order.

## 1. Prepare an accepted candidate, then bump the version

Complete phase implementation, independent review and local regression first.
Critical/Important safety issues block release. Preserve a candidate branch; do not
publish incomplete work to main merely to trigger a release. Version preparation
does not authorize a tag or claim installer acceptance.

Set the new version in `pyproject.toml`, then in the files that must agree
with it. `tests/test_version.py` fails until all of them do.

| File | Why it carries the version | How to refresh |
|---|---|---|
| `formslang/__init__.py` | fallback for source checkouts without installed metadata | by hand |
| `desktop/package.json` | desktop shell package | by hand |
| `desktop/package-lock.json` | lock of the above | `npm --prefix desktop install --package-lock-only` |
| `desktop/src-tauri/tauri.conf.json` | installer file names and the version Windows shows | by hand |
| `desktop/src-tauri/Cargo.toml` | Rust crate of the desktop shell | by hand |
| `desktop/src-tauri/Cargo.lock` | lock of the above | rewritten by the next `npm run tauri build` |

Then `pip install -e .` so the installed metadata follows; the engine
spec refuses to freeze a stale install.

Move the `[Unreleased]` section of `CHANGELOG.md` under the new version
with its date, add the compare link at the bottom and point `[Unreleased]`
at the new tag. Run `python -m pytest -q` and `python -m ruff check .`.

## 2. Build and test the exact candidate before tagging

Commit and push the candidate branch. Run the full CI matrix through a PR to main.
Run **Installer acceptance** on that exact candidate branch/ref (Actions, Installer
acceptance, Run workflow). It calls `build-installers.yml`, which freezes the
engine from `packaging/formslang-engine.spec` and builds the MSI and NSIS
installers once for the run. Four jobs then use them on disposable Windows
runners:

- `clean (nsis)` and `clean (msi)` install the candidate on a fresh runner at a
  non-ASCII user-space path and drive the packaged product.
- `upgrade (nsis)` and `upgrade (msi)` install the baseline release, save an
  approval through it, upgrade to the candidate and verify that the approval,
  the export and the native desktop survived. They also exercise packaged
  project/review/generation/report commands and uninstall/reinstall
  preservation.

A same-binary smoke is not an upgrade result.

The `baseline` input names the release to upgrade from. Empty means the latest
published release, which GitHub resolves without prereleases. Name it
explicitly when the candidate version is already published or when more than
one upgrade path must be accepted, and run the workflow once per baseline:
3.0.0-beta.1 used two runs, with baselines `2.2.0` and `2.1.0`.

Download the `installers-<version>` artifact from one of those runs. Those are
the files to publish, and the build log prints their SHA-256. Every run builds
its own installers, and rebuilding the same commit has produced different
bytes, so record which run built the published files and which baselines
exercised those exact bytes. The other runs cover the same commit with a
sibling build. A local build from the README recipe is fine for trying things
out, but publish the CI artifact, since that is what the acceptance ran
against.

Any candidate code change invalidates the previous exact-candidate acceptance.
Do not tag if matrix, browser, generation, frozen benchmark, security, installer,
upgrade, version consistency or asset checks fail. Record RELEASE BLOCKED and retain
the recoverable candidate instead of bypassing a gate.

## 3. Integrate accepted state and create the annotated tag

Verify remote ancestry, checks and exact accepted tree. Integrate through repository
workflow, verify main and its final checks, then tag the accepted product state:

```bash
git tag -a v2.0.0 -m "FormsLang 2.0.0"
git push origin v2.0.0
```

Never move a published tag. If integration changes the product tree, rebuild and
retest before tagging. Record both tested candidate and integration SHAs where a
merge commit preserves the exact tested tree. Only validated CI-produced binaries
may become release assets.

## 4. Publish and record

Create the GitHub release from the existing tag, attach the two installers
from the artifact and paste the changelog entry as the body, or the version's
`docs/release-notes-<version>.md` when one exists. Publish a beta
with `gh release create --prerelease --latest=false`, so the stable release
stays the latest one. Then add a
section to `docs/quality-acceptance.md` with the tested commit, the CI and
acceptance run links, the installer hashes and what remains untested.
Compare the published digests with the ones you recorded:

```bash
gh release view v1.2.3 --json assets --jq '.assets[] | "\(.digest)  \(.name)"'
```

Runtime acceptance against a real Forms and APEX instance is a separate
task and is never implied by a green release.
