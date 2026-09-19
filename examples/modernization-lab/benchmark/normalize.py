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
        package: str | None = attrs.get("package") or None
        table: str | None = attrs.get("table") or None
        view: str | None = None

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
        elif etype in {"PACKAGE_SUBPROGRAM", "SUBPROGRAM_BODY"}:
            procedure = attrs.get("procedure") or (ename.split(".")[1] if "." in ename else ename)
            package = attrs.get("package") or (ename.split(".")[0] if "." in ename else None)
        elif etype == "PACKAGE_SPEC" or etype == "PACKAGE_BODY":
            package = ename
        elif etype == "CONSTANT_DECLARATION":
            package = attrs.get("package") or (ename.split(".")[0] if "." in ename else ename)
        elif etype == "TABLE":
            table = ename
        elif etype == "VIEW":
            view = ename

        recommendation = f.get("recommendation", "UNKNOWN")
        # Every decision the ground truth can express counts as a prediction.
        # MOVE_TO_PLSQL_API and REPLACE_WITH_APEX_NATIVE were missing here, so a
        # correct answer in either class was being filed as PARTIAL.
        if recommendation in {"PRESERVE", "CONVERT", "REFACTOR", "DROP",
                              "MOVE_TO_PLSQL_API", "REPLACE_WITH_APEX_NATIVE",
                              "MANUAL_REVIEW"}:
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
                "package": package,
                "table": table,
                "view": view,
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
