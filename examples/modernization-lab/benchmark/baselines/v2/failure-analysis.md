# FormsLang Modernization Benchmark: Baseline v2 Failure Analysis

**Date**: 2026-09-18  
**Protocol Version**: 1.0  
**Source Commit**: `9005c4389834ffcdf132734d04f6843a6b657cdf`  
**Engine**: `formslang.parser.parse_xml -> formslang.blueprint.build` (Deterministic, AI: None)  

---

## 1. Executive Summary

This document provides a detailed case-by-case failure analysis of the frozen `v2` baseline for the `B2DEV-TECH/FormsLang` prediction benchmark on `examples/modernization-lab`.

In benchmark v2, FormsLang evolved from Forms-only static analysis to **Forms + Oracle Database source reasoning**. Standalone `.sql` (DDL, views, constraints), `.pks` (package specs, constants, subprogram declarations), and `.pkb` (package bodies, procedural state machines, DML routines) were ingested into a unified Blueprint graph. Cross-layer heuristics were introduced for CHECK constraint mirroring, status predicate duplication, formula structural matching, clean API delegation, and direct DML bypass detection.

Every measurement below was captured against the strictly immutable ground-truth registry (`expected/modernization-ground-truth.json`, SHA256 `4b43e879e6124c7b2821ffedfc64c3ff19a825f61b39d7b911d9da209ce69615`). In accordance with benchmark principles, **no engine code or heuristics were modified after the v2 run**.

### Key Measured Outcomes (v2 vs. v1)
- **Total Cases**: 41
- **Observable Cases**: 38 (38 Fully Observable, 0 Partially Observable, 3 Not Observable) — *vs. 28 (16 Fully, 12 Partially, 13 Not Observable) in v1*
- **Exact Classification Accuracy (Observable)**: **68.4%** (26/38) — *vs. 21.4% (6/28) in v1 (+47.0% absolute)*
- **Exact Classification Accuracy (Fully Observable)**: **68.4%** (26/38) — *vs. 25.0% (4/16) in v1 (+43.4% absolute)*
- **Exact Risk Accuracy (Observable)**: **68.4%** (26/38) — *vs. 21.4% (6/28) in v1 (+47.0% absolute)*
- **Macro F1**: **0.6257** — *vs. 0.1333 in v1 (+0.4924)*
- **Manual Review Recall**: **80.0%** (8/10) — *vs. 60.0% (3/5) in v1 (+20.0% absolute)*
- **False Automation Rate**: **20.0%** (2/10) — *vs. 40.0% (2/5) in v1 (-20.0% absolute cut in half)*
- **Critical Risk Recall**: **100.0%** (4/4) — *vs. 0.0% (0/2) in v1*
- **Critical Safety Misses**: **0** (0 allowable in enterprise safety boundary)

---

## 2. Failure Category Distribution

Every mismatch and non-observable case is classified under one of the standard protocol failure categories:

| Failure Category | Count | Share of Total | Primary Root Cause |
|:---|---:|---:|:---|
| `NONE` (Exact Match) | 22 | 53.7% | Matched ground-truth classification and risk level (or correctly identified architectural decision). |
| `ARCHITECTURAL_JUDGMENT` | 6 | 14.6% | FormsLang static heuristics diverged from human architectural judgment (e.g. navigation redesign vs manual review, UI layout vs convert). |
| `RULE_MAPPING_GAP` | 4 | 9.8% | Ground-truth specific target classes (`REPLACE_WITH_APEX_NATIVE`, `MOVE_TO_PLSQL_API`) were mapped to broader engine classes (`CONVERT`, `REFACTOR`). |
| `RISK_MODEL_GAP` | 4 | 9.8% | Classification matched, but deterministic risk score deviated from human ground-truth risk assessment. |
| `SOURCE_NOT_INGESTED` | 3 | 7.3% | Non-code library documentation cases (`OM_SHARED.md`). Standalone code sources are now 100% ingested. |
| `VERDICT_GAP` | 2 | 4.9% | Safety misses where a case requiring human review (`MANUAL_REVIEW`) was classified as automatable (`CONVERT`). |
| `DETECTION_GAP` | 0 | 0.0% | All observable components in Forms2XML and database fixtures were detected. |
| `PARSER_INFORMATION_GAP` | 0 | 0.0% | Lexical parsers extracted all declared constructs, triggers, and SQL/PLSQL bodies. |

---

## 3. Detailed Analysis of Remaining Failures

### Category 1: `VERDICT_GAP` (2 Cases - Remaining Safety Misses)

