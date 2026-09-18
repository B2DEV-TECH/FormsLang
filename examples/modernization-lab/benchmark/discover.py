"""Observability analysis for FormsLang modernization benchmark.

Evaluates evidence availability for all 41 ground-truth cases against the
current FormsLang ingestion engine without modifying or contaminating prediction.
"""

from __future__ import annotations

import json
from pathlib import Path

FULLY_OBSERVABLE = "FULLY_OBSERVABLE"
PARTIALLY_OBSERVABLE = "PARTIALLY_OBSERVABLE"
NOT_OBSERVABLE = "NOT_OBSERVABLE"

OBSERVABILITY_STATUSES = (FULLY_OBSERVABLE, PARTIALLY_OBSERVABLE, NOT_OBSERVABLE)


def analyze_observability(ground_truth_path: Path, xml_dir: Path) -> dict:
    """Analyze observability for all cases in ground truth."""
    data = json.loads(ground_truth_path.read_text(encoding="utf-8"))
    cases = data.get("cases", [])

    results = []
    available_files = {p.name for p in xml_dir.glob("*.xml")}

    for c in cases:
        cid = c["id"]
        source_desc = c.get("source", "")

        has_forms = "forms/xml/" in source_desc
        has_db = "database/" in source_desc
        has_lib = "forms/libraries/" in source_desc

        required_sources = []
        available_sources = []

        # Parse source references
        parts = [p.strip() for p in source_desc.split(";")]
        for p in parts:
            if "(" in p:
                src_path = p.split("(")[0].strip()
            else:
                src_path = p.strip()
            required_sources.append(src_path)

            for xml_file in available_files:
                if xml_file in p:
                    available_sources.append(f"forms/xml/{xml_file}")

        required_sources = sorted(set(required_sources))
        available_sources = sorted(set(available_sources))

        if not has_forms:
            status = NOT_OBSERVABLE
            if has_db:
                reason = (
                    "Case source resides exclusively in database packages/DDL/views. "
                    "Current FormsLang engine does not ingest standalone SQL/PLSQL."
                )
            elif has_lib:
                reason = (
                    "Case source resides in library documentation (OM_SHARED.md). "
                    "Current FormsLang engine does not ingest non-XML documentation."
                )
            else:
                reason = "Case source is not present in ingested Forms2XML files."
        elif has_db or has_lib:
            status = PARTIALLY_OBSERVABLE
            reason = (
                "Form trigger/item is visible in Forms2XML, but associated database packages, "
                "views, or library definitions cited by the case rationale are not ingested."
            )
        else:
            status = FULLY_OBSERVABLE
            reason = (
                "All source evidence referenced by the case is fully contained within the "
                "sanitized Forms2XML files parsed by FormsLang."
            )

        results.append({
            "case_id": cid,
            "title": c.get("title", ""),
            "classification": c.get("classification", ""),
            "risk": c.get("risk", ""),
            "observability": status,
            "required_sources": required_sources,
            "available_sources": available_sources,
            "reason": reason,
        })

    summary = {
        "total_cases": len(results),
        "fully_observable": sum(1 for r in results if r["observability"] == FULLY_OBSERVABLE),
        "partially_observable": sum(1 for r in results if r["observability"] == PARTIALLY_OBSERVABLE),
        "not_observable": sum(1 for r in results if r["observability"] == NOT_OBSERVABLE),
        "cases": results,
    }

    return summary


def write_observability(ground_truth_path: Path, xml_dir: Path, output_path: Path) -> dict:
    """Generate and write observability.json."""
    summary = analyze_observability(ground_truth_path, xml_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary
