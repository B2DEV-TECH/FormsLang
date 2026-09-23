"""Modernization Model (IR) -- EXPERIMENTAL foundation for a future release.

Status in FormsLang 2.1: not authoritative and not wired into the product. The
persisted project assessment (Blueprint + review ledger) remains the single
source of truth; Estate Intelligence is a projection of it (``hotspots``,
``project_projection``). Nothing here governs invalidation, review or
generation. The mappings are string correspondences, not proof of semantic
equivalence, and a value with no mapping stays ``UNKNOWN``.
"""

from __future__ import annotations

import copy
import hashlib
from dataclasses import asdict, dataclass, field
from typing import Any

from .project_model import TargetProfile, canonical_json

# ---------------------------------------------------------------------------
# Level 3: Modernization Intent Taxonomy (§2.3)
# ---------------------------------------------------------------------------

INTENTS = frozenset({
    "PRESERVE_EXISTING_OWNER",
    "CENTRALIZE_EXISTING_OWNER",
    "INTRODUCE_SERVICE_BOUNDARY",
    "REPLACE_MECHANICAL_BEHAVIOR",
    "REDESIGN_BEHAVIOR",
    "RESOLVE_OWNERSHIP",
    "REMOVE_OBSOLETE_BEHAVIOR",
    "REVIEW_BUSINESS_INTENT",
    "REVIEW_CONCURRENCY",
    "REVIEW_SECURITY",
    "UNKNOWN",
})

# ---------------------------------------------------------------------------
# Level 2: Structural Signals Taxonomy (§2.2)
# ---------------------------------------------------------------------------

SIGNALS = frozenset({
    "DIRECT_DML",
    "API_DELEGATION",
    "API_BYPASS_CANDIDATE",
    "DUPLICATED_PREDICATE",
    "GLOBAL_STATE",
    "CROSS_MODULE_NAVIGATION",
    "DEPENDENCY_CYCLE",
    "CONCURRENCY_GUARD",
    "GUARD_LOSS",
    "ORPHANED_LOGIC",
})

# ---------------------------------------------------------------------------
# Level 5: Human Decision Dispositions
# ---------------------------------------------------------------------------

DISPOSITIONS = frozenset({
    "KEEP",
    "OVERRIDE",
    "IGNORE",
    "DISCUSS",
    "DEFER",
})

# ---------------------------------------------------------------------------
# Level 6: Generation Eligibility Statuses
# ---------------------------------------------------------------------------

ELIGIBILITY_STATUS = frozenset({
    "ELIGIBLE",
    "BLOCKED",
    "NOT_APPLICABLE",
    "REQUIRES_DECISION",
})

# ---------------------------------------------------------------------------
# Legacy recommendation correspondence (§3) -- not lossless; unmapped values stay UNKNOWN
# ---------------------------------------------------------------------------

LEGACY_TO_INTENT: dict[str, str] = {
    "MOVE_TO_PLSQL_API": "CENTRALIZE_EXISTING_OWNER",
    "REPLACE_WITH_APEX_NATIVE": "REPLACE_MECHANICAL_BEHAVIOR",
    "PRESERVE": "PRESERVE_EXISTING_OWNER",
    "CONVERT": "INTRODUCE_SERVICE_BOUNDARY",
    "REFACTOR": "REDESIGN_BEHAVIOR",
    "MANUAL_REVIEW": "REVIEW_BUSINESS_INTENT",
    "DROP": "REMOVE_OBSOLETE_BEHAVIOR",
}

INTENT_TO_APEX: dict[str, str] = {
    "CENTRALIZE_EXISTING_OWNER": "MOVE_TO_PLSQL_API",
    "REPLACE_MECHANICAL_BEHAVIOR": "REPLACE_WITH_APEX_NATIVE",
    "PRESERVE_EXISTING_OWNER": "PRESERVE",
    "INTRODUCE_SERVICE_BOUNDARY": "CONVERT",
    "REDESIGN_BEHAVIOR": "REFACTOR",
    "REVIEW_BUSINESS_INTENT": "MANUAL_REVIEW",
    "REMOVE_OBSOLETE_BEHAVIOR": "DROP",
    "RESOLVE_OWNERSHIP": "MANUAL_REVIEW",
    "REVIEW_CONCURRENCY": "MANUAL_REVIEW",
    "REVIEW_SECURITY": "MANUAL_REVIEW",
    "UNKNOWN": "MANUAL_REVIEW",
}

