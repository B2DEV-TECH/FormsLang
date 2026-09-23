# FormsLang 2.1 Estate Intelligence Design Specification

> **Status (PR #11 remediation):** in development for FormsLang 2.1, not released. Sections 3 and 5 were revised to match the implementation: hotspots are projections of the saved Blueprint, severities are bounded by evidence, and projections stay in memory (no persisted projection table). See `formslang/hotspots.py`.

**Repository:** `B2DEV-TECH/FormsLang`\
**Milestone:** `FormsLang 2.1`\
**Authoritative Reference:** [docs/superpowers/specs/2026-09-21-formslang-modernization-intelligence-platform-spec.md](2026-09-21-formslang-modernization-intelligence-platform-spec.md) §11–§13, §31–§32, §88–§89

---

## 1. Executive Summary & Purpose

The goal of **FormsLang 2.1 (Estate Intelligence)** is to provide immense architectural value during legacy discovery before code generation is ever attempted.

Estate Intelligence transforms raw, opaque directories of Oracle Forms XML and database sources into an interactive **Modernization Cockpit** answering seven fundamental executive and engineering questions in approximately 10 seconds:
1. *How large is this legacy estate?*
2. *What exact sources were analyzed, and is the analysis fresh?*
3. *Where are the critical modernization risks?*
4. *What architectural hotspots deserve human attention first?*
5. *Which business rules are duplicated across UI modules?*
6. *Where does UI code bypass established database APIs?*
7. *How much of the estate can be mechanically resolved versus requiring human architectural decisions?*

---

## 2. Estate Cockpit Metrics & Evidence Ledger

Estate metrics are strictly computed from Level 1 Observed Facts. The engine **never fabricates percentages** when denominators are ambiguous.

| Metric | Computation Source | Significance |
| :--- | :--- | :--- |
| **Forms Modules** | Unique parsed `.fmb.xml` modules | Estate scale |
| **Triggers** | Count of form-, block-, and item-level triggers | UI event complexity |
| **Program Units** | Procedures/functions declared inside Forms | Local legacy PL/SQL volume |
| **Attached Libraries** | Unique `.pll` dependencies resolved | Shared client-side library reuse |
| **Database Packages** | Unique `.pks`/`.pkb` packages in source scope | Encapsulated server-side API volume |
| **Database Tables / Views** | Tables and views referenced in DML / SELECT | Data schema footprint |
| **Cross-Layer Dependencies** | Directed edges between Forms and DB objects | Architectural coupling |
| **Business-Rule Candidates**| Clusters of isomorphic or shared validation rules | Modernization centralization candidates |
| **Architectural Hotspots** | Verified instances of high-risk structural anti-patterns | Priority review targets |

---

## 3. Hotspot Engine Contracts

Every hotspot is a *candidate for architecture review*, never a verdict. It is
derived from the persisted Blueprint -- the engine's structural signal codes
(`[CODE]` statement prefixes), typed edges, resolved symbolic references and
stored unit attributes. The detectors never re-parse source. Fewer trustworthy
candidates are preferred to many aggressive ones.

### 3.1 `API_BYPASS_CANDIDATE` — "Possible API bypass"
* **Evidence contract:** the engine signal `DIRECT_DML_BYPASSES_API` on a Forms
  unit; the unit's `WRITES` edge resolves to a supplied `TABLE`; at least one
  packaged `SUBPROGRAM_BODY` also writes that table; the unit does not call it.
* **What it does not prove:** co-writing shows two layers write one table. It
  does not prove the package is the authoritative owner. The package is shown
  as a *potential existing API owner*.
* **Severity rule:** `MEDIUM` for co-writing only; `HIGH` when the co-writing
  subprogram carries measurably more guards (locking, explicit failure,
  affected-row checks). Never `CRITICAL` from this evidence alone; the unit's
  own measured risk stays visible on its finding.
* **Negative controls:** the unit calls the subprogram; the reference is
  unresolved; a same-named table from another source; no package writes the
  table. Table naming (`TMP_*`, `GTT_*`) is not treated as proof of anything.

### 3.2 `DUPLICATED_RULE_CLUSTER` — "Duplicated business-rule candidate"
* **Evidence contract:** engine signals `LOGIC_DUPLICATED_QUERY`, `_FORMULA` or
  `_PREDICATE` naming the same packaged subprogram.
* **What it does not prove:** the match is structural (query shape, arithmetic
  skeleton, literal set), not semantic equivalence; local variations may be
  legitimate. No AST-similarity score is computed.
* **Severity rule:** `MEDIUM` for copies in one module; `HIGH` for two or more.

### 3.3 `GLOBAL_STATE_COUPLING`
* **Evidence contract:** Forms units in two or more modules reference the same
  `:GLOBAL` variable (the lexer already excludes comments and literals).
* **What it does not prove:** runtime order, initialization and lifetime. A
  unit that both assigns and reads a variable is recorded as a reference, so
  observed writers are a lower bound.
* **Severity rule:** `MEDIUM` when shared; `HIGH` when one module is observed
  assigning it and a different module references it.

### 3.4 Not in 2.1: cross-layer ownership conflict
The earlier draft described divergent Form/database constraints. The engine
does not emit a conflict signal (it emits `MIRRORS_SCHEMA_CONSTRAINT` when a
trigger *agrees* with a CHECK constraint), so no such hotspot is reported.

Identities are SHA-256 digests of the hotspot type and its anchoring Blueprint
identities, independent of process, hash seed and input order.

---

## 4. "Start Here" Deterministic Ranking Algorithm

The Overview Cockpit presents a ranked list of top findings requiring immediate architect attention. To ensure trust, ranking is **100% deterministic and explainable**—never an arbitrary AI guess.

$$\text{PriorityScore}(F) = \text{BaseSeverity}(F) \times \left(1.0 + 0.2 \times \log_2(1 + \text{FanIn}(F)) + 0.3 \times \text{IsBypass}(F) + 0.25 \times \text{HasExistingAPI}(F)\right)$$

* **Severity Weights:** `CRITICAL` = 100, `HIGH` = 50, `MEDIUM` = 20, `LOW` = 5.
* **Explainability Guarantee:** The UI displays the breakdown factors when hovering over the score (e.g., *"Severity 100 + API Bypass (+30) + 14 Calling Modules (+76) = Score 206"*).

---

## 5. Performance Budgets & Scale Guarantees

Budgets are targets, not measured guarantees, for enterprise estates containing 500+ Forms and 5,000+ dependencies.

| Operation | Performance Budget (Warm Cache) | Strategy |
| :--- | :---: | :--- |
| **Cockpit Overview Projection** | $< 100\text{ ms}$ | In-memory projection cached per assessment and review revision (no persisted projection table; measure before persisting). |
| **Inventory First Page (50 items)** | $< 250\text{ ms}$ | Server-side pagination over the cached projection. |
| **Filtered Inventory Search** | $< 500\text{ ms}$ | Bounded query text and page size over the cached projection. |
| **Finding Detail Drawer** | $< 300\text{ ms}$ | Content-addressed fetch of exact finding record and evidence refs. |
| **Global Search Query (`Ctrl+K`)** | $< 500\text{ ms}$ | Bounded server-side query returning top 20 matches. |
| **Architecture Neighborhood Graph** | $< 750\text{ ms}$ | Module-level fold of the Blueprint graph; independent node, relationship and selector budgets with truncation metadata. |
| **Cold Project Reopen** | $< 2.0\text{ s}$ | Single-pass schema verification and metadata load. |
