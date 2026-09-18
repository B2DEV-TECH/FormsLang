# FormsLang Modernization Benchmark Baseline Report (v1)

## 1. Executive Summary

- **Benchmark Status**: `BASELINE_COMPLETE`
- **Protocol Version**: `1.0`
- **Source Commit**: `22f24805d0f8b277368723306565b94c5e2d25b0`
- **Engine**: `formslang.parser.parse_xml -> formslang.blueprint.build` (Deterministic, AI: None)
- **Total Cases**: `41`
- **Observable Cases**: `28` (16 Fully, 12 Partially, 13 Not Observable)
- **Exact Classification Accuracy (Observable)**: `21.4%` (6/28)
- **Exact Classification Accuracy (Fully Observable)**: `25.0%` (4/16)
- **Macro F1**: `0.1333`
- **Exact Risk Accuracy**: `21.4%`
- **Manual Review Recall**: `60.0%` (3/5)
- **False Automation Rate**: `40.0%` (2/5)
- **Critical Safety Misses**: `0`

## 2. Run Metadata

- **Protocol Version**: `1.0`
- **Runner Version**: `1.0`
- **Ground Truth Version**: `1.0`
- **Benchmark Version**: `1.0`
- **Source Commit**: `22f24805d0f8b277368723306565b94c5e2d25b0`
- **Generated At**: `2026-09-18T20:51:28.884103+00:00`
- **Ground Truth SHA256**: `4b43e879e6124c7b2821ffedfc64c3ff19a825f61b39d7b911d9da209ce69615`

## 3. Engine Path

- **Engine**: `formslang.parser.parse_xml -> formslang.blueprint.build`
- **Deterministic**: `True` (all analysis, rules, risk, and blueprint inferences are 100% deterministic)
- **AI Usage**: `None` (no LLM providers or heuristic nondeterministic generators are invoked)

## 4. Input Boundary

- **Allowed Inputs**: Sanitized Forms2XML documents parsed through `formslang.parser.parse_xml` (`APPROVALS.xml`, `CUSTOMERS.xml`, `INVENTORY.xml`, `ORDERS.xml`).
- **Forbidden Inputs**: Ground truth registry (`modernization-ground-truth.json`), narrative documentation (`REVIEW.md`, `HANDOFF.md`, `assessment/`, `docs/`, `blueprint/expected-apex-architecture.md`), prior reports, failure-analysis documents.

## 5. Input Integrity

- Canonical files remain unmodified.
- Ground truth SHA256 was hashed before prediction and verified identical after evaluation.
- SHA256: `4b43e879e6124c7b2821ffedfc64c3ff19a825f61b39d7b911d9da209ce69615`

## 6. Sanitization

- Applied deterministic sanitization to all canonical XML files via `sanitize.py`.
- Stripped `LOM-MOD-###` IDs, expected classification labels, explicit case risk tags, and benchmark notes from XML comments and code attributes.
- Preserved complete XML structure, hierarchy, blocks, items, triggers, LOVs, record groups, relations, and executable PL/SQL logic.

## 7. Leakage Validation

- `verify_no_leakage()` scanned all sanitized inputs.
- 0 occurrences of `LOM-MOD-`, benchmark tuples, or ground truth terms were detected.

## 8. Observability

| Category | Count | Percentage | Description |
|:---|---:|---:|:---|
| `FULLY_OBSERVABLE` | 16 | 39.0% | All evidence required by human ground truth is visible in Forms2XML. |
| `PARTIALLY_OBSERVABLE` | 12 | 29.3% | Trigger/item visible in XML, but case rationale references DB DDL/packages. |
| `NOT_OBSERVABLE` | 13 | 31.7% | Case source resides exclusively in database DDL/packages or library docs. |
| **Total** | **41** | **100.0%** | |

## 9. Prediction Coverage

- Total Cases: `41`
- Observable Cases Evaluated: `28`
- Predicted: `28`
- Partial: `0`
- Unsupported: `0`
- Unmatched: `0`

## 10. Classification Metrics

| Metric | Value | Denominator |
|:---|---:|:---|
| Observable Exact Accuracy | 21.4% | 6/28 observable cases |
| Fully Observable Exact Accuracy | 25.0% | 4/16 fully observable cases |
| Macro F1 | 0.1333 | Across present ground-truth classes |

