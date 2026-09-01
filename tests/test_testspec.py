"""Test specifications: what they claim, where they claim it from, and what
survives a rules change.

The rule under test throughout is the one the module was written for: a case
comes from the *original* Forms body, and it says which of the three origins
it stands on. A case that quietly presented a guess as a Forms fact would be
worse than no case at all.
"""

from __future__ import annotations

import json

import pytest

from formslang import rules, testspec
from formslang.analysis import ENGINE_VERSION, analyze_task
from formslang.convert import ConversionTask, build_tasks
from formslang.parser import parse_xml
from formslang.store import Store
from formslang.testspec import (
    ACCEPTED,
    BOUNDARY,
    EXCEPTION,
    FROM_FORMS,
    FROM_MIGRATION,
    NEEDS_CONFIRMATION,
    NEEDS_WORK,
    NORMAL,
    NULLS,
    PENDING,
    REGRESSION,
    REJECTED,
    SIDE_EFFECT,
    TRANSACTION,
)
from formslang.testspec import (
    TestCase as Case,
)


def task(source: str, *, kind: str = "trigger", name: str = "WHEN-BUTTON-PRESSED",
         owner: str = "ORDERS", task_id: str = "t1") -> ConversionTask:
    """A conversion task built by hand, so each test states its own input."""
    return ConversionTask(
        id=task_id, module="DEMO", kind=kind, name=name, owner=owner,
        verdict="ASSISTED", apex_hint="", source=source,
        lines=len(source.splitlines()),
    )


def by_kind(cases: list[Case]) -> dict[str, list[Case]]:
    out: dict[str, list[Case]] = {}
    for case in cases:
        out.setdefault(case.kind, []).append(case)
    return out


class FakeItem:
    """Just the item properties the generator reads."""

    def __init__(self, required=False, max_length=None, data_type=""):
        self.required = required
        self.max_length = max_length
        self.data_type = data_type


# -- every unit gets at least a normal path ------------------------------


def test_a_unit_with_no_findings_still_gets_its_normal_path():
    cases = testspec.generate(task("BEGIN NULL; END;"))
    assert [c.kind for c in cases] == [NORMAL]
    assert cases[0].origin == FROM_FORMS


def test_the_when_of_a_trigger_is_its_firing_point_not_its_name():
    cases = testspec.generate(task("BEGIN NULL; END;", name="WHEN-NEW-FORM-INSTANCE"))
    assert cases[0].when == ["the form is opened"]


def test_a_program_unit_is_exercised_by_being_called():
    cases = testspec.generate(
        task("BEGIN NULL; END;", kind="program_unit", name="P_TOTAL", owner="")
    )
    assert cases[0].when == ["P_TOTAL is called"]


def test_every_case_carries_the_evidence_that_produced_it():
    body = """
    BEGIN
      INSERT INTO ORDERS (ID) VALUES (:ORDERS.ID);
      HOST('print.bat');
      :GLOBAL.LAST := 'x';
    EXCEPTION WHEN OTHERS THEN NULL;
    END;
    """
    unit = task(body, name="PRE-INSERT")
    cases = testspec.generate(unit, analysis=analyze_task(unit))
    assert len(cases) > 4
    for case in cases:
        assert case.evidence, f"{case.title} claims something with no evidence"
        assert case.when and case.then


def test_a_case_only_ever_carries_one_of_the_three_declared_origins():
    body = "BEGIN HOST('x'); COMMIT_FORM; :GLOBAL.A := 1; END;"
    unit = task(body, name="PRE-COMMIT")
    for case in testspec.generate(unit, analysis=analyze_task(unit)):
        assert case.origin in testspec.ORIGINS
        assert case.kind in testspec.KINDS
        assert case.origin_label == testspec.ORIGIN_LABEL[case.origin]


# -- firing points --------------------------------------------------------


