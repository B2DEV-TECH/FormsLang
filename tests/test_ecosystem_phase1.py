"""FormsLang 2.3 phase 1: what the 2.2 engine records for the ecosystem contract.

These are characterization tests. They pin the facts ``ecosystem/1`` may use
today and the gaps it must not paper over (docs/design/ecosystem-explorer-2.3/).
A test named ``test_gap_*`` asserts a limitation of the current engine; when a
later phase closes that gap on purpose, the test is expected to change with it,
together with the committed inventory.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from examples.verify import ecosystem_inventory as inv
from examples.verify.project_corporate_scale import blueprint_counts, write_fixture
from formslang import blueprint, database, hotspots
from formslang.parser import parse_xml

REPO = Path(__file__).resolve().parents[1]
GOLDEN = REPO / "docs/design/ecosystem-explorer-2.3/inventory-2.2.json"


def build(name):
    spec = inv.CORPORA[name]
    forms = inv._paths(spec["forms"], suffixes={".xml"})
    db = inv._paths(spec["database"], suffixes=inv.DATABASE_SUFFIXES,
                    exclude_parts=spec.get("exclude_database_parts", ()))
    modules = [parse_xml(p) for p in forms]
    bp = blueprint.build(modules, title=name, source_keys=[p.name for p in forms],
                         database_sources=database.parse_database_sources(db) if db else None)
    return modules, bp


@pytest.fixture(scope="module")
def showcase():
    return build("showcase")


@pytest.fixture(scope="module")
def lab():
    return build("modernization_lab")


@pytest.fixture(scope="module")
def case_c():
    return build("case_c")


@pytest.fixture(scope="module")
def screens():
    return build("visual_hierarchy")


def by_id(bp):
    return {e["id"]: e for e in bp["entities"]}


def out(bp, entity_id):
    names = by_id(bp)
    return [(e["type"], e["level"], names[e["target"]]["type"], names[e["target"]]["name"])
            for e in bp["edges"] if e["source"] == entity_id]


def trigger(bp, module, owner, name="WHEN-BUTTON-PRESSED"):
    return next(e for e in bp["entities"] if e["type"] == "TRIGGER" and e["module"] == module
                and e["name"] == name and e["attributes"].get("owner", "") == owner)


# ---------------------------------------------------------------------------
# Committed inventory
# ---------------------------------------------------------------------------

def test_inventory_is_deterministic_and_matches_the_committed_baseline():
    first = inv.render(inv.inventory())
    assert first == inv.render(inv.inventory())
    assert "\\\\" not in first and ":/" not in first  # no absolute or Windows paths leak in
    assert first == GOLDEN.read_text(encoding="utf-8"), (
        "Regenerate with: python examples/verify/ecosystem_inventory.py --output "
        "docs/design/ecosystem-explorer-2.3/inventory-2.2.json, then review the diff")


# ---------------------------------------------------------------------------
# Case A: DEMO_ALL_ELEMENTS / POST-COMMIT
# ---------------------------------------------------------------------------

def test_case_a_post_commit_edges_are_the_ones_the_source_supports(showcase):
    _, bp = showcase
    unit = trigger(bp, "module.xml", "", "POST-COMMIT")
    assert "PKG_UTIL.P_MSG" in unit["attributes"]["source_text"]
    edges = [e for e in out(bp, unit["id"]) if e[0] != "INVOKES_BUILTIN"]
    assert ("USES_PROGRAM_UNIT", "FACT", "PROGRAM_UNIT", "P_CALC_TOTAL_ITENS") in edges
    assert ("CALLS", "FACT", "ROUTINE_REFERENCE", "PKG_UTIL.P_MSG") in edges
    ref = next(e for e in bp["entities"] if e["type"] == "ROUTINE_REFERENCE" and e["name"] == "PKG_UTIL.P_MSG")
    assert ref["attributes"]["resolution"] == "SYMBOLIC_REFERENCE"
    assert "resolved_target" not in ref


def test_gap_case_a_qualified_call_to_local_package_stays_symbolic(showcase):
    _, bp = showcase
    # PKG_UTIL is a program unit of this very form, yet PKG_UTIL.P_MSG is not linked to it.
    assert any(e["type"] == "PROGRAM_UNIT" and e["name"] == "PKG_UTIL" for e in bp["entities"])
    unit = trigger(bp, "module.xml", "", "POST-COMMIT")
    assert not [e for e in out(bp, unit["id"]) if e[3] == "PKG_UTIL"]


def test_gap_case_a_function_call_inside_an_expression_has_no_edge(showcase):
    _, bp = showcase
    unit = trigger(bp, "module.xml", "", "POST-COMMIT")
    assert "PKG_UTIL.F_USUARIO" in unit["attributes"]["source_text"]
    assert not [e for e in out(bp, unit["id"]) if "F_USUARIO" in e[3]]


def test_gap_case_a_risk_factor_calls_a_resolved_local_call_unresolved(showcase):
    _, bp = showcase
    unit = trigger(bp, "module.xml", "", "POST-COMMIT")
    titles = {f["title"] for f in unit["attributes"]["risk"]["factors"]}
    assert "Unresolved local calls" in titles
    assert ("USES_PROGRAM_UNIT", "FACT", "PROGRAM_UNIT", "P_CALC_TOTAL_ITENS") in out(bp, unit["id"])


# ---------------------------------------------------------------------------
# Case B: modernization lab, APPROVALS
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("owner", ["BK_APPROVAL.BT_APPROVE", "BK_APPROVAL.BT_REJECT"])
def test_case_b_trigger_writes_both_tables_and_never_calls_the_api(lab, owner):
    _, bp = lab
    names = by_id(bp)
    unit = trigger(bp, "APPROVALS.xml", owner)
    edges = [e for e in bp["edges"] if e["source"] == unit["id"]]
    writes = [names[e["target"]] for e in edges if e["type"] == "WRITES"]
    assert sorted(w["name"] for w in writes) == ["LOM_APPROVALS", "LOM_ORDERS"]
    for write in writes:
        # The bridge to the database object is an attribute of the reference, not an edge.
        assert write["type"] == "TABLE_OR_VIEW_REFERENCE"
        assert write["resolution"] == "RESOLVED_TO_DATABASE_OBJECT"
        assert names[write["resolved_target"]]["type"] == "TABLE"
    calls = {names[e["target"]]["name"] for e in edges if e["type"] == "CALLS"}
    assert calls == {"OM_SHARED.SHOW_MESSAGE"}
    assert not any(n.startswith(("LOM_ORDER_API", "LOM_APPROVAL_API")) for n in calls)
    # The link to the API exists only as an interpretive inference.
    interpretive = [(e["type"], e["level"], names[e["target"]]["name"]) for e in edges
                    if names[e["target"]]["name"].startswith("LOM_ORDER_API")]
    assert interpretive == [("DUPLICATES_LOGIC", "INFERENCE", "LOM_ORDER_API.TRANSITION_STATUS")]


def test_case_b_bypass_candidates_are_candidates_with_their_caveat(lab):
    _, bp = lab
    found = hotspots.detect_api_bypass_candidates(bp)
    pairs = sorted((by_id(bp)[h["entity_id"]]["attributes"]["owner"], h["evidence"]["table"]) for h in found)
    assert pairs == [("BK_APPROVAL.BT_APPROVE", "LOM_APPROVALS"), ("BK_APPROVAL.BT_APPROVE", "LOM_ORDERS"),
                     ("BK_APPROVAL.BT_REJECT", "LOM_APPROVALS"), ("BK_APPROVAL.BT_REJECT", "LOM_ORDERS")]
    for h in found:
        assert h["classification"] == "CANDIDATE"
        assert h["evidence"]["unit_calls_co_writer"] is False
        assert any("does not prove which one is the authoritative owner" in u for u in h["uncertainty"])


def test_case_b_update_right_after_then_is_recorded_as_a_write(lab):
    # G-DML, closed in plsql-evidence/2: this UPDATE follows THEN inside an IF.
    modules, bp = lab
    approvals = next(m for m in modules if m.name == "APPROVALS")
    for owner, button in (("BK_APPROVAL.BT_APPROVE", "BT_APPROVE"), ("BK_APPROVAL.BT_REJECT", "BT_REJECT")):
        text = next(t.text for b in approvals.blocks for i in b.items for t in i.triggers if i.name == button)
        assert "THEN\n    UPDATE lom_approvals" in text
        unit = trigger(bp, "APPROVALS.xml", owner)
        written = [e[3] for e in out(bp, unit["id"]) if e[0] == "WRITES"]
        assert sorted(written) == ["LOM_APPROVALS", "LOM_ORDERS"]


# ---------------------------------------------------------------------------
# Case C: two SUBMIT routines in different schemas and one call without schema
# ---------------------------------------------------------------------------

def test_case_c_three_call_sites_keep_three_symbol_identities(case_c):
    _, bp = case_c
    names = by_id(bp)
    targets = {}
    for owner in ("CTL.BT_SALES", "CTL.BT_BILLING", "CTL.BT_UNQUALIFIED"):
        unit = trigger(bp, "SUBMIT_DESK.xml", owner)
        [call] = [e for e in bp["edges"] if e["source"] == unit["id"] and e["type"] == "CALLS"]
        assert call["level"] == "FACT"
        targets[owner] = names[call["target"]]
    assert {t["name"] for t in targets.values()} == {
        "SALES_OWNER.ORDER_API.SUBMIT", "BILLING_OWNER.ORDER_API.SUBMIT", "ORDER_API.SUBMIT"}
    assert len({t["id"] for t in targets.values()}) == 3
    for owner in ("CTL.BT_SALES", "CTL.BT_BILLING"):
        assert "resolved_target" not in targets[owner]


def test_gap_case_c_same_named_packages_in_two_schemas_collapse_into_one(case_c):
    _, bp = case_c
    specs = [e for e in bp["entities"] if e["type"] == "PACKAGE_SPEC"]
    assert [e["name"] for e in specs] == ["ORDER_API"]  # the schema is dropped; one file wins
    # The bodies collapse the same way: only the last file's SUBMIT, and its write, survive.
    [sub] = [e for e in bp["entities"] if e["type"] == "SUBPROGRAM_BODY"]
    assert Path(sub["module"]).name == "sales_order_api.pkb"
    assert [e[3] for e in out(bp, sub["id"]) if e[0] == "WRITES"] == ["SALES_OWNER.SALES_ORDERS"]
    # The call without schema is resolved to that survivor, with no ambiguity recorded.
    ref = next(e for e in bp["entities"] if e["type"] == "ROUTINE_REFERENCE" and e["name"] == "ORDER_API.SUBMIT")
    assert ref["resolution"] == "RESOLVED_TO_DATABASE_OBJECT"


def test_case_c_legacy_resolution_of_the_unqualified_call_is_never_presented_as_resolved():
    # Contract §5.1: 2.2 resolved ORDER_API.SUBMIT to the one package that survived the
    # schema collapse. The explorer shows it as a legacy resolution whose schema collision
    # cannot be checked, not as a confirmed link, until a schema-aware re-analysis.
    calls = inv.inventory()["corpora"]["case_c"]["case"]["calls"]
    [unqualified] = calls["CTL.BT_UNQUALIFIED"]
    assert unqualified["resolution"] == "RESOLVED_TO_DATABASE_OBJECT"  # what 2.2 saved
    assert unqualified["explorer_resolution"] == {
        "resolution": "LEGACY_RESOLVED", "caveat": "SCHEMA_COLLISION_NOT_VERIFIABLE"}
    for owner in ("CTL.BT_SALES", "CTL.BT_BILLING"):
        [call] = calls[owner]
        assert call["explorer_resolution"] == {"resolution": "UNRESOLVED"}


def test_no_2_2_database_resolution_is_presented_as_resolved():
    # Tables are keyed by bare name too (G-SCHEMA-COLLIDE), so the rule covers every
    # database reference a 2.1/2.2 engine resolved, e.g. Case B's LOM_ORDERS writes.
    data = json.loads(GOLDEN.read_text(encoding="utf-8"))
    seen = []

    def walk(node):
        if isinstance(node, dict):
            if "explorer_resolution" in node:
                seen.append((node["resolution"], node["explorer_resolution"]["resolution"]))
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(data)
    assert ("RESOLVED_TO_DATABASE_OBJECT", "LEGACY_RESOLVED") in seen
    assert all(explorer != "RESOLVED" for _, explorer in seen)
    assert all(explorer == "LEGACY_RESOLVED" for raw, explorer in seen if raw == "RESOLVED_TO_DATABASE_OBJECT")


def test_legacy_rule_lifts_only_for_a_schema_aware_engine_and_only_for_database_targets():
    assert inv.explorer_resolution("ROUTINE_REFERENCE", "RESOLVED_TO_DATABASE_OBJECT",
                                   schema_aware=True) == {"resolution": "RESOLVED"}
    assert inv.explorer_resolution("TABLE_OR_VIEW_REFERENCE", "RESOLVED_TO_DATABASE_OBJECT",
                                   schema_aware=False)["resolution"] == "LEGACY_RESOLVED"
    assert inv.explorer_resolution("FORM_REFERENCE", "SYMBOLIC_REFERENCE", schema_aware=False) is None


@pytest.mark.parametrize("header", [
    "CREATE OR REPLACE PACKAGE BODY P AS",
    "CREATE OR REPLACE PACKAGE BODY S.P AS",
    "create package body s.p is",
])
def test_schema_qualified_package_body_keeps_its_subprograms(header):
    # G-SCHEMA-BODY, closed: the body start was found by looking two tokens back
    # for BODY, which is "." when the name carries its schema.
    body = database.parse_package_body(
        f"{header} PROCEDURE X IS BEGIN NULL; END X; "
        "FUNCTION Y RETURN NUMBER IS BEGIN RETURN 1; END Y; END P;")
    assert body.name == "P"
    assert [(s.name, s.subprogram_type) for s in body.subprograms] == [("X", "PROCEDURE"), ("Y", "FUNCTION")]


def test_case_c_schema_qualified_package_bodies_yield_their_subprograms(case_c):
    _, bp = case_c
    # A saved 2.2 assessment lacks these facts, so it must read as an older engine.
    # blueprint-analysis/2 introduced them; any later engine keeps them.
    assert int(bp["engine_version"].split("+")[0].rsplit("/", 1)[1]) >= 2
    [body] = [e for e in bp["entities"] if e["type"] == "PACKAGE_BODY"]
    [sub] = [e for e in bp["entities"] if e["type"] == "SUBPROGRAM_BODY"]
    assert sub["name"] == "ORDER_API.SUBMIT"
    assert {"source": body["id"], "target": sub["id"], "type": "IMPLEMENTS"}.items() <= next(
        e for e in bp["edges"] if e["source"] == body["id"] and e["target"] == sub["id"]).items()
    edges = out(bp, sub["id"])
    assert ("IMPLEMENTS", "PACKAGE_SUBPROGRAM", "ORDER_API.SUBMIT") in [(e[0], e[2], e[3]) for e in edges]
    assert [e[0] for e in edges if e[0] == "WRITES"] == ["WRITES"]


# ---------------------------------------------------------------------------
# Visual hierarchy: positive and negative declarations
# ---------------------------------------------------------------------------

def test_parser_carries_the_visual_hierarchy_the_blueprint_drops(screens):
    modules, bp = screens
    main = next(m for m in modules if m.name == "SCREENS")
    canvas = {c.name: c for c in main.canvases}
    assert canvas["CV_TABS"].tab_pages == ["TAB_ONE", "TAB_TWO"]
    assert canvas["CV_HIDDEN"].visible is False
    assert main.window_details["WIN_SIDE"].primary_canvas == "CV_SHARED"
    assert canvas["CV_SHARED"].window_name == "WIN_MAIN"
    # The Blueprint keeps the nodes but none of those attributes, and no TAB_PAGE node.
    for entity in bp["entities"]:
        if entity["type"] in {"CANVAS", "WINDOW"}:
            assert entity["attributes"] == {}
    assert not [e for e in bp["entities"] if e["type"] == "TAB_PAGE"]
    types = {e["id"]: e["type"] for e in bp["entities"]}
    visual = {(types[e["source"]], e["type"], types[e["target"]]) for e in bp["edges"]
              if {types[e["source"]], types[e["target"]]} & {"CANVAS", "WINDOW"}}
    assert visual == {("FORM", "CONTAINS", "CANVAS"), ("FORM", "CONTAINS", "WINDOW"),
                      ("ITEM", "REFERENCES", "CANVAS")}


def test_gap_visible_true_and_content_cannot_be_told_from_parser_defaults(screens):
    modules, _ = screens
    canvas = {c.name: c for c in next(m for m in modules if m.name == "SCREENS").canvases}
    declared, defaulted = canvas["CV_VISIBLE_DECLARED"], canvas["CV_DEFAULTS"]
    assert (declared.visible, declared.canvas_type) == (defaulted.visible, defaulted.canvas_type) == (True, "Content")
    # Only the raw source tells them apart; the inventory reads it for that reason.
    parsed = inv.measure_corpus("visual_hierarchy", inv.CORPORA["visual_hierarchy"])
    rows = {c["name"]: c for c in parsed["parser_visual"]["SCREENS"]["canvases"]}
    assert rows["CV_VISIBLE_DECLARED"]["visible_origin"] == "DECLARED"
    assert rows["CV_DEFAULTS"]["visible_origin"] == "PARSER_DEFAULT"
    assert rows["CV_DEFAULTS"]["canvas_type_origin"] == "PARSER_DEFAULT"
    assert rows["CV_HIDDEN"] | {} == {**rows["CV_HIDDEN"], "visible": False, "visible_origin": "DECLARED"}


def test_inventory_reports_conflicts_and_unplaced_items_without_choosing(screens):
    parsed = inv.measure_corpus("visual_hierarchy", inv.CORPORA["visual_hierarchy"])["parser_visual"]["SCREENS"]
    assert parsed["window_canvas_conflicts"] == [
        {"window": "WIN_SIDE", "primary_canvas": "CV_SHARED", "canvas_window_name": "WIN_MAIN"}]
    assert parsed["canvases_with_undeclared_window"] == ["CV_ORPHAN"]
    assert parsed["items"]["without_canvas"] == ["CTL.NO_CANVAS"]
    assert parsed["items"]["canvas_not_declared"] == [{"item": "CTL.GHOST", "canvas": "CV_NOT_DECLARED"}]
    assert parsed["items"]["tab_page_not_declared_on_canvas"] == [
        {"item": "BK_SPLIT.LOST_TAB_FIELD", "canvas": "CV_TABS", "tab_page": "TAB_UNDECLARED"}]
    # Canvases as the items name them, declared or not.
    assert parsed["blocks_across_canvases"] == {
        "BK_SPLIT": ["CV_MAIN", "CV_TABS"], "CTL": ["CV_HIDDEN", "CV_MAIN", "CV_NOT_DECLARED", "CV_SHARED"]}


def test_gap_item_on_undeclared_canvas_leaves_no_trace_in_the_blueprint(screens):
    _, bp = screens
    names = by_id(bp)
    for qualified in ("CTL.GHOST", "CTL.NO_CANVAS"):
        item = next(e for e in bp["entities"] if e["type"] == "ITEM" and e["name"] == qualified)
        assert not [e for e in bp["edges"] if e["source"] == item["id"] and names[e["target"]]["type"] == "CANVAS"]
    assert not [e for e in bp["entities"] if e["name"] == "CV_NOT_DECLARED"]


def test_item_references_canvas_is_proved_by_canvas_name_and_shares_its_type(screens):
    _, bp = screens
    names = by_id(bp)
    evidence = {e["id"]: e for e in bp["evidence"]}
    placements = [e for e in bp["edges"] if e["type"] == "REFERENCES" and names[e["target"]]["type"] == "CANVAS"]
    assert placements and all(names[e["source"]]["type"] == "ITEM" for e in placements)
    for edge in placements:
        assert evidence[edge["evidence"][0]]["text"].startswith("CanvasName: ")
    # The same raw type also carries data/bind references, so the projection must type it.
    others = {names[e["target"]]["type"] for e in bp["edges"] if e["type"] == "REFERENCES"} - {"CANVAS"}
    assert "ITEM" in others


def test_navigation_frontiers_literal_missing_dynamic_and_cycle(screens):
    _, bp = screens
    names = by_id(bp)
    opens = sorted((names[e["source"]]["attributes"]["owner"], names[e["source"]]["module"],
                    names[e["target"]]["type"], names[e["target"]]["name"])
                   for e in bp["edges"] if e["type"] == "OPENS_FORM")
    assert opens == [
        ("CTL.BT_BACK", "SCREENS_PEER.xml", "FORM", "SCREENS"),
        ("CTL.BT_MISSING", "SCREENS.xml", "FORM_REFERENCE", "NOT_SUPPLIED"),
        ("CTL.BT_PEER", "SCREENS.xml", "FORM", "SCREENS_PEER"),
    ]
    missing = next(e for e in bp["entities"] if e["type"] == "FORM_REFERENCE")
    assert missing["attributes"]["resolution"] == "SYMBOLIC_REFERENCE"
    dynamic = trigger(bp, "SCREENS.xml", "CTL.BT_DYNAMIC")
    assert not [e for e in bp["edges"] if e["source"] == dynamic["id"] and e["type"] == "OPENS_FORM"]
    finding = next(f for f in bp["findings"] if f["entity"] == dynamic["id"])
    assert "Runtime target unresolved: OPEN_FORM" in finding["unresolved_questions"]


def test_gap_dynamic_sql_is_a_risk_factor_not_a_graph_frontier(screens):
    _, bp = screens
    unit = trigger(bp, "SCREENS.xml", "CTL.BT_DDL")
    assert "dynamic_sql" in {f["id"] for f in unit["attributes"]["risk"]["factors"]}
    kinds = {e[0] for e in out(bp, unit["id"])}
    assert kinds == {"INVOKES_BUILTIN", "REFERENCES"}


# ---------------------------------------------------------------------------
# Scale generator
# ---------------------------------------------------------------------------

def test_scale_ecosystem_profile_declares_hierarchy_navigation_and_missing_sources(tmp_path):
    write_fixture(tmp_path, 30, "ecosystem")
    paths = sorted((tmp_path / "sources/forms").glob("*.xml"))
    modules = [parse_xml(p) for p in paths]
    sample = modules[25]
    assert [c.name for c in sample.canvases] == ["CV_MAIN", "CV_TABS", "CV_HIDDEN", "CV_POPUP"]
    assert next(c for c in sample.canvases if c.name == "CV_HIDDEN").visible is False
    assert next(c for c in sample.canvases if c.name == "CV_TABS").tab_pages == ["TAB_A", "TAB_B", "TAB_C"]
    bp = blueprint.build(modules, title="scale", source_keys=[p.name for p in paths],
                         database_sources=database.parse_database_sources([tmp_path / "sources/database/scale.sql"]))
    counts = blueprint_counts(bp)
    assert counts["windows"] == 2 * 29 and counts["canvases"] == 4 * 29
    assert counts["opens_form"] == 29 + 1  # one literal peer per module, one CALL_FORM to a missing form
    assert counts["form_references"] == 1
    assert any(e["type"] == "ROUTINE_REFERENCE" and e["name"].startswith("LEGACY_API.") for e in bp["entities"])
    assert json.dumps(counts)  # plain, serialisable counts for result.json


def test_scale_baseline_profile_is_unchanged(tmp_path):
    write_fixture(tmp_path, 3)
    text = (tmp_path / "sources/forms/module_0001.xml").read_text(encoding="utf-8")
    assert "<Canvas" not in text and text.count("WHEN-VALIDATE-ITEM") == 12
