"""The analysis seam: compatibility findings, versioning and round-trips."""

from __future__ import annotations

import json

from formslang import analysis, behavior, risk, rules
from formslang.convert import ConversionTask
from formslang.plsql import analyze

BODY = """
BEGIN
  GO_BLOCK('ITEMS');
  EXECUTE_QUERY;
  HOST('print.bat');
  COMMIT_FORM;
END;
"""


def test_findings_come_from_the_catalog_not_from_prose():
    findings = analysis.compat_findings(analyze(BODY))
    names = {f.name for f in findings}
    assert {"GO_BLOCK", "EXECUTE_QUERY", "HOST", "COMMIT_FORM"} <= names
    for finding in findings:
        spec = rules.spec_for(finding.name)
        assert finding.migration_class == spec.migration_class
        assert finding.apex == spec.apex


def test_findings_lead_with_the_most_dangerous_construct():
    findings = analysis.compat_findings(analyze(BODY))
    assert findings == sorted(findings, key=lambda f: (-f.risk, -f.count, f.name))


def test_a_literal_target_is_carried_into_the_finding():
    findings = {f.name: f for f in analysis.compat_findings(analyze(BODY))}
    assert findings["GO_BLOCK"].targets == ("ITEMS",)
    assert findings["HOST"].targets == ("print.bat",)


def test_a_computed_target_is_left_empty_rather_than_guessed():
    code = "BEGIN GO_BLOCK('ORD' || :CONTROL.SUFFIX); END;"
    findings = {f.name: f for f in analysis.compat_findings(analyze(code))}
    assert findings["GO_BLOCK"].targets == ()


def test_analyse_unit_answers_all_three_questions():
    item = analysis.analyze_unit(BODY, kind="trigger", name="WHEN-BUTTON-PRESSED", owner="ORDERS")
    assert item.risk.level in risk.RISK_LEVELS
    assert item.behavior.value in behavior.BEHAVIORS
    assert item.findings
    assert item.title == "ORDERS.WHEN-BUTTON-PRESSED"
    assert item.engine_version == analysis.ENGINE_VERSION
    assert item.stale is False


def test_unsupported_findings_are_reported_separately():
    item = analysis.analyze_unit(BODY, kind="trigger", name="WHEN-BUTTON-PRESSED")
    assert [f.name for f in item.unsupported] == ["HOST"]


def test_analysis_survives_a_json_round_trip():
    item = analysis.analyze_unit(BODY, kind="trigger", name="WHEN-BUTTON-PRESSED", owner="ORDERS")
    again = analysis.UnitAnalysis.from_dict(json.loads(json.dumps(item.to_dict())))
    assert again.to_dict() == item.to_dict()


def test_an_analysis_from_older_rules_reports_itself_stale():
    item = analysis.analyze_unit(BODY, kind="trigger", name="WHEN-BUTTON-PRESSED")
    item.engine_version = "analysis/1+risk/0+behavior/0+catalog:deadbeef"
    assert item.stale is True


def test_the_engine_version_changes_when_the_rules_change(monkeypatch):
    """A cached analysis must not survive a change in the rules that made it."""
    before = analysis._engine_version()
    monkeypatch.setitem(rules.TRIGGER_RISK, "PRE-INSERT", (0.99, "changed for the test"))
    assert analysis._engine_version() != before


def test_a_conversion_task_analyses_end_to_end():
    task = ConversionTask(
        id="t1", module="FRM_TEST", kind="trigger", name="WHEN-BUTTON-PRESSED",
        owner="ORDERS", verdict=rules.ASSISTED, apex_hint="", source=BODY, lines=6,
    )
    item = analysis.analyze_task(task)
    assert item.task_id == "t1"
    assert item.module == "FRM_TEST"
    assert item.findings


def test_summarize_counts_only_what_it_measured():
    items = [
        analysis.analyze_unit(BODY, kind="trigger", name="WHEN-BUTTON-PRESSED"),
        analysis.analyze_unit("BEGIN :A.B := 1; END;", kind="program_unit", name="P"),
    ]
    out = analysis.summarize(items)
    assert out["total"] == 2
    assert sum(out["risk"].values()) == 2
    assert sum(out["behavior"].values()) == 2
    assert out["unsupported"] == {"HOST": 1}
    assert out["stale"] == 0


def test_summarize_of_nothing_is_zero_not_a_guess():
    out = analysis.summarize([])
    assert out["total"] == 0
    assert out["avg_score"] == 0.0
    assert sum(out["risk"].values()) == 0