@pytest.mark.parametrize(
    "name,expected",
    [
        ("KEY-DUPREC", "the user presses the key mapped to KEY-DUPREC on ORDERS"),
        ("PRE-SELECT", "Forms reaches the PRE-SELECT point on ORDERS"),
        ("POST-CHANGE", "Forms has passed the POST-CHANGE point on ORDERS"),
        ("ON-COUNT", "Forms would perform the action ON-COUNT replaces on ORDERS"),
        ("WHEN-BANANA-SPLIT", "the WHEN-BANANA-SPLIT trigger point is reached on ORDERS"),
    ],
)
def test_an_unlisted_trigger_falls_back_to_the_shape_of_its_name(name, expected):
    """Better a sentence derived from the prefix than an invented firing rule."""
    assert testspec.fires_when("trigger", name, "ORDERS") == expected


def test_a_listed_trigger_beats_the_prefix_rule():
    assert testspec.fires_when("trigger", "PRE-INSERT", "ORDERS") == (
        "each new row is about to be inserted"
    )


# -- items: what the module metadata does and does not allow -------------


def test_a_required_item_produces_a_null_case_grounded_in_the_form():
    body = "BEGIN :ORDERS.ORDER_ID := 1; END;"
    items = {"ORDERS.ORDER_ID": FakeItem(required=True)}
    cases = by_kind(testspec.generate(task(body), items=items))
    (null_case,) = cases[NULLS]
    assert null_case.origin == FROM_FORMS
    assert "ORDERS.ORDER_ID" in null_case.given[0]
    assert null_case.evidence == ["ORDERS.ORDER_ID is declared Required in the form"]


def test_without_module_metadata_the_same_item_needs_confirmation_not_a_guess():
    body = "BEGIN :ORDERS.ORDER_ID := 1; END;"
    cases = by_kind(testspec.generate(task(body), items=None))
    (null_case,) = cases[NULLS]
    assert null_case.origin == NEEDS_CONFIRMATION
    assert "no Required or Length property was found" in null_case.evidence[0]
    assert BOUNDARY not in cases


def test_a_declared_length_and_a_numeric_type_give_different_boundary_sentences():
    body = "BEGIN :ORDERS.NAME := 'x'; :ORDERS.QTY := 1; END;"
    items = {
        "ORDERS.NAME": FakeItem(max_length=30, data_type="Char"),
        "ORDERS.QTY": FakeItem(data_type="Number"),
    }
    (boundary,) = by_kind(testspec.generate(task(body), items=items))[BOUNDARY]
    assert boundary.origin == FROM_FORMS
    assert "ORDERS.NAME (max 30)" in " ".join(boundary.given)
    assert "numeric items: ORDERS.QTY" in " ".join(boundary.given)
    assert any("at the limit is accepted" in row for row in boundary.then)
    assert any("negative value" in row for row in boundary.then)


def test_forms_own_namespaces_are_not_treated_as_page_items():
    """GLOBAL, PARAMETER and SYSTEM are not items anyone can leave blank."""
    body = "BEGIN :GLOBAL.A := :PARAMETER.B; :ORDERS.C := :SYSTEM.CURSOR_ITEM; END;"
    cases = by_kind(testspec.generate(task(body), items=None))
    (null_case,) = cases[NULLS]
    given = " ".join(null_case.given)
    assert "ORDERS.C" in given
    assert "GLOBAL.A" not in given and "PARAMETER.B" not in given
    assert "SYSTEM.CURSOR_ITEM" not in given


def test_a_long_list_of_items_stops_naming_and_starts_counting():
    refs = [f":ORDERS.C{i} := 1;" for i in range(10)]
    cases = by_kind(testspec.generate(task("BEGIN " + " ".join(refs) + " END;")))
    given = " ".join(cases[NULLS][0].given)
    assert "and 4 more" in given


# -- transaction ----------------------------------------------------------


def test_a_commit_cycle_trigger_gets_a_transaction_case_even_with_a_quiet_body():
    unit = task("BEGIN NULL; END;", name="POST-UPDATE")
    (case,) = by_kind(testspec.generate(unit, analysis=analyze_task(unit)))[TRANSACTION]
    assert case.origin == FROM_MIGRATION
    assert "at POST-UPDATE" in " ".join(case.given)
    assert any("committed once" in row for row in case.then)