1. **LOM-MOD-004** (`CUSTOMERS.xml` / `CUSTOMER_TYPE_CODE` / `WHEN-VALIDATE-ITEM`):
   - *Ground Truth*: `MANUAL_REVIEW`, Risk: `LOW`, Verdict: `MANUAL`
   - *Engine Prediction*: `CONVERT`, Risk: `HIGH`, Verdict: `AUTO`
   - *Root Cause*: The trigger copies `DEFAULT_CREDIT_LIMIT` into `CREDIT_LIMIT` via `COPY()` only when the target is null. The engine sees a standard item assignment and recommends framework item conversion. However, the ground-truth challenge is an unresolved business policy question: should a customer's credit limit ever be capped by their type on subsequent updates? Without human process input, static analysis treats it as shallow copy logic.
2. **LOM-MOD-018** (`INVENTORY.xml` / `BK_INVENTORY` / `PRE-QUERY`):
   - *Ground Truth*: `MANUAL_REVIEW`, Risk: `MEDIUM`, Verdict: `MANUAL`
   - *Engine Prediction*: `CONVERT`, Risk: `HIGH`, Verdict: `ASSISTED`
   - *Root Cause*: The trigger sets `DEFAULT_WHERE` dynamically via `SET_BLOCK_PROPERTY` using warehouse lookup. The catalog rule maps `SET_BLOCK_PROPERTY` to `ASSISTED`/`CONVERT` (region query source). However, the underlying schema issue is that no constraint enforces a single default warehouse in `LOM_WAREHOUSES`, which requires architectural review.

*Note on Safety*: These 2 cases constitute the remaining 20.0% False Automation Rate. All 4 `CRITICAL` risk cases were perfectly identified (`100% Critical Recall`, 0 critical safety misses).

---

### Category 2: `RULE_MAPPING_GAP` (4 Cases)

1. **LOM-MOD-012** (`CUSTOMERS.xml` / `CUSTOMER_TYPE_CODE` / `WHEN-VALIDATE-ITEM`):
   - *Ground Truth*: `REPLACE_WITH_APEX_NATIVE`, Risk: `LOW`
   - *Engine Prediction*: `CONVERT`, Risk: `HIGH`
   - *Root Cause*: Item default from LOV mapping. Engine produced `CONVERT` (target framework item validation/default), whereas human ground truth specifically labels it `REPLACE_WITH_APEX_NATIVE`.
2. **LOM-MOD-015** (`CUSTOMERS.xml` / `EMAIL` / `WHEN-VALIDATE-ITEM`):
   - *Ground Truth*: `REPLACE_WITH_APEX_NATIVE`, Risk: `LOW`
   - *Engine Prediction*: `REFACTOR`, Risk: `LOW`
   - *Root Cause*: Hand-rolled regex validation. FormsLang detects a conditional rejection pattern (`REFACTOR`), whereas the ground truth specifically targets native APEX email validation.
3. **LOM-MOD-035** (`INVENTORY.xml` / `BK_INVENTORY` / `POST-QUERY`):
   - *Ground Truth*: `REPLACE_WITH_APEX_NATIVE`, Risk: `LOW`
   - *Engine Prediction*: `CONVERT`, Risk: `MEDIUM`
   - *Root Cause*: Low-stock flag computed per-row in `POST-QUERY`. Engine classified the row computation as `CONVERT`, whereas APEX replaces it with an Interactive Report highlight attribute without PL/SQL.
4. **LOM-MOD-037** (`ORDERS.xml` / `BK_ORDER_LINE` / `PRE-INSERT`):
   - *Ground Truth*: `MOVE_TO_PLSQL_API`, Risk: `HIGH`
   - *Engine Prediction*: `CONVERT`, Risk: `MEDIUM`
   - *Root Cause*: Line-level DML trigger. Engine classified sequence/insert trigger as `CONVERT`, whereas human review identified that order line operations lack a PL/SQL API entirely and must be designed from scratch.

---

### Category 3: `ARCHITECTURAL_JUDGMENT` (6 Cases)

1. **LOM-MOD-008** (`WHEN-NEW-FORM-INSTANCE` session setup):
   - *Ground Truth*: `REFACTOR` (global variable redesign into `:APP_USER`), Risk: `LOW`
   - *Engine Prediction*: `CONVERT` (page load process), Risk: `MEDIUM`
2. **LOM-MOD-017** (`BK_ORDER_LINE.PRE-INSERT` MAX+1 numbering):
   - *Ground Truth*: `REFACTOR` (concurrency race condition needs lock/identity), Risk: `MEDIUM`
   - *Engine Prediction*: `CONVERT`, Risk: `MEDIUM`
