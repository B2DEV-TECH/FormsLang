"""Tests for FormsLang 2.1 Multi-Form System Map and Global Modernization Search.

Tests bounded neighborhood topology traversal (§14), edge evidence inspection,
layer filtering, direct DML bypass detection, and multi-category instant search.
"""

from formslang.project_projection import (
    PreparedProjection,
    ProjectionKey,
    prepare_projection,
    search_project,
    system_map,
)


def _make_key(pid="a" * 32):
    return ProjectionKey(
        store_scope="scope1",
        project_id=pid,
        analysis_revision="1" * 64,
        review_revision=0,
        target=("Oracle APEX", "26.1", "APEXlang"),
        freshness="CURRENT",
    )


def _sample_blueprint():
    return {
        "entities": [
            {"id": "form:orders", "type": "FORM", "name": "ORDERS.fmb", "module": "ORDERS.fmb"},
            {"id": "form:customers", "type": "FORM", "name": "CUSTOMERS.fmb", "module": "CUSTOMERS.fmb"},
            {"id": "pkg:order_api", "type": "PACKAGE", "name": "ORDER_API", "module": "db/order_api.pks"},
            {"id": "table:orders", "type": "TABLE", "name": "TAB_ORDERS", "module": "db/schema.sql"},
            {"id": "table:customers", "type": "TABLE", "name": "TAB_CUSTOMERS", "module": "db/schema.sql"},
            {"id": "view:order_summary", "type": "VIEW", "name": "VW_ORDER_SUMMARY", "module": "db/views.sql"},
            {"id": "global:user", "type": "GLOBAL", "name": "GLOBAL.USER_ID", "module": ""},
            {"id": "lib:common", "type": "LIBRARY", "name": "COMMON.pll", "module": "COMMON.pll"},
            {"id": "trigger:orders_pi", "type": "TRIGGER", "name": "POST-INSERT", "module": "ORDERS.fmb"},
            {"id": "rule:discount", "type": "BUSINESS_RULE", "name": "BR-DISCOUNT-LIMIT", "module": "ORDERS.fmb", "attributes": {"classification": ["BUSINESS_RULE"]}},
        ],
        "edges": [
            {"id": "e1", "type": "OPENS_FORM", "source": "form:customers", "target": "form:orders"},
            {"id": "e2", "type": "CALLS", "source": "form:orders", "target": "pkg:order_api"},
            {"id": "e3", "type": "WRITES", "source": "pkg:order_api", "target": "table:orders"},
            {"id": "e4", "type": "WRITES", "source": "form:orders", "target": "table:orders"},  # Direct DML bypass!
            {"id": "e5", "type": "READS", "source": "form:orders", "target": "view:order_summary"},
            {"id": "e6", "type": "REFERENCES", "source": "form:orders", "target": "global:user"},
            {"id": "e7", "type": "USES", "source": "form:orders", "target": "lib:common"},
            {"id": "e8", "type": "WRITES", "source": "form:customers", "target": "table:customers"},
        ],
        "findings": [
            {
                "id": "f_bypass",
                "entity": "form:orders",
                "risk": "CRITICAL",
                "recommendation": "MOVE_TO_PLSQL_API",
                "reason": "Direct DML on TAB_ORDERS while ORDER_API exists",
                "classification": ["DATA_ACCESS"],
            },
            {
                "id": "f_rule",
                "entity": "rule:discount",
                "risk": "HIGH",
                "recommendation": "REFACTOR",
                "reason": "Discount threshold validation",
                "classification": ["BUSINESS_RULE"],
            },
        ],
    }


def _make_prepared(blueprint=None):
    bp = blueprint if blueprint is not None else _sample_blueprint()
    descriptor = {
        "id": "a" * 32,
        "name": "Estate Modernization",
        "description": "System Map Testing",
        "client_label": "Enterprise Client",
        "target": {"platform": "Oracle APEX", "version": "26.1", "representation": "APEXlang"},
    }
    assessment = {
        "status": "Current",
        "analysis_revision": "1" * 64,
        "source_revision": "2" * 64,
        "review_revision": 0,
        "analyzed_at": "2026-09-21T18:00:00Z",
        "blueprint": bp,
    }
    return prepare_projection(descriptor, assessment, {"status": "CURRENT"}, store_scope="test")


