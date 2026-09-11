# Modernization Blueprint — engineering plan

Audit baseline: `791d980`, FormsLang 1.2.2. Work isolated on
`codex/formslang-20260910`; the original checkout is not modified.

## 1. Current architecture

The Python engine has no third-party runtime dependencies. `parser.py` reads
Forms2XML into `model.FormModule` (triggers, program units, blocks/items, LOVs,
record groups, relations, canvases/windows). Binary conversion uses the user's
Oracle installation through `oracle.py`, staging copies outside the source tree.
The model has structural owners but no XML byte/line offsets. Code evidence can
have **body-relative** lines, never invented XML line numbers.

`plsql.py` is a lexical analyzer, not a PL/SQL compiler. `rules.py` supplies the
execution verdict and compatibility class. `assess.py` aggregates portfolios and
fingerprints repeated code, including its explicit 15% copy-review assumption.
`analysis.py` versions the risk/behavior/catalog/sensitive-data stack. `depgraph.py`
already supplies structural edges, adjacency indexes and bounded exploration.
Its identities are module-local; SQL reads/writes and schema-qualified calls are
not distinguished. Literal/comment handling is too narrow for evidence extraction.

`Store` is an additive SQLite session schema with append-only human decisions,
cached analysis/module graphs and content-sensitive test reviews. The Workbench
is one local HTTP server and a self-contained, build-free HTML/JS UI assembled
from `ui/`. It already has Project, dependency, review and test panels.
`projects.py`/`authstore.py` separately register tenant-owned session databases;
RBAC and project-path resolution must guard new Blueprint routes in auth mode.

Doc renders the parsed structure. Diff compares module properties and code.
Preview and APEX export share `apexlayout.py`; `apexlang.py` exports approved
work to reproducible APEX 26.1 ZIPs. SQLcl validation/import is opt-in and owns
its own credential boundary. Blueprint architecture approval cannot approve code,
confirm database keys, create endpoints, invoke SQLcl or claim runtime parity.

AI is an optional provider abstraction (including Ollama), gated by egress policy;
keys use environment/OS storage. Sensitive-data findings redact matched values.
Static analysis is local. Reports are confidential source-derived artifacts.
Tests cover parser, corpus goldens, analysis, UI/API, auth/CSRF/IDOR, sessions,
exports and SQLcl failures. CI runs Python 3.10–3.13 on Linux/Windows, ruff,
reproducible exports and real SQLcl compiler gates. Roadmap explicitly deferred
cross-module Workbench analysis and runtime test execution; this work addresses
the former, not the latter.

## 2. Reusable components

Reuse FormModule, Forms2XML conversion, structural dependency graph, catalog,
`analyze_unit`, assessment/dedup, readiness formula, Store, provider/policy and
Workbench modal/API conventions. Add an evidence-oriented lexical interface to
`plsql.py` without changing legacy scoring/fingerprint semantics in this release.
Reuse graph structural construction with code extraction switched off; enrich
and namespace it for applications, using indexed adjacency for exploration.

## 3. Missing capabilities

Application scope and shared targets; source-backed call/data-access events;
epistemic labels; business-rule candidates; architectural recommendations and API
reuse ranking; optional conservative enterprise patterns; architecture and
coverage artifacts; content-versioned architecture reviews; portfolio UI.
Database object existence, synonym resolution, privileges, external callers and
callee coupling remain unknown unless supplied local evidence establishes them.

## 4. Data model

Versioned JSON Blueprint with application identity, entities, evidence, edges,
findings, architecture, API candidates, coverage, assessment and limitations.
Stable content-independent entity IDs namespace local components by source key;
shared reference targets retain full normalized schema-qualified names. Review
revisions hash deterministic findings and dependency context; source changes
invalidate prior decisions, while preserving history. FACT describes observed
syntax/properties, INFERENCE classifications, ASSUMPTION target prerequisites,
UNKNOWN unresolved runtime/database behavior. Unqualified references are shared
symbolic names, not assertions that schemas resolve to one physical object.

## 5. Analysis changes

Offset-preserving tokenization handles comments, escaped strings and Oracle
alternative quoting. Extract conservative calls, static SQL read/write targets,
binds and literal Forms targets; computed targets remain unresolved. Avoid
promoting lexical ambiguity (CTEs, dynamic SQL, quoted identifiers) into database
facts. Conditional rejection is a business-rule candidate, not a business meaning.
Catalog verdict/class stays authoritative for conversion execution; the new
decision is an architectural recommendation. No automatic DROP of mixed bodies.
Reuse `readiness/1` as migration-work progress with full formula, alongside
explicit unknowns and catalog debt; never advertise it as safety probability.

