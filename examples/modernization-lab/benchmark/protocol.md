# FormsLang Modernization Benchmark Protocol

**Version**: 1.0  
**Target Repository**: `B2DEV-TECH/FormsLang`  
**Primary Target Scenario**: `examples/modernization-lab`  
**Ground Truth Version**: 1.0  
**Runner Version**: 1.0
**Baselines Frozen Under This Protocol**: `v1`, `v2`, `v3`

This protocol is versioned independently of the baselines it governs. All
three baselines so far were produced under protocol 1.0, which is what makes
them comparable; changing the protocol requires restating which baselines a
given number can be compared against.

---

## 1. Benchmark Purpose
The purpose of this benchmark is to rigorously, reproducibly, and honestly measure the capabilities of the existing FormsLang engine when analyzing a realistic, sanitized Oracle Forms portfolio scenario. Specifically, it answers:

> *Given only allowed, sanitized source evidence, what modernization decisions can the current FormsLang system make, and how do those decisions compare with an independent, human-reviewed ground truth?*

The objective is **not** to achieve vanity metrics or 100% accuracy through tuning, but to establish a transparent, unvarnished baseline that senior architects and engineers can audit and trust.

---

## 2. Current Engine Being Tested
- **Entrypoint**: `formslang.blueprint.build(modules, ...)`
- **Parser**: `formslang.parser.parse_xml(path)`
- **Components**:
  - `formslang.parser`: parses Oracle Forms2XML into domain models (`FormModule`, `Block`, `Item`, `Trigger`, etc.).
  - `formslang.analysis`: executes `analyze_unit()`, calculating compatibility findings and engine fingerprints.
  - `formslang.rules`: catalog of Forms built-ins, triggers, and migration verdicts (`AUTO`, `ASSISTED`, `MANUAL`, `DROP`).
  - `formslang.risk`: deterministic risk assessment engine producing raw scores and levels (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).
  - `formslang.plsql` & `formslang.plsql_evidence`: lexical extraction of built-in calls, table references, and DML.
  - `formslang.blueprint`: architecture knowledge graph and recommendation engine emitting decisions (`PRESERVE`, `CONVERT`, `REFACTOR`, `DROP`, `MANUAL_REVIEW`, `UNKNOWN`).
- **Determinism**: 100% deterministic. No AI or external LLM models are invoked.

---

## 3. Threat Model (Answer-Key Leakage)
The primary threat to benchmark validity is **answer-key leakage**.
In the canonical modernisation lab fixtures, triggers and XML attributes contain explicit comments such as:
- Case IDs: `LOM-MOD-013`, `LOM-MOD-027`
- Classification labels: `CONVERT`, `MOVE_TO_PLSQL_API`, `REFACTOR`
- Risk labels: `LOW risk`, `HIGH risk`, `CRITICAL`
- Category labels: `category A`, `category E`
- Rationale or ground-truth citations: `see LOM-MOD-011`, `ground-truth`

Any predictor reading these comments or tokens could trivially achieve 100% accuracy by regurgitating the comments rather than analyzing the source code.
**Rule**: All case-specific answer-key tokens must be deterministically removed before the predictor runs.

---

## 4. Allowed Inputs
The predictor is strictly restricted to:
1. Sanitized Forms2XML documents in `benchmark/generated/input/forms/xml/*.xml`.
2. FormsLang domain model outputs derived directly from those XML files.
3. FormsLang deterministic static analysis, rules catalog, and blueprint graph inferences.

---

## 5. Forbidden Inputs
The predictor must **never** read, parse, or receive:
- The ground truth file: `expected/modernization-ground-truth.json`.
- Narrative documentation: `REVIEW.md`, `HANDOFF.md`, `assessment/complexity-and-risk-rollup.md`, `docs/modernization-challenges.md`, `docs/adr/*.md`, `blueprint/expected-apex-architecture.md`.
- Observability payloads or prior benchmark baseline reports.
- Any benchmark helper functions that bridge to the ground truth.

