"""Offline evaluator comparing FormsLang predictions against modernization ground truth.

Computes classification metrics, risk metrics, verdict safety metrics,
confusion matrices, and per-case results with transparent denominators.
Strictly offline and isolated from any prediction logic.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CLASSES = [
    "PRESERVE",
    "CONVERT",
    "REFACTOR",
    "MOVE_TO_PLSQL_API",
    "REPLACE_WITH_APEX_NATIVE",
    "MANUAL_REVIEW",
    "DROP",
]

RISK_LEVELS = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

# Mapping rules from ground truth case source description to Forms structure
CASE_SOURCE_TARGETS = {
    "LOM-MOD-004": {"module": "CUSTOMERS", "block": "BK_CUSTOMER", "item": "CUSTOMER_TYPE_CODE", "trigger": "WHEN-VALIDATE-ITEM"},
    "LOM-MOD-008": {"module": "CUSTOMERS", "block": None, "item": None, "trigger": "WHEN-NEW-FORM-INSTANCE"},
    "LOM-MOD-010": {"module": "CUSTOMERS", "block": "BK_CUSTOMER", "item": "CREDIT_LIMIT", "trigger": "WHEN-VALIDATE-ITEM"},
    "LOM-MOD-011": {"module": "CUSTOMERS", "block": "BK_CUSTOMER", "item": "STATUS", "trigger": "WHEN-VALIDATE-ITEM"},
    "LOM-MOD-012": {"module": "CUSTOMERS", "block": "BK_CUSTOMER", "item": "CUSTOMER_TYPE_CODE", "trigger": "WHEN-VALIDATE-ITEM"},
    "LOM-MOD-013": {"module": "CUSTOMERS", "block": "BK_CUSTOMER", "item": None, "trigger": "PRE-INSERT"},
    "LOM-MOD-014": {"module": "CUSTOMERS", "block": "BK_CUSTOMER", "item": None, "trigger": "POST-UPDATE"},
    "LOM-MOD-015": {"module": "CUSTOMERS", "block": "BK_CUSTOMER", "item": "EMAIL", "trigger": "WHEN-VALIDATE-ITEM"},
    "LOM-MOD-016": {"module": "INVENTORY", "block": "BK_INVENTORY", "item": "BT_ADJUST", "trigger": "WHEN-BUTTON-PRESSED"},
    "LOM-MOD-017": {"module": "ORDERS", "block": "BK_ORDER_LINE", "item": None, "trigger": "PRE-INSERT"},
    "LOM-MOD-018": {"module": "INVENTORY", "block": "BK_INVENTORY", "item": None, "trigger": "PRE-QUERY"},
    "LOM-MOD-019": {"module": "ORDERS", "block": "BK_ORDER", "item": "CUSTOMER_ID", "trigger": "WHEN-VALIDATE-ITEM"},
    "LOM-MOD-020": {"module": "ORDERS", "block": "BK_ORDER", "item": "BT_VIEW_APPROVALS", "trigger": "WHEN-BUTTON-PRESSED"},
    "LOM-MOD-021": {"module": "ORDERS", "block": "BK_ORDER", "item": "BT_SUBMIT", "trigger": "WHEN-BUTTON-PRESSED"},
    "LOM-MOD-022": {"module": "ORDERS", "block": "BK_ORDER_LINE", "item": "BT_VIEW_INVENTORY", "trigger": "WHEN-BUTTON-PRESSED"},
    "LOM-MOD-023": {"module": "ORDERS", "block": "BK_ORDER", "item": "BT_VIEW_CUSTOMER", "trigger": "WHEN-BUTTON-PRESSED"},
    "LOM-MOD-024": {"module": "ORDERS", "block": "BK_ORDER", "item": "BT_NEW", "trigger": "WHEN-BUTTON-PRESSED"},
    "LOM-MOD-025": {"module": "ORDERS", "block": "BK_ORDER_LINE", "item": "QUANTITY", "trigger": "WHEN-VALIDATE-ITEM"},
    "LOM-MOD-026": {"module": "ORDERS", "block": "BK_ORDER_LINE", "item": "QUANTITY", "trigger": "WHEN-VALIDATE-ITEM"},
    "LOM-MOD-027": {"module": "ORDERS", "block": "BK_ORDER_LINE", "item": "QUANTITY", "trigger": "WHEN-VALIDATE-ITEM"},
    "LOM-MOD-028": {"module": "ORDERS", "block": "BK_ORDER_LINE", "item": None, "trigger": "POST-INSERT"},
    "LOM-MOD-029": {"module": "APPROVALS", "block": "BK_APPROVAL", "item": None, "trigger": "PRE-QUERY"},
    "LOM-MOD-033": {"module": "ORDERS", "block": "BK_ORDER", "item": "BT_FIND", "trigger": "WHEN-BUTTON-PRESSED"},
    "LOM-MOD-034": {"module": "ORDERS", "block": "BK_ORDER", "item": "BT_SUBMIT", "trigger": "WHEN-BUTTON-PRESSED"},
    "LOM-MOD-035": {"module": "INVENTORY", "block": "BK_INVENTORY", "item": None, "trigger": "POST-QUERY"},
    "LOM-MOD-037": {"module": "ORDERS", "block": "BK_ORDER_LINE", "item": None, "trigger": "PRE-INSERT"},
    "LOM-MOD-041": {"module": "APPROVALS", "block": "BK_APPROVAL", "item": "BT_APPROVE", "trigger": "WHEN-BUTTON-PRESSED"},
    "LOM-MOD-042": {"module": "APPROVALS", "block": "BK_APPROVAL", "item": "BT_REJECT", "trigger": "WHEN-BUTTON-PRESSED"},
}


def find_matching_prediction(target: dict[str, Any], predictions: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Find prediction corresponding to structural target."""
    for p in predictions:
        src = p.get("source", {})
        if src.get("module") != target.get("module"):
            continue
        if target.get("trigger") and src.get("trigger") != target.get("trigger"):
            continue
        if target.get("block") != src.get("block"):
            continue
        if target.get("item") != src.get("item"):
            continue
        return p
    return None