def test_an_explicit_commit_is_reported_as_the_unit_driving_the_transaction():
    unit = task("BEGIN COMMIT_FORM; END;", name="WHEN-BUTTON-PRESSED")
    (case,) = by_kind(testspec.generate(unit, analysis=analyze_task(unit)))[TRANSACTION]
    assert "COMMIT_FORM" in " ".join(case.given)
    assert any(row.startswith("COMMIT_FORM x1") for row in case.evidence)


def test_a_unit_outside_the_commit_cycle_that_writes_nothing_gets_no_transaction_case():
    unit = task("BEGIN GO_BLOCK('ORDERS'); END;", name="WHEN-NEW-FORM-INSTANCE")
    assert TRANSACTION not in by_kind(
        testspec.generate(unit, analysis=analyze_task(unit))
    )


# -- side effects ---------------------------------------------------------


def test_the_rows_a_write_touches_are_named_from_its_own_sql():
    body = "BEGIN UPDATE ORDERS SET TOTAL = 0 WHERE ID = 1; END;"
    unit = task(body, name="WHEN-BUTTON-PRESSED")
    cases = by_kind(testspec.generate(unit, analysis=analyze_task(unit)))[SIDE_EFFECT]
    rows = [c for c in cases if c.title == "The same rows are still touched"]
    assert rows and rows[0].origin == FROM_FORMS
    assert "ORDERS" in " ".join(rows[0].given)


def test_a_global_gets_a_case_about_the_move_not_about_forms():
    body = "BEGIN :GLOBAL.DIR := 'C:\\tmp'; END;"
    cases = by_kind(testspec.generate(task(body)))[SIDE_EFFECT]
    (shared,) = [c for c in cases if "Shared state" in c.title]
    assert shared.origin == FROM_MIGRATION
    assert any("does not leak between sessions" in row for row in shared.then)


def test_a_runtime_assembled_statement_is_admitted_as_unreadable():
    body = "BEGIN EXECUTE IMMEDIATE 'DELETE FROM ' || v_name; END;"
    cases = by_kind(testspec.generate(task(body)))[SIDE_EFFECT]
    (dynamic,) = [c for c in cases if "dynamic statement" in c.title]
    assert dynamic.origin == NEEDS_CONFIRMATION
    assert any("a reviewer states which objects" in row for row in dynamic.then)


# -- exceptions -----------------------------------------------------------


def test_an_existing_handler_is_tested_as_forms_behaviour():
    body = "BEGIN INSERT INTO T VALUES (1); EXCEPTION WHEN OTHERS THEN NULL; END;"
    (case,) = by_kind(testspec.generate(task(body)))[EXCEPTION]
    assert case.origin == FROM_FORMS
    assert case.evidence == ["an EXCEPTION section is present in this body"]


def test_no_handler_at_all_is_a_difference_the_migration_introduces():
    body = "BEGIN INSERT INTO T VALUES (1); END;"
    (case,) = by_kind(testspec.generate(task(body)))[EXCEPTION]
    assert case.origin == FROM_MIGRATION
    assert any("FRM-40735" in row for row in case.then)


def test_a_body_that_neither_runs_sql_nor_branches_gets_no_exception_case():
    assert EXCEPTION not in by_kind(testspec.generate(task("BEGIN NULL; END;")))


# -- regression -----------------------------------------------------------


def test_one_regression_case_per_family_not_one_per_call():
    """GO_BLOCK and NEXT_RECORD are the same family; four calls are one case."""
    body = "BEGIN GO_BLOCK('A'); GO_BLOCK('B'); NEXT_RECORD; HOST('x'); END;"
    unit = task(body)
    cases = by_kind(testspec.generate(unit, analysis=analyze_task(unit)))[REGRESSION]
    titles = [c.title for c in cases]
    assert len(titles) == len(set(titles))
    nav = [c for c in cases if "navigation" in c.title.lower()]
    assert len(nav) == 1
    given = " ".join(nav[0].given)
    assert "GO_BLOCK" in given and "NEXT_RECORD" in given
    assert any(row.startswith("GO_BLOCK x2") for row in nav[0].evidence)


