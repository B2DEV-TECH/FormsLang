"""What the model is told, and what it is allowed to change afterwards.

The rule engine runs before the provider. These tests pin the two halves of
that contract: the measured facts reach the prompt, and the answer that comes
back can only make the behaviour classification more conservative.
"""

from __future__ import annotations

import json

import pytest

from formslang import ai, behavior
from formslang.analysis import analyze_task
from formslang.convert import (
    SYSTEM_PROMPT,
    ConversionTask,
    build_prompt,
    parse_proposal,
    propose,
    propose_many,
)
from formslang.store import Store
from formslang.workbench import Workbench

DANGEROUS = """
BEGIN
  GO_BLOCK('ITEMS');
  HOST('print.bat');
  COMMIT_FORM;
END;
"""

ARITHMETIC = """
BEGIN
  :ORDERS.TOTAL := :ORDERS.QTY * :ORDERS.PRICE;
  IF :ORDERS.TOTAL > 1000 THEN
    :ORDERS.DISCOUNT := 0.1;
  END IF;
END;
"""


def task(source: str = DANGEROUS, *, name: str = "WHEN-BUTTON-PRESSED", tid: str = "t1"):
    return ConversionTask(
        id=tid, module="DEMO", kind="trigger", name=name, owner="ORDERS",
        verdict="ASSISTED", apex_hint="dynamic action", source=source,
        lines=source.count("\n"), fingerprint=f"fp-{tid}",
        builtins=[("GO_BLOCK", "ASSISTED", "navigate in the page")],
    )


def user_text(messages) -> str:
    return "\n".join(m.content for m in messages if m.role == "user")


class Scripted(ai.Provider):
    """Records what it was asked and answers with a fixed payload."""

    type_id = "scripted"

    def __init__(self, payload: dict | None = None):
        super().__init__(model="scripted-1")
        self.payload = payload or {"apex_target": "Process", "code": "x;", "confidence": 0.8}
        self.prompts: list[str] = []

    def complete(self, messages, max_tokens=0):
        self.prompts.append(user_text(messages))
        return json.dumps(self.payload)


# -- what reaches the prompt ---------------------------------------------


def test_the_prompt_carries_the_measured_facts_not_a_bare_code_dump():
    text = user_text(build_prompt(task(), analyze_task(task())))
    assert "Deterministic analysis" in text
    assert "Risk: " in text
    assert "Behaviour after migration:" in text


def test_the_prompt_names_the_migration_class_of_each_construct():
    text = user_text(build_prompt(task(), analyze_task(task())))
    assert "UNSUPPORTED" in text, "HOST has no APEX equivalent and the model must know"
    assert "GO_BLOCK" in text and "COMMIT_FORM" in text


def test_a_resolved_target_is_passed_along_and_a_computed_one_is_not():
    resolved = user_text(build_prompt(task(), analyze_task(task())))
    assert "-> ITEMS" in resolved

    computed = task("BEGIN GO_BLOCK('ORD' || :CONTROL.SUFFIX); END;")
    assert "->" not in user_text(build_prompt(computed, analyze_task(computed)))


def test_the_prompt_still_works_without_an_analysis():
    """Older call sites keep the flat built-in list -- nothing breaks."""
    text = user_text(build_prompt(task()))
    assert "Deterministic analysis" not in text
    assert "Forms built-ins used" in text and "GO_BLOCK" in text


def test_the_source_is_always_the_last_thing_the_model_reads():
    text = user_text(build_prompt(task(), analyze_task(task())))
    assert text.index("```plsql") > text.index("Deterministic analysis")


def test_the_system_prompt_tells_the_model_it_may_not_argue_with_the_engine():
    assert "MAY NOT CONTRADICT" in SYSTEM_PROMPT
    assert "measured facts" in SYSTEM_PROMPT
    assert "will be ignored" in SYSTEM_PROMPT


# -- what comes back ------------------------------------------------------


