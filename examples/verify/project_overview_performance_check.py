"""Measure Phase C read projections on deterministic, public-safe synthetic data."""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import subprocess
import sys
import time
import tracemalloc
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from formslang.project_projection import (
    ProjectionCache,
    inventory_page,
    overview,
    prepare_projection,
    projection_key,
)


def build_fixture(*, forms=500, findings=5_000):
    """Return a deterministic assessment-shaped read fixture without customer data."""
    project_id = "c" * 32
    analysis_revision = "a" * 64
    source_revision = "b" * 64
    descriptor = {
        "id": project_id, "name": "Synthetic 500 Form Estate",
        "description": "Public-safe Phase C read-scale fixture", "client_label": "",
        "target_platform": "Oracle APEX", "target_version": "26.1",
        "target_representation": "APEXlang",
    }
    entities = [
        {
            "id": f"form:{index:04d}", "type": "FORM", "name": f"FORM_{index:04d}",
            "module": f"forms/form_{index:04d}.xml", "attributes": {}, "evidence": [],
            "review_state": "PENDING",
        }
        for index in range(forms)
    ]
    entities.extend([
        {"id": "package_spec:shared", "type": "PACKAGE_SPEC", "name": "SHARED_API",
         "module": "database/shared_api.pks", "attributes": {}, "evidence": [],
         "review_state": "PENDING"},
        {"id": "package_body:shared", "type": "PACKAGE_BODY", "name": "SHARED_API",
         "module": "database/shared_api.pkb", "attributes": {}, "evidence": [],
         "review_state": "PENDING"},
        {"id": "table:work", "type": "TABLE", "name": "WORK_ITEMS",
         "module": "database/schema.sql", "attributes": {"columns": [{"name": "ID"}]},
         "evidence": [], "review_state": "PENDING"},
    ])
    risks = ("CRITICAL", "HIGH", "MEDIUM", "LOW", None)
    recommendations = (
        "PRESERVE", "CONVERT", "REFACTOR", "MOVE_TO_PLSQL_API",
        "REPLACE_WITH_APEX_NATIVE", "MANUAL_REVIEW", "DROP", "FUTURE_VALUE",
    )
    interventions = ("AUTO", "ASSISTED", "MANUAL", "FUTURE_VALUE")
    finding_rows, edges = [], []
    for index in range(findings):
        entity_id = f"trigger:{index:05d}"
        risk = risks[index % len(risks)]
        attributes = {"risk": {"level": risk, "basis": "Synthetic evidence"}} if risk else {}
        entities.append({
            "id": entity_id, "type": "TRIGGER", "name": f"TRIGGER_{index:05d}",
            "module": f"forms/form_{index % forms:04d}.xml", "attributes": attributes,
            "evidence": [], "review_state": "PENDING",
        })
        finding_rows.append({
            "id": f"finding:{index:05d}", "entity": entity_id,
            "recommendation": recommendations[index % len(recommendations)],
            "execution_verdict": interventions[index % len(interventions)],
            "reason": f"Synthetic modernization evidence {index:05d}.",
            "classification": ["BUSINESS_RULE"] if index % 3 == 0 else [],
            "review_state": "PENDING", "dependencies": [], "evidence": [],
            "unresolved_questions": [],
        })
        edges.append({
            "id": f"edge:{index:05d}", "source": entity_id,
            "target": "package_spec:shared" if index % 2 else "table:work",
            "type": "CALLS" if index % 2 else "READS", "evidence": [],
        })
    manifest = [
        {"source_id": f"source:{index:04d}", "root_id": "forms",
         "relative_path": f"form_{index:04d}.xml", "representation": "xml",
         "selected": True, "status": "available"}
        for index in range(forms)
    ]
    assessment = {
        "schema_version": "project-assessment/1", "project_id": project_id,
        "source_revision": source_revision, "analysis_revision": analysis_revision,
        "review_revision": 0, "analyzed_at": "2026-09-20T12:00:00Z",
        "status": "Current", "completion_state": "COMPLETE",
        "target": {"platform": "Oracle APEX", "version": "26.1",
                   "representation": "APEXlang"},
        "source_manifest": manifest,
        "inventory": {
            "candidates": forms + 3,
            "forms": {"discovered": forms, "parseable": forms, "analyzed": forms,
                      "fmb_without_xml": 0},
            "database": {"packages": 1, "package_specs": 1, "package_bodies": 1,
                         "tables": 1, "views": 0, "analyzed": 3},
            "warnings": 0,
        },
        "diagnostics": [], "engine_identity": {"blueprint": "blueprint/1"},
        "blueprint": {"entities": entities, "edges": edges, "findings": finding_rows,
                      "failures": [], "evidence": []},
    }
    freshness = {"status": "CURRENT", "reasons": [],
                 "analysis_revision": analysis_revision}
    return descriptor, assessment, freshness


