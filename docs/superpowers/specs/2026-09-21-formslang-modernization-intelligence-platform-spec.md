# FormsLang 2.1 → 3.0

# Oracle Forms Modernization Intelligence Platform

## Authoritative Product, Architecture, UX and Delivery Specification

Repository:

`B2DEV-TECH/FormsLang`

Current stable baseline:

`FormsLang 2.0.0`

---

# 0. Executive Vision

FormsLang must evolve from:

> **Oracle Forms → Oracle APEX Modernization Workbench**

into:

> **Oracle Forms Modernization Intelligence Platform**

The strategic objective is simple:

> **Before a team rewrites a single Oracle Form, FormsLang should be the first tool they run.**

FormsLang should provide enough value during discovery, assessment and architectural review that the tool remains useful even when the eventual target is not Oracle APEX.

Long-term target possibilities include:

* Oracle APEX
* Java / Spring
* .NET
* React or another web frontend with APIs
* custom enterprise architecture
* partial preservation
* database-centric modernization
* retirement
* redesign
* mixed modernization strategies

APEX remains the first and most complete target implementation.

FormsLang must not weaken, remove or destabilize its APEX capability while becoming target-neutral.

The product is not becoming a generic transpiler.

The core mission is:

> **Understand the legacy system, expose modernization evidence, support architectural decisions, and only then enable target-specific implementation.**

---

# 1. Core Product Positioning

## 1.1 Primary category

Use this product category consistently:

**Oracle Forms Modernization Intelligence**

Supporting description:

> FormsLang analyzes Oracle Forms and database source together to reveal dependencies, business-rule ownership, architectural hotspots, modernization risk and reviewable modernization decisions before implementation begins.

---

# 1.2 Strategic product phrase

The product should eventually make this sentence natural:

> **“Before we modernize these Forms, let’s run FormsLang.”**

Secondary positioning:

> **Understand first. Modernize second.**

---

# 1.3 FormsLang must not depend on a target to be useful

A user should be able to create a project with:

```text
Oracle Forms source
+
Database source
```

and obtain significant modernization value without selecting APEX, Java, .NET or another target.

Target selection must become optional during assessment.

Target selection becomes necessary only when target-specific recommendations, planning, generation or validation are requested.

---

# 2. Product Doctrine

These are system laws.

They are not marketing language.

Any implementation conflicting with them requires explicit architectural review.

---

## 2.1 Understand before generating

The order is:

```text
Discover
→ Understand
→ Assess
→ Decide
→ Plan
→ Generate
→ Validate
→ Deliver
```

Generation is downstream.

It must never become the entry point of the modernization workflow.

---

## 2.2 Facts and recommendations are different things

The system must explicitly separate:

```text
OBSERVED FACTS
        ↓
STRUCTURAL INTERPRETATION
        ↓
MODERNIZATION INTENT
        ↓
TARGET-SPECIFIC RECOMMENDATION
        ↓
HUMAN DECISION
        ↓
IMPLEMENTATION / GENERATION ELIGIBILITY
```

Do not collapse these concepts into one recommendation object.

---

## 2.3 Engine recommendation is not human approval

Retain and strengthen the existing distinction between:

* deterministic engine recommendation
* architectural human decision
* target-plan approval
* code approval
* generation authorization
* artifact validation
* deployment
* runtime verification
* UAT acceptance

No earlier state implies a later one.

---

## 2.4 Evidence is mandatory

Important modernization decisions must be evidence-backed.

A finding without sufficient evidence must degrade toward:

```text
UNKNOWN
```

or:

```text
MANUAL REVIEW
```

rather than receive fabricated confidence.

---

## 2.5 No black-box modernization decisions

A user should be able to answer:

```text
What did FormsLang observe?
Where did it observe it?
What structural relationship was inferred?
What rule was applied?
What recommendation came from that rule?
What did the human decide?
What artifact was eventually generated?
```

---

## 2.6 Human review is architecture

Human-in-the-loop is not a disclaimer.

It is a product boundary.

The system must continue following:

> **Engine proposes. Evidence explains. Human decides.**

---

## 2.7 Unknown is a valid state

Do not convert insufficient evidence into:

* LOW risk
* AUTO
* Preserve
* Convert
* successful generation

Unknown must remain visible.

---

## 2.8 Local-first remains a product requirement

Static discovery and modernization assessment must continue to work without:

* cloud AI
* Oracle database credentials
* mandatory user account
* external telemetry
* provider API keys

Optional AI may assist explanation or drafting where already supported, but the deterministic modernization assessment remains independent.

---

# 3. Existing 2.0 Architecture Is the Baseline

Before modifying anything, inspect the actual repository and current documentation.

At minimum read:

```text
README.md

docs/architecture-2.md
docs/project-model.md
docs/project-workflows.md
docs/project-overview.md
docs/modernization-review.md
docs/project-generation.md
docs/project-reports.md
docs/forms-to-apex.md
docs/quality-acceptance.md
```

Inspect implementation behind:

```text
ProjectService
ProjectAssessment
ProjectReviewService
ProjectGenerationService
ProjectReportService
project_projection
project_store
project_model
project_analysis
Blueprint
existing Store
APEXlayout
APEXlang
Tauri desktop shell
current HTML/JS workbench
```

The implementation must respect the current architectural invariants unless this specification explicitly replaces one.

---

# 4. Architecture Laws to Preserve

The following 2.0 architectural decisions remain correct.

## 4.1 One engine

Do not create separate analysis pipelines for:

```text
UI
CLI
HTTP
APEX
Java
Reports
```

There must continue to be one source of modernization evidence.

---

## 4.2 One project model

Do not introduce a second project database for modernization intelligence.

Extend the existing project model through additive versioned schema changes.

---

## 4.3 One assessment source of truth

Persisted assessment state remains authoritative.

UI projections are derived read models.

Do not turn dashboards into independent persistence.

---

## 4.4 Same services for UI / CLI / API

The desktop UI, local browser, CLI and HTTP API must continue calling the same services.

No business rule may exist only in JavaScript.

---

## 4.5 Review history remains append-only

Human review must not rewrite deterministic evidence.

Past decisions must remain inspectable even when stale.

---

## 4.6 No frontend rewrite without evidence

Do not migrate to React, Vue, Angular or another frontend framework merely because the UX is changing.

The existing HTML/JS/Tauri architecture remains preferred unless an independently documented technical limitation proves otherwise.

The goal is:

> **information architecture modernization, not frontend-framework modernization.**

---

# 5. New Product Information Architecture

The current product flow is approximately:

```text
Overview
Inventory
Review
Dependencies
Generate
Reports
Settings
```

This structure will not scale to the new product vision.

