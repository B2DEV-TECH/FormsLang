"""The project view, and the one number on it that could be mistaken for a verdict.

The readiness score is arithmetic over rows a person can go and check. These
tests pin the arithmetic, and pin the promise around it: nothing is excluded
to make the number look better, and the formula that produced it travels
with it.
"""

from __future__ import annotations

import json

import pytest

from formslang import behavior as behavior_mod
from formslang import dashboard, rules, testspec
from formslang import risk as risk_mod
from formslang.analysis import analyze_task
from formslang.convert import build_tasks
from formslang.parser import parse_xml
from formslang.store import APPROVED, NEEDS_WORK, PENDING, REJECTED, Store


@pytest.fixture()
def store(tmp_path, sample_xml):
    s = Store(tmp_path / "s.db")
    s.init_session("DEMO_ORDER", str(sample_xml))
    s.add_tasks(build_tasks(parse_xml(sample_xml)))
    yield s
    s.close()


def analysed(store: Store) -> Store:
    """The state a real session is in: every unit measured by the rules."""
    for task_id in store.task_ids():
        store.save_analysis(analyze_task(store.get_task(task_id)))
    return store


def specified(store: Store) -> Store:
    for task_id in store.task_ids():
        store.save_test_cases(
            task_id,
            testspec.generate(store.get_task(task_id),
                              analysis=store.get_analysis(task_id)),
        )
    return store


class FakeView:
    """The two fields the readiness maths reads, and nothing else."""

    def __init__(self, state=PENDING, level=None, value=None, proposal=None):
        self.state = state
        self.proposal = proposal
        self.task = {"id": "x", "title": "t", "kind": "trigger", "verdict": "AUTO",
                     "lines": 1}
        self.analysis = None
        if level or value:
            self.analysis = {"risk": {"level": level}, "behavior": {"value": value}}


# -- the formula ----------------------------------------------------------


def test_the_weights_of_the_published_formula_add_up_to_what_it_claims():
    out = dashboard.explain()
    assert out["total_weight"] == sum(c["weight"] for c in out["components"])
    assert out["total_weight"] == 100


def test_every_component_of_the_score_is_published_with_its_own_sentence():
    published = {c["key"] for c in dashboard.explain()["components"]}
    scored = {c["key"] for c in dashboard.readiness([], [])["components"]}
    assert published == scored
    for component in dashboard.explain()["components"]:
        assert component["detail"].strip()
        assert component["title"].strip()


def test_the_formula_says_it_is_not_a_safety_judgement():
    out = dashboard.explain()
    assert "not a judgement that the migration is safe" in out["caveat"]
    assert "No model contributes" in out["caveat"]


def test_an_empty_session_scores_zero_rather_than_dividing_by_it():
    out = dashboard.readiness([], [])
    assert out["score"] == 0.0
    assert out["of"] == 100
    assert all(c["ratio"] == 0.0 for c in out["components"])


def test_a_finished_session_reaches_the_full_hundred():
    views = [FakeView(APPROVED, risk_mod.LOW, behavior_mod.PRESERVED, {"code": "x"})
             for _ in range(4)]
    cases = [{"state": testspec.ACCEPTED} for _ in range(3)]
    assert dashboard.readiness(views, cases)["score"] == 100.0


def test_an_unmeasured_unit_lowers_the_score_instead_of_leaving_the_totals():
    """Excluding it would make the least finished session look the best."""
    measured = [FakeView(APPROVED, risk_mod.LOW, behavior_mod.PRESERVED)]
    unmeasured = [*measured, FakeView(APPROVED)]
    a = {c["key"]: c["ratio"] for c in dashboard.readiness(measured, [])["components"]}
    b = {c["key"]: c["ratio"] for c in dashboard.readiness(unmeasured, [])["components"]}
    assert b["risk_clear"] < a["risk_clear"]
    assert b["behavior_settled"] < a["behavior_settled"]
    assert b["approved"] == a["approved"] == 1.0  # both units are still approved


def test_a_critical_unit_carries_more_weight_than_a_medium_one():
    def clear(level):
        views = [FakeView(PENDING, level, behavior_mod.PRESERVED)]
        parts = {c["key"]: c["ratio"] for c in dashboard.readiness(views, [])["components"]}
        return parts["risk_clear"]

    assert clear(risk_mod.LOW) > clear(risk_mod.MEDIUM) > clear(risk_mod.HIGH) > clear(
        risk_mod.CRITICAL
    )
    assert clear(risk_mod.CRITICAL) == 0.0