---

## 6. Sanitization
A deterministic sanitizer (`sanitize.py`) processes all canonical XML files into generated input locations:
- Replaces XML comment blocks containing benchmark citations with generic XML comments.
- Cleans `Tooltip` and `Comment` XML attributes of all `LOM-MOD-###` references.
- Strips benchmark case annotations, classification tuples, and risk labels from `TriggerText` and `ProgramUnitText` attributes while strictly preserving executable PL/SQL statements and indentation.
- Preserves 100% of XML tags, attributes, blocks, items, triggers, LOVs, record groups, relations, and business logic.
- **Determinism Guarantee**: Repeated execution produces byte-identical files.

---

## 7. Leakage Detection
Following sanitization, `sanitize.verify_no_leakage()` scans all generated input files using regular expressions:
- `LOM-MOD-\d+`
- `\bground[-_ ]truth\b`
- `\bexpected[-_ ]decision\b`
- `\bexpected[-_ ]action\b`
- `\b(?:CONVERT|PRESERVE|REFACTOR|MOVE_TO_PLSQL_API|REPLACE_WITH_APEX_NATIVE|MANUAL_REVIEW|DROP)\s*,\s*(?:LOW|MEDIUM|HIGH|CRITICAL)\b`
- `\bcategory\s+[A-F]\b`

If any matching token is found, the run immediately aborts with an exit code of 2.

---

## 8. Observability Analysis
Every ground-truth case is classified into one of three observability tiers:
1. **`FULLY_OBSERVABLE`**: All source artifacts required to make the modernization decision exist within the ingested Forms2XML files.
2. **`PARTIALLY_OBSERVABLE`**: The trigger or component is visible in Forms2XML, but the ground-truth rationale relies on database packages, tables, or external documentation not ingested by the engine.
3. **`NOT_OBSERVABLE`**: The case source resides exclusively in database DDL (`.sql`), database package specs/bodies (`.pks`/`.pkb`), or external documentation (`OM_SHARED.md`).

---

## 9. Prediction Path
1. Parse sanitized XML using `formslang.parser.parse_xml`.
2. Construct Blueprint using `formslang.blueprint.build`.
3. Capture the full raw output in `benchmark/generated/raw-analysis.json`.
4. The predictor assigns decisions based strictly on observed source structure.

---

