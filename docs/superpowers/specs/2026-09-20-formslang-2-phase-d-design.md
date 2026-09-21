# FormsLang 2.0 Phase D: Modernization Review and Human Decision Governance

Status: architecture approved by the project owner on 2026-09-20. This document
defines Phase D only. It does not claim implementation or acceptance, and it does
not authorize Phase E project-level APEXlang generation, Phase F reports/packages,
a version change, tag, release or merge.

## Intent and verified starting point

Turn the persisted findings, deterministic evidence and append-only review history
delivered by Phases A-C into an efficient, auditable corporate review workflow.
An Oracle architect must be able to understand a recommendation, inspect its
evidence, accept or override it safely, and leave a revision-bound decision trail
without changing the engine's original result.

- Branch: `codex/formslang-2-phase-d`.
- Base: `262361e263ec3b3c4b74b607f3e2f8a7c7a1fa09`, merge of Phase C PR #8.
- Pre-change Windows / Python 3.12 verification: **1,497 passed, 5 skipped in
  329.57 seconds**. The five skips require symlink privileges unavailable to the
  current Windows account.
- Product version remains 1.6.0. No tag or release is created.
- Frozen benchmark and ground-truth history remains immutable.

The owner's Phase D brief is authoritative. Existing project identity,
authorization, assessment persistence, source/analysis/review revisions,
freshness, Phase C projections, CLI, HTTP and Workbench shell remain the foundation
and are not redesigned.

## Product and architecture principles

The product boundary remains explicit:

```text
Engine Recommendation
        |
        v
Human Decision Overlay
        |
        v
Code Approval                 (not implemented in Phase D)
        |
        v
Generation Authorization     (not implemented in Phase D)
```

The deterministic engine recommendation and evidence are immutable assessment
facts. Human decisions and annotations are append-only overlays. Phase D never
rewrites an engine recommendation, reruns analysis for a review mutation, or treats
review completion as generation authorization.

The selected implementation architecture is:

```text
Workbench / HTTP / CLI
          |
          v
    ProjectService facade
          |
          v
 ProjectReviewService
    /       |       \
queue    policy    mutations/history
    \       |       /
 ProjectAssessment + blueprint_review + blueprint_annotation
          |
          v
   ProjectStore / SQLite
```

`ProjectService` remains the sole interface facade and reauthorizes each operation.
A focused `ProjectReviewService` owns queue/detail projection, decision validation,
bulk policy, history and annotations. It does not become a second project model or
analysis engine.

Phase D introduces no persistent review projection tables. Queue and progress
views are deterministic projections over the current assessment and append-only
review records. The 5,000-finding scale test is the gate for proposing indexes or
future persisted projections. Any such optimization requires measured evidence and
separate architecture review.

## Authoritative data and additive persistence

### Decisions and history

The existing `blueprint_review` table remains the authoritative append-only human
decision history. Its existing internal actions remain compatible:

| User-facing state | Existing internal action | Progress semantics |
| --- | --- | --- |
| Pending | no current applicable event | unresolved |
| Accepted | `APPROVE` | resolved |
| Changed | `MODIFY` | resolved |
| Needs Review | `REJECT` | unresolved |
| Deferred | `DEFER` | unresolved |
| Needs Revalidation | `STALE` projection | unresolved |

`Needs Revalidation` is not a new stored action. It is projected when existing
history is no longer applicable to the current finding, analysis/source revision,
engine recommendation/version or target binding. History is retained; an old
approval is never copied silently to new evidence.

Each new review event extends the existing `finding_snapshot` JSON with bounded,
versioned objects instead of duplicating project state in new columns:

```json
{
  "project_binding": {
    "analysis_revision": "...",
    "source_revision": "...",
    "finding_revision": "...",
    "engine_recommendation": "MOVE_TO_PLSQL_API",
    "engine_version": "...",
    "target": {
      "platform": "Oracle APEX",
      "version": "26.1",
      "representation": "APEXlang"
    }
  },
  "human_context": {
    "reason_code": "ARCHITECTURE_DECISION",
    "owner": null,
    "note": "...",
    "critical_evidence_confirmed": false
  }
}
```

The snapshot remains bounded and contains identities/evidence references rather
than unbounded source bodies.

### Human annotations

Add one append-only `blueprint_annotation` table only if implementation confirms
the existing schema cannot represent annotations without conflating them with
decisions. It stores:

