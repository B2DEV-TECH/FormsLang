"""Tests for Modernization Model (IR) 6-level taxonomy, mappings, and invalidation matrix."""

from __future__ import annotations

import pytest

from formslang.modernization_model import (
    EVENT_DISPLAY_PREFERENCE_CHANGED,
    EVENT_ENGINE_RULES_UPDATED,
    EVENT_HUMAN_DECISION_RECORDED,
    EVENT_POLICY_UPDATED,
    EVENT_SOURCE_BYTES_MODIFIED,
    EVENT_TARGET_STRATEGY_CHANGED,
    INTENTS,
    LEGACY_TO_INTENT,
    SIGNALS,
    GenerationEligibility,
    HumanDecision,
    ModernizationIntent,
    ObservedFact,
    RevisionTaxonomy,
    StructuralSignal,
    TargetRecommendation,
    apply_stale_decision_preservation,
    compute_model_digest,
    evaluate_invalidation_matrix,
    map_intent_to_target_recommendation,
    map_legacy_recommendation_to_intent,
    model_from_finding,
)
from formslang.project_model import TargetProfile


def test_taxonomy_data_structures_roundtrip():
    fact = ObservedFact(
        kind="CODE",
        source_id="src:orders",
        entity="ORDERS",
        location="ORDERS.ORDER_TOTAL.POST-CHANGE",
        lines=(10, 25),
        code_excerpt="calc_total();",
        attributes={"trigger": "POST-CHANGE"},
    )
    fact_dict = fact.to_dict()
    assert ObservedFact.from_dict(fact_dict) == fact

    signal = StructuralSignal(
        id="sig:1",
        kind="DIRECT_DML",
        severity="HIGH",
        priority_score=65.0,
        fan_in=3,
        factors=["base_severity: 50", "api_bypass (+30.0%)"],
        facts=[fact_dict],
        summary="Direct DML on orders bypassing ORDER_API",
    )
    assert signal.kind in SIGNALS
    signal_dict = signal.to_dict()
    assert StructuralSignal.from_dict(signal_dict) == signal

    intent = ModernizationIntent(
        id="intent:1",
        kind="CENTRALIZE_EXISTING_OWNER",
        summary="Centralize order mutations to ORDER_API",
        architectural_rationale="Database package ORDER_API encapsulates business rules.",
        signals=[signal_dict],
    )
    assert intent.kind in INTENTS
    intent_dict = intent.to_dict()
    assert ModernizationIntent.from_dict(intent_dict) == intent

    rec = TargetRecommendation(
        id="rec:1",
        target_platform="Oracle APEX",
        recommendation_code="MOVE_TO_PLSQL_API",
        target_component_kind="plsql_package_procedure",
        rationale="Call ORDER_API.MUTATE in process.",
        native_opportunity=False,
    )
    assert TargetRecommendation.from_dict(rec.to_dict()) == rec

    decision = HumanDecision(
        id="dec:1",
        item_id="finding:123",
        disposition="KEEP",
        target_profile=TargetProfile(platform="Oracle APEX", version="26.1"),
        notes="Approved for migration to ORDER_API.",
        reviewer="Lead Architect",
        decided_at="2026-09-21T20:00:00Z",
    )
    dec_dict = decision.to_dict()
    dec_restored = HumanDecision.from_dict(dec_dict)
    assert dec_restored.disposition == "KEEP"
    assert dec_restored.reviewer == "Lead Architect"
    assert isinstance(dec_restored.target_profile, TargetProfile)

    eligibility = GenerationEligibility(
        module_id="orders",
        status="ELIGIBLE",
        eligible=True,
        blockers=[],
        warnings=[],
    )
    assert GenerationEligibility.from_dict(eligibility.to_dict()) == eligibility


