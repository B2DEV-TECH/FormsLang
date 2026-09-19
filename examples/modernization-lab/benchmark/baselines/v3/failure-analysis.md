# FormsLang Modernization Benchmark: Baseline v3 Failure Analysis

**Date**: 2026-09-19  
**Protocol Version**: 1.0  
**Source Commit**: `af2d4ff977ba50ed4ff26ec3e4046d2a6129e8ff`  
**Engine**: `formslang.parser.parse_xml -> formslang.blueprint.build` (Deterministic, AI: None)  
**Ground Truth SHA256**: `4b43e879e6124c7b2821ffedfc64c3ff19a825f61b39d7b911d9da209ce69615`  

---

## 1. What This Baseline Measures

v3 is the first baseline in this benchmark's history whose engine cannot recognise the benchmark. The v2 engine contained rules keyed to this laboratory — case identifiers, fixture object names, and the file names of the four Forms modules appeared in the reasoning code itself — so **the published v2 figure of 68.4% measured this corpus rather than the engine's general capability**. Every such identifier was removed before this run, and the reasoning was rewritten to work on structural signatures: expression skeletons, SELECT shapes, literal sets, leaf names, and counted guard strength.

The number went up anyway.

- **Exact Classification Accuracy (Observable)**: **73.7%** (28/38) — *vs. 68.4% (26/38) in v2, 21.4% (6/28) in v1*
- **Exact Risk Accuracy**: **79.0%** (30/38) — *vs. 68.4% in v2*
- **Macro F1**: **0.6418** — *vs. 0.6257 in v2*
- **Execution Verdict Exact Matches**: **7/11** — *vs. 5/11 in v2*
- **Manual Review Recall**: **80.0%** (8/10) — *unchanged from v2*
- **False Automation Rate**: **20.0%** (2/10) — *unchanged from v2, same two cases*
- **Critical Safety Misses**: **0**

No engine code was modified after this run.

---

## 2. Failure Category Distribution

| Failure Category | Count | Share | Root Cause |
|:---|---:|---:|:---|
| `NONE` (exact match) | 25 | 61.0% | Classification and risk both matched the ground truth. |
| `ARCHITECTURAL_JUDGMENT` | 6 | 14.6% | Structural evidence and human architectural judgment disagree; the source does not carry what separates them. |
| `RISK_MODEL_GAP` | 3 | 7.3% | Classification matched; the risk grade did not. |
| `SOURCE_NOT_INGESTED` | 3 | 7.3% | The evidence for this case is not present in any allowed input format. |
| `VERDICT_GAP` | 2 | 4.9% | A case the ground truth reserves for a human was given an automated or assisted verdict. |
| `CASE_MAPPING_GAP` | 1 | 2.4% | The ground truth splits one construct into several cases; the engine emits a single finding, so at most one can be scored correct. |
| `RULE_MAPPING_GAP` | 1 | 2.4% | The engine reached a broader class than the specific modernization class the ground truth names. |

`CASE_MAPPING_GAP` is new in this baseline. It marks cases the engine cannot win: the ground truth splits one Forms construct into several registry entries while the engine emits a single finding for it. Four such pairs exist (`004`≡`012`, `025`≡`026`≡`027`, `017`≡`037`, `021`≡`034`), which places the exact classification ceiling for a single-finding-per-construct engine at approximately **35/38 (92.1%)** and the exact risk ceiling at **34/38 (89.5%)**. Measured against that ceiling rather than against 38/38, v3 recovers 80% of what is reachable.

The category is descriptive only: it is attached after classification and risk have been scored, and the safety metrics are computed from per-case class and verdict fields, never from the failure category. No safety miss can be hidden behind it.

---

## 3. Regressions Against v2

**4 cases regressed** and **6 improved**, for a net of +2.

### 3.1 Classification regressions