```text
id
entity / finding identity
annotation kind
note
reviewer identity
created_at
analysis/source/finding/engine/target binding snapshot
```

Supported annotation kinds are initially bounded to:

```text
CONFIRMED_BUSINESS_RULE
PRESENTATION_ONLY
DATABASE_API_AUTHORITATIVE
LEGACY_LOGIC_OBSOLETE
NEEDS_BUSINESS_OWNER_DECISION
```

Annotations have independent history and never mutate engine facts or decision
state. An annotation insert increments `modernization_project.review_revision`
through an additive trigger, just as a review event does. It never changes
`source_revision` or `analysis_revision`.

### Transactions and revisions

A single decision or annotation transaction atomically persists:

```text
event/history row
provenance and revision binding
monotonic review_revision increment
```

ProjectStore's existing `BEGIN IMMEDIATE` write boundary remains authoritative.
Within that transaction the service compares the submitted analysis, source,
review and finding revisions with current values before inserting. A mismatch
returns conflict and writes nothing. No retry masks a race.

## Review read contracts

### Queue

`ProjectReviewService.list_queue(...)` returns a bounded, JSON-compatible page:

```json
{
  "project_id": "...",
  "analysis_revision": "...",
  "source_revision": "...",
  "review_revision": 12,
  "freshness": "CURRENT",
  "filters": {},
  "sort": "priority",
  "offset": 0,
  "limit": 50,
  "total": 1284,
  "items": []
}
```

Default limit is 50 and maximum limit is 200. The default sort reuses Phase C's
transparent priority order:

1. unresolved CRITICAL safety findings;
2. unresolved HIGH findings;
3. other unresolved findings by risk;
4. MANUAL findings;
5. stale decisions;
6. evidenced API bypass, duplicated logic or cross-module impact;
7. dependency centrality;
8. stable source/finding identity.

It supports server-side search, stable sorting and composable filters for risk,
recommendation, intervention, review status, module, source type, critical-only,
manual-only and stale-only. Named shortcuts include Pending, Critical, High, Human
Review, Move to PL/SQL API, Use Native APEX, Needs Revalidation and Deferred.

### Detail

`ProjectReviewService.detail(finding_id, ...)` answers five questions directly:

1. What is this?
2. Why does it matter?
3. What does FormsLang recommend?
4. What evidence supports it?
5. What should happen next?

The response distinguishes four evidence classes:

```text
Observed Fact
Engine Inference
Human Annotation
Human Decision
```

It may include source identity, relative location, related database objects,
incoming/outgoing dependencies, risk evidence, reason, target suggestion and
bounded history. Raw reason codes and machine details live under an Advanced
section.

Source excerpts are permitted only when project authorization allows them. They
are focused around known evidence locations and capped by line count and character
count. List responses never contain excerpts. Standard responses never contain an
absolute host path, credential, private membership identifier or an unbounded
source/package body.

History is bounded separately from detail, with default and maximum limits. Large
history is never embedded in every queue row.

### Review progress

One shared projection calculates both Overview and Review workspace counts:

```text
Resolved     Accepted + Changed
Unresolved   Pending + Needs Review + Deferred + Needs Revalidation
```

It reports factual current-finding counts including total resolved/total,
critical resolved/total and manual resolved/total. Deferred is intentionally not
complete. The UI may say `Review complete` only when every applicable current
finding meets the documented resolved definition; it never says migration is
complete.

## Decision commands and policy

Every mutation derives the reviewer from `ProjectAccess.actor`. Local mode uses the
existing OS/local identity; authenticated mode uses the current server session.
The browser never supplies an authoritative reviewer display name.

All commands submit exact project, analysis, source, review and finding revisions.
They are valid only for the current authorized project assessment. Stale, missing,
incomplete or unverified assessment conditions return a safe conflict/remediation
response rather than mutating historical evidence.

### Accept

Accept records `APPROVE` against the current engine recommendation. It may use the
structured rationale `Accepted engine recommendation.` so users do not type
repetitive prose for simple decisions. An optional note is allowed. The engine
recommendation remains stored separately and unchanged.

### Change

Change records `MODIFY` and requires a free-text rationale. Allowed target
directions are:

```text
PRESERVE
CONVERT
REFACTOR
MOVE_TO_PLSQL_API
REPLACE_WITH_APEX_NATIVE
MANUAL_REVIEW
DROP
```

