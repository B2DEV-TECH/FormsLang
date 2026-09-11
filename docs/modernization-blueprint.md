# Modernization Blueprint

Blueprint describes an application's observed structure, dependencies and
modernization choices before implementation. It extends the existing Workbench,
catalog, assessment and session database. It does not execute Forms, query a
database, create ORDS endpoints or certify functional parity.

## Run locally

```console
formslang blueprint ORDERS.xml -o out
formslang blueprint ORDERS.fmb -o out --oracle-home C:\Oracle\Middleware
formslang blueprint ./application -o out --title Purchasing
formslang blueprint ./application -o out --enterprise-context --metadata inventory.json
formslang workbench out/blueprint.session.db
formslang blueprint out/blueprint.session.db -o reviewed-out
```

Directories are recursive unless `--no-recursive` is supplied. Forms2XML files
need no Oracle installation; binaries use the same user-installed Oracle
converter as assessment. Binaries and matching XML in the same directory follow
assessment's binary-first convention. The conversion cache isolates each binary
content hash, including matching filenames from different directories. Inputs
are not overwritten. Sources over 256 MiB are refused explicitly.

Exit status is **0** for a complete analysis, **1** for partial/failed sources
with an inspectable Blueprint, and **2** for invalid input/output configuration.
Failed sources remain listed; counts cover only successful inputs. A directory
with no supported sources fails. Menus/libraries not representable as FormModule
remain explicit parser failures, not invented Forms. An output directory nested
under the source is excluded from collection.

In the Workbench, use **Blueprint**, then **Analyze locally** on the open module
or supply an application directory. Open the generated session to resume a
portfolio. **Regenerate** rereads available module XML; portfolio regeneration
uses the CLI or the application-directory input. Stored snapshots remain readable
when source files are unavailable. Snapshot content does not silently follow
later source edits: regenerate after changes. Use **Write artifacts** to export
the current review state.

## Local optional database/PL/SQL inventory

An optional UTF-8 JSON file (up to 32 MiB) supplies user-owned metadata. No Oracle
metadata, proprietary source or DDL is distributed. Example **synthetic** input:

```json
{
  "objects": [
    {"name": "APP.ORDERS", "type": "TABLE", "source": "local-inventory.json"},
    {"name": "APP.ORDER_POLICY", "type": "PACKAGE", "source": "reviewed-local-export.sql",
     "body": "procedure check_order is begin null; end;"}
  ]
}
```

Supported object types: TABLE, VIEW, PACKAGE, PROCEDURE, FUNCTION, SEQUENCE.
`body` is optional PL/SQL text, analyzed locally using the same pipeline. The
`source` field is a provenance label, not an instruction to read or execute a
file. Metadata establishes **what the supplied inventory states**, not live
database existence. Exact qualified name matches link references to inventory
objects. It does not resolve synonyms, schemas, overloads or package members.
Package-body signals cannot prove an individual routine's coupling is absent.

## Artifacts and schema

`out/blueprint.session.db` uses the existing Store. `out/modernization/` contains:

- `blueprint.json`: full versioned knowledge model, evidence and human reviews.
- `blueprint.html`: self-contained offline report/search, no external assets.
- `architecture.json`, `dependencies.json`, `business-rules.json`,
  `modernization-plan.json`: focused machine-readable views.
- `reports/`: executive summary, architecture, dependency analysis, business-rule
  inventory, modernization plan, risk and modernization coverage, in Markdown.
- `diagrams/`: current architecture, proposed target and dependency Mermaid.

`schema_version: blueprint/1` is additive to the existing 1.x contracts.
`engine_version` identifies the Blueprint rules, evidence lexer and existing
catalog/risk/behavior stack independently of the schema. Entity IDs hash the
entity type, source key and structural identity; external symbolic references use
their full normalized qualified names. Package and routine references shared by
several Forms are represented once. Unqualified identical names are shared
**symbols**, not a claim of one physical object across database schemas.
Duplicate module names in different directories have distinct local identities.
Package specifications and bodies retain separate source identities.

Each edge has source/target entity IDs, type, epistemic level and evidence IDs.
Evidence contains source key, component, text and optional decoded-body line and
character offsets. They are **not XML file line numbers**. Facts about source
syntax do not prove that a branch executes or that a call succeeds. The lexer
handles ordinary strings, escaped quotes, Oracle alternative quoting and comments.
It distinguishes static READS/WRITES, literal navigation targets, bind references,
sequences, transaction statements and qualified invocation syntax. It is not a
PL/SQL compiler: typed collection indexing may look like a routine invocation;
quoted identifiers, database links, complex SQL/CTEs, dynamic SQL, overloads and
computed targets require additional review. The UI discloses bounded results;
the JSON retains the full graph. Mermaid limits its overview to 200 dependency
edges and uses inert IDs to avoid injecting source text into diagram syntax.

