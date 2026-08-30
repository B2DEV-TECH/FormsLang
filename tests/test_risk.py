"""The risk engine. Deterministic, bounded, and answerable to a reviewer."""

from __future__ import annotations

from formslang import risk, rules
from formslang.plsql import analyze

SAFE = """
BEGIN
  :ORDERS.TOTAL := :ORDERS.QTY * :ORDERS.PRICE;
END;
"""

DANGEROUS = """
BEGIN
  GO_BLOCK('ITEMS');
  EXECUTE_QUERY;
  COPY(:ORDERS.ID, 'GLOBAL.LAST_ORDER');
  HOST('print.bat');
  FORMS_DDL('ALTER SESSION SET NLS_DATE_FORMAT = ''DD/MM/YYYY''');
  COMMIT_FORM;
END;
"""


def assess(code: str, **kw):
    return risk.assess(analyze(code), source=code, **kw)


def test_score_curve_is_the_published_formula():
    assert risk.score_from_raw(0) == 0.0
    assert round(risk.score_from_raw(risk.HALF_LIFE), 1) == 50.0
    assert round(risk.score_from_raw(risk.HALF_LIFE * 2), 1) == 75.0
    # Saturating: no amount of evidence ever reaches a round 100.
    assert risk.score_from_raw(10_000) < 100.0


def test_levels_follow_the_published_thresholds():
    assert risk.level_for(0) == risk.LOW
    assert risk.level_for(19.9) == risk.LOW
    assert risk.level_for(20) == risk.MEDIUM
    assert risk.level_for(44.9) == risk.MEDIUM
    assert risk.level_for(45) == risk.HIGH
    assert risk.level_for(70) == risk.CRITICAL


def test_arithmetic_is_plain_arithmetic():
    """Anyone can add the factors up and get the same number."""
    result = assess(DANGEROUS, kind="trigger", trigger_name="WHEN-BUTTON-PRESSED")
    assert round(sum(f.points for f in result.factors), 4) == round(result.raw, 4)
    assert round(risk.score_from_raw(result.raw), 4) == round(result.score, 4)


def test_the_same_input_always_scores_the_same():
    a = assess(DANGEROUS, trigger_name="WHEN-BUTTON-PRESSED")
    b = assess(DANGEROUS, trigger_name="WHEN-BUTTON-PRESSED")
    assert a.to_dict() == b.to_dict()


def test_plain_arithmetic_is_not_dangerous():
    result = assess(SAFE, kind="program_unit")
    assert result.level == risk.LOW
    assert result.score == 0.0
    assert result.factors == []


def test_an_empty_body_scores_nothing_rather_than_guessing():
    assert assess("").level == risk.LOW
    assert assess("").raw == 0.0


def test_dangerous_constructs_raise_the_level():
    result = assess(DANGEROUS, trigger_name="WHEN-BUTTON-PRESSED")
    assert result.level in (risk.HIGH, risk.CRITICAL)
    assert result.review_areas


def test_every_factor_carries_its_evidence_and_a_review_area():
    result = assess(DANGEROUS, trigger_name="WHEN-BUTTON-PRESSED")
    assert result.factors
    for factor in result.factors:
        assert factor.title.strip() and factor.detail.strip()
        assert factor.points > 0


def test_one_dangerous_construct_alone_floors_the_level_at_high():
    """HOST cannot be quietly LOW just because the body is three lines."""
    result = assess("BEGIN HOST('del *.*'); END;", kind="program_unit")
    assert result.level == risk.HIGH
    assert any(f.floor for f in result.factors)


def test_a_floor_never_reaches_critical_on_its_own():
    """CRITICAL means several dangerous things at once, and must be earned."""
    result = assess("BEGIN HOST('x'); END;", kind="program_unit")
    assert result.level != risk.CRITICAL


def test_repeating_a_call_costs_more_but_not_linearly():
    once = assess("BEGIN GO_BLOCK('A'); END;", kind="program_unit").raw
    many = assess("BEGIN " + "GO_BLOCK('A'); " * 8 + " END;", kind="program_unit").raw
    assert many > once
    assert many < once * 8


def test_an_unrecognised_bare_call_is_priced_not_ignored():
    """It may be a local procedure, or a built-in we never catalogued."""
    unknown = assess("BEGIN DO_THE_LEGACY_THING(1); END;", kind="program_unit")
    assert unknown.raw > 0
    assert any(f.id == "unresolved_calls" for f in unknown.factors)


def test_a_qualified_package_call_is_not_treated_as_catalog_debt():
    """PKG.PROC is ordinary database code and migrates as it is."""
    result = assess("BEGIN SOME_LEGACY_PACK.DO_IT(1); END;", kind="program_unit")
    assert not any(f.id in ("unresolved_calls", "catalog_debt") for f in result.factors)


def test_a_dangerous_trigger_point_counts_by_itself():
    empty_ish = "BEGIN NULL; END;"
    plain = assess(empty_ish, trigger_name="WHEN-BUTTON-PRESSED").raw
    risky = assess(empty_ish, trigger_name="ON-LOCK").raw
    assert risky > plain


def test_explain_publishes_the_formula_and_what_is_not_an_input():
    doc = risk.explain()
    assert "0.5" in doc["formula"] and "raw" in doc["formula"]
    assert doc["thresholds"] and doc["inputs"]
    joined = " ".join(doc["not_inputs"]).lower()
    assert "confidence" in joined


def test_risk_is_not_the_verdict():
    """An AUTO construct can still be dangerous -- that is the whole point."""
    spec = rules.spec_for("COMMIT_FORM")
    assert spec.verdict == rules.AUTO
    assert spec.risk >= 0.8
