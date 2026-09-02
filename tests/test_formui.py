"""formui: read-only Forms UI vs. APEX default-mapping preview."""

from __future__ import annotations

from formslang.formui import render_html, write_report
from formslang.model import Block, Canvas, FormModule, Item
from formslang.parser import parse_xml


def test_render_html_covers_a_real_module(sample_xml):
    module = parse_xml(sample_xml)
    html = render_html(module, generated_at="2026-01-01 00:00 UTC")

    assert module.name in html
    assert "<!doctype html>" in html.lower()
    assert "CV_MAIN" in html
    for block in module.blocks:
        for item in block.items:
            assert item.name in html
    # ORDER_ID is a Text Item -> textField; BTN_PRINT is a Push Button -> button.
    assert "textField" in html
    assert "button" in html


def test_render_html_has_no_apex_type_picker():
    """Hard UX rule: the reviewer must never be offered a choice here."""
    module = FormModule(
        name="NOPICK",
        blocks=[Block(name="B", items=[Item(name="X", item_type="Text Item")])],
    )
    html = render_html(module)

    assert "<select" not in html
    assert "<option" not in html


def test_render_html_handles_an_empty_module():
    module = FormModule(name="EMPTY")
    html = render_html(module, generated_at="2026-01-01 00:00 UTC")

    assert "EMPTY" in html
    assert "no canvases in this module" in html
    assert "no blocks in this module" in html


def test_unpositioned_items_are_called_out_instead_of_silently_dropped():
    canvas = Canvas(name="CV1", width=200, height=200)
    item = Item(name="NO_POS", item_type="Text Item", canvas="CV1")  # no x/y/width/height
    module = FormModule(name="M", canvases=[canvas], blocks=[Block(name="B", items=[item])])

    html = render_html(module)

    assert "NO_POS" in html
    assert "no recorded position" in html


def test_item_not_on_a_known_canvas_is_still_shown():
    item = Item(name="ORPHAN", item_type="Check Box", canvas="MISSING_CANVAS")
    module = FormModule(name="M", blocks=[Block(name="B", items=[item])])

    html = render_html(module)

    assert "ORPHAN" in html
    assert "Not on a known canvas" in html


def test_unconfirmed_item_types_are_flagged_approx_not_claimed_as_mapped():
    item = Item(name="RG1", item_type="Radio Group")
    module = FormModule(name="M", blocks=[Block(name="B", items=[item])])

    html = render_html(module)

    assert "approx" in html


def test_apex_label_spaces_out_an_underscored_prompt():
    """A raw internal-code prompt is one unbroken word -- it must not stay that way.

    Real Forms modules sometimes leave Prompt as the developer's own code
    (e.g. ``ATSF_101ENDERECO_COMPLEMENTO``) instead of real copy. With no
    space to break on, that string doesn't wrap and blows out the two-column
    layout instead. Spacing it out fixes the overflow and the readability
    in one move.
    """
    item = Item(name="X", item_type="Check Box", prompt="ATSF_101ENDERECO_COMPLEMENTO")
    module = FormModule(name="M", blocks=[Block(name="B", items=[item])])

    html = render_html(module)

    assert "ATSF_101ENDERECO_COMPLEMENTO" not in html
    assert "ATSF 101ENDERECO COMPLEMENTO" in html


def test_apex_label_keeps_an_authored_prompt_as_written():
    """A prompt with no underscores -- real copy -- is shown verbatim, not title-cased."""
    item = Item(name="X", item_type="Text Item", prompt="Posição de Estocagem")
    module = FormModule(name="M", blocks=[Block(name="B", items=[item])])

    html = render_html(module)

    assert "Posição de Estocagem" in html


def test_write_report_creates_named_file(tmp_path):
    module = FormModule(name="DEMO_ORDER")
    path = write_report(module, tmp_path / "preview")

    assert path.exists()
    assert path.name == "DEMO_ORDER.preview.html"
    assert "DEMO_ORDER" in path.read_text(encoding="utf-8")
