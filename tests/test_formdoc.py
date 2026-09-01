"""formdoc: HTML technical documentation for one module."""

from __future__ import annotations

from formslang.formdoc import render_html, write_report
from formslang.model import (
    Block,
    FormModule,
    Item,
    Lov,
    ProgramUnit,
    RecordGroup,
    Relation,
    Trigger,
)
from formslang.parser import parse_xml


def test_render_html_covers_a_real_module(sample_xml):
    module = parse_xml(sample_xml)
    html = render_html(module, generated_at="2026-01-01 00:00 UTC")

    assert module.name in html
    assert "<!doctype html>" in html.lower()
    for block in module.blocks:
        assert block.name in html
        for item in block.items:
            assert item.name in html
    for trigger in module.all_triggers:
        assert trigger.name in html


def test_render_html_handles_an_empty_module():
    module = FormModule(name="EMPTY")
    html = render_html(module, generated_at="2026-01-01 00:00 UTC")

    assert "EMPTY" in html
    assert "no blocks" in html
    assert "no program units" in html
    assert "no record groups" in html


def test_render_html_escapes_plsql_and_names():
    module = FormModule(
        name="ESC",
        triggers=[Trigger(name="WHEN<X>", text="IF a < b THEN NULL; END IF;", scope="form", owner="")],
    )
    html = render_html(module)

    assert "WHEN&lt;X&gt;" in html
    assert "a &lt; b" in html
    assert "<X>" not in html


def test_render_html_shows_conversion_warnings():
    module = FormModule(name="W", convert_warnings=["LOV FOO has no record group"])
    html = render_html(module)

    assert "Conversion warnings" in html
    assert "LOV FOO has no record group" in html


def test_render_html_lists_block_properties_and_relations():
    block = Block(
        name="ORDERS",
        query_data_source_name="ORDERS",
        where_clause="STATUS = 'OPEN'",
        items=[Item(name="ORDER_ID", item_type="Text Item", required=True)],
        triggers=[Trigger(name="WHEN-VALIDATE-RECORD", text="NULL;", scope="block", owner="ORDERS")],
    )
    module = FormModule(
        name="DEMO",
        blocks=[block],
        relations=[Relation(name="ORD_LINES", detail_block="ORDER_LINES", join_condition="ORDERS.ID = ORDER_LINES.ORDER_ID")],
        lovs=[Lov(name="LOV_STATUS", record_group="RG_STATUS", columns=1)],
        record_groups=[RecordGroup(name="RG_STATUS", kind="Query", query="SELECT 1 FROM DUAL")],
        program_units=[ProgramUnit(name="PKG_UTIL", kind="Package Body", text="BEGIN NULL; END;")],
    )
    html = render_html(module)

    assert "ORDERS" in html
    assert "STATUS = &#x27;OPEN&#x27;" in html or "STATUS = 'OPEN'" in html
    assert "ORD_LINES" in html
    assert "LOV_STATUS" in html
    assert "RG_STATUS" in html
    assert "PKG_UTIL" in html


def test_write_report_creates_named_file(tmp_path):
    module = FormModule(name="DEMO_ORDER")
    path = write_report(module, tmp_path / "doc")

    assert path.exists()
    assert path.name == "DEMO_ORDER.doc.html"
    assert "DEMO_ORDER" in path.read_text(encoding="utf-8")