Choosing the current recommendation is an Accept, not a Change. `UNKNOWN` and
legacy-only internal directions such as `WRAP_AS_API` are not silently mapped to a
different user choice; they remain unresolved unless an explicit supported choice
is made.

A HIGH-risk change always requires the normal explicit rationale. A CRITICAL
change additionally requires a checked acknowledgement that the reviewer examined
the current evidence, plus current revision binding. Missing confirmation,
rationale or current revisions is rejected server-side.

### Needs Review

Needs Review records `REJECT` with a structured reason and optional note. Initial
reasons are:

```text
BUSINESS_OWNER_INPUT
ARCHITECTURE_DECISION
INSUFFICIENT_DATABASE_CONTEXT
UNCLEAR_LEGACY_INTENT
OTHER
```

It remains unresolved and may block later generation policy. Phase D does not
implement that generation gate.

### Defer

Defer records `DEFER` with optional reason, owner and follow-up note. It remains
unresolved. Phase D does not build assignment or social collaboration around the
owner field.

### Replay and idempotency

The primary safety contract is revision compare-and-swap. A replay after the first
successful mutation carries an old review revision and conflicts instead of
creating misleading duplicate history. A new distributed idempotency subsystem is
not introduced. This behavior is documented for API and CLI consumers.

## Safe bulk review

Bulk policy is server-side; the browser is never the authority. Bulk review uses a
two-step preview/commit protocol.

### Ordinary bulk-accept eligibility

A finding is eligible only when all conditions hold:

```text
LOW risk
AUTO intervention
Pending on the current revision
current assessment/finding revisions
recommendation in the mechanical allowlist
no sensitive or unresolved exclusion evidence
```

The initial conservative allowlist is:

```text
PRESERVE
CONVERT
REPLACE_WITH_APEX_NATIVE
```

This allowlist does not mean every finding with those recommendations is eligible;
all other policy conditions still apply.

Ordinary bulk acceptance always excludes CRITICAL, HIGH, MEDIUM, MANUAL, stale and
unknown-risk findings; DROP, REFACTOR, MOVE_TO_PLSQL_API, MANUAL_REVIEW and UNKNOWN
recommendations; and any finding with evidenced security, identity,
approval/workflow, transaction, API-bypass, duplicated-logic, cross-module or
unresolved external-dependency signals. Exclusions return stable, human-readable
reason codes and counts.

### Preview and commit

Preview receives the exact selected finding IDs and finding revisions plus current
analysis/source/review revisions. It returns selected, eligible and excluded
counts; each excluded item and reason; and a deterministic preview token bound to:

```text
project identity
analysis/source/review revisions
sorted finding IDs and finding revisions
bulk policy version
eligible and excluded outcome
```

Commit sends the same exact set and token. Under one write transaction the server
reauthorizes, rechecks revisions, recomputes eligibility and verifies the token.
Any mismatch produces `409 Conflict` and zero decisions. A valid commit inserts
all eligible decisions atomically; excluded rows remain untouched. Bulk defer and
bulk Needs Review use the same exact-set/all-or-nothing revision safety, without
pretending those actions resolve findings.

There is no generic `Accept all AUTO` operation.

## HTTP API

Extend `/api/v2/projects` only with the Phase D surface:

```text
GET  /api/v2/projects/:id/review
GET  /api/v2/projects/:id/review/:finding_id
POST /api/v2/projects/:id/review/:finding_id
POST /api/v2/projects/:id/review/bulk-preview
POST /api/v2/projects/:id/review/bulk
```

The single-finding POST carries an explicit operation such as `DECIDE` or
`ANNOTATE`; alternatively an implementation may use a narrowly named annotation
subroute if that improves existing dispatch conventions without expanding scope.
No endpoint accepts a trusted reviewer identity from the client.

Every response carries `analysis_revision`, `source_revision` and
`review_revision`. Mutation conflicts return repository-consistent HTTP 409 with a
safe code and the instruction to reload current evidence. Finding IDs are always
resolved inside the authorized project; a Project A ID can never read or mutate
Project B even if the text or opaque ID collides.

Every request reauthorizes current session, MFA scope, membership, organization,
project grant and action. Add or reuse an explicit review-mutation permission so a
read-only project grant cannot mutate. Existing Origin, CSRF and Host protections
remain mandatory.

