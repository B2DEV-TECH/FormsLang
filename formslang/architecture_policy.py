"""Target-neutral Architecture Policy Engine.

Implements Sections 21, 22, and 71 of the FormsLang 2.1-3.0 Specification:
- Separation of Observed Facts, Default Policy, Organization Policy, Project Overrides, and Human Decision.
- Hierarchical resolution: Default -> Organization -> Project.
- Explicit policy provenance on architectural recommendations (Fact + Policy = Intent/Recommendation).
- Multi-revision invalidation support: Policy updates invalidate target interpretations without mutating observed facts.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

POLICY_VERSION = 1

# Policy provenance source levels
PROVENANCE_DEFAULT = "DEFAULT"
PROVENANCE_ORGANIZATION = "ORGANIZATION"
PROVENANCE_PROJECT = "PROJECT"

# Direct DML Actions
DIRECT_DML_PREFER_EXISTING_OWNER = "prefer_existing_owner"
DIRECT_DML_MANUAL_REVIEW = "manual_review"
DIRECT_DML_ALLOW_DIRECT = "allow_direct"

VALID_DIRECT_DML_ACTIONS = frozenset({
    DIRECT_DML_PREFER_EXISTING_OWNER,
    DIRECT_DML_MANUAL_REVIEW,
    DIRECT_DML_ALLOW_DIRECT,
})

# Global State Actions
GLOBAL_STATE_REDESIGN = "redesign_state_management"
GLOBAL_STATE_PRESERVE = "preserve_package_state"
GLOBAL_STATE_ASSISTED = "assisted"
GLOBAL_STATE_BLOCK = "block_generation"

VALID_GLOBAL_STATE_RECOMMENDATIONS = frozenset({
    GLOBAL_STATE_REDESIGN,
    GLOBAL_STATE_PRESERVE,
    GLOBAL_STATE_ASSISTED,
})

VALID_GLOBAL_STATE_EXECUTIONS = frozenset({
    GLOBAL_STATE_ASSISTED,
    GLOBAL_STATE_BLOCK,
    "manual",
})


class ArchitecturePolicyError(ValueError):
    """Invalid architecture policy specification."""


@dataclass(frozen=True)
class DirectDmlPolicy:
    when_existing_owner: str = DIRECT_DML_PREFER_EXISTING_OWNER
    no_owner: str = DIRECT_DML_MANUAL_REVIEW


@dataclass(frozen=True)
class GlobalStatePolicy:
    recommendation: str = GLOBAL_STATE_REDESIGN
    execution: str = GLOBAL_STATE_ASSISTED


@dataclass(frozen=True)
class DatabaseApiPolicy:
    preserve_by_default: bool = True


@dataclass(frozen=True)
class ArchitecturePolicy:
    """Immutable architecture policy definition."""

    policy_version: int = POLICY_VERSION
    direct_dml: DirectDmlPolicy = field(default_factory=DirectDmlPolicy)
    global_state: GlobalStatePolicy = field(default_factory=GlobalStatePolicy)
    database_api: DatabaseApiPolicy = field(default_factory=DatabaseApiPolicy)


def default_architecture_policy() -> ArchitecturePolicy:
    """Default FormsLang modern architecture baseline."""
    return ArchitecturePolicy()


def validate_policy_dict(payload: dict[str, Any]) -> None:
    """Validate raw dictionary before deserialization."""
    if not isinstance(payload, dict):
        raise ArchitecturePolicyError("Policy payload must be a dictionary")

    version = payload.get("policy_version", POLICY_VERSION)
    if version != POLICY_VERSION:
        raise ArchitecturePolicyError(f"Unsupported policy version: {version}")

    if "direct_dml" in payload:
        ddml = payload["direct_dml"]
        if not isinstance(ddml, dict):
            raise ArchitecturePolicyError("direct_dml must be an object")
        owner_action = ddml.get("when_existing_owner", DIRECT_DML_PREFER_EXISTING_OWNER)
        if owner_action not in VALID_DIRECT_DML_ACTIONS:
            raise ArchitecturePolicyError(f"Invalid direct_dml.when_existing_owner: {owner_action}")
        no_owner_action = ddml.get("no_owner", DIRECT_DML_MANUAL_REVIEW)
        if no_owner_action not in VALID_DIRECT_DML_ACTIONS:
            raise ArchitecturePolicyError(f"Invalid direct_dml.no_owner: {no_owner_action}")

    if "global_state" in payload:
        gs = payload["global_state"]
        if not isinstance(gs, dict):
            raise ArchitecturePolicyError("global_state must be an object")
        rec = gs.get("recommendation", GLOBAL_STATE_REDESIGN)
        if rec not in VALID_GLOBAL_STATE_RECOMMENDATIONS:
            raise ArchitecturePolicyError(f"Invalid global_state.recommendation: {rec}")
        exec_mode = gs.get("execution", GLOBAL_STATE_ASSISTED)
        if exec_mode not in VALID_GLOBAL_STATE_EXECUTIONS:
            raise ArchitecturePolicyError(f"Invalid global_state.execution: {exec_mode}")

    if "database_api" in payload:
        db_api = payload["database_api"]
        if not isinstance(db_api, dict):
            raise ArchitecturePolicyError("database_api must be an object")
        if "preserve_by_default" in db_api and not isinstance(db_api["preserve_by_default"], bool):
            raise ArchitecturePolicyError("database_api.preserve_by_default must be a boolean")


def policy_to_dict(policy: ArchitecturePolicy) -> dict[str, Any]:
    """Serialize policy to JSON-compatible dictionary."""
    return {
        "policy_version": policy.policy_version,
        "direct_dml": {
            "when_existing_owner": policy.direct_dml.when_existing_owner,
            "no_owner": policy.direct_dml.no_owner,
        },
        "global_state": {
            "recommendation": policy.global_state.recommendation,
            "execution": policy.global_state.execution,
        },
        "database_api": {
            "preserve_by_default": policy.database_api.preserve_by_default,
        },
    }


def policy_from_dict(payload: dict[str, Any]) -> ArchitecturePolicy:
    """Construct validated ArchitecturePolicy from dictionary."""
    validate_policy_dict(payload)
    ddml_data = payload.get("direct_dml", {})
    gs_data = payload.get("global_state", {})
    api_data = payload.get("database_api", {})

    return ArchitecturePolicy(
        policy_version=payload.get("policy_version", POLICY_VERSION),
        direct_dml=DirectDmlPolicy(
            when_existing_owner=ddml_data.get("when_existing_owner", DIRECT_DML_PREFER_EXISTING_OWNER),
            no_owner=ddml_data.get("no_owner", DIRECT_DML_MANUAL_REVIEW),
        ),
        global_state=GlobalStatePolicy(
            recommendation=gs_data.get("recommendation", GLOBAL_STATE_REDESIGN),
            execution=gs_data.get("execution", GLOBAL_STATE_ASSISTED),
        ),
        database_api=DatabaseApiPolicy(
            preserve_by_default=api_data.get("preserve_by_default", True),
        ),
    )


def resolve_effective_policy(
    default_policy: ArchitecturePolicy | None = None,
    organization_policy: dict[str, Any] | ArchitecturePolicy | None = None,
    project_policy: dict[str, Any] | ArchitecturePolicy | None = None,
) -> tuple[ArchitecturePolicy, dict[str, str]]:
    """Resolve hierarchical policy and track provenance for every setting.

    Hierarchy:
    FormsLang Default -> Organization Policy -> Project Policy

    Returns:
    (effective_policy, provenance_map)
    where provenance_map tracks which level defined each setting.
    """
    base = default_policy or default_architecture_policy()
    provenance = {
        "direct_dml.when_existing_owner": PROVENANCE_DEFAULT,
        "direct_dml.no_owner": PROVENANCE_DEFAULT,
        "global_state.recommendation": PROVENANCE_DEFAULT,
        "global_state.execution": PROVENANCE_DEFAULT,
        "database_api.preserve_by_default": PROVENANCE_DEFAULT,
    }

    effective = policy_to_dict(base)

    def apply_layer(layer_data: dict[str, Any] | ArchitecturePolicy | None, source_label: str) -> None:
        if not layer_data:
            return
        data = policy_to_dict(layer_data) if isinstance(layer_data, ArchitecturePolicy) else copy.deepcopy(layer_data)
        validate_policy_dict(data)

        if "direct_dml" in data:
            ddml = data["direct_dml"]
            if "when_existing_owner" in ddml:
                effective["direct_dml"]["when_existing_owner"] = ddml["when_existing_owner"]
                provenance["direct_dml.when_existing_owner"] = source_label
            if "no_owner" in ddml:
                effective["direct_dml"]["no_owner"] = ddml["no_owner"]
                provenance["direct_dml.no_owner"] = source_label

        if "global_state" in data:
            gs = data["global_state"]
            if "recommendation" in gs:
                effective["global_state"]["recommendation"] = gs["recommendation"]
                provenance["global_state.recommendation"] = source_label
            if "execution" in gs:
                effective["global_state"]["execution"] = gs["execution"]
                provenance["global_state.execution"] = source_label

        if "database_api" in data:
            db_api = data["database_api"]
            if "preserve_by_default" in db_api:
                effective["database_api"]["preserve_by_default"] = db_api["preserve_by_default"]
                provenance["database_api.preserve_by_default"] = source_label

    apply_layer(organization_policy, PROVENANCE_ORGANIZATION)
    apply_layer(project_policy, PROVENANCE_PROJECT)

    return policy_from_dict(effective), provenance


class ArchitecturePolicyEvaluator:
    """Evaluates observed facts against effective policy to generate explainable recommendations."""

    def __init__(self, policy: ArchitecturePolicy, provenance: dict[str, str] | None = None):
        self.policy = policy
        self.provenance = provenance or {}

    def evaluate_direct_dml(
        self,
        table_name: str,
        has_known_owner: bool,
        owner_name: str | None = None,
    ) -> dict[str, Any]:
        """Evaluate direct DML bypassing an existing owner vs table without an owner.

        Formula (§22):
        Structural evidence + Policy = Recommendation & Intent
        """
        table_upper = table_name.upper()
        if has_known_owner and owner_name:
            rule_key = "direct_dml.when_existing_owner"
            action = self.policy.direct_dml.when_existing_owner
            prov = self.provenance.get(rule_key, PROVENANCE_DEFAULT)

            if action == DIRECT_DML_PREFER_EXISTING_OWNER:
                return {
                    "rule": rule_key,
                    "action": action,
                    "provenance": f"Structural evidence + {prov} policy ({action})",
                    "intent": "REROUTE_TO_OWNING_API",
                    "recommendation": f"Reroute direct DML on '{table_upper}' through package API '{owner_name.upper()}'",
                    "requires_redesign": False,
                }
            elif action == DIRECT_DML_MANUAL_REVIEW:
                return {
                    "rule": rule_key,
                    "action": action,
                    "provenance": f"Structural evidence + {prov} policy ({action})",
                    "intent": "REVIEW_BYPASS_OWNERSHIP",
                    "recommendation": f"Manual architectural review: direct DML on '{table_upper}' coexists with API '{owner_name.upper()}'",
                    "requires_redesign": False,
                }
            else:
                return {
                    "rule": rule_key,
                    "action": action,
                    "provenance": f"Structural evidence + {prov} policy ({action})",
                    "intent": "ALLOW_DIRECT_TABLE_ACCESS",
                    "recommendation": f"Retain direct DML on '{table_upper}' per policy",
                    "requires_redesign": False,
                }
        else:
            rule_key = "direct_dml.no_owner"
            action = self.policy.direct_dml.no_owner
            prov = self.provenance.get(rule_key, PROVENANCE_DEFAULT)

            if action == DIRECT_DML_MANUAL_REVIEW:
                return {
                    "rule": rule_key,
                    "action": action,
                    "provenance": f"Structural evidence + {prov} policy ({action})",
                    "intent": "INSPECT_TABLE_TRIGGERS",
                    "recommendation": f"Inspect table triggers and constraints on '{table_upper}' prior to direct access generation",
                    "requires_redesign": False,
                }
            else:
                return {
                    "rule": rule_key,
                    "action": action,
                    "provenance": f"Structural evidence + {prov} policy ({action})",
                    "intent": "ALLOW_DIRECT_TABLE_ACCESS",
                    "recommendation": f"Allow direct table access on '{table_upper}'",
                    "requires_redesign": False,
                }

    def evaluate_global_state(self, package_name: str) -> dict[str, Any]:
        """Evaluate package-level global state coupling."""
        rule_key = "global_state.recommendation"
        rec_action = self.policy.global_state.recommendation
        exec_mode = self.policy.global_state.execution
        prov = self.provenance.get(rule_key, PROVENANCE_DEFAULT)

        pkg_upper = package_name.upper()
        if rec_action == GLOBAL_STATE_REDESIGN:
            return {
                "rule": rule_key,
                "action": rec_action,
                "execution_mode": exec_mode,
                "provenance": f"Structural evidence + {prov} policy ({rec_action})",
                "intent": "REDESIGN_STATE_MANAGEMENT",
                "recommendation": f"Extract package session variables in '{pkg_upper}' to client/framework context before generation",
                "block_generation": (exec_mode == GLOBAL_STATE_BLOCK),
            }
        elif rec_action == GLOBAL_STATE_PRESERVE:
            return {
                "rule": rule_key,
                "action": rec_action,
                "execution_mode": exec_mode,
                "provenance": f"Structural evidence + {prov} policy ({rec_action})",
                "intent": "PRESERVE_PACKAGE_STATE",
                "recommendation": f"Preserve package state in '{pkg_upper}'; verify connection affinity and session pooling",
                "block_generation": False,
            }
        else:
            return {
                "rule": rule_key,
                "action": rec_action,
                "execution_mode": exec_mode,
                "provenance": f"Structural evidence + {prov} policy ({rec_action})",
                "intent": "ASSISTED_STATE_REFACTOR",
                "recommendation": f"Assisted refactor: convert '{pkg_upper}' package state to stateless parameters where possible",
                "block_generation": False,
            }

    def evaluate_database_api(self, api_name: str) -> dict[str, Any]:
        """Evaluate existing PL/SQL database API preservation."""
        rule_key = "database_api.preserve_by_default"
        preserve = self.policy.database_api.preserve_by_default
        prov = self.provenance.get(rule_key, PROVENANCE_DEFAULT)
        api_upper = api_name.upper()

        if preserve:
            return {
                "rule": rule_key,
                "action": "preserve",
                "provenance": f"Structural evidence + {prov} policy (preserve_by_default)",
                "intent": "PRESERVE_DATABASE_API",
                "recommendation": f"Preserve existing database package API '{api_upper}' as core domain service",
            }
        else:
            return {
                "rule": rule_key,
                "action": "refactor",
                "provenance": f"Structural evidence + {prov} policy (refactor)",
                "intent": "REVIEW_API_REFACTOR",
                "recommendation": f"Evaluate API '{api_upper}' for modernization refactoring",
            }
