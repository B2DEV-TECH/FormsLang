# 8. APEXlang generation

Open **Generate**, select a module and inspect blockers. Generation supports one independent module application per run, not arbitrary page selection or automatic estate-wide merging.

1. Prepare code review from current sources.
2. Resolve architectural findings in Review.
3. Confirm supported target mappings, security/database prerequisites and observed row keys, with rationale.
4. Save the target plan **before** approving executable code.
5. Inspect and approve each required code unit separately.
6. Generate only when the server policy marks this scope eligible.

A checkbox does not implement missing authorization or business behavior. Unsupported executable mappings, stale evidence, unresolved critical/manual architecture, missing keys and unapproved code block output. When omission would remove a required control, the module is blocked rather than emitted as apparently usable.

Artifacts are versioned and hash-bound. Download a ZIP and edit a separate copy under version control; do not edit managed artifacts in place. Human edits are never silently overwritten. Database refactoring candidates are descriptions, not invented executable SQL.

Generation does not import, deploy or execute DDL. See [generation boundaries](../project-generation.md).
