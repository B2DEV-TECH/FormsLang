"""Regression runner for the golden corpus.

Two things are asserted per tier: the committed golden JSON still matches
what the pipeline produces today (with a readable diff on mismatch, not
just "assertion failed"), and the pipeline is actually deterministic
(building the same tier twice in the same run produces byte-identical
text). If a tier's golden is out of date, see tests/update_golden.py --
this file never writes a golden file itself.
"""

from __future__ import annotations

import difflib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import golden


def _readable_diff(tier: str, expected: str, actual: str) -> str:
    diff = "\n".join(
        difflib.unified_diff(
            expected.splitlines(),
            actual.splitlines(),
            fromfile=f"{tier}.json (committed)",
            tofile=f"{tier}.json (current pipeline)",
            lineterm="",
        )
    )
    return (
        f"golden mismatch for tier {tier!r} -- if this change is intentional, "
        f"review the diff below and run: py tests/update_golden.py --tier {tier}\n\n{diff}"
    )


@pytest.mark.parametrize("tier", golden.TIERS)
def test_golden_matches_committed(tier: str) -> None:
    path = golden.golden_path(tier)
    assert path.exists(), f"missing golden file for tier {tier!r}: {path} -- run py tests/update_golden.py --tier {tier}"

    expected = path.read_text(encoding="utf-8")
    actual = golden.dumps(golden.build_golden(tier))
    assert actual == expected, _readable_diff(tier, expected, actual)


@pytest.mark.parametrize("tier", golden.TIERS)
def test_golden_is_deterministic(tier: str) -> None:
    first = golden.dumps(golden.build_golden(tier))
    second = golden.dumps(golden.build_golden(tier))
    assert first == second, f"tier {tier!r} produced different output across two runs -- something non-deterministic leaked into the golden dump"
