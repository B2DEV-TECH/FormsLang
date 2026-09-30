# FormsLang 3.0 — Journey shell design (WP-39a + WP-41 slice 1)

Status: **Draft for owner review (2026-09-30).** This is a design only. Nothing
described here is implemented. It refines
[master-specification.md §16–17](master-specification.md#16-workbench-information-architecture-and-visual-system)
and changes no requirement or release gate. The re-sequencing it depends on is
recorded in [implementation-plan.md](implementation-plan.md#owner-approved-re-sequencing-2026-09-30).

## Why this comes now

After installing 3.0.0-beta.1, the owner reported that FormsLang is too
complex to use. Three causes were named:

1. **Too many menus.** The Workbench has two navigation layers with about 19
   entries, and some are duplicated.
2. **No clear next step.** Nothing says what to do after creating a project,
   adding sources or analyzing them.
3. **Two products mixed.** The 1.x module-conversion flow and the 2.x project
   flow coexist as separate models.

The specification already requires a replacement: UX-01 to UX-07, all
*Specified*, owned by WP-41 in M5. The plan placed M5 after M2–M4. This design
brings forward a UX-only slice of M5. The rest of M5 keeps its dependencies.

## Owner decisions (2026-09-30)

| # | Decision |
|---|---|
| D1 | **Everything is a project.** There is one domain model. The 1.x single-module flow survives only as a labeled legacy tool until it is retired. |
| D2 | **The primary navigation is the journey rail.** It covers the Understand → Decide → Build → Validate steps, labelled **Explore · Decisions · Build · Validate** as §16.2 requires. Reports and History are separate project-wide entries. |
| D3 | **The rail is a state map, not a wizard.** Every step is always clickable. It shows real state and the shortcut that unblocks it. Order is enforced only by domain dependencies, never by navigation. |
| D4 | **Two scopes, one component (B3).** A project rail with counts, a four-dot position per Form, and the same rail scoped to a Form when one is open. |
| D5 | **Approach 1.** A narrow typed read-only service (WP-39a), then the first shell slice (WP-41 slice 1) that hosts the existing views. ADR-08 keeps the current frontend stack. |

## Baseline at `21dcf48`

These are facts, not proposals:

- **Global navigation** (`formslang/ui/shell.py`): Modernization Projects,
  Review, Project, Blueprint, Documentation, Visual preview, Structural diff,
  Exports and Settings. It also has a *Current module* switcher and a
  *Conversion provider* block.
- **Project navigation** (`projectSectionNav` in
  `formslang/ui/modernization_project.py`): Overview, Explore a Form, System
  Map, Hotspots, Inventory, Review, Dependencies, Generate, Reports and Project
  Settings.
- **Routing.** The Workbench has no URL routing (no hash or `pushState`), so no
  legacy deep link needs a redirect.
- **Source roots are folders.** `ProjectIntake.select_source` rejects anything
  that is not a directory.
- **Freshness is project-level only.** `check_freshness` in
  `formslang/project_freshness.py` returns `CURRENT`, `STALE`, `INCOMPLETE`,
  `MISSING_SOURCE` or `UNVERIFIED`. No per-Form freshness exists.
- **Finding review.** Reviews are append-only rows in `blueprint_review`. The
  `review_state` is `PENDING`, `APPROVE`, `MODIFY`, `REJECT`, `DEFER` or
  `STALE`, and `RESOLVED_REVIEWS = {APPROVE, MODIFY}`.
- **Generation blockers.** They form a flat list of `{code, id, message}`
  records with **24 codes**, defined in `project_generation_policy.py` and
  `project_generation.py`. A module is eligible when it has no blockers.
- **Artifacts** are immutable `project_artifact` rows. Each one binds
  `analysis_revision`, `source_revision`, `review_revision`, `target_revision`
  and `code_revision`. Artifact currency is checked in `project_reports.py`
  (`ARTIFACT_REVISION_STALE`, `ARTIFACT_CODE_STALE` and related codes).
- **Validation** rows are append-only. Their statuses are `Validated`,
  `Validation Failed`, `Not Validated`, `Package Verified` and
  `Package Invalid`.
- **No per-Form journey aggregate exists.** The WP-12 journey joins four
  existing endpoints in the browser.

## 1. Shell and navigation (WP-41 slice 1)

```text
┌────────────────────────────────────────────────────────────────────────────┐
│ FormsLang  Dispatch desk ▾  [Current]  [Search project…]  Reports History Advanced ▾ │
├────────────────────────────────────────────────────────────────────────────┤
│ ✓ Explore         →  ▶ Decisions       →  Build                →  Validate  │
│   3 Forms · 1 pkg      2 findings open      1 ready · 1 blocked     nothing built │
├────────────────────────────────────────────────────────────────────────────┤
│ Forms   [All 3] [Decisions 1] [Build 1] [Blocked 1]                         │
│ CUSTOMERS  ● ◉ ○ ○   2 findings to decide              Open →              │
│ NOTICE     ● ● ◉ ○   Ready to build                     Open →              │
│ SHIPMENTS  ● ✕ ○ ○   Blocked: module not prepared       Why? →              │
└────────────────────────────────────────────────────────────────────────────┘
```

**Regions**

- **Top bar.** It holds:
  - the project menu (switch project, sources, project settings);
  - the freshness badge;
  - project search, which is the existing 2.1 search, not the WP-11 structured
    search;
  - Reports, History and Advanced ▾.
- **Journey rail.** Four steps, each showing its state and a short count. The
  labels are Explore, Decisions, Build and Validate. The step identifiers,
  which this document uses for the rules, are `UNDERSTAND`, `DECIDE`, `BUILD`
  and `VALIDATE`.
- **Workspace.** The content of the selected step. In slice 1 it is an existing
  view.

**Three states**

1. **New project, no sources.** Explore (Understand) is highlighted with "No
   sources yet". The workspace shows one action, *Add sources*, which is the existing
   folder intake. The other steps stay clickable and say what they need, for
   example "Needs analysis".
2. **Analyzed project, project scope.**
   - The rail shows counts across Forms.
   - The highlighted step is the first step, in order, where any Form is
     `ACTION`, `BLOCKED` or `STALE`.
   - Clicking a step filters the Form list to the Forms in that step.
   - Each Form shows four dots: done, current, blocked or not reached.
3. **Form open, Form scope.** A breadcrumb `Project › FORM` appears, and the
   same rail is computed for the Form. The workspace shows that step's existing
   view, filtered to the Form.

**Removed from the primary navigation:** the 9-entry sidebar, the *Current
module* switcher and the 10 project tabs. Every task they support stays
reachable, as §3 shows.

## 2. Journey status service (WP-39a)

### Principles

- The service is read-only. It adds no table, no persistence authority and no
  domain rule.
- It composes facts the product already computes and assigns each one to a
  step. That classification lives in the service. The UI and the CLI render it
  and never recompute it.
- Each response uses **one** freshness value, and every step derives from it,
  so Understand and Build cannot contradict each other. The value is returned
  with its `checked_at`. The caller supplies it, following the existing
  conventions:
  - HTTP passes the last saved source check (`ProjectHTTP._freshness`), like
    every other projection route. It does not re-hash sources on each page
    load. With no saved check, the value is `UNVERIFIED` /
    `SOURCE_CHECK_REQUIRED`.
  - The CLI runs and saves a new check (`service.freshness()`), as
    `project summary` does.
- Generation detail is read with its module session opened **read-only**. A
  journey request writes nothing.

### Step states

Each step has one of five states: `DONE`, `ACTION` (work is available in this
step), `WAITING` (it depends on an earlier step), `BLOCKED` (it cannot proceed
here) and `STALE` (it was done, but a revision changed). Reason codes carry the
specifics, and every reason names the step whose action resolves it.

**Understand (Form).** The state follows project freshness, because no
per-Form freshness exists.

| Freshness | State | Reason | Action |
|---|---|---|---|
| (project has no source roots) | `ACTION` | `NO_SOURCES` | Add sources |
| `CURRENT` | `DONE`, or `ACTION` if the Form has an Understand-class blocker | — / blocker code | — / add sources |
| `INCOMPLETE` | `ACTION` | `NOT_ANALYZED` / `ASSESSMENT_INCOMPLETE` | Analyze |
| `UNVERIFIED` | `ACTION` | the recorded reason | Check sources |
| `STALE` | `STALE` | `SOURCE_CHANGED` / `ENGINE_CHANGED` | Re-analyze |
| `MISSING_SOURCE` | `BLOCKED` | `SOURCE_MISSING` | Restore or relink sources |

**Decide (Form).**

- `WAITING` (reason `NEEDS_CURRENT_ANALYSIS`) when the project has no sources
  or its freshness is not `CURRENT`. Reviews can be recorded only on current
  evidence. A Form's own Understand-class blockers, such as an unresolved
  dependency, do **not** make Decide wait, because its findings can still be
  reviewed.
- Otherwise `ACTION` when there are unresolved findings or any Decide-class
  blocker is present.
- Otherwise `DONE`.

A finding is unresolved when its `review_state` is not in `RESOLVED_REVIEWS`.
The count uses **the same finding scope the generation policy uses for
`UNRESOLVED_REVIEW`**, so Decide and Build never disagree about the same Form.
Plan confirmation and code approval are decisions (§16.8: *Review / Conversion
Review → Decisions*), so they belong to Decide.

**Build (Form).** The first matching rule wins:

1. `BLOCKED` with reason `NO_GENERATION_SCOPE`, resolved in Understand, when
   the Form has no generation scope. A generation scope is a selected XML
   manifest entry whose module matches the Form entity, which is the only
   case where a `source_id` exists. Validate is then `WAITING`.
2. `BLOCKED` with reason `GENERATION_DETAIL_UNAVAILABLE` and the error message
   when reading the generation detail fails. This happens, for example, when
   a prepared session is missing or its source was edited. `ProjectBusy` is
   never absorbed; it propagates as a conflict.
3. `BLOCKED` if any product-limit blocker is present. All reasons are listed,
   including any Decide-class ones.
4. `WAITING` if any Understand-class or Decide-class blocker is present.
5. `ACTION` with `UNCLASSIFIED` reasons if only unknown blocker codes remain.
6. `DONE` if the Form's latest selected-module artifact is current.
7. `STALE` if that artifact exists but is not current.
8. Otherwise `ACTION` (`READY_TO_GENERATE`).

An artifact is **current** when the delivery-report currency rule finds no
reason (`ARTIFACT_REVISION_STALE`, `ARTIFACT_CODE_UNAVAILABLE` or
`ARTIFACT_CODE_STALE`) **and** the archive passes the generation service's own
integrity check (`ARTIFACT_INTEGRITY` otherwise). The currency rule moves out of
`ProjectReportService._artifacts` into one `ProjectGenerationService` method,
and reports and the journey share it. The report's behavior does not change.
If that rule marks an artifact stale after a review on an unrelated Form (the
binding carries the project-wide `review_revision`), the journey shows it as
the rule says. WP-39a records that as a finding and does not change the rule.

**Validate (Form).**

- `WAITING` when Build is not `DONE`.
- `DONE` when the latest validation of the current artifact is `Validated`.
- Otherwise `ACTION`, with one of these reasons:
  - `NOT_RUN` when there is no validation;
  - `NOT_VALIDATED` when the status is `Not Validated`, which includes a
    missing SQLcl, and the recorded message is shown;
  - `VALIDATION_FAILED`, whose action leads back to Decide and the evidence
    (UX-02).

The package statuses `Package Verified` and `Package Invalid` belong to
project-level package artifacts. They appear in the project Validate list, not
in a Form journey.

### Generation blocker classification (all 24 codes)

| Class | Resolved in | Codes |
|---|---|---|
| Understand | Understand | `SOURCE_NOT_CURRENT`, `MODULE_NOT_OBSERVED`, `UNRESOLVED_DEPENDENCY` |
| Decide | Decide | `UNRESOLVED_REVIEW`, `UNSUPPORTED_TARGET_DECISION`, `UNRESOLVED_ARCHITECTURE`, `PREREQUISITE_NOT_CONFIRMED`, `UNSUPPORTED_TARGET`, `TARGET_STRATEGY_UNSELECTED`, `TARGET_NOT_GENERATING`, `TARGET_KEYS_CHANGED`, `ROW_KEY_NOT_CONFIRMED`, `MODULE_NOT_PREPARED`, `CODE_NOT_APPROVED`, `CODE_NEEDS_REVALIDATION`, `UNSUPPORTED_TARGET_CODE` |
| Product limit | not by deciding; shown as "outside supported scope" | `UNSUPPORTED_TABLE_IDENTITY`, `UNSUPPORTED_COLUMN_IDENTITY`, `UNSUPPORTED_LAYOUT`, `UNSUPPORTED_EXECUTION_MAPPING`, `UNSUPPORTED_ITEM_CONTROL`, `UNSUPPORTED_DATA_CONTROL`, `UNSUPPORTED_DATABASE_MAPPING`, `TARGET_NAME_COLLISION` |

Three `UNSUPPORTED_*` codes are Decide-class, because a decision resolves them:

- `UNSUPPORTED_TARGET_DECISION` is emitted for every finding that has no
  reviewed, supported recommendation yet;
- `UNSUPPORTED_TARGET` asks for a supported target profile;
- `UNSUPPORTED_TARGET_CODE` means the reviewed code still carries Forms runtime
  behavior, which the reviewer can rewrite.

If they were classified as product limits, every newly analyzed Form would
show Build as blocked instead of waiting for decisions.
`UNSUPPORTED_TABLE_IDENTITY` stays a limit even when the table is merely
missing from the sources, and its message says which case applies.

The service never guesses an unknown value. That covers blocker codes,
freshness values, review states and validation statuses. An unknown value
yields reason `UNCLASSIFIED` with the raw value, and the step becomes `ACTION`,
never `DONE`. An exhaustiveness test fails when a code literal in the
generation modules has no class.

### Project aggregation

- For each step, the service counts Forms per state.
- The focus step is the first step, in order, where any Form is `ACTION`,
  `BLOCKED` or `STALE`. When every Form is `DONE`, there is no focus.
- The journey counts Forms only, because only Forms have a generation scope.
  The Explore step shows package and library counts from the existing
  overview inventory, which already groups package specs and bodies. The
  journey does not recount them.
- At project scope, Understand also takes its state straight from project
  freshness and source roots. A project with no sources, or no analyzed Form,
  still has a state and a next action.

### Contract

- HTTP: `GET /api/v2/projects/{pid}/journey` and
  `GET /api/v2/projects/{pid}/journey?form=<form entity id>`.
- CLI: `formslang project journey <project> [--form <id or name>] [--json]`.
  Like every project command, it takes the project directory or descriptor.
- `form` matches an entity id first, then a case-insensitive name. An unknown
  Form gives 404 (HTTP) or exit 2 (CLI). An ambiguous name is rejected.
- Code: a new module, `formslang/project_journey_status.py`.
  `tests/test_project_journey.py` already holds the WP-12 journey tests, so the
  name stays distinct.
- If the project's analysis or review revision changes while the journey is
  read, the request fails with `RevisionConflict` (409), as delivery reports
  do.

```json
{
  "schema": "formslang-journey/1",
  "project_id": "…",
  "binding": {"project_id": "…", "analysis_revision": "…", "source_revision": "…", "review_revision": 12},
  "freshness": {"status": "CURRENT", "reasons": [], "checked_at": "…"},
  "focus": "DECIDE",
  "steps": [
    {"step": "UNDERSTAND", "counts": {"DONE": 3},
     "project": {"step": "UNDERSTAND", "state": "DONE", "reasons": []}},
    {"step": "DECIDE", "counts": {"ACTION": 1, "DONE": 2}}
  ],
  "forms": [
    {"entity_id": "form:…", "name": "CUSTOMERS", "module": "forms/customers.xml", "source_id": "…",
     "steps": [
       {"step": "DECIDE", "state": "ACTION",
        "reasons": [{"code": "UNRESOLVED_REVIEW", "resolved_in": "DECIDE", "count": 2}]}
     ]}
  ]
}
```

A reason's `resolved_in` is `null` for product limits and unclassified values.

`schema` is an internal payload label. It is not the ADR-13 CLI envelope, which
stays with WP-39b and WP-40.

### Performance

The fixture is the existing 500-Form one: 500 Forms, 5,000 findings and 5,000
dependencies. It is measured by extending
`examples/verify/project_overview_performance_check.py`, and the gate is
relative to the same run:

- The **cold project journey median must not exceed 1.5× the cold Overview
  median** measured in that run.
- This fixture has no generation scope, so the gate measures:
  - the composition;
  - the freshness rules;
  - the Decide scope walk over 500 Forms and 5,000 findings.

  The per-Form generation detail is not part of this gate. That limit is
  recorded with the numbers.
- If the gate fails, implementation stops and the owner decides. One possible
  remedy is to load the full Build facts only when a Form opens.
- The numbers go into the evidence register.

## 3. Transition (WP-41 slice 1)

| Entry | Project scope | Form scope |
|---|---|---|
| **Explore** (Understand) | Form list with dots; secondary *Views* menu: System Map, Hotspots, Inventory, Dependencies (existing views) | Explore a Form (WP-12) and Module 360 detail |
| **Decisions** (Decide) | Finding review queue | The Form's findings, target-plan confirmation, and code review and approval (the former *Conversion review*) |
| **Build** | Ready and blocked Forms | Existing module generation view |
| **Validate** | Artifacts and their status | The Form's artifacts and *Validate* |
| **Reports** | Existing Reports section and Exports | — |
| **History** | Existing review and job history, **labeled partial** (full history is WP-20) | The Form's review history |
| **Advanced ▾** | Project Settings, Settings, AI provider, and the 1.x module tools: *Open a single module* (legacy), Blueprint, Documentation, Visual preview, Structural diff | — |

**Rules**

1. Slice 1 does not rewrite the existing views. It hosts them in the shell, and
   each step's workspace is redesigned in later slices.
2. D1 applies with honest limits. *Add sources* stays folder-based, and
   single-file intake needs an intake change that is out of scope. The 1.x
   single-module flow stays in Advanced, labeled legacy.
3. Nothing disappears without a tested replacement (§16.8). An inventory test
   maps every former navigation entry to a new home.
4. The installed acceptance journeys are updated in the same slice: the beta
   A→B journey (30 checks) and the 2.2 visual journey (25 checks). Every check
   is kept or replaced by an equivalent one, and each replacement is recorded
   with its reason.
5. URL routing is out of scope. Context stays in memory as today, and UX-02
   progresses in later slices.

## 4. Plan amendment and ADR-08

- [implementation-plan.md](implementation-plan.md) changes the M5 table:
  - WP-39 splits into WP-39a (this service) and WP-39b (the original scope
    and dependencies).
  - WP-41 gains a slice 1 that depends on ADR-08, WP-39a and the WP-12
    findings.
  - A dated owner-approved re-sequencing note explains the order.
- [ADR-08](adr/ADR-08-frontend-stack.md) is **Proposed**. It keeps
  server-rendered HTML and JS in Python strings, with no build step and the
  current CSP. WP-41 slice 1 does not change the frontend until ADR-08 is
  **Accepted**.
- The execution order is ADR-08 acceptance → WP-39a → WP-41 slice 1. After
  that come the rest of WP-11, the WP-20 reconciliation of #38 → #41, M4, and
  then WP-39b, WP-40 and the later WP-41 slices.

## 5. Tests and exit evidence

**WP-39a.** Tests come first.

- One test per state rule.
- Exhaustiveness tests over the 24 blocker codes, freshness values, review
  states and validation statuses.
- CLI/HTTP equality on the same fixture.
- A consistency test: Decide's unresolved count equals the scope behind
  `UNRESOLVED_REVIEW`.
- The performance gate above.
- Full `pytest` and `ruff`.

**WP-41 slice 1.**

- Edge browser acceptance for the three states (new, analyzed, Form open), with
  every step clickable in both scopes.
- The navigation inventory test.
- The shell's controls work from the keyboard.
- No layout regression at 390, 720 and 1366 px. This is not a WCAG 2.2 AA
  claim.
- Updated installed journeys with the check accounting described in §3.
- Installer acceptance on the candidate before merge.

**Unchanged rules.** The plan's working rules apply. The Windows flake families
(#20, and the job-status HTTP 500 instrumented by #23) are handled by the
existing repeated-run policy.

## 6. Not claimed by this design

- The rail does not simulate Oracle Forms runtime or imply an executed
  navigation order (SCOPE-02, GRAPH-05).
- Decide does not offer `.flm`, decision preview or supersession (WP-30/31).
  History does not offer checkpoints (WP-20).
- There is no structured search, graph or evidence inspector (WP-11, WP-39b,
  later WP-41 slices).
- Slice 1 does not complete any UX-01..07 requirement. The evidence register
  will record partial progress only.
