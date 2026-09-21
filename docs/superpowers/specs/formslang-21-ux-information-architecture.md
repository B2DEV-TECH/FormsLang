# FormsLang 2.1 UX & Information Architecture Specification

**Repository:** `B2DEV-TECH/FormsLang`  
**Phase:** `FormsLang 2.1 (Phase 0 UX Foundation)`  
**Authoritative Reference:** [docs/superpowers/specs/2026-09-21-formslang-modernization-intelligence-platform-spec.md](2026-09-21-formslang-modernization-intelligence-platform-spec.md) §5–§8, §12–§14, §18–§20, §29–§30

---

## 1. Information Architecture Overhaul

### 1.1 From Flat Tool Tabs to Enterprise Journey
FormsLang 2.0 uses a flat tab model (`Overview`, `Inventory`, `Review`, `Dependencies`, `Generate`, `Reports`, `Settings`). This layout was optimized for single-target conversion workflows.

FormsLang 2.1 introduces an information hierarchy centered on the five core modernization questions:
1. **UNDERSTAND:** What do I have?
2. **ASSESS:** What matters?
3. **DECIDE:** What should happen?
4. **PLAN:** In what sequence should modernization proceed?
5. **DELIVER:** What is safe to move forward?

### 1.2 Canonical Navigation Model

```
+--------------------------------------------------------------------------+
| FORMSLANG  [Project: ERP_SALES_MOD]  [Target: UNSELECTED v]  [Ctrl+K]    |
+--------------------------------------------------------------------------+
|  NAVIGATION                     |  MAIN CONTENT VIEW                     |
|                                 |                                        |
|  * Overview (Cockpit)           |                                        |
|                                 |                                        |
|  v ESTATE                       |                                        |
|    - Inventory                  |                                        |
|    - Dependencies               |                                        |
|    - Business Rules             |                                        |
|    - Ownership                  |                                        |
|    - Hotspots                   |                                        |
|                                 |                                        |
|  v ARCHITECTURE                 |                                        |
|    - System Map                 |                                        |
|    - Data Flow                  |                                        |
|    - Coupling                   |                                        |
|    - API Boundaries             |                                        |
|                                 |                                        |
|  * Review                       |                                        |
|                                 |                                        |
|  * Plan                         |                                        |
|                                 |                                        |
|  * Deliver (Target-Gated)       |                                        |
|                                 |                                        |
|  --------------------------     |                                        |
|  * Project Settings             |                                        |
+--------------------------------------------------------------------------+
```

---

## 2. Phase 0: Design Tokens & System Standards

FormsLang retains its native HTML/CSS/JS architecture running inside Tauri / desktop / browser. No third-party UI framework is added. To ensure visual coherence across large estates, the UI standardizes on the following design tokens.

### 2.1 Surface Hierarchy & Typography
* **Base Background (`--surface-0`):** `#0c0d0e` (pure enterprise dark canvas).
* **Card / Panel Surface (`--surface-1`):** `#16181b` (subtle contrast).
* **Raised Surface / Popover (`--surface-2`):** `#212429`.
* **Border Token (`--border-subtle`):** `#2c3138`; **(`--border-strong`):** `#404752`.
* **Typography:** System monospaced/sans fonts (`Inter`, `-apple-system`, `Segoe UI`, `monospace`), strict 4px/8px modular rhythm.

### 2.2 Status, Risk & Verification Tokens
```css
/* Risk Badges */
--risk-critical: #ff4d4f; /* Direct DML bypass, guard loss */
--risk-high:     #faad14; /* Duplicated rules, cycle */
--risk-medium:   #1890ff; /* Assisted refactoring */
--risk-low:      #52c41a; /* Pure mechanical / automated */
--risk-unknown:  #8c8c8c; /* Insufficient evidence */

/* Review States */
--review-accepted: #52c41a;
--review-changed:  #13c2c2;
--review-needs:    #faad14;
--review-stale:    #f5222d;

/* Freshness States */
--freshness-current:    #52c41a;
--freshness-stale:      #faad14;
--freshness-missing:    #f5222d;
--freshness-unverified: #8c8c8c;
```

### 2.3 Terminology Cleanup
Internal engine implementation artifacts must not leak into user-facing copy:

| Internal Engine Term | Forbidden in Primary UX | Mandatory User-Facing Term |
| :--- | :--- | :--- |
| `finding_revision` / `analysis_revision` | *"Revision conflict: 4 != 5"* | *"Source changed since analysis. Reanalyze to review current evidence."* |
| `CAS` / `Store mutation` | *"CAS mismatch on project"* | *"Project was modified concurrently. Refreshing state."* |
| `Blueprint projection` | *"Projection building..."* | *"Loading estate inventory..."* |
| `unselected target` | *"Invalid target descriptor"* | *"Target: Not Selected (Modernization Intelligence Mode)"* |

