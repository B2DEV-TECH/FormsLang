"""The dependency graph: what breaks if this unit changes.

The graph is only worth having if it is honest, so most of what is pinned
here is honesty rather than coverage: every edge carries evidence, a name
built at runtime produces no edge at all, and a reference to something the
module does not contain is kept and marked rather than quietly dropped.
"""

from __future__ import annotations

import json

import pytest

from formslang import depgraph
from formslang.convert import build_tasks
from formslang.depgraph import (
    BLOCK,
    CONTAINS,
    DepGraph,
    Edge,
    Node,
    node_id,
)
from formslang.model import Block, FormModule, ProgramUnit, Relation, Trigger
from formslang.parser import parse_xml
from formslang.store import Store


@pytest.fixture()
def module(sample_xml):
    return parse_xml(sample_xml)


@pytest.fixture()
def tasks(module):
    return build_tasks(module)


@pytest.fixture()
def graph(module, tasks):
    """The sample form, with the queue and one risk level wired in."""
    ids = {f"{t.kind}|{t.owner}|{t.name}".upper(): t.id for t in tasks}
    risks = {tasks[0].id: "HIGH"}
    return depgraph.build(module, task_ids=ids, risks=risks)


def edge_kinds(graph, src, dst):
    return {e.kind for e in graph.outbound(src) if e.dst == dst}


def reached(walk):
    return {row["id"] for row in walk}


def unit(name, text, owner="", scope="form"):
    return Trigger(name=name, text=text, scope=scope, owner=owner)


# -- structure -----------------------------------------------------------


def test_structure_is_graphed_before_a_line_of_code_is_read(graph):
    """Containment comes from the parsed module, not from the PL/SQL."""
    form = node_id("module", "DEMO_ORDER")
    block = node_id("block", "ORDERS")
    assert edge_kinds(graph, form, block) == {CONTAINS}
    assert edge_kinds(graph, block, node_id("item", "ORDERS.ORDER_ID")) == {CONTAINS}


def test_a_database_block_depends_on_the_table_behind_it(graph):
    block = node_id("block", "ORDERS")
    table = node_id("table", "ORDERS")
    found = [e for e in graph.outbound(block) if e.dst == table]
    assert [e.kind for e in found] == ["queries"]
    assert found[0].evidence == "block data source"
    assert graph.node(table).external is True


def test_the_lov_chain_reaches_the_table_nobody_mentions(graph):
    """Item -> LOV -> record group -> table, which is three hops of silence."""
    item = node_id("item", "ORDERS.CUSTOMER")
    assert node_id("table", "CUSTOMERS") not in reached(graph.depends_on(item, depth=2))
    assert node_id("table", "CUSTOMERS") in reached(graph.depends_on(item, depth=3))


def test_a_relation_points_at_its_detail_block_with_the_join_as_evidence():
    module = FormModule(
        name="F", blocks=[Block(name="MASTER"), Block(name="DETAIL")],
        relations=[Relation(name="R1", detail_block="DETAIL",
                            join_condition="MASTER.ID = DETAIL.MASTER_ID")],
    )
    graph = depgraph.build(module)
    found = graph.outbound(node_id("relation", "R1"))
    assert [(e.dst, e.kind, e.evidence) for e in found] == [
        (node_id("block", "DETAIL"), "relates", "MASTER.ID = DETAIL.MASTER_ID")
    ]
    assert graph.node(node_id("block", "DETAIL")).missing is False


def test_a_relation_to_a_block_this_form_lacks_is_marked_missing():
    module = FormModule(
        name="F", blocks=[Block(name="MASTER")],
        relations=[Relation(name="R1", detail_block="ELSEWHERE")],
    )
    graph = depgraph.build(module)
    assert graph.node(node_id("block", "ELSEWHERE")).missing is True


# -- evidence ------------------------------------------------------------


def test_every_edge_that_is_not_containment_carries_its_evidence(graph):
    """An edge you cannot trace back to the source is an opinion."""
    unsupported = [e for e in graph.edges if e.kind != CONTAINS and not e.evidence]
    assert unsupported == []


def test_a_literal_argument_becomes_an_edge_quoting_the_call(graph):
    found = [e for e in graph.outbound(node_id("trigger", "WHEN-NEW-FORM-INSTANCE"))
             if e.dst == node_id("block", "ORDERS")]
    assert [(e.kind, e.evidence) for e in found] == [("navigates", "GO_BLOCK('ORDERS')")]


