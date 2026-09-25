# FormsLang 3.0
## Versioned Modernization Repository
### Master Product, Architecture, Experience, Language, Reporting, and Delivery Specification

| Document control | Value |
|---|---|
| Document ID | FL3-MASTER-2026-09-25 |
| Specification revision | 1.0 — integrated English specification |
| Date | September 25, 2026 |
| Product owner | Geraldo Viana / B2DEV TECH |
| Intended readers | Implementation agents, maintainers, architects, Oracle Forms/APEX specialists, frontend engineers, test engineers, and security reviewers |
| Status | Implementation contract for the requested direction; not evidence that any 3.0 feature has shipped |
| Source baseline | The Portuguese specification dated September 25, 2026, plus the owner's subsequent whole-repository and first-class-reporting direction |
| Delivery principle | Correct architecture and demonstrated usefulness take precedence over an early version-number announcement |
| Initial target | Oracle APEX through the existing APEXlang-related capabilities, subject to verified adapter support |
| Default operating model | Local-first, offline-capable, single-owner workspace; shared-server support is separately gated |

> **FormsLang is the versioned workspace between understanding an Oracle Forms legacy estate and delivering a modern application. It preserves the sources, evidence, decisions, plans, outputs, validation records, and reports that explain the entire modernization journey.**

> **The versioned object is the modernization project as a whole—not merely a decision file, a generated application, or a graph.**

---

## How to use this specification

Read Sections 1–8 before designing persistence or changing the application shell. Read Sections 9–17 before changing the language, services, CLI, HTTP contracts, or frontend. Read Sections 18–25 before implementing reporting, generation, migration, security, or release behavior. Execute the milestones and acceptance contracts in Sections 26–30. The appendices define delivery traceability, source references, and the implementation-agent handoff.

This is a consolidated specification, not an addendum that requires the implementer to reconstruct earlier conversations. It incorporates the original direction and deliberately strengthens whole-project versioning and reporting. The original feature limitations and evidence rules remain binding unless a more explicit rule here refines them.

**Normative terms:** MUST and MUST NOT are release obligations for the applicable scope. SHOULD is the default and requires a recorded reason to diverge. MAY is optional. A requirement described as **future** does not become a 3.0 obligation merely because an interface could support it. **Candidate measurement thresholds** must be baselined and ratified before their implementation milestone; they must not be changed retrospectively to turn a failing release green.

New commands, schemas, paths, object types, and examples in this document are design contracts, not claims about currently installed FormsLang behavior. The implementation agent MUST verify the checked-out repository before selecting exact integration paths. Do not advertise illustrative commands until executable documentation tests prove them.

### Contents