## 6. UI

Add Blueprint entry to existing Workbench: application summary, source/failure
scope, strategy, readiness explanation, architecture, API ranking and searchable
dependency inventory with bounded neighborhoods. Inspect evidence, classification,
recommendation and review history. Approve/modify/reject/defer architecture;
record coverage separately with human evidence. Optional AI explanation is a
clearly marked, sanitized proposal, never a mutation of deterministic results.

## 7. CLI

`formslang blueprint <file|directory> -o out`, recursive by default, optional
enterprise context and local database metadata. Reuse Oracle adapter with
isolated content-addressed caches. Write `out/modernization/` JSON/HTML/Markdown/
Mermaid artifacts plus a resumable session DB. Support exporting a Blueprint
session after review. Failures are explicit and cause nonzero exit status;
successfully parsed modules remain inspectable. Artifacts are deterministic.

## 8. Compatibility risks

Keep existing commands, verdicts, IDs, scores and APEX bytes unchanged. New graph
option defaults to legacy behavior. Do not change fingerprint semantics silently.
Package spec/body identities and same-named modules need independent IDs. Code
and metadata are untrusted: escaped HTML, fixed output filenames, no source-driven
paths or Mermaid syntax, no remote assets. Bound explorer output; disclose limits.

## 9. Sessions and migrations

Add Blueprint snapshot/review tables via Store's existing CREATE IF NOT EXISTS
mechanism. Older sessions open unchanged. Blueprint-only portfolio sessions do
not synthesize conversion approvals/tasks. Existing one-module sessions can build
a Blueprint from reachable XML; persisted snapshots survive missing sources and
state their provenance. A different finding revision makes old review stale.
Auth mode must resolve a registered project to the current session before access;
deny unregistered/foreign sessions rather than trusting client-supplied ownership.

## 10. Test strategy and sequence

Establish existing test baseline. Implement lexer/model/engine, then artifacts/CLI,
Store reviews, Workbench UI/API and optional AI. Test multi-form shared targets,
schema-qualified calls, comments/literals/declarations, short units, read/write,
dynamic and unresolved calls, business-rule false positives, API score explanation,
enterprise opt-in, deterministic bytes, partial input failures, stale reviews and
coverage separation. Test HTML/diagram injection, sanitized AI/policy and auth
authorization. Run full pytest and ruff plus CLI corpus smoke and JS syntax check.
Document formulas, schemas, boundaries and remaining uncertainty. No release,
deployment or changes to the other agent's branch are part of this task.

## Implementation and validation record

Implemented the application model as a versioned JSON contract, reusing the
existing structural graph builder and CodeAnalysis/risk/catalog contracts.
Blueprint uses the located lexer for its code facts and scores; legacy assessment
and fingerprint semantics remain unchanged. The bounded explorer performs one-hop
inspection with filters and pagination. Architectural decisions and their source/
dependency snapshots use additive Store tables; human decisions do not overwrite
the deterministic recommendation or approve conversion code. Engine and schema
versions are independent. Output is bound to its source session and rejects
escaping symlinks; generated Markdown also escapes source-provided image/link syntax.

Validation on Windows / Python 3.13:

- Baseline before implementation: 994 passed, 1 skipped.
- Full suite after integration: 1,029 passed, 2 skipped. The additional skip is
  the symlink-creation test on a Windows account without that privilege.
- Focused Blueprint checks after final report escaping: 31 passed, 1 skipped.
- Ruff, JavaScript syntax checking and `git diff --check` pass.
- The five-module synthetic corpus generates a complete portfolio without source
  failures (513 entities, 930 graph edges, 487 review findings).
- Headless Edge: actual overview, trigger filtering, source evidence and persisted
  DEFER review exercised with no JavaScript exceptions. Blueprint modal fits both
  the desktop viewport and a 720px viewport. The existing review page underneath
  the modal still has a narrow-width overflow in its original comment/reviewer row;
  this does not overflow the Blueprint panel and is outside this change.
- Browser, configuration and session data used isolated temporary directories;
  the temporary server/browser were stopped after validation.

No live Oracle Forms conversion, SQLcl import or runtime parity test was performed
for this feature. Binary routing/cache isolation is covered through the existing
Oracle adapter with synthetic test doubles; existing export/import tests remain
green. These limits are also stated in the product guide.
