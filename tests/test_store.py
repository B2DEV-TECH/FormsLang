"""The session store: decisions survive, and history is never overwritten."""

from __future__ import annotations

import json

import pytest

from formslang import rules
from formslang.convert import Proposal, build_tasks
from formslang.parser import parse_xml
from formslang.store import (
    APPROVED,
    JOB_CANCELLED,
    JOB_COMPLETED,
    JOB_CRASHED,
    JOB_RUNNING,
    PENDING,
    REJECTED,
    Store,
)


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


def test_empty_verdict_from_an_old_session_reads_as_unknown(store):
    task_id = store.task_ids()[0]
    store.db.execute("UPDATE task SET verdict = '' WHERE id = ?", (task_id,))
    store.db.commit()

    assert store.get_task(task_id).verdict == rules.UNKNOWN


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


# -- telemetry --------------------------------------------------------------


def test_session_settings_round_trip_and_survive_reopening(tmp_path, sample_xml):
    """Small per-session facts (the export's checksum salt, its last
    deployment choices) live with the session, not in the user's config."""
    path = tmp_path / "settings.db"
    s = Store(path)
    s.init_session("DEMO_ORDER", str(sample_xml))
    assert s.setting("missing") == ""
    assert s.setting("missing", "fallback") == "fallback"

    s.set_setting("apex_checksum_salt", "ABC")
    s.set_setting("apex_checksum_salt", "DEF")  # a later write replaces, never appends
    assert s.setting("apex_checksum_salt") == "DEF"
    s.close()

    reopened = Store(path)
    try:
        assert reopened.setting("apex_checksum_salt") == "DEF"
    finally:
        reopened.close()


def test_stage_summary_is_empty_until_something_is_recorded(store):
    assert store.stage_summary() == {}


def test_recorded_stages_are_aggregated_per_stage_name(store):
    store.record_stage("analysis", 10.0, item_count=2)
    store.record_stage("analysis", 30.0, item_count=3)
    store.record_stage("export", 5.0)

    summary = store.stage_summary()
    assert set(summary) == {"analysis", "export"}
    assert summary["analysis"]["count"] == 2
    assert summary["analysis"]["min_ms"] == 10.0
    assert summary["analysis"]["max_ms"] == 30.0
    assert summary["analysis"]["total_ms"] == 40.0
    assert summary["analysis"]["failed"] == 0


def test_a_failed_stage_is_counted_but_not_hidden(store):
    store.record_stage("ai_propose", 12.0, ok=True)
    store.record_stage("ai_propose", 8.0, ok=False, error_kind="ProviderError")

    summary = store.stage_summary()
    assert summary["ai_propose"]["count"] == 2
    assert summary["ai_propose"]["failed"] == 1


def test_stage_timing_never_stores_free_text_content(store):
    """record_stage has no field for source code, prompts, or model answers --
    only a stage name, numbers, and the exception's class name ever land here."""
    store.record_stage("ai_propose", 1.0, ok=False, error_kind="ValueError")
    row = store.db.execute("SELECT * FROM stage_timing").fetchone()
    assert set(row.keys()) == {
        "id", "stage", "started_at", "duration_ms", "item_count", "ok", "error_kind",
    }


# -- job runs -----------------------------------------------------------


def test_a_new_job_run_starts_in_the_running_state(store):
    run_id = store.start_job_run(total=5)
    run = store.last_job_run()
    assert run["id"] == run_id
    assert run["status"] == JOB_RUNNING
    assert run["total"] == 5
    assert run["done"] == 0
    assert run["cancel_requested"] == 0


def test_progress_and_completion_are_persisted(store):
    run_id = store.start_job_run(total=3)
    store.update_job_run(run_id, done=2, failed=1)
    store.finish_job_run(run_id, JOB_COMPLETED)

    run = store.last_job_run()
    assert run["done"] == 2 and run["failed"] == 1
    assert run["status"] == JOB_COMPLETED
    assert run["ended_at"] != ""


def test_finish_job_run_refuses_an_unknown_status(store):
    run_id = store.start_job_run(total=1)
    with pytest.raises(ValueError, match="unknown job_run status"):
        store.finish_job_run(run_id, "paused")


def test_cancel_is_requested_only_for_a_run_that_is_still_running(store):
    run_id = store.start_job_run(total=2)
    assert store.request_job_cancel(run_id) is True
    assert store.is_job_cancel_requested(run_id) is True

    store.finish_job_run(run_id, JOB_CANCELLED)
    # Already finished: a second request is a no-op, not a resurrection.
    assert store.request_job_cancel(run_id) is False


def test_cancel_on_an_unknown_run_id_is_a_clean_no_op(store):
    assert store.request_job_cancel(999) is False
    assert store.is_job_cancel_requested(999) is False


def test_a_run_left_running_becomes_crashed_when_the_session_reopens(tmp_path, sample_xml):
    """A row stuck at 'running' can only mean the process that owned it never
    reached start_job's finally block -- reconcile_job_runs is what turns that
    into a queryable, honest status instead of a run stuck forever mid-flight."""
    path = tmp_path / "orphan.db"
    s = Store(path)
    s.init_session("DEMO_ORDER", str(sample_xml))
    run_id = s.start_job_run(total=4)
    s.update_job_run(run_id, done=1, failed=0)
    s.close()  # simulates the process dying before finish_job_run ever runs

    again = Store(path)
    try:
        run = again.last_job_run()
        assert run["id"] == run_id
        assert run["status"] == JOB_CRASHED
        assert run["done"] == 1, "progress already recorded must not be lost"
    finally:
        again.close()


def test_last_job_run_is_none_when_no_job_has_ever_run(store):
    assert store.last_job_run() is None
