"""Contract edge cases for Estate Intelligence hotspots.

The journeys in test_estate_intelligence.py start from real XML and PL/SQL. The
cases here pin boundaries that are awkward to author as source files. Every
structure below uses the exact producer shapes of blueprint._Builder: signal
codes carried as ``[CODE]`` statement prefixes, ``SUBPROGRAM_BODY`` writers,
symbolic references resolved through ``resolved_target``, and unit attributes
``source_text``/``bind_references``/``inputs``.
"""

from __future__ import annotations

import math
import random

from formslang.hotspots import (
    HOTSPOT_API_BYPASS,
    detect_estate_hotspots,
    hotspot_id,
    signal_codes,
)
from formslang.project_projection import overview, prepare_projection

GUARDED = ("select state into v from t where id = p for update; "
           "update t set state = 'X' where id = p; "
           "if sql%rowcount = 0 then raise_application_error(-20001, 'missing'); end if;")


def finding(entity, *codes, target=""):
    return {"id": entity, "entity": entity, "recommendation": "MANUAL_REVIEW",
            "suggested_target": target, "execution_verdict": "MANUAL",
            "evidence": [f"evidence:{entity}"],
            "statements": [{"level": "INFERENCE", "text": "Plain prose mentions [NOT_A_CODE] late."},
                           *({"level": "INFERENCE", "text": f"[{c}] engine statement"} for c in codes)]}


def bypass_blueprint(*, resolved=True, writer_table="table:ledger"):
    return {
        "entities": [
            {"id": "form:entry", "type": "FORM", "name": "ENTRY", "module": "r/entry.xml", "attributes": {}},
            {"id": "trigger:save", "type": "TRIGGER", "name": "WHEN-BUTTON-PRESSED", "module": "r/entry.xml",
             "attributes": {"owner": "B.SAVE", "source_text": "update ledger set state = 'X';",
                            "bind_references": [], "inputs": []}},
            {"id": "ref:ledger", "type": "TABLE_OR_VIEW_REFERENCE", "name": "LEDGER", "module": "",
             "attributes": {},
             **({"resolution": "RESOLVED_TO_DATABASE_OBJECT", "resolved_target": "table:ledger"}
                if resolved else {})},
            {"id": "table:ledger", "type": "TABLE", "name": "LEDGER", "module": "db/a.sql", "attributes": {}},
            {"id": "table:ledger_other", "type": "TABLE", "name": "LEDGER", "module": "db/b.sql",
             "attributes": {}},
            {"id": "ref:ledger_db", "type": "TABLE_OR_VIEW_REFERENCE", "name": "LEDGER", "module": "",
             "attributes": {}, "resolution": "RESOLVED_TO_DATABASE_OBJECT", "resolved_target": writer_table},
            {"id": "sub:api.touch", "type": "SUBPROGRAM_BODY", "name": "API.TOUCH", "module": "db/api.pkb",
             "attributes": {"package": "API", "source_text": GUARDED}},
        ],
        "edges": [
            {"id": "e1", "type": "WRITES", "source": "trigger:save", "target": "ref:ledger", "evidence": ["x"]},
            {"id": "e2", "type": "WRITES", "source": "sub:api.touch", "target": "ref:ledger_db", "evidence": ["y"]},
        ],
        "findings": [finding("trigger:save", "DIRECT_DML_BYPASSES_API", target="API.TOUCH")],
        "evidence": [],
    }


def test_signal_codes_read_only_the_canonical_prefix():
    assert signal_codes(finding("t", "DIRECT_DML_BYPASSES_API")) == {"DIRECT_DML_BYPASSES_API"}
    assert signal_codes({"code": "DIRECT_DML_BYPASSES_API", "statements": []}) == frozenset()
    assert signal_codes({"statements": [{"text": "[lower] no"}, {"text": " [SPACED] no"}]}) == frozenset()


def test_resolved_co_writer_with_guards_is_a_high_candidate():
    result = detect_estate_hotspots(bypass_blueprint())
    (hotspot,) = result["hotspots"]
    assert hotspot["hotspot_type"] == HOTSPOT_API_BYPASS and hotspot["severity"] == "HIGH"
    assert hotspot["evidence"]["potential_existing_api_owners"] == ["API.TOUCH"]
    assert hotspot["id"] == hotspot_id(HOTSPOT_API_BYPASS, "trigger:save", "table:ledger")


def test_unresolved_reference_is_never_promoted_to_a_bypass():
    assert detect_estate_hotspots(bypass_blueprint(resolved=False))["total"] == 0


def test_same_named_table_in_another_source_is_not_the_same_table():
    assert detect_estate_hotspots(bypass_blueprint(writer_table="table:ledger_other"))["total"] == 0


