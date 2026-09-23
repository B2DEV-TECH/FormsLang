"""Experimental target adapter surface: complete profiles and fail-closed behavior.

The production APEX path is ProjectGenerationService + the existing exporter;
these adapters must never report success they did not earn.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from formslang.adapters.apex import Apex26TargetAdapter
from formslang.adapters.generic import GenericModernizationAdapter
from formslang.project_model import (
    GENERIC_TARGET,
    UNSELECTED_TARGET,
    ProjectError,
    TargetProfile,
)
from formslang.target_adapter import TargetAdapter, get_target_adapter, list_target_adapters


def test_builtin_adapters_follow_the_protocol():
    adapters = list_target_adapters()
    assert {a.id for a in adapters} == {"oracle_apex_26_1", "generic_modernize"}
    assert all(isinstance(a, TargetAdapter) for a in adapters)


@pytest.mark.parametrize("key", [TargetProfile(), "oracle_apex_26_1", "apex", "APEX"])
def test_apex_resolves_only_through_its_complete_profile(key):
    assert isinstance(get_target_adapter(key), Apex26TargetAdapter)


@pytest.mark.parametrize("key", [GENERIC_TARGET, "generic_modernize", "generic"])
def test_generic_resolves_only_through_its_complete_profile(key):
    assert isinstance(get_target_adapter(key), GenericModernizationAdapter)


@pytest.mark.parametrize("key", [
    TargetProfile("Oracle APEX", "99.9", "APEXlang"),
    TargetProfile("Oracle APEX", "26.1", "OtherFormat"),
    TargetProfile("Generic Modernization", "2.0", "Neutral Backlog"),
    TargetProfile("Java", "21", "Spring"),
    UNSELECTED_TARGET, "UNSELECTED", "Oracle APEX", "java", "",
])
def test_unknown_or_incomplete_profiles_fail_explicitly(key):
    with pytest.raises(ProjectError):
        get_target_adapter(key)


def test_apex_adapter_reports_missing_sqlcl_as_not_validated(tmp_path: Path):
    package = tmp_path / "application.apex.zip"
    package.write_bytes(b"PK")
    with patch("formslang.apeximport.sqlcl_version", return_value=""):
        result = Apex26TargetAdapter().validate_deliverables(str(package))
    assert result["valid"] is False and result["status"] == "NOT_VALIDATED" and result["available"] is False
    absent = Apex26TargetAdapter().validate_deliverables(str(tmp_path / "absent.zip"))
    assert absent["valid"] is False and absent["status"] == "NOT_VALIDATED"


def test_apex_adapter_never_publishes_a_manifest_as_an_application(tmp_path: Path):
    for scope in ({}, {"session_db_path": str(tmp_path / "s.db")}, {"module_obj": object()}):
        with pytest.raises(ProjectError):
            Apex26TargetAdapter().generate_deliverables("source:orders", scope, str(tmp_path / "out"))
    assert not (tmp_path / "out").exists()


def test_generic_adapter_requires_the_explicit_estate_scope_and_snapshot(tmp_path: Path):
    adapter = GenericModernizationAdapter()
    assert adapter.capabilities()["supports_code_generation"] is False
    with pytest.raises(ProjectError):
        adapter.generate_deliverables("source:orders", {}, str(tmp_path))
    with pytest.raises(ProjectError):
        adapter.generate_deliverables("all", {"assessment": {"blueprint": {}}}, str(tmp_path))
    with pytest.raises(ProjectError):
        adapter.interpret_intent("PRESERVE_EXISTING_OWNER")
    missing = adapter.validate_deliverables(str(tmp_path / "missing.zip"))
    assert missing["valid"] is False and missing["status"] == "NOT_VALIDATED"