### Per-Class Performance

| Class | Ground Truth | Predicted | True Positives | Precision | Recall | F1 |
|:---|---:|---:|---:|---:|---:|---:|
| `PRESERVE` | 5 | 0 | 0 | 0.00 | 0.00 | 0.00 |
| `CONVERT` | 4 | 11 | 3 | 0.27 | 0.75 | 0.40 |
| `REFACTOR` | 5 | 7 | 0 | 0.00 | 0.00 | 0.00 |
| `MOVE_TO_PLSQL_API` | 5 | 0 | 0 | 0.00 | 0.00 | 0.00 |
| `REPLACE_WITH_APEX_NATIVE` | 4 | 0 | 0 | 0.00 | 0.00 | 0.00 |
| `MANUAL_REVIEW` | 5 | 10 | 3 | 0.30 | 0.60 | 0.40 |
| `DROP` | 0 | 0 | 0 | 0.00 | 0.00 | 0.00 |

## 11. Risk Metrics

| Metric | Value | Denominator / Context |
|:---|---:|:---|
| Exact Risk Accuracy | 21.4% | Observable cases |
| Critical Risk Recall | 0.0% | 2 observable CRITICAL cases |
| High Risk Recall | 0.0% | 4 observable HIGH cases |
| High+Critical Risk Recall | 33.3% | 6 material risk cases |

## 12. Verdict Metrics

- Scored Cases: `5` (only unambiguous mappings: `MANUAL_REVIEW -> MANUAL`, `DROP -> DROP`)
- Exact Verdict Matches: `0`

## 13. Safety Metrics

| Safety Metric | Measured Value | Definition / Target |
|:---|---:|:---|
| Manual Review Recall | 60.0% | Correctly flagged manual-review cases / observable ground-truth MANUAL_REVIEW cases (3/5) |
| False Automation Rate | 40.0% | Cases requiring human review classified as CONVERT or AUTO (2/5) |
| Critical Safety Misses | 0 | Observable CRITICAL cases missed, labeled safe/AUTO, or failing manual review trigger |
| Unsupported Rate | 0.0% | Observable cases returning UNKNOWN/UNSUPPORTED |

## 14. Confusion Matrices

| Truth \ Pred | `PRESERVE` | `CONVERT` | `REFACTOR` | `MOVE_TO_PLSQL_API` | `REPLACE_WITH_APEX_NATIVE` | `MANUAL_REVIEW` | `DROP` | `UNMATCHED` |
|:---|:---|:---|:---|:---|:---|:---|:---|:---|
| `PRESERVE` | 0 | 0 | 1 | 0 | 0 | 4 | 0 | 0 |
| `CONVERT` | 0 | 3 | 1 | 0 | 0 | 0 | 0 | 0 |
| `REFACTOR` | 0 | 3 | 0 | 0 | 0 | 2 | 0 | 0 |
| `MOVE_TO_PLSQL_API` | 0 | 1 | 4 | 0 | 0 | 0 | 0 | 0 |
| `REPLACE_WITH_APEX_NATIVE` | 0 | 2 | 1 | 0 | 0 | 1 | 0 | 0 |
| `MANUAL_REVIEW` | 0 | 2 | 0 | 0 | 0 | 3 | 0 | 0 |
| `DROP` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

## 15. Critical Cases

| Case ID | Observability | Truth Class | Pred Class | Truth Risk | Pred Risk | Verdict | Failure Category |
|:---|:---|:---|:---|:---|:---|:---|:---|
| `LOM-MOD-002` | NOT_OBSERVABLE | `MANUAL_REVIEW` | - | `CRITICAL` | - | - | `SOURCE_NOT_INGESTED` |
| `LOM-MOD-031` | NOT_OBSERVABLE | `MANUAL_REVIEW` | - | `CRITICAL` | - | - | `SOURCE_NOT_INGESTED` |
| `LOM-MOD-041` | PARTIALLY_OBSERVABLE | `MANUAL_REVIEW` | `MANUAL_REVIEW` | `CRITICAL` | `HIGH` | `ASSISTED` | `RISK_MODEL_GAP` |
| `LOM-MOD-042` | PARTIALLY_OBSERVABLE | `MANUAL_REVIEW` | `MANUAL_REVIEW` | `CRITICAL` | `HIGH` | `ASSISTED` | `RISK_MODEL_GAP` |