INTENT_TO_GENERIC: dict[str, str] = {
    "CENTRALIZE_EXISTING_OWNER": "PRESERVE_EXISTING_SERVICE_BOUNDARY",
    "REPLACE_MECHANICAL_BEHAVIOR": "REPLACE_WITH_WEB_FRAMEWORK_NATIVE",
    "PRESERVE_EXISTING_OWNER": "PRESERVE",
    "INTRODUCE_SERVICE_BOUNDARY": "EXTRACT_TO_BACKEND_SERVICE",
    "REDESIGN_BEHAVIOR": "REDESIGN_STATE_OR_WORKFLOW",
    "REVIEW_BUSINESS_INTENT": "MANUAL_ARCHITECTURE_REVIEW",
    "REMOVE_OBSOLETE_BEHAVIOR": "DECOMMISSION_OR_RETIRE",
    "RESOLVE_OWNERSHIP": "RESOLVE_CROSS_LAYER_CONFLICT",
    "REVIEW_CONCURRENCY": "MIGRATE_CONCURRENCY_MODEL",
    "REVIEW_SECURITY": "AUDIT_SECURITY_BOUNDARY",
    "UNKNOWN": "MANUAL_ARCHITECTURE_REVIEW",
}


def map_legacy_recommendation_to_intent(legacy: str) -> str:
    """Map a 2.0 recommendation to an intent; values without a mapping stay UNKNOWN."""
    normalized = str(legacy).strip().upper()
    return LEGACY_TO_INTENT.get(normalized, "UNKNOWN")


def map_intent_to_target_recommendation(intent: str, target_platform: str) -> str:
    """Map target-neutral intent to target-specific recommendation code."""
    normalized_intent = str(intent).strip().upper()
    platform = str(target_platform).strip()
    if platform == "Oracle APEX":
        return INTENT_TO_APEX.get(normalized_intent, "MANUAL_REVIEW")
    if platform == "Generic Modernization":
        return INTENT_TO_GENERIC.get(normalized_intent, "MANUAL_ARCHITECTURE_REVIEW")
    raise ValueError(f"No recommendation mapping for target platform: {platform or 'none'}")


# ---------------------------------------------------------------------------
# 6-Level Data Structures
# ---------------------------------------------------------------------------

@dataclass
class ObservedFact:
    """Level 1: Deterministic extraction from source AST or DDL/PLSQL."""
    kind: str  # MODULE, CODE, DATABASE, NAVIGATION, GLOBAL
    source_id: str
    entity: str
    location: str
    lines: tuple[int, int] | None = None
    code_excerpt: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ObservedFact:
        return cls(**data)


@dataclass
class StructuralSignal:
    """Level 2: Cross-layer structural interpretation of observed facts."""
    id: str
    kind: str  # From SIGNALS
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW, UNKNOWN
    priority_score: float = 0.0
    fan_in: int = 0
    factors: list[str] = field(default_factory=list)
    facts: list[dict[str, Any]] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StructuralSignal:
        return cls(**data)


@dataclass
class ModernizationIntent:
    """Level 3: Target-neutral architectural goal."""
    id: str
    kind: str  # From INTENTS
    summary: str
    architectural_rationale: str
    signals: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ModernizationIntent:
        return cls(**data)


@dataclass
class TargetRecommendation:
    """Level 4: Target-specific implementation mapping."""
    id: str
    target_platform: str
    recommendation_code: str
    target_component_kind: str
    rationale: str
    native_opportunity: bool = False
    policy_provenance: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TargetRecommendation:
        return cls(**data)


@dataclass
class HumanDecision:
    """Level 5: Human architect decision with append-only audit trail."""
    id: str
    item_id: str
    disposition: str  # From DISPOSITIONS
    target_profile: TargetProfile | dict[str, Any]
    notes: str = ""
    reviewer: str = ""
    decided_at: str = ""
    stale: bool = False
    stale_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if isinstance(self.target_profile, TargetProfile):
            data["target_profile"] = asdict(self.target_profile)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HumanDecision:
        profile_data = data.get("target_profile", {})
        if isinstance(profile_data, dict):
            profile = TargetProfile(**profile_data) if profile_data else TargetProfile()
        else:
            profile = profile_data
        data_copy = dict(data)
        data_copy["target_profile"] = profile
        return cls(**data_copy)