---

## 3. Structured Text Wireframes

### 3.1 First-Run Onboarding

```
+--------------------------------------------------------------------------+
|                            WELCOME TO FORMSLANG                          |
|             Oracle Forms Modernization Intelligence Platform             |
|                                                                          |
|  What do you want to do?                                                 |
|                                                                          |
|  +--------------------------------------------------------------------+  |
|  | [1] ANALYZE MY FORMS ESTATE                                        |  |
|  |     Understand architecture, cross-layer dependencies, and         |  |
|  |     modernization risk before choosing a target technology.        |  |
|  |     (Target: Unselected. 100% Local. No credentials needed.)       |  |
|  +--------------------------------------------------------------------+  |
|                                                                          |
|  +--------------------------------------------------------------------+  |
|  | [2] MODERNIZE TO ORACLE APEX                                       |  |
|  |     Analyze estate and prepare an APEX 26.1 modernization          |  |
|  |     strategy with APEXlang generation & offline validation.        |  |
|  +--------------------------------------------------------------------+  |
|                                                                          |
|  +--------------------------------------------------------------------+  |
|  | [3] EXPLORE DEMO PROJECT                                           |  |
|  |     Open a synthetic enterprise Forms application with cross-layer  |  |
|  |     APIs, direct DML hotspots, and pre-analyzed evidence.          |  |
|  +--------------------------------------------------------------------+  |
+--------------------------------------------------------------------------+
```

### 3.2 Overview: Modernization Cockpit (10-Second Assessment)

```
+--------------------------------------------------------------------------+
| OVERVIEW: ERP_SALES_MOD                     [Freshness: Current (SHA-256)]|
+--------------------------------------------------------------------------+
| ESTATE METRICS                                                           |
| [ 420 Forms Modules ]   [ 1,840 Triggers ]    [ 86 Database Packages ]   |
| [ 340 Tables / Views]   [ 4,210 Dependencies] [ 112 Business Rules ]     |
+--------------------------------------------------------------------------+
| RISK & ARCHITECTURE HOTSPOTS                                             |
| Direct DML Hotspots:     14 [CRITICAL] | Dependency Cycles:      3 [HIGH]|
| API Bypass Candidates:    8 [CRITICAL] | Global State Usages:   42 [MED] |
| Duplicated Rule Clusters: 19 [HIGH]    | Unowned Behaviors:     11 [HIGH]|
+--------------------------------------------------------------------------+
| START HERE (Deterministic Priority Ranking)                              |
|                                                                          |
| 1. ORDERS.fmb (Trigger POST-INSERT)                     [CRITICAL RISK]  |
|    Issue: Direct DML writes to ORDERS table while ORDER_API exists.      |
|    Evidence: ORDER_API.INSERT_ORDER() owns table; 14 modules use API.    |
|    Action Required: Review Centralization Intent.                        |
|                                                                          |
| 2. APPROVALS.fmb (Trigger WHEN-VALIDATE-RECORD)         [CRITICAL RISK]  |
|    Issue: Conflicting business rule ownership with SEC_PACKAGE.          |
|    Evidence: Conflicting discount approval ceiling detected.             |
|    Action Required: Resolve Ownership Conflict.                         |
|                                                                          |
| 3. INVENTORY.fmb (Item P_ITEM_QTY)                      [HIGH RISK]      |
|    Issue: Stock availability validation duplicated across 4 modules.     |
|    Evidence: Identical structural AST in 4 separate form triggers.       |
|    Action Required: Centralize validation rule candidate.                |
+--------------------------------------------------------------------------+
```

### 3.3 Estate: Business Rules & Ownership Breakdown

```
+--------------------------------------------------------------------------+
| ESTATE > BUSINESS RULES & OWNERSHIP CANDIDATES                           |
| Filter: [All Owners v] [Risk: High+ v] [Search rules...                ] |
+--------------------------------------------------------------------------+
| Rule Candidate ID | Observed Implementation Locations | Inferred Owner   |
+-------------------+-----------------------------------+------------------+
| BR-DISCOUNT-LIMIT | ORDERS.fmb (WVI: P_DISC)          | DATABASE_API     |
|                   | CUSTOMERS.fmb (WVI: P_DISC)       | (PKG_DISCOUNTS)  |
|                   | PKG_DISCOUNTS.VALIDATE_CEILING    | [Status: Conflict]|
+-------------------+-----------------------------------+------------------+
| BR-CREDIT-CHECK   | ORDERS.fmb (KEY-COMMIT)           | FORM             |
|                   | QUOTES.fmb (KEY-COMMIT)           | (Unowned in DB)  |
|                   |                                   | [Status: Shared] |
+--------------------------------------------------------------------------+
| DETAIL DRAWER: BR-DISCOUNT-LIMIT                                         |
| * Observed Facts:                                                        |
|   - ORDERS.fmb executes direct check: `IF :P_DISC > 20 THEN ...`         |
|   - PKG_DISCOUNTS enforces dynamic tiers from TAB_POLICY.                |
| * Structural Inferences:                                                 |
|   - Form trigger bypasses centralized policy table.                      |
| * Modernization Intent:                                                  |
|   - CENTRALIZE_EXISTING_OWNER (Delegate entirely to PKG_DISCOUNTS).       |
+--------------------------------------------------------------------------+
```