def test_a_family_that_maps_straight_across_is_left_out_of_the_grouping():
    """GO_ITEM is a direct equivalent: it does not drag its family into a case."""
    unit = task("BEGIN GO_ITEM('A'); END;")
    assert REGRESSION not in by_kind(
        testspec.generate(unit, analysis=analyze_task(unit))
    )


def test_an_unsupported_builtin_claims_no_apex_equivalent():
    unit = task("BEGIN HOST('print.bat'); END;")
    cases = by_kind(testspec.generate(unit, analysis=analyze_task(unit)))[REGRESSION]
    (host,) = [c for c in cases if "HOST" in " ".join(c.given)]
    assert host.origin == NEEDS_CONFIRMATION
    assert any("a person decides what happens" in row for row in host.then)
    assert any(f"[{rules.UNSUPPORTED}]" in row for row in host.evidence)


def test_a_direct_equivalent_does_not_earn_a_regression_case():
    """MESSAGE maps straight across; a case for it is noise, not coverage."""
    unit = task("BEGIN MESSAGE('hi'); END;")
    cases = by_kind(testspec.generate(unit, analysis=analyze_task(unit)))
    assert REGRESSION not in cases


def test_every_stated_uncertainty_becomes_a_case_a_person_has_to_answer():
    unit = task("BEGIN :GLOBAL.DIR := 'x'; END;", name="PRE-INSERT")
    analysis = analyze_task(unit)
    assert analysis.behavior.uncertainties
    assert len(analysis.behavior.uncertainties) > 1  # two questions, two cases
    cases = by_kind(testspec.generate(unit, analysis=analysis))[REGRESSION]
    unanswered = [c for c in cases if c.origin == NEEDS_CONFIRMATION]
    assert len(unanswered) >= len(analysis.behavior.uncertainties)
    for note in analysis.behavior.uncertainties:
        assert any(note in c.evidence for c in unanswered)


def test_two_open_questions_do_not_collapse_into_one_case():
    """Cases are identified by title, so a shared title would lose one."""
    unit = task("BEGIN :GLOBAL.DIR := 'x'; END;", name="PRE-INSERT")
    analysis = analyze_task(unit)
    cases = by_kind(testspec.generate(unit, analysis=analysis))[REGRESSION]
    open_questions = [c for c in cases if c.title.startswith("Open question:")]
    assert len(open_questions) == len(analysis.behavior.uncertainties)
    assert len({c.id for c in open_questions}) == len(open_questions)
    for case in open_questions:
        assert len(case.title) < 100


# -- identity -------------------------------------------------------------


def test_a_case_keeps_its_id_when_its_wording_does_not_change():
    body = "BEGIN INSERT INTO T VALUES (1); END;"
    first = testspec.generate(task(body))
    again = testspec.generate(task(body))
    assert [c.id for c in first] == [c.id for c in again]


def test_a_different_unit_never_shares_a_case_id():
    body = "BEGIN NULL; END;"
    a = testspec.generate(task(body, task_id="t1"))
    b = testspec.generate(task(body, task_id="t2"))
    assert {c.id for c in a}.isdisjoint({c.id for c in b})


def test_rewording_a_case_makes_it_a_different_case():
    assert testspec.case_id("t1", NORMAL, "A") != testspec.case_id("t1", NORMAL, "B")
    assert testspec.case_id("t1", NORMAL, "A") != testspec.case_id("t1", BOUNDARY, "A")


def test_cases_come_back_in_the_order_a_reviewer_reads_them():
    body = """
    BEGIN
      INSERT INTO ORDERS (ID) VALUES (:ORDERS.ID);
      HOST('x');
    END;
    """
    unit = task(body, name="PRE-INSERT")
    cases = testspec.generate(unit, analysis=analyze_task(unit))
    order = [testspec._KIND_ORDER[c.kind] for c in cases]
    assert order == sorted(order)


