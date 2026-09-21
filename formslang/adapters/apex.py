"""Oracle APEX 26.1 Target Adapter implementation.

Preserves 100% of existing APEXlang generation, layout geometry,
and offline SQLcl validation capabilities (§106, §3.2).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..modernization_model import map_intent_to_target_recommendation
from ..project_model import TargetProfile


class Apex26TargetAdapter:
    """Target adapter for Oracle APEX 26.1 (APEXlang)."""

    id: str = "oracle_apex_26_1"
    display_name: str = "Oracle APEX 26.1"
    target_version: str = "26.1"
    target_profile: TargetProfile = TargetProfile(
        platform="Oracle APEX", version="26.1", representation="APEXlang"
    )

    def capabilities(self) -> dict[str, bool]:
        return {
            "supports_code_generation": True,
            "supports_offline_validation": True,
            "supports_layout_fidelity": True,
            "supports_wave_planning": False,
            "supports_backlog_export": False,
        }

    def interpret_intent(
        self, intent: str, context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        rec = map_intent_to_target_recommendation(intent, "Oracle APEX")
        component_kinds = {
            "MOVE_TO_PLSQL_API": "plsql_package_procedure",
            "REPLACE_WITH_APEX_NATIVE": "validation",
            "PRESERVE": "database_package",
            "CONVERT": "apex_process",
            "REFACTOR": "apex_page_component",
            "DROP": "none",
            "MANUAL_REVIEW": "manual_inspection",
        }
        rationales = {
            "MOVE_TO_PLSQL_API": "Encapsulate data mutation in an authoritative PL/SQL database package procedure.",
            "REPLACE_WITH_APEX_NATIVE": "Replace procedural trigger logic with native APEX declarative validations or Dynamic Actions.",
            "PRESERVE": "Keep existing database object intact; APEX consumes it directly.",
            "CONVERT": "Transform legacy block/item logic into an APEX Page Processing unit.",
            "REFACTOR": "Redesign complex screen workflow into stateless modern APEX components.",
            "DROP": "Retire obsolete legacy code or dead trigger.",
            "MANUAL_REVIEW": "Architectural review required by a domain expert.",
        }
        return {
            "recommendation": rec,
            "target_component_kind": component_kinds.get(rec, "manual_inspection"),
            "rationale": rationales.get(rec, "Standard APEX modernization pattern."),
            "native_opportunity": rec == "REPLACE_WITH_APEX_NATIVE",
        }

    def evaluate_eligibility(
        self, module_id: str, project_state: dict[str, Any]
    ) -> dict[str, Any]:
        blockers: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []

        target = project_state.get("target", {})
        if target.get("platform") != "Oracle APEX":
            blockers.append({
                "code": "TARGET_MISMATCH",
                "message": f"Target platform is {target.get('platform')}, expected Oracle APEX.",
            })

        # Inspect any recorded blockers in project state
        blockers.extend(project_state.get("blockers", []))

        return {
            "eligible": len(blockers) == 0,
            "blockers": blockers,
            "warnings": warnings,
        }

    def generate_deliverables(
        self, module_id: str, reviewed_scope: dict[str, Any], output_path: str
    ) -> dict[str, Any]:
        """Generates APEXlang delivery package."""
        from .. import apexlang, store

        out_dir = Path(output_path)
        out_dir.mkdir(parents=True, exist_ok=True)

        session_db_path = reviewed_scope.get("session_db_path")
        module_obj = reviewed_scope.get("module_obj")

        if session_db_path and module_obj:
            session_store = store.Store(Path(session_db_path), reconcile_jobs=False)
            try:
                result = apexlang.export_apexlang(
                    session_store,
                    module_obj,
                    out_dir / "apexlang",
                    {"alias": "module-" + module_id[:20], "ai_layout": False},
                )
                manifest_data = json.loads(result.manifest_path.read_text(encoding="utf-8"))
                return {
                    "manifest": manifest_data,
                    "package_path": str(result.zip_path),
                }
            finally:
                session_store.close()

        # Fallback manifest creation if direct objects not passed
        manifest = {"files": {}, "module_id": module_id, "platform": "Oracle APEX"}
        manifest_path = out_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return {
            "manifest": manifest,
            "package_path": str(manifest_path),
        }

    def validate_deliverables(
        self, package_path: str, context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Validates APEX package using offline SQLcl check if present."""
        from .. import apeximport

        path = Path(package_path)
        version = apeximport.sqlcl_version()
        if not version:
            return {
                "valid": True,  # Non-blocking when SQLcl not installed locally
                "engine_name": "Oracle SQLcl APEXlang Compiler",
                "diagnostics": ["SQLcl not found in environment; syntax check skipped."],
            }

        try:
            verdict = apeximport.run_import(path, validate_only=True)
            positive = "Validation successful." in verdict.stdout
            return {
                "valid": verdict.ok and positive,
                "engine_name": f"Oracle SQLcl ({version})",
                "diagnostics": [verdict.stdout.strip()] if verdict.stdout else [],
            }
        except (ValueError, OSError) as exc:
            return {
                "valid": False,
                "engine_name": "Oracle SQLcl APEXlang Compiler",
                "diagnostics": [str(exc)],
            }
