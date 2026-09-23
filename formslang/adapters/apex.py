"""Oracle APEX 26.1 target adapter -- EXPERIMENTAL, not the production path.

FormsLang 2.1 generates APEXlang only through ``ProjectGenerationService``,
which applies the review, code-approval, target-plan, source and size gates
and calls the existing exporter directly. This adapter is not wired into that
path. Its public methods fail closed: missing inputs raise, and an unavailable
validator is reported as NOT_VALIDATED, never as success.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..modernization_model import map_intent_to_target_recommendation
from ..project_model import ProjectError, TargetProfile


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

        session_db_path = reviewed_scope.get("session_db_path")
        module_obj = reviewed_scope.get("module_obj")
        if not session_db_path or module_obj is None:
            raise ProjectError("APEX generation requires a prepared, reviewed module session; nothing was generated.")
        out_dir = Path(output_path)
        out_dir.mkdir(parents=True, exist_ok=True)
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

    def validate_deliverables(
        self, package_path: str, context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Validates APEX package using offline SQLcl check if present."""
        from .. import apeximport

        path = Path(package_path)
        if not path.is_file():
            return {"valid": False, "status": "NOT_VALIDATED", "available": None,
                    "engine_name": "Oracle SQLcl APEXlang Compiler",
                    "diagnostics": ["Package not found; nothing was validated."]}
        version = apeximport.sqlcl_version()
        if not version:
            # Validator unavailable is not validation success.
            return {"valid": False, "status": "NOT_VALIDATED", "available": False,
                    "engine_name": "Oracle SQLcl APEXlang Compiler",
                    "diagnostics": ["SQLcl is not available; the package was not validated."]}

        try:
            verdict = apeximport.run_import(path, validate_only=True)
            positive = "Validation successful." in verdict.stdout
            return {
                "valid": verdict.ok and positive,
                "status": "VALIDATED" if verdict.ok and positive else "VALIDATION_FAILED",
                "available": True,
                "engine_name": f"Oracle SQLcl ({version})",
                "diagnostics": [verdict.stdout.strip()] if verdict.stdout else [],
            }
        except (ValueError, OSError) as exc:
            return {
                "valid": False,
                "status": "NOT_VALIDATED",
                "available": True,
                "engine_name": "Oracle SQLcl APEXlang Compiler",
                "diagnostics": [str(exc)],
            }