@pytest.mark.parametrize("value", ["PRESERVED", "CHANGED", "UNCERTAIN"])
def test_a_valid_behaviour_answer_is_kept(value):
    p = parse_proposal(json.dumps({"code": "x;", "behavior": value, "behavior_reason": "why"}))
    assert p.behavior == value
    assert p.behavior_reason == "why"


@pytest.mark.parametrize("value", ["probably fine", "", "MOSTLY_PRESERVED", 7])
def test_an_invented_behaviour_answer_is_dropped_not_normalised(value):
    """A word the taxonomy does not contain means the model did not answer."""
    p = parse_proposal(json.dumps({"code": "x;", "behavior": value}))
    assert p.behavior == ""


def test_propose_forwards_the_analysis_to_the_provider():
    provider = Scripted()
    propose(task(), provider, analysis=analyze_task(task()))
    assert "Deterministic analysis" in provider.prompts[0]


def test_propose_many_analyses_every_body_without_being_asked():
    provider = Scripted()
    propose_many([task(), task(ARITHMETIC, name="POST-CHANGE", tid="t2")], provider)
    assert len(provider.prompts) == 2
    assert all("Deterministic analysis" in p for p in provider.prompts)


# -- the merge, in the workbench -----------------------------------------


@pytest.fixture()
def bench(tmp_path, sample_xml):
    def build(source: str, name: str, payload: dict):
        store = Store(tmp_path / f"{name}.db")
        store.init_session("DEMO", str(sample_xml))
        store.add_tasks([task(source, name=name)])
        wb = Workbench(store, Scripted(payload), tmp_path / "export")
        return store, wb

    return build


def test_the_model_may_make_the_behaviour_more_conservative(bench):
    store, wb = bench(ARITHMETIC, "POST-CHANGE", {
        "code": "x;", "confidence": 0.8,
        "behavior": "CHANGED", "behavior_reason": "the item is recalculated on submit",
    })
    try:
        assert store.get_analysis("t1").behavior.value == behavior.PRESERVED
        wb._run_job(["t1"])
        merged = store.get_analysis("t1").behavior
        assert merged.value == behavior.CHANGED
        assert merged.source == "rules+ai"
        assert any("INFERENCE" in r for r in merged.reasons)
    finally:
        store.close()


def test_the_model_may_not_talk_the_behaviour_back_down(bench):
    store, wb = bench(DANGEROUS, "WHEN-BUTTON-PRESSED", {
        "code": "x;", "confidence": 0.9,
        "behavior": "PRESERVED", "behavior_reason": "looks equivalent to me",
    })
    try:
        before = store.get_analysis("t1").behavior
        assert before.value == behavior.CHANGED
        wb._run_job(["t1"])
        after = store.get_analysis("t1").behavior
        assert after.value == behavior.CHANGED
        assert after.source == "rules"
        assert not any("looks equivalent" in r for r in after.reasons)
    finally:
        store.close()


def test_the_second_opinion_is_stored_next_to_the_proposal_not_inside_it(bench):
    store, wb = bench(ARITHMETIC, "POST-CHANGE", {
        "code": "x;", "confidence": 0.8, "behavior": "UNCERTAIN",
        "behavior_reason": "the commit point is not visible from here",
    })
    try:
        wb._run_job(["t1"])
        saved = store.latest_proposal("t1")
        assert saved["behavior"] == "UNCERTAIN"
        assert saved["behavior_reason"].startswith("the commit point")
    finally:
        store.close()


def test_a_silent_model_leaves_the_engine_answer_untouched(bench):
    store, wb = bench(ARITHMETIC, "POST-CHANGE", {"code": "x;", "confidence": 0.8})
    try:
        wb._run_job(["t1"])
        kept = store.get_analysis("t1").behavior
        assert kept.value == behavior.PRESERVED
        assert kept.source == "rules"
    finally:
        store.close()
