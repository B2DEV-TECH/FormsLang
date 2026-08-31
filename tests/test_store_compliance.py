"""The compliance export: what was found, redacted, and where the provider's traffic went."""

from __future__ import annotations

import pytest

from formslang.analysis import analyze_task
from formslang.convert import ConversionTask, Proposal, build_tasks
from formslang.parser import parse_xml
from formslang.store import Store

PASSWORD_BODY = """
PROCEDURE do_login IS
BEGIN
  GRANT CONNECT TO scott IDENTIFIED BY tiger123;
  v_password := 'hunter2222';
END;
"""

CPF_BODY = """
BEGIN
  :GLOBAL.CPF := '529.982.247-25';
END;
"""

SAFE_BODY = """
BEGIN
  NULL;
END;
"""


@pytest.fixture()
def store(tmp_path, sample_xml):
    s = Store(tmp_path / "s.db")
    s.init_session("DEMO_ORDER", str(sample_xml))
    s.add_tasks(build_tasks(parse_xml(sample_xml)))
    yield s
    s.close()


def _add_unit(store: Store, unit_id: str, source: str) -> None:
    task = ConversionTask(
        id=unit_id,
        module="DEMO_ORDER",
        kind="trigger",
        name=unit_id,
        owner="",
        verdict="DIRECT_EQUIVALENT",
        apex_hint="",
        source=source,
        lines=source.count("\n") + 1,
    )
    store.add_tasks([task])
    store.save_analysis(analyze_task(task))


def test_a_session_with_nothing_to_report_exports_nothing(store):
    assert store.export_compliance(store.path.parent) is None
    assert not (store.path.parent / "compliance.md").exists()


def test_the_report_never_carries_the_secret_itself(store, tmp_path):
    _add_unit(store, "U_PASSWORD", PASSWORD_BODY)

    path = store.export_compliance(tmp_path / "out")
    assert path is not None
    text = path.read_text(encoding="utf-8")

    assert "tiger123" not in text
    assert "hunter2222" not in text
    assert "CREDENTIAL" in text


def test_category_and_severity_are_aggregated_across_units(store, tmp_path):
    _add_unit(store, "U_PASSWORD", PASSWORD_BODY)
    _add_unit(store, "U_CPF", CPF_BODY)
    _add_unit(store, "U_SAFE", SAFE_BODY)

    path = store.export_compliance(tmp_path / "out")
    text = path.read_text(encoding="utf-8")

    assert "CREDENTIAL" in text
    assert "BR_DOCUMENT" in text
    assert "U_PASSWORD" in text
    assert "U_CPF" in text
    # A unit with nothing to flag stays out of the per-unit sections.
    assert "U_SAFE ::" not in text


def test_providers_used_are_listed_with_their_egress(store, tmp_path):
    task_id = store.task_ids()[0]
    store.save_proposal(task_id, Proposal(code="x", provider="echo", model="echo"))

    path = store.export_compliance(tmp_path / "out")
    assert path is not None
    text = path.read_text(encoding="utf-8")

    assert "echo" in text
    assert "NONE" in text


def test_the_export_directory_gets_the_compliance_file_alongside_tests(store, tmp_path):
    _add_unit(store, "U_PASSWORD", PASSWORD_BODY)
    out = tmp_path / "review"
    store.export(out)
    assert (out / "compliance.md").exists()
