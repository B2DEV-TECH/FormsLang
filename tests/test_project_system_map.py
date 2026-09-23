"""System Map projection contract: module-level architecture with bounded responses.

Real-source journeys live in test_estate_intelligence.py. These cases use the
producer's shapes (FORM roots containing triggers, SUBPROGRAM_BODY writers,
resolved symbolic references) at a scale that is impractical to author as XML.
"""

from __future__ import annotations

import json
import time

import pytest

from formslang.project_model import ProjectError
from formslang.project_projection import (
    MAP_MAX_EDGES,
    MAP_MAX_SELECTOR,
    prepare_projection,
    search_project,
    system_map,
)


def prepared_from(blueprint):
    assessment = {"status": "Current", "analysis_revision": "1" * 64, "source_revision": "2" * 64,
                  "review_revision": 0, "analyzed_at": "2026-09-21T18:00:00Z", "project_id": "a" * 32,
                  "blueprint": {"evidence": [], **blueprint}}
    return prepare_projection({"id": "a" * 32, "name": "Estate"}, assessment, {"status": "CURRENT"},
                              store_scope="test")


def form(name, module):
    return {"id": f"form:{name}", "type": "FORM", "name": name, "module": module, "attributes": {}}


def unit(identity, module, kind="TRIGGER"):
    return {"id": identity, "type": kind, "name": identity.upper(), "module": module, "attributes": {}}


def table(name):
    return {"id": f"table:{name}", "type": "TABLE", "name": name, "module": "db/t.sql", "attributes": {}}


def reference(name, resolved=None):
    row = {"id": f"ref:{name}", "type": "TABLE_OR_VIEW_REFERENCE", "name": name, "module": "", "attributes": {}}
    if resolved:
        row.update(resolution="RESOLVED_TO_DATABASE_OBJECT", resolved_target=resolved)
    return row


def edge(identity, kind, source, target):
    return {"id": identity, "type": kind, "source": source, "target": target, "evidence": [f"ev:{identity}"]}


def small_estate():
    return {
        "entities": [
            form("ORDERS", "r/orders.xml"), form("CUSTOMERS", "r/customers.xml"),
            unit("trg_save", "r/orders.xml"), unit("trg_open", "r/customers.xml"),
            unit("pu_back", "r/orders.xml", "PROGRAM_UNIT"),
            table("ORDERS_T"), reference("ORDERS_T", "table:ORDERS_T"), reference("UNKNOWN_T"),
            {"id": "spec:api", "type": "PACKAGE_SPEC", "name": "API", "module": "db/api.pks", "attributes": {}},
            {"id": "sub:api.save", "type": "SUBPROGRAM_BODY", "name": "API.SAVE", "module": "db/api.pkb",
             "attributes": {"package": "API"}},
            {"id": "psub:api.save", "type": "PACKAGE_SUBPROGRAM", "name": "API.SAVE", "module": "db/api.pks",
             "attributes": {"package": "API"}},
            {"id": "call:api.save", "type": "ROUTINE_REFERENCE", "name": "API.SAVE", "module": "",
             "attributes": {}, "resolution": "RESOLVED_TO_DATABASE_OBJECT", "resolved_target": "psub:api.save"},
            {"id": "b:x", "type": "BUILTIN", "name": "COMMIT_FORM", "module": "", "attributes": {}},
        ],
        "edges": [
            edge("c1", "CONTAINS", "form:ORDERS", "trg_save"),
            edge("c2", "CONTAINS", "form:CUSTOMERS", "trg_open"),
            edge("w1", "WRITES", "trg_save", "ref:ORDERS_T"),
            edge("w2", "WRITES", "pu_back", "ref:ORDERS_T"),
            edge("w3", "WRITES", "sub:api.save", "ref:ORDERS_T"),
            edge("r1", "READS", "trg_save", "ref:UNKNOWN_T"),
            edge("k1", "CALLS", "trg_save", "call:api.save"),
            edge("o1", "OPENS_FORM", "trg_open", "form:ORDERS"),
            edge("o2", "OPENS_FORM", "trg_save", "form:CUSTOMERS"),
            edge("i1", "INVOKES_BUILTIN", "trg_save", "b:x"),
            edge("d1", "DECLARES", "spec:api", "psub:api.save"),
        ],
        "findings": [
            {"id": "trg_save", "entity": "trg_save", "recommendation": "MANUAL_REVIEW", "statements": []},
            {"id": "pu_back", "entity": "pu_back", "recommendation": "MANUAL_REVIEW", "statements": []},
        ],
    }


def by_names(result):
    nodes = {n["id"]: n["name"] for n in result["nodes"]}
    return {(nodes[e["source"]], nodes[e["target"]], e["classification"]): e for e in result["edges"]}


def test_form_focus_exposes_component_dependencies_and_cycles():
    result = system_map(prepared_from(small_estate()), focus="form:ORDERS", depth=1)
    edges = by_names(result)
    writes = edges[("ORDERS", "ORDERS_T", "WRITES")]
    assert writes["count"] == 2 and writes["components"] == ["PU_BACK", "TRG_SAVE"]
    assert ("ORDERS", "API", "CALLS") in edges
    assert ("ORDERS", "UNKNOWN_T", "READS") in edges
    assert ("ORDERS", "CUSTOMERS", "OPENS_FORM") in edges and ("CUSTOMERS", "ORDERS", "OPENS_FORM") in edges
    nodes = {n["name"]: n for n in result["nodes"]}
    assert nodes["UNKNOWN_T"]["layer"] == "UNRESOLVED" and nodes["API"]["type"] == "PACKAGE"
    assert nodes["ORDERS"]["findings_count"] == 2 and nodes["ORDERS"]["members"] >= 2
    assert "COMMIT_FORM" not in nodes and "TRG_SAVE" not in nodes