@dataclass
class GenerationEligibility:
    """Level 6: Gate verifying valid source revision and human sign-off."""
    module_id: str
    status: str  # From ELIGIBILITY_STATUS
    eligible: bool = False
    blockers: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GenerationEligibility:
        return cls(**data)


# ---------------------------------------------------------------------------
# Multi-Revision Taxonomy & Invalidation Matrix (§40)
# ---------------------------------------------------------------------------

@dataclass
class RevisionTaxonomy:
    """Fine-grained multi-revision tracking (§4.1)."""
    source_revision: str = ""
    analysis_revision: str = ""
    modernization_model_revision: str = ""
    review_revision: int = 0
    policy_revision: str = ""
    target_strategy_revision: str = ""
    code_approval_revision: str = ""
    artifact_revision: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# Change events that trigger invalidation evaluation
EVENT_SOURCE_BYTES_MODIFIED = "SOURCE_BYTES_MODIFIED"
EVENT_ENGINE_RULES_UPDATED = "ENGINE_RULES_UPDATED"
EVENT_POLICY_UPDATED = "POLICY_UPDATED"
EVENT_TARGET_STRATEGY_CHANGED = "TARGET_STRATEGY_CHANGED"
EVENT_HUMAN_DECISION_RECORDED = "HUMAN_DECISION_RECORDED"
EVENT_DISPLAY_PREFERENCE_CHANGED = "DISPLAY_PREFERENCE_CHANGED"

SUPPORTED_EVENTS = frozenset({
    EVENT_SOURCE_BYTES_MODIFIED,
    EVENT_ENGINE_RULES_UPDATED,
    EVENT_POLICY_UPDATED,
    EVENT_TARGET_STRATEGY_CHANGED,
    EVENT_HUMAN_DECISION_RECORDED,
    EVENT_DISPLAY_PREFERENCE_CHANGED,
})


@dataclass
class InvalidationReport:
    """Result of evaluating the Invalidation Matrix (§4.2)."""
    event: str
    reextract_facts_and_signals: bool
    recompute_intent: bool
    mark_decisions_stale: bool
    invalidate_target_plan: bool
    invalidate_code_approvals: bool
    invalidate_artifacts: bool
    stale_decision_count: int = 0
    audit_message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_invalidation_matrix(
    event: str,
    *,
    current_revisions: dict[str, Any] | RevisionTaxonomy,
    previous_revisions: dict[str, Any] | RevisionTaxonomy | None = None,
    decisions: list[dict[str, Any]] | None = None,
) -> InvalidationReport:
    """Deterministic evaluation of the Multi-Revision Invalidation Matrix (§40).

    Guarantees that:
    1. Human decisions are NEVER silently discarded when source changes;
       they are marked as STALE with full audit trail.
    2. Display or filter preferences never trigger downstream cache invalidation.
    3. Target strategy changes invalidate plans and code approvals without
       affecting source facts or human review decisions.
    """
    if event not in SUPPORTED_EVENTS:
        raise ValueError(f"Unknown invalidation trigger event: {event}")

    stale_count = 0
    if decisions:
        stale_count = len(decisions)

    if event == EVENT_SOURCE_BYTES_MODIFIED:
        return InvalidationReport(
            event=event,
            reextract_facts_and_signals=True,
            recompute_intent=True,
            mark_decisions_stale=True,
            invalidate_target_plan=True,
            invalidate_code_approvals=True,
            invalidate_artifacts=True,
            stale_decision_count=stale_count,
            audit_message="Source bytes modified: re-extracted facts, intent recomputed, previous decisions marked stale.",
        )

    if event == EVENT_ENGINE_RULES_UPDATED:
        return InvalidationReport(
            event=event,
            reextract_facts_and_signals=True,
            recompute_intent=True,
            mark_decisions_stale=True,
            invalidate_target_plan=True,
            invalidate_code_approvals=True,
            invalidate_artifacts=True,
            stale_decision_count=stale_count,
            audit_message="Engine rules updated: re-extracted facts, recomputed intent, previous decisions marked stale.",
        )

    if event == EVENT_POLICY_UPDATED:
        return InvalidationReport(
            event=event,
            reextract_facts_and_signals=False,
            recompute_intent=True,
            mark_decisions_stale=False,
            invalidate_target_plan=True,
            invalidate_code_approvals=False,
            invalidate_artifacts=False,
            stale_decision_count=0,
            audit_message="Policy updated: intent recomputed; target plan invalidated.",
        )

    if event == EVENT_TARGET_STRATEGY_CHANGED:
        return InvalidationReport(
            event=event,
            reextract_facts_and_signals=False,
            recompute_intent=False,
            mark_decisions_stale=False,
            invalidate_target_plan=True,
            invalidate_code_approvals=True,
            invalidate_artifacts=True,
            stale_decision_count=0,
            audit_message="Target strategy changed: target plan and code approvals invalidated; facts and human decisions preserved.",
        )

    if event == EVENT_HUMAN_DECISION_RECORDED:
        return InvalidationReport(
            event=event,
            reextract_facts_and_signals=False,
            recompute_intent=False,
            mark_decisions_stale=False,
            invalidate_target_plan=True,
            invalidate_code_approvals=True,
            invalidate_artifacts=True,
            stale_decision_count=0,
            audit_message="Human decision recorded: target plan invalidated for affected unit.",
        )

    # EVENT_DISPLAY_PREFERENCE_CHANGED
    return InvalidationReport(
        event=event,
        reextract_facts_and_signals=False,
        recompute_intent=False,
        mark_decisions_stale=False,
        invalidate_target_plan=False,
        invalidate_code_approvals=False,
        invalidate_artifacts=False,
        stale_decision_count=0,
        audit_message="Display/filter preference changed: no operational invalidation.",
    )


