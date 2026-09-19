# FormsLang Modernization Prediction Benchmark

A reproducible, leak-free evaluation benchmark measuring the modernization decision capabilities of the FormsLang engine against an authoritative, human-reviewed ground truth on `examples/modernization-lab`.

---

## What the Benchmark Does

1. **Sanitizes Fixtures**: Automatically strips all answer-key leakage (case IDs, expected classifications, risk annotations) from Forms2XML files without modifying canonical sources or altering semantic XML structure.
2. **Enforces Strict Isolation**: Verifies zero leakage remains in inputs before invoking the engine. Ground truth is isolated from the predictor.
3. **Executes Real Engine**: Runs `formslang.parser.parse_xml` and `formslang.blueprint.build` to generate raw findings.
4. **Normalizes Predictions**: Maps raw blueprint findings to standard prediction records.
5. **Evaluates Against Ground Truth**: Computes exact classification accuracy, Macro F1, risk accuracy, manual review recall, false automation rate, and confusion matrices.
6. **Freezes Baseline**: Persists frozen, versioned run artifacts into `baselines/<name>/`. Three baselines exist so far: `v1` (Forms2XML only), `v2` (Forms2XML plus database sources) and `v3` (structural modernization reasoning). A frozen baseline is never edited or re-run; a new engine gets a new directory.

---

## Quickstart Commands

### 1. Dry Run
Validates repository state, fixture parsing, sanitization determinism, leakage scanning, and schema conformance without freezing a baseline:
```bash
python examples/modernization-lab/benchmark/run_benchmark.py --dry-run
```

### 2. Full Baseline Execution & Freeze
Runs the entire pipeline, generates predictions, evaluates against ground
truth and freezes the result. `--baseline-name` names the target directory;
without `--freeze` the run writes only to `generated/`:
```bash
python examples/modernization-lab/benchmark/run_benchmark.py --freeze --baseline-name v4
```
Freezing over an existing baseline requires `--force`, which should not be
needed: the point of a baseline is that it does not move.

### 3. Evaluate Existing Predictions
Evaluates an existing `predictions.json` offline:
```bash
python examples/modernization-lab/benchmark/evaluate.py --predictions examples/modernization-lab/benchmark/baselines/v3/predictions.json
```

---

## Understanding "Not Observable"

Observability says whether the engine can even see the evidence a case
turns on. It is a property of what the engine ingests, so it changed when
the engine learned to read database sources:

| Tier | Under v1 | Under v2 and v3 |
|:---|---:|---:|
| `FULLY_OBSERVABLE` -- all required evidence is visible to the engine | 16 | 38 |
| `PARTIALLY_OBSERVABLE` -- the Forms trigger is visible but the rationale cites database packages or DDL | 12 | 0 |
| `NOT_OBSERVABLE` -- the source is not ingested at all | 13 | 3 |

Under v1 the engine read only Forms2XML, so every case whose rationale cited
a package or DDL fell short. v2 added standalone `.sql` / `.pks` / `.pkb`
ingestion, which promoted 25 cases to fully observable. The three that remain
un-observable live exclusively in `OM_SHARED.md`, a documentation file
standing in for a Forms library; ingesting it is deferred.

Cases in the `NOT_OBSERVABLE` tier are counted as un-ingested source gaps and
excluded from classification accuracy denominators, which is why v2 and v3
report out of 38 rather than 41. Comparing a v1 percentage with a v3
percentage therefore compares two different denominators; the side-by-side
table in `baselines/v3/comparison-v1-v2-v3.md` is the honest version.

---

## Artifact Locations

- **Frozen Baselines**: `benchmark/baselines/v1/`, `v2/`, `v3/`. Each holds:
  - `manifest.json`: List of sanitized input files with SHA256 hashes.
  - `observability.json`: Observability categorization for all 41 cases.
  - `raw-analysis.json`: Raw engine output from FormsLang blueprint.
  - `predictions.json`: Normalized predictions.
  - `benchmark-report.json`: Machine-readable evaluation metrics and confusion matrix.
  - `benchmark-report.md`: Human-readable 23-section evaluation report.
  - `failure-analysis.md`: In-depth analysis of mismatches and safety misses.
  - `comparison-v1-v2-v3.md` (in `v3/` only): per-case comparison across the
    three baselines, including the cases each new engine *lost*.
- **Working / Disposable Outputs**: `benchmark/generated/`
- **Schemas**: `benchmark/schema/`
- **Protocol**: `benchmark/protocol.md`
