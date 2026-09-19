"""Main CLI orchestrator for FormsLang Modernization Prediction Benchmark.

Usage:
    python benchmark/run_benchmark.py --dry-run
    python benchmark/run_benchmark.py
    python benchmark/run_benchmark.py --freeze
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Relative imports within benchmark package
BENCHMARK_DIR = Path(__file__).resolve().parent
LAB_ROOT = BENCHMARK_DIR.parent
REPO_ROOT = LAB_ROOT.parent.parent

sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(BENCHMARK_DIR))

import discover
import evaluate
import normalize
import predict
import sanitize


def get_git_commit(repo_root: Path) -> str | None:
    """Extract current git commit SHA or return None if unavailable."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return None


def get_file_sha256(path: Path) -> str:
    """Calculate SHA256 hash of file contents."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="FormsLang Modernization Prediction Benchmark Runner")
    parser.add_argument("--dry-run", action="store_true", help="Validate fixtures, schemas, and pipeline without baseline freeze")
    parser.add_argument("--freeze", action="store_true", help="Freeze outputs to versioned baseline directory (see --baseline-name)")
    parser.add_argument(
        "--baseline-name",
        help="Target baseline directory name. Required with --freeze; "
        "a frozen baseline is never re-used, so name the next one.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing baseline directory. The protocol says a "
        "frozen baseline does not move, so this should not be needed.",
    )
    parser.add_argument("--predictions", type=str, help="Evaluate existing predictions file directly")
    args = parser.parse_args()

    config_path = BENCHMARK_DIR / "benchmark-config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))

    gt_path = LAB_ROOT / config["ground_truth_path"]
    if not gt_path.exists():
        print(f"ERROR: Ground truth file not found: {gt_path}", file=sys.stderr)
        return 1

    # 1. Pre-run SHA256 of Ground Truth
    gt_sha_before = get_file_sha256(gt_path)
    print(f"[1/8] Ground truth verified (SHA256: {gt_sha_before[:12]}...)")

    source_commit = get_git_commit(REPO_ROOT)
    print(f"      Source commit: {source_commit or 'UNAVAILABLE'}")

    generated_dir = LAB_ROOT / config["generated_dir"]
    input_xml_dir = generated_dir / "input" / "forms" / "xml"
    input_xml_dir.mkdir(parents=True, exist_ok=True)

    # 2. Sanitize Canonical XML and Database Sources
    print("[2/8] Sanitizing Forms2XML and database source fixtures...")
    canonical_xml_dir = LAB_ROOT / config["canonical_xml_dir"]
    canonical_db_dir = LAB_ROOT / config.get("canonical_database_dir", "database")
    input_db_dir = generated_dir / "input" / "database"
    manifest_files = []

    for xml_file in sorted(canonical_xml_dir.glob("*.xml")):
        orig_sha = get_file_sha256(xml_file)
        dest_path = input_xml_dir / xml_file.name
        san_sha = sanitize.sanitize_file(xml_file, dest_path)
        manifest_files.append({
            "original_path": f"forms/xml/{xml_file.name}",
            "sanitized_path": f"benchmark/generated/input/forms/xml/{xml_file.name}",
            "original_sha256": orig_sha,
            "sanitized_sha256": san_sha,
        })

    if canonical_db_dir.exists():
        for db_file in sorted(canonical_db_dir.rglob("*")):
            if db_file.is_file() and db_file.suffix.lower() in {".sql", ".pks", ".pkb"}:
                rel_path = db_file.relative_to(canonical_db_dir)
                dest_path = input_db_dir / rel_path
                orig_sha = get_file_sha256(db_file)
                san_sha = sanitize.sanitize_file(db_file, dest_path)
                manifest_files.append({
                    "original_path": f"database/{rel_path.as_posix()}",
                    "sanitized_path": f"benchmark/generated/input/database/{rel_path.as_posix()}",
                    "original_sha256": orig_sha,
                    "sanitized_sha256": san_sha,
                })

    # 3. Leakage Validation
    print("[3/8] Scanning sanitized inputs for answer-key leakage...")
    try:
        sanitize.verify_no_leakage(generated_dir / "input")
        print("      Leakage check passed: zero answer keys found in inputs.")
    except (RuntimeError, ValueError) as exc:
        print(f"ERROR: Leakage check failed: {exc}", file=sys.stderr)
        return 2

    # 4. Manifest Generation
    manifest = {
        "protocol_version": config["protocol_version"],
        "source_commit": source_commit,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "files": manifest_files,
    }
    manifest_path = generated_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[4/8] Manifest written: {manifest_path.name}")

    # 5. Observability Analysis
    obs_path = generated_dir / "observability.json"
    obs_summary = discover.write_observability(gt_path, canonical_xml_dir, obs_path, canonical_db_dir)
    print(f"[5/8] Observability analyzed: {obs_summary['fully_observable']} Fully, {obs_summary['partially_observable']} Partially, {obs_summary['not_observable']} Not Observable")

    if args.dry_run:
        print("\n=======================================================")
        print("DRY RUN COMPLETED SUCCESSFULLY.")
        print("Fixtures parsed, sanitized, checked for leaks, and manifest built.")
        print("=======================================================")
        return 0

    # 6. Execute Real FormsLang Engine
    print("[6/8] Executing FormsLang prediction engine on sanitized inputs...")
    raw_analysis_path = generated_dir / "raw-analysis.json"
    raw_analysis = predict.run_prediction(input_xml_dir, raw_analysis_path, input_db_dir if input_db_dir.exists() else None)
    print(f"      Raw analysis saved: {len(raw_analysis['blueprint']['findings'])} findings extracted.")

    # 7. Normalize Predictions
    print("[7/8] Normalizing engine findings to benchmark predictions format...")
    predictions_path = generated_dir / "predictions.json"
    predictions_payload = normalize.write_predictions(raw_analysis_path, predictions_path, source_commit, config["protocol_version"])
    print(f"      Predictions written: {len(predictions_payload['predictions'])} normalized predictions.")

    # 8. Offline Evaluation
    print("[8/8] Evaluating predictions against authoritative ground truth...")
    gt_payload = json.loads(gt_path.read_text(encoding="utf-8"))
    report = evaluate.evaluate_run(predictions_payload, obs_summary, gt_payload, gt_sha_before)
    report["baseline_name"] = args.baseline_name

    report_json_path = generated_dir / "benchmark-report.json"
    report_md_path = generated_dir / "benchmark-report.md"
    evaluate.write_reports(report, report_json_path, report_md_path)

    # Post-run SHA256 verification of Ground Truth
    gt_sha_after = get_file_sha256(gt_path)
    if gt_sha_after != gt_sha_before:
        print(f"CRITICAL ERROR: Ground truth modified during run! {gt_sha_before} != {gt_sha_after}", file=sys.stderr)
        return 3
    print("      Ground truth immutability verified (SHA256 unchanged).")

    # Baseline Freeze. Only ever on an explicit --freeze: a run that merely
    # checks a number must not be able to overwrite recorded history.
    if args.freeze:
        if not args.baseline_name:
            print(
                "ERROR: --freeze requires --baseline-name. Frozen baselines are "
                "immutable, so the new run needs a directory of its own.",
                file=sys.stderr,
            )
            return 4
        baseline_dir = BENCHMARK_DIR / "baselines" / args.baseline_name
        if baseline_dir.exists() and not args.force:
            print(
                f"ERROR: baseline '{args.baseline_name}' already exists at "
                f"{baseline_dir}. A frozen baseline is never edited, re-run or "
                f"overwritten -- not to correct a number, not to re-render a "
                f"report. Freeze the new engine under a new name, or pass "
                f"--force if you truly mean to destroy the recorded one.",
                file=sys.stderr,
            )
            return 4
        baseline_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(manifest_path, baseline_dir / "manifest.json")
        shutil.copy2(obs_path, baseline_dir / "observability.json")
        shutil.copy2(raw_analysis_path, baseline_dir / "raw-analysis.json")
        shutil.copy2(predictions_path, baseline_dir / "predictions.json")
        shutil.copy2(report_json_path, baseline_dir / "benchmark-report.json")
        shutil.copy2(report_md_path, baseline_dir / "benchmark-report.md")
        print(f"\nBaseline frozen into: {baseline_dir}")
    else:
        print(f"\nOutputs left in: {generated_dir} (no --freeze, nothing frozen)")

    # Terminal summary output
    cov = report["coverage"]
    clf = report["classification_metrics"]
    risk = report["risk_metrics"]
    safe = report["safety_metrics"]

    print("\n" + "=" * 64)
    print("       FORMSLANG MODERNIZATION BENCHMARK BASELINE REPORT")
    print("=" * 64)
    print("Benchmark Status               : BASELINE_COMPLETE")
    print(f"Source Commit                  : {source_commit}")
    print(f"Total Cases                    : {cov['total_cases']}")
    print(f"  - Fully Observable           : {cov['fully_observable']}")
    print(f"  - Partially Observable       : {cov['partially_observable']}")
    print(f"  - Not Observable             : {cov['not_observable']}")
    print("-" * 64)
    print(f"Exact Accuracy (Observable)    : {clf['observable_exact_accuracy'] * 100:.1f}% ({clf['observable_exact_matches']}/{clf['observable_denominator']})")
    print(f"Exact Accuracy (Fully Obs)     : {clf['fully_observable_accuracy'] * 100:.1f}% ({clf['fully_observable_matches']}/{clf['fully_observable_denominator']})")
    print(f"Macro F1                       : {clf['macro_f1']:.4f}")
    print(f"Risk Accuracy                  : {risk['exact_accuracy'] * 100:.1f}%")
    print("-" * 64)
    print(f"Manual Review Recall           : {safe['manual_review_recall'] * 100:.1f}% ({safe['manual_review_recalled']}/{safe['manual_review_total']})")
    print(f"False Automation Rate          : {safe['false_automation_rate'] * 100:.1f}% ({safe['false_automation_count']}/{safe['manual_review_total']})")
    print(f"Critical Safety Misses         : {safe['critical_safety_misses_count']}")
    print("=" * 64)
    print(f"JSON Report : {report_json_path}")
    print(f"MD Report   : {report_md_path}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