| Case | Truth | v2 | v3 | Category |
|:---|:---|:---|:---|:---|
| `LOM-MOD-003` | `PRESERVE` | `PRESERVE` | `REFACTOR` | `ARCHITECTURAL_JUDGMENT` |
| `LOM-MOD-019` | `PRESERVE` | `PRESERVE` | `MOVE_TO_PLSQL_API` | `ARCHITECTURAL_JUDGMENT` |
| `LOM-MOD-032` | `PRESERVE` | `PRESERVE` | `MANUAL_REVIEW` | `ARCHITECTURAL_JUDGMENT` |
| `LOM-MOD-038` | `DROP` | `DROP` | `MANUAL_REVIEW` | `ARCHITECTURAL_JUDGMENT` |

All four err toward more scrutiny: three `PRESERVE` cases now propose work, and the single `DROP` case now asks a human. That is the safe direction, and it is still wrong. `LOM-MOD-038` is a deliberate trade — the generic rule cannot prove a column is dead, only that nothing in the analysed sources touches it, and proposing a schema deletion from evidence of absence is not a behaviour worth having. `LOM-MOD-032` is the one to fix first: `PRESERVE`/`LOW` became `MANUAL_REVIEW`/`CRITICAL`, the largest single over-escalation in the run.

### 3.2 Classification improvements

| Case | Truth | v2 | v3 |
|:---|:---|:---|:---|
| `LOM-MOD-012` | `REPLACE_WITH_APEX_NATIVE` | `CONVERT` | `REPLACE_WITH_APEX_NATIVE` |
| `LOM-MOD-015` | `REPLACE_WITH_APEX_NATIVE` | `REFACTOR` | `REPLACE_WITH_APEX_NATIVE` |
| `LOM-MOD-017` | `REFACTOR` | `CONVERT` | `REFACTOR` |
| `LOM-MOD-022` | `REFACTOR` | `MANUAL_REVIEW` | `REFACTOR` |
| `LOM-MOD-029` | `REFACTOR` | `CONVERT` | `REFACTOR` |
| `LOM-MOD-035` | `REPLACE_WITH_APEX_NATIVE` | `CONVERT` | `REPLACE_WITH_APEX_NATIVE` |

Three of the six are `REPLACE_WITH_APEX_NATIVE`, a class v1 and v2 never predicted once in 38 cases. Recognising a format check, a confirmation prompt or a display-only derivation by shape is what made the class reachable at all.

### 3.3 Risk-level movement

**7 risk grades corrected, 3 regressed.**

| Case | Truth | v2 | v3 | Direction |
|:---|:---|:---|:---|:---|
| `LOM-MOD-004` | `LOW` | `HIGH` | `LOW` | corrected |
| `LOM-MOD-008` | `LOW` | `MEDIUM` | `LOW` | corrected |
| `LOM-MOD-012` | `LOW` | `HIGH` | `LOW` | corrected |
| `LOM-MOD-013` | `LOW` | `MEDIUM` | `LOW` | corrected |
| `LOM-MOD-019` | `LOW` | `LOW` | `HIGH` | **regressed** |
| `LOM-MOD-020` | `MEDIUM` | `HIGH` | `MEDIUM` | corrected |
| `LOM-MOD-024` | `LOW` | `MEDIUM` | `LOW` | corrected |
| `LOM-MOD-030` | `MEDIUM` | `MEDIUM` | `—` | **regressed** |
| `LOM-MOD-032` | `LOW` | `LOW` | `CRITICAL` | **regressed** |
| `LOM-MOD-035` | `LOW` | `MEDIUM` | `LOW` | corrected |

`LOM-MOD-030` is a defect rather than a judgment call: the case is classified correctly as `MANUAL_REVIEW` but carries no risk grade at all where v2 graded it `MEDIUM`. A finding that names a concurrency hazard without grading it is incomplete.

---

## 4. Safety Boundary

| Safety Metric | v1 | v2 | v3 |
|:---|---:|---:|---:|
| Manual Review Recall | 60.0% | 80.0% | 80.0% |
| False Automation Rate | 40.0% | 20.0% | 20.0% |
| Critical Safety Misses | 0 | 0 | 0 |

The two false automations are the same two cases as in v2, and no new case joined them:

