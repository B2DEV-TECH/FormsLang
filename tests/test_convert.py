"""Task building, defensive parsing, and converting copy-paste only once."""

from __future__ import annotations

import json

from formslang import ai, rules
from formslang.convert import (
    ConversionTask,
    build_prompt,
    build_tasks,
    parse_proposal,
    propose,
    propose_many,
)
from formslang.parser import parse_xml


def _tasks(sample_xml):
    return build_tasks(parse_xml(sample_xml))


def test_every_code_body_becomes_a_task(sample_xml):
    tasks = _tasks(sample_xml)
    names = {t.title for t in tasks}
    assert "WHEN-NEW-FORM-INSTANCE" in names
    assert "ORDERS.PRE-INSERT" in names
    assert "ORDERS.CUSTOMER.WHEN-VALIDATE-ITEM" in names
    assert "P_TOTAL" in names


def test_trivial_bodies_are_not_worth_a_model_call(sample_xml):
    # "NULL;" and "CLEAR_FORM;" carry no conversion decision.
    assert "WHEN-BANANA-SPLIT" not in {t.title for t in _tasks(sample_xml)}


def test_task_carries_the_catalog_verdict(sample_xml):
    t = next(t for t in _tasks(sample_xml) if t.name == "WHEN-CUSTOM-ITEM-EVENT")
    assert t.verdict == "MANUAL"
    assert t.apex_hint


def test_every_task_carries_a_known_verdict(sample_xml):
    allowed = {rules.AUTO, rules.ASSISTED, rules.MANUAL, rules.DROP, rules.UNKNOWN}

    assert {task.verdict for task in _tasks(sample_xml)} <= allowed


def test_task_ids_are_stable(sample_xml):
    first = {t.title: t.id for t in _tasks(sample_xml)}
    second = {t.title: t.id for t in _tasks(sample_xml)}
    assert first == second


def test_prompt_carries_source_and_classification(sample_xml):
    t = next(t for t in _tasks(sample_xml) if t.name == "WHEN-BUTTON-PRESSED")
    system, user = build_prompt(t)
    assert system.role == "system"
    assert "never invent" in system.content.lower()
    assert "HOST" in user.content and "[MANUAL]" in user.content
    assert ":GLOBAL.DIR" in user.content or "GLOBAL.DIR" in user.content


def test_proposal_survives_a_markdown_fence():
    p = parse_proposal('```json\n{"apex_target": "Validation", "code": "null;", "confidence": 0.9}\n```')
    assert p.ok and p.apex_target == "Validation" and p.confidence == 0.9


def test_proposal_survives_prose_around_the_json():
    p = parse_proposal('Sure! Here you go:\n{"code": "x", "confidence": 0.5}\nHope that helps.')
    assert p.ok and p.code == "x"


def test_garbage_is_an_error_not_an_empty_conversion():
    p = parse_proposal("I think you should rewrite this form by hand.")
    assert not p.ok
    assert p.code == ""
    assert p.confidence == 0.0


def test_empty_answer_is_an_error():
    assert not parse_proposal("").ok


def test_confidence_is_clamped():
    assert parse_proposal('{"confidence": 7}').confidence == 1.0
    assert parse_proposal('{"confidence": "not a number"}').confidence == 0.0


def test_provider_failure_becomes_a_proposal_not_an_exception(sample_xml):
    class Broken(ai.Provider):
        type_id = "broken"

        def complete(self, messages, max_tokens=0):
            raise ai.ProviderError("rate limited")

    p = propose(_tasks(sample_xml)[0], Broken())
    assert not p.ok and "rate limited" in p.error


def test_identical_bodies_are_converted_once():
    calls = []

    class Counting(ai.Provider):
        type_id = "counting"

        def complete(self, messages, max_tokens=0):
            calls.append(messages[-1].content)
            return json.dumps({"apex_target": "Process", "code": "x;", "confidence": 0.8})

    body = "BEGIN\n  TRATA_ERRO('the same pasted block');\n  RAISE FORM_TRIGGER_FAILURE;\nEND;"
    tasks = [
        ConversionTask(
            id=f"t{i}", module=f"M{i}", kind="trigger", name="ON-ERROR", owner="",
            verdict="ASSISTED", apex_hint="", source=body, lines=4,
            fingerprint="samefingerprint",
        )
        for i in range(5)
    ]
    out = propose_many(tasks, Counting())

    assert len(calls) == 1, "one distinct body must cost one model call"
    assert len(out) == 5
    assert all(p.ok and p.code == "x;" for p in out.values())
    reused = [p for p in out.values() if any("Reused" in n for n in p.notes)]
    assert len(reused) == 4, "copies must be marked as reused, never passed off as fresh"


def test_failed_proposals_are_not_cached_as_shared():
    attempts = []

    class FlakyThenFine(ai.Provider):
        type_id = "flaky"

        def complete(self, messages, max_tokens=0):
            attempts.append(1)
            if len(attempts) == 1:
                raise ai.ProviderError("timeout")
            return json.dumps({"code": "ok;", "confidence": 0.7})

    tasks = [
        ConversionTask(
            id=f"t{i}", module=f"M{i}", kind="trigger", name="X", owner="",
            verdict="AUTO", apex_hint="", source="BEGIN NULL; END;", lines=1,
            fingerprint="fp",
        )
        for i in range(2)
    ]
    out = propose_many(tasks, FlakyThenFine())
    assert len(attempts) == 2, "a failed answer must not be reused as if it were good"
    assert out["t1"].ok


def test_the_prompt_carries_the_unit_and_nothing_else_from_the_session(sample_xml):
    """One unit's body goes out. Not the session, not another unit, not a key.

    The product's promise is that a conversion sends the code being
    converted. Anything else that ends up in the payload -- a neighbouring
    trigger, a stored decision, a credential -- would be sent without the
    reviewer ever asking for it.
    """
    tasks = _tasks(sample_xml)
    mine = next(t for t in tasks if t.name == "WHEN-BUTTON-PRESSED")
    _system, user = build_prompt(mine)

    for other in tasks:
        if other.id == mine.id:
            continue
        body = other.source.strip()
        if len(body) > 30:  # a one-liner like NULL; legitimately appears anywhere
            assert body not in user.content, f"{other.title} travelled with {mine.title}"

    payload = (user.content + _system.content).lower()
    for leak in ("api_key", "apikey", "authorization", "bearer ", "config.json",
                 "formslang_ai_key", "sqlite", "session.json"):
        assert leak not in payload, f"{leak!r} has no business in a prompt"


def test_the_deterministic_analysis_travels_as_fact_not_as_a_question(sample_xml):
    """Passing the rules' answer stops the model re-deriving it, badly."""
    from formslang.analysis import analyze_task

    task = next(t for t in _tasks(sample_xml) if t.name == "WHEN-BUTTON-PRESSED")
    _system, user = build_prompt(task, analyze_task(task))
    assert "measured facts about the source, not opinions" in user.content
    assert "Risk: " in user.content and "Behaviour after migration:" in user.content
    assert "UNSUPPORTED" in user.content, "the migration class travels with the built-in"