Do not simply add more tabs.

The new project navigation should converge toward:

```text
PROJECT

Overview

Estate
  Inventory
  Dependencies
  Business Rules
  Ownership
  Hotspots

Architecture
  System Map
  Data Flow
  Coupling
  API Boundaries

Review

Plan

Deliver

------------------

Project Settings
```

Exact names may be adjusted after UX validation, but the conceptual grouping must remain.

---

# 6. Primary Product Journey

The product should communicate this mental model:

```text
UNDERSTAND
What do I have?

ASSESS
What matters?

DECIDE
What should happen?

PLAN
How should modernization proceed?

DELIVER
What is safe to move forward?
```

Target-specific generation sits inside the later stages.

APEX must no longer define the entire project lifecycle.

---

# 7. Phase 0 — UX and Product Foundation

This phase must happen before large feature expansion.

It is not a visual redesign.

It establishes the information architecture that future phases depend on.

---

## 7.1 Preserve visual identity

Keep:

* FormsLang/B2DEV dark design
* current product identity
* existing Tauri shell
* existing brand assets
* existing accessibility support
* current responsive/minimum-window behavior where valid

Improve consistency where necessary.

---

## 7.2 Establish design tokens

Formalize reusable tokens for:

```text
spacing
typography
surface hierarchy
borders
focus states
risk colors
freshness states
review states
execution states
target states
loading states
disabled states
empty states
warnings
success
errors
```

Do not scatter arbitrary colors/styles through new pages.

---

## 7.3 Component inventory

Audit existing reusable UI patterns.

Create or normalize components for:

```text
Navigation
Page Header
Metric Card
Status Badge
Risk Badge
Execution Badge
Freshness Badge
Filter Bar
Facet
Search Field
Table
Virtual/Paginated List
Details Drawer
Evidence Block
Code Excerpt
Decision Panel
History Timeline
Empty State
Loading State
Conflict State
Stale State
Error Banner
Modal / Confirmation
Graph Inspector
```

Do not introduce a component abstraction framework unless required.

---

## 7.4 Terminology cleanup

User-facing terminology must favor concepts over internal implementation terms.

Avoid exposing unnecessarily:

```text
finding_revision
analysis_revision
Blueprint protocol
projection
CAS
store identity
```

when the user only needs:

```text
Current
Stale
Needs reanalysis
Needs review
Changed source
Decision outdated
```

Technical diagnostics may expose deeper values in advanced/debug views.

---

# 8. New Onboarding Experience

The first-run experience should communicate product intent immediately.

Suggested entry:

```text
What do you want to do?
```

Option 1:

### Analyze my Forms estate

> Understand architecture and modernization risk before choosing a target.

Option 2:

### Modernize to Oracle APEX

> Analyze the estate and prepare an Oracle APEX modernization strategy.

Option 3:

### Explore Demo Project

> See how FormsLang analyzes a synthetic Forms application. No setup required.

These options are UX affordances only.

They must NOT create separate internal pipelines.

All routes must converge into the same ProjectService / project model.

---

# 9. Target Selection Must Become Optional

The current descriptor requires an APEX target.

This must be carefully evolved.

New project state should permit:

```text
target_strategy = UNSELECTED
```

This is a valid state.

It must support:

```text
Discover
Analyze
Overview
Estate
Architecture
Review
Reports
Plan
```

without a target.

Target-specific recommendation and generation are unavailable until a target exists.

---

# 10. Target Strategy Model

Introduce a formal target strategy concept.

Conceptually:

```text
TargetStrategy

id
type
name
version
representation
adapter_id
policy_id
configuration
status
created_at
revision
```

Initial supported strategies:

```text
UNSELECTED
ORACLE_APEX_26_1
GENERIC_MODERNIZATION
```

Future strategies:

```text
JAVA_SPRING
DOTNET
CUSTOM
```

Do not claim future adapters exist until implemented.

---

# 11. Estate Intelligence

FormsLang 2.1 should make the assessment itself valuable enough to justify adoption.

Create a first-class **Estate Intelligence** experience.

---

# 12. New Overview — Modernization Cockpit

The project Overview must be redesigned around fast understanding.

A user should understand the estate in approximately 10 seconds.

The page should answer:

```text
How large is this estate?
What was analyzed?
How fresh is it?
Where is the risk?
What deserves attention first?
What architectural patterns are appearing?
How much remains unresolved?
```

---

## 12.1 Estate metrics

Where evidence supports them, show:

```text
Forms modules
Triggers
Program units
Libraries
Packages
Procedures/functions
Views
Tables
Dependencies
Business-rule candidates
Findings
```

Never fabricate percentages when denominator semantics are unclear.

---

## 12.2 Modernization hotspots

Introduce first-class hotspot concepts such as:

```text
Direct DML hotspots
API bypass candidates
Duplicated rule clusters
Global-state hotspots
Navigation coupling
Dependency cycles
High fan-in components
High fan-out components
Cross-layer ownership conflicts
Unresolved business-rule ownership
Critical review items
```

Each hotspot type requires:

```text
definition
deterministic detection contract
evidence
severity policy
false-positive boundary
tests
```

No hotspot may exist only because it looks useful in the dashboard.

---

## 12.3 Start Here

Overview should include a ranked list:

```text
START HERE

1. ORDERS
   Critical
   Direct DML appears to bypass guarded API

2. APPROVALS
   Critical
   Conflicting business-rule ownership

3. INVENTORY
   High
   Validation duplicated across multiple modules
```

Ranking must be deterministic and explainable.

Do not invent AI priority.

Priority factors should be inspectable.

---

# 13. Estate Workspace

Create a grouped Estate workspace.

---

## 13.1 Inventory

Retain existing server-side:

```text
search
filter
sort
pagination
revision fencing
```

Extend inventory categories only where supported by normalized assessment facts.

---

## 13.2 Dependencies

Dependencies should become easier to navigate.

Support:

```text
incoming dependencies
outgoing dependencies
cross-layer edges
dependency type
risk context
source module
target component
```

---

## 13.3 Business Rules

Create a first-class business-rule candidate view.

A candidate should represent:

```text
rule cluster identity
observed implementations
structural similarity
source locations
owning layers
conflicts
possible owner
risk
review state
```

Do not imply semantic identity when structural similarity is insufficient.

Use cautious terminology such as:

```text
candidate
overlap
possible duplicate
possible owner
```

where required.

---

# 14. Architecture Workspace

This area should become one of the strongest differentiators of FormsLang.

---

## 14.1 System Map

Provide an interactive architecture graph.

Example:

```text
ORDERS.fmb
   |
   +-- calls ------> ORDER_API
   |                   |
   |                   +-- writes ---> ORDERS
   |
   +-- reads ------> INVENTORY
   |
   +-- CALL_FORM --> ORDER_LINES.fmb
```