def test_a_name_built_at_runtime_produces_no_edge_and_is_reported_instead():
    """GO_BLOCK(v_name) is a dependency we cannot name, and we say so."""
    module = FormModule(
        name="F", blocks=[Block(name="ORDERS")],
        triggers=[unit("WHEN-NEW-FORM-INSTANCE",
                       "BEGIN\n  GO_BLOCK(v_target);\nEND;")],
    )
    graph = depgraph.build(module)
    trigger = graph.node(node_id("trigger", "WHEN-NEW-FORM-INSTANCE"))
    assert trigger.unresolved_targets == ["GO_BLOCK"]
    assert [e for e in graph.outbound(trigger.id) if e.kind == "navigates"] == []
    assert graph.summary()["unresolved"] == 1


def test_a_resolved_target_is_not_reported_as_unresolved(graph):
    trigger = graph.node(node_id("trigger", "WHEN-NEW-FORM-INSTANCE"))
    assert trigger.unresolved_targets == []


# -- missing and external ------------------------------------------------


def test_a_reference_to_something_the_module_lacks_is_kept_and_marked(graph):
    """PRE-INSERT writes :ORDERS.CREATED, and no such item is declared."""
    created = graph.node(node_id("item", "ORDERS.CREATED"))
    assert created.missing is True
    assert node_id("trigger", "ORDERS.PRE-INSERT") in {
        e.src for e in graph.inbound(created.id)
    }


def test_a_declared_item_is_never_marked_missing(graph):
    assert graph.node(node_id("item", "ORDERS.CUSTOMER")).missing is False


@pytest.mark.parametrize("kind,name", [
    ("global", "GLOBAL.DIR"),
    ("library", "DEMO_LIB"),
    ("table", "CUSTOMERS"),
    ("external", "PRINT.BAT"),
])
def test_objects_outside_this_form_are_marked_external(graph, kind, name):
    assert graph.node(node_id(kind, name)).external is True


def test_a_qualified_call_becomes_a_package_and_a_bare_one_a_missing_procedure():
    module = FormModule(
        name="F",
        triggers=[unit("WHEN-NEW-FORM-INSTANCE",
                       "BEGIN\n  ord_api.recalc(1);\n  do_something(2);\nEND;")],
    )
    graph = depgraph.build(module)
    package = graph.node(node_id("package", "ORD_API"))
    procedure = graph.node(node_id("procedure", "DO_SOMETHING"))
    assert (package.external, package.missing) == (True, False)
    assert procedure.missing is True


def test_a_call_to_a_program_unit_in_this_form_is_not_reported_as_missing():
    module = FormModule(
        name="F",
        program_units=[ProgramUnit(name="P_TOTAL", kind="Procedure",
                                   text="PROCEDURE P_TOTAL IS BEGIN NULL; END;")],
        triggers=[unit("WHEN-NEW-FORM-INSTANCE", "BEGIN\n  P_TOTAL(1);\nEND;")],
    )
    graph = depgraph.build(module)
    target = node_id("program_unit", "P_TOTAL")
    assert node_id("procedure", "P_TOTAL") not in graph.nodes
    assert edge_kinds(graph, node_id("trigger", "WHEN-NEW-FORM-INSTANCE"), target) == {"calls"}


def test_static_sql_names_its_tables_and_dynamic_sql_does_not():
    """A lexical reader cannot see through EXECUTE IMMEDIATE, and does not try."""
    module = FormModule(
        name="F",
        triggers=[
            unit("A", "BEGIN\n  UPDATE order_lines SET qty = 1;\nEND;"),
            unit("B", "BEGIN\n  EXECUTE IMMEDIATE 'DELETE FROM secret_table';\nEND;"),
        ],
    )
    graph = depgraph.build(module)
    assert node_id("table", "ORDER_LINES") in graph.nodes
    assert node_id("table", "SECRET_TABLE") not in graph.nodes


# -- walks ---------------------------------------------------------------

def test_impact_answers_what_breaks_if_this_changes(graph):
    """Everything pointing at the table, one hop out and then two."""
    table = node_id("table", "ORDERS")
    direct = graph.impact(table, depth=1)
    assert reached(direct) == {node_id("block", "ORDERS")}
    assert direct[0]["depth"] == 1
    assert node_id("module", "DEMO_ORDER") in reached(graph.impact(table, depth=2))


