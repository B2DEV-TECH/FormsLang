"""Estate Intelligence tests for FormsLang 2.1+.

Tests the 4 authoritative Hotspot Anti-Pattern Detectors (§88, §89, §107),
the deterministic logarithmic 'Start Here' priority ranking algorithm (§4),
and Overview Cockpit read models.
"""

import math

from formslang.hotspots import (
    HOTSPOT_API_BYPASS,
    HOTSPOT_DUPLICATED_RULE,
    HOTSPOT_GLOBAL_STATE,
    HOTSPOT_OWNERSHIP_CONFLICT,
    detect_api_bypass_candidates,
    detect_cross_layer_ownership_conflicts,
    detect_duplicated_rule_clusters,
    detect_estate_hotspots,
    detect_global_state_couplings,
    is_temp_table,
)
from formslang.project_projection import overview, prepare_projection


def test_is_temp_table_detection():
    assert is_temp_table("TMP_ORDERS")
    assert is_temp_table("temp_session_data")
    assert is_temp_table("GTT_INVOICES")
    assert is_temp_table("WRK_BATCH")
    assert not is_temp_table("ORDERS")
    assert not is_temp_table("CUSTOMER_ACCOUNTS")


def test_detect_api_bypass_candidate_via_graph():
    blueprint = {
        "entities": [
            {"id": "trigger:t1", "type": "TRIGGER", "name": "ON-INSERT", "module": "orders.xml"},
            {"id": "table:orders", "type": "TABLE", "name": "ORDERS", "module": "db/schema.sql"},
            {"id": "pkg:api", "type": "PACKAGE_SPEC", "name": "ORDER_API", "module": "db/order_api.pks"},
        ],
        "edges": [
            {"id": "e1", "type": "WRITES", "source": "trigger:t1", "target": "table:orders"},
            {"id": "e2", "type": "WRITES", "source": "pkg:api", "target": "table:orders"},
        ],
        "findings": [],
    }
    hotspots = detect_api_bypass_candidates(blueprint)
    assert len(hotspots) == 1
    h = hotspots[0]
    assert h.hotspot_type == HOTSPOT_API_BYPASS
    assert h.severity == "CRITICAL"
    assert h.entity_id == "trigger:t1"
    assert h.evidence["table"] == "ORDERS"
    assert h.evidence["bypassed_package"] == "ORDER_API"


def test_detect_api_bypass_ignores_temp_tables():
    blueprint = {
        "entities": [
            {"id": "trigger:t1", "type": "TRIGGER", "name": "POST-QUERY", "module": "orders.xml"},
            {"id": "table:tmp", "type": "TABLE", "name": "TMP_ORDERS", "module": "db/schema.sql"},
            {"id": "pkg:api", "type": "PACKAGE_SPEC", "name": "ORDER_API", "module": "db/order_api.pks"},
        ],
        "edges": [
            {"id": "e1", "type": "WRITES", "source": "trigger:t1", "target": "table:tmp"},
            {"id": "e2", "type": "WRITES", "source": "pkg:api", "target": "table:tmp"},
        ],
        "findings": [],
    }
    hotspots = detect_api_bypass_candidates(blueprint)
    assert len(hotspots) == 0


def test_detect_duplicated_rule_clusters():
    blueprint = {
        "entities": [
            {"id": "trigger:t1", "type": "TRIGGER", "name": "WVI_DISCOUNT", "module": "orders.xml"},
            {"id": "trigger:t2", "type": "TRIGGER", "name": "WVI_RATE", "module": "invoices.xml"},
        ],
        "findings": [
            {
                "id": "f1",
                "entity": "trigger:t1",
                "code": "LOGIC_DUPLICATED_PREDICATE",
                "target": "DISCOUNT_RULE",
                "statement": "Validates discount threshold",
            },
            {
                "id": "f2",
                "entity": "trigger:t2",
                "code": "LOGIC_DUPLICATED_PREDICATE",
                "target": "DISCOUNT_RULE",
                "statement": "Validates discount threshold",
            },
        ],
    }
    clusters = detect_duplicated_rule_clusters(blueprint)
    assert len(clusters) == 1
    c = clusters[0]
    assert c.hotspot_type == HOTSPOT_DUPLICATED_RULE
    assert c.severity == "HIGH"
    assert c.evidence["occurrences"] == 2
    assert "orders.xml" in c.evidence["modules"]
    assert "invoices.xml" in c.evidence["modules"]