## 10. Normalization
Raw analysis findings are normalized by `normalize.py` into a standardized format:
- Finding ID and raw output reference.
- Source location tuple: `(module, block, item, trigger, procedure)`.
- Classification recommendation.
- Risk level (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`, `UNKNOWN`).
- Execution verdict (`AUTO`, `ASSISTED`, `MANUAL`, `DROP`, `UNKNOWN`).
- Evidence references.

---

## 11. Source Matching
Predictions are matched to ground-truth cases via structured coordinate matching:
- `module`: Name of the XML module (e.g. `ORDERS`, `CUSTOMERS`).
- `block`: Block name if block-level or item-level, or `None` if form-level.
- `item`: Item name if item-level, or `None` if block-level or form-level.
- `trigger`: Trigger name (e.g. `WHEN-VALIDATE-ITEM`, `PRE-INSERT`).

No loose free-text fuzzy matching is permitted.

---

## 12. Evaluation Eligibility
- **`NOT_OBSERVABLE` cases (13 cases)**: Excluded from classification accuracy denominators. They are counted as un-ingested source gaps, not engine prediction errors.
- **`FULLY_OBSERVABLE` (16 cases) and `PARTIALLY_OBSERVABLE` (12 cases)**: Form the 28 eligible observable cases evaluated for accuracy, F1, risk, and safety.
- Fully observable cases are also scored independently to highlight performance when evidence is completely visible.

---

## 13. Classification Metrics
1. **Exact Accuracy (Observable)**: `exact_matches / observable_cases`.
2. **Exact Accuracy (Fully Observable)**: `exact_matches / fully_observable_cases`.
3. **Macro F1**: Unweighted arithmetic mean of F1 scores across all present ground-truth classes.
4. **Per-Class Precision, Recall, and F1**: Computed transparently per migration class.

---

## 14. Risk Metrics
1. **Exact Risk Accuracy**: Share of observable cases where predicted risk level matches ground truth.
2. **Critical Risk Recall**: Proportion of observable CRITICAL cases correctly flagged as CRITICAL.
3. **High Risk Recall**: Proportion of observable HIGH cases correctly flagged as HIGH.
4. **High+Critical Recall**: Combined recall for all material-risk cases.

---

## 15. Verdict Metrics
- Scored where ground-truth verdict is unambiguous (`MANUAL_REVIEW -> MANUAL`, `DROP -> DROP`).
- All other cases are marked `NOT_SCORED` to avoid fabricating ground truth.

---

## 16. Safety Metrics
1. **Manual Review Recall**:
   $$\frac{\text{Observable MANUAL\_REVIEW cases predicted as MANUAL\_REVIEW or verdict MANUAL}}{\text{Total Observable MANUAL\_REVIEW cases}}$$
2. **False Automation Rate**:
   $$\frac{\text{Observable MANUAL\_REVIEW cases predicted as CONVERT or verdict AUTO}}{\text{Total Observable MANUAL\_REVIEW cases}}$$
3. **Critical Safety Misses**:
   Any observable CRITICAL case that is:
   - Missed entirely (`UNMATCHED`), or
   - Predicted as `AUTO` verdict, or
   - Scored with a benign risk level (`LOW` or `MEDIUM`).
   Target: **0 allowable**.

---

## 17. Baseline Freeze
Once a baseline is generated:
- Outputs are frozen to an immutable version directory, `benchmark/baselines/<name>/`.
- Engine prediction heuristics are **frozen**. No tuning or tweaking is allowed after viewing baseline results.
- Future engine runs must be stored under a new baseline directory. `v1`, `v2`
  and `v3` are taken; the next is `v4`.
- A frozen directory is never edited, re-run or overwritten -- not to correct a
  number, not to re-render a report. The prediction that was made is the
  prediction that stands, including its mistakes. Improvements are a later
  baseline, and the comparison between the two is the deliverable.

---

## 18. Ground-Truth Governance
- Ground truth file: `examples/modernization-lab/expected/modernization-ground-truth.json`.
- The runner computes the SHA256 of the ground truth before the run and asserts it remains identical after evaluation.
- Any modification to ground truth invalidates the run.

---

## 19. Reproducibility
The entire benchmark is runnable with standard Python without proprietary dependencies:
```bash
python examples/modernization-lab/benchmark/run_benchmark.py --dry-run
python examples/modernization-lab/benchmark/run_benchmark.py --freeze --baseline-name v4
```
Outputs are verifiable by inspecting `benchmark/baselines/<name>/`.

---

## 20. Known Limitations
1. ~~**No Standalone SQL Ingestion**~~ -- **lifted for v2 onward.** FormsLang
   ingests database DDL and package files via `--database-src`; the limitation
   as written applies only to baseline `v1`. What remains un-ingested is
   `OM_SHARED.md` (3 cases) and Forms `.pll` libraries.
2. **Lexical PL/SQL Extraction**: FormsLang uses lexical extraction rather than a full semantic PL/SQL compiler.
3. ~~**No Live Oracle DB Execution**~~ -- **lifted 2026-09-19.** The fixtures
   were installed, seeded, verified and reset in a disposable schema on Oracle
   26ai Free 23.26.3.0.0; 54 objects, all `VALID`, 6/6 fixture assertions `OK`.
   See "SQL validation status" in `examples/modernization-lab/REVIEW.md`. This
   validates the fixtures, not the predictions: no engine output is checked
   against a running database.
4. **Hand-Authored XML**: Forms2XML files were hand-crafted per ADR-001 rather than exported from Oracle Forms Builder.