def test_a_case_survives_a_json_round_trip_field_for_field():
    case = Case(
        id="abc", task_id="t1", kind=BOUNDARY, origin=FROM_MIGRATION, title="T",
        given=["g"], when=["w"], then=["t"], evidence=["e"],
    )
    back = Case.from_dict(json.loads(json.dumps(case.to_dict())))
    assert back == case
    assert case.to_dict()["kind_label"] == "Boundary"
    assert case.to_dict()["origin_label"] == "Introduced by the migration"


# -- rollup ---------------------------------------------------------------


def test_summarize_counts_by_kind_origin_and_reviewer_state():
    rows = [
        {"kind": NORMAL, "origin": FROM_FORMS, "state": ACCEPTED},
        {"kind": NORMAL, "origin": FROM_FORMS, "state": PENDING},
        {"kind": REGRESSION, "origin": NEEDS_CONFIRMATION, "state": REJECTED,
         "stale": True},
    ]
    out = testspec.summarize(rows)
    assert out["total"] == 3
    assert out["kinds"][NORMAL] == 2
    assert out["origins"][NEEDS_CONFIRMATION] == 1
    assert out["states"][ACCEPTED] == 1 and out["states"][PENDING] == 1
    assert out["reviewed"] == 2
    assert out["stale"] == 1
    assert out["version"] == testspec.VERSION


def test_summarize_of_nothing_is_zeroes_not_an_empty_dict():
    out = testspec.summarize([])
    assert out["total"] == 0
    assert set(out["kinds"]) == set(testspec.KINDS)
    assert set(out["origins"]) == set(testspec.ORIGINS)


def test_summarize_counts_runs_apart_from_review_state():
    rows = [
        {"kind": NORMAL, "origin": FROM_FORMS, "state": ACCEPTED,
         "run_state": testspec.RUN_PASS},
        {"kind": NORMAL, "origin": FROM_FORMS, "state": ACCEPTED,
         "run_state": testspec.RUN_FAIL},
        {"kind": NORMAL, "origin": FROM_FORMS, "state": PENDING},
    ]
    out = testspec.summarize(rows)
    assert out["runs"][testspec.RUN_PASS] == 1
    assert out["runs"][testspec.RUN_FAIL] == 1
    assert out["runs"][testspec.NOT_RUN] == 1
    assert out["executed"] == 2


def test_a_row_with_no_run_state_counts_as_not_run():
    out = testspec.summarize([{"kind": NORMAL, "origin": FROM_FORMS, "state": PENDING}])
    assert out["runs"][testspec.NOT_RUN] == 1
    assert out["executed"] == 0


# -- markdown -------------------------------------------------------------


def test_the_exported_markdown_marks_what_a_reviewer_answered():
    units = [{
        "title": "ORDERS.PRE-INSERT", "kind": "trigger", "risk": "HIGH",
        "behavior": "CHANGED",
        "cases": [
            {"title": "Accepted one", "kind": NORMAL, "kind_label": "Normal path",
             "origin": FROM_FORMS, "given": ["g"], "when": ["w"], "then": ["t"],
             "evidence": ["e"], "state": ACCEPTED, "reviewer": "geraldo",
             "comment": "confirmed"},
            {"title": "Rejected one", "kind": REGRESSION, "origin": FROM_MIGRATION,
             "given": [], "when": ["w"], "then": ["t"], "evidence": [],
             "state": REJECTED, "reviewer": "", "comment": ""},
            {"title": "Needs work one", "kind": NULLS, "origin": NEEDS_CONFIRMATION,
             "given": [], "when": ["w"], "then": ["t"], "evidence": [],
             "state": NEEDS_WORK, "reviewer": "qa", "comment": ""},
            {"title": "Untouched one", "kind": NORMAL, "origin": FROM_FORMS,
             "given": [], "when": ["w"], "then": ["t"], "evidence": [],
             "state": PENDING},
        ],
    }]
    text = testspec.render_markdown("DEMO_ORDER", units)
    assert "# Test specification -- DEMO_ORDER" in text
    assert "[x] Accepted one" in text
    assert "[-] Rejected one" in text
    assert "[!] Needs work one" in text
    assert "[ ] Untouched one" in text
    assert "Accepted by geraldo -- confirmed" in text
    assert "Needs modification by qa" in text
    assert "`trigger | HIGH | CHANGED`" in text
    assert "<details><summary>Evidence</summary>" in text
    assert (
        "**4 case(s)** across 1 unit(s); 3 reviewed, 1 pending; "
        "0 executed, 0 passed, 0 failed." in text
    )