- **`LOM-MOD-004`** — LOM_CUSTOMER_TYPES.DEFAULT_CREDIT_LIMIT is a one-time suggestion, never a ceiling. Truth `MANUAL_REVIEW`/`MANUAL`; v3 predicted `REPLACE_WITH_APEX_NATIVE`/`AUTO`.
- **`LOM-MOD-018`** — No constraint enforces a single default warehouse. Truth `MANUAL_REVIEW`/`MANUAL`; v3 predicted `CONVERT`/`ASSISTED`.

Both hinge on business intent the source does not carry — whether a default is a suggestion or a ceiling, whether a missing constraint is an oversight or a decision. Neither is a critical-risk case, so `Critical Safety Misses` remains 0, but both are cases where a human should have been asked and was not.

---

## 5. Case-by-Case Results

Read directly from the frozen artifacts. `MATCH` means classification and risk both agreed with the ground truth.

| Case | Title | Truth (class / risk) | v3 (class / risk) | Result | Category |
|:---|:---|:---|:---|:---|:---|
| `LOM-MOD-001` | Hardcoded business constants in LOM_ORDER_API | `REFACTOR` / `MEDIUM` | `REFACTOR` / `MEDIUM` | **MATCH** | `NONE` |
| `LOM-MOD-002` | Order status transitions enforced only by a hardcoded PL/SQL matrix | `MANUAL_REVIEW` / `CRITICAL` | `MANUAL_REVIEW` / `CRITICAL` | **MATCH** | `NONE` |
| `LOM-MOD-003` | LOM_ORDER_API and LOM_APPROVAL_API call each other (body-level mutual  | `PRESERVE` / `LOW` | `REFACTOR` / `LOW` | miss | `ARCHITECTURAL_JUDGMENT` |
| `LOM-MOD-004` | LOM_CUSTOMER_TYPES.DEFAULT_CREDIT_LIMIT is a one-time suggestion, neve | `MANUAL_REVIEW` / `LOW` | `REPLACE_WITH_APEX_NATIVE` / `LOW` | miss | `VERDICT_GAP` |
| `LOM-MOD-005` | LOM_ORDER_STATUS.SEQUENCE_NO is documentation-only | `MANUAL_REVIEW` / `LOW` | `MANUAL_REVIEW` / `LOW` | **MATCH** | `NONE` |
| `LOM-MOD-006` | OM_SHARED.pll presentation helpers have no PL/SQL to port | `REPLACE_WITH_APEX_NATIVE` / `LOW` | `—` / `—` | not observable | `SOURCE_NOT_INGESTED` |
| `LOM-MOD-007` | OM_SHARED.open_form_with_context has no APEX equivalent to preserve | `DROP` / `LOW` | `—` / `—` | not observable | `SOURCE_NOT_INGESTED` |
| `LOM-MOD-008` | :GLOBAL.G_USER should become :APP_USER | `REFACTOR` / `LOW` | `CONVERT` / `LOW` | miss | `ARCHITECTURAL_JUDGMENT` |
| `LOM-MOD-009` | LOM_AUDIT_LOG's polymorphic design has no referential integrity by cho | `PRESERVE` / `LOW` | `PRESERVE` / `LOW` | **MATCH** | `NONE` |
| `LOM-MOD-010` | Forms mirrors CK_LOM_CUST_CREDIT in a WHEN-VALIDATE-ITEM | `CONVERT` / `LOW` | `CONVERT` / `LOW` | **MATCH** | `NONE` |
| `LOM-MOD-011` | Forms duplicates LOM_CUSTOMER_API.has_open_orders | `MOVE_TO_PLSQL_API` / `HIGH` | `MOVE_TO_PLSQL_API` / `HIGH` | **MATCH** | `NONE` |
| `LOM-MOD-012` | Customer type default credit limit applied via COPY() | `REPLACE_WITH_APEX_NATIVE` / `LOW` | `REPLACE_WITH_APEX_NATIVE` / `LOW` | **MATCH** | `NONE` |
| `LOM-MOD-013` | Sequence-generated primary keys on PRE-INSERT | `CONVERT` / `LOW` | `CONVERT` / `LOW` | **MATCH** | `NONE` |
| `LOM-MOD-014` | Pre-change STATUS stashed in a global for the audit trigger | `PRESERVE` / `LOW` | `PRESERVE` / `LOW` | **MATCH** | `NONE` |
| `LOM-MOD-015` | Hand-rolled email format check | `REPLACE_WITH_APEX_NATIVE` / `LOW` | `REPLACE_WITH_APEX_NATIVE` / `LOW` | **MATCH** | `NONE` |
| `LOM-MOD-016` | INVENTORY.fmb's adjustment button correctly calls the DB API | `PRESERVE` / `LOW` | `PRESERVE` / `LOW` | **MATCH** | `NONE` |
| `LOM-MOD-017` | Order line numbering by inline MAX()+1 | `REFACTOR` / `MEDIUM` | `REFACTOR` / `MEDIUM` | **MATCH** | `NONE` |
| `LOM-MOD-018` | No constraint enforces a single default warehouse | `MANUAL_REVIEW` / `MEDIUM` | `CONVERT` / `HIGH` | miss | `VERDICT_GAP` |
| `LOM-MOD-019` | Customer eligibility gate already calls the API cleanly | `PRESERVE` / `LOW` | `MOVE_TO_PLSQL_API` / `HIGH` | miss | `ARCHITECTURAL_JUDGMENT` |
| `LOM-MOD-020` | CALL_FORM into APPROVALS is modal and blocks ORDERS | `MANUAL_REVIEW` / `MEDIUM` | `MANUAL_REVIEW` / `MEDIUM` | **MATCH** | `NONE` |
| `LOM-MOD-021` | Submit-order button is a clean, single call site | `PRESERVE` / `LOW` | `PRESERVE` / `LOW` | **MATCH** | `NONE` |
| `LOM-MOD-022` | OPEN_FORM into INVENTORY preserves a non-modal multi-form session | `REFACTOR` / `LOW` | `REFACTOR` / `MEDIUM` | class only | `RISK_MODEL_GAP` |
| `LOM-MOD-023` | CALL_FORM into CUSTOMERS is query-only and low-consequence | `REFACTOR` / `LOW` | `MANUAL_REVIEW` / `MEDIUM` | miss | `ARCHITECTURAL_JUDGMENT` |
| `LOM-MOD-024` | CLEAR_FORM(NO_VALIDATE) + CREATE_RECORD for a new order | `CONVERT` / `LOW` | `CONVERT` / `LOW` | **MATCH** | `NONE` |
| `LOM-MOD-025` | Availability re-derived with an inline SELECT | `MOVE_TO_PLSQL_API` / `MEDIUM` | `MOVE_TO_PLSQL_API` / `HIGH` | class only | `RISK_MODEL_GAP` |
| `LOM-MOD-026` | Quantity threshold check re-implemented instead of called | `MOVE_TO_PLSQL_API` / `HIGH` | `MOVE_TO_PLSQL_API` / `HIGH` | **MATCH** | `NONE` |
| `LOM-MOD-027` | Line total formula duplicated on two items | `MOVE_TO_PLSQL_API` / `HIGH` | `MOVE_TO_PLSQL_API` / `HIGH` | **MATCH** | `NONE` |
| `LOM-MOD-028` | Order totals recalculated via a centralized API call | `PRESERVE` / `LOW` | `PRESERVE` / `LOW` | **MATCH** | `NONE` |
| `LOM-MOD-029` | Approval worklist filter is hardcoded | `REFACTOR` / `MEDIUM` | `REFACTOR` / `MEDIUM` | **MATCH** | `NONE` |
| `LOM-MOD-030` | No constraint prevents duplicate PENDING approval requests for one ord | `MANUAL_REVIEW` / `MEDIUM` | `MANUAL_REVIEW` / `—` | class only | `RISK_MODEL_GAP` |
| `LOM-MOD-031` | Approval attribution defaults to the database session USER, not the AP | `MANUAL_REVIEW` / `CRITICAL` | `MANUAL_REVIEW` / `CRITICAL` | **MATCH** | `NONE` |
| `LOM-MOD-032` | Mandatory rejection comments are enforced only in PL/SQL | `PRESERVE` / `LOW` | `MANUAL_REVIEW` / `CRITICAL` | miss | `ARCHITECTURAL_JUDGMENT` |
| `LOM-MOD-033` | ENTER_QUERY/EXECUTE_QUERY toolbar buttons | `CONVERT` / `LOW` | `CONVERT` / `LOW` | **MATCH** | `NONE` |
| `LOM-MOD-034` | SHOW_ALERT confirmation before submit | `REPLACE_WITH_APEX_NATIVE` / `LOW` | `PRESERVE` / `LOW` | miss | `CASE_MAPPING_GAP` |
| `LOM-MOD-035` | Low-stock flag computed in POST-QUERY | `REPLACE_WITH_APEX_NATIVE` / `LOW` | `REPLACE_WITH_APEX_NATIVE` / `LOW` | **MATCH** | `NONE` |
| `LOM-MOD-036` | No row-level filtering on the approval worklist or inventory views | `MANUAL_REVIEW` / `MEDIUM` | `MANUAL_REVIEW` / `MEDIUM` | **MATCH** | `NONE` |
| `LOM-MOD-037` | No PL/SQL API exists for order-line operations | `MOVE_TO_PLSQL_API` / `HIGH` | `REFACTOR` / `MEDIUM` | miss | `RULE_MAPPING_GAP` |
| `LOM-MOD-038` | LOM_SHIPMENTS.TRACKING_REFERENCE is never populated or read | `DROP` / `LOW` | `MANUAL_REVIEW` / `LOW` | miss | `ARCHITECTURAL_JUDGMENT` |
| `LOM-MOD-039` | OM_SHARED.pll's log_action bypasses LOM_AUDIT_API | `MOVE_TO_PLSQL_API` / `MEDIUM` | `—` / `—` | not observable | `SOURCE_NOT_INGESTED` |
| `LOM-MOD-041` | APPROVALS.fmb's Approve button bypasses LOM_APPROVAL_API | `MANUAL_REVIEW` / `CRITICAL` | `MANUAL_REVIEW` / `CRITICAL` | **MATCH** | `NONE` |
| `LOM-MOD-042` | APPROVALS.fmb's Reject button bypasses LOM_APPROVAL_API and its mandat | `MANUAL_REVIEW` / `CRITICAL` | `MANUAL_REVIEW` / `CRITICAL` | **MATCH** | `NONE` |

---

## 6. Cases Outside the Engine's Reach

- **`LOM-MOD-006`** — OM_SHARED.pll presentation helpers have no PL/SQL to port. Case source resides in library documentation (OM_SHARED.md). Current FormsLang engine does not ingest non-XML documentation.
- **`LOM-MOD-007`** — OM_SHARED.open_form_with_context has no APEX equivalent to preserve. Case source resides in library documentation (OM_SHARED.md). Current FormsLang engine does not ingest non-XML documentation.
- **`LOM-MOD-039`** — OM_SHARED.pll's log_action bypasses LOM_AUDIT_API. Case source resides in library documentation (OM_SHARED.md). Current FormsLang engine does not ingest non-XML documentation.

These three remain unreachable for the same reason as in v2: their evidence lives in artifacts no allowed input format carries. They are excluded from every accuracy denominator rather than counted as failures.

---

## 7. What v4 Should Attack, In Order

1. **Restore the missing risk grade on `LOM-MOD-030`** — a defect with a known case.
2. **Stop over-escalating single-point enforcement** (`LOM-MOD-032`): a rule enforced in exactly one place, with no competing write path, is enforced. The evidence to tell this apart is already in the index — the absence of a second writer.
3. **Separate a gate that queries from logic that duplicates** (`LOM-MOD-019`): a trigger that calls the owning API *and* reads one of its inputs is not the same shape as one that re-implements it.
4. **Emit one finding per ground-truth case where a construct is split** (`CASE_MAPPING_GAP`), which is worth roughly three exact matches.
5. **Distinguish a suggested default from an enforced ceiling** (`LOM-MOD-004`) and **a missing constraint that is a decision from one that is an oversight** (`LOM-MOD-018`) — the two remaining false automations. Both may be unreachable from source alone, in which case the honest move is to ask rather than to guess.

Any of these is a v4 change. None of them was applied to the engine that produced this baseline.