def test_detect_global_state_coupling_with_navigation():
    blueprint = {
        "entities": [
            {
                "id": "unit:auth",
                "type": "TRIGGER",
                "name": "PRE-FORM",
                "module": "login.xml",
                "attributes": {
                    "source": ":GLOBAL.USER_TOKEN := 'XYZ'; CALL_FORM('ORDERS');",
                },
            },
            {
                "id": "unit:orders",
                "type": "TRIGGER",
                "name": "WHEN-NEW-FORM-INSTANCE",
                "module": "orders.xml",
                "attributes": {
                    "source": "IF :GLOBAL.USER_TOKEN IS NULL THEN RAISE FORM_TRIGGER_FAILURE; END IF;",
                },
            },
        ],
        "edges": [],
        "findings": [],
    }
    hotspots = detect_global_state_couplings(blueprint)
    assert len(hotspots) == 1
    h = hotspots[0]
    assert h.hotspot_type == HOTSPOT_GLOBAL_STATE
    assert h.severity == "HIGH"  # Elevated due to CALL_FORM
    assert h.evidence["variable"] == ":GLOBAL.USER_TOKEN"
    assert "login.xml" in h.evidence["writers"]
    assert "orders.xml" in h.evidence["readers"]
    assert h.evidence["cross_module_navigation"] is True


def test_detect_global_state_coupling_without_navigation():
    blueprint = {
        "entities": [
            {
                "id": "unit:m1",
                "type": "TRIGGER",
                "name": "POST-CHANGE",
                "module": "m1.xml",
                "attributes": {"source": ":GLOBAL.SHARED_COUNTER := 1;"},
            },
            {
                "id": "unit:m2",
                "type": "TRIGGER",
                "name": "PRE-QUERY",
                "module": "m2.xml",
                "attributes": {"source": ":BLOCK.ITEM := :GLOBAL.SHARED_COUNTER;"},
            },
        ],
        "edges": [],
        "findings": [],
    }
    hotspots = detect_global_state_couplings(blueprint)
    assert len(hotspots) == 1
    h = hotspots[0]
    assert h.hotspot_type == HOTSPOT_GLOBAL_STATE
    assert h.severity == "MEDIUM"  # No cross-module navigation


def test_detect_cross_layer_ownership_conflicts():
    blueprint = {
        "entities": [
            {"id": "trigger:chk", "type": "TRIGGER", "name": "WVI_AGE", "module": "customer.xml"},
        ],
        "findings": [
            {
                "id": "f_conflict",
                "entity": "trigger:chk",
                "code": HOTSPOT_OWNERSHIP_CONFLICT,
                "statement": "Form trigger allows age > 18 while DB check constraint enforces age >= 21",
                "reason": "Boundary divergence on CUSTOMER.AGE",
            },
        ],
    }
    conflicts = detect_cross_layer_ownership_conflicts(blueprint)
    assert len(conflicts) == 1
    assert conflicts[0].hotspot_type == HOTSPOT_OWNERSHIP_CONFLICT
    assert conflicts[0].severity == "CRITICAL"


