# FormsLang Modernization Benchmark: Baseline v1 Failure Analysis

**Date**: 2026-09-18  
**Protocol Version**: 1.0  
**Source Commit**: `22f24805d0f8b277368723306565b94c5e2d25b0`  
**Engine**: `formslang.parser.parse_xml -> formslang.blueprint.build` (Deterministic, AI: None)  

---

## 1. Executive Summary

This document provides a detailed, case-by-case failure analysis of the frozen `v1` baseline for the `B2DEV-TECH/FormsLang` prediction benchmark on `examples/modernization-lab`.

In accordance with Section 53 of the benchmark protocol, **no engine heuristics, classification rules, risk scores, or parsers were tuned or modified to improve scores**. This analysis documents the genuine behavior, capabilities, and gaps of the existing FormsLang engine when evaluated against the human-reviewed ground truth.

### Key Measured Outcomes
- **Total Cases**: 41
- **Observable Cases**: 28 (16 Fully Observable, 12 Partially Observable, 13 Not Observable)
- **Exact Classification Accuracy (Observable)**: 21.4% (6/28)
- **Exact Classification Accuracy (Fully Observable)**: 25.0% (4/16)
- **Exact Risk Accuracy (Observable)**: 21.4% (6/28)
- **Macro F1**: 0.1333
- **Manual Review Recall**: 60.0% (3/5)
- **False Automation Rate**: 40.0% (2/5)
- **Critical Safety Misses**: 0 (0 allowable in enterprise safety boundary)

---

## 2. Failure Category Distribution

Every mismatch and non-observable case is classified under one of the standard protocol failure categories:

| Failure Category | Count | Share of Total | Primary Root Cause |
|:---|---:|---:|:---|
| `SOURCE_NOT_INGESTED` | 13 | 31.7% | Case source resides exclusively in standalone database packages (`.pks`/`.pkb`), DDL (`.sql`), or library documentation. Current FormsLang engine only ingests Forms2XML files. |
| `ARCHITECTURAL_JUDGMENT` | 7 | 17.1% | FormsLang static heuristics diverged from human architectural judgment (e.g. flagging complex state preservation vs. refactoring). |
| `RULE_MAPPING_GAP` | 4 | 9.8% | Ground-truth specific target classes (`MOVE_TO_PLSQL_API`, `REPLACE_WITH_APEX_NATIVE`) were mapped to broader engine classes (`REFACTOR`, `CONVERT`). |
| `VERDICT_GAP` | 2 | 4.9% | Safety misses where a case requiring human review (`MANUAL_REVIEW`, verdict `MANUAL`) was classified as automatable (`CONVERT`, verdict `AUTO`/`ASSISTED`). |
| `RISK_MODEL_GAP` | 1 | 2.4% | Classification matched, but deterministic risk score deviated from human ground-truth risk assessment. |
| `DETECTION_GAP` | 0 | 0.0% | All observable components in Forms2XML were successfully parsed and detected. |
| `PARSER_INFORMATION_GAP` | 0 | 0.0% | FormsLang's XML parser extracted all declared triggers, properties, and embedded PL/SQL. |
| `NONE` (Exact Match) | 14 | 34.1% | Exact match on classification and risk, or correctly identified architectural decision. |

---

## 3. Detailed Analysis by Category

### Category 1: `SOURCE_NOT_INGESTED` (13 Cases)

**Affected Cases**: LOM-MOD-001, LOM-MOD-002, LOM-MOD-003, LOM-MOD-005, LOM-MOD-006, LOM-MOD-007, LOM-MOD-009, LOM-MOD-030, LOM-MOD-031, LOM-MOD-032, LOM-MOD-036, LOM-MOD-038, LOM-MOD-039.

**Root Cause**:
FormsLang is designed to ingest Oracle Forms2XML modules (`.xml`) and `.fmb` binaries converted to XML via Oracle toolchains. It does not possess a native standalone SQL/PLSQL file crawler or DDL/package parser.
- **Database Packages/DDL**: MOD-001, 002, 003, 005, 009, 030, 031, 032, 036, 038, 039 reside in `database/packages/lom_*.pks/pkb` or `database/ddl/*.sql`.
- **Attached Library Docs**: MOD-006, 007 reside in `forms/libraries/OM_SHARED.md` (representing a binary `.pll` library whose source is documented).