def _measure(operation, iterations):
    values = []
    for _ in range(iterations):
        started = time.perf_counter()
        operation()
        values.append((time.perf_counter() - started) * 1000)
    return {"iterations": iterations, "median_ms": round(statistics.median(values), 3),
            "maximum_ms": round(max(values), 3)}


def run_measurements(directory: Path, *, iterations=5):
    descriptor, assessment, freshness = build_fixture()
    persisted = directory / "synthetic-assessment.json"
    persisted.write_text(json.dumps(assessment, separators=(",", ":")), encoding="utf-8")
    prepared = prepare_projection(descriptor, assessment, freshness, store_scope="scale-verifier")
    key = projection_key(descriptor, assessment, freshness, store_scope="scale-verifier")
    cache = ProjectionCache()
    cache.get_or_build(key, lambda: prepared)

    tracemalloc.start()
    cold = _measure(lambda: overview(prepare_projection(
        descriptor, assessment, freshness, store_scope="cold-scale",
    )), iterations)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    measurements = {
        "cold_overview": cold,
        "inventory_first_page": _measure(
            lambda: inventory_page(prepared, "forms", limit=50), iterations),
        "combined_filter": _measure(lambda: inventory_page(
            prepared, "findings", filters={"risk": "CRITICAL", "intervention": "MANUAL"},
            limit=50,
        ), iterations),
        "search": _measure(lambda: inventory_page(
            prepared, "findings", query="TRIGGER_04999", limit=50,
        ), iterations),
        "reopen_and_overview": _measure(lambda: overview(prepare_projection(
            descriptor, json.loads(persisted.read_text(encoding="utf-8")), freshness,
            store_scope="reopened-scale",
        )), iterations),
        "warm_cache_overview": _measure(lambda: overview(cache.get_or_build(
            key, lambda: prepared,
        )), iterations),
    }
    summary = overview(prepared)
    semantic_ok = (
        summary["inventory"]["forms_modules"] == 500
        and summary["inventory"]["modernization_findings"] == 5_000
        and summary["inventory"]["dependencies"] == 5_000
        and sum(summary["risk_distribution"].values()) == 5_000
    )
    return {
        "fixture": {"forms": 500, "findings": 5_000, "dependencies": 5_000},
        "platform": platform.platform(), "python": platform.python_version(),
        "commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO, text=True,
        ).strip(),
        "measurements": measurements, "python_tracemalloc_peak_bytes": peak,
        "semantic_reconciliation": semantic_ok,
        "persistence_strategy": "saved assessment JSON + bounded in-memory projections; no projection tables",
        "limitations": "Synthetic read-model scale only; not engine throughput, browser rendering, customer data, or an analyst-time claim.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--iterations", type=int, default=5)
    args = parser.parse_args()
    if not 1 <= args.iterations <= 50:
        parser.error("--iterations must be between 1 and 50")
    run = args.output.resolve() / ("run-" + uuid.uuid4().hex[:12])
    run.mkdir(parents=True)
    report = run_measurements(run, iterations=args.iterations)
    (run / "result.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Phase C projection evidence: {run}")
    print(json.dumps(report, indent=2))
    return 0 if report["semantic_reconciliation"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