---

## 14.2 Graph scalability

Never render an entire enterprise graph by default.

Support:

```text
progressive expansion
depth limits
edge-type filtering
risk filtering
layer filtering
search
focus mode
neighborhood mode
```

Default view should show a bounded meaningful neighborhood.

---

## 14.3 Node detail

Selecting a node should expose:

```text
Name
Type
Layer
Incoming dependency count
Outgoing dependency count
Used by
Reads
Writes
Calls
Business-rule candidates
Findings
Risk distribution
Related review decisions
```

---

## 14.4 Edge detail

An edge is first-class evidence.

Selecting an edge should expose:

```text
CALLS
READS
WRITES
NAVIGATES_TO
IMPLEMENTS
DUPLICATES
OVERLAPS
GUARDS
BYPASSES
```

Only create edge types whose semantics are explicitly defined.

---

# 15. Modernization Intelligence Model

This is the most important backend evolution.

Create a versioned target-neutral representation.

Working name:

```text
Modernization Model
```

Internal name may be:

```text
Modernization IR
```

Avoid branding the implementation name prematurely in user-facing UI.

---

# 16. Layered Model

The model should contain separate layers.

---

## 16.1 Observed facts

Examples:

```text
Module A contains Trigger B
Trigger B writes TABLE_X
Package P writes TABLE_X
Module A calls Package P
Constraint C guards TABLE_X
Trigger B uses GLOBAL variable G
Module A navigates to Module C
```

Observed facts should be reproducible directly from analyzed source.

---

## 16.2 Structural signals

Examples:

```text
DIRECT_DML
API_DELEGATION
API_BYPASS_CANDIDATE
DUPLICATED_PREDICATE
GLOBAL_STATE
CROSS_MODULE_NAVIGATION
DEPENDENCY_CYCLE
NATIVE_TARGET_PATTERN
CONCURRENCY_GUARD
GUARD_LOSS
```

Signals are interpretations of facts.

They must retain the evidence used to derive them.

---

## 16.3 Modernization intent

Introduce target-neutral intents.

Candidate taxonomy:

```text
PRESERVE_EXISTING_OWNER
CENTRALIZE_EXISTING_OWNER
REPLACE_MECHANICAL_BEHAVIOR
REDESIGN_BEHAVIOR
REMOVE_OBSOLETE_BEHAVIOR
INTRODUCE_SERVICE_BOUNDARY
REVIEW_BUSINESS_INTENT
RESOLVE_OWNERSHIP
REVIEW_SECURITY
REVIEW_CONCURRENCY
UNKNOWN
```

Do not finalize names blindly.

Before implementation, map all existing FormsLang recommendations to proposed intents and prove the model can express current behavior without information loss.

---

# 17. Existing Recommendation Compatibility

Current recommendations include concepts such as:

```text
PRESERVE
CONVERT
REFACTOR
MOVE_TO_PLSQL_API
REPLACE_WITH_APEX_NATIVE
MANUAL_REVIEW
DROP
```

Do not delete or silently reinterpret them.

Create an explicit migration/mapping layer.

Example concept:

```text
Observed Intent:
CENTRALIZE_EXISTING_OWNER

APEX recommendation:
MOVE_TO_PLSQL_API

Generic recommendation:
PRESERVE_EXISTING_SERVICE_BOUNDARY
```

Historical reviews must remain interpretable.

---

# 18. Facts vs Inferences vs Decisions in UX

Every detail view should visually distinguish:

## Observed

```text
Trigger writes ORDERS directly
ORDER_API writes ORDERS
12 modules call ORDER_API
Current trigger does not call ORDER_API
```

## Inferred

```text
Possible API bypass
```

## Recommendation

```text
Centralize through existing owner
```

## Human Decision

```text
Accepted
Reviewer: ...
Date: ...
Rationale: ...
```

This separation must also exist in APIs and serialized models.

---

# 19. Review UX Upgrade

Do not rewrite the review engine.

Upgrade the user experience around it.

The primary question should be:

> **What did FormsLang find, why does it matter, and what decision do I need to make?**

---

## 19.1 Review layout

Preferred structure:

```text
Priority queue
|
+-- filters
+-- hotspots
+-- risk
+-- status

Selected finding

Recommendation
Risk
Execution level

Why

Observed facts

Evidence

Impact

Related architecture

Human decision

History
```

---

## 19.2 Review decision actions

Keep explicit concepts:

```text
Accept
Change
Needs Review
Defer
```

Do not simplify them into a generic “Resolved”.

---

## 19.3 Staleness

When evidence becomes stale:

* retain old decision
* visibly mark it non-applicable
* explain why
* require revalidation/review
* never silently reuse it

---

# 20. Modernization Plan

Introduce a new first-class Plan workspace.

Assessment answers:

> What exists?

Review answers:

> What should happen?

Plan answers:

> In what sequence should we modernize?

---

## 20.1 Modernization waves

Allow deterministic proposed waves such as:

```text
Wave 1
Low coupling
Resolved decisions
No critical blockers

Wave 2
Moderate dependencies
Some assisted work

Wave 3
High architectural coupling
Requires architecture review

Hold
Unresolved critical behavior
```

These are not schedule estimates.

Do not invent:

```text
days
hours
cost
ROI
completion dates
team size
```

unless the user explicitly supplies calibrated organizational data in a future feature.

---

## 20.2 Wave rationale

Each module's proposed wave should explain:

```text
coupling
risk
unresolved decisions
dependency order
target readiness
architecture blockers
```

---

## 20.3 Dependency-aware ordering

Investigate whether topological or partial dependency ordering adds value.

Cycles must remain explicit.

Do not fabricate a sequence if a cycle prevents deterministic ordering.

---

# 21. Architecture Policy

FormsLang should separate:

```text
Facts
+
FormsLang default policy
+
Organization policy
+
Project overrides
+
Human decision
```

---

## 21.1 Policy hierarchy

Conceptually:

```text
FormsLang Default
      ↓
Organization Policy
      ↓
Project Policy
```

More specific policy overrides less specific policy only where explicitly supported.

---

## 21.2 Example

```yaml
policy_version: 1

direct_dml:
  when_existing_owner: prefer_existing_owner
  no_owner: manual_review

global_state:
  recommendation: redesign_state_management
  execution: assisted

database_api:
  preserve_by_default: true
```

The exact schema must be designed and validated before implementation.

---

## 21.3 Policy must not rewrite facts

Policy may influence:

```text
recommendation
target interpretation
execution threshold
required approval
```

Policy must not alter:

```text
what source was observed
what dependency exists
what evidence exists
```