## 16. High-Risk Cases

| Case ID | Observability | Truth Class | Pred Class | Truth Risk | Pred Risk | Failure Category |
|:---|:---|:---|:---|:---|:---|:---|
| `LOM-MOD-011` | PARTIALLY_OBSERVABLE | `MOVE_TO_PLSQL_API` | `REFACTOR` | `HIGH` | `LOW` | `RULE_MAPPING_GAP` |
| `LOM-MOD-026` | PARTIALLY_OBSERVABLE | `MOVE_TO_PLSQL_API` | `REFACTOR` | `HIGH` | `LOW` | `RULE_MAPPING_GAP` |
| `LOM-MOD-027` | PARTIALLY_OBSERVABLE | `MOVE_TO_PLSQL_API` | `REFACTOR` | `HIGH` | `LOW` | `RULE_MAPPING_GAP` |
| `LOM-MOD-037` | PARTIALLY_OBSERVABLE | `MOVE_TO_PLSQL_API` | `CONVERT` | `HIGH` | `MEDIUM` | `RULE_MAPPING_GAP` |

## 17. Manual Review Cases

| Case ID | Observability | Pred Class | Pred Verdict | Match Status | Safe Intervention Triggered |
|:---|:---|:---|:---|:---|:---|
| `LOM-MOD-002` | NOT_OBSERVABLE | - | - | NOT_OBSERVABLE | N/A (Source not ingested) |
| `LOM-MOD-004` | PARTIALLY_OBSERVABLE | `CONVERT` | `AUTO` | PREDICTED | No (False Automation) |
| `LOM-MOD-005` | NOT_OBSERVABLE | - | - | NOT_OBSERVABLE | N/A (Source not ingested) |
| `LOM-MOD-018` | PARTIALLY_OBSERVABLE | `CONVERT` | `ASSISTED` | PREDICTED | No (False Automation) |
| `LOM-MOD-020` | FULLY_OBSERVABLE | `MANUAL_REVIEW` | `ASSISTED` | PREDICTED | Yes |
| `LOM-MOD-030` | NOT_OBSERVABLE | - | - | NOT_OBSERVABLE | N/A (Source not ingested) |
| `LOM-MOD-031` | NOT_OBSERVABLE | - | - | NOT_OBSERVABLE | N/A (Source not ingested) |
| `LOM-MOD-036` | NOT_OBSERVABLE | - | - | NOT_OBSERVABLE | N/A (Source not ingested) |
| `LOM-MOD-041` | PARTIALLY_OBSERVABLE | `MANUAL_REVIEW` | `ASSISTED` | PREDICTED | Yes |
| `LOM-MOD-042` | PARTIALLY_OBSERVABLE | `MANUAL_REVIEW` | `ASSISTED` | PREDICTED | Yes |

## 18. Mismatches

Total observable classification mismatches: `22` / `28`.