def test_depends_on_and_impact_look_opposite_ways(graph):
    block = node_id("block", "ORDERS")
    assert node_id("table", "ORDERS") in reached(graph.depends_on(block, depth=1))
    assert node_id("table", "ORDERS") not in reached(graph.impact(block, depth=1))
    assert node_id("module", "DEMO_ORDER") in reached(graph.impact(block, depth=1))


def test_a_walk_reports_the_edge_it_travelled(graph):
    row = next(r for r in graph.depends_on(node_id("block", "ORDERS"), depth=1)
               if r["id"] == node_id("table", "ORDERS"))
    assert row["via"] == "queries"
    assert row["via_label"] == "queries"
    assert row["evidence"] == "block data source"
    assert row["external"] is True


def test_depth_is_clamped_so_an_explorer_never_becomes_a_wall_of_text(graph):
    form = node_id("module", "DEMO_ORDER")
    assert graph.depends_on(form, depth=99) == graph.depends_on(form, depth=depgraph.MAX_DEPTH)
    assert graph.depends_on(form, depth=0) == graph.depends_on(form, depth=1)


def test_a_walk_never_visits_a_node_twice(graph):
    walk = graph.depends_on(node_id("module", "DEMO_ORDER"), depth=depgraph.MAX_DEPTH)
    ids = [row["id"] for row in walk]
    assert len(ids) == len(set(ids))


def test_a_cycle_terminates():
    module = FormModule(
        name="F", blocks=[Block(name="A"), Block(name="B")],
        triggers=[
            unit("T1", "BEGIN GO_BLOCK('B'); END;"),
            unit("T2", "BEGIN GO_BLOCK('A'); END;"),
        ],
    )
    graph = depgraph.build(module)
    graph.add_edge(node_id("block", "A"), node_id("block", "B"), "navigates", "manual")
    graph.add_edge(node_id("block", "B"), node_id("block", "A"), "navigates", "manual")
    walk = graph.depends_on(node_id("block", "A"), depth=depgraph.MAX_DEPTH)
    assert node_id("block", "A") not in reached(walk)


def test_walking_from_a_node_that_does_not_exist_is_empty_not_an_error(graph):
    assert graph.depends_on("block:NOWHERE") == []
    assert graph.explore("block:NOWHERE") == {}


# -- the queue's view ----------------------------------------------------


def test_a_task_finds_its_node_and_its_neighbourhood(graph, tasks):
    task = next(t for t in tasks if t.name == "WHEN-NEW-FORM-INSTANCE")
    out = graph.for_task(task.id, depth=1)
    assert out["node"]["id"] == node_id("trigger", "WHEN-NEW-FORM-INSTANCE")
    assert out["label"] == "Trigger"
    assert out["direct_out"] == 1
    assert node_id("block", "ORDERS") in reached(out["depends_on"])


def test_a_task_the_graph_has_never_heard_of_returns_nothing(graph):
    assert graph.for_task("deadbeef") == {}


def test_the_risk_level_of_a_task_is_stamped_on_its_node(graph, tasks):
    assert graph.node(node_id("trigger", "WHEN-NEW-FORM-INSTANCE")).risk == "HIGH"
    assert graph.node(node_id("trigger", "KEY-CLRFRM")).risk == ""


# -- assembly ------------------------------------------------------------


def test_the_same_edge_stated_twice_is_stored_once():
    graph = DepGraph("F")
    graph.add_node(Node("a", BLOCK, "A"))
    graph.add_node(Node("b", BLOCK, "B"))
    graph.add_edge("a", "b", "navigates", "GO_BLOCK('B')")
    graph.add_edge("a", "b", "navigates", "GO_BLOCK('B')")
    assert len(graph.edges) == 1
    graph.add_edge("a", "b", "navigates", "NEXT_BLOCK")
    assert len(graph.edges) == 2


def test_an_edge_to_a_node_nobody_declared_is_refused():
    graph = DepGraph("F")
    graph.add_node(Node("a", BLOCK, "A"))
    graph.add_edge("a", "ghost", "navigates", "x")
    graph.add_edge("a", "a", CONTAINS, "self")
    assert graph.edges == []