3. **LOM-MOD-022** (`BT_VIEW_INVENTORY` non-modal `OPEN_FORM`):
   - *Ground Truth*: `REFACTOR` (session parameters to URL/page item), Risk: `LOW`
   - *Engine Prediction*: `MANUAL_REVIEW` (inter-form navigation redesign), Risk: `HIGH`
4. **LOM-MOD-023** (`BT_VIEW_CUSTOMER` query-only `CALL_FORM`):
   - *Ground Truth*: `REFACTOR` (plain link navigation), Risk: `LOW`
   - *Engine Prediction*: `MANUAL_REVIEW` (modal navigation redesign), Risk: `HIGH`
5. **LOM-MOD-029** (`APPROVALS.xml` / `PRE-QUERY` hardcoded worklist filter):
   - *Ground Truth*: `REFACTOR` (configurable region filter), Risk: `MEDIUM`
   - *Engine Prediction*: `CONVERT` (region query source), Risk: `MEDIUM`
6. **LOM-MOD-034** (`SHOW_ALERT` confirm dialogs):
   - *Ground Truth*: `REPLACE_WITH_APEX_NATIVE` (Confirm dynamic action), Risk: `LOW`
   - *Engine Prediction*: `PRESERVE`, Risk: `LOW`

---

### Category 4: `RISK_MODEL_GAP` (4 Cases)

1. **LOM-MOD-013** (`CUSTOMERS.xml` / `PRE-INSERT` sequence default):
   - Classification matched (`CONVERT`), but engine scored `MEDIUM` risk (truth `LOW`) due to block-level trigger point weighting.
2. **LOM-MOD-020** (`ORDERS.xml` / `BT_VIEW_APPROVALS` modal `CALL_FORM`):
   - Classification matched (`MANUAL_REVIEW`), but engine scored `HIGH` risk (truth `MEDIUM`).
3. **LOM-MOD-024** (`ORDERS.xml` / `BT_NEW` clear and create record):
   - Classification matched (`CONVERT`), but engine scored `MEDIUM` risk (truth `LOW`).
4. **LOM-MOD-025** (`ORDERS.xml` / `QUANTITY` availability check bypass):
   - Classification matched (`MOVE_TO_PLSQL_API`), but engine scored `HIGH` risk (truth `MEDIUM`).

---

### Category 5: `SOURCE_NOT_INGESTED` (3 Cases)

- **LOM-MOD-006**: Presentation helpers in `forms/libraries/OM_SHARED.md` (`REPLACE_WITH_APEX_NATIVE`).
- **LOM-MOD-007**: `open_form_with_context` in `forms/libraries/OM_SHARED.md` (`DROP`).
- **LOM-MOD-039**: `log_action` in `forms/libraries/OM_SHARED.md` (`MOVE_TO_PLSQL_API`).

*Assessment*: These 3 cases reside solely in non-code documentation representing an Oracle Forms binary library (`.pll`). Because FormsLang ingests code fixtures rather than freeform narrative documentation, these remain appropriately marked as `NOT_OBSERVABLE`.

---

## 4. Safety & Critical Case Verification

Benchmark v2 evaluated all 4 authoritative `CRITICAL` risk cases in the scenario:

| Case ID | Layer | Description | Truth Class / Risk | Pred Class / Risk | Status |
|:---|:---|:---|:---|:---|:---|
| **LOM-MOD-002** | Database (`.pkb`) | Procedural status transition matrix | `MANUAL_REVIEW` / `CRITICAL` | `MANUAL_REVIEW` / `CRITICAL` | **Exact Match** |
| **LOM-MOD-031** | Database (`.pks`) | Default session USER attribution | `MANUAL_REVIEW` / `CRITICAL` | `MANUAL_REVIEW` / `CRITICAL` | **Exact Match** |
| **LOM-MOD-041** | Forms (`.xml`) | Approve button direct DML bypass | `MANUAL_REVIEW` / `CRITICAL` | `MANUAL_REVIEW` / `CRITICAL` | **Exact Match** |
| **LOM-MOD-042** | Forms (`.xml`) | Reject button direct DML bypass | `MANUAL_REVIEW` / `CRITICAL` | `MANUAL_REVIEW` / `CRITICAL` | **Exact Match** |

- **Critical Risk Recall**: **100.0% (4/4)**
- **Critical Safety Misses**: **0**
- **Conclusion**: Cross-layer reasoning successfully prevented false automation on all core enterprise security, audit, and state integrity boundaries.
