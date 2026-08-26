"""The session store: decisions survive, and history is never overwritten."""

from __future__ import annotations

import json

import pytest

from formslang.convert import Proposal, build_tasks
from formslang.parser import parse_xml
from formslang.store import APPROVED, PENDING, REJECTED, Store


@pytest.fixture()
def store(tmp_path, sample_xml):
    s = Store(tmp_path / "s.db")
    s.init_session("DEMO_ORDER", str(sample_xml))
    s.add_tasks(build_tasks(parse_xml(sample_xml)))
    yield s
    s.close()


def test_tasks_are_stored_and_start_pending(store):
    stats = store.stats()
    assert stats["tasks"] > 0
    assert stats[PENDING] == stats["tasks"]
    assert stats["proposed"] == 0


def test_adding_the_same_tasks_twice_does_not_duplicate(store, sample_xml):
    before = store.stats()["tasks"]
    added = store.add_tasks(build_tasks(parse_xml(sample_xml)))
    assert added == 0
    assert store.stats()["tasks"] == before


def test_proposal_round_trips(store):
    task_id = store.task_ids()[0]
    store.save_proposal(task_id, Proposal(
        apex_target="Page process", code="null;", notes=["a"],
        open_questions=["b"], confidence=0.75, provider="echo", model="m",
    ))
    p = store.latest_proposal(task_id)
    assert p["apex_target"] == "Page process"
    assert p["notes"] == ["a"] and p["open_questions"] == ["b"]
    assert p["confidence"] == 0.75


def test_latest_proposal_wins(store):
    task_id = store.task_ids()[0]
    store.save_proposal(task_id, Proposal(code="first", confidence=0.1))
    store.save_proposal(task_id, Proposal(code="second", confidence=0.9))
    assert store.latest_proposal(task_id)["code"] == "second"


def test_pending_tasks_shrink_as_proposals_arrive(store):
    task_id = store.task_ids()[0]
    before = len(store.pending_tasks())
    store.save_proposal(task_id, Proposal(code="x"))
    assert len(store.pending_tasks()) == before - 1


def test_decision_history_is_kept(store):
    task_id = store.task_ids()[0]
    store.set_decision(task_id, REJECTED, comment="wrong target", reviewer="ana")
    store.set_decision(task_id, APPROVED, code="ok;", reviewer="ana")

    assert store.view(task_id).state == APPROVED
    history = store.history(task_id)
    assert [h["state"] for h in history] == [APPROVED, REJECTED]
    assert history[-1]["comment"] == "wrong target"


def test_reviewer_edit_beats_the_model_text(store):
    task_id = store.task_ids()[0]
    store.save_proposal(task_id, Proposal(code="model version"))
    store.set_decision(task_id, APPROVED, code="human version", reviewer="ana")
    assert store.view(task_id).code == "human version"


def test_unknown_state_is_refused(store):
    with pytest.raises(ValueError, match="unknown state"):
        store.set_decision(store.task_ids()[0], "maybe")


def test_export_writes_only_approved_units(store, tmp_path):
    ids = store.task_ids()
    store.save_proposal(ids[0], Proposal(code="approved code", apex_target="Validation"))
    store.set_decision(ids[0], APPROVED, code="approved code", reviewer="ana")
    store.save_proposal(ids[1], Proposal(code="rejected code"))
    store.set_decision(ids[1], REJECTED, code="rejected code")

    sql_path, json_path = store.export(tmp_path / "export")
    sql = sql_path.read_text(encoding="utf-8")
    assert "approved code" in sql
    assert "rejected code" not in sql
    assert "approved by: ana" in sql

    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["stats"]["approved"] == 1
    # The record covers every task, not just the approved ones.
    assert len(data["tasks"]) == len(ids)


def test_session_survives_reopening(tmp_path, sample_xml):
    path = tmp_path / "resume.db"
    s = Store(path)
    s.init_session("DEMO_ORDER", str(sample_xml))
    s.add_tasks(build_tasks(parse_xml(sample_xml)))
    task_id = s.task_ids()[0]
    s.set_decision(task_id, APPROVED, code="kept", reviewer="ana")
    s.close()

    again = Store(path)
    try:
        assert again.session()["title"] == "DEMO_ORDER"
        assert again.view(task_id).state == APPROVED
        assert again.view(task_id).code == "kept"
    finally:
        again.close()