def test_finding_the_real_object_clears_missing_but_losing_it_never_sets_it():
    """Structure and code discover the same node from opposite directions."""
    graph = DepGraph("F")
    graph.add_node(Node("item:ORDERS.QTY", "item", "ORDERS.QTY", missing=True))
    graph.add_node(Node("item:ORDERS.QTY", "item", "ORDERS.QTY", owner="ORDERS"))
    node = graph.node("item:ORDERS.QTY")
    assert node.missing is False
    assert node.owner == "ORDERS"
    graph.add_node(Node("item:ORDERS.QTY", "item", "ORDERS.QTY", missing=True))
    assert graph.node("item:ORDERS.QTY").missing is False


def test_enriching_a_node_accumulates_facts_without_losing_any():
    graph = DepGraph("F")
    graph.add_node(Node("t", "trigger", "T", unresolved_targets=["GO_BLOCK"]))
    graph.add_node(Node("t", "trigger", "T", task_id="abc", risk="HIGH",
                        unresolved_targets=["GO_BLOCK", "SHOW_LOV"], attrs={"lines": 4}))
    node = graph.node("t")
    assert (node.task_id, node.risk) == ("abc", "HIGH")
    assert node.unresolved_targets == ["GO_BLOCK", "SHOW_LOV"]
    assert node.attrs["lines"] == 4


# -- rollup --------------------------------------------------------------


def test_the_summary_counts_what_a_reviewer_would_otherwise_count_by_hand(graph):
    summary = graph.summary()
    assert summary["module"] == "DEMO_ORDER"
    assert summary["version"] == depgraph.VERSION
    assert summary["nodes"] == len(graph.nodes)
    assert summary["edges"] == len(graph.edges)
    assert summary["missing"] == 1
    assert summary["by_kind"]["block"] == 1
    assert sum(summary["by_kind"].values()) == summary["nodes"]


def test_the_hubs_are_the_nodes_the_form_leans_on(graph):
    hubs = graph.summary()["hubs"]
    assert hubs, "a form with 26 edges has hubs"
    assert all(h["in"] > 0 for h in hubs)
    assert all(h["kind"] != "module" for h in hubs), "the form contains everything"
    assert [h["in"] for h in hubs] == sorted((h["in"] for h in hubs), reverse=True)


# -- persistence ---------------------------------------------------------


def test_a_graph_survives_json(graph):
    revived = DepGraph.from_dict(json.loads(json.dumps(graph.to_dict())))
    assert revived.summary() == graph.summary()
    block = node_id("block", "ORDERS")
    assert revived.depends_on(block, depth=2) == graph.depends_on(block, depth=2)
    assert revived.impact(block, depth=2) == graph.impact(block, depth=2)


def test_a_graph_read_back_from_nothing_is_empty_not_broken():
    empty = DepGraph.from_dict({})
    assert empty.nodes == {} and empty.edges == []
    assert empty.summary()["nodes"] == 0


def test_a_node_and_an_edge_round_trip_field_by_field():
    node = Node("item:A.B", "item", "A.B", owner="A", task_id="t1", external=False,
                missing=True, risk="CRITICAL", unresolved_targets=["GO_BLOCK"],
                attrs={"lines": 9})
    assert Node.from_dict(node.to_dict()) == node
    edge = Edge("a", "b", "calls", "P_TOTAL(...)", "t1")
    assert Edge.from_dict(edge.to_dict()) == edge


def test_the_graph_is_stored_beside_the_module_and_reopens_with_it(tmp_path, sample_xml, graph):
    store = Store(tmp_path / "s.db")
    store.init_session("DEMO_ORDER", str(sample_xml))
    store.save_module_meta("DEMO_ORDER", {"assessment": "kept"})
    store.save_graph("DEMO_ORDER", graph)
    store.close()

    reopened = Store(tmp_path / "s.db")
    try:
        revived = reopened.graph("DEMO_ORDER")
        assert revived is not None
        assert revived.summary() == graph.summary()
        meta = reopened.module_meta("DEMO_ORDER")
        assert meta["assessment"] == "kept", "saving a graph must not erase the assessment"
        assert meta["graph_summary"]["nodes"] == len(graph.nodes)
        assert reopened.graph("SOME_OTHER_FORM") is None
    finally:
        reopened.close()
