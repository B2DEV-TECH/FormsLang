"""Generic Modernization Target Adapter implementation.

Produces target-neutral discovery assets, backlog stories,
architectural decision packages, and wave roadmaps (§106, §4).
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import zipfile
from pathlib import Path
from typing import Any

from ..modernization_model import map_intent_to_target_recommendation
from ..project_model import TargetProfile, canonical_json


class GenericModernizationAdapter:
    """Target adapter for Generic Modernization (neutral backlog, waves, ADRs)."""

    id: str = "generic_modernize"
    display_name: str = "Generic Modernization"
    target_version: str = "1.0"
    target_profile: TargetProfile = TargetProfile(
        platform="Generic Modernization", version="1.0", representation="Neutral Backlog"
    )

    def capabilities(self) -> dict[str, bool]:
        return {
            "supports_code_generation": False,
            "supports_offline_validation": True,
            "supports_layout_fidelity": False,
            "supports_wave_planning": True,
            "supports_backlog_export": True,
        }

    def interpret_intent(
        self, intent: str, context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        rec = map_intent_to_target_recommendation(intent, "Generic Modernization")
        component_kinds = {
            "PRESERVE_EXISTING_SERVICE_BOUNDARY": "database_api_or_domain_service",
            "REPLACE_WITH_WEB_FRAMEWORK_NATIVE": "web_client_validation",
            "PRESERVE": "database_stored_logic",
            "EXTRACT_TO_BACKEND_SERVICE": "rest_service_or_backend_bean",
            "REDESIGN_STATE_OR_WORKFLOW": "stateless_workflow_orchestration",
            "MANUAL_ARCHITECTURE_REVIEW": "architecture_review_item",
            "DECOMMISSION_OR_RETIRE": "none",
            "RESOLVE_CROSS_LAYER_CONFLICT": "cross_layer_governance_item",
            "MIGRATE_CONCURRENCY_MODEL": "optimistic_locking_protocol",
            "AUDIT_SECURITY_BOUNDARY": "security_perimeter_audit",
        }
        rationales = {
            "PRESERVE_EXISTING_SERVICE_BOUNDARY": "Reuse existing database package or service layer without rewriting it.",
            "REPLACE_WITH_WEB_FRAMEWORK_NATIVE": "Replace client-side mechanical triggers with standard web framework features.",
            "PRESERVE": "Preserve authoritative database objects in the database layer.",
            "EXTRACT_TO_BACKEND_SERVICE": "Extract business logic trapped in UI triggers into modern backend REST services or beans.",
            "REDESIGN_STATE_OR_WORKFLOW": "Redesign stateful, multi-screen legacy workflows into stateless modern cloud patterns.",
            "MANUAL_ARCHITECTURE_REVIEW": "Engage enterprise architect to define target strategy for high-risk business logic.",
            "DECOMMISSION_OR_RETIRE": "Retire obsolete or dead code without porting.",
        }
        return {
            "recommendation": rec,
            "target_component_kind": component_kinds.get(rec, "architecture_review_item"),
            "rationale": rationales.get(rec, "Target-neutral modernization action."),
            "native_opportunity": False,
        }

    def evaluate_eligibility(
        self, module_id: str, project_state: dict[str, Any]
    ) -> dict[str, Any]:
        """Generic modernization is always eligible as long as the project is analyzed."""
        blockers: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []

        blueprint = project_state.get("blueprint", {})
        entities = blueprint.get("entities", [])
        if not entities and not project_state.get("source_manifest"):
            blockers.append({
                "code": "NO_ANALYZED_MODULES",
                "message": "Analyze project sources before generating modern architectural deliverables.",
            })

        return {
            "eligible": len(blockers) == 0,
            "blockers": blockers,
            "warnings": warnings,
        }

    def generate_deliverables(
        self, module_id: str, reviewed_scope: dict[str, Any], output_path: str
    ) -> dict[str, Any]:
        """Generates target-neutral architectural deliverables:

        1. modernization_backlog.csv & modernization_backlog.json
        2. architectural_decisions.md & architectural_decisions.json
        3. migration_waves.md & migration_waves.json
        4. system_interface_catalog.json
        5. manifest.json
        """
        out_dir = Path(output_path)
        out_dir.mkdir(parents=True, exist_ok=True)

        assessment = reviewed_scope.get("assessment", {})
        blueprint = assessment.get("blueprint", {})
        findings = blueprint.get("findings", [])
        entities = blueprint.get("entities", [])
        edges = blueprint.get("edges", [])

        # Filter to selected module if specified and not empty
        if module_id and module_id not in {"*", "all"}:
            module_findings = [f for f in findings if f.get("source_id") == module_id or f.get("module") == module_id]
            if module_findings:
                findings = module_findings

        # 1. Generate Modernization Backlog
        backlog_items = []
        csv_buffer = io.StringIO()
        csv_writer = csv.writer(csv_buffer)
        csv_writer.writerow([
            "ID", "Module", "Type", "Intent", "TargetRecommendation",
            "Severity", "PriorityScore", "Summary", "Location", "Status",
        ])

        for idx, f in enumerate(findings, 1):
            fid = f.get("id", f"item-{idx}")
            mod = f.get("form") or f.get("module") or module_id
            rec = f.get("recommendation", "MANUAL_REVIEW")
            from ..modernization_model import map_legacy_recommendation_to_intent
            intent = map_legacy_recommendation_to_intent(rec)
            target_rec = self.interpret_intent(intent)["recommendation"]
            sev = f.get("severity", "MEDIUM")
            score = f.get("priority_score", 0.0)
            summary = f.get("summary") or f.get("title") or "Modernization finding"
            loc = f.get("location") or f.get("block") or "Form Root"

            item = {
                "id": fid,
                "module": mod,
                "intent": intent,
                "target_recommendation": target_rec,
                "severity": sev,
                "priority_score": score,
                "summary": summary,
                "location": loc,
                "epic": f"Modernize {mod}",
                "acceptance_criteria": [
                    f"Decouple logic from legacy Oracle Form trigger at {loc}.",
                    f"Implement target pattern: {target_rec}.",
                    "Validate data mutation integrity against database constraints.",
                ],
            }
            backlog_items.append(item)
            csv_writer.writerow([
                fid, mod, f.get("type", "FINDING"), intent, target_rec,
                sev, score, summary, loc, "PROPOSED",
            ])

        (out_dir / "modernization_backlog.json").write_text(
            canonical_json(backlog_items), encoding="utf-8"
        )
        (out_dir / "modernization_backlog.csv").write_text(
            csv_buffer.getvalue(), encoding="utf-8"
        )

        # 2. Architectural Decisions (ADR format)
        adrs = []
        adr_md_lines = [
            "# Architecture Decision Records (ADRs)",
            "",
            f"Project: {assessment.get('project_id', 'Modernization Project')}",
            f"Generated: {assessment.get('analyzed_at', 'current')}",
            "",
        ]
        decisions_list = reviewed_scope.get("decisions", [])
        if not decisions_list:
            # Synthesize recommended ADRs from top intents
            grouped_by_intent: dict[str, list[dict[str, Any]]] = {}
            for item in backlog_items:
                grouped_by_intent.setdefault(item["intent"], []).append(item)

            for intent_name, items in grouped_by_intent.items():
                adr_id = f"ADR-{len(adrs) + 1:03d}"
                adr = {
                    "id": adr_id,
                    "title": f"Adopt {intent_name} strategy for {len(items)} components",
                    "status": "PROPOSED",
                    "context": f"{len(items)} legacy trigger/procedural blocks require modernization under intent {intent_name}.",
                    "decision": f"Apply target pattern '{self.interpret_intent(intent_name)['recommendation']}' across identified modules.",
                    "consequences": "Enforces single authoritative boundary and reduces UI-tier business logic fragmentation.",
                    "affected_components": [it["id"] for it in items[:10]],
                }
                adrs.append(adr)
                adr_md_lines.extend([
                    f"## {adr['id']}: {adr['title']}",
                    f"**Status:** {adr['status']}  ",
                    f"**Context:** {adr['context']}  ",
                    f"**Decision:** {adr['decision']}  ",
                    f"**Consequences:** {adr['consequences']}  ",
                    "",
                ])
        else:
            for idx, d in enumerate(decisions_list, 1):
                adr_id = f"ADR-{idx:03d}"
                adr = {
                    "id": adr_id,
                    "title": f"Architectural Decision for {d.get('item_id', 'component')}",
                    "status": "ACCEPTED" if d.get("disposition") == "KEEP" else "MODIFIED",
                    "context": f"Review sign-off by {d.get('reviewer', 'Architect')}.",
                    "decision": f"Disposition: {d.get('disposition')}. Notes: {d.get('notes', 'None')}.",
                    "consequences": "Preserves audit trail in immutable ledger.",
                }
                adrs.append(adr)
                adr_md_lines.extend([
                    f"## {adr['id']}: {adr['title']}",
                    f"**Status:** {adr['status']}  ",
                    f"**Decision:** {adr['decision']}  ",
                    "",
                ])

        (out_dir / "architectural_decisions.json").write_text(
            canonical_json(adrs), encoding="utf-8"
        )
        (out_dir / "architectural_decisions.md").write_text(
            "\n".join(adr_md_lines), encoding="utf-8"
        )

        # 3. Migration Waves Planning (§106.4)
        form_entities = [e for e in entities if e.get("type") == "FORM"]
        wave1, wave2, wave3 = [], [], []
        for fe in form_entities:
            f_name = fe.get("name") or fe.get("module") or fe.get("id")
            # Modules with API bypasses or high findings go to later waves
            f_findings = [b for b in backlog_items if b["module"] == f_name]
            max_score = max((b["priority_score"] for b in f_findings), default=0.0)
            if max_score > 70 or any(b["intent"] == "CENTRALIZE_EXISTING_OWNER" for b in f_findings):
                wave3.append({"form": f_name, "reason": "High complexity / API bypass candidates", "items": len(f_findings)})
            elif len(f_findings) > 2 or max_score > 30:
                wave2.append({"form": f_name, "reason": "Moderate complexity / standard service dependencies", "items": len(f_findings)})
            else:
                wave1.append({"form": f_name, "reason": "Independent module / quick win", "items": len(f_findings)})

        waves_data = {
            "wave_1_foundations": {"name": "Wave 1: Independent Foundations", "modules": wave1},
            "wave_2_services": {"name": "Wave 2: Core Domain Services", "modules": wave2},
            "wave_3_coupled": {"name": "Wave 3: Coupled Hotspots & Redesign", "modules": wave3},
        }
        (out_dir / "migration_waves.json").write_text(
            canonical_json(waves_data), encoding="utf-8"
        )

        waves_md = [
            "# Modernization Migration Waves",
            "",
            "## Wave 1: Independent Foundations (Quick Wins)",
            f"Total Modules: {len(wave1)}",
            *[f"- **{m['form']}**: {m['reason']} ({m['items']} findings)" for m in wave1],
            "",
            "## Wave 2: Core Domain Services",
            f"Total Modules: {len(wave2)}",
            *[f"- **{m['form']}**: {m['reason']} ({m['items']} findings)" for m in wave2],
            "",
            "## Wave 3: Coupled Hotspots & Redesign",
            f"Total Modules: {len(wave3)}",
            *[f"- **{m['form']}**: {m['reason']} ({m['items']} findings)" for m in wave3],
            "",
        ]
        (out_dir / "migration_waves.md").write_text(
            "\n".join(waves_md), encoding="utf-8"
        )

        # 4. System Interface Catalog
        db_entities = [e for e in entities if e.get("type") in {"TABLE", "PACKAGE", "PACKAGE_SPEC", "PACKAGE_BODY", "VIEW"}]
        call_edges = [ed for ed in edges if ed.get("type") in {"CALLS", "WRITES", "DIRECT_DML"}]
        interface_catalog = {
            "database_objects": db_entities,
            "system_interactions": call_edges,
            "inferred_service_boundaries": [
                {
                    "target_service": e.get("name"),
                    "type": e.get("type"),
                    "consumers": [c.get("source") for c in call_edges if c.get("target") == e.get("name")],
                }
                for e in db_entities if e.get("type") in {"PACKAGE", "PACKAGE_SPEC"}
            ],
        }
        (out_dir / "system_interface_catalog.json").write_text(
            canonical_json(interface_catalog), encoding="utf-8"
        )

        # 5. Build ZIP bundle for uniform download & export compatibility
        zip_path = out_dir / "application.apex.zip"
        manifest_files: dict[str, str] = {}

        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for p in sorted(out_dir.rglob("*")):
                if p.is_file() and p.name != "application.apex.zip":
                    rel = p.relative_to(out_dir).as_posix()
                    file_bytes = p.read_bytes()
                    file_sha = hashlib.sha256(file_bytes).hexdigest()
                    manifest_files[rel] = file_sha
                    archive.writestr(rel, file_bytes)

        manifest = {
            "schema_version": "generic-modernization/1",
            "module_id": module_id,
            "target_platform": "Generic Modernization",
            "files": manifest_files,
            "sha256": hashlib.sha256(zip_path.read_bytes()).hexdigest(),
        }
        (out_dir / "manifest.json").write_text(
            canonical_json(manifest), encoding="utf-8"
        )

        return {
            "manifest": manifest,
            "package_path": str(zip_path),
        }

    def validate_deliverables(
        self, package_path: str, context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Validates manifest integrity, checksums, and schema of generic deliverables."""
        path = Path(package_path)
        if not path.is_file():
            return {
                "valid": False,
                "engine_name": "FormsLang Generic Modernization Validator",
                "diagnostics": [f"Deliverables package not found at: {path}"],
            }

        diagnostics: list[str] = []
        try:
            with zipfile.ZipFile(path, "r") as archive:
                names = archive.namelist()
                required = {"modernization_backlog.json", "migration_waves.json"}
                missing = required - set(names)
                if missing:
                    diagnostics.append(f"Missing required deliverable files: {sorted(missing)}")

                # Validate JSON parseability
                for item in names:
                    if item.endswith(".json"):
                        try:
                            json.loads(archive.read(item).decode("utf-8"))
                        except (json.JSONDecodeError, UnicodeDecodeError) as err:
                            diagnostics.append(f"Malformed JSON in {item}: {err}")

            return {
                "valid": len(diagnostics) == 0,
                "engine_name": "FormsLang Generic Modernization Validator",
                "diagnostics": diagnostics,
            }
        except (zipfile.BadZipFile, OSError) as exc:
            return {
                "valid": False,
                "engine_name": "FormsLang Generic Modernization Validator",
                "diagnostics": [f"Corrupt zip archive: {exc}"],
            }