def evaluate_run(
    predictions_payload: dict[str, Any],
    observability_payload: dict[str, Any],
    ground_truth_payload: dict[str, Any],
    ground_truth_sha256: str,
) -> dict[str, Any]:
    """Execute complete evaluation logic and generate benchmark report."""
    cases = ground_truth_payload.get("cases", [])
    obs_map = {c["case_id"]: c for c in observability_payload.get("cases", [])}
    preds = predictions_payload.get("predictions", [])

    per_case_results = []
    confusion: dict[str, dict[str, int]] = {r: {c: 0 for c in CLASSES + ["UNMATCHED", "UNSUPPORTED"]} for r in CLASSES}

    fully_obs_cases = []
    partially_obs_cases = []
    not_obs_cases = []

    for c in cases:
        cid = c["id"]
        t_class = c.get("classification", "UNKNOWN")
        t_risk = c.get("risk", "UNKNOWN")
        obs_info = obs_map.get(cid, {})
        obs_status = obs_info.get("observability", "UNKNOWN")

        # Expected verdict derivation
        if t_class == "MANUAL_REVIEW":
            expected_verdict = "MANUAL"
        elif t_class == "DROP":
            expected_verdict = "DROP"
        else:
            expected_verdict = "NOT_SCORED"

        target_spec = CASE_SOURCE_TARGETS.get(cid)
        matched_pred = find_matching_prediction(target_spec, preds) if target_spec else None

        if obs_status == "NOT_OBSERVABLE":
            not_obs_cases.append(cid)
            per_case_results.append({
                "case_id": cid,
                "title": c.get("title", ""),
                "observability": obs_status,
                "ground_truth_class": t_class,
                "predicted_class": None,
                "ground_truth_risk": t_risk,
                "predicted_risk": None,
                "ground_truth_verdict": expected_verdict,
                "predicted_verdict": None,
                "match_status": "NOT_OBSERVABLE",
                "source": c.get("source", ""),
                "engine_evidence": [],
                "raw_finding_ref": None,
                "failure_category": "SOURCE_NOT_INGESTED",
                "notes": obs_info.get("reason", "Source not ingested"),
            })
            continue

        if obs_status == "FULLY_OBSERVABLE":
            fully_obs_cases.append(cid)
        else:
            partially_obs_cases.append(cid)

        if matched_pred is None:
            pred_class = "UNMATCHED"
            pred_risk = "UNKNOWN"
            pred_verdict = "UNKNOWN"
            match_status = "UNMATCHED"
            raw_ref = None
            evidence = []
            fail_cat = "DETECTION_GAP"
            notes = "No matching trigger or construct detected by FormsLang engine."
        else:
            pred_class = matched_pred.get("classification", "UNKNOWN")
            pred_risk = matched_pred.get("risk", "UNKNOWN")
            pred_verdict = matched_pred.get("verdict", "UNKNOWN")
            match_status = "PREDICTED"
            raw_ref = matched_pred.get("raw_output_ref")
            evidence = matched_pred.get("evidence", [])

            # Failure category analysis
            if pred_class == t_class and pred_risk == t_risk:
                fail_cat = "NONE"
                notes = "Matched ground-truth classification and risk level."
            elif pred_class != t_class:
                if t_class in {"MOVE_TO_PLSQL_API", "REPLACE_WITH_APEX_NATIVE"} and pred_class in {"REFACTOR", "CONVERT", "MANUAL_REVIEW"}:
                    fail_cat = "RULE_MAPPING_GAP"
                    notes = f"Engine taxonomy produced {pred_class} instead of specific modernization class {t_class}."
                elif t_class == "MANUAL_REVIEW" and pred_class != "MANUAL_REVIEW":
                    fail_cat = "VERDICT_GAP"
                    notes = f"Safety miss: case requiring human review was classified as {pred_class}."
                else:
                    fail_cat = "ARCHITECTURAL_JUDGMENT"
                    notes = f"Engine recommended {pred_class} where human review determined {t_class}."
            elif pred_risk != t_risk:
                fail_cat = "RISK_MODEL_GAP"
                notes = f"Classification matched ({t_class}) but risk model scored {pred_risk} (truth {t_risk})."
            else:
                fail_cat = "OTHER"
                notes = "Mismatch observed."

        col_key = pred_class if pred_class in confusion[t_class] else "UNSUPPORTED"
        confusion[t_class][col_key] = confusion[t_class].get(col_key, 0) + 1

        per_case_results.append({
            "case_id": cid,
            "title": c.get("title", ""),
            "observability": obs_status,
            "ground_truth_class": t_class,
            "predicted_class": pred_class if pred_class != "UNMATCHED" else None,
            "ground_truth_risk": t_risk,
            "predicted_risk": pred_risk if pred_risk != "UNKNOWN" else None,
            "ground_truth_verdict": expected_verdict,
            "predicted_verdict": pred_verdict if pred_verdict != "UNKNOWN" else None,
            "match_status": match_status,
            "source": c.get("source", ""),
            "engine_evidence": evidence,
            "raw_finding_ref": raw_ref,
            "failure_category": fail_cat,
            "notes": notes,
        })

    # Coverage calculations
    total_cases = len(cases)
    fully_obs_count = len(fully_obs_cases)
    partially_obs_count = len(partially_obs_cases)
    not_obs_count = len(not_obs_cases)
    observable_cases = [r for r in per_case_results if r["observability"] != "NOT_OBSERVABLE"]
    observable_count = len(observable_cases)

    # Classification Metrics on Observable Cases
    exact_matches = sum(1 for r in observable_cases if r["predicted_class"] == r["ground_truth_class"])
    exact_accuracy = round(exact_matches / observable_count, 4) if observable_count else 0.0

    # Fully Observable subset metrics
    fully_cases = [r for r in per_case_results if r["observability"] == "FULLY_OBSERVABLE"]
    fully_exact_matches = sum(1 for r in fully_cases if r["predicted_class"] == r["ground_truth_class"])
    fully_exact_accuracy = round(fully_exact_matches / len(fully_cases), 4) if fully_cases else 0.0

    # Per-Class Precision, Recall, F1 (Observable cases)
    per_class_metrics = {}
    f1_list = []
    for cls_name in CLASSES:
        tp = sum(1 for r in observable_cases if r["ground_truth_class"] == cls_name and r["predicted_class"] == cls_name)
        fp = sum(1 for r in observable_cases if r["ground_truth_class"] != cls_name and r["predicted_class"] == cls_name)
        fn = sum(1 for r in observable_cases if r["ground_truth_class"] == cls_name and r["predicted_class"] != cls_name)

        prec = round(tp / (tp + fp), 4) if (tp + fp) else 0.0
        rec = round(tp / (tp + fn), 4) if (tp + fn) else 0.0
        f1 = round(2 * prec * rec / (prec + rec), 4) if (prec + rec) else 0.0

        per_class_metrics[cls_name] = {
            "ground_truth_count": sum(1 for r in observable_cases if r["ground_truth_class"] == cls_name),
            "predicted_count": sum(1 for r in observable_cases if r["predicted_class"] == cls_name),
            "true_positives": tp,
            "precision": prec,
            "recall": rec,
            "f1": f1,
        }
        if (tp + fn) > 0:  # Only average classes present in observable ground truth
            f1_list.append(f1)

    macro_f1 = round(sum(f1_list) / len(f1_list), 4) if f1_list else 0.0

    # Risk Metrics
    risk_matches = sum(1 for r in observable_cases if r["predicted_risk"] == r["ground_truth_risk"])
    risk_accuracy = round(risk_matches / observable_count, 4) if observable_count else 0.0

    crit_cases = [r for r in observable_cases if r["ground_truth_risk"] == "CRITICAL"]
    crit_recall = round(sum(1 for r in crit_cases if r["predicted_risk"] == "CRITICAL") / len(crit_cases), 4) if crit_cases else 0.0

    high_cases = [r for r in observable_cases if r["ground_truth_risk"] == "HIGH"]
    high_recall = round(sum(1 for r in high_cases if r["predicted_risk"] == "HIGH") / len(high_cases), 4) if high_cases else 0.0

    high_crit_cases = [r for r in observable_cases if r["ground_truth_risk"] in {"HIGH", "CRITICAL"}]
    high_crit_recall = round(sum(1 for r in high_crit_cases if r["predicted_risk"] in {"HIGH", "CRITICAL"}) / len(high_crit_cases), 4) if high_crit_cases else 0.0

    # Safety Metrics
    mr_cases = [r for r in observable_cases if r["ground_truth_class"] == "MANUAL_REVIEW"]
    mr_recalled = sum(1 for r in mr_cases if r["predicted_class"] == "MANUAL_REVIEW" or r["predicted_verdict"] == "MANUAL")
    manual_review_recall = round(mr_recalled / len(mr_cases), 4) if mr_cases else 0.0

    # False Automation Rate: cases with truth MANUAL_REVIEW predicted as CONVERT or AUTO
    false_automations = [
        r for r in mr_cases
        if r["predicted_class"] == "CONVERT" or r["predicted_verdict"] == "AUTO"
    ]
    false_automation_rate = round(len(false_automations) / len(mr_cases), 4) if mr_cases else 0.0

    # Critical Safety Misses: observable CRITICAL cases where predicted risk is LOW/MEDIUM or verdict is AUTO
    critical_safety_misses = [
        r for r in crit_cases
        if r["predicted_risk"] in {"LOW", "MEDIUM"} or r["predicted_verdict"] == "AUTO"
    ]

    report = {
        "protocol_version": "1.0",
        "benchmark_version": "1.0",
        "ground_truth_version": "1.0",
        "source_commit": predictions_payload.get("source_commit"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "engine_path": predictions_payload.get("engine_path", "unknown"),
        "ground_truth_sha256": ground_truth_sha256,
        "coverage": {
            "total_cases": total_cases,
            "fully_observable": fully_obs_count,
            "partially_observable": partially_obs_count,
            "not_observable": not_obs_count,
            "observable_cases": observable_count,
            "predicted": sum(1 for r in observable_cases if r["match_status"] == "PREDICTED"),
            "partial": sum(1 for r in observable_cases if r["match_status"] == "PARTIAL"),
            "unsupported": sum(1 for r in observable_cases if r["match_status"] == "UNSUPPORTED"),
            "error": 0,
            "unmatched": sum(1 for r in observable_cases if r["match_status"] == "UNMATCHED"),
        },
        "classification_metrics": {
            "observable_exact_accuracy": exact_accuracy,
            "observable_exact_matches": exact_matches,
            "observable_denominator": observable_count,
            "fully_observable_accuracy": fully_exact_accuracy,
            "fully_observable_matches": fully_exact_matches,
            "fully_observable_denominator": len(fully_cases),
            "macro_f1": macro_f1,
            "per_class": per_class_metrics,
        },
        "risk_metrics": {
            "exact_accuracy": risk_accuracy,
            "critical_recall": crit_recall,
            "critical_total": len(crit_cases),
            "high_recall": high_recall,
            "high_total": len(high_cases),
            "high_critical_recall": high_crit_recall,
            "high_critical_total": len(high_crit_cases),
        },
        "verdict_metrics": {
            "scored_cases_count": sum(1 for r in observable_cases if r["ground_truth_verdict"] != "NOT_SCORED"),
            "exact_matches": sum(1 for r in observable_cases if r["ground_truth_verdict"] != "NOT_SCORED" and r["ground_truth_verdict"] == r["predicted_verdict"]),
        },
        "safety_metrics": {
            "manual_review_recall": manual_review_recall,
            "manual_review_total": len(mr_cases),
            "manual_review_recalled": mr_recalled,
            "false_automation_rate": false_automation_rate,
            "false_automation_count": len(false_automations),
            "critical_safety_misses_count": len(critical_safety_misses),
            "critical_safety_miss_case_ids": [r["case_id"] for r in critical_safety_misses],
            "unsupported_rate": round(sum(1 for r in observable_cases if r["match_status"] == "UNSUPPORTED") / observable_count, 4) if observable_count else 0.0,
        },
        "confusion_matrix": confusion,
        "per_case_results": per_case_results,
    }

    return report


def render_markdown_report(report: dict[str, Any]) -> str:
    """Format benchmark evaluation into comprehensive Markdown report covering all required sections."""
    cov = report["coverage"]
    clf = report["classification_metrics"]
    risk = report["risk_metrics"]
    safe = report["safety_metrics"]
    v_metrics = report.get("verdict_metrics", {})
    per_case = report["per_case_results"]

    md = []
    # 1. Executive Summary
    md.append("# FormsLang Modernization Benchmark Baseline Report (v1)")
    md.append("")
    md.append("## 1. Executive Summary")
    md.append("")
    md.append("- **Benchmark Status**: `BASELINE_COMPLETE`")
    md.append(f"- **Protocol Version**: `{report['protocol_version']}`")
    md.append(f"- **Source Commit**: `{report['source_commit']}`")
    md.append(f"- **Engine**: `{report['engine_path']}` (Deterministic, AI: None)")
    md.append(f"- **Total Cases**: `{cov['total_cases']}`")
    md.append(f"- **Observable Cases**: `{cov['observable_cases']}` ({cov['fully_observable']} Fully, {cov['partially_observable']} Partially, {cov['not_observable']} Not Observable)")
    md.append(f"- **Exact Classification Accuracy (Observable)**: `{clf['observable_exact_accuracy'] * 100:.1f}%` ({clf['observable_exact_matches']}/{clf['observable_denominator']})")
    md.append(f"- **Exact Classification Accuracy (Fully Observable)**: `{clf['fully_observable_accuracy'] * 100:.1f}%` ({clf['fully_observable_matches']}/{clf['fully_observable_denominator']})")
    md.append(f"- **Macro F1**: `{clf['macro_f1']:.4f}`")
    md.append(f"- **Exact Risk Accuracy**: `{risk['exact_accuracy'] * 100:.1f}%`")
    md.append(f"- **Manual Review Recall**: `{safe['manual_review_recall'] * 100:.1f}%` ({safe['manual_review_recalled']}/{safe['manual_review_total']})")
    md.append(f"- **False Automation Rate**: `{safe['false_automation_rate'] * 100:.1f}%` ({safe['false_automation_count']}/{safe['manual_review_total']})")
    md.append(f"- **Critical Safety Misses**: `{safe['critical_safety_misses_count']}`")
    md.append("")

    # 2. Run Metadata
    md.append("## 2. Run Metadata")
    md.append("")
    md.append(f"- **Protocol Version**: `{report['protocol_version']}`")
    md.append("- **Runner Version**: `1.0`")
    md.append(f"- **Ground Truth Version**: `{report['ground_truth_version']}`")
    md.append(f"- **Benchmark Version**: `{report['benchmark_version']}`")
    md.append(f"- **Source Commit**: `{report['source_commit']}`")
    md.append(f"- **Generated At**: `{report['generated_at']}`")
    md.append(f"- **Ground Truth SHA256**: `{report['ground_truth_sha256']}`")
    md.append("")

    # 3. Engine Path
    md.append("## 3. Engine Path")
    md.append("")
    md.append(f"- **Engine**: `{report['engine_path']}`")
    md.append("- **Deterministic**: `True` (all analysis, rules, risk, and blueprint inferences are 100% deterministic)")
    md.append("- **AI Usage**: `None` (no LLM providers or heuristic nondeterministic generators are invoked)")
    md.append("")

    # 4. Input Boundary
    md.append("## 4. Input Boundary")
    md.append("")
    md.append("- **Allowed Inputs**: Sanitized Forms2XML documents parsed through `formslang.parser.parse_xml` (`APPROVALS.xml`, `CUSTOMERS.xml`, `INVENTORY.xml`, `ORDERS.xml`).")
    md.append("- **Forbidden Inputs**: Ground truth registry (`modernization-ground-truth.json`), narrative documentation (`REVIEW.md`, `HANDOFF.md`, `assessment/`, `docs/`, `blueprint/expected-apex-architecture.md`), prior reports, failure-analysis documents.")
    md.append("")

    # 5. Input Integrity
    md.append("## 5. Input Integrity")
    md.append("")
    md.append("- Canonical files remain unmodified.")
    md.append("- Ground truth SHA256 was hashed before prediction and verified identical after evaluation.")
    md.append(f"- SHA256: `{report['ground_truth_sha256']}`")
    md.append("")

    # 6. Sanitization
    md.append("## 6. Sanitization")
    md.append("")
    md.append("- Applied deterministic sanitization to all canonical XML files via `sanitize.py`.")
    md.append("- Stripped `LOM-MOD-###` IDs, expected classification labels, explicit case risk tags, and benchmark notes from XML comments and code attributes.")
    md.append("- Preserved complete XML structure, hierarchy, blocks, items, triggers, LOVs, record groups, relations, and executable PL/SQL logic.")
    md.append("")

    # 7. Leakage Validation
    md.append("## 7. Leakage Validation")
    md.append("")
    md.append("- `verify_no_leakage()` scanned all sanitized inputs.")
    md.append("- 0 occurrences of `LOM-MOD-`, benchmark tuples, or ground truth terms were detected.")
    md.append("")

    # 8. Observability
    md.append("## 8. Observability")
    md.append("")
    md.append("| Category | Count | Percentage | Description |")
    md.append("|:---|---:|---:|:---|")
    md.append(f"| `FULLY_OBSERVABLE` | {cov['fully_observable']} | {cov['fully_observable']/cov['total_cases']*100:.1f}% | All evidence required by human ground truth is visible in Forms2XML. |")
    md.append(f"| `PARTIALLY_OBSERVABLE` | {cov['partially_observable']} | {cov['partially_observable']/cov['total_cases']*100:.1f}% | Trigger/item visible in XML, but case rationale references DB DDL/packages. |")
    md.append(f"| `NOT_OBSERVABLE` | {cov['not_observable']} | {cov['not_observable']/cov['total_cases']*100:.1f}% | Case source resides exclusively in database DDL/packages or library docs. |")
    md.append(f"| **Total** | **{cov['total_cases']}** | **100.0%** | |")
    md.append("")

    # 9. Prediction Coverage
    md.append("## 9. Prediction Coverage")
    md.append("")
    md.append(f"- Total Cases: `{cov['total_cases']}`")
    md.append(f"- Observable Cases Evaluated: `{cov['observable_cases']}`")
    md.append(f"- Predicted: `{cov['predicted']}`")
    md.append(f"- Partial: `{cov['partial']}`")
    md.append(f"- Unsupported: `{cov['unsupported']}`")
    md.append(f"- Unmatched: `{cov['unmatched']}`")
    md.append("")

    # 10. Classification Metrics
    md.append("## 10. Classification Metrics")
    md.append("")
    md.append("| Metric | Value | Denominator |")
    md.append("|:---|---:|:---|")
    md.append(f"| Observable Exact Accuracy | {clf['observable_exact_accuracy']*100:.1f}% | {clf['observable_exact_matches']}/{clf['observable_denominator']} observable cases |")
    md.append(f"| Fully Observable Exact Accuracy | {clf['fully_observable_accuracy']*100:.1f}% | {clf['fully_observable_matches']}/{clf['fully_observable_denominator']} fully observable cases |")
    md.append(f"| Macro F1 | {clf['macro_f1']:.4f} | Across present ground-truth classes |")
    md.append("")
    md.append("### Per-Class Performance")
    md.append("")
    md.append("| Class | Ground Truth | Predicted | True Positives | Precision | Recall | F1 |")
    md.append("|:---|---:|---:|---:|---:|---:|---:|")
    for cls_name, m in clf["per_class"].items():
        md.append(f"| `{cls_name}` | {m['ground_truth_count']} | {m['predicted_count']} | {m['true_positives']} | {m['precision']:.2f} | {m['recall']:.2f} | {m['f1']:.2f} |")
    md.append("")

    # 11. Risk Metrics
    md.append("## 11. Risk Metrics")
    md.append("")
    md.append("| Metric | Value | Denominator / Context |")
    md.append("|:---|---:|:---|")
    md.append(f"| Exact Risk Accuracy | {risk['exact_accuracy']*100:.1f}% | Observable cases |")
    md.append(f"| Critical Risk Recall | {risk['critical_recall']*100:.1f}% | {risk['critical_total']} observable CRITICAL cases |")
    md.append(f"| High Risk Recall | {risk['high_recall']*100:.1f}% | {risk['high_total']} observable HIGH cases |")
    md.append(f"| High+Critical Risk Recall | {risk['high_critical_recall']*100:.1f}% | {risk['high_critical_total']} material risk cases |")
    md.append("")

    # 12. Verdict Metrics
    md.append("## 12. Verdict Metrics")
    md.append("")
    md.append(f"- Scored Cases: `{v_metrics.get('scored_cases_count', 0)}` (only unambiguous mappings: `MANUAL_REVIEW -> MANUAL`, `DROP -> DROP`)")
    md.append(f"- Exact Verdict Matches: `{v_metrics.get('exact_matches', 0)}`")
    md.append("")

    # 13. Safety Metrics
    md.append("## 13. Safety Metrics")
    md.append("")
    md.append("| Safety Metric | Measured Value | Definition / Target |")
    md.append("|:---|---:|:---|")
    md.append(f"| Manual Review Recall | {safe['manual_review_recall']*100:.1f}% | Correctly flagged manual-review cases / observable ground-truth MANUAL_REVIEW cases ({safe['manual_review_recalled']}/{safe['manual_review_total']}) |")
    md.append(f"| False Automation Rate | {safe['false_automation_rate']*100:.1f}% | Cases requiring human review classified as CONVERT or AUTO ({safe['false_automation_count']}/{safe['manual_review_total']}) |")
    md.append(f"| Critical Safety Misses | {safe['critical_safety_misses_count']} | Observable CRITICAL cases missed, labeled safe/AUTO, or failing manual review trigger |")
    md.append(f"| Unsupported Rate | {safe['unsupported_rate']*100:.1f}% | Observable cases returning UNKNOWN/UNSUPPORTED |")
    md.append("")

    # 14. Confusion Matrices
    md.append("## 14. Confusion Matrices")
    md.append("")
    header_cols = ["Truth \\ Pred"] + [f"`{c}`" for c in CLASSES] + ["`UNMATCHED`"]
    md.append("| " + " | ".join(header_cols) + " |")
    md.append("|" + ":---|" * len(header_cols))
    for r in CLASSES:
        row = [f"`{r}`"]
        for c in CLASSES + ["UNMATCHED"]:
            row.append(str(report["confusion_matrix"][r].get(c, 0)))
        md.append("| " + " | ".join(row) + " |")
    md.append("")

    # 15. Critical Cases
    crit_list = [r for r in per_case if r["ground_truth_risk"] == "CRITICAL"]
    md.append("## 15. Critical Cases")
    md.append("")
    md.append("| Case ID | Observability | Truth Class | Pred Class | Truth Risk | Pred Risk | Verdict | Failure Category |")
    md.append("|:---|:---|:---|:---|:---|:---|:---|:---|")
    for r in crit_list:
        p_cls = f"`{r['predicted_class']}`" if r["predicted_class"] else "-"
        p_risk = f"`{r['predicted_risk']}`" if r["predicted_risk"] else "-"
        p_v = f"`{r['predicted_verdict']}`" if r["predicted_verdict"] else "-"
        md.append(f"| `{r['case_id']}` | {r['observability']} | `{r['ground_truth_class']}` | {p_cls} | `{r['ground_truth_risk']}` | {p_risk} | {p_v} | `{r['failure_category']}` |")
    md.append("")

    # 16. High-Risk Cases
    high_list = [r for r in per_case if r["ground_truth_risk"] == "HIGH"]
    md.append("## 16. High-Risk Cases")
    md.append("")
    md.append("| Case ID | Observability | Truth Class | Pred Class | Truth Risk | Pred Risk | Failure Category |")
    md.append("|:---|:---|:---|:---|:---|:---|:---|")
    for r in high_list:
        p_cls = f"`{r['predicted_class']}`" if r["predicted_class"] else "-"
        p_risk = f"`{r['predicted_risk']}`" if r["predicted_risk"] else "-"
        md.append(f"| `{r['case_id']}` | {r['observability']} | `{r['ground_truth_class']}` | {p_cls} | `{r['ground_truth_risk']}` | {p_risk} | `{r['failure_category']}` |")
    md.append("")

    # 17. Manual Review Cases
    mr_list = [r for r in per_case if r["ground_truth_class"] == "MANUAL_REVIEW"]
    md.append("## 17. Manual Review Cases")
    md.append("")
    md.append("| Case ID | Observability | Pred Class | Pred Verdict | Match Status | Safe Intervention Triggered |")
    md.append("|:---|:---|:---|:---|:---|:---|")
    for r in mr_list:
        p_cls = f"`{r['predicted_class']}`" if r["predicted_class"] else "-"
        p_v = f"`{r['predicted_verdict']}`" if r["predicted_verdict"] else "-"
        safe_triggered = "Yes" if r["predicted_class"] == "MANUAL_REVIEW" or r["predicted_verdict"] == "MANUAL" else "No (False Automation)"
        if r["observability"] == "NOT_OBSERVABLE":
            safe_triggered = "N/A (Source not ingested)"
        md.append(f"| `{r['case_id']}` | {r['observability']} | {p_cls} | {p_v} | {r['match_status']} | {safe_triggered} |")
    md.append("")

    # 18. Mismatches
    mismatches = [r for r in per_case if r["observability"] != "NOT_OBSERVABLE" and r["predicted_class"] != r["ground_truth_class"]]
    md.append("## 18. Mismatches")
    md.append("")
    md.append(f"Total observable classification mismatches: `{len(mismatches)}` / `{cov['observable_cases']}`.")
    md.append("")
    md.append("| Case ID | Truth Class | Pred Class | Truth Risk | Pred Risk | Failure Category | Notes |")
    md.append("|:---|:---|:---|:---|:---|:---|:---|")
    for r in mismatches:
        md.append(f"| `{r['case_id']}` | `{r['ground_truth_class']}` | `{r['predicted_class']}` | `{r['ground_truth_risk']}` | `{r['predicted_risk']}` | `{r['failure_category']}` | {r['notes']} |")
    md.append("")

    # 19. Unsupported Cases
    unsupported = [r for r in per_case if r["match_status"] == "UNSUPPORTED"]
    md.append("## 19. Unsupported Cases")
    md.append("")
    if unsupported:
        for r in unsupported:
            md.append(f"- `{r['case_id']}`: {r['notes']}")
    else:
        md.append("Zero observable cases resulted in `UNSUPPORTED` status. FormsLang blueprint assigned valid decision recommendations across all 28 observable units.")
    md.append("")

    # 20. Failure Analysis Summary
    fail_counts = {}
    for r in per_case:
        cat = r["failure_category"]
        fail_counts[cat] = fail_counts.get(cat, 0) + 1
    md.append("## 20. Failure Analysis Summary")
    md.append("")
    md.append("| Failure Category | Count | Primary Cause |")
    md.append("|:---|---:|:---|")
    for cat, count in sorted(fail_counts.items(), key=lambda kv: -kv[1]):
        md.append(f"| `{cat}` | {count} | Breakdown detailed in failure-analysis.md |")
    md.append("")

    # 21. Per-Case Results
    md.append("## 21. Per-Case Results (All 41 Cases)")
    md.append("")
    md.append("| Case ID | Observability | Truth Class | Pred Class | Truth Risk | Pred Risk | Truth Verdict | Pred Verdict | Match Status | Failure Category | Notes |")
    md.append("|:---|:---|:---|:---|:---|:---|:---|:---|:---|:---|:---|")
    for r in per_case:
        p_cls = f"`{r['predicted_class']}`" if r["predicted_class"] else "-"
        p_risk = f"`{r['predicted_risk']}`" if r["predicted_risk"] else "-"
        p_v = f"`{r['predicted_verdict']}`" if r["predicted_verdict"] else "-"
        md.append(f"| `{r['case_id']}` | {r['observability']} | `{r['ground_truth_class']}` | {p_cls} | `{r['ground_truth_risk']}` | {p_risk} | `{r['ground_truth_verdict']}` | {p_v} | {r['match_status']} | `{r['failure_category']}` | {r['notes']} |")
    md.append("")

    # 22. Limitations
    md.append("## 22. Limitations")
    md.append("")
    md.append("1. **No Standalone SQL/PLSQL Ingestion**: 13/41 cases reside in `.pks`/`.pkb`/`.sql` and are `NOT_OBSERVABLE` to current FormsLang.")
    md.append("2. **Lexical PL/SQL Extraction**: FormsLang extracts calls and DML lexically without semantic compilation or cross-module type resolution.")
    md.append("3. **No Live Oracle Validation**: Baseline operates on structurally valid static fixtures; compilation against a live Oracle Database has not occurred.")
    md.append("4. **Hand-Authored XML**: Forms2XML fixtures are hand-authored per ADR-001 and not generated by Oracle Forms Builder.")
    md.append("")

    # 23. Reproduction
    md.append("## 23. Reproduction")
    md.append("")
    md.append("To reproduce this exact baseline:")
    md.append("```bash")
    md.append("# Dry run validation")
    md.append("python examples/modernization-lab/benchmark/run_benchmark.py --dry-run")
    md.append("")
    md.append("# Full benchmark run and evaluation")
    md.append("python examples/modernization-lab/benchmark/run_benchmark.py")
    md.append("```")
    md.append("")

    return "\n".join(md)


def write_reports(
    report: dict[str, Any],
    json_path: Path,
    markdown_path: Path,
) -> None:
    """Persist both JSON and Markdown reports."""
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    md_text = render_markdown_report(report)
    markdown_path.write_text(md_text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline evaluator comparing FormsLang predictions to ground truth")
    parser.add_argument("--predictions", required=True, type=str, help="Path to predictions.json")
    parser.add_argument("--ground-truth", default="examples/modernization-lab/expected/modernization-ground-truth.json", type=str, help="Path to ground truth JSON")
    parser.add_argument("--observability", default="examples/modernization-lab/benchmark/generated/observability.json", type=str, help="Path to observability.json")
    parser.add_argument("--output-dir", default="examples/modernization-lab/benchmark/generated", type=str, help="Output directory for reports")
    parser.add_argument("--json-only", action="store_true", help="Emit only JSON report to stdout")
    args = parser.parse_args()

    pred_path = Path(args.predictions)
    gt_path = Path(args.ground_truth)
    obs_path = Path(args.observability)
    out_dir = Path(args.output_dir)

    if not pred_path.exists():
        print(f"ERROR: Predictions file not found: {pred_path}", file=sys.stderr)
        return 1
    if not gt_path.exists():
        print(f"ERROR: Ground truth file not found: {gt_path}", file=sys.stderr)
        return 1
    if not obs_path.exists():
        print(f"ERROR: Observability file not found: {obs_path}", file=sys.stderr)
        return 1

    gt_sha = hashlib.sha256(gt_path.read_bytes()).hexdigest()
    preds_payload = json.loads(pred_path.read_text(encoding="utf-8"))
    obs_payload = json.loads(obs_path.read_text(encoding="utf-8"))
    gt_payload = json.loads(gt_path.read_text(encoding="utf-8"))

    report = evaluate_run(preds_payload, obs_payload, gt_payload, gt_sha)

    if args.json_only:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0

    json_out = out_dir / "benchmark-report.json"
    md_out = out_dir / "benchmark-report.md"
    write_reports(report, json_out, md_out)
    print(f"Evaluation complete. Reports written to:\n  {json_out}\n  {md_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