def test_detect_estate_hotspots_aggregation():
    blueprint = {
        "entities": [
            {"id": "t1", "type": "TRIGGER", "name": "T1", "module": "m1.xml"},
            {"id": "t2", "type": "TRIGGER", "name": "T2", "module": "m2.xml"},
            {"id": "table:1", "type": "TABLE", "name": "T_DATA", "module": "db.sql"},
            {"id": "pkg:1", "type": "PACKAGE_SPEC", "name": "DATA_API", "module": "db.pks"},
        ],
        "edges": [
            {"id": "e1", "type": "WRITES", "source": "t1", "target": "table:1"},
            {"id": "e2", "type": "WRITES", "source": "pkg:1", "target": "table:1"},
        ],
        "findings": [
            {"id": "f1", "entity": "t2", "code": HOTSPOT_OWNERSHIP_CONFLICT, "statement": "Divergent check"},
        ],
    }
    summary = detect_estate_hotspots(blueprint)
    assert summary["total"] == 2
    assert summary["by_type"]["api_bypass"] == 1
    assert summary["by_type"]["cross_layer_conflict"] == 1


def test_start_here_priority_scoring_formula():
    descriptor = {
        "id": "p_test",
        "name": "Estate Test",
        "source_roots": [{"id": "src", "kind": "forms", "path": "."}],
        "target": {"platform": "Oracle APEX", "version": "26.1", "representation": "APEXlang"},
    }
    # 1 critical finding with 3 fan-in edges and API bypass
    assessment = {
        "status": "Current",
        "analysis_revision": "a" * 64,
        "source_revision": "b" * 64,
        "review_revision": 0,
        "analyzed_at": "2026-09-21T12:00:00Z",
        "blueprint": {
            "entities": [
                {"id": "form:main", "type": "FORM", "name": "MAIN", "module": "main.xml"},
                {"id": "trigger:t1", "type": "TRIGGER", "name": "WVI", "module": "main.xml", "attributes": {"risk": {"level": "CRITICAL"}}},
                {"id": "sub1", "type": "PROGRAM_UNIT", "name": "CALLER1", "module": "main.xml"},
                {"id": "sub2", "type": "PROGRAM_UNIT", "name": "CALLER2", "module": "main.xml"},
                {"id": "sub3", "type": "PROGRAM_UNIT", "name": "CALLER3", "module": "main.xml"},
            ],
            "edges": [
                {"id": "e1", "type": "CALLS", "source": "sub1", "target": "trigger:t1"},
                {"id": "e2", "type": "CALLS", "source": "sub2", "target": "trigger:t1"},
                {"id": "e3", "type": "CALLS", "source": "sub3", "target": "trigger:t1"},
            ],
            "findings": [
                {
                    "id": "finding:crit_bypass",
                    "entity": "trigger:t1",
                    "code": "DIRECT_DML_BYPASSES_API",
                    "recommendation": "MANUAL_REVIEW",
                    "execution_verdict": "MANUAL",
                    "reason": "Direct DML bypasses API",
                    "classification": ["BUSINESS_RULE"],
                    "statements": [],
                    "evidence": [],
                },
            ],
        },
        "inventory": {},
    }
    prepared = prepare_projection(descriptor, assessment, {"status": "CURRENT"}, store_scope="test_store")
    result = overview(prepared)

    # Check overview contains hotspots
    assert "hotspots" in result
    assert result["inventory"]["architectural_hotspots"] >= 0

    # Check priority summary and start_here ranking
    priority = result["priority"]
    assert priority["total"] == 1
    assert len(priority["start_here"]) == 1
    top = priority["start_here"][0]

    # Verify calculation:
    # Base: 100 (CRITICAL)
    # FanIn: 3 -> log2(1 + 3) = 2.0 -> 0.2 * 2.0 = 0.40
    # IsBypass: True -> +0.30
    # Expected multiplier: 1.0 + 0.40 + 0.30 = 1.70
    # Expected score: 100 * 1.70 = 170.0
    expected_score = round(100.0 * (1.0 + 0.2 * math.log2(4) + 0.30), 1)
    assert top["score"] == expected_score
    assert any("Base Severity: 100" in b for b in top["breakdown"])
    assert any("Fan-In: 3" in b for b in top["breakdown"])
    assert any("API Bypass: Yes" in b for b in top["breakdown"])