**Technical Assessment**:
Excluding these 13 cases from classification scoring is correct under the protocol because a tool cannot predict on files it is not permitted or equipped to ingest. No attempt was made to write a shadow SQL parser prior to baseline, preserving benchmark integrity.

---

### Category 2: `VERDICT_GAP` (2 Cases - Safety Misses)

**Affected Cases**:
1. **LOM-MOD-004** (`CUSTOMERS.xml` / `CUSTOMER_TYPE_CODE` / `WHEN-VALIDATE-ITEM`):
   - *Ground Truth*: `MANUAL_REVIEW`, Risk: `LOW`, Verdict: `MANUAL`
   - *Engine Prediction*: `CONVERT`, Risk: `HIGH`, Verdict: `AUTO`
   - *Mechanism*: The trigger copies `DEFAULT_CREDIT_LIMIT` into `CREDIT_LIMIT` only if null. The engine classified this as a mechanical item validation/copy (`CONVERT`). However, the human case identified that whether a customer's credit limit should ever be capped by their type on subsequent updates is an open business policy question requiring human confirmation.
2. **LOM-MOD-018** (`INVENTORY.xml` / `BK_INVENTORY` / `PRE-QUERY`):
   - *Ground Truth*: `MANUAL_REVIEW`, Risk: `MEDIUM`, Verdict: `MANUAL`
   - *Engine Prediction*: `CONVERT`, Risk: `HIGH`, Verdict: `AUTO`
   - *Mechanism*: The trigger sets `DEFAULT_WHERE` dynamically (`SET_BLOCK_PROPERTY`). The catalog rule maps `SET_BLOCK_PROPERTY` to `ASSISTED`/`CONVERT` (region query source). However, dynamic WHERE clause generation in desktop Forms carries query injection risks and must be redesigned for APEX declarative filtering.

**Safety Significance**:
These 2 cases constitute the **40.0% False Automation Rate** (2 out of 5 observable `MANUAL_REVIEW` cases). In an enterprise modernization scenario, an engine that blindly marks these as automatic conversions creates technical and operational risk.

---

### Category 3: `RULE_MAPPING_GAP` (4 Cases)

**Affected Cases**:
1. **LOM-MOD-011** (`CUSTOMERS.xml` / `STATUS` / `WHEN-VALIDATE-ITEM`):
   - *Ground Truth*: `MOVE_TO_PLSQL_API`, Risk: `HIGH`
   - *Engine Prediction*: `REFACTOR`, Risk: `LOW`
   - *Reason*: Status validation duplicates database package logic. FormsLang's blueprint engine assigned `REFACTOR` (identifying it as a coupled business rule), but does not have a dedicated `MOVE_TO_PLSQL_API` classification category.
2. **LOM-MOD-012** (`CUSTOMERS.xml` / `CUSTOMER_TYPE_CODE` / `WHEN-VALIDATE-ITEM`):
   - *Ground Truth*: `REPLACE_WITH_APEX_NATIVE`, Risk: `LOW`
   - *Engine Prediction*: `CONVERT`, Risk: `HIGH`
   - *Reason*: Item default from LOV mapping. Engine produced `CONVERT`, whereas human review identified that APEX native item default attributes replace the trigger entirely.
3. **LOM-MOD-015** (`CUSTOMERS.xml` / `EMAIL` / `WHEN-VALIDATE-ITEM`):
   - *Ground Truth*: `REPLACE_WITH_APEX_NATIVE`, Risk: `LOW`
   - *Engine Prediction*: `REFACTOR`, Risk: `LOW`
   - *Reason*: Email regex validation. Engine recognized a conditional rejection rule (`REFACTOR`), but ground truth targets native APEX email validation.
4. **LOM-MOD-025** (`ORDERS.xml` / `QUANTITY` / `WHEN-VALIDATE-ITEM`):
   - *Ground Truth*: `MOVE_TO_PLSQL_API`, Risk: `HIGH`
   - *Engine Prediction*: `REFACTOR`, Risk: `HIGH`
   - *Reason*: Inline availability query duplicates `lom_inventory_api.get_available_qty`. Engine detected a complex business rule and assigned `REFACTOR`.

