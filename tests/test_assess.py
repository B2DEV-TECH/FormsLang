"""Scoring, and the portfolio pass that stops copy-paste being paid twice."""

from __future__ import annotations

import copy

import pytest

from formslang import rules
from formslang.assess import (
    DUPLICATE_REVIEW_FACTOR,
    TIERS,
    PortfolioAssessment,
    assess_module,
)
from formslang.parser import parse_xml


def test_module_is_scored_and_tiered(sample_xml):
    a = assess_module(parse_xml(sample_xml))
    assert a.name == "DEMO_ORDER"
    assert a.points > 0
    assert a.net_points == a.points  # nothing is shared until a portfolio runs
    assert a.tier in {t[2] for t in TIERS}


def test_blockers_and_manual_triggers_are_surfaced(sample_xml):
    a = assess_module(parse_xml(sample_xml))
    assert any(b[0].startswith("WEBUTIL_") for b in a.blockers)
    assert any(name == "HOST" for name, _r, _n in a.blockers)
    assert any(t == "WHEN-CUSTOM-ITEM-EVENT" for t, _r in a.manual_triggers)


def test_unknown_trigger_is_named_not_swallowed(sample_xml):
    a = assess_module(parse_xml(sample_xml))
    assert a.unknown_triggers == ["WHEN-BANANA-SPLIT"]
    assert a.trigger_verdicts[rules.UNKNOWN] == 1


def test_global_variable_raises_a_warning(sample_xml):
    a = assess_module(parse_xml(sample_xml))
    assert any(":GLOBAL" in w for w in a.warnings)


def test_every_code_body_becomes_a_unit(sample_xml):
    a = assess_module(parse_xml(sample_xml))
    kinds = [u.kind for u in a.units]
    assert kinds.count("trigger") == 7
    assert kinds.count("program_unit") == 1
    assert all(u.points > 0 for u in a.units)


def test_identical_modules_are_charged_once(sample_xml):
    """Two clones of the same form must not cost twice one form."""
    one = assess_module(parse_xml(sample_xml))
    two = copy.deepcopy(one)
    two.name = "DEMO_ORDER_CLONE"

    pf = PortfolioAssessment(modules=[one, two])
    pf.finalize()

    assert pf.shared_blocks, "identical bodies must be detected as shared"
    assert pf.total_points < pf.raw_points
    assert pf.duplication_savings > 0
    # Each clone keeps only the review cost of the shared bodies.
    for m in pf.modules:
        assert m.net_points < m.points


def test_unique_modules_are_not_discounted(sample_xml):
    solo = assess_module(parse_xml(sample_xml))
    pf = PortfolioAssessment(modules=[solo])
    pf.finalize()
    assert pf.shared_blocks == []
    assert pf.total_points == pytest.approx(pf.raw_points)
    assert pf.duplication_savings == pytest.approx(0)


def test_shared_block_accounting_adds_up(sample_xml):
    a = assess_module(parse_xml(sample_xml))
    b = copy.deepcopy(a)
    b.name = "CLONE"
    pf = PortfolioAssessment(modules=[a, b])
    pf.finalize()

    # Raw charges every copy in full. Net charges each instance only its
    # review share, then adds one full price per distinct block.
    expected_saving = sum(
        s.unit_points * s.instances * (1 - DUPLICATE_REVIEW_FACTOR) - s.unit_points
        for s in pf.shared_blocks
    )
    assert abs(pf.duplication_savings - expected_saving) < 0.01


def test_trivial_bodies_are_not_treated_as_shared_code(sample_xml):
    """"NULL;" in two forms is not evidence of code reuse."""
    a = assess_module(parse_xml(sample_xml))
    tiny = next(u for u in a.units if u.name == "WHEN-BANANA-SPLIT")
    assert tiny.fingerprint == ""