Generation has no clock/randomness/network input. Identical ordered-independent
modules/options/reviews produce identical artifact bytes. The SQLite review audit
does carry real reviewer timestamps. Existing assessment fingerprints are reused
as normalization-based reuse signals; they are not proofs of semantic identity
(legacy normalization uppercases literals). Existing assessment/fingerprint behavior
and APEX export bytes are unchanged. Blueprint reuses the same CodeAnalysis,
catalog, risk and behavior models with improved lexical event counts, versioned
separately. This prevents a string containing a built-in name from resurfacing
as a false risk dependency. Legacy assessment totals remain a separate
compatibility view; their normalization rules are not silently changed.

## Evidence and business-rule candidates

- **FACT**: observed source syntax, declaration or supplied metadata statement.
- **INFERENCE**: rule classification, package interpretation, API candidacy or
  modernization recommendation derived from those facts.
- **ASSUMPTION**: prerequisites such as target availability, requiring confirmation.
- **UNKNOWN**: unresolved targets, callee bodies, privileges, external consumers
  and runtime equivalence.

A validation trigger alone is not a business rule. The initial candidate detector
looks for a conditional (`IF`/`CASE`) and rejection (`RAISE FORM_TRIGGER_FAILURE`
or `RAISE_APPLICATION_ERROR`) within a body. This is **co-occurrence**, not
control-flow proof that the condition causes rejection. It retains condition,
rejection, call and bind evidence. It does not invent the business meaning of
the predicate. Read/reference binds are candidate inputs; assignment targets are
kept separately. Classification can include several categories: UI behavior,
business rule, data access, navigation, transaction control, integration,
framework/infrastructure and unknown. Inventory candidate counts are not a count
of all actual application business rules.

## Decisions and API ranking

The existing execution verdict answers how a construct crosses to APEX:
AUTO / ASSISTED / MANUAL / DROP / UNKNOWN. Its catalog compatibility classes
remain authoritative. Blueprint's architectural recommendation answers what to
do with the capability: PRESERVE / CONVERT / REFACTOR / WRAP_AS_API / DROP /
MANUAL_REVIEW / UNKNOWN. An AUTO validation can warrant REFACTOR because its
rule is coupled to a UI lifecycle; AUTO never implies safe.

The deterministic rules give integration/transaction/unsupported behavior human
review priority, conditional rejection/catalog redesign a refactoring candidate,
and catalog-supported simple components a conversion candidate. A standalone
program unit may be a preservation candidate only when the available analysis
detects no Forms coupling or unresolved dependencies, with that exact qualification.
A package reference without a body is never declared safe to preserve. DROP is
only suggested for a complete body consisting of catalog NOT_REQUIRED calls;
mixed bodies are not dropped. WRAP_AS_API is available as a human architecture
choice; a reuse ranking alone does not decide that an API must exist.

An API candidate is a qualified invocation referenced by at least two Forms.
Its **reuse-priority index**, maximum 13, is:

```text
2 × min(4, distinct Forms − 1)
  + min(4, distinct caller units − 1)
  + 1 for qualified invocation syntax
```

The small integer weights prioritize breadth across Forms, then caller reuse;
caps prevent a single popular symbol dominating a review queue indefinitely.
This is a documented ranking heuristic, not calibrated probability, API quality
or safety. Call-site counts are deduplicated by caller unit. Unknown callee
coupling, parameter complexity, privileges and transaction ownership receive **no
invented score**; they are explicit review questions. ORDS is mentioned only as
an optional boundary when an HTTP consumer justifies it. No endpoint is generated.

Optional enterprise context reports conservative underscore-prefixed naming
signals (FND/AP/AR/PO/GL/FA/INV/ONT/HR) and XX-style custom names, with evidence,
involved modules and possible domains. A prefix is never proof of an EBS
installation, standard Oracle ownership or a particular business application.

## Readiness and coverage

Blueprint reuses **readiness/1**, labeled **Migration work progress**, instead of
inventing another safety score:

```text
30 × reviewed-unit ratio + 25 × approved-unit ratio
  + 20 × (1 − mean risk weight)
  + 15 × mean behavior credit + 10 × reviewed-test-specification ratio
```

