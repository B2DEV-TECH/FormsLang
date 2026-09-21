# FormsLang 2.1 Estate Intelligence Design Specification

**Repository:** `B2DEV-TECH/FormsLang`  
**Milestone:** `FormsLang 2.1`  
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

In accordance with §88, every hotspot is defined by a strict contract. No hotspot is introduced merely for dashboard aesthetics.

### 3.1 Hotspot 1: `API_BYPASS_CANDIDATE` (Direct DML Hotspot)
* **Architectural Problem:** A Form trigger directly executes `INSERT`, `UPDATE`, or `DELETE` on table $T$, bypassing an existing database package $P$ that already owns write operations on $T$. In a modern web application, this causes critical business logic or audit omissions.
* **Source Evidence Required:**
  1. Module trigger AST contains a DML statement referencing table $T$.
  2. Database source contains a package procedure/function $P.M()$ referencing table $T$ with DML.
  3. Package $P$ is called by at least one other module or trigger in the estate.
* **Deterministic Detection Algorithm:**
  $$\text{Bypass}(M, U, T) = \text{HasDML}(U, T) \land \exists P \in \text{DBPackages} : \text{HasDML}(P, T) \land \neg \text{Calls}(U, P)$$
* **Severity Policy:** `CRITICAL`.
* **False-Positive Boundary:** If table $T$ is an unconstrained temporary scratch table (`TMP_*`, `GTT_*`) without package coverage, classify as `DIRECT_DML_UNOWNED` (Severity: `MEDIUM`), not `API_BYPASS`.
* **UI Projection:** Highlighted with red badge, direct side-by-side comparison showing Form trigger SQL vs existing Package API procedure signature.

### 3.2 Hotspot 2: `DUPLICATED_RULE_CLUSTER`
* **Architectural Problem:** Identical or structurally isomorphic validation rules (e.g. credit limit, discount threshold, date validation) are implemented independently across multiple Forms triggers rather than centralized in a database package or service.
* **Source Evidence Required:**
  1. Two or more distinct program units or triggers in different modules.
  2. AST subtrees containing comparison predicates (`>`, `<`, `BETWEEN`, `IN`, regex) matching with tree isomorphism score $\ge 0.90$.
* **Deterministic Detection Algorithm:**
  $$\text{Cluster}(U_1, U_2) \iff \text{AST_Distance}(U_1.\text{pred}, U_2.\text{pred}) \le \theta_{\text{iso}} \land \text{TargetTable}(U_1) = \text{TargetTable}(U_2)$$
* **Severity Policy:** `HIGH`.
* **False-Positive Boundary:** Generic UI boilerplates (e.g. `IF :P_ITEM IS NULL THEN RAISE FORM_TRIGGER_FAILURE;`) are filtered out via semantic stop-lists.
* **UI Projection:** Grouped rule card displaying the $N$ occurrences, highlighting differences in threshold constants or error messages.

### 3.3 Hotspot 3: `GLOBAL_STATE_COUPLING`
* **Architectural Problem:** Legacy Forms relying on `:GLOBAL.*` variables to pass state across modules or coordinate multi-form workflows. In stateless web architectures (APEX, Spring, React), this breaks bookmarking, multi-tab browsing, and session isolation.
* **Source Evidence Required:** Read or write operations against `:GLOBAL.<name>` across two or more separate modules.
* **Deterministic Detection Algorithm:**
  $$\text{Coupled}(M_1, M_2, G) \iff (\text{Writes}(M_1, G) \land \text{Reads}(M_2, G)) \lor (\text{Reads}(M_1, G) \land \text{Writes}(M_2, G))$$
* **Severity Policy:** `MEDIUM` (elevated to `HIGH` if combined with cross-module navigation `CALL_FORM`).
* **UI Projection:** Dependency edge marked with state bag icon; recommendation to introduce explicit session state or URL parameters.

### 3.4 Hotspot 4: `CROSS_LAYER_OWNERSHIP_CONFLICT`
* **Architectural Problem:** Both the Forms trigger and a database trigger/constraint enforce different, conflicting validation constraints on the same column (e.g. Form allows discount up to 25%, but DB constraint enforces max 20%).
* **Source Evidence Required:** Form trigger predicate evaluating column $C$ compared against DB check constraint or DB trigger predicate on $C$ where boundary values diverge.
* **Severity Policy:** `CRITICAL`.
* **UI Projection:** Warning card flagged as `BLOCKED_UNTIL_HUMAN_RESOLUTION`.

---

## 4. "Start Here" Deterministic Ranking Algorithm

The Overview Cockpit presents a ranked list of top findings requiring immediate architect attention. To ensure trust, ranking is **100% deterministic and explainable**—never an arbitrary AI guess.

$$\text{PriorityScore}(F) = \text{BaseSeverity}(F) \times \left(1.0 + 0.2 \times \log_2(1 + \text{FanIn}(F)) + 0.3 \times \text{IsBypass}(F) + 0.25 \times \text{HasExistingAPI}(F)\right)$$

* **Severity Weights:** `CRITICAL` = 100, `HIGH` = 50, `MEDIUM` = 20, `LOW` = 5.
* **Explainability Guarantee:** The UI displays the breakdown factors when hovering over the score (e.g., *"Severity 100 + API Bypass (+30) + 14 Calling Modules (+76) = Score 206"*).

---

## 5. Performance Budgets & Scale Guarantees

FormsLang must remain blazingly fast on enterprise estates containing 500+ Forms and 5,000+ dependencies.

| Operation | Performance Budget (Warm Cache) | Strategy |
| :--- | :---: | :--- |
| **Cockpit Overview Projection** | $< 100\text{ ms}$ | Pre-aggregated projection table updated on analysis commit. |
| **Inventory First Page (50 items)** | $< 250\text{ ms}$ | Server-side pagination & SQLite index on `(project_id, category)`. |
| **Filtered Inventory Search** | $< 500\text{ ms}$ | Bounded multi-column indices without unindexed table scans. |
| **Finding Detail Drawer** | $< 300\text{ ms}$ | Content-addressed fetch of exact finding record and evidence refs. |
| **Global Search Query (`Ctrl+K`)** | $< 500\text{ ms}$ | Bounded server-side query returning top 20 matches. |
| **Architecture Neighborhood Graph** | $< 750\text{ ms}$ | Breadth-first search limited to depth $\le 2$ from focus node. |
| **Cold Project Reopen** | $< 2.0\text{ s}$ | Single-pass schema verification and metadata load. |