---

# 22. Policy UX

Do not hide policy exclusively in YAML.

Provide a readable UI.

Example:

```text
Architecture Policy

Direct DML
Prefer existing API when ownership is observed

Global State
Requires redesign before generation

Existing PL/SQL API
Preserve by default
```

Show policy provenance on recommendations.

Example:

```text
Recommendation source

Structural evidence
+
Organization policy
=
Centralize through existing owner
```

---

# 23. Target Adapter Architecture

Target-specific logic must be moved behind a stable adapter boundary.

Do not implement Java/.NET generation directly in the modernization core.

---

# 24. Target Adapter Responsibilities

A target adapter may provide:

```text
target metadata
supported modernization intents
target-specific recommendation mapping
target-native equivalents
generation eligibility rules
artifact generation
validation capability
target-specific blockers
```

---

## 24.1 Core must not call target internals directly

Target-specific behavior must go through a defined interface.

Conceptual interface:

```python
class TargetAdapter:

    id
    name
    version

    def capabilities(...):
        ...

    def interpret_intent(...):
        ...

    def target_recommendation(...):
        ...

    def eligibility(...):
        ...

    def generate(...):
        ...

    def validate(...):
        ...
```

This is conceptual only.

Design the real interface based on current code before implementation.

---

# 25. APEX Adapter

The first adapter is the current Oracle APEX implementation.

Do not rewrite the APEX exporter.

Extract/adapt existing functionality behind the adapter contract.

APEX adapter includes current capabilities around:

```text
APEX 26.1
APEXlang
layout mapping
target plans
code review
generation
SQLcl offline validation
artifact delivery
```

---

# 26. Generic Modernization Target

Before Java or .NET, create a non-generating target:

```text
Generic Modernization Architecture
```

Its purpose is to prove target-neutral modeling.

It may interpret intents such as:

```text
preserve existing owner
introduce service boundary
replace UI-only behavior
review business logic
redesign state handling
manual architecture decision
```

It generates no executable application.

It may export:

```text
architecture recommendations
backlog
decision package
modernization plan
```

This target proves FormsLang provides value independent of APEX.

---

# 27. Future Target SDK

Only after APEX + Generic prove the abstraction.

Future community adapters may include:

```text
Spring
.NET
custom enterprise target
```

Do not ship placeholders pretending to support these.

---

# 28. SDK Security Boundary

Community adapters must not automatically gain arbitrary access to:

```text
credentials
filesystem
network
source outside authorized scope
OS secret store
project database internals
```

If adapters become externally loadable, define an explicit capability model first.

Do not implement dynamic third-party plugin loading casually.

---

# 29. Global Search / Command Palette

Large estates need navigation beyond the sidebar.

Introduce:

```text
Ctrl/Cmd + K
```

Search across:

```text
Forms
Triggers
Program Units
Packages
Tables
Views
Business-rule candidates
Findings
Architecture nodes
Review items
```

Example:

```text
ORDERS

Form        ORDERS.fmb
Package     ORDER_API
Table       ORDERS
Finding     Direct DML in ORDERS
Rule        Approval status candidate
```

Search must use safe server-side bounded queries.

Do not load the entire estate into browser memory.

---

# 30. Deep Linking

Important product states must have stable deep links.

Examples:

```text
project overview
inventory entity
architecture node
finding
review decision
plan wave
artifact
report
```

A user should be able to send another engineer a link to a finding.

Revision-aware behavior must prevent a link from silently displaying materially different evidence as if unchanged.

---

# 31. Scale Requirements

Minimum synthetic scale target remains at least:

```text
500 Forms
5,000 findings
5,000+ dependencies
```

Future acceptance should add larger tests where useful.

---

## 31.1 UI scale laws

Forbidden:

```text
render every graph node at once
500-item unsearchable dropdown
load every finding client-side
filter huge datasets only in browser
DOM-render thousands of cards
```

Required where appropriate:

```text
server-side filtering
pagination
bounded graph expansion
virtualization if measured necessary
progressive detail
faceted search
cached projections
revision fencing
```

---

# 32. Estate Intelligence Performance Budgets

Define measurable budgets before implementation.

Candidate starting targets on synthetic acceptance hardware:

```text
Warm Overview projection:
<100 ms server-side where cache valid

Inventory first page:
<250 ms

Filtered inventory:
<500 ms

Finding detail:
<300 ms

Search:
<500 ms

Graph neighborhood:
<750 ms

Cold project reopen:
retain current few-second class or improve
```

Do not claim hard SLA.

Record measured acceptance hardware and dataset.

---

# 33. Reports 2.1

Expand reporting around modernization intelligence.

---

## 33.1 Executive Modernization Assessment

Must answer:

```text
estate size
analysis status
risk distribution
hotspots
unresolved critical decisions
modernization direction distribution
recommended investigation areas
proposed waves
```

No invented cost or duration.

---

## 33.2 Technical Modernization Assessment

Include:

```text
architecture inventory
dependency evidence
business-rule candidates
ownership
hotspots
risks
review decisions
target strategy
policy
modernization plan
blockers
```

---

## 33.3 Modernization Backlog

Backlog must be exportable as:

```text
CSV
JSON
```

Potential future issue-tracker integration is out of scope until designed separately.

---

# 34. Killer Report Requirement

A consulting engineer should be able to run FormsLang during discovery and produce a document worth giving to a customer even if no code generation occurs.

This is a core success criterion.

---

# 35. Reports Must Preserve Evidence Boundaries

Reports must distinguish:

```text
Observed
Inferred
Recommended
Human Approved
Target-specific
Unresolved
```

Never flatten them into one authoritative-looking statement.

---

# 36. Security and Privacy

Existing local-first guarantees remain.

No assessment feature may automatically send source externally.

---

## 36.1 Credentials

Credentials remain in the existing secret-store architecture.

Never place them in:

```text
project.json
assessment models
reports
Modernization IR
target adapter configuration serialization
```

unless a future encrypted credential-reference design explicitly permits a non-secret reference.

---

## 36.2 Source disclosure

List APIs should not expose source bodies.

Evidence details remain bounded.

Sensitive-data scanning and existing policies remain applicable.

---

## 36.3 Reports

Continue suppressing:

```text
credentials
host paths where unnecessary
sensitive raw source
human notes unless explicitly requested
```

---

# 37. Determinism

Core modernization assessment remains deterministic.

Given:

```text
same source bytes
same engine identity
same options
same policy
```

the deterministic assessment must remain identical.

Human decisions and timestamps are naturally separate.

---

# 38. Engine Identity

Engine identity must eventually incorporate:

```text
analysis rules
Modernization Model schema version
policy engine version
target interpretation rules where relevant
```