def test_system_map_empty_project():
    empty_prepared = PreparedProjection(
        _make_key(), {"name": "Empty"}, {}, {"project": {"name": "Empty"}}, {}, {},
    )
    result = system_map(empty_prepared)
    assert result["nodes"] == []
    assert result["edges"] == []
    assert result["focus"] is None
    assert result["total_nodes"] == 0
    assert not result["truncated"]


def test_system_map_default_focus_and_depth_1():
    prepared = _make_prepared()
    res_d1 = system_map(prepared, focus="form:orders", depth=1)
    assert res_d1["focus"] == "form:orders"
    node_ids = {n["id"] for n in res_d1["nodes"]}
    assert "form:orders" in node_ids
    assert "pkg:order_api" in node_ids
    assert "table:orders" in node_ids
    assert "global:user" in node_ids
    assert "table:customers" not in node_ids


def test_system_map_depth_2_includes_indirect_neighbors():
    prepared = _make_prepared()
    res_d2 = system_map(prepared, focus="form:orders", depth=2)
    node_ids = {n["id"] for n in res_d2["nodes"]}
    assert "table:customers" in node_ids
    assert res_d2["total_nodes"] > 5


def test_system_map_limit_capping_and_truncation():
    prepared = _make_prepared()
    res_limited = system_map(prepared, focus="form:orders", depth=3, limit=3)
    assert len(res_limited["nodes"]) <= 3
    assert res_limited["truncated"] is True


def test_system_map_layer_filtering():
    prepared = _make_prepared()
    res_db = system_map(prepared, focus="form:orders", depth=2, layer="DATABASE")
    for n in res_db["nodes"]:
        if n["id"] != "form:orders":
            assert n["layer"] == "DATABASE"
    assert any(n["type"] == "TABLE" for n in res_db["nodes"])


def test_system_map_edge_classification_and_bypass():
    prepared = _make_prepared()
    res = system_map(prepared, focus="form:orders", depth=2)
    edges = {e["id"]: e for e in res["edges"]}

    assert edges["e1"]["classification"] == "OPENS_FORM"
    assert edges["e2"]["classification"] == "CALLS"
    assert edges["e3"]["classification"] == "WRITES"
    assert edges["e4"]["classification"] == "DIRECT_DML" or edges["e4"]["is_hotspot"]
    assert edges["e6"]["classification"] == "SHARES_STATE"


def test_system_map_edge_type_filter():
    prepared = _make_prepared()
    res_calls = system_map(prepared, focus="form:orders", depth=2, edge_type="CALLS")
    for e in res_calls["edges"]:
        assert e["classification"] == "CALLS"


def test_search_project_empty_query():
    prepared = _make_prepared()
    res = search_project(prepared, "")
    assert res["total"] == 0
    assert res["results"] == []


def test_search_project_multi_category_matches():
    prepared = _make_prepared()

    res_orders = search_project(prepared, "orders")
    assert res_orders["total"] > 0
    categories = {r["category"] for r in res_orders["results"]}
    assert "forms" in categories
    assert "tables" in categories

    top = res_orders["results"][0]
    assert "orders" in top["title"].casefold()
    assert "action" in top
    assert "view" in top["action"]


def test_search_project_matches_packages_and_rules():
    prepared = _make_prepared()

    res_pkg = search_project(prepared, "ORDER_API")
    assert any(r["category"] == "packages" and "ORDER_API" in r["title"] for r in res_pkg["results"])

    res_rule = search_project(prepared, "DISCOUNT")
    assert any(r["category"] == "business_rules" for r in res_rule["results"])


def test_search_project_limit():
    prepared = _make_prepared()
    res = search_project(prepared, "o", limit=2)
    assert len(res["results"]) <= 2
    assert res["total"] >= len(res["results"])