def test_the_markdown_says_nothing_was_executed():
    text = testspec.render_markdown("DEMO", [])
    assert "Nothing here has been executed by FormsLang" in text
    for origin in testspec.ORIGINS:
        assert origin in text


def test_a_unit_with_no_cases_does_not_get_an_empty_heading():
    text = testspec.render_markdown("DEMO", [{"title": "EMPTY", "cases": []}])
    assert "## EMPTY" not in text


def test_the_markdown_shows_what_actually_happened_when_a_case_ran():
    units = [{
        "title": "ORDERS.PRE-INSERT", "cases": [
            {"title": "Ran and passed", "kind": NORMAL, "origin": FROM_FORMS,
             "given": [], "when": ["w"], "then": ["t"], "evidence": [],
             "state": PENDING, "run_state": testspec.RUN_PASS,
             "run_by": "geraldo", "run_notes": "matches prod",
             "run_at": "2026-08-31 10:00:00"},
            {"title": "Never run", "kind": NORMAL, "origin": FROM_FORMS,
             "given": [], "when": ["w"], "then": ["t"], "evidence": [],
             "state": PENDING, "run_state": testspec.NOT_RUN},
        ],
    }]
    text = testspec.render_markdown("DEMO", units)
    assert "· Passed</sub>" in text
    assert "Run: Passed by geraldo (2026-08-31 10:00:00) -- matches prod" in text
    assert "Run: " not in text.split("Never run")[1].split("###")[0]
    assert "0 executed" not in text
    assert "1 executed, 1 passed, 0 failed." in text


# -- the store: a review outlives the rules that produced the case --------


@pytest.fixture()
def store(tmp_path, sample_xml):
    s = Store(tmp_path / "s.db")
    s.init_session("DEMO_ORDER", str(sample_xml))
    s.add_tasks(build_tasks(parse_xml(sample_xml)))
    yield s
    s.close()


def specify(store: Store, module=None) -> str:
    """Generate and save the specification for the first task; return its id."""
    items = testspec.items_of(module) if module is not None else None
    task_id = store.task_ids()[0]
    unit = store.get_task(task_id)
    store.save_test_cases(
        task_id, testspec.generate(unit, analysis=analyze_task(unit), items=items)
    )
    return task_id


def test_a_saved_case_starts_pending_and_says_which_engine_wrote_it(store):
    task_id = specify(store)
    cases = store.test_cases(task_id)
    assert cases
    for case in cases:
        assert case["state"] == PENDING
        assert case["stale"] is False
        assert case["task_id"] == task_id
        assert case["given"] and case["then"]


def test_regenerating_leaves_an_accepted_case_accepted(store):
    task_id = specify(store)
    first = store.test_cases(task_id)[0]
    store.decide_test_case(first["id"], ACCEPTED, "geraldo", "checked against prod")

    out = store.save_test_cases(
        task_id, testspec.generate(store.get_task(task_id),
                                   analysis=store.get_analysis(task_id))
    )
    assert out["kept"] >= 1
    same = {c["id"]: c for c in store.test_cases(task_id)}[first["id"]]
    assert same["state"] == ACCEPTED
    assert same["reviewer"] == "geraldo"
    assert same["comment"] == "checked against prod"
    assert same["decided_at"]


def test_a_case_that_vanishes_is_dropped_only_while_nobody_answered_it(store):
    """A reviewed case is evidence; a rules change must not delete evidence."""
    task_id = specify(store)
    cases = store.test_cases(task_id)
    answered, unanswered = cases[0], cases[-1]
    assert answered["id"] != unanswered["id"]
    store.decide_test_case(answered["id"], REJECTED, "geraldo")

    out = store.save_test_cases(task_id, [])
    assert out["dropped"] == len(cases) - 1
    assert out["orphaned"] == 1
    left = store.test_cases(task_id)
    assert [c["id"] for c in left] == [answered["id"]]
    assert left[0]["state"] == REJECTED


