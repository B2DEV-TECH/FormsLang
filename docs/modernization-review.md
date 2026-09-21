# Modernization Review

Open **Start Priority Review** from Overview or **Review** in project navigation.
Static review needs neither AI nor a database connection. This documents the
FormsLang 2.0 implementation; release acceptance is recorded in quality-acceptance.md.

## States and evidence

| Display | Internal action | Resolved for review progress |
|---|---|---|
| Pending | No applicable event | No |
| Accepted | APPROVE | Yes |
| Changed | MODIFY | Yes |
| Needs Review | REJECT | No |
| Deferred | DEFER | No |
| Needs Revalidation | STALE projection over retained history | No |

Engine evidence stays in ProjectAssessment. Decisions append to `blueprint_review`;
independent annotations append to `blueprint_annotation`. Review completion is not
code approval or generation authorization. Changing direction to Human Review
records an architectural choice; it does not make unresolved architecture safe.

Accept can use **Accepted engine recommendation.** Change requires a rationale and
a supported direction. UNKNOWN/unsupported directions cannot be accepted. CRITICAL
Change additionally requires confirmation that current evidence was examined.
Needs Review records a reason; Defer remains unresolved.

The split pane keeps filters and the selected finding. Search, module/source type,
risk, recommendation, intervention and status compose server-side. Priority uses
Phase C's ordering and visible factors. Queue pages default to 50, maximum 200.

Details distinguish facts/inferences from human decisions/annotations. Structural
source excerpts omit literals/comments and suppress recognized sensitive contexts.
Each excerpt is limited to 80 lines/8,000 characters, at most 20 related entities.
Inspect authorized local source for exact values. Lists contain no source bodies.
History/annotation pages default to 50, maximum 200. Old events remain visible with
revision applicability. Human annotations do not modify deterministic evidence.

## Revisions and concurrency

Writes require project ID, source/analysis/review revisions and exact finding
revision. Reviewer identity comes from the server's current identity, never the
browser. Read-only grants cannot mutate. All adapters call ProjectService and its
focused ProjectReviewService delegate.

The service reauthorizes and verifies source hashes, then uses the existing project
worker lock and SQLite transaction. Hashes are checked again before commit. A stale
client, concurrent review or changed source causes conflict and rollback. Replaying
an old request cannot append duplicate history. UI conflicts reload evidence and
require a new human submission.

Current means as of the last hash check, not a filesystem watch or atomic control
over external editors. Subsequent changes invalidate applicability on freshness
check. Prior events are retained.

## Bulk review

Select up to 200 findings on the current page, preview eligibility, then confirm.
Ordinary bulk Accept requires LOW, AUTO, Pending/current evidence, a supported
mechanical direction and explicit safe evidence. AUTO alone is insufficient.
Preserve, Convert and Use Native APEX are the initial direction allowlist.

Mechanical engine signals and their co-occurring built-ins are checked. A native
SHOW_ALERT confirmation can qualify; adding LOCK_RECORD excludes it even when the
engine still reports LOW/AUTO. Unknown/sensitive evidence, unresolved dependencies,
critical/manual/stale findings and unsupported directions are excluded with reasons.
This conservative policy may require individual review of benign findings.

Preview binds project/revisions, exact selection, policy and eligibility. Commit
recomputes under one transaction. Mismatch rejects every write; otherwise only the
eligible set is committed atomically. Bulk Defer/Needs Review have the same revision
contract and remain unresolved.

## API and CLI

```text
GET  /api/v2/projects/:id/review
GET  /api/v2/projects/:id/review/:finding
POST /api/v2/projects/:id/review/:finding
POST /api/v2/projects/:id/review/bulk-preview
POST /api/v2/projects/:id/review/bulk
```

Single POST uses `operation: DECIDE` (default) or `ANNOTATE`. Detail returns the
`binding` object to submit unchanged. List supports inventory filters,
`sort=priority`, `revision`, `review_revision`, `offset` and `limit`. Detail's
offset/limit bound history. Conflicts return HTTP 409.

```bash
formslang project review list ./project --risk CRITICAL --json
formslang project review show ./project --finding FINDING_ID --json
formslang project review decide ./project --finding FINDING_ID --action APPROVE --binding '{"project_id":"...","analysis_revision":"...","source_revision":"...","review_revision":0,"finding_revision":"..."}' --json
```

`decide` supports `--recommendation`, `--rationale`, `--reason`, `--confirm-critical`.
`annotate` accepts `--kind`, `--note` and the same binding. Authenticated installations
use the authorized Workbench/API session; local CLI cannot bypass authenticated mode.

## Boundaries

There are no persisted projection tables. Scale measurements gate in-memory
optimization. Phase D does not generate/deploy code, prove runtime parity or replace
UAT. Automated browser/accessibility checks are not human usability research or a
manual screen-reader audit. Project generation and delivery remain Phase E/F.
