"""Tests for Target-Neutral Architecture Policy Engine (Sections 21, 22, 71)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from formslang import rbac
from formslang.architecture_policy import (
    DIRECT_DML_MANUAL_REVIEW,
    DIRECT_DML_PREFER_EXISTING_OWNER,
    GLOBAL_STATE_BLOCK,
    GLOBAL_STATE_PRESERVE,
    GLOBAL_STATE_REDESIGN,
    ArchitecturePolicyError,
    ArchitecturePolicyEvaluator,
    default_architecture_policy,
    policy_from_dict,
    policy_to_dict,
    resolve_effective_policy,
)
from formslang.cli import main
from formslang.project_http import ProjectHTTP
from formslang.project_intake import ProjectIntake
from formslang.project_service import ProjectService


def test_default_architecture_policy():
    policy = default_architecture_policy()
    assert policy.policy_version == 1
    assert policy.direct_dml.when_existing_owner == DIRECT_DML_PREFER_EXISTING_OWNER
    assert policy.direct_dml.no_owner == DIRECT_DML_MANUAL_REVIEW
    assert policy.global_state.recommendation == GLOBAL_STATE_REDESIGN
    assert policy.global_state.execution == "assisted"
    assert policy.database_api.preserve_by_default is True


def test_policy_serialization_roundtrip():
    policy = default_architecture_policy()
    serialized = policy_to_dict(policy)
    deserialized = policy_from_dict(serialized)
    assert policy == deserialized


def test_invalid_policy_validation():
    with pytest.raises(ArchitecturePolicyError):
        policy_from_dict({"policy_version": 99})

    with pytest.raises(ArchitecturePolicyError):
        policy_from_dict({"direct_dml": {"when_existing_owner": "invalid_action"}})

    with pytest.raises(ArchitecturePolicyError):
        policy_from_dict({"global_state": {"recommendation": "invalid_rec"}})


def test_policy_hierarchy_resolution():
    base = default_architecture_policy()

    org_override = {
        "direct_dml": {
            "when_existing_owner": DIRECT_DML_MANUAL_REVIEW,
        }
    }

    project_override = {
        "global_state": {
            "recommendation": GLOBAL_STATE_PRESERVE,
            "execution": "manual",
        }
    }

    effective, provenance = resolve_effective_policy(
        base,
        organization_policy=org_override,
        project_policy=project_override,
    )

    assert effective.direct_dml.when_existing_owner == DIRECT_DML_MANUAL_REVIEW
    assert provenance["direct_dml.when_existing_owner"] == "ORGANIZATION"

    assert effective.direct_dml.no_owner == DIRECT_DML_MANUAL_REVIEW
    assert provenance["direct_dml.no_owner"] == "DEFAULT"

    assert effective.global_state.recommendation == GLOBAL_STATE_PRESERVE
    assert provenance["global_state.recommendation"] == "PROJECT"

    assert effective.database_api.preserve_by_default is True
    assert provenance["database_api.preserve_by_default"] == "DEFAULT"


def test_policy_evaluator_direct_dml():
    policy = default_architecture_policy()
    _, provenance = resolve_effective_policy(policy)
    evaluator = ArchitecturePolicyEvaluator(policy, provenance)

    # Table with known package owner
    res_owned = evaluator.evaluate_direct_dml("ORDERS", has_known_owner=True, owner_name="PKG_ORDERS")
    assert res_owned["intent"] == "REROUTE_TO_OWNING_API"
    assert "PKG_ORDERS" in res_owned["recommendation"]
    assert "DEFAULT policy (prefer_existing_owner)" in res_owned["provenance"]

    # Table without owner
    res_unowned = evaluator.evaluate_direct_dml("AUDIT_LOG", has_known_owner=False)
    assert res_unowned["intent"] == "INSPECT_TABLE_TRIGGERS"
    assert "AUDIT_LOG" in res_unowned["recommendation"]


def test_policy_evaluator_global_state_and_database_api():
    # Global state with block_generation execution
    blocked_policy = policy_from_dict({
        "global_state": {
            "recommendation": GLOBAL_STATE_REDESIGN,
            "execution": GLOBAL_STATE_BLOCK,
        }
    })
    evaluator = ArchitecturePolicyEvaluator(blocked_policy)
    res_state = evaluator.evaluate_global_state("PKG_SESSION")
    assert res_state["intent"] == "REDESIGN_STATE_MANAGEMENT"
    assert res_state["block_generation"] is True

    # Database API
    res_api = evaluator.evaluate_database_api("PKG_CUSTOMERS")
    assert res_api["intent"] == "PRESERVE_DATABASE_API"
    assert "PKG_CUSTOMERS" in res_api["recommendation"]


def test_policy_is_not_a_2_1_product_surface(tmp_path: Path, capsys):
    """Policy is an experimental library: configuring it must not look enforceable."""
    intake = ProjectIntake(tmp_path / "data", tmp_path / "config")
    created = intake.create_demo(destination=tmp_path / "demo_proj")
    pid = created["project"]["id"]
    service = ProjectService(intake.access(pid, rbac.RUN_CONVERSION))
    try:
        assert not hasattr(service, "architecture_policy")
        assert not hasattr(service, "update_architecture_policy")
    finally:
        service.close()
    handler = ProjectHTTP(workbench=None)
    for method, body in (("GET", {}), ("PUT", {"direct_dml": {"when_existing_owner": "allow_direct"}})):
        status, _ = handler._dispatch(method, f"/api/v2/projects/{pid}/policy", {}, body, intake)
        assert status == 404
    with pytest.raises(SystemExit):
        main(["project", "policy", str(tmp_path / "demo_proj"), "--json"])
    capsys.readouterr()


def test_cli_search_is_bounded(tmp_path: Path, capsys):
    proj_dir = str(tmp_path / "cli_proj")
    assert main(["project", "demo", proj_dir, "--json"]) == 0
    capsys.readouterr()
    assert main(["project", "analyze", proj_dir]) in (0, 1)
    capsys.readouterr()
    assert main(["project", "search", proj_dir, "--query", "CUSTOMERS", "--limit", "5", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert "results" in data and len(data["results"]) <= 5
    with pytest.raises(SystemExit):
        main(["project", "search", proj_dir, "--query", "CUSTOMERS", "--limit", "1000"])
    capsys.readouterr()