def test_legacy_recommendation_correspondence():
    assert len(LEGACY_TO_INTENT) == 7
    expected_mappings = {
        "MOVE_TO_PLSQL_API": "CENTRALIZE_EXISTING_OWNER",
        "REPLACE_WITH_APEX_NATIVE": "REPLACE_MECHANICAL_BEHAVIOR",
        "PRESERVE": "PRESERVE_EXISTING_OWNER",
        "CONVERT": "INTRODUCE_SERVICE_BOUNDARY",
        "REFACTOR": "REDESIGN_BEHAVIOR",
        "MANUAL_REVIEW": "REVIEW_BUSINESS_INTENT",
        "DROP": "REMOVE_OBSOLETE_BEHAVIOR",
    }
    for legacy, expected_intent in expected_mappings.items():
        assert map_legacy_recommendation_to_intent(legacy) == expected_intent
        # APEX target mapping restores original recommendation
        assert map_intent_to_target_recommendation(expected_intent, "Oracle APEX") == legacy

    # Generic Modernization target mappings
    assert map_intent_to_target_recommendation("CENTRALIZE_EXISTING_OWNER", "Generic Modernization") == "PRESERVE_EXISTING_SERVICE_BOUNDARY"
    assert map_intent_to_target_recommendation("REPLACE_MECHANICAL_BEHAVIOR", "Generic Modernization") == "REPLACE_WITH_WEB_FRAMEWORK_NATIVE"
    assert map_intent_to_target_recommendation("INTRODUCE_SERVICE_BOUNDARY", "Generic Modernization") == "EXTRACT_TO_BACKEND_SERVICE"
    assert map_intent_to_target_recommendation("REDESIGN_BEHAVIOR", "Generic Modernization") == "REDESIGN_STATE_OR_WORKFLOW"
    assert map_intent_to_target_recommendation("REVIEW_BUSINESS_INTENT", "Generic Modernization") == "MANUAL_ARCHITECTURE_REVIEW"
    assert map_intent_to_target_recommendation("REMOVE_OBSOLETE_BEHAVIOR", "Generic Modernization") == "DECOMMISSION_OR_RETIRE"

    # Unknown fallback
    assert map_legacy_recommendation_to_intent("UNKNOWN_RANDOM_CODE") == "UNKNOWN"
    assert map_intent_to_target_recommendation("UNKNOWN", "Oracle APEX") == "MANUAL_REVIEW"
    assert map_intent_to_target_recommendation("UNKNOWN", "Generic Modernization") == "MANUAL_ARCHITECTURE_REVIEW"


def test_model_from_finding_and_digest():
    finding = {
        "id": "f-42",
        "source_id": "src:customers",
        "form": "CUSTOMERS",
        "block": "CUST",
        "item": "CREDIT_LIMIT",
        "trigger": "WHEN-VALIDATE-ITEM",
        "source": "if :CUST.CREDIT_LIMIT < 0 then fail; end if;",
        "recommendation": "REPLACE_WITH_APEX_NATIVE",
        "severity": "MEDIUM",
        "priority_score": 25.0,
        "priority_factors": ["base_severity: 20", "fan_in: 1"],
        "summary": "Credit limit validation in trigger",
        "rationale": "Use declarative range check.",
    }
    intent = model_from_finding(finding)
    assert intent.kind == "REPLACE_MECHANICAL_BEHAVIOR"
    assert len(intent.signals) == 1
    sig = intent.signals[0]
    assert sig["priority_score"] == 25.0
    assert len(sig["facts"]) == 1
    assert sig["facts"][0]["attributes"]["trigger"] == "WHEN-VALIDATE-ITEM"

    digest = compute_model_digest(intent.to_dict())
    assert len(digest) == 64
    assert compute_model_digest(intent.to_dict()) == digest


def test_invalidation_matrix_source_bytes_modified():
    report = evaluate_invalidation_matrix(
        EVENT_SOURCE_BYTES_MODIFIED,
        current_revisions=RevisionTaxonomy(source_revision="sha-new"),
        previous_revisions=RevisionTaxonomy(source_revision="sha-old"),
        decisions=[{"id": "dec:1", "disposition": "KEEP"}],
    )
    assert report.reextract_facts_and_signals is True
    assert report.recompute_intent is True
    assert report.mark_decisions_stale is True
    assert report.invalidate_target_plan is True
    assert report.invalidate_code_approvals is True
    assert report.invalidate_artifacts is True
    assert report.stale_decision_count == 1


