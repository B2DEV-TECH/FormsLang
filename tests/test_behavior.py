"""Behaviour classification, and the guard that keeps AI from softening it."""

from __future__ import annotations

from formslang import behavior
from formslang.plsql import analyze

ARITHMETIC = """
BEGIN
  :ORDERS.TOTAL := :ORDERS.QTY * :ORDERS.PRICE;
  IF :ORDERS.TOTAL > 1000 THEN
    :ORDERS.DISCOUNT := 0.1;
  END IF;
END;
"""

COMMITS = """
BEGIN
  COMMIT_FORM;
END;
"""

INDIRECT = """
BEGIN
  COPY(TO_CHAR(SYSDATE), 'ORDERS.' || :CONTROL.FIELD_NAME);
END;
"""


def classify(code: str, **kw):
    return behavior.classify(analyze(code), source=code, **kw)


def test_plain_arithmetic_is_preserved():
    result = classify(ARITHMETIC, kind="program_unit")
    assert result.value == behavior.PRESERVED
    assert result.reasons


def test_a_moved_transaction_boundary_is_changed_and_says_so():
    result = classify(COMMITS, trigger_name="WHEN-BUTTON-PRESSED")
    assert result.value == behavior.CHANGED
    assert any("transaction" in r.lower() for r in result.reasons)


def test_a_cycle_trigger_that_stops_firing_is_changed():
    result = classify("BEGIN :ORDERS.A := 1; END;", trigger_name="WHEN-NEW-BLOCK-INSTANCE")
    assert result.value == behavior.CHANGED


def test_a_relocated_trigger_is_uncertain_until_someone_chooses():
    result = classify("BEGIN :ORDERS.A := 1; END;", trigger_name="PRE-INSERT")
    assert result.value == behavior.UNCERTAIN
    assert any("PRE-INSERT" in u for u in result.uncertainties)


def test_a_runtime_built_target_is_uncertain_not_preserved():
    result = classify(INDIRECT, kind="program_unit")
    assert result.value == behavior.UNCERTAIN
    assert result.uncertainties


def test_an_unsupported_builtin_loses_the_capability_and_says_which():
    result = classify("BEGIN HOST('print.bat'); END;", kind="program_unit")
    assert result.value == behavior.CHANGED
    assert any("HOST" in r for r in result.reasons)


def test_a_body_too_small_to_analyse_is_uncertain_not_preserved():
    """Absence of evidence is never a clean bill of health."""
    result = classify("NULL;", kind="program_unit")
    assert result.value == behavior.UNCERTAIN
    assert result.uncertainties


def test_globals_are_flagged_because_their_lifetime_changes():
    result = classify("BEGIN :GLOBAL.LAST_ID := 7; END;", kind="program_unit")
    assert result.value == behavior.UNCERTAIN
    assert any("GLOBAL.LAST_ID" in u for u in result.uncertainties)


def test_ai_may_never_promote_a_unit_back_to_preserved():
    determined = behavior.BehaviorResult(value=behavior.CHANGED, reasons=["rule said so"])
    merged = behavior.merge_ai(determined, "PRESERVED", "looks fine to me")
    assert merged.value == behavior.CHANGED
    assert merged is determined
    assert merged.source == "rules"


def test_ai_may_never_soften_uncertain_to_preserved():
    determined = behavior.BehaviorResult(value=behavior.UNCERTAIN, uncertainties=["unclear"])
    assert behavior.merge_ai(determined, "PRESERVED").value == behavior.UNCERTAIN


def test_ai_may_make_the_answer_more_conservative():
    determined = behavior.BehaviorResult(value=behavior.PRESERVED, reasons=["nothing found"])
    merged = behavior.merge_ai(determined, "CHANGED", "the commit moves")
    assert merged.value == behavior.CHANGED
    assert merged.source == "rules+ai"
    assert any("INFERENCE" in r for r in merged.reasons)


def test_a_meaningless_ai_answer_changes_nothing():
    determined = behavior.BehaviorResult(value=behavior.PRESERVED)
    assert behavior.merge_ai(determined, "PROBABLY FINE").value == behavior.PRESERVED
    assert behavior.merge_ai(determined, "").value == behavior.PRESERVED
