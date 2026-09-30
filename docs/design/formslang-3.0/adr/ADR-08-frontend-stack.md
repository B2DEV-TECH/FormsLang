# ADR-08 — Frontend technology and component split

Status: **Proposed (2026-09-30)**. Owner acceptance pending. WP-41 slice 1
([journey-shell-design.md](../journey-shell-design.md)) does not change the
frontend until this ADR is **Accepted**.

## Context

The specification's default is to reuse a lightweight, maintainable stack
unless a measured alternative wins (§31). SCOPE-06 forbids a new frontend
framework without an architecture decision and a demonstrated benefit across
packaging, security, accessibility and CI.

Baseline at `21dcf48`:

- **Markup.** The Workbench UI is HTML, CSS and JavaScript emitted from Python
  string constants in `formslang/ui/*.py`, about 6,500 lines. `formslang/workbench.py`
  serves it.
- **Build.** The UI has no build step and no npm dependency. `desktop/package.json`
  holds only the Tauri CLI and the icon script.
- **Security policy.** The Workbench sends `default-src 'none'; script-src
  'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; connect-src
  'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'`.
- **Vendored code.** One library is vendored: `qrcode-generator` 1.4.4, used
  for MFA enrollment. Its provenance and pinned SHA-256 are in
  `formslang/vendor/README.md`.
- **Packaging.** The Tauri desktop shell and the MSI/NSIS installers package
  the frozen engine, which serves the same UI.

WP-41 needs a new shell:

- a top bar;
- a journey rail with state badges in two scopes;
- a workspace that hosts the existing views;
- keyboard operation and the 390/720/1366 px layouts.

## Alternatives

1. **Keep the current stack**, with a small component convention. This is the
   selected option.
2. **A component framework with a build step** (a bundler plus React, Vue or
   Svelte).
   - It gains components, a large ecosystem and familiar testing.
   - It costs:
     - a Node build chain inside the Python package and the installers, and
       longer CI;
     - a CSP change for bundled scripts;
     - an npm supply-chain surface;
     - either a rewrite of about 6,500 lines or two UI stacks during the
       transition.
   - No measured benefit justifies it under SCOPE-06.
3. **Native custom elements without a build**. They give encapsulation without
   tooling, but they add a second pattern next to the existing one. The
   convention in option 1 can adopt them later if a component needs them.

## Decision (proposed)

Keep server-rendered HTML, CSS and JavaScript emitted from Python strings. Add
no build step and no new runtime dependency. Apply these rules:

- **Placement.** New shell code goes in new, focused modules (for example
  `formslang/ui/journey_shell.py`), not in `modernization_visual.py`, which
  receives no new logic (ARCH-02, baseline audit).
- **Component shape.** A component is a Python constant or function that emits
  markup, plus a small script scoped to that component.
- **No domain rules in the browser.** The rail renders the WP-39a journey
  payload as it is. The browser never computes step state.
- **CSP.** The CSP stays as it is: no external origin and no `eval`.

## Consequences

- Installers, offline operation, the CSP and CI do not change. WP-12 already
  built a read-only journey on this stack.
- There is no component framework, so discipline replaces tooling. The rules
  are focused modules, the existing element-reachability test and the Edge
  acceptance harness.
- `script-src 'unsafe-inline'` remains. This is the existing trade-off, not a
  new one. Moving to nonces or hashes is separate hardening under G-11.

## Implementation boundary

This ADR governs the WP-41 slices. It does not govern the report renderer
(ADR-09), the Tauri desktop shell or the authentication pages.

## Tests

- **Existing:**
  - `tests/test_workbench.py::test_the_ui_script_only_reaches_for_elements_that_exist`;
  - the workbench and corporate Edge browser acceptance;
  - the installed journeys in Installer acceptance.
- **Added by WP-41 slice 1:**
  - the three shell states;
  - the navigation inventory;
  - keyboard operation of the shell controls;
  - the 390/720/1366 px layouts.

## Compatibility

No API or persistence format changes. The existing views keep working while
the shell hosts them.

## Evidence attached

- **WP-12 (PR #28).** A read-only Form journey was built on this stack and
  passed Edge browser acceptance.
- **3.0.0-beta.1 Installer acceptance,** runs 36707032924 and 36707067083. The
  installed beta A→B journey passed 30/30 in each of the 8 jobs, and the
  installed visual check passed 25 checks with no failure. The frontend works
  installed, offline and under the current CSP. The record is in
  `docs/quality-acceptance.md`, section 3.0.0-beta.1.

## Evidence gaps (for the owner to weigh before acceptance)

- No measured bundle or CI comparison against alternative 2 was produced,
  because that alternative is not proposed.
- The current UI has had no WCAG 2.2 AA audit. Slice 1 adds keyboard and
  layout tests only.