def test_a_case_written_under_older_rules_is_flagged_never_hidden(store):
    task_id = specify(store)
    case_id = store.test_cases(task_id)[0]["id"]
    store.db.execute(
        "UPDATE test_case SET engine_version = 'analysis/0' WHERE id = ?", (case_id,)
    )
    store.db.commit()
    marked = {c["id"]: c for c in store.test_cases(task_id)}[case_id]
    assert marked["stale"] is True
    assert task_id in store.stale_test_task_ids()


def test_a_task_with_no_specification_is_reported_as_needing_one(store):
    assert store.stale_test_task_ids() == store.task_ids()
    task_id = specify(store)
    assert task_id not in store.stale_test_task_ids()


def test_an_unknown_reviewer_state_is_refused_not_stored(store):
    task_id = specify(store)
    case_id = store.test_cases(task_id)[0]["id"]
    assert store.decide_test_case(case_id, "maybe") is False
    assert store.test_cases(task_id)[0]["state"] == PENDING


def test_deciding_a_case_nobody_has_heard_of_reports_failure(store):
    assert store.decide_test_case("nope", ACCEPTED) is False


# -- the store: what actually happened when a case was run -----------------


def test_a_fresh_case_has_never_been_run(store):
    task_id = specify(store)
    case = store.test_cases(task_id)[0]
    assert case["run_state"] == testspec.NOT_RUN
    assert case["run_by"] == "" and case["run_notes"] == "" and case["run_at"] == ""


def test_recording_a_run_is_kept_apart_from_the_reviewer_decision(store):
    task_id = specify(store)
    case_id = store.test_cases(task_id)[0]["id"]
    store.decide_test_case(case_id, ACCEPTED, "geraldo", "looks right")
    assert store.record_test_run(
        case_id, testspec.RUN_PASS, "qa-analyst", "ran against APEX 26.1"
    ) is True
    case = {c["id"]: c for c in store.test_cases(task_id)}[case_id]
    assert case["state"] == ACCEPTED and case["reviewer"] == "geraldo"
    assert case["run_state"] == testspec.RUN_PASS
    assert case["run_by"] == "qa-analyst"
    assert case["run_notes"] == "ran against APEX 26.1"
    assert case["run_at"]


def test_a_case_can_be_run_again_and_the_latest_result_wins(store):
    task_id = specify(store)
    case_id = store.test_cases(task_id)[0]["id"]
    store.record_test_run(case_id, testspec.RUN_FAIL, "qa", "NPE on save")
    store.record_test_run(case_id, testspec.RUN_PASS, "qa", "fixed and re-run")
    case = {c["id"]: c for c in store.test_cases(task_id)}[case_id]
    assert case["run_state"] == testspec.RUN_PASS
    assert case["run_notes"] == "fixed and re-run"


def test_an_unknown_run_state_is_refused_not_stored(store):
    task_id = specify(store)
    case_id = store.test_cases(task_id)[0]["id"]
    assert store.record_test_run(case_id, "kinda-passed") is False
    assert store.test_cases(task_id)[0]["run_state"] == testspec.NOT_RUN


def test_recording_a_run_for_a_case_nobody_has_heard_of_reports_failure(store):
    assert store.record_test_run("nope", testspec.RUN_PASS) is False


def test_regenerating_leaves_a_recorded_run_in_place(store):
    """A rules change must not erase evidence that a case was actually run,
    exactly as it must not erase the reviewer's accept/reject."""
    task_id = specify(store)
    first = store.test_cases(task_id)[0]
    store.record_test_run(first["id"], testspec.RUN_PASS, "qa", "ok")

    store.save_test_cases(
        task_id, testspec.generate(store.get_task(task_id),
                                   analysis=store.get_analysis(task_id))
    )
    same = {c["id"]: c for c in store.test_cases(task_id)}[first["id"]]
    assert same["run_state"] == testspec.RUN_PASS
    assert same["run_by"] == "qa" and same["run_notes"] == "ok"