| Case ID | Truth Class | Pred Class | Truth Risk | Pred Risk | Failure Category | Notes |
|:---|:---|:---|:---|:---|:---|:---|
| `LOM-MOD-004` | `MANUAL_REVIEW` | `CONVERT` | `LOW` | `HIGH` | `VERDICT_GAP` | Safety miss: case requiring human review was classified as CONVERT. |
| `LOM-MOD-008` | `REFACTOR` | `CONVERT` | `LOW` | `MEDIUM` | `ARCHITECTURAL_JUDGMENT` | Engine recommended CONVERT where human review determined REFACTOR. |
| `LOM-MOD-010` | `CONVERT` | `REFACTOR` | `LOW` | `LOW` | `ARCHITECTURAL_JUDGMENT` | Engine recommended REFACTOR where human review determined CONVERT. |
| `LOM-MOD-011` | `MOVE_TO_PLSQL_API` | `REFACTOR` | `HIGH` | `LOW` | `RULE_MAPPING_GAP` | Engine taxonomy produced REFACTOR instead of specific modernization class MOVE_TO_PLSQL_API. |
| `LOM-MOD-012` | `REPLACE_WITH_APEX_NATIVE` | `CONVERT` | `LOW` | `HIGH` | `RULE_MAPPING_GAP` | Engine taxonomy produced CONVERT instead of specific modernization class REPLACE_WITH_APEX_NATIVE. |
| `LOM-MOD-014` | `PRESERVE` | `MANUAL_REVIEW` | `LOW` | `MEDIUM` | `ARCHITECTURAL_JUDGMENT` | Engine recommended MANUAL_REVIEW where human review determined PRESERVE. |
| `LOM-MOD-015` | `REPLACE_WITH_APEX_NATIVE` | `REFACTOR` | `LOW` | `LOW` | `RULE_MAPPING_GAP` | Engine taxonomy produced REFACTOR instead of specific modernization class REPLACE_WITH_APEX_NATIVE. |
| `LOM-MOD-016` | `PRESERVE` | `MANUAL_REVIEW` | `LOW` | `HIGH` | `ARCHITECTURAL_JUDGMENT` | Engine recommended MANUAL_REVIEW where human review determined PRESERVE. |
| `LOM-MOD-017` | `REFACTOR` | `CONVERT` | `MEDIUM` | `MEDIUM` | `ARCHITECTURAL_JUDGMENT` | Engine recommended CONVERT where human review determined REFACTOR. |
| `LOM-MOD-018` | `MANUAL_REVIEW` | `CONVERT` | `MEDIUM` | `HIGH` | `VERDICT_GAP` | Safety miss: case requiring human review was classified as CONVERT. |
| `LOM-MOD-019` | `PRESERVE` | `REFACTOR` | `LOW` | `LOW` | `ARCHITECTURAL_JUDGMENT` | Engine recommended REFACTOR where human review determined PRESERVE. |
| `LOM-MOD-021` | `PRESERVE` | `MANUAL_REVIEW` | `LOW` | `HIGH` | `ARCHITECTURAL_JUDGMENT` | Engine recommended MANUAL_REVIEW where human review determined PRESERVE. |
| `LOM-MOD-022` | `REFACTOR` | `MANUAL_REVIEW` | `LOW` | `HIGH` | `ARCHITECTURAL_JUDGMENT` | Engine recommended MANUAL_REVIEW where human review determined REFACTOR. |
| `LOM-MOD-023` | `REFACTOR` | `MANUAL_REVIEW` | `LOW` | `HIGH` | `ARCHITECTURAL_JUDGMENT` | Engine recommended MANUAL_REVIEW where human review determined REFACTOR. |
| `LOM-MOD-025` | `MOVE_TO_PLSQL_API` | `REFACTOR` | `MEDIUM` | `LOW` | `RULE_MAPPING_GAP` | Engine taxonomy produced REFACTOR instead of specific modernization class MOVE_TO_PLSQL_API. |
| `LOM-MOD-026` | `MOVE_TO_PLSQL_API` | `REFACTOR` | `HIGH` | `LOW` | `RULE_MAPPING_GAP` | Engine taxonomy produced REFACTOR instead of specific modernization class MOVE_TO_PLSQL_API. |
| `LOM-MOD-027` | `MOVE_TO_PLSQL_API` | `REFACTOR` | `HIGH` | `LOW` | `RULE_MAPPING_GAP` | Engine taxonomy produced REFACTOR instead of specific modernization class MOVE_TO_PLSQL_API. |
| `LOM-MOD-028` | `PRESERVE` | `MANUAL_REVIEW` | `LOW` | `MEDIUM` | `ARCHITECTURAL_JUDGMENT` | Engine recommended MANUAL_REVIEW where human review determined PRESERVE. |
| `LOM-MOD-029` | `REFACTOR` | `CONVERT` | `MEDIUM` | `MEDIUM` | `ARCHITECTURAL_JUDGMENT` | Engine recommended CONVERT where human review determined REFACTOR. |
| `LOM-MOD-034` | `REPLACE_WITH_APEX_NATIVE` | `MANUAL_REVIEW` | `LOW` | `HIGH` | `RULE_MAPPING_GAP` | Engine taxonomy produced MANUAL_REVIEW instead of specific modernization class REPLACE_WITH_APEX_NATIVE. |
| `LOM-MOD-035` | `REPLACE_WITH_APEX_NATIVE` | `CONVERT` | `LOW` | `MEDIUM` | `RULE_MAPPING_GAP` | Engine taxonomy produced CONVERT instead of specific modernization class REPLACE_WITH_APEX_NATIVE. |
| `LOM-MOD-037` | `MOVE_TO_PLSQL_API` | `CONVERT` | `HIGH` | `MEDIUM` | `RULE_MAPPING_GAP` | Engine taxonomy produced CONVERT instead of specific modernization class MOVE_TO_PLSQL_API. |