Risk weights: LOW 0, MEDIUM .34, HIGH .67, CRITICAL 1; missing analysis 1.
Behavior credit: PRESERVED 1, CHANGED .5, UNCERTAIN/missing 0. All source units
are in the denominator. No units/tests means zero for the corresponding ratio.
The existing score is displayed to one decimal with its full components; it is
not a probability of successful migration. Catalog debt, existing portfolio
assessment and published risk formula remain available in JSON. Unresolved and
failed sources are explicit. A fresh CLI Blueprint has no conversion approvals
or test decisions. A module built inside an existing Workbench session can reuse
conversion review/test decisions only against identical source bodies and current
test specifications; risk/behavior are freshly deterministic, never AI-derived.

Architecture review has APPROVE / MODIFY / REJECT / DEFER, a reviewer and a
required rationale. MODIFY stores a separate human recommendation and target;
the engine's original recommendation remains intact. Reviews are bound to a
hash of analysis/options/source/dependency context. Regeneration after changes
makes old decisions STALE, preserves their history (including the finding,
evidence and dependency snapshot reviewed at the time) and resets their effective
coverage. An engine mismatch requires regeneration before new review.

Approving architecture does not approve conversion code, database keys, export
SQL, AI text or coverage. Coverage starts REQUIRES_REVIEW. Recording PRESERVED,
CONVERTED, REFACTORED or DROPPED_INTENTIONALLY requires human implementation
evidence, such as a reviewed change/test reference. UNSUPPORTED and UNKNOWN are
also available. These are human declarations, not executed verification.

## Privacy, authorization and AI

Analysis, evidence extraction and artifacts run locally. Reports contain
source-derived confidential information and follow the same handling as Doc and
session exports. No telemetry, remote fonts, CDN, database connection or cloud
AI is added. Output names are fixed and path containment is checked. HTML and
Markdown escape source content; the browser never executes source-provided markup.

The optional **Request advisory explanation** action explicitly sends only an
allowlisted, anonymized structure: component/dependency types and counts,
classification and recommendation. Source names, paths, code, literals and human
review comments are excluded. It uses the already configured provider (including
local Ollama) and rechecks existing enterprise egress policy. The response is
unapproved text, cannot change findings/reviews/coverage/readiness/risk, and is not
an official architecture decision. There is no mandatory AI step.

New Blueprint routes inherit Host, content-type, authentication, scope and CSRF
checks. Auth mode additionally requires the current session to be a registered
project in the active organization, rechecks membership/RBAC, and derives reviewer
identity from the authenticated user. Viewer mutation/export without permission
is refused; unregistered/foreign sessions are hidden. Arbitrary directory-based
portfolio opening is disabled in auth mode: generate through CLI and register the
resulting session using the existing project flow. No new tenant path resolver
or permission system is introduced.

## CI and further evidence

Run `python -m pytest -q` and `python -m ruff check .`. The Blueprint suite covers
multi-form identities/reuse, source lexical traps, recommendation evidence,
deterministic artifacts, partial failures, review invalidation, coverage, provider
privacy/policy and Workbench authorization. Existing APEX/SQLcl gates remain
unchanged. Runtime parity, synonym/overload resolution, executed regression tests,
automatic ORDS generation and database discovery are not implemented or implied.

### Guided Workbench experience

The Blueprint opens with **Understand**, **Inspect & decide**, and **Modernization
plan**. The first view shows source-backed connections and a bounded reading
queue: stale reviews, integrations/transactions, rule candidates, then other
code. This ordering is navigation advice, not a new risk score. Each arrow is
an observed dependency, not a runtime execution sequence.

**Explain this application** explicitly asks the configured provider for a
structured architecture briefing. The request contains anonymous component
aliases, types, classifications and observed relationships; source code, names,
paths, literals, reviewer comments and credentials are excluded. Aliases resolve
back to local names after the response, and unknown component links are rejected.
The provider cannot establish business meaning without source semantics, so it
must explain structural evidence and identify what to investigate, not invent
business purpose. Echo asks the user to configure a real model. Existing egress
policy applies, including local-provider support and enterprise cloud blocking.

The explanation stays an unapproved proposal. It is cached in the current browser
page for the source revision/provider and can be saved as a separate HTML briefing.
It does not change deterministic reports, readiness, coverage or human decisions.
A page reload clears that cache. No AI request is made just by opening Blueprint.

Component inspection shows the decoded PL/SQL body when present in the snapshot
(up to 64,000 characters, with truncation indicated). Existing snapshots without
this optional field retain their evidence excerpts until regenerated. Recording
an architecture decision and claiming implementation coverage remain separate.