def test_signal_without_structural_co_writer_produces_nothing():
    blueprint = bypass_blueprint()
    blueprint["edges"] = [e for e in blueprint["edges"] if e["id"] != "e2"]
    assert detect_estate_hotspots(blueprint)["total"] == 0


def global_blueprint(modules):
    entities, edges = [], []
    entities.append({"id": "g:x", "type": "GLOBAL_REFERENCE", "name": "GLOBAL.X", "module": "",
                     "attributes": {}})
    for index, (module, writes) in enumerate(modules):
        unit = f"trigger:{index}"
        entities.append({"id": unit, "type": "TRIGGER", "name": "T", "module": module, "attributes": {
            "owner": "B", "bind_references": ["GLOBAL.X"], "inputs": [] if writes else ["GLOBAL.X"]}})
        edges.append({"id": f"e{index}", "type": "REFERENCES", "source": unit, "target": "g:x"})
    return {"entities": entities, "edges": edges, "findings": [], "evidence": []}


def test_global_state_needs_two_modules_and_grades_observed_cross_flow():
    assert detect_estate_hotspots(global_blueprint([("r/a.xml", True), ("r/a.xml", False)]))["total"] == 0
    shared = detect_estate_hotspots(global_blueprint([("r/a.xml", False), ("r/b.xml", False)]))
    assert shared["hotspots"][0]["severity"] == "MEDIUM"
    flow = detect_estate_hotspots(global_blueprint([("r/a.xml", True), ("r/b.xml", False)]))
    assert flow["hotspots"][0]["severity"] == "HIGH"
    assert flow["hotspots"][0]["evidence"]["observed_writers"] == ["r/a.xml"]


def test_duplicated_rule_severity_depends_on_module_spread():
    one = {"entities": [
        {"id": "t1", "type": "TRIGGER", "name": "A", "module": "r/a.xml", "attributes": {}},
        {"id": "t2", "type": "TRIGGER", "name": "B", "module": "r/a.xml", "attributes": {}},
        {"id": "sub", "type": "SUBPROGRAM_BODY", "name": "API.F", "module": "db/api.pkb", "attributes": {}}],
        "edges": [], "evidence": [],
        "findings": [finding("t1", "LOGIC_DUPLICATED_FORMULA", target="API.F"),
                     finding("t2", "LOGIC_DUPLICATED_QUERY", target="API.F")]}
    (hotspot,) = detect_estate_hotspots(one)["hotspots"]
    assert hotspot["severity"] == "MEDIUM"
    assert hotspot["evidence"]["match_kinds"] == ["LOGIC_DUPLICATED_FORMULA", "LOGIC_DUPLICATED_QUERY"]
    one["entities"][1]["module"] = "r/b.xml"
    assert detect_estate_hotspots(one)["hotspots"][0]["severity"] == "HIGH"


def test_output_is_independent_of_input_order():
    blueprint = bypass_blueprint()
    baseline = detect_estate_hotspots(blueprint)
    for seed in range(5):
        shuffled = {key: list(value) if isinstance(value, list) else value for key, value in blueprint.items()}
        for key in ("entities", "edges", "findings"):
            random.Random(seed).shuffle(shuffled[key])
        assert detect_estate_hotspots(shuffled) == baseline


def test_start_here_explains_priority_from_engine_signals():
    blueprint = bypass_blueprint()
    blueprint["entities"][1]["attributes"]["risk"] = {"level": "CRITICAL"}
    for index in range(3):
        blueprint["entities"].append({"id": f"pu{index}", "type": "PROGRAM_UNIT", "name": f"P{index}",
                                      "module": "r/entry.xml", "attributes": {}})
        blueprint["edges"].append({"id": f"c{index}", "type": "CALLS", "source": f"pu{index}",
                                   "target": "trigger:save"})
    assessment = {"status": "Current", "analysis_revision": "a" * 64, "source_revision": "b" * 64,
                  "review_revision": 0, "analyzed_at": "2026-09-21T12:00:00Z", "blueprint": blueprint}
    prepared = prepare_projection({"id": "p" * 32, "name": "Estate"}, assessment, {"status": "CURRENT"},
                                  store_scope="test")
    (top,) = overview(prepared)["priority"]["start_here"]
    fan_in = 1 + 3  # log2(1 + three callers)
    assert top["signals"] == ("DIRECT_DML_BYPASSES_API",)
    assert top["hotspot_ids"] and "HOTSPOT_CANDIDATE" in top["factors"]
    assert "API_BYPASS" in top["factors"]
    expected = round(100.0 * (1.0 + 0.2 * math.log2(fan_in) + 0.30 + 0.25), 1)
    assert top["score"] == expected
    assert any(line.startswith("Measured risk: CRITICAL") for line in top["breakdown"])
