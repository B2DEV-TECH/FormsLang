# FormsLang 2.0 — Oracle Forms to APEX Modernization Workbench

FormsLang 2.0 brings source discovery, assessment, modernization review, eligible
APEXlang generation and consulting deliverables into one persistent project workflow.

## Who it is for

Oracle Forms/APEX developers, architects, consulting leads and application owners
who need evidence before making modernization decisions. The machine inventories,
correlates and triages; people retain architecture, business intent and UAT.

## Typical workflow

Install → New Project → Select legacy sources → Analyze → Overview/Inventory →
Review → Generate eligible APEX 26.1 / APEXlang → Validate → Export package.

- Four-step onboarding and a real synthetic demo need no external AI or database.
- Saved evidence includes source fingerprints, warnings and freshness/relink state.
- Review preserves engine recommendations separately from human decisions, annotations,
  rationale and history. Critical overrides and bulk operations have server-side policy.
- Selected-module generation separately checks architecture, code, target prerequisites
  and current revisions. Versioned artifacts are hash-bound and never auto-deployed.
- Printable executive/technical reports, CSV/JSON backlog and modernization packages
  carry provenance, exact hashes, validation evidence and explicit exclusions.
- CLI and versioned project APIs use the same services. Existing 1.x sessions and
  power-user commands remain available; back up originals before upgrading.

## Local-first and limitations

Static assessment/review/deterministic generation work offline. AI is optional,
explicitly configured assistance, never automatic approval. Default reports exclude
source bodies/private notes but retain technical identifiers and are not anonymous.

Forms2XML is required for supported Forms semantics; binary discovery is not parsing.
Generation currently creates one independent eligible module application, not a merged
estate. Unsupported mappings, missing controls and stale approvals remain blocked.
SQLcl offline validation is syntax/structure evidence, not runtime parity or Oracle
endorsement. Architects, developers and business owners still review and perform UAT.

## Install and upgrade

Release assets are the Windows EXE/MSI produced by the accepted CI build, not local
rebuilds. Exact hashes, 1.6.0 upgrade evidence and outstanding manual validation are
recorded in [quality acceptance](quality-acceptance.md). A candidate branch or this
prepared note alone does not mean a release has been published.

[User guide](user-guide/README.md) · [Manual validation](manual-validation-2.0.md) ·
[APEX 26.1 boundaries](apex-26-modernization.md) · [Security/privacy](user-guide/12-security-and-privacy.md) ·
[Changelog](../CHANGELOG.md) · [Roadmap](roadmap-2.md)
