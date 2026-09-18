"""Normalizer converting raw FormsLang engine output into structured benchmark predictions."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def normalize_findings(
    raw_analysis: dict[str, Any],
    source_commit: str | None,
    protocol_version: str = "1.0",
) -> dict[str, Any]:
    """Normalize raw analysis findings into benchmark prediction format."""
    bp = raw_analysis.get("blueprint", {})
    entities_map = {e["id"]: e for e in bp.get("entities", [])}
    findings = bp.get("findings", [])
    fl_version = raw_analysis.get("forms_lang_version", "unknown")

    predictions = []

    for f in findings:
        fid = f.get("id", "")
        eid = f.get("entity", fid)
        entity = entities_map.get(eid, {})
        etype = entity.get("type", "")
        ename = entity.get("name", "")
        attrs = entity.get("attributes", {})
        module_file = entity.get("module", "")
        module_name = Path(module_file).stem if module_file else ""

        block: str | None = None
        item: str | None = None
        trigger: str | None = None
        procedure: str | None = None

        if etype == "TRIGGER":
            trigger = ename
            owner = attrs.get("owner", "")
            if "." in owner:
                parts = owner.split(".", 1)
                block = parts[0]
                item = parts[1]
            elif owner:
                block = owner
        elif etype == "ITEM":
            item = ename
            block = attrs.get("owner") or None
        elif etype == "BLOCK":
            block = ename
        elif etype == "PROGRAM_UNIT":
            procedure = ename

        recommendation = f.get("recommendation", "UNKNOWN")
        if recommendation in {"PRESERVE", "CONVERT", "REFACTOR", "DROP", "MANUAL_REVIEW"}:
            status = "PREDICTED"
        elif recommendation == "UNKNOWN":
            status = "UNSUPPORTED"
        else:
            status = "PARTIAL"

        risk_level = attrs.get("risk", {}).get("level", "UNKNOWN")
        verdict = f.get("execution_verdict") or attrs.get("migration_verdict", "UNKNOWN")

        predictions.append({
            "finding_id": fid,
            "status": status,
            "source": {
                "file": module_file,
                "module": module_name,
                "block": block,
                "item": item,
                "trigger": trigger,
                "procedure": procedure,
            },
            "classification": recommendation,
            "risk": risk_level,
            "verdict": verdict,
            "evidence": f.get("evidence", []),
            "raw_output_ref": fid,
            "notes": f.get("reason", ""),
        })

    return {
        "protocol_version": protocol_version,
        "forms_lang_version": fl_version,
        "source_commit": source_commit,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "engine_path": "formslang.parser.parse_xml -> formslang.blueprint.build",
        "predictions": predictions,
    }


def write_predictions(
    raw_analysis_path: Path,
    predictions_path: Path,
    source_commit: str | None,
    protocol_version: str = "1.0",
) -> dict[str, Any]:
    """Load raw analysis, normalize, and write predictions.json."""
    raw = json.loads(raw_analysis_path.read_text(encoding="utf-8"))
    normalized = normalize_findings(raw, source_commit, protocol_version)
    predictions_path.parent.mkdir(parents=True, exist_ok=True)
    predictions_path.write_text(
        json.dumps(normalized, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return normalized