## CLI

Add the smallest useful surface under the existing project CLI:

```text
formslang project review list
formslang project review show
formslang project review decide
formslang project review annotate
```

CLI methods call the same `ProjectService` / `ProjectReviewService` operations as
HTTP and UI. Machine-readable output preserves engine recommendation, human
decision, review state, exact revisions, rationale and annotations. A separate CLI
persistence path is prohibited. Bulk CLI commands are deferred unless implementation
shows a clear need without duplicating the preview/commit contract.

## Workbench experience

Phase C's `Start Priority Review` opens a real project-scoped Modernization Review
workspace, not the read-only inventory bridge. It uses the existing shell, request
guards, visual tokens, accessibility utilities and adjustable layout.

Desktop uses a split pane:

```text
Review queue and filters | Evidence, history and decision actions
```

Tablet/smaller layouts stack those panes. Queue search, filters, sort, page,
selection, scroll and focused finding survive detail changes and return navigation.
The user can use Previous and Next Priority without closing a modal or reloading
the whole application. Advancing after a decision is optional, never forced.

The detail pane displays:

```text
identity and context
risk and intervention
engine recommendation
human-readable reason
Forms evidence
database evidence
target suggestion
bounded history and annotations
Accept / Change / Needs Review / Defer
```

Significant actions use semantic forms with inline validation. A CRITICAL change
uses a focused dialog that names the control risk, requires the evidence-review
checkbox and rationale, traps/restores focus and does not use generic `Are you
sure?` copy.

After a mutation the client refreshes the affected queue row, detail, revision and
Overview progress from server projections without reanalysis. A 409 announces that
the evidence changed, discards no user data silently and reloads current evidence.
Stale-response guards prevent Project A responses or writes from populating Project
B.

Risk and state are always conveyed through text/icons as well as color. Queue,
selection, forms, dialogs and Previous/Next controls are keyboard operable;
headings/table/list semantics, error associations, live status and reduced motion
remain supported. Charts are not required for Phase D.

All project/module/source labels, rationale, notes and annotations are rendered as
text through existing escaping helpers. Markdown or HTML execution is not added.

## Cache and projection invalidation

A meaningful review or annotation event increments `review_revision`. The Phase C
cache key already includes that revision, so current Overview and inventory/review
counts naturally miss the old entry. Deterministic analysis is not invalidated and
does not rerun.

Queue/detail reads carry their revision fence. A client must not merge pages or
details from different review/analysis revisions; it resets/reloads instead.

## Concurrency behavior

The required outcomes are:

- simultaneous reviewers: one transaction wins; the stale writer receives 409;
- review versus reanalysis/source refresh: whichever commits first is preserved;
  a later assessment change makes the old review non-applicable rather than copying
  it forward;
- bulk preview versus any mutation: token/revision mismatch prevents all writes;
- reopen during a mutation: readers see the last committed state, never a partial
  event;
- network replay: old review revision conflicts and does not duplicate history.

No automatic retry hides these races.

## Performance gate

Use a synthetic persisted assessment with approximately 5,000 findings, thousands
of decision/annotation history rows and thousands of dependencies. Record at least:

```text
queue first page
priority filter
detail
bounded history
single mutation
bulk preview
bulk commit
```

These are local synthetic projection measurements, not customer or engine
performance claims. First implement the deterministic read model over existing
data. Only a measured regression or unacceptable latency may justify narrowly
scoped indexes. Persistent projection tables remain out of scope and require a
separate proposal.

## Verification strategy

Implementation follows test-driven RED-GREEN steps and includes:

### Service and persistence

- accept preserves engine recommendation, stores human decision and increments
  review revision;
- change requires and persists rationale;
- CRITICAL change rejects missing confirmation, rationale or current revision;
- Needs Review and Deferred remain unresolved;
- changed source/analysis marks old decisions Needs Revalidation and retains
  history;
- annotations remain independent from engine evidence and decision state;
- decision/history/revision mutation is atomic;
- decisions and history survive close/reopen without analysis.

### Bulk and concurrency

- eligible LOW/AUTO/mechanical findings can be accepted;
- critical/manual/sensitive/stale/unsafe findings are excluded with exact reasons;
- state changes after preview make commit fail atomically;
- simultaneous reviewers cannot overwrite one another;
- review versus reanalysis/source refresh preserves committed history and correct
  applicability;
- project/finding ID collisions cannot cross project boundaries.

### API, authorization and security

- local authorized reads/mutations;
- authenticated owner/member behavior according to grants;
- foreign project, revoked membership, wrong organization and read-only mutation
  denial;
- list/detail pagination, filters, search and revision mismatch;
- no source leakage in queue and bounded authorized evidence in detail;
- XSS payloads in project/module/source labels, rationale and annotations render as
  inert text;
- current Origin/CSRF/Host policy remains enforced.

### Interface parity and browser acceptance

- CLI and API/UI reconcile against the same decision state and revisions;
- real browser flow: Overview, Start Priority Review, critical evidence, Accept,
  next item, Change with rationale, Defer, Needs Revalidation filter, history, back
  to updated Overview;
- real bulk browser flow previews eligible/excluded, commits safe rows and records
  history while dangerous rows remain excluded;
- stale browser submission produces conflict and reloads evidence;
- keyboard navigation, focus restoration/trap, semantic forms, non-color status and
  reduced-motion behavior are verified;
- Phase C and legacy browser suites remain green.

### Final gates

Run and record exact results for:

```text
full pytest
focused Phase D tests
JS/DOM tests
Phase D browser acceptance
Phase C browser regression
legacy Workbench browser regression
Ruff
git diff --check
benchmark/ground-truth hash verification
synthetic 5,000-finding performance measurements
```

An independent high-reasoning review with fresh context evaluates authorization
bypass, stale overwrite, critical override bypass, bulk-policy bypass,
cross-project mutation, revision races, XSS, source leakage and count
reconciliation. Findings are classified Critical/Important/Minor with a Merge/Hold
recommendation. Material issues are fixed RED-GREEN and all affected gates rerun.

## Documentation deliverables

Implementation updates only truthful current-state documentation:

```text
docs/architecture-2.md
docs/project-workflows.md
docs/quality-acceptance.md
docs/modernization-review.md   (new)
```

`docs/modernization-review.md` documents state mapping, resolved/unresolved
semantics, revision binding, override and CRITICAL confirmation policy, bulk
eligibility/exclusions, annotations, history, privacy and conflict behavior.
Stable README marketing is not changed to claim FormsLang 2.0 is released.

## Explicit non-goals and deferred scope

Phase D does not implement:

- project-level APEXlang generation or generation gates (Phase E);
- deployment, import or database execution;
- executive/technical reports or modernization packages (Phase F);
- Jira/Azure DevOps integrations;
- a central collaboration/comment server, team assignment system or social feed;
- AI approval, AI decision mutation or an AI requirement;
- semantic search or a new analysis/classification engine;
- persistent review projection tables without scale evidence;
- a 2.0 version bump, tag, release or automatic merge.

`blocks_generation` may be exposed only as a truthful policy hint for obvious
unresolved critical/manual/stale states. It is not a Phase E eligibility engine and
cannot authorize output.

## Known design limitations

- Review applicability is intentionally conservative: changed evidence makes the
  prior human decision stale even when a human might later judge it equivalent.
- Bulk eligibility starts with a narrow allowlist; broader mechanical policies
  require evidence and separate review.
- Local reviewer identity is the existing OS/local identity, not enterprise-grade
  non-repudiation.
- The revision fence provides safe replay behavior but not a general distributed
  idempotency-key system.
- Static evidence can remain incomplete when database/library source is absent;
  the UI must show that limitation and permit Needs Review.
- Phase D records governance decisions but does not prove functional equivalence,
  complete migration or generation safety.

## Definition of done

Phase D is complete only when the real application stack provides a project review
queue; priority/search/filter/pagination; evidence detail; Accept, Change, Needs
Review and Defer; protected CRITICAL changes; stale decisions and history; human
annotations; factual progress; safe bulk preview/commit; API/UI/CLI parity; current
authorization and project isolation; revision/concurrency/XSS/source-leakage
protections; real browser acceptance; scale measurements; full green verification;
unchanged frozen benchmarks; and no Phase E/F, version, tag or release change.

The product outcome is an auditable workflow in which an Oracle architect can work
through hundreds or thousands of findings efficiently, understand why each engine
recommendation exists, safely override it when justified, and preserve deterministic
evidence alongside human governance history.
