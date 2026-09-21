# Assessment reports and delivery

The FormsLang 2.0 **Reports** workspace exports a persisted
assessment without reanalysis, AI calls, database connections or code generation.
It shares ProjectService, ProjectAssessment, review history and artifact records
with the other interfaces. There are no report/projection persistence tables.

## Workflow

Open an analyzed project, choose **Reports**, inspect its freshness, then download
an Executive Assessment, Technical Assessment, Risk Report, Backlog CSV/JSON,
Decision History JSON or Modernization Package ZIP. HTML is self-contained,
printable and script-free; FormsLang need not remain running to read it.

Human rationale/annotation text is excluded by default. Opting in affects decision
and backlog exports, never executive HTML. Standalone sensitive files have a
`-sensitive` filename and disclosure metadata. Technical identifiers remain present:
default exports are not anonymous. Review distribution policy before sharing.

Generated APEXlang requires a separate explicit package opt-in. It may contain
business logic. Inclusion verifies recorded revisions, target plan, current code
approval fingerprint, archive layout and every file hash. Missing/corrupt module
sessions are read-only failures, never recreated. Edited, stale or unavailable
artifacts are excluded with reasons, not regenerated or silently overwritten.

## Snapshot contract

The request binds project, source, analysis and review revisions plus a digest of
the captured assessment/review/target/artifact metadata. Stale client requests return
409 and require explicit reload. A database read snapshot captures consistent
history and metadata; project operation locking prevents normal concurrent writes.
A report describes that historical snapshot, not later reviews. Freshness is checked
again before returning, so a source change cannot silently retain a Current label.

Stale, incomplete and missing-source assessments can be delivered, with their
actual state visible. Export does not change the assessment timestamp. ZIP members
are sorted with fixed ZIP timestamps. Equal snapshots and disclosure options yield
equal bytes while source and included artifact integrity remain unchanged.
The manifest hashes every member except itself and records versions, revisions,
target, persisted timestamps, artifact validation evidence, exclusions and limits.
Validation is syntax evidence, not runtime equivalence.

## Package contents

```text
README.md
manifest.json
assessment/ executive-summary.html, technical-assessment.html,
            risk-report.html, application-inventory.json
architecture/ target-architecture.md, dependency-map.json,
              modernization-decisions.json
backlog/ modernization-backlog.csv, modernization-backlog.json
review/ decisions.json, unresolved-decisions.csv
database/ prerequisites.md, refactoring-candidates.md
evidence/ analysis.json
apexlang/<artifact-id>/...  (only verified, explicitly included artifacts)
```

Database documents are proposals/prerequisites, not executable SQL. Target
architecture is evidence-linked suggestions, not a fabricated deployed design.
Evidence is a structural projection, not the full source-bearing assessment.
Free-form engine reasons can contain literals from source code; deliverables use
structural signal identities instead. Exact explanations remain in authorized Review.
Host-path/credential-shaped metadata is suppressed. No filter can guarantee that
arbitrary human notes contain no secrets; sensitive opt-in requires human inspection.

Backlog JSON retains values without spreadsheet escaping; CSV neutralizes formula
prefixes and includes snapshot provenance columns. JSON decision/backlog exports
are envelopes with `metadata` and `rows`. Engine recommendation and human decision
remain distinct, with history applicability and annotations. Deferred/Needs Review
remain unresolved. Empty CSV has headers; its standalone filename includes snapshot
identity. There are no effort, cost or elapsed migration estimates.

## API and CLI

- `GET /api/v2/projects/:id/reports` returns formats and snapshot binding.
- `GET /api/v2/projects/:id/reports/:format` downloads an attachment; supply the
  complete binding and explicit `include_notes=0|1`, `include_artifacts=0|1`.
- Metadata requires current VIEW permission; downloads reauthorize EXPORT
  permission. Standard project isolation and authenticated session rules apply.

```console
formslang project report path/to/.formslang/project.json --format status --json
formslang project report path/to/.formslang/project.json --format executive --output executive.html
formslang project report path/to/.formslang/project.json --format package --include-artifacts --output delivery.zip
```

CLI refuses to overwrite existing output. UI/API/CLI all call ProjectReportService
through ProjectService. No deployment or automatic report publication occurs.

## Current limits

Delivery is synchronous and in memory, capped at 128 MiB of uncompressed members.
Large reports can require noticeable memory/time; no streaming or persistent
projection architecture is claimed. Artifact inclusion is conservative and may
exclude otherwise useful historical code after review changes. Stored validation
records remain historical evidence; edited included artifacts cannot retain a
current Validated claim. No PDF renderer, issue-tracker connector, executable
database refactoring generator or source-complete evidence export is implemented.
Release/installer/upgrade acceptance is separate from this phase.
