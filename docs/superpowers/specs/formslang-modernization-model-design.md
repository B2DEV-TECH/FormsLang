# FormsLang Modernization Model (IR) Specification

**Repository:** `B2DEV-TECH/FormsLang`  
**Horizon:** `FormsLang 2.2`  
**Authoritative Reference:** [docs/superpowers/specs/2026-09-21-formslang-modernization-intelligence-platform-spec.md](2026-09-21-formslang-modernization-intelligence-platform-spec.md) §15–§18, §37–§41

---

## 1. Executive Summary & Purpose

The **Modernization Model** (internal technical name: **Modernization IR**) is the core architectural data structure that enables FormsLang to become target-neutral.

In FormsLang 2.0, findings directly combined observed AST features with APEX-specific recommendations (`MOVE_TO_PLSQL_API`, `REPLACE_WITH_APEX_NATIVE`). This tight coupling prevented FormsLang from serving modernization initiatives targeting Java, .NET, or generic cloud-native architectures.

The Modernization Model enforces a clean, deterministic separation between:
1. **What the legacy system actually does** (Observed Facts)
2. **What structural patterns exist across layers** (Structural Signals)
3. **What architectural outcome should happen** (Modernization Intent)
4. **How a specific target platform accomplishes that outcome** (Target Recommendation)
5. **What the human architect decides** (Human Decision)
6. **Whether downstream generation is authorized** (Eligibility)

```
+-------------------------------------------------------------------------+
| LEVEL 1: OBSERVED FACTS                                                 |
| Deterministic extraction from Forms XML AST & Database DDL/PLSQL        |
+-------------------------------------------------------------------------+
                                     │
                                     ▼
+-------------------------------------------------------------------------+
| LEVEL 2: STRUCTURAL SIGNALS                                             |
| Cross-layer relationships, bypass candidates, duplicated AST clusters  |
+-------------------------------------------------------------------------+
                                     │
                                     ▼
+-------------------------------------------------------------------------+
| LEVEL 3: MODERNIZATION INTENT (Target-Neutral)                          |
| Centralize, preserve, redesign, replace, review ownership               |
+-------------------------------------------------------------------------+
                                     │
                 Target Adapter Interpretation Layer
                                     │
         +---------------------------+---------------------------+
         ▼                                                       ▼
+---------------------------------+     +---------------------------------+
| LEVEL 4A: ORACLE APEX ADAPTER   |     | LEVEL 4B: GENERIC MODERNIZATION |
| `MOVE_TO_PLSQL_API`             |     | `INTRODUCE_SERVICE_BOUNDARY`    |
| `REPLACE_WITH_APEX_NATIVE`      |     | `REPLACE_WITH_WEB_VALIDATION`   |
+---------------------------------+     +---------------------------------+
                                     │
                                     ▼
+-------------------------------------------------------------------------+
| LEVEL 5: HUMAN ARCHITECTURAL DECISION                                   |
| Accepted, Changed, Needs Review, Deferred (Append-only history)         |
+-------------------------------------------------------------------------+
                                     │
                                     ▼
+-------------------------------------------------------------------------+
| LEVEL 6: GENERATION ELIGIBILITY & PROVENANCE                            |
| Target-specific gate verifying valid source revision & human approval   |
+-------------------------------------------------------------------------+
```

---

## 2. Layered Model Specification

### 2.1 Level 1: Observed Facts
Observed facts are reproducible directly from analyzed source files without heuristics.

* **Module Facts:** Forms modules, blocks, items, canvases, windows, visual attributes, property classes, record groups.
* **Code Facts:** Triggers, program units, attached `.pll` libraries, AST statements (SELECT, INSERT, UPDATE, DELETE, MERGE, CALL, ASSIGNMENT).
* **Database Facts:** Tables, columns, constraints (PK, FK, CHECK, UNIQUE), views, package specifications, package bodies, procedures, standalone functions, database triggers.
* **Navigation Facts:** `CALL_FORM`, `NEW_FORM`, `OPEN_FORM` invocations and parameter lists.
* **Global Facts:** `GLOBAL.*`, `:PARAMETER.*`, package variables with session-level lifecycle.

### 2.2 Level 2: Structural Signals
Structural signals interpret observed facts across layers. Signals retain complete pointer references back to Level 1 facts:

| Signal Identifier | Semantics | Evidence Required |
| :--- | :--- | :--- |
| `DIRECT_DML` | A Form trigger directly executes DML on a table. | Forms trigger AST has INSERT/UPDATE/DELETE targeting table $T$. |
| `API_DELEGATION` | A Form invokes a database package procedure to mutate state. | Forms trigger calls $P.M()$; $P.M()$ executes DML on table $T$. |
| `API_BYPASS_CANDIDATE` | Form writes to table $T$ directly, while an existing package $P$ already provides encapsulated mutation for $T$. | Trigger executes `DIRECT_DML` on $T$; package $P$ writes $T$; multiple other modules use $P$. |
| `DUPLICATED_PREDICATE` | Identical or near-isomorphic validation predicate implemented across multiple Form units. | AST subtree isomorphism $\ge 0.90$ across triggers without shared procedure call. |
| `GLOBAL_STATE` | Cross-module communication or branching dependent on `:GLOBAL.*`. | Read/write access to named global variable across multiple compilation units. |
| `CROSS_MODULE_NAVIGATION` | Hardcoded form-to-form navigation. | `CALL_FORM` / `OPEN_FORM` calls referencing target module names. |
| `DEPENDENCY_CYCLE` | Circular dependency between modules or libraries. | Path in directed graph where $A \rightarrow \dots \rightarrow A$. |
| `CONCURRENCY_GUARD` | Pessimistic record locking via `SELECT ... FOR UPDATE`. | Form trigger or package contains explicit `FOR UPDATE` cursor or statement. |
| `GUARD_LOSS` | Form updates table $T$ directly without evaluating database CHECK constraint or package validation rule. | Write occurs without prerequisite validation call present in sibling modules. |