1. [Product mandate and success definition](#1-product-mandate-and-success-definition)
2. [Scope, release boundaries, and non-goals](#2-scope-release-boundaries-and-non-goals)
3. [Baseline inspection and reuse strategy](#3-baseline-inspection-and-reuse-strategy)
4. [Domain vocabulary and non-negotiable invariants](#4-domain-vocabulary-and-non-negotiable-invariants)
5. [Repository architecture and authority](#5-repository-architecture-and-authority)
6. [Immutable objects, identities, and canonical formats](#6-immutable-objects-identities-and-canonical-formats)
7. [Checkpoints, history, Git exchange, and restoration](#7-checkpoints-history-git-exchange-and-restoration)
8. [Transactions, concurrency, failure recovery, and jobs](#8-transactions-concurrency-failure-recovery-and-jobs)
9. [Source intake, facts, evidence, and analysis](#9-source-intake-facts-evidence-and-analysis)
10. [Graph, search, dependency paths, and change impact](#10-graph-search-dependency-paths-and-change-impact)
11. [FormsLang Decision Language](#11-formslang-decision-language)
12. [Decision lifecycle, approvals, and import semantics](#12-decision-lifecycle-approvals-and-import-semantics)
13. [Services, module boundaries, and integration contracts](#13-services-module-boundaries-and-integration-contracts)
14. [CLI product contract](#14-cli-product-contract)
15. [HTTP and asynchronous interaction contracts](#15-http-and-asynchronous-interaction-contracts)
16. [Workbench information architecture and visual system](#16-workbench-information-architecture-and-visual-system)
17. [Detailed screens and end-to-end journeys](#17-detailed-screens-and-end-to-end-journeys)
18. [Reporting as a first-class product capability](#18-reporting-as-a-first-class-product-capability)
19. [Metric definitions, coverage, and readiness](#19-metric-definitions-coverage-and-readiness)
20. [Planning, intermediate representation, and APEX generation](#20-planning-intermediate-representation-and-apex-generation)
21. [Validation and source-to-target traceability](#21-validation-and-source-to-target-traceability)
22. [Optional AI and controlled information disclosure](#22-optional-ai-and-controlled-information-disclosure)
23. [Security, privacy, access, and operational modes](#23-security-privacy-access-and-operational-modes)
24. [Legacy migration, installation, and compatibility](#24-legacy-migration-installation-and-compatibility)
25. [Performance, accessibility, observability, and support](#25-performance-accessibility-observability-and-support)
26. [Implementation milestones and dependency ordering](#26-implementation-milestones-and-dependency-ordering)
27. [Test corpus and acceptance scenarios](#27-test-corpus-and-acceptance-scenarios)
28. [Release gates and definition of done](#28-release-gates-and-definition-of-done)
29. [README, documentation, and public communication](#29-readme-documentation-and-public-communication)
30. [Agent execution protocol and first implementation assignment](#30-agent-execution-protocol-and-first-implementation-assignment)
31. [Required architecture decision records](#31-required-architecture-decision-records)
32. [Original-specification coverage and reference register](#32-original-specification-coverage-and-reference-register)
33. [Final acceptance narrative](#33-final-acceptance-narrative)

---

## 1. Product mandate and success definition

### 1.1 The problem to solve

An engineer receives one unfamiliar Form or an estate containing hundreds of Forms, related libraries, database packages, queries, and operational knowledge. Before producing a target application, the engineer needs to determine what exists, how it is connected, what the available source actually proves, what is missing, what must be preserved, and what should be redesigned.

The owner has rejected a product experience that requires understanding a collection of internal analysis screens before obtaining practical value. FormsLang must organize modernization work, rather than expose every engine subsystem as a separate dashboard.

The core journey remains:

**Understand → Decide → Build → Validate.**

The repository spans this journey. **History and Reports are first-class cross-cutting surfaces**, not extra steps that every newcomer must complete and not obscure Advanced exports.

### 1.2 Product identity

**DIR-01.** FormsLang MUST be a versioned modernization repository and workbench. It MUST NOT be implemented merely as a Forms-to-APEX converter with a replacement theme and a DSL editor.

**DIR-02.** A project MUST correlate source artifacts, immutable analyses, extracted facts, evidence, dependency relationships, unknowns, decisions, mappings, plans, generated artifacts, validations, human acceptance evidence, risks, blockers, reports, and historical change.

**DIR-03.** Workbench, CLI, report generation, and automation MUST operate on the same repository model and domain services. They are alternative ways to inspect and operate the same project.

**DIR-04.** The FormsLang language MUST express modernization intent and reviewed decisions in a small, declarative, portable form. It MUST NOT become a second general-purpose programming language, a replacement for PL/SQL, or a universal application runtime.

**DIR-05.** Oracle APEX is the first implementation target. APEX-specific choices MUST be explicit target mappings, not definitions of what the legacy application is.

**DIR-06.** An engineer MUST be able to obtain useful exploration, history, and reporting without an AI account, a live Oracle database, an APEX workspace, or hand-written DSL.

### 1.3 The question every meaningful object must answer

For a permitted object and a selected repository context, the product should answer:

> What is it? Where did it come from? What uses it? What does it use? What evidence supports those statements? What is unresolved? What was decided? Who recorded or approved that decision? What changed? What may be affected? How is it represented in the target? What has actually been validated?

Not every answer will exist. Missing answers must be represented as missing, with a reason and a next action—not filled with plausible prose.

### 1.4 Primary users and observable outcomes

| User | Job to accomplish | Observable product outcome |
|---|---|---|
| Engineer encountering an unknown module | Identify a screen, its components, and its first meaningful dependency | Opens a Form, follows a relationship, inspects evidence, and records a question without training in internal engine terminology |
| Modernization architect | Understand an estate and its boundaries | Navigates cross-Form and database dependencies, distinguishes unknowns, compares baselines, and produces a traceable assessment |
| Oracle Forms/APEX specialist | Choose and validate a target representation | Records an evidence-backed mapping, sees a semantic diff, builds only eligible scope, and follows validation failures back to the original decision |
| Technical lead or reviewer | Review why and how a migration changed | Reviews history and decision changes without having to infer intent from generated SQL |
| CLI/CI engineer | Reproduce work and enforce gates | Reopens an authorized portable project, reproduces deterministic outputs, obtains stable JSON, and detects stale decisions and policy failures |
| Manager or delivery stakeholder | Understand progress and unresolved scope | Reads a report with defined denominators, explicit limitations, and evidence-backed blockers, rather than an invented completion percentage |

### 1.5 Success is demonstrated, not announced

A feature is not complete because its class exists, its mockup looks correct, or an isolated test is green. It is complete when the relevant user journey works on a packaged build against a declared fixture, negative cases remain honest, and the evidence is attached to the implementation milestone.

The product is not required to finish quickly. It is required to avoid indefinite architectural churn: ship reviewable increments, preserve a working baseline, and converge through measurable gates.

## 2. Scope, release boundaries, and non-goals

### 2.1 Required 3.0 capability groups

| Capability group | Required scope |
|---|---|
| Repository | Whole-project context, immutable content references, checkpoints, coherent history, status, comparison, export/import, integrity verification, and recovery |
| Understanding | Supported source intake, evidence-backed analysis, screen-centered exploration, component and database relationships, explicit missing coverage |
| Language and decisions | Parser, canonical serializer, semantic validation, human approval, conflict detection, portability, versioned history, and safe legacy migration |
| Workbench and CLI | Equivalent domain operations, modern navigation, evidence inspector, usable diffs, historical views, accessible alternatives, and stable automation contracts |
| Reports | Technical and executive report center, full authorized-scope queries, provenance, metric definitions, change reports, completeness statements, and portable report packages |
| Target delivery | Deterministic planning and generation for explicitly supported APEX constructs; traceable omissions and blockers |
| Validation | Separately represented structural, tool, import, runtime, and human acceptance evidence |
| Delivery | Existing-project upgrade, packaged installation, regression protection, release documentation, and usability evidence |

### 2.2 Explicitly separate the horizons

**3.0 required:** the repository foundation and a complete, useful end-to-end modernization journey, including reports, for supported representations and supported APEX scope.

**Conditional on additional acceptance:** one consolidated APEX application spanning multiple Forms; new Forms/SQL constructs; automatic Oracle environment execution; supported authenticated team/server deployment. None is implied by a generic adapter or a database schema.

**Future:** Java, .NET, React, or other target generators; distributed repository hosting; native branch orchestration; automatic semantic merge beyond a reviewed import workflow; collaboration features that require a new security model; production deployment orchestration.

A roadmap may evolve. It MUST NOT retroactively label an unmet required capability as future simply to call a partial build 3.0. Scope changes require an explicit owner decision and an updated release contract.

### 2.3 Non-goals and prohibited shortcuts

**SCOPE-01.** Do not implement a clone of Git's storage engine, remote protocol, hosting platform, or branch UI merely to justify the Git-like product analogy. Reuse Git for file version control where appropriate. FormsLang supplies domain semantics.

**SCOPE-02.** Do not simulate Oracle Forms runtime, claim exact user navigation order from static relationships, or equate a graph path with an executed workflow.

**SCOPE-03.** Do not claim that registering an FMB or PLL binary provides semantic parsing. Record and preserve the file when authorized; explain the supported conversion/representation path.

**SCOPE-04.** Do not claim full Forms/APEX functional equivalence, universal trigger conversion, production readiness, or a measured migration saving without corresponding evidence.

**SCOPE-05.** Do not rewrite working parsers, APEXlang semantics, authentication, or project persistence wholesale for stylistic consistency. Refactor behind tested contracts.

**SCOPE-06.** Do not force a new graph database, frontend framework, cloud service, or remote dependency without an architecture decision and demonstrated benefit across packaging, security, maintenance, and performance.

**SCOPE-07.** Do not equate "everything versioned" with putting secrets, private source bodies, all logs, live SQLite files, or unbounded binary history into Git.

**SCOPE-08.** Do not ship a decorative graph or a generic CRUD dashboard as the replacement Workbench. The visual interface must shorten real modernization tasks.

## 3. Baseline inspection and reuse strategy

### 3.1 What the source document establishes—and what it does not

The original specification used release 2.2.0 as its public baseline and referenced the first ecosystem-explorer 2.3 phase as contract/test groundwork. It described a project manifest, SQLite-backed history, analysis/Blueprint representations, APEX-related export capabilities, and existing CLI/Workbench surfaces. These are statements from that source document, not a fresh audit of the current repository. [B1]

The implementation agent MUST record the actual branch, commit, installed/buildable version, release assets, and open work before making a change. A feature already completed since that baseline must be reused and tested rather than implemented a second time.

### 3.2 Initial inspection targets

Inspect the following repository-relative paths where present; locate their current equivalents when renamed:

```text
AGENTS.md and applicable nested agent instructions
README.md
pyproject.toml and dependency/lock files
.github/workflows/
docs/roadmap-2.md
docs/architecture-2.md
docs/project-model.md
docs/modernization-review.md
docs/forms-to-apex.md
docs/user-guide/12-security-and-privacy.md
docs/user-guide/15-limitations.md
docs/design/ecosystem-explorer-2.3/
formslang/ui/modernization_visual.py
ProjectService and project storage implementation
Blueprint/assessment models and serializers
modernization_model.py, architecture_policy.py, target_adapter.py, adapters/
Existing CLI, APEXlang exporter, reporting code, and installer definitions
Existing fixtures, upgrade tests, browser tests, and SQLcl validation workflows
```

These names are inspection leads from the source specification; new code paths must follow the verified checkout, not an invented directory hierarchy.

### 3.3 Baseline findings to verify

| Recorded concern | Required verification | Action if already fixed |
|---|---|---|
| G-DML: an UPDATE immediately after THEN was not recognized as a write | Reproduce with an isolated fixture; test INSERT, UPDATE, DELETE, and MERGE classification | Cite the fixing commit and retain a regression; do not reintroduce an alternate parser |
| Schema/package name collisions and qualified body resolution | Same-name packages in different schemas; qualified and unqualified calls; spec/body association | Reuse the correct resolver and verify evidence and ambiguity handling |
| Windows ProjectBusy/descriptor/timing failures | Repeated instrumented concurrent read/write tests and installer-path tests | Record evidence of stability; distinguish scheduling flakes from data-integrity defects |
| Legacy relationship certainty | Confirm the meaning and handling of LEGACY_RESOLVED | Preserve historical semantics; require explicit reanalysis for new facts |
| Large aggregate map concealing useful connections | Measure focal exploration on 100/500-Form fixtures | Keep aggregate views secondary even if performance improved |
| Experimental IR/adapters | Determine whether they are called by real product paths and have accepted contracts | Integrate the real implementation rather than create duplicate abstractions |
| Existing output sanitization | Probe identifiers derived from HOST, URLs, connection text, and source literals | Preserve fixes across graph, report, export, and AI paths |

### 3.4 Required baseline deliverable

Create `docs/design/formslang-3.0/baseline-audit.md` with commit-pinned evidence, a current architecture map in text, test commands actually discovered, defects reproduced or not reproduced, existing capabilities, and a reuse/change/remove inventory. Record unavailable Oracle environments explicitly.

The baseline must not contain real customer source, credentials, private invoices, or corporate identifiers. Use synthetic examples or authorized sanitized fixtures.

## 4. Domain vocabulary and non-negotiable invariants

### 4.1 Canonical terms

| Term | Meaning |
|---|---|
| Repository / project | The identity and correlated durable record of one modernization effort; "project" may remain the friendly UI term |
| Workspace | A local operational instance used to inspect or modify a repository |
| Source artifact | An authorized input file or representation with identity, type, exact content digest, and acquisition metadata |
| Source set | An immutable manifest identifying the exact source objects used for an analysis |
| Analysis | An immutable extraction result bound to source content, engine version, parser capabilities, and configuration |
| Fact | A statement extracted under a declared method, with provenance and certainty |
| Evidence | A reference to the source location, exact source object, extraction rule, and relevant coverage |
| Relationship | A typed connection between entities; certainty and target resolution are distinct |
| Decision | An explicit human-recorded modernization choice, with intent, rationale, provenance, and lifecycle |
| Mapping | A target-specific refinement of a decision, with required prerequisites and capability checks |
| Proposal | Unapproved input from AI, rules, or a person; never equivalent to an approved decision |
| Plan | A deterministic projection of selected facts, applicable decisions, target capabilities, and policy |
| Artifact | A generated or explicitly registered delivery object with a digest and traceability |
| Validation run | Evidence of a specific check against specific artifacts, sources, criteria, and environment |
| Checkpoint | An immutable manifest identifying a coherent repository state and its durable object references |
| Baseline | A named checkpoint used for comparison or a milestone; not a declaration that migration is complete |
| Report | A versioned query/aggregation/rendering result bound to a checkpoint, scope, and disclosure profile |
| Applicability | Whether a decision or result remains usable in a selected context; not the same as its historical approval state |
| Freshness | Relationship between captured state, current authorized source/workspace state, and current policy/tool context |

### 4.2 Invariants

**INV-01 — Immutable historical truth.** Published source sets, analyses, accepted events, checkpoints, and report data snapshots must not be rewritten in place. Corrections create new objects or events.

**INV-02 — Evidence with claims.** Every substantive extracted claim must identify evidence or a precise absence/uncertainty reason. Display and export must preserve that distinction.

**INV-03 — Separate axes.** OBSERVED versus INFERRED describes extraction certainty. RESOLVED versus UNRESOLVED/AMBIGUOUS describes target identification. APPROVED describes a human decision. PASSED describes a validation run. These states are not interchangeable.

**INV-04 — One domain implementation.** HTTP, CLI, Workbench, background jobs, and reports must not implement separate eligibility, matching, coverage, or decision rules.

**INV-05 — Explicit writes.** Opening a page, importing a file for preview, obtaining AI output, or rendering a report must not approve a decision or mutate legacy analysis facts.

**INV-06 — Revision binding.** Every query result and mutating operation must identify its source, analysis, decision, policy, and applicable artifact context; clients must not combine incompatible revisions into a single apparently coherent view.

**INV-07 — Unknown is not zero.** Missing data, missing permission, unsupported syntax, truncation, and no observed match must be distinguishable.

**INV-08 — Reproducibility has prerequisites.** Deterministic outputs require the same captured inputs, schemas, engine/adapter versions, policies, and selected parameters. Missing private objects or toolchains must produce an explicit limitation.

**INV-09 — No false authority.** A digest proves content identity/integrity under the selected algorithm, not a person's authorship or approval. A Git commit author, DSL reviewer string, or imported event must not grant authorization.

**INV-10 — No silent loss.** Upgrade, import, export, cleanup, or UI replacement must not silently discard decisions, annotations, artifacts, evidence, or unresolved work.

**INV-11 — Target independence.** Understanding and decision intent must not require an APEX target. Target-specific mappings become active only for a declared supported adapter.

**INV-12 — Bounded, honest visualization.** A limited graph is a view, not the entire repository. Its budgets and coverage must be visible. Layout changes are not domain changes.

**INV-13 — Privacy across projections.** Permission and disclosure rules apply equally to graphs, names, counts, search results, history, reports, errors, exports, and AI requests.

**INV-14 — Product evidence over labels.** Installed-build tests, actual usability sessions, and exact validation records are required before claims of release, parity, or readiness.

## 5. Repository architecture and authority

### 5.1 Selected architecture

Use a **local transactional repository coordinator with an immutable object store and canonical portable exports**.

The default preserves SQLite as the operational authority for accepted events, local revision fences, permissions, job state, object registration, and publication intents. Immutable object bytes hold source snapshots and durable domain outputs. Canonical exports make the same state inspectable, portable, and reviewable in Git.

Git is an optional transport and review mechanism for authorized files; it is not the database for running jobs and not an implicit decision-approval engine.

This is a selected design, not a license to maintain two divergent truths. A change to file-authoritative operation requires an ADR proving atomicity, conflict behavior, migration, and recovery before implementation.

### 5.2 Responsibility map

| Layer | Authority / responsibility | Must not do |
|---|---|---|
| SQLite coordinator | Accepted local events, revision fences, object catalog, access metadata, publication journal, current workspace references | Treat edited export files as trusted writes on open |
| Immutable object store | Verified bytes referenced by durable manifests | Mutate an existing content-addressed object |
| Canonical portable representation | Reviewable projection of recorded state plus sufficient authorized history and objects to reopen the declared export profile | Pretend missing source bodies or redacted records can be reconstructed |
| Git repository | Version selected portable files; provide normal Git history/branches/PRs outside FormsLang | Supply runtime authorization or transactional job semantics |
| Query indexes and caches | Accelerate immutable-snapshot queries | Become a second source of extracted facts or decisions |
| Workbench state | Selection, panels, zoom, filters, and presentation preferences | Change source certainty, relationship resolution, approval, or build eligibility |
| Report engine | Evaluate versioned metrics and render authorized repository projections | Parse raw source separately or invent a reporting-only dependency model |

### 5.3 Logical workspace layout

The following is a logical contract. Adapt physical placement to preserve the verified existing project format and installer behavior.

```text
modernization-project/
  formslang.repository.json        # portable repository identity/configuration, no secrets
  .formslang/
    repository.sqlite             # operational coordinator; excluded from Git
    objects/                      # immutable content-addressed objects
    staging/                      # incomplete object publication; never ordinary reader input
    cache/                        # disposable projections; permission-scoped
    runtime/                      # locks, transient job state, local logs
    local.json                    # local root bindings and machine preferences; no export
  exchange/                       # explicitly published, policy-controlled portable content
    repository.json
    checkpoints/
    events/
    decisions/
    manifests/
    objects/                      # only the authorized objects selected by the export profile
    disclosure.json
  exports/                        # explicit report or delivery packages, not an authority
  .gitignore
```

`exchange/` is illustrative; preserve compatible project roots and use one resolved path policy. Do not move a user's project into this layout merely by opening it.

**REP-01.** The repository MUST retain a durable identity independent of its absolute filesystem path.

**REP-02.** Operational databases, cache files, source-body stores, credentials, and local bindings MUST be excluded from normal Git publication. Export selection is explicit and policy-controlled.

**REP-03.** Existing tracked sensitive files must be detected and reported when preparing publication. Adding a `.gitignore` entry does not untrack an already tracked file. [T4] Do not rewrite Git history automatically.

**REP-04.** The repository MUST permit both a fully self-contained authorized export and a restricted metadata/review export. The latter must report which operations cannot be reproduced without excluded objects.

**REP-05.** Immutable durable facts and evidence are repository contents even when indexed in a cache. Deleting caches must not delete the only copy of those facts.

**REP-06.** Private annotations and rejected/expired proposals need not be disclosed to every recipient. Their inclusion, exclusion, retention, and availability must be stated by the export profile without exposing unauthorized counts or identities.

### 5.4 Selected alternatives and tradeoffs

| Alternative | Benefits | Reason it is not the default |
|---|---|---|
| SQLite plus immutable objects and explicit export | Preserves transactional foundations, supports offline operation, enables portable review | Requires a tested publication/recovery protocol and a clear portability contract |
| Files/Git as live operational authority | Directly reviewable project edits | Requires a different locking, authorization, recovery, and job model; unsafe as an unexamined rewrite |
| Remote hosted repository with centralized services | Potential shared collaboration | Introduces infrastructure, availability, identity, and security obligations outside the local-first release |

Do not choose a remote service to avoid specifying local crash consistency. Do not retain SQLite while secretly making Git checkout overwrite it.

## 6. Immutable objects, identities, and canonical formats

### 6.1 Durable object families

| Object family | Minimum content | Typical parents / references |
|---|---|---|
| Source object | Exact bytes or a protected external-object reference, type, size, acquisition metadata | Acquisition/conversion record |
| Source-set manifest | Logical source roots, relative locators, raw digests, declared availability | Source objects |
| Analysis object | Engine identity, schema, capabilities, facts, relationships, uncertainty, extraction diagnostics | Source set |
| Evidence object/index | Source digest, locator, attribute/span information, extraction rule and version | Analysis and source objects |
| Decision event | Immutable event identity, subject, intent, rationale, actor provenance, expected base, approval metadata | Source/analysis, earlier decision events, policy |
| Decision checkpoint | Canonical `.flm` plus reference to history needed to explain its state | Decision event frontier, analysis |
| Plan | Selected scope, dependency closure, eligible units, blockers, decisions, target capability manifest | Analysis, decisions, policy |
| Artifact manifest | Output objects, hashes, emission status, source-to-target mappings | Plan, adapter/toolchain identity |
| Validation record | Kind, artifact hashes, case/scope, environment, result, evidence, actor/runner | Artifacts, criteria, current policy |
| Report dataset/manifest | Definitions, scope, checkpoint, facts and aggregates, completeness, disclosure | Selected checkpoint, metric definitions, rendered files |
| Repository checkpoint | Coherent root references and provenance | Earlier checkpoints plus referenced durable objects |

Objects may be physically combined where existing schemas require it. Their semantic identities and references must remain explicit and testable.

### 6.2 Identity rules

**OBJ-01.** Use a versioned digest scheme, initially SHA-256 for FormsLang object identities. Domain-separate object kind and schema version from canonical bytes. Do not assume a Git object ID and a FormsLang object ID are interchangeable.

**OBJ-02.** Source digests MUST refer to exact original bytes. Canonical analysis or DSL encoding must not rewrite the source being evidenced.

**OBJ-03.** A domain object ID is distinct from a local event sequence, job ID, display label, and source entity locator. Event IDs are assigned once and retained across export/import. Exporting must not regenerate them.

**OBJ-04.** Monotonic revision counters are local to an identified ledger/workspace origin. Two clones both reaching decision revision 17 are not necessarily equivalent. Portable comparison uses content/event identities and ancestry, not numeric equality alone.

**OBJ-05.** Distinguish immutable analysis `entity_id` from a versioned `logical_locator` used to propose correspondence across analyses. A renamed or similarly spelled entity must not inherit approval automatically.

**OBJ-06.** Digests and opaque identifiers are not anonymization. Treat exported identifiers as potentially sensitive and apply the same disclosure policy used for other metadata.

### 6.3 Canonical serialization

Canonical JSON schemas MUST define field types, required fields, nullable states, enum values, ordering of meaningful arrays, ordering of set-like arrays, and treatment of optional fields. Reject duplicate object keys. Use UTF-8 and LF for generated textual objects; preserve the exact semantics of opaque source identifiers and quoted database identifiers.

For new human-authored labels and rationale, the parser may require normalized Unicode and provide an explicit diagnostic. Do not normalize raw source bytes or silently change the code points of a source-qualified identifier to satisfy a presentation convention.

Integers and exact decimal encodings are preferred for portable counts and ratios. NaN, infinity, platform-dependent floating-point rendering, transient filesystem paths, request timestamps, and random export-time IDs are prohibited in deterministic core objects.

A recommended digest input is:

```text
UTF8("formslang-object") + NUL
+ UTF8(object_kind) + NUL
+ UTF8(schema_version) + NUL
+ canonical_payload_bytes
```

The schema prohibits NUL inside kind/schema identifiers. The hashed payload excludes its own `object_id`, detached signatures, and nonsemantic transport metadata. The format and byte examples must be golden-tested before adoption.

### 6.4 Determinism versus historical identity

Serializing the same accepted event history produces the same event/checkpoint content. Recorded event timestamps and actor provenance do not change on export. Two different histories can legitimately describe the same current decision state; a semantic-state digest may match while their history/checkpoint digests differ.

A build artifact must be deterministic for its declared build input. A new validation execution may legitimately create a different run record with a different timestamp and observation. Never erase that distinction to obtain artificially matching hashes.

### 6.5 Integrity is not a signature

The original phrase about a checkpoint being "signed by hashes" is refined here: a checkpoint is **content-addressed and integrity-verifiable**. It is **cryptographically signed** only when an actual supported signature scheme, trusted key, and verification result exist.

Local imported history may be inspectable yet have unverified author provenance. The UI and reports must show that status, and active approvals must obey the receiving workspace's trust policy.

## 7. Checkpoints, history, Git exchange, and restoration

### 7.1 Whole-project checkpoint contract

**HIST-01.** A repository checkpoint MUST identify a coherent state across all applicable durable categories. Exporting only `.flm` is a decision export, not a complete repository checkpoint.

The checkpoint schema, initially `formslang-checkpoint/1`, must include the following fields or equivalent typed references:

| Field | Contract |
|---|---|
| `repository_id` | Stable logical repository identity |
| `schema_version` | Checkpoint schema identifier |
| `parent_checkpoint_refs` | Immutable parent references; no inferred ancestry from local sequence numbers |
| `source_set_ref` | Exact captured source manifest, or explicit absence before intake |
| `analysis_ref` | Exact published analysis and its engine/capability identity |
| `decision_snapshot_ref` | Canonical decision state, bound to its accepted event frontier |
| `event_frontier_ref` | Durable history necessary to explain included state; export coverage declared separately |
| `policy_ref` | Versioned domain/build policy used for the state; not exported credentials or an authorization grant |
| `capability_refs` | Relevant parser/adapter capability definitions |
| `annotation_set_ref` | Durable project questions/notes available in the checkpoint's declared visibility scope |
| `plan_set_ref` | Recorded plans and their immutable input bindings |
| `artifact_set_ref` | Generated or registered output manifests |
| `validation_set_ref` | Specific validation and acceptance records |
| `report_set_ref` | Reports already created from earlier or otherwise acyclic input contexts |
| `history_metadata` | Stable creation event, provenance, and optional label/rationale |

Each referenced set is deterministic and versioned; an empty set is different from an unavailable/redacted set. The implementation must validate referential closure for the chosen export profile.

A named checkpoint is an explicit capture/label operation. Accepted changes remain durable in their events and immutable objects before a user creates a named baseline. A query against `current` captures one consistent input vector; it must not write a new checkpoint merely because a user opened a page. An explicit build/report/export operation may publish a checkpoint as part of its declared write contract.

### 7.2 Avoid circular provenance

A report produced from checkpoint C cannot be added to C while keeping C immutable and preserving a valid digest. Create report R bound to C, then publish a subsequent checkpoint C2 that references R. The same principle applies to artifacts and validations created from an earlier checkpoint.

The UI must distinguish **input checkpoint** from **publication checkpoint**. Do not recalculate a checkpoint recursively until its self-reference appears to work.

### 7.3 Checkpoint operations

**HIST-02.** Required domain operations are `status`, `log`, `show`, `diff`, `checkpoint create/list/show`, `baseline create/list/show`, `verify`, `export`, `import preview/apply`, and recovery/restore operations.

**HIST-03.** `status` must separately report working-source changes, unpublished analyses, decision changes, stale decisions, unresolved dependencies, blocked plans, validation applicability, publication pending/failure, and object availability. It must not reduce all these conditions to a misleading clean/dirty boolean.

**HIST-04.** `log` must support project, subject, decision, artifact, validation, and report scope. It must show recorded action, origin/actor trust, rationale when available, and the affected context. It is domain history—not a renamed Git log.

**HIST-05.** `show` must inspect a checkpoint or object without changing the workspace's active state. Historical views are visibly read-only.

**HIST-06.** A baseline is an immutable named reference to a checkpoint. Names must be validated independently of filesystem paths. Moving an existing label is not permitted silently; create a replacement label with recorded rationale or use an explicitly audited administrative operation.

**HIST-07.** Restoring an older decision as the current choice must create a new event referencing the old decision and the current base. It must not erase intervening history or decrease local revision counters.

### 7.4 Diff dimensions

| Diff | Question answered | Required exclusions / distinctions |
|---|---|---|
| Source diff | Which captured inputs changed? | Separate exact byte changes, renamed candidates, missing files, and availability/disclosure changes |
| Analysis diff | Which extracted entities or relationships changed? | Separate source changes from engine/schema/capability changes; incomparable is not unchanged |
| Decision diff | Which human choices changed, and why? | Preserve old and new rationale, actor provenance, supersession, and applicability |
| Mapping/plan diff | Which target instructions or eligibility results changed? | Distinguish changed policy/capability from changed human intent |
| Artifact diff | Which generated outputs changed? | Distinguish raw file diff from structural target diff and omitted scope |
| Validation diff | Which checks were added, invalidated, passed, failed, or not executed? | A new artifact does not inherit the old artifact's passing run |
| Report diff | Which measured facts changed between comparable report inputs? | Denominator or metric-definition changes must be shown explicitly |
| Impact view | Which decisions, outputs, and tests may be affected? | Show observed paths and analysis limits; do not claim actual runtime impact |

A textual Git merge without file conflicts may still contain a domain conflict. FormsLang must validate domain consistency independently of Git's textual merge process. Git integration uses the real Git tool's semantics rather than an imitation. [T5]

### 7.5 Portable export profiles

| Profile | Intended recipient | Required characteristics |
|---|---|---|
| `full-private` | Authorized engineer transferring or backing up a complete project | Includes the selected durable history and all authorized objects needed to reopen the specified scope; excludes credentials, sessions, runtime locks, caches, and unselected private data |
| `review` | Reviewer inspecting modernization choices | Includes canonical decisions, necessary permitted evidence metadata, manifests, and declared historical coverage; source bodies only by explicit selection |
| `report` | Stakeholder receiving an assessment | Includes report data/renderings, permitted evidence appendix, definitions, disclosure statement, and integrity manifest; not automatically a writable project |

**HIST-08.** Export preview must enumerate included categories, visibility rules, known reproducibility gaps, selected checkpoint, estimated size, and sensitive-content warnings within the caller's permissions.

**HIST-09.** Exported source references must use logical roots and content identities, not disclose local absolute paths. External object locations must be allowlisted, non-secret references; no bearer tokens or credentialed URLs.

**HIST-10.** Full portability must be tested by reopening a package in a clean authorized workspace without the original SQLite file and without the original machine paths. A metadata-only package must open with explicit unavailable-object states rather than fail opaquely or fabricate objects.

**HIST-11.** An export can preserve a selected historical frontier rather than every event ever created, but the omission must be declared. A package advertised as complete must contain all durable history and objects promised by that profile and scope.

### 7.6 Import and trust boundaries

Import is a domain operation, not a filesystem overwrite:

1. Parse the package and enforce size/path/schema limits in staging.
2. Verify object identities and the declared manifest closure.
3. Determine repository identity, ancestry, source availability, and origin trust.
4. Produce a semantic change/conflict report against the selected local base.
5. Show which claimed approvals are trusted, unverified, or inapplicable under local policy.
6. Require explicit apply authorization and revision fences.
7. Register accepted imported objects and append local import/decision events transactionally.
8. Publish a new local checkpoint only through the normal publication protocol.

**HIST-12.** Import preview must be side-effect free with respect to accepted project state. Staged temporary files must be isolated and removable.

**HIST-13.** Applying the same package twice must be idempotent. Reused foreign event IDs with different content are an integrity/conflict error, not an update.

**HIST-14.** Imported actor names and `state "approved"` do not create active local approvals. Unverified history remains inspectable as imported history. Current generation requires approval provenance acceptable to the receiving policy, or an explicit new local approval.

**HIST-15.** Domain policy carried by a package may be inspected, but it must not weaken the receiving workspace's security or execution policy.

### 7.7 Git branches, working trees, and safe synchronization

Native branch management is not required in 3.0. Users can version permitted exchange files in normal Git branches or worktrees and use FormsLang's explicit semantic import workflow.

The workspace must detect when the portable files it previously imported have changed because of checkout, reset, merge, or manual edit. It must display **external changes awaiting reconciliation**, not silently load a stale SQLite state and present it as the checked-out branch.

Detection must not rely solely on a file watcher. Verify the relevant manifest and decision digests before operations that depend on synchronized exchange state. A Git worktree receives its own operational workspace binding; unrelated worktrees must not write the same live SQLite file.

Conflicting alternatives must remain visible until explicitly resolved. A conflict-free import can apply a deterministic non-overlapping change only if the base, source bindings, policy, and permissions still validate. Same-subject conflicting choices must not use last-writer-wins.

### 7.8 Backup, restore, and retention

**HIST-16.** Back up SQLite using a supported consistent backup procedure, and include referenced immutable objects according to a captured manifest. A live raw-file copy must not be assumed to include a consistent transactional state. SQLite provides an online backup API for this purpose. [T3]

**HIST-17.** Restore defaults to a new destination and verifies integrity before opening. In-place disaster recovery requires a separately documented backup and explicit destructive-operation authorization.

**HIST-18.** Garbage collection must preserve every object reachable from retained checkpoints, accepted events, retained reports, active jobs, and explicit retention pins. Dry-run must show the deletion set. Retention changes are not an excuse to erase decision history silently.

**HIST-19.** Source deletion requests and privacy obligations may make historical evidence unavailable. Keep a non-sensitive tombstone or availability record where permitted; do not claim deleted evidence is still inspectable. Never promise that deleting a local object removes copies already exported or committed elsewhere.

## 8. Transactions, concurrency, failure recovery, and jobs

### 8.1 Failure model

Design for process termination, power interruption within supported durability assumptions, disk full, file permission errors, antivirus/file-lock interference, corrupt/missing objects, stale clients, concurrent CLI/UI operations, cancellation, and failed export publication.

SQLite atomicity applies to its database transactions under its documented assumptions; it does not automatically turn unrelated filesystem publication into one atomic database transaction. The repository publication protocol below is an application requirement. [T1]

### 8.2 Selected write protocol

Publication targets internal canonical objects/manifests by default. Writing an authorized portable view into `exchange/` requires an explicit export operation or a previously approved automatic-publication profile. A normal decision save must not newly disclose private source or put it into Git. Track internal publication separately from optional exchange synchronization; an export that was never requested is `not_requested`, not a failed save. Nothing in this protocol commits or pushes Git automatically.

**TX-01.** Every durable mutation must execute through one domain transaction coordinator with authorization, revision checks, idempotency checks, and a single documented project-write discipline.

Use the following publication order, refined and proven in the storage ADR:

1. Resolve an immutable input context and verify permission before expensive work.
2. Build candidate immutable object bytes outside a long-held database write transaction.
3. Write staged files on the intended volume; validate digests and schemas; flush according to the supported platform durability policy.
4. Promote immutable object bytes to internal content-addressed locations. Existing matching objects may be reused; different bytes at the same identity are an integrity failure.
5. Acquire the short repository write transaction; recheck authorization, expected revisions, input bindings, and idempotency key.
6. Append events, register verified objects, update local revision fences, and record a publication intent containing the exact canonical export bytes or sufficient immutable references to reconstruct them.
7. Commit the database transaction.
8. Publish the required canonical checkpoint files and, only when requested/authorized, the exchange files through staged, verified replacement. Publish each final root manifest last so normal readers do not follow an incomplete publication.
9. Mark the publication intent complete in a subsequent short transaction. Only then report the portable checkpoint as synchronized.

A crash before the database commit may leave unreferenced immutable objects. They are harmless orphans and can be reclaimed later; they must not become visible accepted history. A crash after the commit must not lose an accepted decision just because exchange-file publication failed.

### 8.3 Publication states and client behavior

Use explicit states such as `PREPARING`, `COMMITTED_PENDING_PUBLICATION`, `PUBLISHED`, and `PUBLICATION_FAILED`. Their exact names may follow existing conventions, but the semantic distinction is mandatory.

**TX-02.** When the database commit succeeds but portable publication fails, return the accepted event/revision and the pending/failed publication status. Do not claim the whole operation rolled back, and do not tell the user the Git-facing files are synchronized.

**TX-03.** Recovery must be idempotent. Reconstruct files from accepted state and verified immutable objects; never import an arbitrary partially written file as the new authority.

**TX-04.** A missing object referenced by accepted state must quarantine the affected operation and expose an integrity error. Do not automatically regenerate it with a newer engine and pretend it is the original object.

### 8.4 Concurrency and revision fences

Mutation requests must carry the expected repository context, including the relevant analysis and decision state. The service compares the request to current accepted state immediately before commit.

A stale request returns a structured conflict containing permitted current identifiers and a refresh/review action. Do not silently overwrite, auto-approve, or merge conflicting decisions.

**TX-05.** A bulk decision operation is all-or-nothing for its declared batch. Validate all rows, permissions, revision bindings, and confirmations before committing any row. Bound batch size and test at least 5,000 findings without treating a UI pagination limit as a data limit.

**TX-06.** Request IDs are scoped to repository, actor/trust context, operation, and payload digest. Reuse with the same payload returns the recorded result; reuse with a different payload is rejected.

**TX-07.** Avoid full-repository locks during parsing, report rendering, AI calls, or external Oracle execution. Bind work to immutable inputs and acquire a short write transaction only for publication.

### 8.5 SQLite and supported storage locations

Preserve the verified SQLite configuration unless a tested change is required. Do not disable durability or weaken transaction settings to make concurrency tests pass.

If WAL is used, account for its extra files, locking model, and documented same-host/shared-memory limitations. Do not support a shared active database on a network filesystem as the default team solution. [T2]

The active operational repository should reside on a supported local filesystem. Detect or document unsupported network/synchronization-folder operation. Safe export packages can be copied elsewhere after publication; copying a live workspace is not the recommended synchronization mechanism.

### 8.6 Job lifecycle

| State | Meaning | Required behavior |
|---|---|---|
| Queued | Accepted request has not begun computation | Can be cancelled; expose input context |
| Running | Work is in progress against pinned inputs | Structured progress; bounded resources; no fabricated percentage |
| Cancel requested | Cancellation has been requested | Stop at a safe boundary and distinguish committed from uncommitted outputs |
| Succeeded | Declared job result and publication completed | Expose output references and exact scope |
| Partial | Allowed subset completed under an explicitly partial job contract | Enumerate completed, omitted, failed, and unknown scope; not used for partial bulk decision commits |
| Failed | No successful result for the promised job contract | Structured error, preserved diagnostic context, safe retry guidance |
| Cancelled | Work ended at a safe cancellation boundary | Preserve any accepted state and explain what, if anything, was published |
| Recovery required | Accepted state exists but final publication/reconciliation is incomplete | Recover explicitly/idempotently; never show success with missing outputs |

**TX-08.** Analysis, generation, validation, and reporting jobs must retain their input-context references. A job finishing after a user navigates to another project must not replace the visible state of that other project.

**TX-09.** In an authenticated mode, recheck the relevant execution/publication permission before exposing or publishing job outputs. Revoked access must not be bypassed by a previously queued job.

## 9. Source intake, facts, evidence, and analysis

### 9.1 Intake before target selection

A new project opens with an understandable intake action. It must not require choosing APEX, entering database credentials, configuring AI, or authoring a DSL file before exploration.

**SRC-01.** Intake must accept the representations actually supported by the verified engine, classify other files honestly, and display supported, unsupported, partially supported, unreadable, duplicate, and missing inputs.

**SRC-02.** Selecting a source folder requires an authorized root and explicit recursion/exclusion behavior. The preview must show what will be inspected and what will be skipped.

**SRC-03.** A source manifest must preserve raw content digests, logical root identity, relative locator, size/type, and representation/conversion provenance. Duplicate content must not erase separate logical source identities.

**SRC-04.** Changing, deleting, or moving working files must not change an existing source snapshot. Reanalysis creates a new captured source set or reuses an identical verified set.

### 9.2 FMB, PLL, and external conversion tooling

An FMB/PLL can be represented in inventory without claiming its semantics have been parsed. When a supported textual representation is required, show clear conversion guidance.

An integrated Forms2XML operation, if provided, requires a user-authorized executable/tool installation, an argument-array invocation rather than arbitrary shell text, a declared output directory, resource limits, and a recorded tool version. It must not auto-install proprietary tooling or run a binary simply because a source file requests it.

The conversion output must reference the original binary digest and the conversion run. Failure to convert leaves the binary recorded with an explicit unsupported/unavailable semantic state.

### 9.3 Evidence-backed extraction

Every extracted entity and relation must bind to `analysis_revision`, source object identity, extraction rule/capability version, and evidence references.

Evidence should include exact source offsets or stable attribute locators where available. For structured XML, an attribute's presence and provenance are important: a parser default is not equivalent to a value explicitly present in the XML.

**SRC-05.** Do not reopen source files on a graph click to fill missing facts silently. New extraction requires a new explicit analysis revision.

**SRC-06.** A missing body, unsupported construct, unresolved reference, or parse failure must become a visible boundary with reason. No target generator or report renderer may reinterpret the raw code to invent the missing fact.

**SRC-07.** Source code and user annotations are data. Embedded instructions in comments, XML, or SQL do not authorize tools, network access, filesystem writes, or approval.

### 9.4 Forms hierarchy and placement

Represent logical ownership and visual placement separately:

```text
Logical structure: Form → Block → Item
Visual placement:  Form → Window → Canvas → Tab → Item
Code ownership:    Form / Block / Item → Trigger or Program Unit
```

These are navigable views over shared entity identities. An item shown in both trees is one domain entity, not two separately counted objects.

**SRC-08.** Persist window/canvas/tab/item relationships only where declarations and evidence support them. Conflicting `Canvas.window_name` and `Window.primary_canvas` evidence must be shown as a conflict.

**SRC-09.** A canvas explicitly declared `Visible=false` is a static declaration, not proof that it was never displayed at runtime. Missing provenance for a default `Visible=true` or `CanvasType=Content` must be labeled unavailable/unverifiable for that revision.

**SRC-10.** A canvas without a resolved window, an item without a canvas, or a tab with unresolved provenance remains discoverable in an unplaced/unresolved group. Do not drop it from counts or force an inferred placement.

### 9.5 SQL, PL/SQL, and database relationships

Support extracted queries, cursor definitions, program units, package specifications/bodies, tables, views, and relationships according to the verified parser capability matrix.

**SRC-11.** Database object identity must account for schema, quoted identifiers, object kind, package membership, and overload/signature where available. Same-name objects in different schemas are distinct.

**SRC-12.** Unqualified calls with multiple valid candidates remain ambiguous. Do not use the nearest filename, display label, or AI preference as a silent resolver.

**SRC-13.** READS, WRITES, CALLS, OPENS_FORM, EXECUTES_QUERY, COMPOSES, and similar categories must preserve their specific meaning. Composition is not automatically a data dependency; a query declaration does not prove returned rows or transaction timing.

**SRC-14.** Fix and regression-test DML extraction gaps without degrading other statements. Dynamic SQL, synonyms, external calls, and unresolved package bodies must retain explicit coverage limits.

### 9.6 Analysis publication and legacy behavior

Publish an immutable analysis only after source snapshot integrity, parser output schemas, and coverage diagnostics are verified. If analysis is partial, publish its explicitly partial state rather than a success label that implies full coverage.

Legacy snapshots remain inspectable under their original schema/semantics. New extraction capability is obtained through explicit reanalysis. Legacy relationship resolution must not be upgraded to confirmed current resolution by changing a UI label.

## 10. Graph, search, dependency paths, and change impact

### 10.1 Reuse the ecosystem contract

Reuse the existing `ecosystem/1` contract where it remains valid. A breaking semantic change requires a new schema version and compatibility handling. Do not create a parallel graph model solely for the new frontend.

The graph is a revision-bound projection of captured domain facts and human-decision overlays. A group node created to simplify display must be labeled as a grouping, not represented as an extracted legacy object.

### 10.2 Relationship and evidence semantics

**GRAPH-01.** Every edge response must include source/target identity, direction, family/type, original raw type where applicable, certainty, resolution, evidence references, analysis identity, and relevant omission/visibility conditions.

**GRAPH-02.** The initial focus must show a meaningful connected neighborhood of a selected Form or component. Do not use a truncated whole-estate map that happens to return isolated nodes as the entry experience.

**GRAPH-03.** Provide equivalent list/table navigation with the same identity, evidence, filters, and context as the graphical view.

**GRAPH-04.** Separate confirmed relationships, inferred relationships, unresolved references, and proposed/decided modernization overlays visually and textually. Color alone is insufficient.

### 10.3 Initial budgets

Retain the source specification's initial focal budget of **80 nodes / 160 edges** as the candidate default. A path request starts at depth 4, has a hard initial maximum depth of 6, and returns at most 3 ordered candidate paths. These are query limits, not a promise that the rest of the repository has no relationships.

Every bounded response must expose shown counts, permitted known totals where available, truncation reason, continuation cursor, and unresolved coverage. Add payload-byte, CPU/time, and cancellation budgets. Limits must be configurable through a validated policy, not arbitrary client values.

Global repository totals must never be calculated by counting the currently rendered graph. Full-scope reports use paginated snapshot queries over the same domain objects.

### 10.4 Search and navigation

Search must cover permitted Forms, entities, database objects, decisions, artifacts, validation cases, reports, and known unresolved references. Match by labels and permitted structured metadata; raw source-body search requires source-read permission and explicit scope.

Results must display kind, qualified context, revision/checkpoint, certainty/applicability, and why the result matched. Same-name objects must be distinguishable without opening each result.

A focus transition preserves breadcrumb/history and allows Back to return to the exact prior object and revision. Expanding a graph group must not reset the user's selected evidence or decision draft.

### 10.5 Path search

Search immutable adjacency indexes with stable ordering and explicit relationship-family filters. By default, composition/placement edges do not count as behavioral/data dependencies. Offer a separate structural route when the user is exploring containment.

Cycles must be detected and shown without infinite traversal. Budget exhaustion returns a partial answer and a reason; it is not "no path exists."

**GRAPH-05.** A path is a static relationship path. Never narrate it as an actual order in which an operator clicked screens or the database executed statements.

### 10.6 Cross-revision identity and correspondence

Correspondence results must distinguish `EXACT`, `MOVED_CANDIDATE`, `AMBIGUOUS`, `REMOVED`, `NEW`, and `NOT_COMPARABLE` where applicable.

A locator includes logical root, normalized relative path rules, entity kind, owner chain, qualified name/schema, and a signature discriminator where needed. Path comparison rules must be tested on Windows and Linux, including case-sensitive Oracle identifiers and case-insensitive filesystem collisions.

**GRAPH-06.** Exact matching can support a reviewable reuse candidate. It does not authorize automatic rebinding of a previously approved decision to a changed analysis. Identical immutable analysis content may retain the same binding; changed content requires the explicit applicability/revalidation rules.

### 10.7 Impact calculation

Impact combines changed source/entity/evidence references, dependent decisions, plans, artifact mappings, and validation applicability. It must identify the observed dependency path and the reason each item is considered potentially affected.

Return separate categories for direct impact, transitive potential impact, unknown boundaries, stale evidence, and non-comparable changes. Do not convert an unresolved call into a confirmed downstream impact list.

### 10.8 Indexes and asynchronous safety

Indexes are disposable and read-only after construction. Keys include repository, immutable analysis, decision projection when relevant, visibility scope, and authorization epoch. Do not perform a full deep copy or source freshness scan on every click.

Invalidate or rebuild when the relevant immutable input changes. Permission changes must invalidate visibility-sensitive caches even if source content did not change.

The client must discard late responses whose project, actor/session, checkpoint, focus, or request sequence no longer matches. A response for Project A must never populate Project B after a fast navigation change.

## 11. FormsLang Decision Language

### 11.1 Language purpose and positioning

The proposed language is **FormsLang Decision Language**, file extension `.flm`, initial schema `formslang-decisions/1`.

It is the human-reviewable representation of modernization choices and their source bindings. It is not the full repository, not the extracted source code, not the mutable database, and not a replacement for APEXlang.

**DSL-01.** The language MUST be small, declarative, deterministic, safe to parse, and suitable for code review. A user must be able to understand what decision changed without interpreting an arbitrary program.

**DSL-02.** Interface forms, CLI operations, and file import MUST validate through the same domain validator. No frontend-only fields may bypass domain rules.

**DSL-03.** Do not support code execution, macros, interpolation, environment-variable expansion, filesystem includes, network imports, embedded scripts, or arbitrary SQL fragments in version 1.

### 11.2 Record classes

| Class | Purpose | Inclusion rule |
|---|---|---|
| Source binding | Links the document to repository, analysis, and origin context | Required header metadata |
| Decision | Human-created modernization intent for one subject | Recorded explicitly; may be pending or approved under domain rules |
| Mapping | Target-specific refinement of a decision | Only a known target mapping schema with valid prerequisites |
| Supersession | Points to an earlier decision/event being replaced | New event; the old record remains in history |
| Proposal | Unapproved suggestion | Stored separately; never inserted into the approved decision set by a parser or AI response |

The canonical `.flm` represents a selected decision snapshot. The associated event objects and repository checkpoint preserve its complete declared history. Do not force every historical superseded record into the current decision file merely to avoid implementing event portability.

### 11.3 Grammar contract

The following grammar is normative at the structural level. Token definitions, parser diagnostics, and mapping schemas must be frozen in the language ADR before release.

```ebnf
document       = header, { decision } ;
header         = "formslang-decisions", integer,
                 "project", string,
                 "origin", string,
                 "analysis", string,
                 "engine", string,
                 "decision_revision", integer ;
decision       = "decision", string, "{", { field | mapping }, "}" ;
field          = field_name, value ;
mapping        = "map", string, "{", { map_field_name, value }, "}" ;
value          = string | integer | boolean | null | array ;
array          = "[", [ value, { ",", value } ], "]" ;
string         = JSON_STRING ;
integer        = NON_NEGATIVE_DECIMAL_INTEGER ;
boolean        = "true" | "false" ;
null           = "null" ;
```

Whitespace separates tokens and is otherwise insignificant outside strings. Strings follow JSON escaping rules. Comments are not part of version 1; use rationale and annotations rather than a lossy comment-preservation mechanism. Duplicate fields, duplicate decision IDs, unknown fields, nested mappings, unknown mapping kinds, and major schema versions not understood by the parser are errors.

`field_name` and `map_field_name` are closed sets selected by the schema; they are not arbitrary identifiers. Arrays are bounded and field-specific; accepting an array syntactically does not make it valid for every field. At most one target mapping block is permitted per decision in version 1. Multiple independent target choices require separately scoped decisions with explicit compatibility rules.

### 11.4 Header and decision fields

| Field | Required? | Semantics |
|---|---|---|
| Header `project` | Yes | Stable repository identity |
| Header `origin` | Yes | Ledger/workspace origin for the local revision counter; not an authorization claim |
| Header `analysis` | Yes | Exact immutable analysis identity |
| Header `engine` | Yes | Engine identity associated with that analysis |
| Header `decision_revision` | Yes | Origin-local sequence/fence for the exported state |
| `subject` | Yes | One exact entity or approved scope identity within the declared context |
| `evidence` | Yes | Evidence reference list; empty only for a justified pending/investigation record, never for an evidence-dependent approved mapping |
| `intent` | Yes | One supported intent |
| `state` | Yes | Snapshot lifecycle state; import does not trust it as authorization |
| `rationale` | Yes | Human-readable reason; explicit why, not a copied generic approval message |
| `target` | For target mappings | Supported target/capability namespace |
| `map` block | When mapping is present | Typed target-specific fields |
| `supersedes` | When replacing a decision | Earlier immutable decision/event reference |
| `reviewer` | Only for recorded approval metadata | Display provenance from the accepted event, not client-granted identity |
| `policy_revision` | For approvals requiring policy binding | Policy identity used by the recorded approval |
| `validation_refs` | Optional | Related records; references do not turn a validation into a global pass |

Version 1 approval applicability, capability checks, and preconditions are determined by the domain service and typed mapping schema. Do not accept arbitrary expressions in a field called `preconditions`. Additional portable fields require a schema revision and compatibility tests.

The scalar decision fields in this table are strings; `evidence` and `validation_refs` are arrays of strings. The `apex.form` mapping requires a nonempty table string and a nonempty, duplicate-free ordered key-column string array. Header revisions are bounded nonnegative integers. Version 1 does not use arbitrary nested arrays, booleans, or null for these fields: a value may parse lexically yet fail its field schema. Optional fields are omitted rather than encoded as a misleading null. A supported future mapping schema can introduce other explicitly typed values without opening arbitrary object execution.

Initial parser safety defaults are 8 MiB per input document, 10,000 decision records, 64 KiB per decoded string, 10,000 items per array, and four array nesting levels at the tokenizer/parser boundary; field schemas can impose stricter limits. Larger documented limits require a resource test and a configuration/ADR change. Valid syntax alone never bypasses per-field restrictions or semantic binding.

### 11.5 Canonical example

This example illustrates the complete syntax shape. Identifiers and digests are synthetic examples; semantic binding requires the matching test fixture, not a real customer repository.

```text
formslang-decisions 1
project "repo-demo-orders"
origin "origin-demo-local"
analysis "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
engine "engine-demo-1"
decision_revision 17

decision "dec-0042" {
  subject "block:ORDERS.HEADER"
  evidence ["ev-142", "ev-143"]
  intent "convert"
  target "oracle-apex/26.1"
  map "apex.form" {
    table "ERP.ORDERS"
    key ["ORDER_ID"]
  }
  state "approved"
  rationale "The table and key were verified; price validation remains a separate scoped decision."
  reviewer "actor-demo-reviewer"
  policy_revision "policy-demo-1"
}

decision "dec-0043" {
  subject "trigger:ORDERS.HEADER.WHEN-VALIDATE-ITEM.PRICE"
  evidence ["ev-151"]
  intent "investigate"
  state "pending"
  rationale "The dynamic call target is not resolved in the supplied sources."
}
```

The candidate APEX version label comes from the original design. The implementation must verify actual adapter/toolchain compatibility before presenting that version as supported. A syntax example is not a compatibility claim.

### 11.6 Intents and safety

| Intent | Meaning | Generation consequence |
|---|---|---|
| `preserve` | Keep existing responsibility/behavior through an explicitly supported strategy | Requires a supported implementation strategy; not permission to copy arbitrary code |
| `convert` | Map to an eligible target representation | Requires mapping prerequisites and approval |
| `redesign` | Replace the structure or interaction deliberately | Requires a recorded design and supported implementation path; not automatic generation |
| `replace_native` | Replace legacy behavior with a target-native capability | Requires rationale, compatibility evidence, and elevated risk confirmation where appropriate |
| `retire` | Intentionally remove a responsibility from the target scope | Requires rationale and explicit confirmation; never deletes source or production objects |
| `investigate` | Leave unresolved work visible | Blocks dependent generation unless the selected unit can be safely isolated |
| `defer` | Exclude work from the current delivery scope deliberately | Remains visible in gaps and dependency-closure checks |

### 11.7 Canonical serializer and parser diagnostics

**DSL-04.** The serializer must use a fixed header order, fixed known-field order, deterministic decision ordering by immutable identity, deterministic set-like evidence ordering, consistent indentation, JSON string escaping, UTF-8, and LF.

**DSL-05.** Preserve order where it is semantic, including composite key column order. Sorting every array for determinism is incorrect.

**DSL-06.** Parser diagnostics must include line, column/span, code, expected shape, and an actionable message. They must not echo unbounded source text or secrets.

**DSL-07.** Enforce limits for file bytes, records, string length, nesting, arrays, and total referenced entities. Test malicious escape sequences, deeply nested arrays, huge numbers, duplicated IDs, and unknown versions.

**DSL-08.** Round-trip tests must prove `parse(serialize(model))` preserves the model, and repeated serialization of the same accepted snapshot produces identical bytes. A formatting operation must not approve, rebind, or mutate domain state.

### 11.8 Language evolution and usability gate

Before freezing version 1, complete two real code-review exercises over synthetic or authorized decision changes: one straightforward mapping change and one conflict/stale-evidence case. Record whether a reviewer can understand the subject, evidence, rationale, target, and approval implications from the diff.

Do not expand the language because the backend contains a field. Prefer referencing durable objects over embedding large analysis payloads.

## 12. Decision lifecycle, approvals, and import semantics

### 12.1 Separate three dimensions

| Dimension | Example values | Meaning |
|---|---|---|
| Lifecycle | `pending`, `approved`, `rejected`, `superseded` | Historical human action/state |
| Applicability | `current`, `stale`, `ambiguous`, `unresolved`, `needs_revalidation` | Whether the decision binds safely to the selected analysis/policy context |
| Execution eligibility | `eligible`, `blocked`, `unsupported`, `out_of_scope` | Whether the selected target operation can use it now |

A historically approved decision can be stale and blocked. Do not overwrite its historical state with `stale` and lose the fact that approval occurred. Legacy combined status fields require a lossless adapter into these dimensions.

Proposal state belongs to the proposal store/workflow, not the accepted decision lifecycle. An AI proposal is not a pending human decision until a person explicitly adopts or records it.

### 12.2 Decision creation and approval

**DEC-01.** A decision must identify subject, analysis, evidence, intent, rationale, origin, and actor provenance. Approved mappings require the current policy's prerequisites and appropriate permission.

**DEC-02.** Approval must be explicit. Navigation, save-as-draft, report generation, imported text, or AI assistance must not approve automatically.

**DEC-03.** The approving actor is derived from the active trusted context. A client-supplied `reviewer` value is display/import data only and cannot impersonate another actor.

**DEC-04.** Architectural review and conversion approval are different decision kinds. Migrating an old review record must not silently turn it into a target-generation approval.

**DEC-05.** CRITICAL/risky actions such as retirement, security-sensitive replacement, or broad bulk changes require the existing or newly specified explicit confirmation contract. Confirmation must bind to the previewed revision and payload.

### 12.3 Source changes and revalidation

When a source or engine change produces a new analysis, compute applicability without rewriting the old decision. Exact stable matching may suggest a reuse candidate, but a changed binding requires explicit revalidation or an approved batch operation that records the new binding and rationale.

Different engine versions can change analysis semantics even when source bytes are unchanged. Capability and schema differences must be part of comparison. Unknown compatibility is `needs_revalidation`, not a silently current decision.

Unchanged immutable analysis identity can preserve an existing binding. The service must test this equality explicitly; equal display names or equal local revision counters are insufficient.

### 12.4 Editing and supersession

A draft can be edited according to its draft contract. Once accepted into durable decision history, corrections append new events. Supersession must preserve the previous rationale, actor, evidence, and target mapping.

Conflicting active decisions on the same subject/target/dimension must block generation unless a deterministic, documented combination rule exists. Version 1 should prefer explicit conflict over a complex precedence language.

### 12.5 Preview/apply semantics

A preview returns the proposed canonical change, affected subjects, current context, conflicts, eligibility consequences, required permissions, and any additional confirmation.

Apply must recheck the same conditions under a write fence. A previously valid preview can become stale; the correct result is a conflict requiring review, not an automatic retry that approves a different state.

The importer must detect divergent bases, same-subject competing changes, evidence no longer applicable, schema changes, mismatched repository identity, unauthorized approval claims, duplicate event IDs with different content, and policy incompatibility.

### 12.6 Annotations and investigation work

Questions and notes can be stored independently of decisions, so an engineer can record uncertainty without inventing a migration mapping. They require subject/context binding, author provenance, visibility, and their own edit/history policy.

A note that says "confirmed by business" is not automatically a UAT acceptance record. Offer an explicit workflow to create a structured acceptance record when the required criteria are available.

## 13. Services, module boundaries, and integration contracts

### 13.1 Architecture boundaries

The following services describe responsibilities, not a mandatory file-per-service layout. Reuse and extract the corresponding existing classes after the baseline audit.

| Service / boundary | Owns | Inputs and outputs | Must not own |
|---|---|---|---|
| Repository coordinator | Identity, context resolution, accepted transactions, publication, recovery | Commands and immutable context → events/checkpoint references | Source parsing, visual layout, target-specific lowering |
| Source intake service | Roots, intake preview, source capture, authorized conversion runs | Authorized files/representations → source-set manifest | Implicit remote execution or target selection |
| Analysis/evidence builder | Parser invocation, facts, coverage, evidence | Source set + engine/capabilities → immutable analysis | UI-driven silent enrichment |
| Project query service | Permitted snapshot queries, entity lookup, graph neighborhoods, search | Context + typed filters → bounded projections | Decision mutation or re-parsing source |
| Correspondence/diff service | Versioned matching, semantic changes, impact candidates | Two compatible contexts + scope → diff/impact | Silent approval rebinding |
| Decision service | Preview, recorded choices, approval, supersession, bulk changes | Intent + context + actor → validated events | Trusting client approval fields |
| Language service | `.flm` parse/validate/serialize/format | Text or domain model → diagnostics/canonical representation | Independent decision authority |
| Exchange service | Checkpoint package export/import, disclosure, integrity | Context/profile or package → manifest/preview/apply result | Bypassing repository transactions |
| Planner / IR service | Applicability, dependency closure, target plan, blockers | Analysis + decisions + capabilities + policy → immutable plan | Altering facts to satisfy a target |
| Target adapter | Supported lowering, target validation hooks, artifact mapping | Validated plan → deterministic output objects | Deciding business intent or ignoring unsupported behavior |
| Validation service | Case definitions, runs, human evidence, applicability | Artifact/context + authorized runner → validation record | Treating syntax success as UAT |
| Reporting service | Definitions, snapshot queries, metrics, datasets, renderers | Checkpoint/scope/profile/definition → report objects | Reporting-only facts or hidden denominator changes |
| Proposal/AI service | Context selection, disclosure, provider call, untrusted proposals | Authorized selected context → proposal | Approval, database execution, or unrestricted source upload |
| Presentation adapters | HTTP, CLI, Workbench state/rendering | Same domain commands and query contracts | Business-rule duplication |

### 13.2 Shared context object

All nontrivial operations resolve a typed `RepositoryContext` containing:

```text
repository identity
workspace origin and revision fence, when operating on mutable current state
selected checkpoint, when operating on historical/pinned state
source-set identity and availability
analysis identity and capability/schema versions
decision snapshot/event frontier
policy identity used for domain interpretation
current execution/disclosure authorization context
selected target and capability manifest, when relevant
selected scope and scope-definition version
freshness/applicability metadata
```

Historical policy explains historical decisions. Current authorization governs whether a caller may read, export, approve, or execute now. These are separate fields and must not be conflated.

### 13.3 Dependency direction

Presentation adapters depend on application services; application services depend on domain models and storage/runner interfaces. Domain validation must not import frontend rendering code. Target adapters depend on neutral planning contracts, not on Workbench widgets.

Prefer explicit typed dataclasses/models or the repository's established equivalent. Avoid untyped dictionaries that let `approved=true` travel from an HTTP body into target generation unchecked.

### 13.4 Refactoring strategy

**ARCH-01.** Stop adding domain logic to the large legacy `modernization_visual.py` surface. Extract shared services and typed projections before adding new UI behavior.

**ARCH-02.** Preserve public aliases and migration adapters during the transition. New and legacy views may coexist behind a feature flag, but they must read the same accepted project state.

**ARCH-03.** Every new module must have a narrow public responsibility, testable boundary, and clear dependency direction. A new service layer that merely forwards arbitrary dictionaries to a monolith is not the intended refactor.

**ARCH-04.** Report metrics, CLI summaries, and Workbench badges must call the same domain aggregation definitions. Test equality on the same context, not just approximate visual agreement.

### 13.5 Adapters and environmental dependencies

External tools must be called through runner interfaces with explicit executable identity, version capture, argument validation, working directory, timeout, cancellation, and output sanitization. Unit tests use fixtures/fakes; integration tests identify when the actual external tool ran.

Do not claim Oracle, browser, installer, or security validation from a mocked runner. Keep simulated and actual execution evidence separate.

## 14. CLI product contract

### 14.1 Design principles

The CLI must be useful independently of the Workbench. It is not a collection of undocumented internal endpoints and not a thin command that always opens a browser.

Use the existing `formslang project` command family where compatible. Names below are proposed contracts; preserve equivalent existing commands and document aliases rather than break users unnecessarily.

**CLI-01.** All relevant commands must accept a project path/identity, explicit historical context where appropriate, stable machine-readable output, bounded scope, and predictable errors.

**CLI-02.** `--json` emits only the documented JSON result on stdout. Progress, warnings intended for humans, and diagnostics go to stderr. The JSON also includes structured warnings needed by automation.

**CLI-03.** The CLI must enforce the same permissions, revision fences, eligibility rules, redaction, and confirmation requirements as HTTP/Workbench in the applicable operating mode.

### 14.2 Required command families

| Family | Required operations | Key semantics |
|---|---|---|
| Project | `init`, `open`, `status`, `show`, `verify` | Initialize/open safely; display coherent state; verify object integrity and publication status |
| Sources | `sources preview`, `sources add`, `sources list`, `sources diff` | Explicit capture and supported-type/coverage reporting |
| Analysis | `analyze`, `analyses list/show` | Explicit immutable analysis and job status |
| Exploration | `screens`, `explore`, `entity show`, `evidence show`, `paths`, `search` | Same IDs, evidence, relationship families, limits, and context as the Workbench |
| History | `log`, `diff`, `impact` | Domain history and separate source/decision/plan/validation dimensions |
| Checkpoints | `checkpoint create/list/show`, `baseline create/list/show` | Whole-state references; labels do not imply readiness |
| Decisions | `decisions list/show/preview/set/approve/reject/supersede` | Pending by default for a newly recorded choice; approval explicit |
| Language | `decisions export`, `decisions import --dry-run`, `decisions import --apply`, `decisions format` | Canonical language, domain validation, explicit import |
| Exchange | `export`, `import --dry-run`, `import --apply` | Whole-project/profile exchange, separate from decision-only export |
| Planning/build | `plan`, `generate`, `artifacts list/show/diff` | Bound target plan and supported scoped generation |
| Validation | `validate`, `validations list/show`, `acceptance record` | Distinct validation levels and human acceptance |
| Reports | `reports definitions`, `reports preview`, `reports generate`, `reports list/show/compare` | First-class snapshot reporting with profile, scope, and completeness |
| Operations | `jobs list/show/cancel`, `recover`, `backup`, `restore` | Safe lifecycle and explicit recovery; no silent destructive reset |

Native Git branch, pull, push, force-reset, remote hosting, and production deployment commands are not required in 3.0.

### 14.3 Illustrative workflow

These commands demonstrate intended semantics and are not asserted to work in release 2.x. The implementation must replace them with verified executable examples before publication.

```bash
formslang project init ./erp-modernization --name "ERP Modernization"
formslang project sources preview ./erp-modernization ./forms ./database
formslang project sources add ./erp-modernization ./forms ./database
formslang project analyze ./erp-modernization
formslang project status ./erp-modernization --json
formslang project screens ./erp-modernization --json
formslang project explore ./erp-modernization --form ORDERS --depth 1
formslang project evidence show ./erp-modernization --id ev-142
formslang project decisions preview ./erp-modernization --file ./proposed.flm
formslang project decisions import ./erp-modernization ./proposed.flm --dry-run
formslang project decisions import ./erp-modernization ./proposed.flm --apply --expected-revision 17
formslang project checkpoint create ./erp-modernization --message "Reviewed order-entry scope"
formslang project log ./erp-modernization --subject block:ORDERS.HEADER
formslang project diff ./erp-modernization --from baseline:assessment --to current --decisions
formslang project plan ./erp-modernization --scope ORDERS --target oracle-apex/26.1
formslang project reports generate ./erp-modernization --template technical-assessment --at current --format html
formslang project verify ./erp-modernization
```

`current` must resolve once at command start to an immutable/pinned query context. A multi-page result must not shift to a newer current state between pages.

### 14.4 Human-readable status

Display contextual groups rather than one percentage:

```text
Repository and selected context
Source coverage and working-source changes
Analysis availability and limitations
Decisions: lifecycle, applicability, and conflicts
Plans: eligible, blocked, unsupported, and out-of-scope units
Validation: checks completed, failed, missing, and inapplicable
Reports: checkpoint, scope, freshness, and disclosure profile
Publication/integrity: synchronized, pending, failed, or unavailable objects
```

Numbers are supplied by the domain snapshot. Do not hardcode example totals or use the count of visible graph nodes.

### 14.5 JSON envelope

The shared envelope must define at least:

| Field | Contract |
|---|---|
| `schema_version` | Response schema, versioned independently of product release |
| `repository_id` | Stable project identity |
| `context` | Checkpoint, analysis, decision state, policy, scope, and origin/fence as applicable |
| `data` | Typed command-specific result |
| `coverage` | Known, measured, unresolved, unavailable, and excluded dimensions appropriate to the operation |
| `freshness` | Current/historical/source-change/applicability information |
| `warnings` | Structured code and permitted message/context |
| `truncation` | Boolean, reason, and continuation when bounded |
| `next_cursor` | Opaque context-bound continuation token, if applicable |
| `publication` | Accepted versus synchronized status for mutations that publish files |

Do not expose unauthorized global totals in a `coverage` object merely because a frontend does not display them.

### 14.6 Exit-code contract

| Exit code | Meaning |
|---|---|
| 0 | Operation completed within its declared contract and scope |
| 1 | Unexpected internal failure |
| 2 | Invalid usage, parse error, or invalid input schema |
| 3 | Required input/source representation missing or insufficient for the requested strict operation |
| 4 | Revision, ancestry, semantic-import, or decision conflict |
| 5 | Policy/capability/elegibility blocked the requested operation |
| 6 | The requested validation executed and failed |
| 7 | Access denied |
| 8 | Busy/unavailable system or required external dependency |
| 9 | Integrity/corruption verification failure |
| 10 | Explicitly partial job/export result, with the partial contract and omissions reported |
| 130 | Cancelled/interrupted operation, with committed-state status disclosed |

A successful query may report unresolved facts and still exit 0; it fulfilled the query contract. A strict build requiring those missing facts fails with the appropriate code. Do not use exit 0 for a failed validation merely because JSON was successfully printed.

Ratify compatibility with existing exit codes during the CLI ADR. A `--force` flag may authorize an explicitly destructive output-file overwrite; it must never bypass approval, permission, integrity, or eligibility checks.

## 15. HTTP and asynchronous interaction contracts

### 15.1 API design

HTTP is a presentation adapter over the same application services. Route names below are illustrative. Version public schemas, validate every request, and keep writes separate from previews and queries.

| Route family | Required operation | Permission/context behavior |
|---|---|---|
| `/projects` | List/create/open supported projects | No discovery of unauthorized projects through names, totals, or timing details |
| `/projects/{id}/status` | Repository status | One coherent context; distinguish working state from historical state |
| `/projects/{id}/sources` | Preview/list/add source captures | Authorized roots; explicit mutation and expected context |
| `/projects/{id}/analyses` | List/show/start analysis | Analysis jobs pin source sets and capabilities |
| `/projects/{id}/ecosystem/...` | Screens, focus, nodes, edges, paths, search | Bounded snapshot query, per-object metadata permission |
| `/projects/{id}/evidence/{evidence_id}` | Evidence metadata or permitted snippet | Source body requires source-read permission; no raw paths in URL |
| `/projects/{id}/checkpoints` | Create/list/show snapshots | Whole-state manifest; publication status explicit |
| `/projects/{id}/diff` | Typed context comparison | Permission on both contexts; incomparable data labeled |
| `/projects/{id}/decisions/preview` | Validate a proposed change | No accepted-state mutation |
| `/projects/{id}/decisions` | Record/apply a decision operation | Authenticated/local-trusted actor, revision fence, confirmation, idempotency |
| `/projects/{id}/decisions/import` | Preview/apply DSL changes | Parse, ancestry, applicability, and approval-trust checks |
| `/projects/{id}/plans` | Preview or explicitly publish a plan | GET/preview must not mutate facts or approve decisions |
| `/projects/{id}/generations` | Execute a supported generation | Bound plan and policy; asynchronous job when needed |
| `/projects/{id}/validations` | Execute/list/check validation and human acceptance | Artifact-specific context; authorized execution/attestation |
| `/projects/{id}/reports` | Definitions, preview, generate, list, compare | Same report service; snapshot and disclosure binding |
| `/projects/{id}/exchange` | Export/import/verify | Category selection, sensitivity preview, explicit apply |
| `/projects/{id}/jobs` | Status/cancel/result | Caller permissions checked before exposing output |

### 15.2 Write contract

**API-01.** Mutations carry the expected analysis/decision/workspace state appropriate to the operation and an idempotency key. The server derives identity and authorization, not the request body.

**API-02.** A conflict returns HTTP 409 with a stable domain error code and permitted current context. Integrity errors are distinct from conflicts. Access responses must not leak the existence of inaccessible objects.

**API-03.** Unsafe operations must not be exposed as GET requests. Merely loading a report, history entry, or graph must not trigger source mutation, analysis enrichment, decision approval, or external Oracle execution.

### 15.3 Pagination and snapshot stability

Cursors must bind query, scope, snapshot, and visibility context. Reusing a cursor after an incompatible context or authorization change must return a controlled error, not silently continue in another dataset.

The service must not infer permission from a client-supplied tenant/project ID. Every route, object reference, report download, and job result needs server-side scope validation.

### 15.4 Client state and error handling

The frontend tracks requested context and response identity. On context mismatch it discards the response and offers refresh where appropriate. A stale decision preview is not retried automatically as a fresh approval.

Errors need a stable code, actionable message, retryability, safe diagnostic identifier, and relevant permitted context. Expose detailed stack traces only through an authorized local diagnostic workflow, never in ordinary reports or public endpoints.

## 16. Workbench information architecture and visual system

### 16.1 Experience mandate

The Workbench must expose the repository as a coherent working environment. The intended qualities are precise navigation, a strong visual hierarchy, contextual evidence, meaningful history, and practical delivery controls.

An IDE-like explorer, a reviewable change workflow, and an architecture inspector are useful mental references. They are not instructions to copy another product's branding or build a generic GitHub clone.

**UX-01.** Replace the navigation architecture, design system, and primary workflows—not just colors, spacing, or a landing page.

**UX-02.** Preserve the user's context across exploration, decisions, builds, validation, reports, and history. An error or report finding must lead back to its source object and decision.

**UX-03.** Prioritize understandable connected views over a whole-estate graph with hundreds of overlapping nodes.

### 16.2 Primary navigation

Use a compact primary navigation with:

**Explore · Decisions · Build · Validate · Reports · History**

The four-step journey remains Understand/Decide/Build/Validate. Reports and History are repository-wide entry points available throughout the journey. Project status, current context, source intake, and checkpoint selection are always discoverable in the project header or project menu.

Advanced contains low-frequency configuration and legacy technical tools, not the only route to reports, source evidence, or useful history.

### 16.3 Initial state and progressive disclosure

Before analysis: show project identity, intake status, and one primary action—Add sources.

With one supported Form: open its focal exploration automatically after the explicit analysis completes, with a visible link to the source/coverage summary.

With multiple Forms: show a searchable catalog and a clear next action to select a screen. Do not force users to choose graph lenses, target templates, AI providers, or report settings first.

The first view should answer one question: **What should I inspect or do next in this project?** It must not demand knowledge of internal subsystem names.

### 16.4 Desktop composition

| Region | Purpose | Behavior |
|---|---|---|
| Project rail | Repository tree, catalogs, source groups, recent objects | Collapsible; stable selection; supports keyboard navigation |
| Top context bar | Project name, checkpoint/current state, freshness, global search, primary action | Context always visible; historical mode unmistakable |
| Main workspace | Focal graph, lists, diff, report, or task-specific content | Uses available space; no mandatory analytics dashboard |
| Context inspector | Summary, evidence, dependencies, decisions, history, target/validation links | Resizable; defaults to concise summary; progressive detail |
| Contextual action area | Preview decision, build scope, validation issue, report export | Appears when relevant; must not obscure graph controls or focus |

Candidate desktop sizes are a 220–280 px rail and 320–480 px inspector, with collapse behavior. They are design starting points, not an excuse to break smaller windows. Test actual content, long identifiers, and translated labels before freezing tokens.

### 16.5 Visual system

Create explicit tokens for type scale, spacing, surface hierarchy, borders, focus indicators, semantic states, elevation, and motion. Use a restrained palette and consistent iconography. Technical density should be deliberate: normal reading content remains comfortable, while tables and code panels can be denser without becoming illegible.

Do not use color as the only indication of observed/inferred, approved/stale, pass/fail, or source/target. Include labels, shapes, line styles, icons, and accessible names.

Light/dark themes may be included if fully tested; a theme switch is not more important than a readable evidence panel. Use subtle motion and honor reduced-motion preferences. Avoid moving graph layouts after the user has begun reading a selected node.

### 16.6 Accessibility and responsive behavior

**UX-04.** Target WCAG 2.2 AA for applicable interface behavior, including keyboard operation, visible focus, contrast, meaningful labels, reflow, and non-color state communication. Automated checks are necessary but not sufficient for the claim; perform manual keyboard and assistive-technology tests. [T6]

**UX-05.** Required browser layouts include 390, 720, and 1366 CSS-pixel widths from the original specification. Add a 320 CSS-pixel/reflow check and 200% zoom. For complex two-dimensional diagrams, provide an equivalent accessible list instead of claiming the diagram itself solves every reflow case.

**UX-06.** On narrow screens, default to a list or contained graph viewport. The inspector becomes an accessible panel/dialog with focus management and a reliable return path. No required action may depend only on hover.

**UX-07.** Ctrl+K / Command+K may open global search. Keyboard shortcuts must not intercept typing in editors, must be documented, and must have visible equivalent controls.

### 16.7 Required UI states

Every major surface must define loading, empty, partial, permission-restricted, error, retry, cancelled, stale, historical, and unavailable states where applicable.

Specific required distinctions include:

| Situation | Required message/action |
|---|---|
| No observed relationship | State that none was observed in the selected analyzed scope |
| Graph limit reached | Show that results are bounded and offer continuation/filtering |
| Source missing | Identify permitted missing source context and the safe next intake/rebind action |
| Evidence not authorized | Explain restricted access without exposing the protected content |
| Unsupported representation | Explain what can be inventoried and what representation is required for analysis |
| Decision stale | Show the old binding and the proposed revalidation workflow |
| Concurrent update | Preserve the user's draft, show conflict, and require review |
| AI unavailable | Core workflow continues; no suggestion that AI is required |
| Build blocked | Show the exact blocking subject, reason, and decision/evidence link |
| Validation not run | Say "Not executed" rather than use an empty green badge |
| Publication failed after commit | Say decision saved, portable publication pending/failed; provide recovery |

### 16.8 Legacy surface migration

| Existing surface | New home | Required preservation |
|---|---|---|
| Overview / Start Here | Project header, status, context-appropriate next action | Coverage, freshness, and repository identity |
| System Map / Module 360 | Explore, contextual inspector; aggregate map under secondary tools | IDs, details, and useful deep links |
| Inventory / Dependencies / Hotspots / Blueprint | Explore lists/lenses and contextual decision candidates | Existing technical detail and export discoverability |
| Review / Conversion Review | Decisions, with explicit decision-kind distinction | Approval history and different review semantics |
| Visual Preview / Structural Diff | Explore/Build/Validate comparisons | Clear static-versus-runtime wording |
| Reports / Exports | Reports center plus scoped export actions | Existing output access, now first-class rather than hidden |
| Settings | Project menu / Advanced | Permission-aware configuration and no surprise network exposure |

Before hiding a route, inventory the task it supports and test its replacement. Preserve or redirect legacy deep links with equivalent context. Coexistence for a transition release is acceptable; two conflicting domain models are not.

## 17. Detailed screens and end-to-end journeys

### 17.1 Projects and repository status

The project list shows name, permitted location/identity, last captured context, availability, and last meaningful activity. It must not show an invented migration-completion percentage.

Opening an existing project does not reanalyze it, migrate it destructively, or auto-publish files. If an upgrade is required, show a preview and backup path before explicit action.

Repository status is a useful summary, not the mandatory first page of every session. It links to source changes, decisions requiring review, blocked plans, failed/missing validations, recent reports, and pending publication.

### 17.2 Intake screen

Provide file/folder selection or an equivalent drag/drop path, a categorized preview, per-file diagnostics, source-root bindings, and the explicit Analyze action. Explain binary conversion requirements before running external tools.

The user can cancel a long intake/analysis job safely and resume by inspecting the recorded job state. A failed file must not make every other source disappear or falsely appear fully analyzed.

### 17.3 Explorer

A focused Form view groups related content into a small number of meaningful families: surfaces, logical data blocks/items, logic, data, other Forms, and external/unresolved references. The exact grouping may adapt to the source; avoid showing six empty decorative cards.

Node selection opens a short summary with type, qualified identity, revision, certainty/applicability, relevant relationships, and next actions. Edge selection shows direction, type, evidence, resolution, and limitations.

A "Why?" or "Show evidence" action opens the exact permitted source location. "Focus here" changes the focal entity while preserving navigation history. A static schematic of source placement must be labeled as static and must not imply runtime simulation.

The inspector offers:

```text
Summary
Evidence
Uses / Used by
Decisions and open questions
History and changes
Target mapping / artifacts
Validation
```

These may be sections rather than seven competing top-level tabs. Summary is the initial view, with progressive disclosure.

### 17.4 Decisions workspace

Provide a filterable queue by subject, decision kind, lifecycle, applicability, target, risk, and required action. Support a context-preserving jump from graph to decision and back.

The editor must show source/evidence, intent, rationale, target mapping prerequisites when needed, and the semantic preview. The user sees what will change before approval. A pending decision and an approved decision must have visibly different actions.

Expose a read-only canonical `.flm` preview and diff. A text-edit workflow is useful for advanced users, but it must pass the same preview/apply validation and must not become the default onboarding hurdle.

Saved private drafts may be retained locally with clear status; they must not appear in approved state or ordinary exports. Recording a pending human decision is an explicit durable action.

### 17.5 History and comparison

A timeline can be filtered by entity or operation. Each entry explains action, actor/origin trust, rationale, input/output context, and associated objects. It links to a semantic before/after view.

Comparison defaults to a meaningful baseline/current pair and separates source, analysis, decisions, plans, artifacts, validations, and reports. Incomparability, denominator change, and source availability change are first-class results.

Historical inspection displays a persistent read-only banner. A "Use this as a starting point" action creates a preview for a new operation; it does not reset the current ledger.

### 17.6 Build workspace

Target selection first appears here or in an explicitly target-specific decision. Show adapter version and supported capabilities, selected scope, eligible units, blockers, unresolved dependencies, and planned omissions.

The plan preview must make dependency closure visible. Selecting one apparently eligible block must not silently omit a required unresolved validation or transaction dependency.

Generation requires a current applicable plan and explicit operation. The result links emitted components, omitted scope, source decisions, and artifact hashes. Do not replace unsupported code with a success-looking empty process.

### 17.7 Validation workspace

Display structural/DSL, generated-artifact, tool/syntax, import, runtime, and UAT levels separately. Each row identifies artifact, case/scope, environment, time, result, and applicability.

Selecting a failure navigates to its target component, mapped decision, and evidence. Missing environment or permission produces a clear "Not executed" state and setup guidance, not a fake passing run.

Human acceptance uses structured criteria and evidence references. It is not a generic green checkbox for the entire project.

### 17.8 Reports center

Reports must be accessible directly from primary navigation and contextually from a Form, decision set, baseline comparison, or build.

The creation flow selects template, checkpoint, scope, audience/disclosure profile, and output format; it then previews included sections, available metrics, missing coverage, and source-body inclusion. Defaults should produce a useful assessment without expert report configuration.

The report viewer supports a table of contents, summary-to-detail navigation, metric-definition inspection, evidence links, filtering of detail tables, and explicit stale/input-context labels. Export must preserve the same values and disclosure rules.

### 17.9 Required complete journeys

**J1 — First understanding.** Create/open project → add supported source → analyze → open Form → follow one meaningful relationship → inspect evidence/unknown → record a question → return to the same focus.

**J2 — Decision and Git review.** Select block → review evidence → record intent/mapping → explicit approval → inspect `.flm` diff → create checkpoint → export review profile → reopen/import preview → detect conflicting or stale changes correctly.

**J3 — Build and validation.** Select approved applicable scope → inspect plan/dependency closure → generate supported artifact → verify output manifest → run available validation → follow failure to decision/source → publish a new checkpoint.

**J4 — Executive and technical assessment.** Select checkpoint → generate report preview → inspect defined metrics and missing coverage → render/export technical and executive outputs → follow a claim to evidence → compare with a later compatible baseline.

**J5 — Historical reproducibility.** Export a complete authorized repository scope → reopen in a clean workspace → inspect old decisions/evidence → reproduce deterministic supported outputs using the recorded toolchain → show unavailable execution environments honestly.

**J6 — Failure without data loss.** Save a decision while canonical publication is forced to fail → show accepted state plus pending publication → recover → verify the same event and bytes → confirm no duplicate decision or lost history.

These journeys are product acceptance contracts. Completing isolated screens without them is insufficient.

## 18. Reporting as a first-class product capability

### 18.1 Reporting mandate

**RPT-01.** Reporting is a primary FormsLang capability and release workstream. It must not be implemented as a late export button, a collection of disconnected templates, or a hidden Advanced feature.

**RPT-02.** Reports must be different views of the same repository state used by CLI and Workbench. Every reported fact, count, classification, decision, artifact, or validation must have a defined source and reproducible derivation.

**RPT-03.** Comprehensive means complete for a declared scope and capability set, with explicit unknowns and exclusions. It does not mean that unavailable data is invented or that every report must contain every possible table.

### 18.2 Reporting architecture

Use a shared pipeline:

```text
Report request
→ authorize repository, scope, evidence visibility, and disclosure profile
→ resolve one immutable input context
→ validate versioned report definition and metric definitions
→ execute bounded/paginated domain queries over the complete authorized scope
→ produce canonical report dataset and completeness metadata
→ validate internal reconciliations and provenance
→ render HTML / Markdown / PDF / tabular exports
→ verify and publish report manifest
→ record report history and optional subsequent repository checkpoint
```

A renderer receives a completed typed report dataset; it must not run its own SQL/PLSQL parser, independently compute readiness, or call AI to invent missing findings.

**RPT-04.** Report definitions and metric definitions must have versioned identities. A template change that alters a denominator or classification requires a new definition version.

**RPT-05.** Cache report data only by exact input context, scope, metric/definition versions, disclosure profile, and authorization scope. A privileged report cache must never be reused for a restricted reader.

### 18.3 Required report catalog

A report may be offered as a standalone view or a section in a larger package. The following catalog must have implemented data contracts and useful fixture-backed outputs in 3.0. Where a specific analysis capability is unavailable, the report must identify the unsupported indicator and its consequence; the whole catalog cannot be marked complete with empty placeholder pages.

| ID | Report / section | Minimum required content |
|---|---|---|
| RC-01 | Executive modernization summary | Scope, source coverage, decisions requiring action, generation eligibility, major evidenced blockers, validation status, limitations, and next recorded actions |
| RC-02 | Estate overview | Form/module inventory, source categories, declared boundaries, analysis versions, provided/missing representations, and grouping definitions |
| RC-03 | Forms and component inventory | Qualified Form/component IDs, logical and visual hierarchy, supported feature counts, evidence references, and unresolved placement |
| RC-04 | Dependency topology | Typed cross-module/code/data relationships, direction, certainty, resolution, connected components/cycles where computed, and query coverage |
| RC-05 | Cross-Form navigation | Observed Form-opening/navigation references, exact or unresolved targets, call evidence, and static-analysis limitations |
| RC-06 | Database dependency matrix | Schema-qualified packages/tables/views, permitted source consumers, reads/writes/calls, ambiguous references, and evidence |
| RC-07 | PL/SQL and SQL structure | Supported structural measures, code ownership, program units/cursors/queries, dynamic constructs, unresolved bodies, and measurement definitions |
| RC-08 | Forms feature usage | Detected constructs, count basis, target capability mapping, unsupported/partially supported features, and known extraction gaps |
| RC-09 | Complexity indicators | Versioned structural indicators and distributions, evidence, and explicit absence of unsupported effort/cognitive-complexity claims |
| RC-10 | Risk and technical-debt indicators | Rule-triggered findings, severity/rationale, source evidence, owner/status if recorded, and distinction between technical signal and business risk assessment |
| RC-11 | Unresolved dependencies and knowledge gaps | Unknown targets, missing source, unsupported syntax, ambiguous matches, confidence/certainty boundaries, and recorded follow-up questions |
| RC-12 | Modernization readiness | Eligibility by defined unit/target, blockers, unresolved dependencies, required decision obligations, and validation prerequisites |
| RC-13 | Decisions and rationale | Decision kind, intent, subject, evidence, lifecycle, applicability, target, reviewer provenance, and rationale |
| RC-14 | Decision history | Creation, approval, rejection, supersession, revalidation, import provenance, and conflicts over the selected history range |
| RC-15 | Source-to-target mappings | Source subject → decision → plan unit → target component/file → artifact digest → validation linkage; explicit unmapped/omitted cases |
| RC-16 | APEX mapping and capability coverage | Supported/unsupported construct mapping, required keys/tables, eligible target units, omissions, and adapter/toolchain identity |
| RC-17 | Migration progress | Separate measured dimensions for analysis, decisions, emitted scope, and validation; baseline/cohort definitions and scope changes |
| RC-18 | Blockers and action backlog | Stable blocker ID, affected scope, reason, evidence, recorded owner/action/status if present, and no fabricated due dates |
| RC-19 | Validation coverage | Required criteria/cases, checks executed, pass/fail/error/not-run, applicable artifact context, environment, and human acceptance evidence |
| RC-20 | Change impact | Baseline comparison, directly changed objects, dependent decisions/artifacts/tests, uncertainty boundaries, and supporting paths |
| RC-21 | Modernization gap analysis | Required versus delivered/validated scope, deferred/retired work with rationale, unsupported features, and missing acceptance evidence |
| RC-22 | Generation manifest | Emitted, partially emitted, omitted, blocked, unsupported, and out-of-scope units; output hashes and deterministic input identity |
| RC-23 | Repository history and integrity | Checkpoint lineage, declared event coverage, object availability, integrity verification, publication state, and origin trust |
| RC-24 | Evidence/provenance appendix | Navigable permitted evidence index, source/analysis/tool identities, locators, redaction state, and reasons for unavailable evidence |
| RC-25 | Baseline comparison | Comparable metric changes, definition/denominator changes, source additions/removals, decision changes, and validation applicability |

### 18.4 Required report packages

Provide at least these named templates:

**Executive Assessment.** RC-01, RC-02, RC-10, RC-11, RC-12, RC-17, RC-18, RC-19, and a concise provenance/limitations section. Focus on decisions and delivery implications; do not overwhelm the summary with every trigger listing.

**Technical Modernization Assessment.** Full selected-scope inventory, dependencies, feature/complexity indicators, decisions, mappings, readiness, blockers, validation, and the complete permitted evidence appendix.

**Change and Impact Review.** A pair of explicit compatible checkpoints, source/analysis/decision differences, impacted plans/artifacts/validations, denominator changes, and uncertainty boundaries.

**Delivery and Validation Package.** The selected plan/artifact manifest, source-to-target traceability, omitted and blocked scope, exact checks and environments, outstanding acceptance, and the associated decision baseline.

Users may select sections, but removing a section must not make an incomplete package appear to cover that section. The cover/manifest states the selection.

### 18.5 Report object contract

| Field group | Required values |
|---|---|
| Identity | Report ID, report-definition version, metric-definition set, renderer version |
| Input | Repository/checkpoint, source/analysis/decision/policy/adapter references, selected scope |
| Authorization | Disclosure profile and permitted evidence scope; sensitive execution/session tokens excluded |
| Coverage | Included units, measured units, excluded categories, unsupported indicators, unresolved/unavailable objects, truncation/partial state |
| Data | Typed tables, metrics, classifications, and provenance links |
| Interpretation | Deterministic explanatory text or explicitly labeled human/AI annotations with provenance |
| Output | Format manifests, output hashes, input dataset digest, export/package identity |
| History | Stable creation record, origin/actor, input checkpoint, later publication checkpoint if any |

### 18.6 Metric-to-evidence navigation

**RPT-06.** In the Workbench and HTML report, a metric must open its definition, denominator, filters, counted entity set, and permitted evidence. In PDF/Markdown, provide stable section/table/row references and an appendix—not a broken application-only link.

**RPT-07.** Each finding must identify a rule or recorded human assessment, scope, severity definition where used, evidence, and uncertainty. A paragraph generated by AI is not the originating finding.

**RPT-08.** Evidence links in exported reports must be safe and durable within the declared package. A local application URL may be offered as an additional convenience, but cannot be the sole way to understand the export.

### 18.7 Completeness and large datasets

Reports must query the entire authorized selected scope through paginated domain queries. The 80-node/160-edge visual budget must not cap report counts.

Large evidence appendices may be split into indexed parts. The package must include a manifest identifying all parts and a completeness result. When a resource limit prevents completion, publish an explicitly partial report with the omitted categories/counts where known and permitted. Do not call a first-page export complete.

A protected source must not be reported as nonexistent. Within the caller's disclosure rights, use unavailable/restricted states without leaking unauthorized names or global totals.

### 18.8 Format contracts

| Format | Required behavior |
|---|---|
| Canonical JSON | Complete typed report data, schema/definitions, provenance, completeness, stable machine-readable structure |
| HTML | Offline-viewable, local assets, clear table of contents, readable tables, safe links, accessible structure, no external tracking/resources |
| Markdown | Portable narrative and tables with references to machine data and evidence appendix; useful in code review |
| PDF | Actual tested export with pagination, headings, readable table wrapping, repeated table headers where needed, evidence references, and no clipped content |
| CSV tables | One consistent table per exported dataset, explicit columns/definitions, correct escaping/encoding, and protection against spreadsheet formula injection |

**RPT-09.** PDF is a real rendering capability that must be tested in the packaged environment. A button opening the browser print dialog must not be advertised as an automated PDF renderer unless that is explicitly the documented feature.

**RPT-10.** No report export may fetch arbitrary remote fonts, images, scripts, or styles at rendering time. Choose renderer dependencies and licensed bundled assets through the packaging ADR.

**RPT-11.** Sanitize source-derived HTML/SVG/Markdown/CSV content. Source text must never become executable markup, a script URL, or a spreadsheet formula merely because it is exported.

### 18.9 Determinism and rendering

The canonical report dataset is deterministic for the same checkpoint, scope, definitions, parameters, and disclosure context. Regenerating the same recorded report with the same renderer should produce matching deterministic outputs under its documented contract.

A new report creation event can have a new timestamp; do not let that volatile metadata obscure whether the underlying measured data changed. Separate data digests, rendering digests, and creation/transport metadata. Archive ordering and metadata must be normalized for any package advertised as byte-deterministic.

Report freshness compares the definition's relevant dependency vector, not only the top-level checkpoint ID. Publishing report R from C into C2 does not make R stale merely because C2 also records R. The report remains explicitly as-of C and can be current-for-inputs when its relevant sources, decisions, policy, definitions, and selected artifacts have not changed.

### 18.10 Report quality gates

At minimum, test:

- Metrics reconcile to independent fixture expectations and drill-down sets.
- Workbench, CLI JSON, report JSON, and rendered totals agree for identical context/scope.
- Every headline finding has permitted provenance.
- Unknowns and unmeasured indicators do not become zero or green.
- Report data is not capped by visual pagination.
- Version/scope changes are visible in comparisons.
- HTML works offline and rejects unsafe content.
- PDF pages have no clipped headings, rows, or evidence references; inspect representative rendered pages manually.
- CSV opens with intact text and cannot execute injected formulas from source values.
- Restricted exports do not leak through names, counts, tooltips, embedded JSON, attachments, or generated filenames.
- A report generated while the project changes remains bound to its original context and is visibly historical when appropriate.

## 19. Metric definitions, coverage, and readiness

### 19.1 Metric governance

**MET-01.** Every metric requires an ID, version, business/technical question, unit of analysis, population, numerator/denominator where applicable, filters, deduplication key, source references, capability prerequisites, null/unknown rules, and interpretation limits.

**MET-02.** Do not combine structural analysis, human decisions, generated output, and validation into one global percentage by default. Present independent dimensions.

**MET-03.** A zero denominator yields **Not applicable** or **Undefined**, according to the definition—not 100%. A denominator that cannot be established yields **Unknown**, not zero.

**MET-04.** Scope and denominator changes must be shown separately from within-cohort progress. A smaller backlog caused by deleting source files is not equivalent to completing migration work.

### 19.2 Required definitions

| Metric ID | Definition | Required caveat |
|---|---|---|
| M-SOURCE-REGISTERED | Count of distinct logical source entries in the selected source-set manifest | Identical bytes can occur under different logical source identities; report deduplication basis |
| M-SOURCE-ANALYZED | Count of registered entries with applicable successful/partial analyses, separated by outcome | A partially parsed file is not fully covered |
| M-FORMS | Distinct analyzed Form/module identities in selected scope | A Form count is not a screen/window/canvas count |
| M-COMPONENTS | Counts by declared entity kind and unique domain identity | An item shown in logical and visual trees is counted once per kind, not twice |
| M-RELATIONS | Distinct relationships by type, certainty, and resolution | Counts are for captured analysis scope, not all possible runtime relationships |
| M-UNRESOLVED | Distinct unresolved/ambiguous dependency references with reason | Missing permission and missing source must not be conflated |
| M-DECISION-COVERAGE | Applicable approved decision obligations divided by known required decision obligations | An obligation is a defined subject × decision kind × target/scope × policy rule; duplicate decisions do not inflate progress |
| M-DECISION-STALE | Required obligations whose accepted choices need revalidation in the selected context | Historical approval remains recorded separately |
| M-GENERATION-ELIGIBLE | Eligible target units divided by known selected target units under a declared adapter/policy | Eligibility means buildable under the contract, not functionally migrated |
| M-EMISSION-COVERAGE | Fully emitted selected units divided by known selected units for the same declared granularity | Partial emission, unsupported, omitted, and blocked units remain separate |
| M-MAPPING-COVERAGE | Required source obligations with a complete applicable target mapping divided by known mapping-required obligations | Explicit retirement/deferment is a disposition, not automatically a generated mapping |
| M-VALIDATION-EXECUTION | Required applicable test criteria with an actual run divided by known required criteria | Missing test definitions prevent claims about total business-behavior coverage |
| M-VALIDATION-PASS | Required applicable criteria with acceptable passing evidence divided by known required criteria | Not-run and inapplicable historical passes do not count as passing |
| M-UAT-ACCEPTANCE | Selected acceptance criteria with applicable authorized human acceptance divided by defined selected acceptance criteria | Does not certify unlisted scenarios or the entire estate |
| M-TRACEABILITY | Selected delivery units with complete required source→decision→artifact→validation links divided by known selected delivery units | Missing links are reported explicitly; a link does not prove behavioral equivalence |

### 19.3 Screen and unit definitions

A catalog can use a Form as its entry point while displaying multiple windows/canvases beneath it. Do not label all those constructs interchangeably as "screens" in reports.

If the product introduces a `screen` abstraction, define its extraction/grouping rule, identity, and counting semantics. Until then, display the underlying entity kind accurately. A visually grouped node is not an additional business screen.

For every ratio, the report must state whether the unit is a Form module, block, item, decision obligation, target page, artifact, or acceptance criterion. Ratios across different granularities are not directly comparable.

### 19.4 Example of honest coverage

Suppose a synthetic fixture defines 100 decision obligations. Seventy have applicable approval, ten have historically approved but stale decisions, five have pending decisions, and fifteen have no recorded decision. The current approved coverage is 70/100, not 80/100. These numbers are an explanatory example, not measured FormsLang results.

If the engine can identify obligations for only part of an unsupported source language, the report must explain that the denominator covers the known supported portion. It must not describe that ratio as complete estate coverage.

### 19.5 Complexity and risk

Version 1 complexity reporting should prefer interpretable structural indicators: number of supported program units, triggers, SQL statements, direct dependencies, fan-in/fan-out under declared edge types, unresolved references, and detected target-unsupported constructs.

Do not call line count "cognitive complexity" or assume a high dependency count means a high business risk. A composite score requires a documented model, inputs, weights, rationale, calibration/validation, and interpretation limits; it is not required for the initial useful report.

Risk severity may be a rule classification when the rule is explicit and evidence-backed. Business criticality, financial impact, operational priority, or remediation ownership requires supplied human/business data. Missing business information remains unknown.

### 19.6 Readiness and completion language

Use scoped statements such as:

```text
Eligible for generation under adapter capability set X.
Requires decision review for obligations Y and Z.
Generated for the selected units; omissions listed below.
Imported into the stated test environment.
Runtime cases A and B were exercised.
UAT criteria C and D were accepted by the recorded reviewer.
```

Do not use a global "Migration complete" badge unless a versioned, owner-approved scope and completion policy exists and every required gate for that exact scope has evidence.

### 19.7 Remaining scope and estimates

Remaining **known units** can be reported from the defined obligation/plan sets. Remaining engineering **time or cost** requires a separately approved estimation model with recorded assumptions and calibration data. Do not derive hours or currency from raw object counts by an invented multiplier.

AI must not fill missing estimates, percentages, owners, deadlines, or business criticality. It can summarize already measured values with their caveats.

## 20. Planning, intermediate representation, and APEX generation

### 20.1 Separate facts, intent, plan, and target representation

The implementation must maintain four distinct layers:

| Layer | What it represents | Example |
|---|---|---|
| Facts/evidence | What the supplied legacy source declares or supports | A trigger calls a named routine; a block references a table |
| Modernization intent | What a person decided to preserve, convert, replace, investigate, defer, or retire | Preserve a validation responsibility; replace a supported interaction with a native capability |
| Plan / neutral IR | Applicable choices, required dependencies, prerequisites, and blockers | A delivery unit is eligible only when its required validation and mapping obligations are satisfied |
| Target representation | Concrete supported target components and generated files | A supported APEX form region/process with declared table/key mapping |

"This trigger should become an APEX process" is a decision or target mapping, not an extracted legacy fact.

### 20.2 Plan contract

**BUILD-01.** A plan MUST be deterministic for an exact analysis, decision state, source availability, selected scope, target capability set, and policy.

**BUILD-02.** It MUST include selected units, required dependency closure, applicable decisions, evidence, target version, eligible units, blockers, unsupported units, explicitly omitted/out-of-scope units, and traceability references.

**BUILD-03.** Each blocker MUST have a stable code, affected subject/unit, cause, evidence or missing-evidence reason, and a possible next action when known.

A plan object should expose at least:

```text
schema and plan identity
repository/input checkpoint
analysis and source-set references
decision snapshot/event frontier
policy and adapter capability manifest
selected scope and unit definition
required dependency closure
eligible units and their mappings
blocked/unsupported/omitted/out-of-scope units with reasons
source-to-target traceability requirements
expected output types
validation prerequisites
integrity and deterministic-input digest
```

Plans are projections; they do not modify facts or decisions to make generation succeed.

### 20.3 Dependency closure and partial output

A block can have an approved table/key mapping while a required validation remains unresolved. Its approval does not automatically make the full delivery unit eligible.

Default generation is strict for the selected delivery contract. If required obligations are blocked, fail before publishing an apparently complete artifact. An explicit eligible-subset mode may generate isolated supported units only after previewing the reduced scope and proving that their required closure is satisfied.

A scaffold/preview output, if offered, must be a distinct artifact type with visible omissions and a non-complete status. It must not pass the same gate as a validated delivery artifact.

### 20.4 Adapter capability contract

| Capability | Required adapter behavior |
|---|---|
| Identity | Declares adapter/version, supported target versions, schema, and toolchain requirements |
| Support query | Reports support per construct/mapping, prerequisites, limitations, and reason for refusal |
| Planning | Contributes target-specific constraints without mutating neutral facts |
| Generation | Consumes a validated plan, emits deterministic supported artifacts, and returns a complete manifest |
| Mapping | Correlates each emitted target component to decisions and source/evidence |
| Static validation | Checks the produced representation within a declared scope |
| External validation hooks | Explicit optional runners for tool, import, and runtime checks with environment records |
| Compatibility | Defines behavior for old plans and target-version changes |

A generic adapter interface is not evidence of another working target. Every future target needs its own supported constructs, golden outputs, negative cases, packaging, and runtime acceptance.

### 20.5 APEX-specific requirements

**BUILD-04.** Reuse and harden existing APEXlang/exporter semantics for supported constructs. Do not introduce a parallel APEX emitter merely because the UI is new.

**BUILD-05.** Prefer native APEX constructs for supported behavior. Do not rebuild Forms runtime through a large generic JavaScript layer to hide unsupported mappings. A legitimate target-specific interaction requires an explicit mapping, capability support, and validation.

**BUILD-06.** A form/DML mapping requires a reviewed table, key, binding, and appropriate target component semantics. A name that resembles a table or procedure is not sufficient evidence.

**BUILD-07.** WHEN-VALIDATE-related behavior, original messages, transaction handling, and other triggers must be supported only to the extent established by current fixtures and accepted mappings. Unsupported logic remains visible as Needs Work/Blocked, not silently discarded.

**BUILD-08.** Do not remove a routine such as the source fixture's `P_CALC_TOTAL_ITENS`, reinterpret it as an existing database procedure, or fabricate its signature without resolution evidence. Ambiguity must remain explicit.

**BUILD-09.** Maintain a module-scoped generation boundary unless a separately accepted multi-Form composition contract proves navigation, shared state, authentication, page/application boundaries, import, and runtime behavior. Estate-wide analysis does not imply consolidated estate-wide generation.

**BUILD-10.** Target version changes invalidate or require rechecking the relevant capabilities, plan, and validation applicability. The chosen version must be visible in UI, CLI, artifacts, and reports.

### 20.6 Generation execution and publication

Resolve the plan and exact inputs, verify authorization and current execution policy, run the supported adapter, validate output schemas/hashes, produce the manifest, then publish through the repository coordinator.

Do not execute external database actions inside a SQLite write transaction. Do not run a newly imported script merely because its manifest claims it is an APEX artifact.

Historical generation may be permitted when explicitly requested against captured historical inputs and allowed by current execution policy. Label the output historical and do not present it as a current-source build.

A build requested as current-source must check the relevant working-source bindings/freshness at start and before publishing a current-source success claim. If the working source changes during the job, preserve the correctly pinned artifact as an as-of result but mark it stale relative to current source, or withhold publication under strict policy. A cached last-checked status must not be described as a fresh scan. These checks occur at meaningful operation boundaries, not by rescanning the entire source tree on every graph click.

### 20.7 Artifact manifest and determinism

Every output manifest must enumerate emitted files/components, output digests, source decisions, selected scope, omitted/partial/blocked work, adapter/toolchain identity, and relevant validation prerequisites.

The deterministic contract includes file bytes and structural ordering for declared deterministic outputs. Strip or isolate only documented volatile metadata; do not normalize away meaningful SQL or target differences to make a test pass.

Regenerating the same plan must not invent new target IDs randomly, reorder components arbitrarily, or depend on absolute workstation paths.

## 21. Validation and source-to-target traceability

### 21.1 Validation levels

| Level | Evidence required | Permitted statement |
|---|---|---|
| Repository/DSL integrity | Schema, reference, parser, binding, and checkpoint verification | The selected project/decision representation is structurally consistent |
| Generation | Deterministic output and complete manifest | Artifacts were emitted for the declared scope |
| Static/tool syntax | Exact validator/tool version, invocation scope, result, and sanitized diagnostics | The stated static/tool check passed |
| APEX import | Actual authorized target environment, version, artifact digest, import result | The artifact imported into that environment |
| Runtime observation | Concrete inputs, exercised behavior, outputs, environment, and evidence | The listed runtime cases were exercised with the recorded results |
| Human UAT | Defined acceptance criteria, authorized reviewer, applicable artifacts, evidence, and recorded decision | The listed criteria were accepted by that reviewer |

**VAL-01.** These levels MUST remain separately visible. Passing one does not automatically pass the next.

**VAL-02.** SQLcl/offline checks must be named for the exact scope they exercised. Never label them runtime equivalence, production readiness, or UAT.

### 21.2 Run record

A validation run must bind validation kind, case/criteria version, input checkpoint, artifact digests, relevant source/decision context, tool version, environment identity/classification, runner/actor provenance, start/end timestamps, outcome, sanitized diagnostics, and evidence references.

Outcomes include `passed`, `failed`, `error`, `not_executed`, `cancelled`, and `not_applicable` where appropriate. An inaccessible environment is not a passing test. `not_applicable` requires a documented reason; it is not a way to eliminate a difficult required case.

### 21.3 Applicability

**VAL-03.** A validation is applicable only to the artifacts, criteria, and context it actually checked. A later changed artifact requires a new run or an explicitly supported equivalence/applicability rule with evidence.

**VAL-04.** Old passing runs remain in history when they become stale. Do not delete them or continue counting them as current passes.

**VAL-05.** Human evidence attachments require scope, actor provenance, visibility policy, and immutable content references. A file named `approved.pdf` does not establish who approved what.

### 21.4 Traceability chain

The core chain is:

```text
Source object and locator
→ analysis entity / fact / relationship
→ evidence
→ recorded modernization decision
→ applicable plan unit
→ emitted target component and artifact digest
→ validation case/run
→ human acceptance criterion, where defined
```

Every link may be inspected in both directions within the caller's permissions. Missing links are explicit data-quality findings. A complete chain is traceability, not proof that all possible runtime behaviors are equivalent.

### 21.5 Oracle environment acceptance

Prepare at least one authorized synthetic/sanitized paired example with an actual declared Forms environment and a declared supported APEX environment before claiming validated migration behavior. Record exact versions rather than assume version labels from the original specification are available.

Exercise the selected supported behavior: query/read, field/record validation, create/update where supported, messages, relevant transaction behavior, security checks, and visual review. Document excluded cases and unsupported constructs.

Unavailable Oracle infrastructure does not prevent local repository/DSL/graph/report development. It does prevent marking the corresponding import/runtime release gate as passed.

## 22. Optional AI and controlled information disclosure

### 22.1 AI role

**AI-01.** Core intake, analysis, exploration, decisions, history, reporting, and supported deterministic generation must work without AI.

**AI-02.** AI may explain selected evidence, summarize measured report data, suggest investigation questions, draft decision alternatives, or propose target layouts. Output is untrusted proposal/annotation data until explicitly reviewed.

**AI-03.** AI must not become the source of authoritative dependency counts, database objects, business rules, approvals, cost estimates, or runtime conclusions.

### 22.2 Context selection and consent

Before an external call, show the chosen provider/destination, selected object IDs, types of data, permitted snippets, estimated size, and whether source bodies are included. Offer metadata-only/no-body sharing where meaningful.

The service constructs the minimal authorized context; it must not accept a client instruction to upload the entire repository without disclosure checks. Respect repository and organization egress rules when supported.

Store API credentials in the supported operating-system credential mechanism, not in `.flm`, portable manifests, reports, Git, logs, or browser storage readable by arbitrary source content.

### 22.3 Proposal records

A proposal record includes origin (`ai`, deterministic rule, or human draft), model/provider identity when applicable, selected input context, generated content, citations to permitted objects where available, uncertainty, creation/expiry policy, and review disposition.

An accepted proposal results in an explicit human decision event preserving the proposal's origin. Do not relabel model-authored content as an extracted fact or conceal its provenance.

A rejected or expired proposal remains subject to the configured retention policy. Whole-project versioning does not require indefinitely retaining every prompt or sensitive model response.

### 22.4 Prompt-injection and asynchronous safety

Treat source comments, XML text, SQL literals, report annotations, and retrieved content as untrusted data. Embedded instructions must not grant network access, filesystem authority, tool execution, or approval rights.

Bind the response to repository, input revision, actor, scope, and request. If the context changed, show the result as an old proposal or discard it according to policy; never apply it to the newly selected project.

### 22.5 Quality measurement

Evaluate AI explanations against known evidence: unsupported claims, incorrect suggestions, missing caveats, and erroneous references. Report any evaluation as specific to the fixture, provider/model, prompt version, and task. A good explanation on one example is not evidence that the engine analyzed more source.

## 23. Security, privacy, access, and operational modes

### 23.1 Local-first release boundary

**SEC-01.** Default to local loopback operation and offline core workflows. Do not instruct users to expose the current local engine publicly to obtain team collaboration.

Local mode may avoid an account/login under a trusted-local-owner model, but it still requires safe Host/Origin behavior, filesystem boundaries, command execution controls, and protection against malicious imported content.

Existing authentication, encryption, rate limiting, MFA, or authorization mechanisms discovered in the baseline must not be removed because the initial release emphasizes local operation. Preserve their tested contracts and describe their actual coverage.

### 23.2 Shared/authenticated mode

Supported server/team mode requires a separate accepted threat model and operational guide covering authentication, session lifecycle, secure cookies, HTTPS at the supported boundary, CSRF, Origin/Host validation, trusted-proxy allowlists, base-path handling, per-route/object authorization, audit, cache isolation, backup, and revocation behavior.

**SEC-02.** Do not advertise server mode based solely on the presence of an RBAC class or a login page. Demonstrate the whole supported deployment path with integration tests.

### 23.3 Permission matrix

Use existing equivalent permission names where possible. The matrix must cover at least:

| Capability | Required distinction |
|---|---|
| Read project | Discover/open permitted repository metadata |
| Read graph metadata | See permitted entity names, relationship metadata, and counts |
| Read source | Read raw source/snippets and source-inclusive evidence |
| Read private annotation | See restricted questions/notes |
| Record/propose decision | Create a human pending decision or proposal |
| Approve decision | Approve/reject/revalidate applicable decisions under policy |
| Generate | Produce permitted target artifacts from eligible scope |
| Validate | Run allowed checks; external execution separately constrained |
| Record acceptance | Attest to defined human acceptance criteria |
| Export/report | Publish a selected disclosure profile and permitted contents |
| Manage repository | Configure policy, roots, recovery, retention, and administrative actions |

**SEC-03.** Every route, CLI path in authenticated mode, job worker, source access, report generation, export, and downloadable artifact must enforce the relevant permission. Obscuring a button is not authorization.

**SEC-04.** Permissions must be checked on both sides of a diff and across every object reached by graph traversal. No cross-project or cross-tenant data may leak through caches, counts, errors, or report appendices.

### 23.4 Input and filesystem defenses

Enforce authorized roots, canonical path containment, symlink policy, source-type limits, XML parser safety, archive entry limits, decompression limits, and explicit maximum depth/size/count budgets. Reject traversal, absolute archive paths, unexpected links, executable imports, and unsupported package schemas.

A source path supplied inside `.flm` or a manifest cannot authorize reading outside the selected roots. External references are inert until resolved through an explicit authorized binding operation.

Use argument arrays for external tools, not shell interpolation. Separate executable selection from source content. A connection string found in legacy code must not be used automatically.

### 23.5 Output and disclosure defenses

**SEC-05.** Default graph summaries, logs, public/review exports, and report metadata must exclude source bodies, credentials, connection strings, literal URLs with tokens, private notes, and sensitive local paths unless a permitted explicit profile includes the appropriate category.

**SEC-06.** Sanitization must cover derived names as well as raw snippets. Hashing or shortening a source literal is not automatically a safe public identifier.

**SEC-07.** Render source-derived content as data in HTML, SVG, Markdown, terminals, PDFs, and CSV. Prevent script execution, unsafe links, terminal escape injection, and spreadsheet formula injection.

**SEC-08.** An exported file can be copied outside FormsLang. Do not claim later permission revocation removes already distributed copies. The export preview must make the disclosure consequence clear.

### 23.6 Integrity and audit claims

The application enforces append-only accepted history through its APIs and storage protocol. A person with full control of the local filesystem may be able to replace the database and object store. Therefore, do not advertise the local repository as tamper-proof.

Content digests detect mismatches relative to a trusted reference. Stronger origin/tamper-evidence claims require actual signatures or externally anchored trusted roots with key management and verification. Such a mechanism must not be implied by a chain of ordinary hashes alone.

Local owner identity is local provenance, not globally verified identity. Imported history carries its original trust classification.

### 23.7 Security acceptance

Required adversarial cases include cross-project IDs, stale permissions, cached privileged queries, imported approval forgery, reused idempotency keys with changed payloads, malicious paths/archives/XML, source-derived XSS, unsafe generated filenames, report data leakage, prompt injection, and cancellation/publication races.

When authenticated mode is in release scope, test at least two isolated principals and two repositories/tenants according to the actual model. A single-user happy-path test is insufficient.

## 24. Legacy migration, installation, and compatibility

### 24.1 Lossless migration mandate

**MIG-01.** Preserve supported 2.x source identities, analyses, decision/review history, annotations, artifacts, and validation/report references through upgrade. The baseline audit establishes the exact supported upgrade matrix.

**MIG-02.** Opening a legacy project must not silently reanalyze sources, rewrite historical certainty, fabricate approval events, or delete unsupported records.

### 24.2 Migration workflow

1. Detect the exact old schema/application version and supported upgrade route.
2. Create and verify a consistent backup and referenced-object inventory.
3. Produce a dry-run migration report with object/event counts, identity mappings, unmapped fields, applicability changes, and downgrade implications.
4. Require an explicit upgrade action.
5. Apply an additive/versioned migration through the coordinator with crash recovery.
6. Produce the initial portable checkpoint from migrated history without reapproving it.
7. Verify counts, IDs, notes, artifacts, source bindings, decision-kind distinctions, and semantic equivalence of preserved fields.
8. Open the new experience with a clear explanation of legacy limitations and optional explicit reanalysis.

### 24.3 Unrepresentable legacy data

**MIG-03.** Any field or record that cannot be mapped must appear in an `UNMAPPED` report with its identity, reason, retained representation, and affected functionality. Preserve the original data for inspection; do not silently drop it.

**MIG-04.** Architectural reviews and conversion approvals remain distinct. A legacy approval is not a new authenticated 3.0 decision merely because a `.flm` file was generated.

**MIG-05.** Older analyses remain read-only with their original resolution/evidence limitations. New relationships are added only through explicit reanalysis and decision applicability review.

### 24.4 Downgrade and rollback

An older application must not write a newer unsupported project schema. Prefer an explicit refusal/read-only mode where implemented. Document rollback through a verified pre-upgrade backup, not by deleting new tables until the old app opens.

Test interruption before backup completion, during schema migration, after accepted state but before portable publication, during installer replacement, and on the first reopen.

### 24.5 Packaged delivery

Retain the verified supported distribution matrix and installer formats. Where Windows EXE/MSI is supported, test clean installation, upgrade over the supported old release, non-ASCII/user-space paths, uninstall behavior, and recovery without deleting user projects.

Bundle or explicitly declare frontend/report-rendering dependencies needed offline. A developer checkout with a globally installed browser/tool is not proof that the packaged product includes or correctly locates that dependency.

**MIG-06.** CLI, Workbench, report renderer, demo fixtures, docs, and installer assets must correspond to the same release commit. Do not combine a new installer with old command documentation or screenshots.

### 24.6 Compatibility inventory

Maintain a table for project schema, checkpoint schema, DSL schema, ecosystem query schema, CLI aliases, response envelopes, target adapter/versions, and report-definition versions. For each, state read/write compatibility, migration behavior, rejection diagnostics, and tests.

## 25. Performance, accessibility, observability, and support

### 25.1 Measurement before optimization claims

Use synthetic fixtures at 100 and 500 Forms with declared entity/relationship/finding counts. Include a corpus authorized for testing when available, but do not assume synthetic performance predicts every customer estate.

Record hardware, operating system, runtime versions, storage type, warm/cold state, dataset identity, concurrency, payload size, CPU, memory, and p50/p95 latency. Keep analysis time distinct from interactive query time and report-rendering time.

### 25.2 Candidate performance and usability gates

| Gate | Initial target / method | Required qualification |
|---|---|---|
| First useful result | Median at most 5 minutes from supported intake to a comprehensible Form relationship | Ratify after baseline; no Oracle/AI account requirement for local exploration |
| Three-step discovery | At least 4 of 5 independent professionals choose a Form, open a relationship, and explain evidence/limits without intervention | Actual sessions on installed build; record mistakes and time |
| Return to context | All 5 participants return to the correct focus/revision in the defined task | No lost decision or draft state |
| Focal/path queries | Warm p95 at most 2 seconds on the declared 500-Form fixture | Includes server work and payload; publish environment and limits |
| Coverage integrity | Zero falsely confirmed relationships/writes in the gate fixtures | Also report known false negatives; zero tested false positives is not universal correctness |
| Deterministic outputs | Byte-identical declared deterministic objects for identical inputs | Separate history/run metadata and documented external-tool exceptions |
| Incremental value | Improve at least two preregistered dimensions versus the defined XML→AI baseline without worsening critical-error rate | Same corpus/questions, controlled order, recorded rubric; no unsupported superiority claim |

The implementation may optimize beyond these values, but it cannot silently relax them after observing a failing milestone. Any change must be recorded with rationale and owner review.

### 25.3 Resource budgets

Before exposing each parser, query, import, job, and renderer, record maximum bytes, rows, depth, execution time, concurrent jobs, and cancellation behavior in the relevant ADR/configuration contract. Defaults must be safe and measurable; clients cannot request unlimited work.

Keep the focal graph budgets defined in Section 10. A large report may stream its data and paginate its appendix rather than load the entire estate into the browser.

### 25.4 Windows stability

Instrument descriptor ownership, file closing, transaction boundaries, project locks, publication replacement, and retry reasons. Repeated tests must assert data integrity and final states, not merely wait longer for a green run.

Do not "fix" a race by disabling the test, removing the assertion, reducing concurrency below real use, or dramatically increasing sleeps without understanding the failure.

### 25.5 Observability

Record structured local diagnostics for operation ID, kind, duration, input-context identifiers, counts where permitted, result, resource-limit reason, and publication/recovery state. Source bodies, secrets, and private notes are excluded by default.

Telemetry outside the local machine is opt-in and must disclose collected categories. A local support bundle is generated through preview and redaction, not by zipping the entire repository.

### 25.6 Accessibility and visual review evidence

Capture representative states for each primary screen: empty, populated, partial, restricted, error, conflict, historical, and narrow layout. Manually test keyboard navigation, focus restoration, report navigation, inspector panels, and a screen reader path.

Automated browser tests must cover asynchronous cross-project/revision responses. Screenshot approval alone does not prove working interaction; end-to-end tests alone do not prove a usable visual hierarchy.

### 25.7 Support documentation

Provide actionable guidance for unsupported input, missing source, stale decisions, conflict resolution, publication recovery, missing external tool, unsupported target capability, report completeness, and backup/restore.

Every diagnostic code shown in a common user-facing failure should have a documented explanation and safe next step. Avoid dumping internal exception names without context.

## 26. Implementation milestones and dependency ordering

### 26.1 Program structure

Treat 3.0 as a coordinated program of reviewable increments, not one enormous implementation patch. Each milestone must produce useful evidence and leave the supported baseline working.

Repository semantics precede wholesale UI construction. A small read-only UX prototype may be explored early against verified fixtures, but it must not determine an unsafe persistence model. Reporting definitions and the first useful report slice start early; the reporting milestone completes the catalog rather than introducing reporting for the first time.

### 26.2 Milestone contracts

| Milestone | Purpose and deliverables | Dependencies | Exit evidence |
|---|---|---|---|
| M0 — Establish the real baseline | Inspect current code/instructions/commit; audit capability claims; reproduce recorded defects; discover tests; create requirement matrix and implementation plan | This specification | Commit-pinned baseline, reuse map, actual test results, explicitly unavailable environments, first bounded change selected |
| M1 — Prove repository semantics | ADR for authority/object identity/publication; transactional object/checkpoint spike; failure injection; portable-state schema; early UX task prototype | M0 | Crash/recovery proof, no split authority, deterministic manifests, explicit import/trust boundaries, prototype task observations |
| M2 — Stabilize facts and exploration queries | Resolve actual extraction defects; preserve legacy semantics; capture placement provenance; schema-aware resolution; bounded graph/search/path services | M0; M1 contracts where persistence changes | Positive/negative fixtures, G-DML/schema regressions, connected focal view, query limits, 100/500-Form measurements |
| M3 — Whole-repository history and exchange | Context pinning, checkpoints, status/log/show/diff, baseline labels, object verification, full/review exports, clean-workspace reopen, initial report dataset | M1 and sufficient M2 domain contracts | Portability/closure tests, import conflicts, no forged approval, external-Git-change detection, recovery and disclosure tests |
| M4 — Decision language and lifecycle | `.flm` parser/serializer/diagnostics; typed mapping schemas; preview/apply/approval/supersession; applicability; origin-local revisions; legacy decision migration | M2–M3 | Round trips, deterministic snapshots, review exercises, stale-binding/conflict tests, bulk atomicity, legacy history preserved |
| M5 — New Workbench and CLI parity | New shell/design system; Explore/Decisions/History/Reports entry points; evidence inspector; semantic diffs; supported commands; legacy-route transition | M2–M4; approved UX findings | End-to-end journeys, context preservation, installed browser tests, keyboard/narrow/error states, CLI/UI equality |
| M6 — Plan, build, and validate | Harden neutral IR/adapter; scope closure; generation manifest; target mapping; validation records/applicability; return from failure to evidence | M3–M5 | Deterministic supported output, blocked cases fail honestly, real tool evidence where available, exact target/version matrix |
| M7 — Complete reporting | Full report catalog/templates; defined metrics; large-scope queries; executive/technical/change/delivery packages; JSON/HTML/Markdown/PDF/CSV; disclosure | Shared report slice from M3 plus M4–M6 data | Reconciled counts, full-scope tests, evidence drill-down, offline and PDF inspection, safe exports, baseline comparisons |
| M8 — Product hardening and acceptance | Performance/concurrency, migration/installers, security, usability, actual Oracle cases, documentation verification | Required M1–M7 scope | Five-person study, paired acceptance cases, repeatable Windows stability, upgrade/restore, adversarial tests, no unclosed required gates |
| M9 — Release preparation and publication | Final README/docs/examples, capability table, changelog, same-commit assets, release evidence register | M8 | All required gates evidenced; owner-authorized version/tag/release; published claims match supported build |

### 26.3 Minimum vertical slice

Before expanding broad feature coverage, complete this small but real path using a synthetic Form and a second linked Form:

```text
Register/capture sources
→ immutable analysis
→ one useful relationship with inspectable evidence
→ one explicit decision and canonical `.flm` change
→ whole-project checkpoint and history
→ CLI/UI agreement
→ one supported target plan/artifact, with honest blocked scope
→ available validation record
→ a technical report with the same counts and traceability
→ export/reopen the declared authorized state
```

A complete narrow slice is more valuable than many disconnected placeholder screens. However, it is not the full 3.0 release; the release matrix still applies.

### 26.4 Suggested PR decomposition

Keep related responsibility boundaries in separate reviewable changes:

| PR group | Intended content |
|---|---|
| P01 | Baseline evidence, spec placement, requirement matrix, scoped plan; no speculative product rewrite |
| P02 | Reproduced extraction/stability regression fixes only; each fix with failing-then-passing tests |
| P03 | Object identity/canonical schemas and transaction/publication protocol |
| P04 | Context/checkpoint/history/integrity operations and safe exchange foundations |
| P05 | Evidence capture/query/index improvements without wholesale UI replacement |
| P06 | DSL parser/serializer and pure domain validation |
| P07 | Decision transactions, approval/applicability/import, legacy migration |
| P08 | Read-only new shell/explorer, accessible list, context inspector, CLI exploration |
| P09 | Decision/history/diff interactions and CLI parity |
| P10 | Planner/adapter/manifest/validation integration |
| P11 | Report definitions/datasets/metrics and initial viewer |
| P12 | Full report renderers/catalog, disclosure, and export verification |
| P13 | Installer/upgrade/concurrency/security hardening and usability fixes |
| P14 | Executable docs, capability claims, release evidence, packaging alignment |

The agent may adjust the sequence for the actual checkout, but it must preserve dependencies and explain consolidation. Do not combine a parser rewrite, schema migration, visual redesign, and release tag into one change.

### 26.5 Progress reporting

At each completed unit, report the commit/branch, requirement IDs addressed, files changed, actual tests run with outcomes, any observed failures, integration status, and next bounded task. Distinguish:

```text
Specified
Implemented locally
Tested with fixtures
Validated in packaged build
Validated with actual external environment
Human-reviewed
Merged
Released
```

These are not synonyms. Never use an old test count or a different branch's green CI as proof of the current change.

## 27. Test corpus and acceptance scenarios

### 27.1 Fixture families

| Fixture | Required content | Purpose |
|---|---|---|
| F-A Showcase | The existing `DEMO_ALL_ELEMENTS`-style fixture, POST-COMMIT, and an unresolved `P_CALC_TOTAL_ITENS`-style routine where available | Evidence navigation without inventing database resolution or runtime order |
| F-B SQL laboratory | Synthetic Forms plus DDL/PLSQL, UPDATE after THEN, and INSERT/DELETE/MERGE cases | Extraction correctness and source-change impact |
| F-C Schema ambiguity | Same-name packages in different schemas, spec/body pairs, qualified/unqualified/ambiguous calls | Identity and resolution boundaries |
| F-D Placement | Multiple windows/canvases/tabs/items, explicit hidden values, missing defaults, conflicting window/canvas declarations | Separate logical ownership and visual placement with provenance |
| F-E Decision history | Approved/pending/rejected/superseded decisions, stale evidence, competing imports, origin-local revision collisions | DSL, trust, chronology, semantic conflict, and applicability |
| F-F APEX eligibility | One supported eligible block plus required unsupported/dynamic logic, known keys, missing keys, and independent scopes | Strict closure, supported generation, and explicit omissions |
| F-G Scale | 100 and 500 synthetic Forms; at least 5,000 findings and 5,000 relationships in the stress profile | Bounded views, full-scope reporting, memory/latency, pagination, and concurrency |
| F-H Upgrade/security | Supported 2.x projects, installer paths, separate principals when applicable, malicious source/export fixtures | Lossless migration, isolation, redaction, and safe rendering |
| F-I Oracle acceptance | Authorized synthetic/sanitized paired Forms/APEX scenario with exact declared versions | Actual import/runtime/acceptance evidence |
| F-J Recovery/portability | Forced crashes, disk-full/permission errors, missing/corrupt objects, Git checkout changes, complete/restricted packages | Whole-repository integrity and honest recovery |

Synthetic fixture labels and counts are test requirements, not statements that those fixtures already exist in the checkout. Reuse equivalent existing fixtures and document the mapping.

### 27.2 Acceptance scenario matrix

| ID | Given / action | Required positive result | Required negative / boundary result |
|---|---|---|---|
| AC-01 | A newcomer imports one supported Form and analyzes it | Opens focal Form, follows a meaningful relation, sees evidence | No AI/APEX/database setup required; no hidden whole-estate graph dependency |
| AC-02 | Two Forms have one observed cross-Form reference | Navigate source to target with exact evidence and Back behavior | No claim that this is an executed user workflow |
| AC-03 | UPDATE follows THEN; other DML constructs coexist | Correct supported read/write classification with provenance | No degraded MERGE/DELETE/INSERT behavior or false write edge |
| AC-04 | Two schemas contain homonymous packages | Distinct qualified identities; supported qualified call resolves correctly | Unqualified ambiguous call remains unresolved/ambiguous |
| AC-05 | Placement includes hidden/default/conflicting attributes | Explicit attributes and supported links are visible | Missing default provenance is not invented; no arbitrary window selection |
| AC-06 | Source/body/dynamic-call target is missing | Show unresolved boundary, reason, and investigation action | No fabricated object, path, or safe-generation claim |
| AC-07 | A legacy snapshot lacks newer capture fields | Opens read-only under original semantics | No silent enrichment; explicit reanalysis required |
| AC-08 | Slow response arrives after switching project/revision | Current context remains intact | No cross-project graph, note, report, or decision contamination |
| AC-09 | A graph exceeds its budget | Connected bounded result, truncation, cursor, and alternative list | No assertion that unshown relationships do not exist |
| AC-10 | Failure is injected at each publication boundary | Accepted state is either absent or correctly recoverable according to commit point | No lost accepted event, fake synchronized checkpoint, or mixed export root |
| AC-11 | Publication fails after decision commit, then recovery runs twice | One accepted decision; canonical bytes restored; stable final state | No duplicate event or import of a partial file as authority |
| AC-12 | One item in a bulk decision batch is invalid or stale | Entire batch rejected with useful diagnostics | No partially approved subset |
| AC-13 | CLI and UI write from the same old revision | One valid commit; second receives controlled conflict | No last-writer-wins or lost rationale |
| AC-14 | Parse/serialize/format valid DSL repeatedly | Same model and deterministic bytes; meaningful diff | Formatting does not approve or rebind decisions |
| AC-15 | DSL contains unknown fields, duplicate IDs, huge nested values, or unsupported versions | Controlled parse/validation diagnostics | No execution, unbounded resource use, or ignored security-relevant field |
| AC-16 | Imported DSL claims an arbitrary reviewer and approved state | Claimed provenance remains inspectable but untrusted | No active approval or generation permission forged |
| AC-17 | Divergent imports change the same subject | Semantic conflict and reviewable alternatives | No silent merge because Git text did not conflict |
| AC-18 | External Git checkout/manual edit changes exchange files | Detect and display reconciliation needed | Live database is neither silently overwritten nor falsely presented as matching checkout |
| AC-19 | A complete authorized package is opened on a clean machine/workspace | Original declared objects/history inspectable without original SQLite/paths | Missing toolchain/trust prerequisites explicitly restrict execution |
| AC-20 | A restricted review/report package omits sources and private notes | Useful permitted review with clear availability/disclosure | No hidden content, names, counts, or source-derived identifiers leaked |
| AC-21 | Backup/restore/GC runs with retained and unreferenced objects | Consistent restore; dry-run and reachable-object retention | No deletion of objects used by history/reports/jobs |
| AC-22 | A mapping is approved but a required dependency is unresolved | Plan blocks the dependent unit and explains why | Approval is not treated as complete eligibility |
| AC-23 | Routine resolution is absent or ambiguous | Remains a blocker or explicit unsupported item | No fabricated DB call or removal of original responsibility |
| AC-24 | Same immutable build inputs generate twice | Matching declared deterministic artifacts and manifests | No random IDs/path/timestamp differences hidden by overbroad normalization |
| AC-25 | Static tool validation passes but no Oracle import/runtime runs | Only that exact level is marked passed | No inferred runtime/UAT/production pass |
| AC-26 | Target validation fails | Follow artifact → plan → decision → source evidence | No dead-end error page or missing revision context |
| AC-27 | Report covers more objects than the visual graph budget | Counts reflect full authorized snapshot query; complete appendix index | No first-page/visible-node count represented as total |
| AC-28 | Metric fixture has stale approvals, zero/unknown denominators, duplicates | Defined ratios and distinct unknown/not-applicable results | No duplicate inflation, zero-as-100%, or stale approval counted current |
| AC-29 | A baseline comparison changes scope and metric definition | Show denominator/cohort/definition differences separately | No false progress conclusion from a shrinking scope |
| AC-30 | Source values contain HTML, script URLs, terminal escapes, and CSV formulas | Safe literal display/export; HTML functions offline | No executable source-derived content or remote asset loading |
| AC-31 | Long tables and evidence lists are rendered to PDF | Readable pagination, headings, wrapping, and working references | No clipped or silently dropped sections; manual page inspection recorded |
| AC-32 | A privileged report/query cache exists, then a restricted user queries | Only current permitted data returned | No cached privilege leakage through data or aggregates |
| AC-33 | AI is disabled or returns hostile/unsupported instructions | Core flows work; response remains an untrusted proposal | No source upload, execution, approval, or fact promotion by model text |
| AC-34 | Permission is revoked while a job is running | Authorized execution/publication policy rechecked; safe result handling | No data exposure through a previously queued job |
| AC-35 | Supported 2.x projects upgrade via packaged installer | IDs/history/notes/artifacts retained; backups and restore verified | No automatic reapproval or silent unmapped-field loss |
| AC-36 | Historical review differs from conversion approval | Distinction survives migration and reporting | No promotion of architectural review to generation approval |
| AC-37 | 100/500-Form load, concurrent queries, and repeated Windows writes | Recorded latency/memory/correctness within ratified budgets | No race hidden by disabled checks or arbitrary sleeps |
| AC-38 | Five non-implementer professionals execute installed-build tasks | Measured discovery, return, uncertainty recognition, and decision tasks satisfy gates | Missing sessions remain an unmet gate; browser tests do not substitute |
| AC-39 | Same corpus/questions are used for FormsLang and XML→AI comparison | Preregistered measurements and controlled order with actual results | No superiority or productivity claim without the measured comparison |
| AC-40 | Final release assets, docs, commands, and screenshots are checked | Same commit/version and executable documented workflow | No future command or mockup represented as released behavior |
| AC-41 | Hashes verify but origin signature/trust is absent | Integrity and origin trust shown separately | No "signed," "tamper-proof," or authenticated-approval claim from hash alone |
| AC-42 | A report is generated from checkpoint C | Report references C; later checkpoint can reference report; unchanged input dependencies do not become stale merely on report publication | No self-referential checkpoint digest or mutation of C |
| AC-43 | Cancellation occurs before/after an accepted transaction | Exact committed/uncommitted state disclosed; safe cleanup | No falsely reported rollback of an accepted event |
| AC-44 | Risky retirement/replacement or bulk action is requested | Payload/revision-bound explicit confirmation | No deletion or scope change caused merely by selecting intent |
| AC-45 | Same context is queried in CLI, Workbench, and reports | Matching IDs, counts, applicability, blockers, and redaction | No surface-specific eligibility rules |
| AC-46 | Non-ASCII paths, case collisions, and renamed files are used | Stable qualified identities and safe path handling | No merging distinct source/database identifiers by normalization |
| AC-47 | A target component maps to multiple source decisions or vice versa | Traceability supports declared many-to-many links and consistent counting units | No overwritten mapping or double-counted completion |
| AC-48 | Report generation is partial or evidence is restricted | Completeness/disclosure states and useful next action remain visible | No full-assessment label on a silently incomplete/redacted dataset |

### 27.3 Test implementation requirements

Each acceptance scenario must map to concrete tests or a named manual protocol, fixture/version, command, expected output, and stored evidence. Automated tests must assert the negative condition as well as the happy path.

Use unit tests for pure serializers, matchers, metrics, and eligibility; integration tests for transactions, filesystem publication, import, and service boundaries; browser tests for real interactions/context; packaged tests for installation/offline behavior; actual Oracle tests for import/runtime; and human sessions for usability.

Test doubles must be clearly distinguished from actual external tools. Never count a screenshot fixture as a runtime Oracle acceptance result.

### 27.4 Human study protocol

Recruit five professionals who did not implement the explorer. Give them a supported packaged build, a fixed fixture, and tasks to locate a Form, follow a dependency, explain evidence/uncertainty, return to context, record a decision, and locate a useful report.

Record completion, intervention, time, critical misunderstandings, failed navigation, and qualitative feedback. Do not coach a participant through a task and count it as independent success. Obtain permission for any recordings and avoid collecting unnecessary personal data.

For the XML→AI comparison, preregister the task/rubric, fix source scope and model/tool configuration, counterbalance order, and report error and traceability alongside time. Do not announce the result before running the study.

## 28. Release gates and definition of done

### 28.1 Required gates

| Gate | Release requirement |
|---|---|
| G-01 Baseline truth | Current capabilities and reused code verified; no unreviewed duplicate engine |
| G-02 Repository integrity | Whole-state checkpoints, object verification, accepted history, publication recovery, and coherent context proven |
| G-03 Portability and Git exchange | Complete authorized reopen, restricted-export limits, conflict detection, external-change reconciliation, and origin-trust rules proven |
| G-04 Facts and evidence | Required positive/negative extraction and graph cases pass; limits and unresolved states remain honest |
| G-05 Language and decisions | Parser/serializer, approvals, applicability, semantic import, bulk atomicity, and meaningful review diffs proven |
| G-06 Workbench and CLI | Complete journeys with shared semantics, context preservation, accessible alternatives, and documented machine contracts |
| G-07 Target delivery | Supported APEX capability scope, deterministic output, plan closure, traceability, and explicit omissions |
| G-08 Validation | Exact static/tool/import/runtime/UAT levels supported by actual evidence for the release's claimed scope |
| G-09 Reporting | Useful report catalog/templates, full-scope reconciliations, evidence navigation, safe offline exports, and inspected PDF output |
| G-10 Migration and packaging | Supported 2.x upgrades, backup/restore, Windows installer paths, and same-commit assets proven |
| G-11 Security | Local threat controls and all advertised authenticated-mode controls tested; privacy maintained across projections |
| G-12 Performance and usability | Ratified fixture budgets and actual five-person acceptance protocol satisfied |
| G-13 Documentation | README, quickstart, examples, limitations, schemas, migration, and release claims agree with the built product |

### 28.2 Gate evidence register

For each gate, maintain:

```text
Gate ID and requirement/scenario links
Scope and supported operating mode
Implementation commit(s)
Fixture/corpus/tool/environment versions
Actual commands and outcomes
Evidence locations
Independent review or manual protocol result, where required
Known limitations and unresolved defects
Status: not started / in progress / passed / failed / blocked / not applicable with approved reason
Owner/reviewer and review date
```

No gate is passed because a document says it should be. No blocked human or Oracle gate is passed because local unit tests are green.

### 28.3 What a release must not do

Do not mark all phases complete merely because a large implementation commit exists. Do not manufacture test counts, mark skipped tests passed, rename a missing feature to "experimental" without an explicit scope decision, or publish a release tag without owner authorization.

Do not claim a supported server mode, consolidated multi-Form target, or additional generator that was not included in the accepted gate evidence.

### 28.4 Preview versus general release

A useful incomplete capability can be published as a clearly labeled preview through an authorized release process. Its exact omissions must be visible in UI, docs, and reports. A preview cannot use the full 3.0 acceptance narrative as if all gates had passed.

The program is allowed to take multiple iterations. The goal is a coherent foundation and demonstrated usefulness, not an early version number.

## 29. README, documentation, and public communication

### 29.1 Documentation is part of the product

**DOC-01.** README and user/developer documentation are required release work, not optional cleanup after coding.

**DOC-02.** Until 3.0 ships, the current-release README must remain true for the actual released version discovered in M0. Add a clearly labeled proposed/in-progress 3.0 direction section without replacing current capabilities with future promises.

**DOC-03.** Do not retain the old source document's 2.2.0 wording if the current release has changed. Inspect the actual release and make the status table accurate.

### 29.2 Proposed direction copy before release

The following is suitable as a direction statement, provided it is clearly labeled as planned/in progress and links are added only after the referenced documents exist in the repository:

> **FormsLang 3.0 direction — in development.** FormsLang is evolving into a versioned modernization repository for Oracle Forms estates. The goal is to keep supported source representations, evidence, modernization decisions, plans, generated artifacts, validation records, and reports in one traceable project. A redesigned Workbench and a capable CLI will operate on the same repository. A small declarative decision language will make modernization choices reviewable in Git. Oracle APEX is the first target; AI remains optional. The current release's capabilities and limitations remain listed separately below.

Do not include dead placeholder links or imply that a design document proves implementation.

### 29.3 Required release README structure

| Section | Required content |
|---|---|
| Product definition | Versioned modernization repository, not merely a converter |
| Primary journey | Understand → Decide → Build → Validate, with Reports and History across the project |
| Real screenshot | Actual packaged version, synthetic/authorized fixture, accurate caption |
| First useful result | Verified installation/demo commands and a short route to a Form relationship and evidence |
| One repository, multiple interfaces | Same checkpoint/IDs in Workbench, CLI, `.flm`, and a report |
| Whole-project versioning | Sources/objects, decisions, checkpoints, history, Git exchange, disclosure, and reproducibility limits |
| Language example | Tested canonical decision example and a meaningful diff |
| Reports | Actual executive/technical examples, definition/provenance access, output formats, and known limits |
| Target support | Explicit supported APEX scope and target/toolchain versions; other targets not claimed |
| Validation meaning | Distinct levels and examples of what has and has not been checked |
| Capability table | Released / preview / planned with implementation and evidence links |
| Limitations | Binary representations, dynamic SQL, missing sources, unsupported constructs, multi-Form generation boundary, trust/security modes |
| Upgrade/security/contribution | Supported migration path, backups, disclosure guidance, development/test instructions, and roadmap |

### 29.4 Candidate release-positioning copy

Use only after the matching capabilities pass their gates:

> **Understand your Oracle Forms estate. Version your modernization decisions. Build and validate what the evidence supports.** FormsLang brings source analysis, dependency exploration, reviewed decisions, target planning, generated artifacts, validation evidence, and technical/executive reports into one traceable modernization repository. Work visually or from the CLI, review portable decision changes in Git, and keep uncertainty visible throughout the project. Oracle APEX is the first supported target. AI can assist, but it is never required to understand or control the migration.

Revise any sentence whose capability is not actually delivered. A polished claim is not more important than a truthful capability table.

### 29.5 Required documentation set

Create or update the repository's equivalent of:

```text
quickstart
concepts/repository-and-checkpoints
concepts/evidence-certainty-and-applicability
source-intake-and-supported-representations
visual-explorer
cli-reference
http-schema-reference
decision-language-reference
decision-review-and-approval
history-diff-and-impact
git-exchange-and-conflicts
backup-restore-and-recovery
report-catalog-and-metric-definitions
report-export-and-disclosure
apex-target-and-capabilities
validation-levels-and-acceptance
migration-2-to-3
security-privacy-and-optional-ai
known-limitations
contributing-and-test-evidence
corporate-deployment (only for actually supported deployment modes)
```

### 29.6 Documentation verification

Examples must be executable against release fixtures or explicitly labeled explanatory. Do not copy illustrative commands from this specification into public installation instructions without implementing and testing them.

Verify internal links, screenshots, schema examples, output filenames, command help, version labels, and report downloads. Capture actual CLI and Workbench outputs from the same repository context for the README walkthrough.

## 30. Agent execution protocol and first implementation assignment

### 30.1 Authority and working behavior

This document defines the requested product direction. The agent must inspect the actual checkout and follow applicable repository instructions. It should not ask the owner to repeat the vision already recorded here.

Proceed with read-only inspection, a grounded plan, and bounded implementation increments within the authorization given for the development environment. Ask for a decision only when an actual unresolved architectural conflict materially changes this contract or an operation requires authority not already provided.

**AGENT-01.** Do not begin by generating dozens of screens, installing a new frontend stack, rewriting the persistence layer wholesale, or declaring all phases complete.

**AGENT-02.** Do not work directly on a protected release branch when the repository workflow expects an isolated feature branch/worktree. Preserve unrelated local work. Do not force reset, delete, rebase others' work, or publish a release without explicit authorization.

**AGENT-03.** Use test-first development for behavior changes and regressions. Demonstrate the failure being addressed, implement the smallest correct change, rerun focused tests, then relevant integration/regression suites.

**AGENT-04.** Use exact evidence, not intention: branch, commit, command, outcome, fixture, environment, and remaining limitations.

### 30.2 First assignment: M0, then a bounded foundation slice

Perform these actions in order:

1. Inspect applicable agent instructions, working-tree state, branch, commit, version, build/test configuration, existing design documents, and the current project model.
2. Read this specification in full. For a context-limited agent, read it in section ranges and keep a requirement/decision ledger; do not start from only the first chunk.
3. Place the canonical spec at `docs/design/formslang-3.0/master-specification.md`, or the established equivalent, without changing its release-claim status.
4. Create the baseline audit, requirement matrix, ADR index, and milestone plan. Populate actual discovered module paths and test commands; do not invent them.
5. Verify the recorded G-DML/schema/Windows issues. Mark already fixed items with evidence and select only real remaining defects.
6. Identify the existing transaction authority, object storage, analysis snapshots, decision history, exporter, report code, and all routes that write project state.
7. Produce the first dependency-ordered implementation plan with small changes and tests. Start with a reproduced foundation defect or the smallest verified repository-contract slice; do not combine both with the UI rewrite.
8. Implement that bounded slice using the applicable repository workflow, with a failing test first where behavior changes.
9. Run actual focused and integration tests. Record failures, skips, and unavailable external environments honestly.
10. Report the completed change, evidence, remaining risks, and next bounded slice. Continue through the plan only while its prerequisites remain valid; do not treat one completed slice as a completed release.

### 30.3 Initial files to create

| File | Purpose |
|---|---|
| `docs/design/formslang-3.0/master-specification.md` | Canonical integrated specification |
| `docs/design/formslang-3.0/baseline-audit.md` | Actual current-repository evidence and reuse/change map |
| `docs/design/formslang-3.0/requirements-matrix.md` | Requirement → implementation → test → evidence → milestone/status |
| `docs/design/formslang-3.0/implementation-plan.md` | Ordered bounded work packages and dependencies |
| `docs/design/formslang-3.0/adr-index.md` | Architecture decisions and required validation evidence |
| `docs/design/formslang-3.0/evidence-register.md` | Actual gate results, not planned success |
| `docs/design/formslang-3.0/session-handoff.md` | Current commit, completed work, constraints, failures, next command/task |

Use existing repository conventions when appropriate and record equivalent paths. Do not create a second competing roadmap hidden elsewhere.

### 30.4 Definition of a completed change

A change is complete only when its implementation exists, tests were actually run, relevant negative cases pass, documentation is updated, compatibility is addressed, and evidence is recorded. "Code written" is not "validated in the installed product."

For a UI change, demonstrate real data and state transitions. For a persistence change, demonstrate recovery and concurrency. For a report change, demonstrate counted rows and provenance. For a target change, demonstrate supported output and appropriate validation.

### 30.5 Independent review

Have a reviewer not responsible for the implementation inspect architectural boundaries, migration safety, truthfulness of claims, negative cases, and test evidence before integrating high-risk changes.

A second agent may review, but its approval is not a substitute for actual external runtime tests or human usability sessions. Record what was reviewed and what was not executed.

### 30.6 Safe parallel work

Parallel work is appropriate only after shared contracts are stable and tasks do not write the same files/state. Use isolated branches/worktrees where supported. Repository coordination, schema changes, and decision semantics require a single agreed contract before parallel UI/report/CLI work.

Do not resolve integration conflicts by dropping tests, weakening schema validation, or allowing presentation surfaces to invent their own rules.

### 30.7 Session handoff contract

Every long-running development handoff must record:

```text
Actual branch/commit and working-tree state
Spec revision and active milestone
Requirements completed, in progress, blocked, and not started
Accepted ADRs and unresolved decisions
Real commands/tests executed and outcomes
Known defects and reproduction steps
Relevant files and exact next bounded task
External environments that remain unavailable
Claims that must not yet appear in README/UI/release notes
```

The next agent must read this handoff and verify the checkout. It must not repeat completed work or assume an earlier summary is current without checking.

## 31. Required architecture decision records

| ADR | Decision to close | Default in this specification | Evidence required before dependent implementation/release |
|---|---|---|---|
| ADR-01 | Repository authority and transaction boundary | SQLite coordinator + immutable objects + canonical explicit export | Crash/failure matrix, no split authority, short transactions, migration compatibility |
| ADR-02 | Object identities and canonicalization | Versioned domain-separated SHA-256; raw source bytes preserved | Golden byte examples, duplicate/collision behavior, Unicode/ordering tests, distinction from signatures |
| ADR-03 | Checkpoint and portable-history schema | Whole-state manifests with acyclic references and declared closure | Clean-workspace reopen, history coverage, report/artifact publication acyclicity |
| ADR-04 | Trust of imported history and approvals | Preserve provenance; no approval by imported text alone | Forged actor/state tests, trusted-backup versus untrusted-exchange behavior |
| ADR-05 | DSL grammar and versioning | Small strict `.flm` format with typed mappings | Parser/fuzz/round-trip tests, meaningful PR review exercises, schema compatibility |
| ADR-06 | Cross-revision entity identity | Exact immutable identity + explicit locator/correspondence model | Rename/move/schema/overload/root/engine-change fixtures; no silent rebind |
| ADR-07 | Git exchange synchronization | Explicit preview/apply; external-change detection; no native Git clone | Branch/worktree/checkout/conflict tests; origin-local revision handling |
| ADR-08 | Frontend technology and component split | Reuse a lightweight maintainable stack unless a measured alternative wins | Bundle/offline/installer/security/accessibility/CI tradeoffs and real journey prototype |
| ADR-09 | Report definitions, metrics, and renderers | Shared domain data pipeline and versioned definitions | Reconciliations, complete authorized scope, safe offline HTML/PDF/CSV, packaging tests |
| ADR-10 | APEX adapter and generation granularity | Existing supported module-scoped capabilities first | Native-component mapping, closure, deterministic output, exact Oracle/target evidence |
| ADR-11 | Local versus supported team/server mode | Local-first; broader mode separately gated | Threat model, route/action matrix, cache isolation, proxy/configuration and operational tests |
| ADR-12 | Backup/restore/retention and migration | Consistent backup, explicit migration, verified restore, reachable-object protection | Interrupted upgrade/restore/GC tests and legacy data reconciliation |
| ADR-13 | CLI/API compatibility and errors | Shared schemas, origin-aware fences, stable exit/error meanings | Old-command compatibility, JSON/stdout/stderr tests, cursor and conflict behavior |
| ADR-14 | Performance and resource limits | Bounded queries and ratified fixture-specific budgets | Hardware/fixture baseline, p50/p95/memory, Windows stability, limit and cancellation tests |
| ADR-15 | Validation applicability and acceptance | Artifact/case/environment-bound evidence; separate UAT | Changed-artifact/criteria tests, stale-run handling, human acceptance provenance |

An ADR must state context, alternatives, selected decision, consequences, implementation boundary, tests, and compatibility. "We chose this because it is modern" is not a sufficient rationale.

## 32. Original-specification coverage and reference register

### 32.1 Consolidation and deliberate refinements

This specification is an integrated English implementation contract rather than a line-by-line translation. It preserves the original direction and constraints while incorporating the owner's strengthened repository/reporting mandate.

| Original section / direction | Covered here | Integration note |
|---|---|---|
| 0 — Product direction and UI replacement | 1–5, 16–17 | Preserved four-step journey; whole repository is the versioned object |
| 1 — Verifiable baseline and reuse | 3, 24, 30 | Baseline claims are explicitly historical until the implementation agent checks the current commit |
| 2 — Objectives, non-goals, metrics | 1–2, 19, 25, 28 | Preserved measurable usefulness and honest support boundaries |
| 3 — Mental model and navigation | 16–17 | Reports and History promoted to primary cross-cutting surfaces |
| 4 — Facts, evidence, graph, revisions | 4, 6, 9–10 | Preserved certainty/resolution distinctions and immutable analysis; added whole-state context |
| 5 — Decision language | 7–8, 11–12, 24 | Expanded grammar/trust/import/lifecycle; local counters distinguished from portable identity |
| 6 — IR and APEX target | 20–21 | Preserved supported-scope generation and separate validation levels |
| 7 — CLI | 14–15 | Expanded repository/history/report operations and explicit machine contracts |
| 8 — Optional AI | 22–23 | Preserved human control, selected context, and provenance |
| 9 — Application architecture/security | 5–8, 13, 15, 23 | Specified transaction/publication protocol, object store, access, and recovery |
| 10 — Execution plan | 26, 30 | Reorganized into repository-first, report-integrated milestones and small PRs |
| 11 — Acceptance fixtures | 27–28 | Preserved original cases and added portability, reporting, trust, and crash scenarios |
| 12 — README and communication | 29 | Current-release truth remains mandatory; release copy explicitly conditional |
| 13 — Open decisions/ADRs | 31 | Specific defaults and evidence requirements replace unbounded architectural ambiguity |
| 14 — Final definition of done | 28, 33 | Expanded to whole-project history, portable reopen, and comprehensive reporting |
| Whole-repository addendum | 1, 5–8, 17–19, 26–28 | Sources through reports/history correlated and versioned together |
| First-class reporting addendum | 16–19, 25–29 | Report center, catalog, definitions, formats, privacy, and acceptance gates made mandatory |

Important refinements are intentional: hashes are not called signatures; local decision counters are not treated as globally unique revision identity; an imported reviewer string does not approve anything; reports do not create circular checkpoint references; historical approval and current applicability are separate; and complete versioning does not mean uncontrolled publication of private source.

### 32.2 Owner-provided design sources

**[B1]** `FormsLang-3.0-Especificacao-de-Produto-e-Arquitetura.md`, dated September 25, 2026, 463 source lines, read in full for this consolidation. This is the original product/experience/architecture specification. Its repository/version observations are baseline statements, not a live audit performed while producing this English document.

**[B2]** The owner's subsequent direction in the conversation: FormsLang should become a Git-like structure containing the entire modernization universe, versioned with its own language, a highly useful visual experience, and comprehensive reports, prioritizing the correct long-term foundation over speed.

**[B3]** The architectural direction addendum accepted as the basis for this request: a versioned modernization repository; `.flm` as the decision representation rather than the entire repository; Workbench/CLI/reports as shared-model projections; full traceability; reporting as a primary capability.

### 32.3 Primary technical references

These references support specific technical constraints; they are not evidence that FormsLang implements them. Consult the exact supported versions when implementing.

| Reference | Source | Relevant constraint |
|---|---|---|
| T1 | SQLite, Atomic Commit | Database transaction assumptions and crash behavior; application-level filesystem publication still needs its own protocol |
| T2 | SQLite, Write-Ahead Logging | WAL files, concurrency, and same-host/shared-memory/storage limitations |
| T3 | SQLite, Online Backup API | Consistent backup of an active SQLite database |
| T4 | Git, gitignore | Ignoring files does not untrack files already committed/tracked |
| T5 | Git, git-merge | Real Git merge/conflict workflow; FormsLang adds independent domain consistency checks |
| T6 | W3C, WCAG 2.2 | Accessibility target and relevant keyboard, focus, contrast, reflow, and labeling behavior |

[T1]: https://www.sqlite.org/atomiccommit.html
[T2]: https://www.sqlite.org/wal.html
[T3]: https://www.sqlite.org/backup.html
[T4]: https://git-scm.com/docs/gitignore
[T5]: https://git-scm.com/docs/git-merge
[T6]: https://www.w3.org/TR/WCAG22/

### 32.4 Repository evidence to collect during implementation

Inspect the source paths listed in Section 3 and record commit-pinned links/paths in the baseline and gate registers. In particular, reconcile the actual README, roadmap, project model, decision review, ecosystem contract, gap analysis, performance fixtures, Forms-to-APEX behavior, security guide, limitations, and release assets.

Do not cite a moving `main` branch as proof that a historical claim was true at a particular release. Pin evidence to the implementation commit/release when practical.

## 33. Final acceptance narrative

A professional who did not build FormsLang installs the supported 3.0 package and creates a modernization project. Without configuring AI, choosing APEX, or connecting a database, they add a supported representation of one or more Forms and obtain a useful view of the legacy application.

They select a Form, inspect its logical and visual components, follow a relationship to code or data, and understand what the available source proves and what remains unknown. The graph is clear and bounded, and the equivalent list is equally useful.

They record a modernization choice with rationale and evidence. The same decision appears in the Workbench, CLI, canonical `.flm`, and domain history. The reviewer can see a meaningful diff. A whole-project checkpoint preserves the analysis, source references, decision state, history, and related outputs—not merely the decision text.

When the source changes, FormsLang shows the source and analysis differences, identifies potentially affected decisions and artifacts, and requires appropriate revalidation. It does not silently transfer approval to a new entity or pretend an unresolved dependency is safe.

The professional selects supported target scope, reviews the plan and dependency closure, generates an eligible APEX artifact, and sees every emitted, omitted, unsupported, and blocked unit. Validation levels remain distinct, and failures lead back to the original decision and evidence.

They open Reports directly, generate an executive or technical assessment, inspect how each number was calculated, and navigate from a conclusion to permitted evidence. The report includes its checkpoint, scope, definitions, coverage, unknowns, and validation limitations. A PDF or offline HTML package remains understandable outside the running application.

They export an authorized whole-project package and reopen its declared contents in a clean workspace. Original machine paths and the original SQLite file are not required to inspect the preserved history. Missing private objects, missing external toolchains, and unverified imported approvals remain explicit. Git can version the permitted portable representations without becoming a hidden second operational authority.

A publication failure or concurrent edit does not destroy accepted work. Recovery preserves the recorded events, restores the intended canonical files, and reports exactly what happened. Upgrade from a supported 2.x project preserves existing data and does not invent new approvals.

**Only when these behaviors are supported by the required automated, packaged, external-environment, and human evidence may the product be represented as the completed FormsLang 3.0 described here.**

**The objective is not a faster way to produce an unreviewed conversion. The objective is a durable, understandable, inspectable, and useful repository for controlling the entire modernization effort.**

---

**End of master specification.**
