"""Tests for TargetAdapter protocol, registry, APEX adapter, and Generic Modernization adapter."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from formslang.adapters.apex import Apex26TargetAdapter
from formslang.adapters.generic import GenericModernizationAdapter
from formslang.project_intake import ProjectIntake
from formslang.project_model import ProjectError, TargetProfile
from formslang.project_service import ProjectService
from formslang.target_adapter import (
    TargetAdapter,
    get_target_adapter,
    list_target_adapters,
)


def test_target_adapter_protocol_compliance():
    apex = Apex26TargetAdapter()
    generic = GenericModernizationAdapter()

    assert isinstance(apex, TargetAdapter)
    assert isinstance(generic, TargetAdapter)

    assert apex.id == "oracle_apex_26_1"
    assert apex.display_name == "Oracle APEX 26.1"
    assert apex.target_profile.platform == "Oracle APEX"

    assert generic.id == "generic_modernize"
    assert generic.display_name == "Generic Modernization"
    assert generic.target_profile.platform == "Generic Modernization"


def test_target_adapter_registry_lookup():
    adapters = list_target_adapters()
    assert len(adapters) >= 2

    # By ID
    a1 = get_target_adapter("oracle_apex_26_1")
    assert isinstance(a1, Apex26TargetAdapter)
    a2 = get_target_adapter("generic_modernize")
    assert isinstance(a2, GenericModernizationAdapter)

    # By TargetProfile
    prof_apex = TargetProfile(platform="Oracle APEX", version="26.1")
    assert get_target_adapter(prof_apex).id == "oracle_apex_26_1"

    prof_generic = TargetProfile(platform="Generic Modernization", version="1.0")
    assert get_target_adapter(prof_generic).id == "generic_modernize"

    # By string alias
    assert get_target_adapter("APEX").id == "oracle_apex_26_1"
    assert get_target_adapter("Generic Modernization").id == "generic_modernize"

    # Unknown platform raises ProjectError
    with pytest.raises(ProjectError, match="No target adapter registered"):
        get_target_adapter(TargetProfile(platform="Unknown Target"))


def test_apex_adapter_capabilities_and_intent():
    apex = Apex26TargetAdapter()
    caps = apex.capabilities()
    assert caps["supports_code_generation"] is True
    assert caps["supports_offline_validation"] is True
    assert caps["supports_wave_planning"] is False
    assert caps["supports_backlog_export"] is False

    interpretation = apex.interpret_intent("CENTRALIZE_EXISTING_OWNER")
    assert interpretation["recommendation"] == "MOVE_TO_PLSQL_API"
    assert interpretation["target_component_kind"] == "plsql_package_procedure"
    assert interpretation["native_opportunity"] is False

    interpretation_native = apex.interpret_intent("REPLACE_MECHANICAL_BEHAVIOR")
    assert interpretation_native["recommendation"] == "REPLACE_WITH_APEX_NATIVE"
    assert interpretation_native["target_component_kind"] == "validation"
    assert interpretation_native["native_opportunity"] is True


def test_generic_adapter_capabilities_and_intent():
    generic = GenericModernizationAdapter()
    caps = generic.capabilities()
    assert caps["supports_code_generation"] is False
    assert caps["supports_offline_validation"] is True
    assert caps["supports_wave_planning"] is True
    assert caps["supports_backlog_export"] is True

    interpretation = generic.interpret_intent("CENTRALIZE_EXISTING_OWNER")
    assert interpretation["recommendation"] == "PRESERVE_EXISTING_SERVICE_BOUNDARY"
    assert interpretation["target_component_kind"] == "database_api_or_domain_service"
    assert interpretation["native_opportunity"] is False

    interpretation_extract = generic.interpret_intent("INTRODUCE_SERVICE_BOUNDARY")
    assert interpretation_extract["recommendation"] == "EXTRACT_TO_BACKEND_SERVICE"
    assert interpretation_extract["target_component_kind"] == "rest_service_or_backend_bean"


def test_generic_adapter_generate_and_validate(tmp_path: Path):
    generic = GenericModernizationAdapter()

    # Synthetic assessment scope
    assessment = {
        "project_id": "test-project",
        "analyzed_at": "2026-09-21T20:00:00Z",
        "blueprint": {
            "entities": [
                {"id": "f1", "name": "ORDERS", "type": "FORM"},
                {"id": "f2", "name": "CUSTOMERS", "type": "FORM"},
                {"id": "p1", "name": "ORDER_API", "type": "PACKAGE"},
                {"id": "t1", "name": "ORDERS_TAB", "type": "TABLE"},
            ],
            "findings": [
                {
                    "id": "find-1",
                    "form": "ORDERS",
                    "block": "ORDERS",
                    "recommendation": "MOVE_TO_PLSQL_API",
                    "severity": "HIGH",
                    "priority_score": 80.0,
                    "summary": "Direct DML on orders table",
                    "location": "ORDERS.POST-INSERT",
                },
                {
                    "id": "find-2",
                    "form": "CUSTOMERS",
                    "block": "CUST",
                    "recommendation": "REPLACE_WITH_APEX_NATIVE",
                    "severity": "LOW",
                    "priority_score": 10.0,
                    "summary": "Item validation",
                    "location": "CUST.WHEN-VALIDATE-ITEM",
                },
            ],
            "edges": [
                {"source": "ORDERS", "target": "ORDER_API", "type": "CALLS"},
            ],
        },
    }

    out_dir = tmp_path / "generic_output"
    result = generic.generate_deliverables(
        module_id="all",
        reviewed_scope={"assessment": assessment},
        output_path=str(out_dir),
    )

    manifest = result["manifest"]
    package_path = Path(result["package_path"])

    assert package_path.is_file()
    assert manifest["target_platform"] == "Generic Modernization"

    # Verify files inside output dir
    assert (out_dir / "modernization_backlog.json").is_file()
    assert (out_dir / "modernization_backlog.csv").is_file()
    assert (out_dir / "architectural_decisions.json").is_file()
    assert (out_dir / "architectural_decisions.md").is_file()
    assert (out_dir / "migration_waves.json").is_file()
    assert (out_dir / "migration_waves.md").is_file()
    assert (out_dir / "system_interface_catalog.json").is_file()

    # Inspect backlog JSON
    backlog = json.loads((out_dir / "modernization_backlog.json").read_text(encoding="utf-8"))
    assert len(backlog) == 2
    assert backlog[0]["intent"] == "CENTRALIZE_EXISTING_OWNER"
    assert backlog[0]["target_recommendation"] == "PRESERVE_EXISTING_SERVICE_BOUNDARY"

    # Inspect waves JSON
    waves = json.loads((out_dir / "migration_waves.json").read_text(encoding="utf-8"))
    assert "wave_1_foundations" in waves
    assert "wave_3_coupled" in waves
    # ORDERS has score 80 so it's in wave 3
    assert any(m["form"] == "ORDERS" for m in waves["wave_3_coupled"]["modules"])
    # CUSTOMERS has score 10 so it's in wave 1
    assert any(m["form"] == "CUSTOMERS" for m in waves["wave_1_foundations"]["modules"])

    # Verify package zip
    with zipfile.ZipFile(package_path, "r") as arc:
        names = arc.namelist()
        assert "modernization_backlog.json" in names
        assert "migration_waves.json" in names

    # Validation
    verdict = generic.validate_deliverables(str(package_path))
    assert verdict["valid"] is True
    assert len(verdict["diagnostics"]) == 0

    # Corrupt validation check
    corrupt_zip = tmp_path / "corrupt.zip"
    corrupt_zip.write_bytes(b"not a zip file")
    corrupt_verdict = generic.validate_deliverables(str(corrupt_zip))
    assert corrupt_verdict["valid"] is False


def test_project_service_generic_modernization_lifecycle(tmp_path: Path):
    """End-to-end integration of Generic Modernization target through ProjectService."""
    target_generic = TargetProfile(
        platform="Generic Modernization", version="1.0", representation="Neutral Backlog"
    )
    from formslang import rbac

    intake = ProjectIntake(tmp_path / "data", tmp_path / "config")
    created = intake.create_demo(
        destination=tmp_path / "demo_generic",
        target=target_generic,
    )
    pid = created["project"]["id"]
    access = intake.access(pid, rbac.RUN_CONVERSION)
    service = ProjectService(access, authorize=lambda: intake.access(pid, rbac.RUN_CONVERSION))
    try:
        desc = service.open()
        assert desc.target.platform == "Generic Modernization"

        # Check target_adapter() resolution
        adapter = service.target_adapter()
        assert isinstance(adapter, GenericModernizationAdapter)

        # Analyze project
        service.analyze(expected_revision=None, expected_configuration=0)
        assessment = service.assessment()
        request = {
            "project_id": assessment["project_id"],
            "analysis_revision": assessment["analysis_revision"],
            "source_revision": assessment["source_revision"],
            "review_revision": assessment["review_revision"],
        }

        # Generate deliverables via service
        gen_meta = service.generate(request)
        assert gen_meta["status"] == "Generated"
        assert gen_meta["mode"] == "generic-modernization-package"
        artifact_id = gen_meta["artifact_id"]

        # Download artifact
        data = service.generation_download(artifact_id)
        assert len(data) > 0
        assert gen_meta["sha256"]

        # Validate artifact offline
        val_result = service.generation_validate(artifact_id)
        assert val_result["status"] == "Validated"
        assert val_result["mode"] == "generic-deliverables-validation"
        assert "integrity verified" in val_result["message"]
    finally:
        service.close()


def test_project_service_unselected_target_fails_closed(tmp_path: Path):
    target_unselected = TargetProfile(
        platform="UNSELECTED", version="none", representation="none"
    )
    from formslang import rbac

    intake = ProjectIntake(tmp_path / "data2", tmp_path / "config2")
    created = intake.create_demo(
        destination=tmp_path / "demo_unselected",
        target=target_unselected,
    )
    pid = created["project"]["id"]
    access = intake.access(pid, rbac.RUN_CONVERSION)
    service = ProjectService(access, authorize=lambda: intake.access(pid, rbac.RUN_CONVERSION))
    try:
        with pytest.raises(ProjectError, match="Target strategy is unselected"):
            service.target_adapter()

        service.open()
        service.analyze(expected_revision=None, expected_configuration=0)

        with pytest.raises(ProjectError, match="Target strategy is unselected"):
            service.generate({})
    finally:
        service.close()
