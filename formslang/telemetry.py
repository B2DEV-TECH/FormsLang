"""Wall-clock instrumentation for the conversion pipeline.

Standard library only -- ``time.perf_counter()`` is the one primitive that
behaves the same on Windows and POSIX, which is why this module measures
duration and counts and nothing else. CPU and memory sampling was left out
on purpose: the only portable way to get either without walking outside the
standard library is ``resource.getrusage``, and that call does not exist on
Windows, which is the platform this tool actually ships on. Adding a
dependency such as ``psutil`` to close that gap is not this module's call to
make -- ``pyproject.toml`` declares ``dependencies = []`` deliberately, so
FormsLang keeps running on a locked-down machine where installing a package
is a change request.

Nothing recorded here is content: a stage name, a duration and a count are
never the code, the spec, the prompt or the model's answer. On failure, only
the *class name* of the exception is kept (``error_kind``) -- never
``str(exception)``, which could quote the very source text a stage was
processing.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager

# (stage_name, duration_ms, item_count, ok, error_kind) -> None
Recorder = Callable[[str, float, int, bool, str], None]


@contextmanager
def stage(recorder: Recorder | None, name: str, item_count: int = 0) -> Iterator[None]:
    """Time one pipeline stage and hand the result to ``recorder``.

    ``recorder`` is optional so instrumentation can be wired in without a
    store on hand (a bare ``None`` measures nothing and costs one branch).
    The block's exception, if any, is always re-raised unchanged -- this is
    an observer, never a handler.
    """
    started = time.perf_counter()
    ok = True
    error_kind = ""
    try:
        yield
    except BaseException as e:
        ok = False
        error_kind = type(e).__name__
        raise
    finally:
        duration_ms = (time.perf_counter() - started) * 1000.0
        if recorder is not None:
            recorder(name, duration_ms, item_count, ok, error_kind)


def percentile(values: list[float], pct: float) -> float:
    """Nearest-rank percentile over already-sorted-or-not values.

    No interpolation, no numpy -- this is the simplest definition that is
    still defensible for a baseline, and it needs nothing beyond stdlib
    ``sorted()``. ``pct`` is 0-100. Empty input is 0.0, not an exception:
    a stage that never ran has no latency to report, not a crash to report.
    """
    if not values:
        return 0.0
    ordered = sorted(values)
    if pct <= 0:
        return ordered[0]
    if pct >= 100:
        return ordered[-1]
    idx = max(0, min(len(ordered) - 1, round(pct / 100.0 * len(ordered)) - 1))
    return ordered[idx]


def summarize(durations_ms: list[float]) -> dict:
    """count/min/p50/p95/max/total over one stage's recorded durations."""
    if not durations_ms:
        return {"count": 0, "min_ms": 0.0, "p50_ms": 0.0, "p95_ms": 0.0,
                "max_ms": 0.0, "total_ms": 0.0}
    return {
        "count": len(durations_ms),
        "min_ms": min(durations_ms),
        "p50_ms": percentile(durations_ms, 50),
        "p95_ms": percentile(durations_ms, 95),
        "max_ms": max(durations_ms),
        "total_ms": sum(durations_ms),
    }