def test_a_described_difference_counts_for_half_and_an_open_one_for_nothing():
    def settled(value):
        views = [FakeView(PENDING, risk_mod.LOW, value)]
        parts = {c["key"]: c["ratio"] for c in dashboard.readiness(views, [])["components"]}
        return parts["behavior_settled"]

    assert settled(behavior_mod.PRESERVED) == 1.0
    assert settled(behavior_mod.CHANGED) == 0.5
    assert settled(behavior_mod.UNCERTAIN) == 0.0


def test_rejecting_a_unit_counts_as_reviewed_but_never_as_approved():
    views = [FakeView(REJECTED, risk_mod.LOW, behavior_mod.PRESERVED),
             FakeView(NEEDS_WORK, risk_mod.LOW, behavior_mod.PRESERVED)]
    parts = {c["key"]: c["ratio"] for c in dashboard.readiness(views, [])["components"]}
    assert parts["reviewed"] == 1.0
    assert parts["approved"] == 0.0


def test_an_answered_case_counts_whatever_the_answer_was():
    views = [FakeView(PENDING, risk_mod.LOW, behavior_mod.PRESERVED)]
    cases = [{"state": testspec.ACCEPTED}, {"state": testspec.REJECTED},
             {"state": testspec.NEEDS_WORK}, {"state": testspec.PENDING}]
    parts = {c["key"]: c["ratio"] for c in dashboard.readiness(views, cases)["components"]}
    assert parts["tests_reviewed"] == 0.75


def test_the_score_is_the_sum_of_its_own_published_parts():
    views = [FakeView(APPROVED, risk_mod.HIGH, behavior_mod.CHANGED),
             FakeView(PENDING, risk_mod.MEDIUM, behavior_mod.PRESERVED)]
    out = dashboard.readiness(views, [{"state": testspec.ACCEPTED}])
    assert out["score"] == pytest.approx(sum(c["points"] for c in out["components"]), abs=0.2)


def test_the_same_session_scores_the_same_twice(store):
    specified(analysed(store))
    first = dashboard.build(store)["readiness"]["score"]
    assert dashboard.build(store)["readiness"]["score"] == first


# -- the page around the number -------------------------------------------


def test_the_dashboard_counts_every_unit_under_a_conversion_mode(store):
    out = dashboard.build(store)
    assert out["totals"]["units"] == len(store.task_ids())
    assert sum(out["conversion_modes"].values()) == out["totals"]["units"]
    assert set(out["conversion_modes"]) >= set(rules.VERDICT_ORDER)


def test_decisions_and_their_percentages_describe_the_same_session(store):
    analysed(store)
    ids = store.task_ids()
    store.set_decision(ids[0], APPROVED, code="x", reviewer="geraldo")
    store.set_decision(ids[1], REJECTED, reviewer="geraldo")
    out = dashboard.build(store)
    total = out["totals"]["units"]
    assert out["decisions"][APPROVED] == 1
    assert out["decisions"][REJECTED] == 1
    assert out["decisions"][PENDING] == total - 2
    assert out["percent"]["approved"] == round(100 / total, 1)
    assert out["percent"]["reviewed"] == round(200 / total, 1)


def test_the_distributions_come_from_the_rules_not_from_a_model(store):
    analysed(store)
    out = dashboard.build(store)
    assert sum(out["risk"].values()) == out["coverage"]["analysed"]
    assert sum(out["behavior"].values()) == out["coverage"]["analysed"]
    assert set(out["risk"]) == set(risk_mod.RISK_LEVELS)
    assert set(out["behavior"]) == set(behavior_mod.BEHAVIORS)


def test_the_page_says_how_much_of_the_session_it_actually_measured(store):
    """A distribution over half the units must not read as a whole-session fact."""
    ids = store.task_ids()
    store.save_analysis(analyze_task(store.get_task(ids[0])))
    out = dashboard.build(store)
    assert out["coverage"]["analysed"] == 1
    assert out["coverage"]["missing"] == len(ids) - 1
    assert sum(out["risk"].values()) == 1


