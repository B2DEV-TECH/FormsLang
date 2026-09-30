# FormsLang 3.0.0-beta.1

This beta exercises an installed, local modernization journey on a saved
project. It is a subset of the [FormsLang 3.0 master
specification](https://github.com/B2DEV-TECH/FormsLang/blob/v3.0.0-beta.1/docs/design/formslang-3.0/master-specification.md), not completion of
that specification. Use the product's supported source representations and
review each generated scope before relying on an output.

## Available in this beta

| Area | Supported scope |
|---|---|
| Local project | Create, analyze and reopen a project with supported Forms XML and database sources. The CLI and Workbench can read the saved assessment offline. |
| Form exploration | Open a Form, inspect persisted relationships, redacted source evidence and unresolved references, then follow a resolved Form link. The view shows current generation blockers. |
| Finding review | Accept or defer a saved assessment finding against its current revision and inspect its append-only review history. Target-plan and generated-code approvals are separate. |
| Target output | For an eligible module, separately confirm the target plan and executable code, generate an APEXlang ZIP, and verify its recorded SHA-256 on download. The package is not deployed. |
| Reports | Export executive and technical HTML, a finding-review decision record and a modernization package from the saved project. |
| Windows installers | MSI and NSIS are built from one candidate commit. Publication requires disposable Windows clean installs and separate 2.1.0 and 2.2.0 upgrades to exercise the frozen engine, Workbench, native shell and saved state. |

The installed beta acceptance fixture uses CUSTOMERS and SHIPMENTS for Form
navigation and a separate eligible NOTICE Form for explicit review and
generation. It tests the same saved project, but following SHIPMENTS clears the
prior relationship selection. Review and generation start from their own
controls; there is no seamless context handoff from the Form link.

Validation records the attempted mode and artifact identity. When SQLcl with
APEXlang support is unavailable, the observed result is **Not Validated**.
Offline syntax checking is not runtime equivalence, import proof or user
acceptance. Static relationships do not establish an executed Forms navigation
order.

An intermittent HTTP 500 on a job-status read was observed in Windows CI,
including the [#35 Python 3.13 job](https://github.com/B2DEV-TECH/FormsLang/actions/runs/36672169335/job/109749313078).
Its cause is unknown. [#23](https://github.com/B2DEV-TECH/FormsLang/pull/23)
tracks diagnostic logging separately and does not establish a fix.

The app, CLI and installer assets identify themselves as `3.0.0-beta.1`.
Python distribution metadata normalizes that prerelease to PEP 440
`3.0.0b1`. The MSI requires a numeric `ProductVersion`, so this beta uses
`2.99.1` internally. This is above the published 2.2.0 MSI version and below
a future `3.0.0`; the beta MSI keeps the same `UpgradeCode` as 2.2.0. This
avoids a version-order or product-family
obstacle to a later 3.0.0 major upgrade, but a beta-to-final installation must
be tested with the final artifact. The generated MSI currently permits
downgrades; its version number does not enforce downgrade prevention. Windows
Installer uses three numeric `ProductVersion` fields ([Microsoft
documentation](https://learn.microsoft.com/en-us/windows/win32/msi/productversion)).
Rebuilding installers from the same source commit has produced different
bytes. Release hashes identify the exact uploaded MSI and NSIS; byte-for-byte
build reproducibility is not claimed.

## Planned beyond this beta

The following are not claimed by this build merely because a 3.0 version is
shown:

- Whole-repository checkpoints, object verification, `log/show/diff`, baselines,
  portable history and trusted Git exchange (WP-20), plus the complete 2.x/1.x
  migration and restore contract (WP-22). Existing finding review history is a
  narrower capability.
- The `.flm` decision language, semantic import and full decision lifecycle
  with preview, apply, approval, supersession and conflict handling (WP-30/31).
- A complete typed service, CLI machine contract and new shared Workbench
  journeys, plus opt-in local read-only MCP parity (WP-39 through WP-42).
- Hardened plan closure and target coverage, tool/import/runtime validation
  applicability, policy-scoped AI assistance and an optional execution loop
  (WP-45 through WP-48). The core beta does not require an AI account.
- The complete report catalog, inspected PDF output, security and performance
  evidence, and five-person usability acceptance (WP-50, WP-60 through WP-62).

## FormsLang 3.0 release gates

All 13 gates in the [implementation
checklist](https://github.com/B2DEV-TECH/FormsLang/blob/v3.0.0-beta.1/docs/design/formslang-3.0/implementation-checklist.md#release-gates)
remain open for the full 3.0 release. G-01 and G-04 are in progress; the
other 11 remain **NOT ASSESSED**. A successful beta installer journey
contributes evidence to parts of these gates without closing them.

| Gate | Open requirement | Current status |
|---|---|---|
| G-01 | Baseline truth and reused code verified; no duplicate engine. | In progress |
| G-02 | Whole-state checkpoint, integrity, accepted history and recovery. | Not assessed |
| G-03 | Authorized portability, Git exchange, conflicts and origin trust. | Not assessed |
| G-04 | Positive and negative extraction/graph evidence with honest limits. | In progress |
| G-05 | Language parser, approvals, applicability, import and review diffs. | Not assessed |
| G-06 | Complete Workbench/CLI journey parity, accessibility and machine contracts. | Not assessed |
| G-07 | Target capability scope, deterministic delivery, closure and omissions. | Not assessed |
| G-08 | Static, tool, import, runtime and UAT validation evidence by level. | Not assessed |
| G-09 | Reconciled report catalog, safe exports and inspected PDF. | Not assessed |
| G-10 | Supported 2.x migration, backup/restore and same-commit installers. | Not assessed |
| G-11 | Local and authenticated security controls across projections. | Not assessed |
| G-12 | Ratified performance budgets and five-person usability protocol. | Not assessed |
| G-13 | README, quickstart, examples, schemas, migration and release claims aligned with the product. | Not assessed |

The release decision must use exact-head CI and installed MSI/NSIS evidence,
asset hashes, and owner review. A beta publication cannot be used as evidence
that these final 3.0 gates have passed.