---

### Category 4: `ARCHITECTURAL_JUDGMENT` (7 Cases)

**Affected Cases**:
- **LOM-MOD-008**: `WHEN-NEW-FORM-INSTANCE` session setup. Engine: `CONVERT` (page load process), Truth: `REFACTOR` (global variable redesign needed).
- **LOM-MOD-010**: `CREDIT_LIMIT` >= 0 validation. Engine: `REFACTOR` (business rule pattern), Truth: `CONVERT` (direct APEX item validation).
- **LOM-MOD-014**: `POST-UPDATE` audit logging. Engine: `MANUAL_REVIEW` (non-standard DML timing), Truth: `PRESERVE` (the audit procedure is preserved).
- **LOM-MOD-016**: `BT_ADJUST.WHEN-BUTTON-PRESSED`. Engine: `MANUAL_REVIEW` (imperative button DML), Truth: `PRESERVE` (already calls PL/SQL API).
- **LOM-MOD-017**: `BK_ORDER_LINE.PRE-INSERT`. Engine: `CONVERT`, Truth: `REFACTOR` (concurrency race condition: availability check during client-side pre-insert without locking).
- **LOM-MOD-019**: `CUSTOMER_ID.WHEN-VALIDATE-ITEM`. Engine: `REFACTOR`, Truth: `PRESERVE` (already calls `lom_customer_api.can_place_order`).
- **LOM-MOD-024**: `BT_NEW.WHEN-BUTTON-PRESSED`. Engine: `CONVERT`, Truth: `REFACTOR` (imperative `CREATE_RECORD` needs redesign into APEX master-detail region flow).

---

### Category 5: `RISK_MODEL_GAP` (1 Case)

**Affected Case**:
- **LOM-MOD-013** (`CUSTOMERS.xml` / `PRE-INSERT`):
  - *Ground Truth*: `CONVERT`, Risk: `LOW`
  - *Engine Prediction*: `CONVERT`, Risk: `MEDIUM`
  - *Reason*: The trigger populates `customer_id` from sequence. FormsLang's risk model charges points for block lifecycle trigger execution (`TRIGGER_POINTS`), pushing the score above the 20.0 threshold into `MEDIUM`, whereas a simple sequence default is judged `LOW` risk by humans.

---

## 4. Safety & Critical Case Analysis

### Critical Cases (4 Total in Scenario)
1. **LOM-MOD-002** (Order status matrix): `NOT_OBSERVABLE` (database package).
2. **LOM-MOD-031** (Approval attribution bypass): `NOT_OBSERVABLE` (database package).
3. **LOM-MOD-041** (`BT_APPROVE` button bypasses approval API): `PARTIALLY_OBSERVABLE`.
   - *Engine Prediction*: `MANUAL_REVIEW`, Risk: `HIGH`, Verdict: `MANUAL`.
   - *Outcome*: Engine correctly identified the imperative DML and flagged it for manual intervention.
4. **LOM-MOD-042** (`BT_REJECT` button bypasses approval API): `PARTIALLY_OBSERVABLE`.
   - *Engine Prediction*: `MANUAL_REVIEW`, Risk: `HIGH`, Verdict: `MANUAL`.
   - *Outcome*: Engine correctly identified the imperative DML and flagged it for manual intervention.

Because neither observable critical case was labeled as `AUTO` or `CONVERT`, **Critical Safety Misses = 0**.

---

## 5. Summary & Recommendations

1. **Do Not Patch Heuristics Before Baseline**: This baseline faithfully records the performance of FormsLang v1.
2. **Future Work (Post-v1)**:
   - Introduce database package ingestion so the 13 `NOT_OBSERVABLE` cases can be evaluated.
   - Refine taxonomy mapping to distinguish between general `REFACTOR` and `MOVE_TO_PLSQL_API`.
   - Improve dynamic SQL and session variable detection to eliminate the 2 false automations (MOD-004, MOD-018).