def test_invalidation_matrix_engine_rules_updated():
    report = evaluate_invalidation_matrix(
        EVENT_ENGINE_RULES_UPDATED,
        current_revisions={},
    )
    assert report.reextract_facts_and_signals is True
    assert report.recompute_intent is True
    assert report.mark_decisions_stale is True
    assert report.invalidate_target_plan is True


def test_invalidation_matrix_policy_updated():
    report = evaluate_invalidation_matrix(
        EVENT_POLICY_UPDATED,
        current_revisions={},
    )
    assert report.reextract_facts_and_signals is False
    assert report.recompute_intent is True
    assert report.mark_decisions_stale is False
    assert report.invalidate_target_plan is True
    assert report.invalidate_code_approvals is False


def test_invalidation_matrix_target_strategy_changed():
    report = evaluate_invalidation_matrix(
        EVENT_TARGET_STRATEGY_CHANGED,
        current_revisions={},
    )
    assert report.reextract_facts_and_signals is False
    assert report.recompute_intent is False
    assert report.mark_decisions_stale is False
    assert report.invalidate_target_plan is True
    assert report.invalidate_code_approvals is True
    assert report.invalidate_artifacts is True


def test_invalidation_matrix_human_decision_recorded():
    report = evaluate_invalidation_matrix(
        EVENT_HUMAN_DECISION_RECORDED,
        current_revisions={},
    )
    assert report.reextract_facts_and_signals is False
    assert report.recompute_intent is False
    assert report.mark_decisions_stale is False
    assert report.invalidate_target_plan is True
    assert report.invalidate_code_approvals is True
    assert report.invalidate_artifacts is True


def test_invalidation_matrix_display_preference_changed():
    report = evaluate_invalidation_matrix(
        EVENT_DISPLAY_PREFERENCE_CHANGED,
        current_revisions={},
    )
    assert report.reextract_facts_and_signals is False
    assert report.recompute_intent is False
    assert report.mark_decisions_stale is False
    assert report.invalidate_target_plan is False
    assert report.invalidate_code_approvals is False
    assert report.invalidate_artifacts is False


def test_stale_decision_preservation():
    decisions = [
        {"id": "d1", "item_id": "f1", "disposition": "KEEP", "notes": "Approved by Lead"},
        {"id": "d2", "item_id": "f2", "disposition": "OVERRIDE", "notes": "Extract to Spring service"},
    ]
    preserved = apply_stale_decision_preservation(decisions, "Source modified in revision sha-abc")
    assert len(preserved) == 2
    assert preserved[0]["stale"] is True
    assert preserved[0]["stale_reason"] == "Source modified in revision sha-abc"
    assert preserved[0]["notes"] == "Approved by Lead"
    assert preserved[1]["stale"] is True
    assert preserved[1]["disposition"] == "OVERRIDE"


def test_invalid_event_raises_error():
    with pytest.raises(ValueError, match="Unknown invalidation trigger event"):
        evaluate_invalidation_matrix("UNKNOWN_EVENT", current_revisions={})


def test_unmapped_values_and_missing_evidence_stay_unknown():
    """Experimental IR: no fabricated signal, severity, fan-in or platform fallback."""
    import pytest

    assert map_legacy_recommendation_to_intent("WRAP_AS_API") == "UNKNOWN"
    assert map_legacy_recommendation_to_intent("SOMETHING_NEW") == "UNKNOWN"
    for platform in ("UNSELECTED", "Java", ""):
        with pytest.raises(ValueError):
            map_intent_to_target_recommendation("PRESERVE_EXISTING_OWNER", platform)
    intent = model_from_finding({"id": "f1"})
    assert intent.kind == "UNKNOWN"
    (signal,) = intent.signals
    assert signal["kind"] == "UNKNOWN" and signal["severity"] == "UNKNOWN" and signal["fan_in"] == 0