Target-independent assessment should not become stale merely because an unrelated target adapter changes unless the target-specific projection depends on it.

---

# 39. Revision Model Evolution

Design revisions carefully.

At minimum distinguish:

```text
source revision
analysis revision
modernization-model revision
review revision
policy revision
target strategy revision
target interpretation revision
plan revision
code approval revision
artifact revision
```

Do not create revisions gratuitously.

Some may be derived hashes rather than persisted counters.

Before coding, document which changes invalidate which downstream states.

---

# 40. Invalidation Matrix

Create an explicit matrix.

Example:

| Change              |          Reanalyze |                  Review invalid | Plan invalid |      Code invalid |  Artifact invalid |
| ------------------- | -----------------: | ------------------------------: | -----------: | ----------------: | ----------------: |
| Source bytes        |                Yes |                             Yes |          Yes |               Yes |               Yes |
| Analysis rule       |                Yes |                             Yes |          Yes |               Yes |               Yes |
| Organization policy |                 No | Maybe recommendation projection |          Yes |             Maybe |             Maybe |
| Target strategy     | No core reanalysis |                   Target review |          Yes |               Yes |               Yes |
| Human decision      |                 No |                    New revision |          Yes | Yes when affected | Yes when affected |
| Display preference  |                 No |                              No |           No |                No |                No |

The real matrix must be fully designed and tested.

---

# 41. Migration from 2.0

2.0 projects must continue opening.

Migration must be additive and non-destructive.

Do not silently change historical meaning.

---

## 41.1 Existing APEX projects

Existing:

```text
Oracle APEX / 26.1 / APEXlang
```

projects should migrate to the equivalent new TargetStrategy automatically only when the mapping is unambiguous.

---

## 41.2 Historical reviews

Existing Blueprint review events must remain readable.

Do not rewrite event history into new modernization intents.

Use compatibility projection/mapping.

---

## 41.3 Existing artifacts

Existing generated APEX artifacts retain their original provenance.

Do not upgrade their metadata in a way that falsely implies they were generated under the new adapter architecture.

---

# 42. Demo Project

The bundled demo becomes strategically important.

It must demonstrate:

```text
Forms source
database source
cross-layer analysis
architecture map
API ownership
direct DML
duplicated rule candidate
risk
AUTO
ASSISTED
MANUAL
review
plan
APEX target
generation eligibility
```

All source remains synthetic.

Do not reuse benchmark cases verbatim if that risks coupling demo behavior to benchmark expectations.

---

# 43. “Holy Shit” Demo Moment

The demo must include at least one finding where Forms code alone suggests one action but database context changes the correct direction.

Example concept:

```text
ORDERS.WHEN-VALIDATE-ITEM

Forms-only interpretation:
Convert validation

Cross-layer evidence:
INVENTORY_API already owns equivalent behavior

Modernization intent:
CENTRALIZE_EXISTING_OWNER

APEX recommendation:
MOVE_TO_PLSQL_API

Execution:
ASSISTED
```

This is the product's strongest explanatory moment.

---

# 44. Benchmark Evolution

Do not invalidate frozen v1/v2/v3 benchmark history.

Existing frozen baselines remain immutable.

---

## 44.1 New benchmark generation

Future benchmark versions should evaluate:

```text
observability
fact extraction
ownership inference
modernization intent
target recommendation
risk
execution verdict
false automation
critical safety
```

Do not merge all correctness into one headline metric.

---

# 45. Benchmark vNext

Target:

```text
100+ reviewed cases
```

before claiming materially broader benchmark coverage.

Cases should intentionally include:

```text
Forms-only behavior
existing APIs
direct DML
constraints
database triggers
shared PLL logic
global state
navigation
concurrency
duplicated logic
conflicting ownership
native target behavior
unknown intent
retirement/drop candidates
```

---

# 46. Community Benchmark Contributions

Design a contribution format that accepts synthetic cases.

Contributors should provide:

```text
synthetic source
expected observed facts
expected modernization intent
expected risk
expected execution verdict
review rationale
```

Never require customer code.

---

# 47. Benchmark Anti-Leakage Rule

Continue enforcing:

> **If a reasoning rule cannot be expressed structurally, it does not belong in the engine.**

Automated de-coupling audits must remain release gates.

Search product reasoning for:

```text
benchmark IDs
fixture module names
fixture package names
fixture table names
baseline names
```

Allow these only in benchmark tooling/fixtures/tests where appropriate.

---

# 48. Quality Metrics

Track separately:

```text
Exact modernization-intent accuracy
Macro F1
Risk accuracy
Critical recall
High + Critical recall
Manual-review recall
False automation
Critical safety misses
Observability
Ownership accuracy
Target recommendation accuracy
```

Do not use one number to imply universal migration accuracy.

---

# 49. UX Acceptance

The new UI must receive real acceptance coverage.

At minimum test:

```text
first-run onboarding
no-target project
APEX-target project
Overview
Estate
Architecture
Review
Plan
Deliver
search
deep links
stale project
missing source
incomplete project
revision conflict
500-Form estate
narrow desktop window
keyboard navigation
XSS-safe evidence
```

---

# 50. Accessibility

Retain or improve:

```text
keyboard navigation
focus visibility
semantic controls
labels
ARIA only where necessary
color contrast
non-color state indicators
screen zoom support
```

Automated checks are not a substitute for manual accessibility testing.

Document this limitation.

---

# 51. Error UX

Errors must explain:

```text
what happened
what remains safe
what the user can do next
```

Prefer:

> Source changed after analysis. Your previous assessment was preserved. Reanalyze to review current evidence.

over:

> RevisionConflict.

---

# 52. Freshness UX

Freshness should remain visible at project level.

States:

```text
Current
Stale
Missing Source
Incomplete
Unverified
```

Explain them in plain language.

---

# 53. Command Palette

Implement after underlying search endpoints are stable.

Keyboard:

```text
Ctrl+K / Cmd+K
```

Search results must support direct navigation.

No command may bypass authorization or review gates.

---

# 54. CLI Evolution

CLI must receive target-neutral equivalents.

Potential direction:

```text
formslang project summary
formslang project estate
formslang project architecture
formslang project hotspots
formslang project rules
formslang project review
formslang project plan
formslang project target
formslang project report
```

Do not break existing commands.

---

# 55. HTTP API Evolution

Continue under:

```text
/api/v2
```

for additive compatible capabilities where possible.

Do not create `/api/v3` merely because FormsLang reaches 3.0.

API version changes only for contract-breaking HTTP changes.

---

# 56. Potential New Endpoints

Conceptual only:

