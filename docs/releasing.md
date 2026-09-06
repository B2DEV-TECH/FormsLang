# Releasing FormsLang

One version number declared in seven files, one annotated tag, one GitHub
release whose assets are the exact binaries the acceptance workflow
tested. The steps, in order.

## 1. Bump the version

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

## 2. Tag before publishing, annotated

Commit the bump, then:

```bash
git tag -a v1.2.3 -m "FormsLang 1.2.3"
git push origin main v1.2.3
```

An annotated tag records who cut the release and when, and `git describe`
sees it. A tag created from the GitHub release page is lightweight and
does not exist in your clone until `git fetch --tags`.

## 3. Build and test the installers on CI

Run the **Installer acceptance** workflow on the tag (Actions, Installer
acceptance, Run workflow). It calls `build-installers.yml`, which freezes
the engine from `packaging/formslang-engine.spec`, then on two disposable
Windows runners installs the latest published release, saves an approval
through it, upgrades to the candidate and verifies that the approval, the
export and the native desktop survived, once for NSIS and once for MSI.

Leave the baseline input empty unless the candidate version is already
published; then name the release to upgrade from.

Download the `installers-<version>` artifact from that run. Those are the
files to publish, and the build log prints their SHA-256. A local build
from the README recipe is fine for trying things out, but publish the CI
artifact, since that is what the acceptance ran against.

## 4. Publish and record

Create the GitHub release from the existing tag, attach the two installers
from the artifact and paste the changelog entry as the body. Then add a
section to `docs/quality-acceptance.md` with the tested commit, the CI and
acceptance run links, the installer hashes and what remains untested.
Compare the published digests with the ones you recorded:

```bash
gh release view v1.2.3 --json assets --jq '.assets[] | "\(.digest)  \(.name)"'
```

Runtime acceptance against a real Forms and APEX instance is a separate
task and is never implied by a green release.