### 3.4 Architecture: Bounded System Map & Edge Inspector

```
+--------------------------------------------------------------------------+
| ARCHITECTURE > SYSTEM MAP                  [Depth: 2] [Focus: ORDERS.fmb]|
+--------------------------------------------------------------------------+
|                                                                          |
|   [CUSTOMERS.fmb]                                                        |
|         │ (calls)                                                        |
|         ▼                                                                |
|   [ORDER_API.pks] ◄──────(calls)────── [ORDERS.fmb]                      |
|         │                                    │                           |
|         │ (writes)                           │ (DIRECT_DML - BYPASS!)    |
|         ▼                                    ▼                           |
|   [(T) ORDERS] ◄─────────────────────────────┘                           |
|                                                                          |
+--------------------------------------------------------------------------+
| EDGE EVIDENCE INSPECTOR (ORDERS.fmb ---> (T) ORDERS)                     |
| * Edge Classification: DIRECT_DML [CRITICAL HOTSPOT]                     |
| * Source Location: ORDERS.fmb : BLOCK_ORDER : POST-INSERT : Line 14      |
| * Guarded Alternative: ORDER_API.pks (called by 14 other modules)        |
| * Architectural Verdict: API Bypass Candidate                            |
+--------------------------------------------------------------------------+
```

### 3.5 Modernization Review: The 4-Layer Evidence Layout

Every review finding strictly separates the 4 layers:

```
+--------------------------------------------------------------------------+
| REVIEW FINDING: REV-00421                      [Status: Pending Review]  |
| Module: ORDERS.fmb | Unit: POST-INSERT | Entity: TAB_ORDERS              |
+--------------------------------------------------------------------------+
| 1. OBSERVED FACTS (Deterministic Static Evidence)                        |
|    - ORDERS.fmb: POST-INSERT trigger executes `INSERT INTO TAB_ORDERS...`|
|    - Database source contains package `ORDER_API` with `INSERT_ORDER`.    |
|    - TAB_ORDERS is mutated by `ORDER_API` in 14 other recorded locations.|
+--------------------------------------------------------------------------+
| 2. STRUCTURAL INFERENCE                                                  |
|    - Signal: DIRECT_DML_BYPASS_CANDIDATE.                                |
|    - Rationale: Direct table mutation outside established package API.   |
+--------------------------------------------------------------------------+
| 3. MODERNIZATION INTENT & RECOMMENDATIONS                                |
|    - Target-Neutral Intent: CENTRALIZE_EXISTING_OWNER                    |
|    - Target Recommendation (APEX 26.1): MOVE_TO_PLSQL_API                |
|    - Target Recommendation (Generic): PRESERVE_EXISTING_SERVICE_BOUNDARY |
+--------------------------------------------------------------------------+
| 4. HUMAN DECISION (Architectural Sign-off)                               |
|    [ Accept Intent ]   [ Change Intent v ]   [ Defer ]   [ Needs Review ]|
|                                                                          |
|    Reviewer: Geraldo Viana Jr                                            |
|    Rationale: Centralize order persistence in ORDER_API before APEX gen.  |
|    [ Confirm Decision (Commit to Append-Only History) ]                  |
+--------------------------------------------------------------------------+
```

### 3.6 Global Search / Command Palette (`Ctrl+K`)

```
+--------------------------------------------------------------------------+
| [ Find forms, packages, tables, business rules, hotspots (Ctrl+K)      ] |
+--------------------------------------------------------------------------+
| Search: "ORDERS"                                                         |
|                                                                          |
| Forms Module      ORDERS.fmb            (42 triggers, 14 findings)       |
| Database Package  ORDER_API             (Database API owner, 18 calls)   |
| Database Table    TAB_ORDERS            (Direct DML Hotspot)             |
| Hotspot           ORDERS Direct DML     (Critical API bypass)            |
| Rule Candidate    BR-ORDER-LOCKING      (Pessimistic locking in trigger) |
| Architecture Node ORDERS.fmb            (In System Map)                  |
+--------------------------------------------------------------------------+
```