```text
GET /overview

GET /estate/hotspots
GET /estate/business-rules
GET /estate/ownership

GET /architecture/neighborhood
GET /architecture/node/:id
GET /architecture/edge/:id

GET /plan
POST /plan/recalculate

GET /targets
GET /target
POST /target

GET /policy
POST /policy
```

Design precise schemas before implementation.

---

# 57. No New Persistence Without Evidence

Continue preferring deterministic projections.

Do not create:

```text
dashboard table
search index
graph cache database
hotspot persistence
```

merely for convenience.

Use persisted projections only if scale measurement proves necessary.

---

# 58. Search Index Decision Gate

Before adding FTS or another persisted search structure:

measure current query performance against:

```text
500 Forms
5,000 findings
5,000 dependencies
```

and a larger stress corpus.

Document why an index is justified.

---

# 59. Modernization Plan Persistence

Plan state is different from read-only projections.

If human-adjustable wave assignment or planning decisions exist, those decisions require persisted revisioned state.

Automatic suggested waves should remain derived.

Human plan decisions remain separate.

---

# 60. Product Boundaries

FormsLang does NOT claim to determine:

```text
business truth
whether legacy behavior is desired
organizational architecture
security requirements not visible in source
runtime equivalence
UAT success
performance parity
production readiness
migration completion time
migration cost
```

---

# 61. Target-Neutral Does Not Mean Target-Agnostic Everywhere

Core assessment should be target-neutral.

Some questions inherently require the target.

Example:

```text
Can APEX replace this behavior natively?
```

belongs to the APEX adapter.

Do not move target knowledge into the core merely because the same recommendation existed historically.

---

# 62. APEX Remains a First-Class Experience

Users choosing APEX should still receive:

```text
APEX-native opportunities
APEX-specific recommendation
APEX target plan
APEX code review
APEXlang generation
SQLcl validation
delivery artifacts
```

Target-neutral evolution must not make the APEX path feel generic or degraded.

---

# 63. Generic Target Value

A user selecting no implementation target should still receive:

```text
estate intelligence
architecture map
risk
business-rule candidates
ownership
hotspots
review
modernization intents
plan
reports
backlog
```

This is the key strategic success condition.

---

# 64. README Repositioning

Once features are released, README should eventually lead with:

> **Before you migrate Oracle Forms, understand what you're actually migrating.**

Supporting text:

> FormsLang maps Oracle Forms and database source together to reveal dependencies, duplicated business-rule candidates, API ownership, architecture risk and reviewable modernization decisions before implementation begins.

Do not change README claims until features exist.

---

# 65. Five-Minute First Experience

Target experience:

```text
Install
→ Launch
→ Explore Demo Project
→ Analyze
→ Overview
→ Open hotspot
→ Inspect cross-layer evidence
→ See modernization recommendation
```

No AI setup.

No database login.

No account.

No CLI.

---

# 66. Two-Minute Product Demo

Design the product so a 2-minute recording can show:

```text
00:00 open FormsLang

00:10 Explore Demo Project

00:20 Analyze

00:35 Estate Overview

00:50 hotspot

01:00 Forms evidence

01:10 database evidence

01:20 ownership/recommendation

01:30 human decision

01:40 target interpretation

01:50 generation eligibility

02:00
Understand first. Modernize second.
```

---

# 67. Release Strategy

Do not implement everything and release FormsLang 3.0 at once.

Use incremental releases.

---

# 68. FormsLang 2.1 — Estate Intelligence

Primary goal:

> Make FormsLang valuable before conversion.

Scope:

```text
Phase 0 UX foundation
target-unselected project support
new Overview
Estate workspace
hotspot model
improved dependency experience
global search foundations
executive modernization assessment improvements
demo upgrade
```

Do NOT implement community target SDK yet.

---

# 69. FormsLang 2.2 — Modernization Model

Primary goal:

> Separate what the system observes from what the target should do.

Scope:

```text
Modernization Model / IR
observed facts
structural signals
target-neutral intents
existing recommendation compatibility
facts/inferences/recommendation UX
revision model
migration from 2.1
benchmark extensions
```

---

# 70. FormsLang 2.3 — Architecture & Planning

Scope:

```text
Architecture workspace
bounded graph
ownership experience
business-rule clusters
Modernization Plan
migration waves
dependency-aware ordering
expanded technical reports
```

---

# 71. FormsLang 2.4 — Policy

Scope:

```text
FormsLang default policy
organization policy
project policy
policy provenance
policy UX
revision/invalidation
policy-aware recommendations
```

---

# 72. FormsLang 2.5 — Target Adapter Foundation

Scope:

```text
TargetAdapter interface
APEX extraction behind adapter
Generic modernization target
target strategy UX
target capability model
adapter acceptance tests
```

Do not load external plugins yet.

---

# 73. FormsLang 2.6 — Extension Model

Only after 2.5 proves stable.

Scope:

```text
SDK contract
adapter developer documentation
controlled extension loading design
capability/security model
sample non-production adapter
```

---

# 74. FormsLang 3.0

3.0 is justified when FormsLang can truthfully claim:

> **Oracle Forms modernization intelligence independent of one implementation target.**

Minimum expected capabilities:

```text
target-neutral assessment
Estate Intelligence
architecture mapping
business-rule ownership
reviewable modernization intents
Modernization Plan
policy
APEX adapter
Generic target
stable adapter architecture
high-quality reports
stable migration from 2.x
expanded benchmark
```

3.0 does NOT require Java/.NET code generation.

---

# 75. Non-Goals Through 3.0

Unless separately approved:

```text
Automatic Java application generation
Automatic .NET application generation
Automatic React frontend generation
Full semantic understanding of undocumented business intent
Autonomous architecture decisions
Automatic deployment
Replacing UAT
Cloud SaaS rewrite
Frontend framework migration
LLM-based risk scoring
LLM-based architecture authority
Production project-duration prediction
Automatic migration cost prediction
```

---

# 76. Acceptance Metrics for Product Success

Track product-quality signals rather than vanity features.

Possible technical metrics:

```text
time to first assessment
time to open top hotspot
search latency
review completion flow
number of cross-layer relationships found
percentage of findings with traceable evidence
false automation
critical safety misses
deterministic rebuild success
project reopen compatibility
```

Do not collect telemetry automatically unless a privacy-reviewed opt-in design is created.

Synthetic/local acceptance is sufficient initially.

---

# 77. Testing Strategy

Every phase requires:

```text
unit tests
store integration tests
service tests
CLI tests
HTTP contract tests
browser tests
security tests
concurrency tests
revision conflict tests
upgrade/migration tests
determinism tests
scale tests
XSS tests
```

---

# 78. Frozen Benchmark Protection

Existing benchmark files remain byte-identical.

