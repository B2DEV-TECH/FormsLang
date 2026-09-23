"""Visual projection (2.2): contracts, deterministic layout, overlays and static SVG."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
from test_project_system_map import (
    edge,
    form,
    high_volume_estate,
    prepared_from,
    small_estate,
)

from formslang.project_model import ProjectError
from formslang.project_projection import (
    prepare_projection,
    search_project,
    system_map,
    system_map_node,
    visual_overview,
)
from formslang.project_visualization import (
    BOUNDARY,
    MAX_ROWS,
    attention_matrix,
    estate_layout,
    focus_layout,
    labels_catalog,
    report_estate_svg,
    report_matrix_svg,
    visual_node,
)

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_CLAIMS = ("health score", "% complete", "percent complete", "roi", "wave ", "easy migration",
                    "completion date", "business critical")


def node(identity, name, layer="FORM", node_type="FORM"):
    return {"id": identity, "name": name, "layer": layer, "type": node_type}


def link(source, target, classification="CALLS"):
    return {"source": source, "target": target, "classification": classification}


def test_node_and_edge_contracts_are_complete_and_keep_21_fields():
    result = system_map(prepared_from(small_estate()), focus="form:ORDERS", depth=2)
    for item in result["nodes"]:
        for key in ("id", "name", "type", "presentation_type", "layer", "module", "findings_count",
                    "highest_risk", "hotspot_count", "review_summary", "dependency_count", "unresolved",
                    "fan_in", "fan_out", "risk", "is_focus", "lane", "status"):
            assert key in item, key
        assert item["dependency_count"] == item["fan_in"] + item["fan_out"]
        assert set(item["presentation_type"]) == {"technical", "executive"}
    for item in result["edges"]:
        for key in ("id", "source", "target", "classification", "presentation_label", "count",
                    "components", "hotspot_ids", "evidence_refs", "evidence", "level", "status"):
            assert key in item, key
    nodes = {n["name"]: n for n in result["nodes"]}
    assert nodes["UNKNOWN_T"]["unresolved"] is True and nodes["UNKNOWN_T"]["status"] == "UNRESOLVED"
    assert nodes["UNKNOWN_T"]["lane"] == "INTEGRATION"
    assert nodes["ORDERS"]["lane"] == "APPLICATION" and nodes["API"]["lane"] == "SHARED_LOGIC"
    assert nodes["ORDERS_T"]["lane"] == "DATA"
    # A node without findings reports zero observed findings, not an invented risk.
    assert nodes["ORDERS_T"]["findings_count"] == 0 and nodes["ORDERS_T"]["highest_risk"] == "NONE"
    assert nodes["ORDERS_T"]["review_summary"] == {"total": 0, "decided": 0, "open": 0, "stale": 0,
                                                  "deferred": 0}


def test_executive_labels_rename_presentation_only():
    labels = labels_catalog()
    assert labels["types"]["FORM"] == {"technical": "Form", "executive": "Application module"}
    assert labels["types"]["PACKAGE"]["executive"] == "Shared PL/SQL service"
    assert labels["types"]["TABLE"]["executive"] == labels["types"]["VIEW"]["executive"] == "Data object"
    expected = {"CALLS": "Uses service", "READS": "Reads data", "WRITES": "Changes data",
                "OPENS_FORM": "Opens module", "SHARES_STATE": "Shares global state",
                "DUPLICATES_LOGIC": "Similar logic observed"}
    assert {k: v["executive"] for k, v in labels["relationships"].items() if k in expected} == expected
    assert labels["unresolved"]["executive"] == "Unresolved reference"
    assert len(set(labels["statuses"].values())) == 5


def test_estate_view_places_every_node_in_its_semantic_lane():
    result = system_map(prepared_from(small_estate()), view="ESTATE")
    assert result["view"] == "ESTATE" and result["focus"] is None
    positions = result["layout"]["positions"]
    assert set(positions) == {n["id"] for n in result["nodes"]}
    lanes = {c["id"]: c for c in result["layout"]["columns"]}
    assert list(lanes) == ["APPLICATION", "SHARED_LOGIC", "DATA", "INTEGRATION"]
    for item in result["nodes"]:
        assert positions[item["id"]]["column"] == item["lane"]
    xs = [lanes[lane]["x"] for lane in lanes]
    assert xs == sorted(xs)


def test_default_view_stays_focus_and_focus_accepts_any_node():
    prepared = prepared_from(small_estate())
    assert system_map(prepared)["view"] == "FOCUS"
    by_id = system_map(prepared, focus="table:ORDERS_T", depth=1)
    assert by_id["focus"] == "table:ORDERS_T" and by_id["layout"]["mode"] == "FOCUS"
    by_name = system_map(prepared, focus="api", depth=1)
    assert by_name["focus"] == "spec:api"
    with pytest.raises(ProjectError):
        system_map(prepared, view="GALAXY")


def test_focus_layout_puts_inbound_left_outbound_right_and_flags_cycles():
    nodes = {i: node(i, i.upper()) for i in ("a", "b", "c", "d", "e")}
    edges = [link("a", "b"), link("b", "c"), link("d", "b"), link("c", "b"), link("e", "d")]
    layout = focus_layout(nodes, edges, "b")
    column = {k: v["column"] for k, v in layout["positions"].items()}
    assert column["b"] == "FOCUS"
    assert column["a"] == column["d"] == "IN_1" and column["e"] == "IN_2"
    assert column["c"] == "OUT_1"  # reachable both ways at distance 1: right, flagged
    assert layout["cycle_nodes"] == ["c"]
    x = {k: v["x"] for k, v in layout["positions"].items()}
    assert x["e"] < x["a"] < x["b"] < x["c"]


def test_layout_is_independent_of_input_order():
    nodes = {f"n{i}": node(f"n{i}", f"N{i % 7}", *(("DATABASE", "TABLE") if i % 3 else ("FORM", "FORM")))
             for i in range(40)}
    edges = [link(f"n{i}", f"n{(i * 7) % 40}") for i in range(40) if i != (i * 7) % 40]
    first = estate_layout(nodes, edges)
    shuffled = dict(reversed(list(nodes.items())))
    assert estate_layout(shuffled, list(reversed(edges))) == first
    assert focus_layout(shuffled, list(reversed(edges)), "n3") == focus_layout(nodes, edges, "n3")


def test_layout_is_independent_of_hash_seed():
    script = ("import json,sys;sys.path.insert(0,'tests');"
              "from test_project_system_map import prepared_from,high_volume_estate;"
              "from formslang.project_projection import system_map;"
              "p=prepared_from(high_volume_estate(forms=30,tables=80));"
              "print(json.dumps([system_map(p,view='ESTATE',limit=120),"
              "system_map(p,focus='form:F001',depth=3)],sort_keys=True))")
    outputs = set()
    for seed in ("0", "1", "12345"):
        env = {**os.environ, "PYTHONHASHSEED": seed}
        run = subprocess.run([sys.executable, "-c", script], cwd=ROOT, env=env, capture_output=True,
                             text=True, check=True)
        outputs.add(run.stdout)
    assert len(outputs) == 1


def test_tall_lanes_wrap_into_sub_columns():
    nodes = {f"t{i:03}": node(f"t{i:03}", f"T{i:03}", "DATABASE", "TABLE") for i in range(MAX_ROWS * 2 + 1)}
    layout = estate_layout(nodes, [])
    data = next(c for c in layout["columns"] if c["id"] == "DATA")
    assert data["count"] == MAX_ROWS * 2 + 1
    assert len({p["x"] for p in layout["positions"].values()}) == 3
    assert max(p["y"] for p in layout["positions"].values()) < layout["height"]


def test_empty_estate_and_single_node_have_valid_layouts():
    empty = system_map(prepared_from({"entities": [], "edges": [], "findings": []}), view="ESTATE")
    assert empty["nodes"] == [] and empty["layout"]["positions"] == {}
    single = system_map(prepared_from({"entities": [form("ONLY", "r/o.xml")], "edges": [], "findings": []}))
    assert single["focus"] == "form:ONLY" and list(single["layout"]["positions"]) == ["form:ONLY"]


def test_same_named_nodes_keep_distinct_positions():
    estate = small_estate()
    estate["entities"].append({"id": "spec:api2", "type": "PACKAGE_SPEC", "name": "API",
                               "module": "other/api.pks", "attributes": {}})
    estate["edges"].append(edge("k2", "CALLS", "trg_open", "spec:api2"))
    result = system_map(prepared_from(estate), view="ESTATE")
    positions = result["layout"]["positions"]
    apis = [n["id"] for n in result["nodes"] if n["name"] == "API"]
    assert len(apis) == 2 and positions[apis[0]] != positions[apis[1]]


def test_bounded_estate_view_ranks_by_observed_attention_and_reports_truncation():
    prepared = prepared_from(high_volume_estate(forms=50, tables=400))
    started = time.perf_counter()
    result = system_map(prepared, view="ESTATE", limit=100, edge_limit=150)
    elapsed = time.perf_counter() - started
    assert len(result["nodes"]) == 100 and len(result["edges"]) <= 150
    assert {"reason": "NODE_LIMIT", "limit": 100, "available": 450} in result["truncation"]
    # The two Forms with the most observed relationships are always in view.
    assert {"form:F000", "form:F001"} <= {n["id"] for n in result["nodes"]}
    assert len(json.dumps(result)) < 250_000
    assert elapsed < 10


def test_graph_is_memoized_and_never_mutated_by_responses():
    prepared = prepared_from(small_estate())
    first = system_map(prepared, focus="form:ORDERS")
    graph = prepared.memo["architecture_graph"]
    snapshot = json.dumps(graph, sort_keys=True, default=dict)
    first["nodes"][0]["name"] = "changed"
    first["edges"][0]["components"].append("changed")
    system_map(prepared, view="ESTATE")
    system_map_node(prepared, "form:ORDERS")
    visual_overview(prepared)
    assert prepared.memo["architecture_graph"] is graph
    assert json.dumps(graph, sort_keys=True, default=dict) == snapshot


def reviewed(states, review_revision):
    blueprint = small_estate()
    for finding, state in zip(blueprint["findings"], states):
        finding["review_state"] = state
    assessment = {"status": "Current", "analysis_revision": "1" * 64, "source_revision": "2" * 64,
                  "review_revision": review_revision, "analyzed_at": "2026-09-21T18:00:00Z",
                  "project_id": "a" * 32, "blueprint": {"evidence": [], **blueprint}}
    return prepare_projection({"id": "a" * 32, "name": "Estate"}, assessment, {"status": "CURRENT"},
                              store_scope="test")


def test_review_decision_changes_overlays_without_changing_the_graph():
    before = system_map(reviewed(["PENDING", "PENDING"], 0), focus="form:ORDERS", depth=2)
    after = system_map(reviewed(["APPROVE", "STALE"], 1), focus="form:ORDERS", depth=2)
    assert [e["id"] for e in before["edges"]] == [e["id"] for e in after["edges"]]
    assert before["layout"] == after["layout"]
    orders = lambda r: next(n for n in r["nodes"] if n["id"] == "form:ORDERS")
    assert orders(before)["review_summary"] == {"total": 2, "decided": 0, "open": 2, "stale": 0,
                                                "deferred": 0}
    assert orders(after)["review_summary"] == {"total": 2, "decided": 1, "open": 1, "stale": 1,
                                               "deferred": 0}


def test_node_detail_is_bounded_and_carries_no_source_text():
    prepared = prepared_from(small_estate())
    detail = system_map_node(prepared, "form:ORDERS")
    assert detail["node"]["id"] == "form:ORDERS" and detail["findings_total"] == 2
    assert detail["relationships"]["outbound"]["WRITES"] == 1
    assert detail["relationships"]["inbound"] == {"OPENS_FORM": 1}
    for finding in detail["findings"]:
        assert set(finding) == {"id", "name", "risk", "recommendation", "intervention", "review_state",
                                "hotspot_ids"}
    for bad in ("", "form:NOPE", None, "x" * 501):
        with pytest.raises(ProjectError):
            system_map_node(prepared, bad)


def test_search_results_carry_the_map_node_they_fold_into():
    prepared = prepared_from(small_estate())
    results = {(r["category"], r["title"]): r for r in search_project(prepared, "a", limit=50)["results"]}
    assert results[("packages", "API")]["map_focus"] == "spec:api"
    results = {(r["category"], r["title"]): r for r in search_project(prepared, "orders", limit=50)["results"]}
    assert results[("tables", "ORDERS_T")]["map_focus"] == "table:ORDERS_T"
    assert results[("forms", "ORDERS")]["action"]["map_focus"] == "form:ORDERS"
    assert results[("findings", "r/orders.xml · TRG_SAVE")]["map_focus"] == "form:ORDERS"


def test_visual_overview_counts_are_observed_and_bounded():
    visual = visual_overview(prepared_from(small_estate()))
    lanes = {lane["lane"]: lane for lane in visual["estate"]}
    assert lanes["APPLICATION"]["count"] == 2 and lanes["SHARED_LOGIC"]["count"] == 1
    assert lanes["DATA"]["count"] == 1 and lanes["INTEGRATION"]["count"] == 1
    assert visual["board"]["boundary"] == BOUNDARY
    assert [stage["id"] for stage in visual["journey"]] == ["UNDERSTAND", "ASSESS", "DECIDE", "DELIVER"]
    text = json.dumps(visual).casefold()
    assert "percent" not in text and "progress" not in text
    for claim in FORBIDDEN_CLAIMS:
        assert claim not in text


def test_engine_derived_rule_candidates_are_candidates_not_observed_structure():
    rule = visual_node(node("r", "Conditional rejection candidate: API.X", "OTHER", "BUSINESS_RULE"),
                       fan_in=1, fan_out=0)
    assert rule["status"] == "CANDIDATE"
    assert rule["presentation_type"] == {"technical": "Business rule candidate",
                                         "executive": "Business rule candidate"}
    # An unknown type is neither promoted to a service nor to a candidate.
    other = visual_node(node("o", "X", "OTHER", "SOMETHING_NEW"), fan_in=0, fan_out=0)
    assert (other["status"], other["lane"]) == ("OBSERVED", "INTEGRATION")
    assert visual_node(node("u", "Y", "UNRESOLVED", "ROUTINE_REFERENCE"), fan_in=1, fan_out=0)["status"] == "UNRESOLVED"


def test_attention_matrix_is_bounded_and_ordered():
    hotspots = [{"module": f"m{i % 20:02}", "hotspot_type": "API_BYPASS_CANDIDATE"} for i in range(60)]
    hotspots += [{"module": "m05", "hotspot_type": "GLOBAL_STATE_COUPLING"}]
    matrix = attention_matrix(hotspots, ["API_BYPASS_CANDIDATE", "GLOBAL_STATE_COUPLING"], {})
    assert matrix["truncated"] is True and matrix["total_modules"] == 20 and len(matrix["rows"]) == 15
    assert matrix["rows"][0] == {"module": "m05", "total": 4, "cells": [3, 1]}


def test_report_svg_is_static_escaped_and_deterministic():
    hostile = "<script>alert(1)</script>\"'&"
    rows = [{"source": hostile, "source_layer": "FORM", "target": "T1", "target_layer": "DATABASE",
             "relationship": "WRITES", "count": 2, "level": "FACT", "hotspot_ids": ["h1"]},
            {"source": "F2", "source_layer": "FORM", "target": "X", "target_layer": "UNRESOLVED",
             "relationship": "READS", "count": 1, "level": "INFERENCE", "hotspot_ids": []}]
    first = report_estate_svg(rows)
    assert first == report_estate_svg(list(reversed(rows)))
    lowered = first.casefold()
    for unsafe in ("<script", "foreignobject", "javascript:", "href=", "onload", "onclick"):
        assert unsafe not in lowered
    # The SVG namespace URI is the only URL, and it is never fetched.
    assert lowered.count("http") == 1
    assert "&lt;script&gt;" in first and "stroke-dasharray" in first
    matrix = report_matrix_svg({"types": [{"id": "A", "label": "<b>"}], "rows": [
        {"module": hostile, "total": 1, "cells": [1]}], "total_modules": 1, "truncated": False})
    assert "<b>" not in matrix and "<script" not in matrix.casefold()


def test_tall_estate_layout_stays_deterministic_for_large_estates():
    nodes = {f"x{i}": node(f"x{i}", f"X{i}", "DATABASE", "TABLE") for i in range(200)}
    nodes.update({f"f{i}": node(f"f{i}", f"F{i}") for i in range(20)})
    edges = [link(f"f{i % 20}", f"x{i}", "WRITES") for i in range(200)]
    assert estate_layout(nodes, edges) == estate_layout(nodes, edges)
    assert len(estate_layout(nodes, edges)["positions"]) == 220
