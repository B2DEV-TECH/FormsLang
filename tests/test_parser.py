"""Parser behaviour on the two things Forms2XML does that break naive readers."""

from __future__ import annotations

import pytest

from formslang.parser import decode_forms_text, parse_xml


def test_double_escaped_newlines_become_real_lines():
    raw = "BEGIN&#10;&#9;NULL;&#10;END;"
    assert decode_forms_text(raw) == "BEGIN\n\tNULL;\nEND;"


def test_mojibake_is_repaired():
    assert decode_forms_text("ConexÃ£o") == "Conexão"


def test_text_without_mojibake_is_untouched():
    assert decode_forms_text("plain ASCII text") == "plain ASCII text"


def test_empty_text_is_empty_string():
    assert decode_forms_text(None) == ""
    assert decode_forms_text("") == ""


def test_parse_reads_the_whole_structure(sample_xml):
    mod = parse_xml(sample_xml)
    assert mod.name == "DEMO_ORDER"
    assert len(mod.blocks) == 1
    assert len(mod.all_items) == 3
    assert len(mod.lovs) == 1 and mod.lovs[0].columns == 2
    assert len(mod.record_groups) == 1
    assert mod.attached_libraries == ["DEMO_LIB"]
    assert [c.name for c in mod.canvases] == ["CV_MAIN"]


def test_triggers_are_collected_at_every_scope(sample_xml):
    mod = parse_xml(sample_xml)
    scopes = {t.scope for t in mod.all_triggers}
    assert scopes == {"form", "block", "item"}
    assert len(mod.all_triggers) == 7


def test_trigger_body_keeps_its_line_count(sample_xml):
    mod = parse_xml(sample_xml)
    wnfi = next(t for t in mod.all_triggers if t.name == "WHEN-NEW-FORM-INSTANCE")
    assert wnfi.lines == 4  # would be 1 without the second decoding pass


def test_item_prompt_mojibake_is_repaired(sample_xml):
    mod = parse_xml(sample_xml)
    customer = next(i for i in mod.all_items if i.name == "CUSTOMER")
    assert customer.prompt == "Conexão"


def test_item_geometry_is_parsed(sample_xml):
    mod = parse_xml(sample_xml)
    order_id = next(i for i in mod.all_items if i.name == "ORDER_ID")
    assert (order_id.x, order_id.y, order_id.width, order_id.height) == (20, 20, 100, 17)


def test_canvas_geometry_is_parsed(sample_xml):
    mod = parse_xml(sample_xml)
    canvas = next(c for c in mod.canvases if c.name == "CV_MAIN")
    assert canvas.window_name == "WIN_MAIN"
    assert canvas.canvas_type == "Content"
    assert (canvas.width, canvas.height) == (640, 480)
    assert (canvas.viewport_width, canvas.viewport_height) == (600, 400)


def test_non_form_module_is_rejected(tmp_path):
    path = tmp_path / "MENU_mmb.xml"
    path.write_text(
        '<?xml version="1.0"?>'
        '<Module xmlns="http://xmlns.oracle.com/Forms"><MenuModule Name="M"/></Module>',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="no <FormModule>"):
        parse_xml(path)