Add release tests verifying they were not accidentally changed.

New benchmark versions live separately.

---

# 79. Installer and Upgrade Gate

Every stable release continues requiring:

```text
fresh Windows install
upgrade from previous stable
project reopen
saved reviews survive
descriptor survives
assessment survives
reports work
desktop launches
```

For target-neutral versions, additionally verify:

```text
old APEX project migrates correctly
target-unselected project opens
APEX target remains functional
```

---

# 80. Artifact Compatibility

Do not silently rewrite previously generated managed artifacts.

Existing hashes and validation evidence remain historical.

New target architecture only affects new artifacts.

---

# 81. Documentation

Create documentation hierarchy eventually covering:

```text
Modernization Intelligence
Estate Intelligence
Architecture
Modernization Model
Review
Plan
Policy
Targets
APEX Target
Generic Target
Reports
Security
Benchmark
Extension SDK
Migration
```

Avoid duplicated explanations across ten documents.

---

# 82. Developer Architecture Documentation

Add a central architecture document explaining:

```text
source discovery
parsing
observed facts
signals
Modernization Model
policy
target adapter
review
plan
generation
validation
reports
```

Use one canonical architecture diagram.

---

# 83. UX Documentation

Document:

```text
navigation model
terminology
design tokens
status meanings
risk meanings
review meanings
target states
freshness states
keyboard behavior
minimum viewport
```

---

# 84. Work Execution Model

Do not implement this specification as one giant branch.

Use phased PRs.

Each phase starts with:

```text
design
contracts
migration impact
test plan
performance plan
security impact
```

before large implementation.

---

# 85. Mandatory Pre-Implementation Audit

Before coding Phase 0/2.1, produce:

## A. Current architecture map

List actual:

```text
modules
service ownership
Store tables
project tables
assessment structures
UI screens
routes
CLI commands
```

## B. Gap analysis

For every requested concept classify:

```text
Already exists
Needs extension
Needs refactor
New capability
Should not be built yet
```

## C. Compatibility risks

Identify risks to:

```text
2.0 projects
1.x legacy sessions
APEX generation
review history
installer upgrade
CLI
HTTP
benchmark
```

---

# 86. Architecture Review Gate

Before implementation, present the proposed design for:

```text
target-unselected project state
Modernization Model
target adapter boundary
policy model
navigation structure
Estate Intelligence projections
Architecture graph
revision/invalidation model
```

Do not begin broad implementation until these concepts are internally consistent.

---

# 87. Phase 2.1 Implementation Order

After architecture review, use approximately:

```text
A. UX foundation
B. target-unselected project compatibility
C. Estate projection contracts
D. hotspot engine
E. Overview
F. Estate workspace
G. improved dependencies
H. search
I. reports
J. demo
K. scale/security/accessibility
L. docs
M. release acceptance
```

---

# 88. Hotspot Implementation Rule

Do not create hotspots directly from UI requirements.

For each hotspot first define:

```text
name
problem
source evidence required
deterministic algorithm
risk interpretation
known false positives
known false negatives
expected test fixtures
UI projection
report representation
```

Only then implement.

---

# 89. Candidate Initial Hotspots

Evaluate, do not blindly implement all:

```text
DIRECT_DML
API_BYPASS
DUPLICATED_RULE
GLOBAL_STATE
NAVIGATION_COUPLING
DEPENDENCY_CYCLE
HIGH_FAN_IN
HIGH_FAN_OUT
MULTIPLE_RULE_OWNERS
UNOWNED_RULE
GUARD_LOSS
CONCURRENCY_RISK
UNSUPPORTED_BEHAVIOR
```

Prioritize those already supported by evidence in current engine.

---

# 90. Evidence Model

Evidence references should prefer durable structural identities.

Conceptual:

```text
EvidenceRef

source_id
source_revision
entity_id
entity_type
location
relationship
signal
excerpt_policy
```

Avoid persisting unnecessary full source bodies.

---

# 91. Finding Identity

Findings should remain stable enough for review history where source meaning is unchanged.

Do not use row order or timestamps as identity.

Reanalysis must conservatively invalidate when identity cannot be proven.

---

# 92. Business Rule Candidate Model

Potential fields:

```text
candidate_id
structural_signature
implementations
source_layers
possible_owner
conflicts
supporting_signals
risk
confidence_class
```

Avoid numeric “AI confidence” unless it has a defined mathematical interpretation.

Prefer semantic states such as:

```text
STRONG_EVIDENCE
PARTIAL_EVIDENCE
CONFLICTING_EVIDENCE
INSUFFICIENT_EVIDENCE
```

if useful.

---

# 93. Confidence Terminology

Do not show a percent confidence just because users expect one.

Only display confidence if backed by a defined scoring model.

Otherwise use evidence quality / observability labels.

---

# 94. Architecture Graph Storage

The graph should be derived from assessment data.

Do not immediately create a graph database.

SQLite/current model remains preferred.

A graph database requires measured evidence that current architecture cannot meet product requirements.

---

# 95. AI Boundary

Modernization decisions remain deterministic unless a future separately approved architecture changes this.

AI may be used for:

```text
explanation drafts
documentation
possible code drafts
natural-language summaries
```

but not silently for:

```text
risk truth
source fact extraction truth
architecture approval
business intent truth
generation authorization
```

---

# 96. Enterprise Adoption Goal

The product should become useful to:

```text
individual Oracle developers
Oracle Forms specialists
Oracle APEX developers
architects
modernization teams
consultancies
Oracle partners
ERP teams
enterprise application owners
```

Do not optimize the entire UX around one developer converting one form.

---

# 97. Consultancy Workflow

FormsLang should eventually support this real workflow:

```text
Customer supplies Forms2XML + allowed database source

Consultant creates project

FormsLang analyzes estate

Consultant reviews:
architecture
hotspots
risk
ownership

Consultant produces:
Executive Assessment
Technical Assessment
Modernization Backlog
Proposed Waves

Architecture workshop occurs

Target is selected

Target-specific implementation begins
```

This workflow must be valuable even when FormsLang is not the final code generator.

---

# 98. Product Moat

The defensible value is not:

```text
Forms XML parsing
```

alone.

The moat should become:

```text
cross-layer Oracle Forms modernization knowledge
+
structural reasoning
+
reviewable evidence
+
benchmark
+
human decision history
+
target interpretation
```

---

# 99. Open Source Strategy

Keep core assessment useful in open source.

Do not intentionally cripple open-source discovery to create artificial enterprise value.

Long-term commercial/enterprise differentiation, if ever pursued, should come from real organizational needs such as:

```text
team workflow
centralized governance
organization policy
large-scale collaboration
integrations
support
managed deployment
```