### 2.3 Level 3: Modernization Intent Taxonomy
Modernization Intents are **target-neutral**. They express the architectural goal regardless of whether the system modernizes to APEX, Java, .NET, or microservices:

1. `PRESERVE_EXISTING_OWNER`: The behavior is already encapsulated in the authoritative database package or service layer; keep it there.
2. `CENTRALIZE_EXISTING_OWNER`: The behavior exists in the UI but duplicates or bypasses an authoritative database owner; redirect it to the existing owner.
3. `INTRODUCE_SERVICE_BOUNDARY`: Business logic lives in UI triggers but belongs in the database or backend service layer; extract it.
4. `REPLACE_MECHANICAL_BEHAVIOR`: UI-specific navigation, formatting, or control flow that should be replaced by target-native framework constructs.
5. `REDESIGN_BEHAVIOR`: Complex, legacy-coupled workflows (e.g. global state bags, multi-window coordination) that cannot be mechanically ported.
6. `RESOLVE_OWNERSHIP`: Multiple competing layers or modules claim conflicting ownership of the same business rule; requires human resolution.
7. `REMOVE_OBSOLETE_BEHAVIOR`: Dead code, debugging triggers, or obsolete terminal/platform workarounds.
8. `REVIEW_BUSINESS_INTENT`: Behavior lacks sufficient structural clarity or contains high-risk business logic; requires domain expert review.
9. `REVIEW_CONCURRENCY`: Pessimistic locking or complex transaction management requiring architectural re-evaluation in stateless web targets.
10. `REVIEW_SECURITY`: Hardcoded credentials, dynamic SQL, or missing authorization checks.
11. `UNKNOWN`: Insufficient evidence to infer architectural intent.

---

## 3. Lossless 2.0 Recommendation Compatibility Mapping

FormsLang 2.0 recommendations must map losslessly to the new Modernization Model. Existing project databases and review records must remain valid without destructive rewrites:

| FormsLang 2.0 Recommendation | Modernization Intent (Target-Neutral) | APEX 26.1 Target Recommendation | Generic Modernization Recommendation |
| :--- | :--- | :--- | :--- |
| `MOVE_TO_PLSQL_API` | `CENTRALIZE_EXISTING_OWNER` | `MOVE_TO_PLSQL_API` | `PRESERVE_EXISTING_SERVICE_BOUNDARY` |
| `REPLACE_WITH_APEX_NATIVE` | `REPLACE_MECHANICAL_BEHAVIOR` | `REPLACE_WITH_APEX_NATIVE` | `REPLACE_WITH_WEB_FRAMEWORK_NATIVE` |
| `PRESERVE` | `PRESERVE_EXISTING_OWNER` | `PRESERVE` | `PRESERVE` |
| `CONVERT` | `INTRODUCE_SERVICE_BOUNDARY` | `CONVERT` | `EXTRACT_TO_BACKEND_SERVICE` |
| `REFACTOR` | `REDESIGN_BEHAVIOR` | `REFACTOR` | `REDESIGN_STATE_OR_WORKFLOW` |
| `MANUAL_REVIEW` | `REVIEW_BUSINESS_INTENT` | `MANUAL_REVIEW` | `MANUAL_ARCHITECTURE_REVIEW` |
| `DROP` | `REMOVE_OBSOLETE_BEHAVIOR` | `DROP` | `DECOMMISSION_OR_RETIRE` |

---

## 4. Multi-Revision Model & Invalidation Matrix

To satisfy the safety and determinism doctrines (§2.4, §37, §39, §40), FormsLang manages fine-grained revision tracking.

### 4.1 Revision Taxonomy
* `source_revision`: SHA-256 hash of all analyzed source files.
* `analysis_revision`: Hash of the deterministic analysis engine rules and IR schema version.
* `modernization_model_revision`: Hash of extracted Level 1 facts and Level 2 signals.
* `review_revision`: Monotonic counter of human architectural decisions in the append-only event store.
* `policy_revision`: Hash of active organizational and project policy files.
* `target_strategy_revision`: Version of the selected target adapter and target configuration.
* `code_approval_revision`: Hash of human code review approvals.
* `artifact_revision`: Hash of generated target code packages (e.g. APEXlang ZIP).

### 4.2 Invalidation Matrix

| Triggering Change Event | Re-extract Facts & Signals? | Recompute Intent? | Invalidate Human Decisions? | Invalidate Target Plan? | Invalidate Code Approvals? | Invalidate Generated Artifacts? |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Source Bytes Modified** | **YES** | **YES** | **Mark Stale** | **YES** | **YES** | **YES** |
| **Engine Rules Updated** | **YES** | **YES** | **Mark Stale** | **YES** | **YES** | **YES** |
| **Policy Updated** | NO | **YES** | NO | **YES** | Conditionally | Conditionally |
| **Target Strategy Changed** | NO | NO | NO | **YES** | **YES** | **YES** |
| **Human Decision Recorded**| NO | NO | Append | **YES** | Affected Units | Affected Units |
| **Display / Filter Preference** | NO | NO | NO | NO | NO | NO |

> [!IMPORTANT]
> **Stale Decision Preservation:** When source bytes change, previous human review decisions are **never silently discarded**. They are retained with full audit history and flagged as `STALE (Source Changed)`. The UI displays the side-by-side diff of the source code before prompting the reviewer to revalidate.
