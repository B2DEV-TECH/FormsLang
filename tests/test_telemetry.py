"""Wall-clock instrumentation: it must time, never swallow, and never leak
content -- see formslang/telemetry.py for why only wall-clock is measured.
"""

from __future__ import annotations

from formslang import telemetry


def _recorder(calls: list[tuple]):
    """telemetry.stage() calls the recorder with five positional args --
    pack them into a tuple the way Store.record_stage would receive them."""
    return lambda *args: calls.append(args)


def test_a_successful_stage_is_recorded_once_with_ok_true():
    calls: list[tuple] = []
    with telemetry.stage(_recorder(calls), "parse", item_count=3):
        pass
    assert len(calls) == 1
    name, duration_ms, item_count, ok, error_kind = calls[0]
    assert name == "parse"
    assert duration_ms >= 0.0
    assert item_count == 3
    assert ok is True
    assert error_kind == ""


def test_a_failing_stage_is_recorded_and_the_exception_still_propagates():
    calls: list[tuple] = []
    try:
        with telemetry.stage(_recorder(calls), "ai_propose"):
            raise ValueError("the exact source text of the failing unit")
    except ValueError:
        pass
    else:
        raise AssertionError("the exception must still reach the caller")
    assert len(calls) == 1
    _name, _duration_ms, _item_count, ok, error_kind = calls[0]
    assert ok is False
    assert error_kind == "ValueError"


def test_error_kind_never_carries_the_exception_message():
    """The message can quote the very source a stage was processing --
    only the class name is ever safe to keep."""
    calls: list[tuple] = []
    try:
        with telemetry.stage(_recorder(calls), "export"):
            raise RuntimeError("BEGIN secret_proc(:p_credential); END;")
    except RuntimeError:
        pass
    _name, _duration_ms, _item_count, _ok, error_kind = calls[0]
    assert error_kind == "RuntimeError"
    assert "secret_proc" not in error_kind
    assert "credential" not in error_kind


def test_a_none_recorder_measures_nothing_and_does_not_crash():
    with telemetry.stage(None, "analysis"):
        pass
    with_error = False
    try:
        with telemetry.stage(None, "analysis"):
            raise KeyError("x")
    except KeyError:
        with_error = True
    assert with_error


def test_percentile_of_empty_input_is_zero_not_an_exception():
    assert telemetry.percentile([], 50) == 0.0


def test_percentile_clamps_at_the_ends():
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert telemetry.percentile(values, 0) == 1.0
    assert telemetry.percentile(values, 100) == 5.0


def test_summarize_reports_the_shape_reviewers_expect():
    summary = telemetry.summarize([10.0, 20.0, 30.0])
    assert summary["count"] == 3
    assert summary["min_ms"] == 10.0
    assert summary["max_ms"] == 30.0
    assert summary["total_ms"] == 60.0
    assert summary["p50_ms"] > 0.0


def test_summarize_of_no_durations_is_a_clean_zero_row():
    summary = telemetry.summarize([])
    assert summary == {
        "count": 0, "min_ms": 0.0, "p50_ms": 0.0, "p95_ms": 0.0,
        "max_ms": 0.0, "total_ms": 0.0,
    }