not from making the core analyzer useless.

---

# 100. Release Communication

Do not market future capability before it exists.

For 2.1 say:

> Estate Intelligence

not:

> Multi-target modernization platform

until the target-neutral architecture is actually usable.

---

# 101. Final 3.0 Product Story

The eventual user story should be:

```text
I inherited 600 Oracle Forms.

I do not yet know whether they will become
APEX, Java, .NET or a mix.

I run FormsLang.

FormsLang tells me:

what exists
what depends on what
where business logic lives
which APIs already own behavior
where rules are duplicated
where UI code bypasses architecture
which areas are risky
which decisions are mechanical
which decisions require a human
how the estate can be grouped into modernization waves

Then I choose the target.

FormsLang interprets the reviewed decisions for that target.

Only then do I generate or implement.
```

If FormsLang can credibly support that story, the strategic objective has been reached.

---

# 102. Required First Deliverables From This Specification

Do not begin by implementing dozens of files.

First produce the following artifacts in the repository:

```text
docs/superpowers/specs/
  formslang-modernization-intelligence-vision.md
  formslang-21-ux-information-architecture.md
  formslang-modernization-model-design.md
  formslang-target-adapter-design.md
  formslang-21-estate-intelligence-design.md
```

Exact filenames may follow current repository conventions.

---

# 103. First Design Document — Vision

Document:

```text
Current state
Strategic problem
Product vision
Primary users
Core jobs to be done
Product doctrine
Target-neutral strategy
Non-goals
2.1 → 3.0 roadmap
```

---

# 104. Second Design Document — UX

Create wireframes in text/HTML where useful for:

```text
Onboarding
Overview
Estate
Architecture
Review
Plan
Deliver
Policy
Target Strategy
Global Search
```

Do not implement polished visuals before information hierarchy is approved.

---

# 105. Third Design Document — Modernization Model

Define:

```text
facts
signals
intent
recommendation
review
policy
target interpretation
revision
serialization
migration
```

Include mapping from every current FormsLang recommendation.

---

# 106. Fourth Design Document — Target Adapter

Show how current APEX implementation maps into adapter responsibilities.

Identify code that:

```text
stays core
moves behind adapter
remains legacy compatibility
```

Do not refactor yet.

---

# 107. Fifth Design Document — Estate Intelligence

Define initial:

```text
metrics
hotspots
ranking
Overview
Estate views
scale behavior
API contracts
CLI contracts
reports
tests
```

---

# 108. Agent Operating Instructions

Work against current `main`.

Before changes:

```text
git fetch
verify clean working tree
identify latest stable tag
run baseline test suite
record baseline results
```

Create a dedicated branch:

```text
codex/formslang-modernization-intelligence-design
```

or repository-conventional equivalent.

---

# 109. Do Not Destroy Existing Work

Forbidden without explicit approval:

```text
force reset of user work
rewriting frozen benchmarks
deleting compatibility code
breaking 1.x session import
breaking 2.0 projects
replacing ProjectService with a parallel architecture
introducing a second Store
rewriting UI in another framework
changing APEX generation semantics while designing target adapters
```

---

# 110. Validation Before Coding

For the design PR:

Run:

```text
documentation/link validation
existing architecture tests relevant to touched docs/tools
git diff --check
```

No full implementation is expected in the design PR unless tiny supporting prototypes are explicitly justified.

---

# 111. Design PR Output

Create a PR containing:

```text
Product vision
UX architecture
Modernization Model
Target Adapter architecture
Estate Intelligence design
Migration plan
Phased implementation plan
Risk register
Open questions
Acceptance gates
```

---

# 112. After Design Approval

Implementation begins in small phase branches.

Suggested branch sequence:

```text
codex/formslang-21-foundation
codex/formslang-21-estate
codex/formslang-21-overview
codex/formslang-21-architecture
codex/formslang-21-search
codex/formslang-21-reports
codex/formslang-21-acceptance
```

The exact split should be adjusted based on the approved design.

---

# 113. Critical Product Test

At the end of FormsLang 2.1 ask:

> If I am planning to rewrite my Forms application in Java and never generate APEX, is FormsLang already useful?

If the answer is not clearly yes, 2.1 has not fully achieved its strategic goal.

---

# 114. Critical UX Test

Open a synthetic 500-Form project.

Within one minute, a new user should be able to understand:

```text
estate size
freshness
top risks
top hotspots
where to begin investigation
```

without documentation.

---

# 115. Critical Trust Test

Select a high-priority recommendation.

A reviewer should be able to determine:

```text
what was observed
what was inferred
why the recommendation exists
what evidence supports it
what remains uncertain
whether a human already decided
```

without reading internal database tables or logs.

---

# 116. Critical Architecture Test

The same target-neutral modernization intent must be capable of receiving:

```text
an APEX interpretation
```

and:

```text
a Generic interpretation
```

without rerunning source analysis.

If target selection changes and the entire Forms/database analysis must run again solely because of implementation technology, the abstraction is wrong.

---

# 117. Critical Safety Test

Changing:

```text
source
analysis rules
policy
target
human decision
code approval
```

must invalidate only the downstream state it logically affects.

Never retain a generation authorization whose evidence binding is no longer valid.

---

# 118. Definition of Done for the Full Program

The 2.1 → 3.0 program is successful when:

1. FormsLang provides strong discovery value before target selection.
2. Estate Intelligence makes large Forms estates understandable.
3. Cross-layer architecture is navigable.
4. Observed facts are clearly separated from inferences.
5. Business-rule ownership can be reviewed.
6. Target-neutral modernization intents exist.
7. Human decisions remain auditable.
8. Modernization planning exists without fake scheduling estimates.
9. Organization/project policy can influence recommendations without rewriting facts.
10. APEX functionality operates through a stable target boundary.
11. Generic modernization works without APEX generation.
12. Existing 2.x projects remain compatible.
13. Frozen benchmarks remain intact.
14. New benchmark coverage expands safely.
15. UI remains scalable at large-estate sizes.
16. Security/local-first guarantees remain.
17. Reports are useful as professional discovery deliverables.
18. FormsLang can honestly be described as modernization intelligence rather than merely a Forms-to-APEX converter.

---

# 119. Final Product Principle

Every implementation choice should be tested against this statement:

> **FormsLang should automate the work that machines can verify, expose the evidence behind what they infer, and leave architectural and business judgment with the people responsible for the system.**

And every new feature should answer one of five questions:

```text
UNDERSTAND
What do I have?

ASSESS
What matters?

DECIDE
What should happen?

PLAN
How do we modernize it?

DELIVER
What can safely move forward?
```

If a proposed feature does not materially improve one of those questions, reconsider whether it belongs in the product.