def test_coverage_reports_how_much_has_actually_been_run(store):
    task_id = specify(store)
    cases = store.test_cases(task_id)
    store.record_test_run(cases[0]["id"], testspec.RUN_PASS)
    store.record_test_run(cases[1]["id"], testspec.RUN_FAIL)
    coverage = store.test_coverage()
    assert coverage["runs"][testspec.RUN_PASS] == 1
    assert coverage["runs"][testspec.RUN_FAIL] == 1
    assert coverage["executed"] == 2


def test_coverage_counts_the_units_that_have_no_specification_at_all(store):
    total = len(store.task_ids())
    task_id = specify(store)
    coverage = store.test_coverage()
    assert coverage["tasks"] == total
    assert coverage["specified"] == 1
    assert coverage["missing"] == total - 1
    assert coverage["total"] == len(store.test_cases(task_id))


def test_all_test_cases_follows_the_order_of_the_queue(store):
    for task_id in store.task_ids():
        unit = store.get_task(task_id)
        store.save_test_cases(task_id, testspec.generate(unit))
    rows = store.all_test_cases()
    seen = []
    for row in rows:
        if row["task_id"] not in seen:
            seen.append(row["task_id"])
    assert seen == [i for i in store.task_ids() if i in seen]


def test_a_corrupt_payload_still_yields_a_readable_row(store):
    """A row that cannot be parsed loses its sentences, not the review."""
    task_id = specify(store)
    case_id = store.test_cases(task_id)[0]["id"]
    store.db.execute("UPDATE test_case SET payload = '{oops' WHERE id = ?", (case_id,))
    store.db.commit()
    row = {c["id"]: c for c in store.test_cases(task_id)}[case_id]
    assert row["title"] and row["state"] == PENDING
    assert row.get("given") is None


# -- the export ------------------------------------------------------------


def test_the_export_writes_a_specification_a_person_can_run(store, tmp_path):
    for task_id in store.task_ids():
        store.save_test_cases(task_id, testspec.generate(store.get_task(task_id)))
    store.export(tmp_path / "out")
    tests_md = tmp_path / "out" / "tests.md"
    assert tests_md.exists()
    text = tests_md.read_text(encoding="utf-8")
    assert "# Test specification -- DEMO_ORDER" in text
    assert "does what it did in Forms" in text


def test_the_specification_covers_units_nobody_approved(store, tmp_path):
    """Exporting only approved units would leave the risky half untested."""
    for task_id in store.task_ids():
        store.save_test_cases(task_id, testspec.generate(store.get_task(task_id)))
    assert store.stats()["approved"] == 0
    store.export(tmp_path / "out")
    text = (tmp_path / "out" / "tests.md").read_text(encoding="utf-8")
    for task_id in store.task_ids():
        assert store.get_task(task_id).title in text


def test_no_specification_means_no_empty_file(store, tmp_path):
    assert store.export_tests(tmp_path / "out") is None
    assert not (tmp_path / "out" / "tests.md").exists()


def test_the_session_record_carries_the_cases_and_the_coverage(store, tmp_path):
    task_id = specify(store)
    store.decide_test_case(store.test_cases(task_id)[0]["id"], ACCEPTED, "geraldo")
    _sql, json_path = store.export(tmp_path / "out")
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["test_coverage"]["specified"] == 1
    unit = next(t for t in data["tasks"] if t["id"] == task_id)
    assert unit["test_cases"]
    assert any(c["state"] == ACCEPTED for c in unit["test_cases"])


def test_the_engine_version_travels_with_the_case(store):
    task_id = specify(store)
    row = store.db.execute(
        "SELECT engine_version, spec_version FROM test_case WHERE task_id = ?",
        (task_id,),
    ).fetchone()
    assert row["engine_version"] == ENGINE_VERSION
    assert row["spec_version"] == testspec.VERSION