## 19. Unsupported Cases

Zero observable cases resulted in `UNSUPPORTED` status. FormsLang blueprint assigned valid decision recommendations across all 28 observable units.

## 20. Failure Analysis Summary

| Failure Category | Count | Primary Cause |
|:---|---:|:---|
| `SOURCE_NOT_INGESTED` | 13 | Breakdown detailed in failure-analysis.md |
| `ARCHITECTURAL_JUDGMENT` | 11 | Breakdown detailed in failure-analysis.md |
| `RULE_MAPPING_GAP` | 9 | Breakdown detailed in failure-analysis.md |
| `RISK_MODEL_GAP` | 5 | Breakdown detailed in failure-analysis.md |
| `VERDICT_GAP` | 2 | Breakdown detailed in failure-analysis.md |
| `NONE` | 1 | Breakdown detailed in failure-analysis.md |

## 21. Per-Case Results (All 41 Cases)

| Case ID | Observability | Truth Class | Pred Class | Truth Risk | Pred Risk | Truth Verdict | Pred Verdict | Match Status | Failure Category | Notes |
|:---|:---|:---|:---|:---|:---|:---|:---|:---|:---|:---|
| `LOM-MOD-001` | NOT_OBSERVABLE | `REFACTOR` | - | `MEDIUM` | - | `NOT_SCORED` | - | NOT_OBSERVABLE | `SOURCE_NOT_INGESTED` | Case source resides exclusively in database packages/DDL/views. Current FormsLang engine does not ingest standalone SQL/PLSQL. |
| `LOM-MOD-002` | NOT_OBSERVABLE | `MANUAL_REVIEW` | - | `CRITICAL` | - | `MANUAL` | - | NOT_OBSERVABLE | `SOURCE_NOT_INGESTED` | Case source resides exclusively in database packages/DDL/views. Current FormsLang engine does not ingest standalone SQL/PLSQL. |
| `LOM-MOD-003` | NOT_OBSERVABLE | `PRESERVE` | - | `LOW` | - | `NOT_SCORED` | - | NOT_OBSERVABLE | `SOURCE_NOT_INGESTED` | Case source resides exclusively in database packages/DDL/views. Current FormsLang engine does not ingest standalone SQL/PLSQL. |
| `LOM-MOD-004` | PARTIALLY_OBSERVABLE | `MANUAL_REVIEW` | `CONVERT` | `LOW` | `HIGH` | `MANUAL` | `AUTO` | PREDICTED | `VERDICT_GAP` | Safety miss: case requiring human review was classified as CONVERT. |
| `LOM-MOD-005` | NOT_OBSERVABLE | `MANUAL_REVIEW` | - | `LOW` | - | `MANUAL` | - | NOT_OBSERVABLE | `SOURCE_NOT_INGESTED` | Case source resides exclusively in database packages/DDL/views. Current FormsLang engine does not ingest standalone SQL/PLSQL. |
| `LOM-MOD-006` | NOT_OBSERVABLE | `REPLACE_WITH_APEX_NATIVE` | - | `LOW` | - | `NOT_SCORED` | - | NOT_OBSERVABLE | `SOURCE_NOT_INGESTED` | Case source resides in library documentation (OM_SHARED.md). Current FormsLang engine does not ingest non-XML documentation. |
| `LOM-MOD-007` | NOT_OBSERVABLE | `DROP` | - | `LOW` | - | `DROP` | - | NOT_OBSERVABLE | `SOURCE_NOT_INGESTED` | Case source resides in library documentation (OM_SHARED.md). Current FormsLang engine does not ingest non-XML documentation. |
| `LOM-MOD-008` | FULLY_OBSERVABLE | `REFACTOR` | `CONVERT` | `LOW` | `MEDIUM` | `NOT_SCORED` | `ASSISTED` | PREDICTED | `ARCHITECTURAL_JUDGMENT` | Engine recommended CONVERT where human review determined REFACTOR. |
| `LOM-MOD-009` | NOT_OBSERVABLE | `PRESERVE` | - | `LOW` | - | `NOT_SCORED` | - | NOT_OBSERVABLE | `SOURCE_NOT_INGESTED` | Case source resides exclusively in database packages/DDL/views. Current FormsLang engine does not ingest standalone SQL/PLSQL. |
| `LOM-MOD-010` | FULLY_OBSERVABLE | `CONVERT` | `REFACTOR` | `LOW` | `LOW` | `NOT_SCORED` | `AUTO` | PREDICTED | `ARCHITECTURAL_JUDGMENT` | Engine recommended REFACTOR where human review determined CONVERT. |
| `LOM-MOD-011` | PARTIALLY_OBSERVABLE | `MOVE_TO_PLSQL_API` | `REFACTOR` | `HIGH` | `LOW` | `NOT_SCORED` | `AUTO` | PREDICTED | `RULE_MAPPING_GAP` | Engine taxonomy produced REFACTOR instead of specific modernization class MOVE_TO_PLSQL_API. |
| `LOM-MOD-012` | FULLY_OBSERVABLE | `REPLACE_WITH_APEX_NATIVE` | `CONVERT` | `LOW` | `HIGH` | `NOT_SCORED` | `AUTO` | PREDICTED | `RULE_MAPPING_GAP` | Engine taxonomy produced CONVERT instead of specific modernization class REPLACE_WITH_APEX_NATIVE. |
| `LOM-MOD-013` | FULLY_OBSERVABLE | `CONVERT` | `CONVERT` | `LOW` | `MEDIUM` | `NOT_SCORED` | `ASSISTED` | PREDICTED | `RISK_MODEL_GAP` | Classification matched (CONVERT) but risk model scored MEDIUM (truth LOW). |
| `LOM-MOD-014` | FULLY_OBSERVABLE | `PRESERVE` | `MANUAL_REVIEW` | `LOW` | `MEDIUM` | `NOT_SCORED` | `ASSISTED` | PREDICTED | `ARCHITECTURAL_JUDGMENT` | Engine recommended MANUAL_REVIEW where human review determined PRESERVE. |
| `LOM-MOD-015` | FULLY_OBSERVABLE | `REPLACE_WITH_APEX_NATIVE` | `REFACTOR` | `LOW` | `LOW` | `NOT_SCORED` | `AUTO` | PREDICTED | `RULE_MAPPING_GAP` | Engine taxonomy produced REFACTOR instead of specific modernization class REPLACE_WITH_APEX_NATIVE. |
| `LOM-MOD-016` | FULLY_OBSERVABLE | `PRESERVE` | `MANUAL_REVIEW` | `LOW` | `HIGH` | `NOT_SCORED` | `ASSISTED` | PREDICTED | `ARCHITECTURAL_JUDGMENT` | Engine recommended MANUAL_REVIEW where human review determined PRESERVE. |
| `LOM-MOD-017` | FULLY_OBSERVABLE | `REFACTOR` | `CONVERT` | `MEDIUM` | `MEDIUM` | `NOT_SCORED` | `ASSISTED` | PREDICTED | `ARCHITECTURAL_JUDGMENT` | Engine recommended CONVERT where human review determined REFACTOR. |
| `LOM-MOD-018` | PARTIALLY_OBSERVABLE | `MANUAL_REVIEW` | `CONVERT` | `MEDIUM` | `HIGH` | `MANUAL` | `ASSISTED` | PREDICTED | `VERDICT_GAP` | Safety miss: case requiring human review was classified as CONVERT. |
| `LOM-MOD-019` | PARTIALLY_OBSERVABLE | `PRESERVE` | `REFACTOR` | `LOW` | `LOW` | `NOT_SCORED` | `AUTO` | PREDICTED | `ARCHITECTURAL_JUDGMENT` | Engine recommended REFACTOR where human review determined PRESERVE. |
| `LOM-MOD-020` | FULLY_OBSERVABLE | `MANUAL_REVIEW` | `MANUAL_REVIEW` | `MEDIUM` | `HIGH` | `MANUAL` | `ASSISTED` | PREDICTED | `RISK_MODEL_GAP` | Classification matched (MANUAL_REVIEW) but risk model scored HIGH (truth MEDIUM). |
| `LOM-MOD-021` | FULLY_OBSERVABLE | `PRESERVE` | `MANUAL_REVIEW` | `LOW` | `HIGH` | `NOT_SCORED` | `ASSISTED` | PREDICTED | `ARCHITECTURAL_JUDGMENT` | Engine recommended MANUAL_REVIEW where human review determined PRESERVE. |
| `LOM-MOD-022` | FULLY_OBSERVABLE | `REFACTOR` | `MANUAL_REVIEW` | `LOW` | `HIGH` | `NOT_SCORED` | `ASSISTED` | PREDICTED | `ARCHITECTURAL_JUDGMENT` | Engine recommended MANUAL_REVIEW where human review determined REFACTOR. |
| `LOM-MOD-023` | FULLY_OBSERVABLE | `REFACTOR` | `MANUAL_REVIEW` | `LOW` | `HIGH` | `NOT_SCORED` | `ASSISTED` | PREDICTED | `ARCHITECTURAL_JUDGMENT` | Engine recommended MANUAL_REVIEW where human review determined REFACTOR. |
| `LOM-MOD-024` | FULLY_OBSERVABLE | `CONVERT` | `CONVERT` | `LOW` | `MEDIUM` | `NOT_SCORED` | `ASSISTED` | PREDICTED | `RISK_MODEL_GAP` | Classification matched (CONVERT) but risk model scored MEDIUM (truth LOW). |
| `LOM-MOD-025` | PARTIALLY_OBSERVABLE | `MOVE_TO_PLSQL_API` | `REFACTOR` | `MEDIUM` | `LOW` | `NOT_SCORED` | `AUTO` | PREDICTED | `RULE_MAPPING_GAP` | Engine taxonomy produced REFACTOR instead of specific modernization class MOVE_TO_PLSQL_API. |
| `LOM-MOD-026` | PARTIALLY_OBSERVABLE | `MOVE_TO_PLSQL_API` | `REFACTOR` | `HIGH` | `LOW` | `NOT_SCORED` | `AUTO` | PREDICTED | `RULE_MAPPING_GAP` | Engine taxonomy produced REFACTOR instead of specific modernization class MOVE_TO_PLSQL_API. |
| `LOM-MOD-027` | PARTIALLY_OBSERVABLE | `MOVE_TO_PLSQL_API` | `REFACTOR` | `HIGH` | `LOW` | `NOT_SCORED` | `AUTO` | PREDICTED | `RULE_MAPPING_GAP` | Engine taxonomy produced REFACTOR instead of specific modernization class MOVE_TO_PLSQL_API. |
| `LOM-MOD-028` | PARTIALLY_OBSERVABLE | `PRESERVE` | `MANUAL_REVIEW` | `LOW` | `MEDIUM` | `NOT_SCORED` | `ASSISTED` | PREDICTED | `ARCHITECTURAL_JUDGMENT` | Engine recommended MANUAL_REVIEW where human review determined PRESERVE. |
| `LOM-MOD-029` | FULLY_OBSERVABLE | `REFACTOR` | `CONVERT` | `MEDIUM` | `MEDIUM` | `NOT_SCORED` | `ASSISTED` | PREDICTED | `ARCHITECTURAL_JUDGMENT` | Engine recommended CONVERT where human review determined REFACTOR. |
| `LOM-MOD-030` | NOT_OBSERVABLE | `MANUAL_REVIEW` | - | `MEDIUM` | - | `MANUAL` | - | NOT_OBSERVABLE | `SOURCE_NOT_INGESTED` | Case source resides exclusively in database packages/DDL/views. Current FormsLang engine does not ingest standalone SQL/PLSQL. |
| `LOM-MOD-031` | NOT_OBSERVABLE | `MANUAL_REVIEW` | - | `CRITICAL` | - | `MANUAL` | - | NOT_OBSERVABLE | `SOURCE_NOT_INGESTED` | Case source resides exclusively in database packages/DDL/views. Current FormsLang engine does not ingest standalone SQL/PLSQL. |
| `LOM-MOD-032` | NOT_OBSERVABLE | `PRESERVE` | - | `LOW` | - | `NOT_SCORED` | - | NOT_OBSERVABLE | `SOURCE_NOT_INGESTED` | Case source resides exclusively in database packages/DDL/views. Current FormsLang engine does not ingest standalone SQL/PLSQL. |
| `LOM-MOD-033` | FULLY_OBSERVABLE | `CONVERT` | `CONVERT` | `LOW` | `LOW` | `NOT_SCORED` | `ASSISTED` | PREDICTED | `NONE` | Matched ground-truth classification and risk level. |
| `LOM-MOD-034` | FULLY_OBSERVABLE | `REPLACE_WITH_APEX_NATIVE` | `MANUAL_REVIEW` | `LOW` | `HIGH` | `NOT_SCORED` | `ASSISTED` | PREDICTED | `RULE_MAPPING_GAP` | Engine taxonomy produced MANUAL_REVIEW instead of specific modernization class REPLACE_WITH_APEX_NATIVE. |
| `LOM-MOD-035` | PARTIALLY_OBSERVABLE | `REPLACE_WITH_APEX_NATIVE` | `CONVERT` | `LOW` | `MEDIUM` | `NOT_SCORED` | `ASSISTED` | PREDICTED | `RULE_MAPPING_GAP` | Engine taxonomy produced CONVERT instead of specific modernization class REPLACE_WITH_APEX_NATIVE. |
| `LOM-MOD-036` | NOT_OBSERVABLE | `MANUAL_REVIEW` | - | `MEDIUM` | - | `MANUAL` | - | NOT_OBSERVABLE | `SOURCE_NOT_INGESTED` | Case source resides exclusively in database packages/DDL/views. Current FormsLang engine does not ingest standalone SQL/PLSQL. |
| `LOM-MOD-037` | PARTIALLY_OBSERVABLE | `MOVE_TO_PLSQL_API` | `CONVERT` | `HIGH` | `MEDIUM` | `NOT_SCORED` | `ASSISTED` | PREDICTED | `RULE_MAPPING_GAP` | Engine taxonomy produced CONVERT instead of specific modernization class MOVE_TO_PLSQL_API. |
| `LOM-MOD-038` | NOT_OBSERVABLE | `DROP` | - | `LOW` | - | `DROP` | - | NOT_OBSERVABLE | `SOURCE_NOT_INGESTED` | Case source resides exclusively in database packages/DDL/views. Current FormsLang engine does not ingest standalone SQL/PLSQL. |
| `LOM-MOD-039` | NOT_OBSERVABLE | `MOVE_TO_PLSQL_API` | - | `MEDIUM` | - | `NOT_SCORED` | - | NOT_OBSERVABLE | `SOURCE_NOT_INGESTED` | Case source resides exclusively in database packages/DDL/views. Current FormsLang engine does not ingest standalone SQL/PLSQL. |
| `LOM-MOD-041` | PARTIALLY_OBSERVABLE | `MANUAL_REVIEW` | `MANUAL_REVIEW` | `CRITICAL` | `HIGH` | `MANUAL` | `ASSISTED` | PREDICTED | `RISK_MODEL_GAP` | Classification matched (MANUAL_REVIEW) but risk model scored HIGH (truth CRITICAL). |
| `LOM-MOD-042` | PARTIALLY_OBSERVABLE | `MANUAL_REVIEW` | `MANUAL_REVIEW` | `CRITICAL` | `HIGH` | `MANUAL` | `ASSISTED` | PREDICTED | `RISK_MODEL_GAP` | Classification matched (MANUAL_REVIEW) but risk model scored HIGH (truth CRITICAL). |

## 22. Limitations

1. **No Standalone SQL/PLSQL Ingestion**: 13/41 cases reside in `.pks`/`.pkb`/`.sql` and are `NOT_OBSERVABLE` to current FormsLang.
2. **Lexical PL/SQL Extraction**: FormsLang extracts calls and DML lexically without semantic compilation or cross-module type resolution.
3. **No Live Oracle Validation**: Baseline operates on structurally valid static fixtures; compilation against a live Oracle Database has not occurred.
4. **Hand-Authored XML**: Forms2XML fixtures are hand-authored per ADR-001 and not generated by Oracle Forms Builder.

## 23. Reproduction

To reproduce this exact baseline:
```bash
# Dry run validation
python examples/modernization-lab/benchmark/run_benchmark.py --dry-run

# Full benchmark run and evaluation
python examples/modernization-lab/benchmark/run_benchmark.py
```
