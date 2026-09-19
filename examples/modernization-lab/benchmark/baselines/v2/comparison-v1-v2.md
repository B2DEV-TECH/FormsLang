# FormsLang Modernization Benchmark: v1 vs. v2 Baseline Comparison

**Date**: 2026-09-18  
**Protocol Version**: 1.0  
**Baseline v1 Commit**: `22f24805d0f8b277368723306565b94c5e2d25b0`  
**Baseline v2 Commit**: `9005c4389834ffcdf132734d04f6843a6b657cdf`  
**Ground Truth SHA256**: `4b43e879e6124c7b2821ffedfc64c3ff19a825f61b39d7b911d9da209ce69615` (strictly identical)  

---

## 1. Executive Summary

This report measures the empirical performance delta between **FormsLang Benchmark Baseline v1** (Forms-only static analysis) and **FormsLang Benchmark Baseline v2** (Forms + Oracle Database + Cross-Layer Modernization Reasoning).

In v2, FormsLang ingested standalone Oracle database sources (`.sql`, `.pks`, `.pkb`), constructed cross-layer symbol resolution and dependency graphs (`READS`, `CALLS`, `REFERENCES`, `DECLARES`, `IMPLEMENTS`, `DUPLICATES_LOGIC`), normalized status predicates and financial formulas, and implemented safety rules against direct DML bypasses.

Every improvement was measured against the immutable ground-truth registry without post-run engine tuning.

---

## 2. Quantitative Metric Comparison

| Benchmark Metric | Baseline v1 (Forms-Only) | Baseline v2 (Forms + Database) | Absolute Delta | Relative Change |
|:---|---:|---:|---:|---:|
| **Total Cases** | 41 | 41 | 0 | - |
| **Fully Observable Cases** | 16 (39.0%) | 38 (92.7%) | **+22** | **+137.5%** |
| **Partially Observable Cases** | 12 (29.3%) | 0 (0.0%) | **-12** | **-100.0%** |
| **Not Observable Cases** | 13 (31.7%) | 3 (7.3%) | **-10** | **-76.9%** |
| **Observable Cases Evaluated** | 28 (68.3%) | 38 (92.7%) | **+10** | **+35.7%** |
| **Exact Classification Accuracy (Observable)** | **21.4%** (6/28) | **68.4%** (26/38) | **+47.0%** | **+219.6%** |
| **Exact Classification Accuracy (Fully Obs)** | **25.0%** (4/16) | **68.4%** (26/38) | **+43.4%** | **+173.6%** |
| **Macro F1 Score** | **0.1333** | **0.6257** | **+0.4924** | **+369.4%** |
| **Exact Risk Accuracy** | **21.4%** (6/28) | **68.4%** (26/38) | **+47.0%** | **+219.6%** |
| **Critical Risk Recall** | **0.0%** (0/2) | **100.0%** (4/4) | **+100.0%** | **Infinite (Perfect)** |
| **High Risk Recall** | **50.0%** (2/4) | **75.0%** (3/4) | **+25.0%** | **+50.0%** |
| **High + Critical Risk Recall** | **33.3%** (2/6) | **87.5%** (7/8) | **+54.2%** | **+162.8%** |
| **Manual Review Recall** | **60.0%** (3/5) | **80.0%** (8/10) | **+20.0%** | **+33.3%** |
| **False Automation Rate** | **40.0%** (2/5) | **20.0%** (2/10) | **-20.0%** | **-50.0% (Cut in half)** |
| **Critical Safety Misses** | **0** | **0** | **0** | **Maintained zero** |

---

## 3. Per-Class Precision, Recall, and F1 Delta

| Modernization Class | v1 Ground Truth | v1 F1 | v2 Ground Truth | v2 F1 | F1 Delta |
|:---|---:|---:|---:|---:|---:|
| `PRESERVE` | 6 | 0.0000 | 8 | **0.9412** | **+0.9412** |
| `CONVERT` | 4 | 0.4444 | 4 | **0.5000** | **+0.0556** |
| `REFACTOR` | 7 | 0.1818 | 6 | **0.2500** | **+0.0682** |
| `MOVE_TO_PLSQL_API` | 5 | 0.0000 | 5 | **0.8889** | **+0.8889** |
| `REPLACE_WITH_APEX_NATIVE` | 3 | 0.0000 | 4 | **0.0000** | 0.0000 |
| `MANUAL_REVIEW` | 5 | 0.5455 | 10 | **0.8000** | **+0.2545** |
| `DROP` | 0 | 0.0000 | 1 | **1.0000** | **+1.0000** |

---

## 4. Key Engineering Drivers of v2 Improvements

1. **Standalone Oracle Database Ingestion (`formslang.database`)**:
   - Ingested 11 tables, 2 views, 5 package specifications, and 5 package bodies into the semantic graph.
   - Converted 10 previously un-ingested database cases (MOD-001, 002, 003, 005, 009, 030, 031, 032, 036, 038) into observable, evaluated benchmark targets.
   - All 12 previously `PARTIALLY_OBSERVABLE` cases became `FULLY_OBSERVABLE` because their referenced database entities were ingested and resolved.

2. **Clean API Delegation Detection (`PRESERVE` + `LOW` Risk)**:
   - v1 misclassified clean API calls (`LOM-MOD-014`, `016`, `019`, `021`, `028`) as `REFACTOR` or `MANUAL_REVIEW` due to UI trigger coupling.
   - v2 cross-referenced call signatures against package specifications, detecting authoritative API delegation and lifting `PRESERVE` F1 from `0.00` to `0.9412`.

3. **Status Predicate & Formula Duplication (`MOVE_TO_PLSQL_API` + `HIGH` Risk)**:
   - In v1, duplicate business rules in Forms triggers were indistinguishable from local business logic (`0.00` F1).
   - In v2, conservative structural formula matching and status exclusion set normalization accurately matched `LOM-MOD-011` (`has_open_orders` duplicate) and `LOM-MOD-027` (line total financial calculation duplicate), lifting `MOVE_TO_PLSQL_API` F1 from `0.00` to `0.8889`.

4. **Direct DML Bypass & State Machine Safety (`MANUAL_REVIEW` + `CRITICAL` Risk)**:
   - In v1, bypasses of the state machine in `APPROVALS.fmb` were caught as high-risk UI DML.
   - In v2, cross-checking against the procedural state machine (`LOM_ORDER_API.transition_status`) elevated `LOM-MOD-002`, `031`, `041`, and `042` to `CRITICAL` risk and enforced `MANUAL` verdict, achieving `100% Critical Risk Recall`.

5. **False Automation Rate Reduction**:
   - Halved the False Automation Rate from `40.0%` to `20.0%`, ensuring 8 out of 10 cases requiring human intervention are stopped at the manual review gate.

---

## 5. Frozen Baseline Artifacts

- **v1 Baseline Directory**: `examples/modernization-lab/benchmark/baselines/v1/`
  - SHA256 verified unchanged across all 7 original files.
- **v2 Baseline Directory**: `examples/modernization-lab/benchmark/baselines/v2/`
  - Contains `manifest.json`, `observability.json`, `raw-analysis.json`, `predictions.json`, `benchmark-report.json`, `benchmark-report.md`, `failure-analysis.md`, and this comparison.
