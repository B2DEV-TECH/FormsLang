# Oracle Forms to APEX with FormsLang

FormsLang helps Oracle teams inspect Forms and database source before modernization
decisions. Automate what is safe, assist what is complex, and escalate architectural
judgment to people. It is not a one-click FMB converter.

Stable 1.x provides the existing CLI, Workbench, Blueprint/review and APEX export
capabilities described in the [README](../README.md). Unreleased Phase B adds a
persistent project workflow: choose sources, discover, analyze, inspect a saved
summary, close and reopen. See [project workflows](project-workflows.md).
Its target profile is Oracle APEX 26.1 / APEXlang, not certification that arbitrary
Forms behavior has been converted.

Inputs include Forms2XML and supported SQL/package/DDL source. FMB, PLL, MMB and
OLB are discovered, not silently treated as parsed representations. Optional
Forms2XML conversion needs installed Oracle tooling and explicit confirmation.
Incomplete database context and dynamic SQL limit static evidence.

The pipeline stages and hashes source, reuses deterministic parsers and cross-layer
reasoning, and persists an assessment/Blueprint with warnings and provenance. It
needs neither external AI nor database access. Parse failures remain visible, and
changed source does not silently inherit approval.

FormsLang inventories, correlates dependencies and proposes evidence-backed
directions. Specialists interpret undocumented intent, choose architecture, review
security/workflows and test behavior. Business-rule candidates are not verified
business intent.

APEXlang remains a reviewable output of existing export capabilities. The future
project-level reviewed generation workflow and modernization package are not Phase B
features. Validation, import and deployment remain separate actions; syntax validity
is not functional equivalence. FormsLang does not replace architects, UAT or explicit
approval to execute changes in an Oracle environment.

The intended benefit is less repetitive discovery and more time for expert decisions.
No measured analyst-hours saving or project-duration estimate is claimed.
