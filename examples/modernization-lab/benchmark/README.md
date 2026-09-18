# FormsLang Modernization Prediction Benchmark

A reproducible, leak-free evaluation benchmark measuring the modernization decision capabilities of the FormsLang engine against an authoritative, human-reviewed ground truth on `examples/modernization-lab`.

---

## What the Benchmark Does

1. **Sanitizes Fixtures**: Automatically strips all answer-key leakage (case IDs, expected classifications, risk annotations) from Forms2XML files without modifying canonical sources or altering semantic XML structure.
2. **Enforces Strict Isolation**: Verifies zero leakage remains in inputs before invoking the engine. Ground truth is isolated from the predictor.
3. **Executes Real Engine**: Runs `formslang.parser.parse_xml` and `formslang.blueprint.build` to generate raw findings.
4. **Normalizes Predictions**: Maps raw blueprint findings to standard prediction records.
5. **Evaluates Against Ground Truth**: Computes exact classification accuracy, Macro F1, risk accuracy, manual review recall, false automation rate, and confusion matrices.
6. **Freezes Baseline**: Persists frozen, versioned run artifacts into `baselines/v1/`.

---

## Quickstart Commands

### 1. Dry Run
Validates repository state, fixture parsing, sanitization determinism, leakage scanning, and schema conformance without freezing a baseline:
```bash
python examples/modernization-lab/benchmark/run_benchmark.py --dry-run
```

### 2. Full Baseline Execution & Freeze
Runs the entire pipeline, generates predictions, evaluates against ground truth, and freezes baseline `v1`:
```bash
python examples/modernization-lab/benchmark/run_benchmark.py
```

### 3. Evaluate Existing Predictions
Evaluates an existing `predictions.json` offline:
```bash
python examples/modernization-lab/benchmark/evaluate.py --predictions examples/modernization-lab/benchmark/baselines/v1/predictions.json
```

---

## Understanding "Not Observable"

The 41 cases in the ground-truth registry are partitioned into three observability tiers:
- **`FULLY_OBSERVABLE` (16 cases)**: All required evidence is visible in Forms2XML.
- **`PARTIALLY_OBSERVABLE` (12 cases)**: Forms trigger is visible, but rationale cites database packages/DDL.
- **`NOT_OBSERVABLE` (13 cases)**: Source resides exclusively in standalone database packages (`.pks`/`.pkb`), DDL (`.sql`), or documentation (`OM_SHARED.md`).

Because FormsLang's current ingestion engine processes Forms2XML files and does not ingest standalone SQL/PLSQL files, the 13 `NOT_OBSERVABLE` cases are counted as un-ingested source gaps and are excluded from classification accuracy denominators.

---

## Artifact Locations

- **Frozen Baseline v1**: `benchmark/baselines/v1/`
  - `manifest.json`: List of sanitized input files with SHA256 hashes.
  - `observability.json`: Observability categorization for all 41 cases.
  - `raw-analysis.json`: Raw engine output from FormsLang blueprint.
  - `predictions.json`: Normalized predictions.
  - `benchmark-report.json`: Machine-readable evaluation metrics and confusion matrix.
  - `benchmark-report.md`: Human-readable 23-section evaluation report.
  - `failure-analysis.md`: In-depth analysis of mismatches and safety misses.
- **Working / Disposable Outputs**: `benchmark/generated/`
- **Schemas**: `benchmark/schema/`
- **Protocol**: `benchmark/protocol.md`