def test_package_members_fold_into_one_package_node():
    result = system_map(prepared_from(small_estate()), focus="form:ORDERS", depth=2)
    names = [n["name"] for n in result["nodes"]]
    assert names.count("API") == 1 and "API.SAVE" not in names
    assert ("API", "ORDERS_T", "WRITES") in by_names(result)


def test_empty_estate_returns_an_empty_bounded_map():
    result = system_map(prepared_from({"entities": [], "edges": [], "findings": []}))
    assert result["nodes"] == [] and result["focus"] is None and result["truncated"] is False


def high_volume_estate(forms=500, tables=6000):
    entities = [form(f"F{i:03}", f"r/f{i:03}.xml") for i in range(forms)]
    edges = []
    hub = "r/f000.xml"
    for t in range(tables):
        entities += [table(f"T{t}"), reference(f"T{t}", f"table:T{t}"), unit(f"u{t}", hub)]
        edges.append(edge(f"w{t}", "WRITES", f"u{t}", f"ref:T{t}"))
    # 2,000 parallel edges between two modules collapse to one relationship.
    for p in range(2000):
        entities.append(unit(f"p{p}", "r/f001.xml"))
        edges.append(edge(f"o{p}", "OPENS_FORM", f"p{p}", "form:F000"))
    return {"entities": entities, "edges": edges, "findings": []}


def test_high_fan_out_and_parallel_edges_keep_every_budget_bounded():
    prepared = prepared_from(high_volume_estate())
    started = time.perf_counter()
    result = system_map(prepared, focus="form:F000", depth=1, limit=50, edge_limit=100)
    elapsed = time.perf_counter() - started
    assert len(result["nodes"]) == 50 and len(result["edges"]) <= 100
    assert len(result["available_forms"]) == MAP_MAX_SELECTOR
    reasons = {t["reason"]: t for t in result["truncation"]}
    assert reasons["NODE_LIMIT"]["available"] == 6002
    assert reasons["SELECTOR_LIMIT"]["available"] == 500
    assert result["selector"] == {"total": 500, "shown": MAP_MAX_SELECTOR, "truncated": True}
    parallel = [e for e in result["edges"] if e["classification"] == "OPENS_FORM"]
    assert len(parallel) == 1 and parallel[0]["count"] == 2000 and len(parallel[0]["edge_ids"]) == 5
    assert len(json.dumps(result)) < 200_000
    assert elapsed < 10


def test_edge_budget_is_independent_of_node_budget():
    prepared = prepared_from(high_volume_estate(forms=2, tables=600))
    result = system_map(prepared, focus="form:F000", depth=1, limit=200, edge_limit=MAP_MAX_EDGES)
    assert len(result["edges"]) <= MAP_MAX_EDGES
    capped = system_map(prepared, focus="form:F000", depth=1, limit=200, edge_limit=10)
    assert len(capped["edges"]) == 10
    # 200 kept nodes: the focus, F001 and 198 tables -> 198 WRITES + 1 OPENS_FORM.
    assert {"reason": "EDGE_LIMIT", "limit": 10, "available": 199} in capped["truncation"]


def test_selector_keeps_a_focus_beyond_the_selector_budget():
    prepared = prepared_from(high_volume_estate(forms=260, tables=1))
    result = system_map(prepared, focus="form:F259", depth=1)
    assert result["available_forms"][-1] == {"id": "form:F259", "name": "F259"}
    assert len(result["available_forms"]) == MAP_MAX_SELECTOR == result["selector"]["shown"]


def test_same_named_packages_from_different_roots_stay_distinct():
    estate = small_estate()
    estate["entities"].append({"id": "spec:api2", "type": "PACKAGE_SPEC", "name": "API",
                               "module": "other/api.pks", "attributes": {}})
    estate["entities"][8]["module"] = "db/api.pks"
    estate["entities"][9]["module"] = "db/api.pkb"
    estate["entities"][10]["module"] = "db/api.pks"
    estate["edges"].append(edge("k2", "CALLS", "trg_open", "spec:api2"))
    result = system_map(prepared_from(estate), focus="form:ORDERS", depth=3)
    assert [n["name"] for n in result["nodes"]].count("API") == 2


@pytest.mark.parametrize("kwargs", [
    {"depth": 0}, {"depth": 6}, {"depth": "2"}, {"limit": 0}, {"limit": 201}, {"edge_limit": 0},
    {"edge_limit": 401}, {"layer": "SERVICE"}, {"edge_type": "OWNS"}, {"focus": "form:NOPE"},
    {"focus": "x" * 501},
])
def test_invalid_map_requests_fail_explicitly(kwargs):
    with pytest.raises(ProjectError):
        system_map(prepared_from(small_estate()), **kwargs)


def test_search_is_bounded_and_carries_its_context():
    prepared = prepared_from(small_estate())
    assert search_project(prepared, "")["results"] == []
    result = search_project(prepared, "orders", limit=1)
    assert len(result["results"]) == 1 and result["total"] >= 2
    assert result["project_id"] == "a" * 32 and result["analysis_revision"] == "1" * 64
    for query, limit in (("orders", 0), ("orders", 51), ("orders", True), ("x" * 201, 5), (None, 5)):
        with pytest.raises(ProjectError):
            search_project(prepared, query, limit=limit)