def apply_stale_decision_preservation(
    decisions: list[dict[str, Any]],
    reason: str,
) -> list[dict[str, Any]]:
    """Preserves human decisions by flagging them as STALE without deleting them (§151)."""
    updated: list[dict[str, Any]] = []
    for d in decisions:
        clone = copy.deepcopy(d)
        clone["stale"] = True
        clone["stale_reason"] = reason
        updated.append(clone)
    return updated


# ---------------------------------------------------------------------------
# Model Construction & Extraction Helpers
# ---------------------------------------------------------------------------

def model_from_finding(finding: dict[str, Any], assessment: dict[str, Any] | None = None) -> ModernizationIntent:
    """Constructs a ModernizationIntent from a legacy finding dict."""
    legacy_rec = finding.get("recommendation", "UNKNOWN")
    intent_kind = map_legacy_recommendation_to_intent(legacy_rec)

    # Extract Level 1 facts
    facts: list[dict[str, Any]] = []
    source = finding.get("source") or finding.get("trigger") or ""
    facts.append(
        ObservedFact(
            kind="CODE",
            source_id=finding.get("source_id", ""),
            entity=finding.get("form", "") or finding.get("module", ""),
            location=finding.get("location", "") or finding.get("block", ""),
            code_excerpt=str(source)[:1000],
            attributes={
                "trigger": finding.get("trigger", ""),
                "item": finding.get("item", ""),
                "block": finding.get("block", ""),
            },
        ).to_dict()
    )

    # Extract Level 2 signal
    # Missing or unmapped evidence stays unknown; it is never a named signal.
    signal_kind = finding.get("signal_kind") or finding.get("hotspot_type") or "UNKNOWN"
    if signal_kind not in SIGNALS:
        signal_kind = "UNKNOWN"

    signal = StructuralSignal(
        id=f"sig:{finding.get('id', 'unknown')}",
        kind=signal_kind,
        severity=finding.get("severity", "UNKNOWN"),
        priority_score=float(finding.get("priority_score", 0.0)),
        fan_in=int(finding.get("fan_in", 0)),
        factors=list(finding.get("priority_factors", [])),
        facts=facts,
        summary=finding.get("summary", "") or finding.get("title", ""),
    )

    return ModernizationIntent(
        id=f"intent:{finding.get('id', 'unknown')}",
        kind=intent_kind,
        summary=finding.get("summary", "") or finding.get("title", ""),
        architectural_rationale=finding.get("rationale", "") or finding.get("advice", ""),
        signals=[signal.to_dict()],
    )


def compute_model_digest(data: Any) -> str:
    """Deterministic canonical SHA-256 digest of any model structure."""
    return hashlib.sha256(canonical_json(data).encode("utf-8")).hexdigest()