def test_the_riskiest_units_lead_and_the_list_stays_short(store):
    analysed(store)
    rows = dashboard.build(store)["highest_risk"]
    assert rows
    assert [r["score"] for r in rows] == sorted((r["score"] for r in rows), reverse=True)
    assert len(rows) <= dashboard._HOT_UNITS
    for row in rows:
        assert row["level"] in risk_mod.RISK_LEVELS
        assert row["task_id"] and row["title"]


def test_an_unsupported_construct_is_reported_with_the_units_that_call_it(store):
    analysed(store)
    rows = {r["name"]: r for r in dashboard.build(store)["unsupported"]}
    assert "HOST" in rows, "the sample form calls HOST"
    assert rows["HOST"]["count"] >= 1
    assert rows["HOST"]["units"], "a count with no unit names is a statistic, not work"
    assert all(r["apex"].strip() for r in rows.values()), "say what to do instead"


def test_the_most_frequent_unsupported_construct_comes_first(store):
    analysed(store)
    rows = dashboard.build(store)["unsupported"]
    assert [r["count"] for r in rows] == sorted((r["count"] for r in rows), reverse=True)


def test_dependency_complexity_names_what_the_form_leans_on(store, sample_xml):
    from formslang.depgraph import build as build_graph

    module = parse_xml(sample_xml)
    task_ids = {f"{t.kind}|{t.owner}|{t.name}".upper(): t.id for t in build_tasks(module)}
    graph = build_graph(module, task_ids=task_ids)
    out = dashboard.build(store, graph)["dependencies"]
    assert out["available"] is True
    assert out["nodes"] > 0 and out["edges"] > 0
    assert out["hubs"], "something in this form is depended on"
    for hub in out["hubs"]:
        assert hub["degree"] == hub["in"] + hub["out"]


def test_without_a_graph_the_page_says_so_instead_of_showing_zeroes(store):
    out = dashboard.build(store)["dependencies"]
    assert out["available"] is False and out["reason"]


# -- blockers --------------------------------------------------------------


def test_a_fresh_session_lists_what_is_missing_rather_than_scoring_it_away(store):
    kinds = {b["kind"] for b in dashboard.build(store)["blockers"]}
    assert "unanalysed" in kinds
    assert "unproposed" in kinds
    assert "unreviewed" in kinds


def test_an_unsupported_construct_is_a_blocker_and_names_itself(store):
    analysed(store)
    blockers = {b["kind"]: b for b in dashboard.build(store)["blockers"]}
    assert "unsupported" in blockers
    assert "HOST" in blockers["unsupported"]["detail"]
    assert blockers["unsupported"]["count"] >= 1


def test_unanswered_test_cases_are_a_blocker_until_somebody_answers_them(store):
    specified(analysed(store))
    blockers = {b["kind"]: b for b in dashboard.build(store)["blockers"]}
    assert blockers["unanswered_tests"]["count"] == store.test_coverage()["total"]

    for row in store.all_test_cases():
        store.decide_test_case(row["id"], testspec.ACCEPTED, "geraldo")
    kinds = {b["kind"] for b in dashboard.build(store)["blockers"]}
    assert "unanswered_tests" not in kinds


def test_every_blocker_carries_a_count_and_something_to_do(store):
    for blocker in dashboard.build(analysed(store))["blockers"]:
        assert blocker["count"] > 0
        assert blocker["detail"].strip()


# -- the route -------------------------------------------------------------


def test_the_dashboard_is_served_with_the_formula_beside_the_score(tmp_path, sample_xml):
    import threading
    import urllib.request
    from http.server import ThreadingHTTPServer

    from formslang.ai import EchoProvider
    from formslang.workbench import Handler, Workbench

    store = Store(tmp_path / "s.db")
    store.init_session("DEMO_ORDER", str(sample_xml))
    store.add_tasks(build_tasks(parse_xml(sample_xml)))
    wb = Workbench(store, EchoProvider(), tmp_path / "export")
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), type("B", (Handler,), {"workbench": wb}))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{httpd.server_port}/api/dashboard", timeout=10
        ) as r:
            out = json.loads(r.read())
    finally:
        httpd.shutdown()
        httpd.server_close()
        store.close()

    assert out["totals"]["units"] > 0
    assert 0 <= out["readiness"]["score"] <= 100
    assert out["readiness_model"]["components"], "the score travels with its formula"
    assert out["readiness_model"]["version"] == dashboard.READINESS_VERSION
    assert out["dependencies"]["available"] is True
    assert out["test_coverage"]["specified"] == out["totals"]["units"]
