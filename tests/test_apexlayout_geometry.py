"""apexlayout / apexlang: the layout milestone's second pass -- a control on
the column its Forms x maps to, gaps kept, the concessions the rules record,
labels settled per row, toolbar cells, static defaults and button behaviour.

Synthetic modules only. Every APEXlang keyword asserted here was accepted by
``apex validate`` and rendered on APEX 26.1 (probe app of the fidelity
pass) before it went into the exporter.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from formslang.apexlang import _page_items
from formslang.apexlayout import (
    APPROXIMATION,
    FAITHFUL,
    build_layout,
    forms_expression_default,
    item_default,
    layout_report,
    static_default,
)
from formslang.formui import render_html
from formslang.model import Block, Canvas, FormModule, Graphic, Item, RadioButton, Window
from formslang.parser import parse_xml

SHOWCASE = Path(__file__).parent / "fixtures" / "showcase" / "module.xml"

#: A module in points with a 5-point character cell: a prompt of N
#: characters takes 5N points of room beside its field.
POINTS = {
    "coordinate_system": "Real",
    "coordinate_unit": "Point",
    "char_cell_width": 5,
    "char_cell_height": 14,
}


def _module(items, canvases=None, **kw) -> FormModule:
    return FormModule(
        name="M",
        canvases=canvases or [Canvas(name="CV", width=600, height=200)],
        blocks=[Block(name="B", items=items)],
        **kw,
    )


def _item(name, x, y, width=50, height=14, canvas="CV", item_type="Text Item", **kw) -> Item:
    return Item(
        name=name, item_type=item_type, canvas=canvas, x=x, y=y, width=width, height=height, **kw
    )


def _body(module) -> dict:
    return {p.apex_name: p for p in build_layout(module).roots[0].body}


def _chunks(module) -> list[str]:
    chunks, _ = _page_items(module, 1)
    return chunks


def _chunk(module, name) -> str:
    return next(c for c in _chunks(module) if f"P1_{name}" in c)


def _cell(placed) -> tuple:
    return (placed.grid.new_row, placed.grid.column, placed.grid.span)


# -- columns from x -----------------------------------------------------------


def test_whitespace_between_fields_stays_a_gap_column():
    """On a 600-unit canvas a column is 50 units. A field at x=200 starts in
    column 5; the two columns between it and its neighbour stay empty, as
    the whitespace was on the screen (Universal Theme pads skipped columns)."""
    body = _body(_module([_item("A", 0, 20, width=100), _item("B", 200, 20, width=100)]))

    assert _cell(body["P1_A"]) == (True, 1, 2)
    assert _cell(body["P1_B"]) == (False, 5, 2)
    assert body["P1_B"].grid.new_column
    assert body["P1_A"].flags == [] and body["P1_B"].flags == []


def test_a_leading_gap_is_kept_too():
    """A field Forms drew 100 units in from the left edge starts in column 3
    with two empty columns before it; it is not packed against the edge."""
    body = _body(_module([_item("A", 100, 20, width=100)]))

    assert _cell(body["P1_A"]) == (True, 3, 2)
    assert "startNewRow: true\n            column: 3\n            columnSpan: 2" in _chunk(
        _module([_item("A", 100, 20, width=100)]), "A"
    )


def test_a_field_rounding_onto_its_neighbours_column_is_pushed_right():
    """x=60 rounds to column 2, but the field before it runs to column 2:
    the second moves to the first free column and says so."""
    body = _body(_module([_item("A", 0, 20, width=100), _item("B", 60, 20, width=100)]))

    assert _cell(body["P1_B"]) == (False, 3, 2)
    assert body["P1_B"].flags == ["pushed"]
    assert body["P1_A"].flags == []


def test_a_field_with_no_room_left_on_the_row_wraps_to_the_next_grid_row():
    """A 250-unit field (5 columns) whose x maps to column 12 has one column
    left: less than half its width, so it continues on the next grid row
    from column 1 rather than being squeezed into a sliver."""
    body = _body(_module([_item("A", 0, 20, width=500), _item("B", 540, 20, width=250)]))

    assert _cell(body["P1_A"]) == (True, 1, 10)
    assert _cell(body["P1_B"]) == (True, 1, 5)
    assert body["P1_B"].flags == ["wrapped"]


def test_fields_after_a_wrap_follow_it_onto_the_new_grid_row():
    """Eight 100-unit fields, 100 units apart on a 600-unit canvas (50 a
    column), are 16 columns of a 12-column row. The seventh, past the end
    of the row, wraps -- and being wrapped it is not "pushed" as well --
    and the eighth, 100 units right of it in Forms, lands 2 columns right
    of it on the new row rather than back on the column its own x maps
    to: the pair stays together, as a person redrawing the row as two
    would keep it."""
    items = [_item(f"F{i}", i * 100, 20, width=100) for i in range(8)]
    body = _body(_module(items))
    cells = [_cell(body[f"P1_F{i}"]) for i in range(8)]

    assert cells[:6] == [(True, 1, 2), (False, 3, 2), (False, 5, 2), (False, 7, 2),
                         (False, 9, 2), (False, 11, 2)]
    assert cells[6] == (True, 1, 2)
    assert cells[7] == (False, 3, 2)
    assert body["P1_F6"].flags == ["wrapped"]
    assert body["P1_F7"].flags == []


def test_a_field_reaching_past_the_twelfth_column_is_narrowed():
    """A 4-column field starting in column 11 keeps its row -- half its
    columns fit -- and is narrowed to the two that remain."""
    body = _body(_module([_item("A", 0, 20, width=500), _item("B", 500, 20, width=200)]))

    assert _cell(body["P1_B"]) == (False, 11, 2)
    assert body["P1_B"].flags == ["shrunk"]


def test_a_field_with_a_prompt_beside_it_gets_a_column_for_the_label():
    """A 40-point field with "AB" (10 points) left of it is 50 points wide
    -- one column -- but a left label needs a column of its own next to
    the field's, so the cell is two columns: the label one, the field one."""
    body = _body(_module([_item("A", 100, 20, width=40, prompt="AB")], **POINTS))
    placed = body["P1_A"]

    assert placed.bounds() == (90, 20, 50, 14) and placed.label_room == 10
    assert (placed.grid.column, placed.grid.span, placed.label_span) == (3, 2, 1)
    assert (placed.side, placed.align, placed.flags) == ("left", "right", [])


# -- labels settled per row -----------------------------------------------------


def test_a_label_wider_than_its_field_leaves_the_field_its_last_column():
    """30 characters of prompt (150 points) beside a 10-point field: the pair
    spans three columns and the label wants all three; it gets two, because
    APEX rejects labelColumnSpan >= columnSpan when the page renders."""
    body = _body(_module([_item("A", 200, 20, width=10, prompt="A" * 30)], **POINTS))
    placed = body["P1_A"]

    assert placed.label_room == 150
    assert (placed.grid.column, placed.grid.span, placed.label_span) == (2, 3, 2)
    assert placed.flags == ["label-narrow"]


def test_a_row_that_cannot_give_every_label_a_column_puts_all_its_labels_above():
    """Two captioned fields on one row, the second squeezed into the last
    column: with no room for its label beside it, every label of the row
    goes above its field -- one rhythm per row, as a person would redraw it
    -- and each control says so."""
    module = _module(
        [
            _item("A", 50, 20, width=500, prompt="AB"),
            _item("B", 550, 20, width=50, prompt="CD"),
        ],
        **POINTS,
    )
    body = _body(module)
    a, b = body["P1_A"], body["P1_B"]

    assert (a.grid.column, a.grid.span) == (2, 10)
    assert (b.grid.column, b.grid.span) == (12, 1)
    assert (a.side, a.label_span, a.align) == ("above", 0, "left")
    assert (b.side, b.label_span, b.align) == ("above", 0, "left")
    assert a.flags == ["label-above"] and b.flags == ["shrunk", "label-above"]

    text = "\n".join(_chunks(module))
    assert text.count("template: @/optional-above") == 2
    assert "labelColumnSpan: 1" not in text and "template: @/optional\n" not in text


def test_a_caption_right_of_or_below_the_field_becomes_a_label_above():
    """Universal Theme has no label right of or below a field. The caption
    goes above, where it reads as a caption; floating inside the field
    would read as a placeholder. The report says which was which."""
    module = _module(
        [
            _item("A", 0, 20, width=100, prompt="Qtd", prompt_edge="End"),
            _item("B", 200, 20, width=100, prompt="Un", prompt_edge="Bottom"),
        ],
        **POINTS,
    )
    text = "\n".join(_chunks(module))

    assert text.count("template: @/optional-above") == 2
    assert "floating" not in text
    report = json.dumps(layout_report(build_layout(module)))
    assert "prompt right of the field in Forms, label above it here" in report
    assert "prompt below the field in Forms, label above it here" in report


# -- derived groups beside and below frames --------------------------------------


def test_loose_items_beside_a_frame_are_placed_inside_the_cell_next_to_it():
    """Two fields drawn right of a frame share the frame's row: they are
    wrapped in a chrome-less group that takes the columns their box maps
    to, and inside it they keep their own proportions."""
    frame = Graphic("FR", "Frame", x=0, y=10, width=300, height=100, title="Left")
    canvas = Canvas(name="CV", width=600, height=200, graphics=[frame])
    module = _module(
        [
            _item("A", 20, 30),
            _item("B", 320, 30, width=100),
            _item("C", 440, 30, width=100),
        ],
        canvases=[canvas],
    )
    root = build_layout(module).roots[0]
    frame_node, group = root.subs

    assert (frame_node.id, frame_node.grid.column, frame_node.grid.span) == ("left", 1, 6)
    assert group.derived and (group.grid.new_row, group.grid.column, group.grid.span) == (
        False,
        7,
        4,
    )
    assert [(p.apex_name, p.grid.column, p.grid.span) for p in group.body] == [
        ("P1_B", 1, 5),
        ("P1_C", 8, 5),
    ]


def test_loose_items_below_a_frame_keep_their_columns_on_the_parent():
    """A row of fields below a frame, alone on its row, is a full-width group
    whose items sit on the columns their x maps to on the canvas itself."""
    frame = Graphic("FR", "Frame", x=10, y=10, width=380, height=60, title="Top")
    canvas = Canvas(name="CV", width=400, height=200, graphics=[frame])
    module = _module(
        [_item("A", 20, 30), _item("B", 20, 100), _item("C", 100, 100)], canvases=[canvas]
    )
    root = build_layout(module).roots[0]
    group = root.subs[1]

    assert group.id == "cv-row-1"
    assert (group.grid.new_row, group.grid.column, group.grid.span) == (True, 1, 12)
    assert [(p.apex_name, p.grid.column, p.grid.span) for p in group.body] == [
        ("P1_B", 2, 2),
        ("P1_C", 4, 2),
    ]


# -- toolbars --------------------------------------------------------------------


def _toolbar_module(*toolbar_items) -> FormModule:
    return FormModule(
        name="M",
        canvases=[
            Canvas(name="CV", window_name="WI", canvas_type="Content", width=400, height=200),
            Canvas(
                name="TB", window_name="WI", canvas_type="Horizontal Toolbar", width=300, height=24
            ),
        ],
        blocks=[Block(name="B", items=[_item("A", 10, 10), *toolbar_items])],
        window_details={"WI": Window("WI", title="Cadastro", toolbar="TB")},
    )


def test_toolbar_buttons_share_a_cell_but_a_field_gets_its_own():
    """Buttons side by side flow into one cell, as a button bar does. A field
    on the toolbar gets a cell of its own, so its label and width are its
    own instead of stacking under the buttons; with no label columns in a
    flow region, its prompt goes above it."""
    module = _toolbar_module(
        _item("BT_SAVE", 2, 2, width=20, height=20, canvas="TB", item_type="Push Button",
              label="Salvar"),
        _item("BT_NEW", 30, 2, width=20, height=20, canvas="TB", item_type="Push Button",
              label="Novo"),
        _item("USUARIO", 120, 4, width=80, canvas="TB", prompt="Usuário"),
    )
    toolbar = build_layout(module).roots[0]

    assert toolbar.flow
    assert [(p.item.name, p.grid.new_row, p.grid.new_column) for p in toolbar.body] == [
        ("BT_SAVE", True, False),
        ("BT_NEW", False, False),
        ("USUARIO", False, True),
    ]
    chunks = _chunks(module)
    new = next(c for c in chunks if "button b-bt-new" in c)
    field = next(c for c in chunks if "P1_USUARIO" in c)
    assert "startNewRow: false\n            newColumn: false" in new
    assert "startNewRow: false\n            newColumn: true" in field
    assert "template: @/optional-above" in field
    report = json.dumps(layout_report(build_layout(module)))
    assert "a flow region has no label columns" in report


# -- buttons, check boxes, defaults ---------------------------------------------


def test_a_button_is_wired_for_a_dynamic_action_not_a_page_submit():
    """A Forms button runs its trigger; it never submits the page by itself.
    The exported button is ``definedByDynamicAction`` (rendered as
    type="button" on 26.1), so a click is inert until its action exists."""
    module = _module(
        [_item("BT_OK", 10, 10, width=60, height=20, item_type="Push Button", label="OK")]
    )
    chunk = next(c for c in _chunks(module) if "button b-bt-ok" in c)

    assert "action: definedByDynamicAction" in chunk
    assert "requiresConfirmation: false" in chunk


def test_a_literal_initial_value_is_the_items_static_default():
    """InitializeValue="ATIVO" is a static default (verified on 26.1: it
    fills the field on render). A Forms expression -- $$DATE$$, :GLOBAL.x,
    &PARAM -- is not a value and is left as a note."""
    module = _module(
        [
            _item("ST", 0, 20, initial_value="ATIVO"),
            _item("DT", 100, 20, initial_value="$$DATE$$"),
            _item("GL", 200, 20, initial_value=":GLOBAL.EMPRESA"),
            _item("NO", 300, 20),
        ]
    )
    chunks = {name: _chunk(module, name) for name in ("ST", "DT", "GL", "NO")}

    assert re.search(r'default \{\n\s+type: static\n\s+staticValue: "?ATIVO"?', chunks["ST"])
    assert "default {" not in chunks["DT"] and "$$DATE$$ is an expression" in chunks["DT"]
    assert "default {" not in chunks["GL"] and ":GLOBAL.EMPRESA is an expression" in chunks["GL"]
    assert "default {" not in chunks["NO"] and "expression" not in chunks["NO"]

    assert static_default(Item(name="X", initial_value="ATIVO")) == "ATIVO"
    assert static_default(Item(name="X", initial_value="&PARAM")) == ""
    assert forms_expression_default(Item(name="X", initial_value="&PARAM")) == "&PARAM"
    assert forms_expression_default(Item(name="X", initial_value="ATIVO")) == ""


def test_a_default_on_a_list_or_radio_group_must_be_one_of_its_choices():
    """APEX adds a default that is not one of a radio group's or select
    list's return values to the choices, as an extra one, selected -- a
    fourth button on a three-button group. So the default is written only
    when it is a return value; when it is a choice's *label* (the .fmb
    declares no return values and the names stand in) that choice's return
    value is written and the concession reported; when it is neither, no
    default, and the report says why."""
    buttons = [RadioButton(name="RB_ATIVO", label="Ativo"), RadioButton(name="RB_INATIVO", label="Inativo")]
    declared = [
        RadioButton(name="RB_A", label="Ativo", value="A"),
        RadioButton(name="RB_I", label="Inativo", value="I"),
    ]
    module = _module(
        [
            _item("RG", 0, 20, item_type="Radio Group", radio_buttons=buttons, initial_value="ATIVO"),
            _item("RD", 0, 50, item_type="Radio Group", radio_buttons=declared, initial_value="A"),
            _item("RX", 0, 80, item_type="Radio Group", radio_buttons=declared, initial_value="XYZ"),
            _item(
                "LS", 0, 110, item_type="List Item", choices=["Unidade", "Caixa"],
                choice_values=["UNIDADE", "CAIXA"], initial_value="UNIDADE",
            ),
        ]
    )
    chunks = {name: _chunk(module, name) for name in ("RG", "RD", "RX", "LS")}

    assert re.search(r'staticValue: "?RB_ATIVO"?', chunks["RG"])
    assert "label of a choice, not a return value" in chunks["RG"]
    assert re.search(r'staticValue: "?A"?\n', chunks["RD"])
    assert "not a return value" not in chunks["RD"]
    assert "default {" not in chunks["RX"] and "XYZ is none of the choices" in chunks["RX"]
    assert re.search(r'staticValue: "?UNIDADE"?', chunks["LS"])

    why = (
        "initial value ATIVO is the label of a choice, not a return value: the choice "
        "returning RB_ATIVO is the default"
    )
    assert item_default(module.blocks[0].items[0]) == ("RB_ATIVO", "Ativo", why)
    assert item_default(module.blocks[0].items[1]) == ("A", "Ativo", "")
    assert item_default(module.blocks[0].items[3]) == ("UNIDADE", "Unidade", "")

    report = {c["target"]["name"]: c for c in layout_report(build_layout(module))["controls"]}
    assert "initial value" in report["P1_RG"]["preserved"]
    assert any("label of a choice" in a for a in report["P1_RG"]["approximations"])
    assert report["P1_RD"]["status"] == FAITHFUL
    assert any("none of the choices" in a for a in report["P1_RX"]["approximations"])
    assert "initial value" not in report["P1_RX"]["preserved"]

    html = render_html(module)
    assert '<span class="on"><i></i>Ativo</span>' in html
    assert '<span class="val">Unidade</span>' in html


def test_the_preview_shows_the_static_default_inside_the_field():
    html = render_html(_module([_item("ST", 0, 20, initial_value="ATIVO")]))
    assert '<span class="val">ATIVO</span>' in html


def test_the_parser_reads_initialize_value():
    by_name = {it.name: it for it in parse_xml(SHOWCASE).all_items}
    assert by_name["TP_STATUS"].initial_value == "ATIVO"
    assert by_name["TP_UNIDADE"].initial_value == "UNIDADE"


# -- the mapping report ------------------------------------------------------------


def test_the_mapping_report_names_each_concession_and_the_static_default():
    module = _module(
        [_item("A", 0, 20, width=100, initial_value="X"), _item("B", 60, 20, width=100)]
    )
    report = layout_report(build_layout(module))
    by_name = {c["target"]["name"]: c for c in report["controls"]}

    assert by_name["P1_A"]["status"] == FAITHFUL
    assert "initial value" in by_name["P1_A"]["preserved"]
    assert by_name["P1_A"]["target"]["placement"] == "rules"
    assert by_name["P1_B"]["status"] == APPROXIMATION
    why = by_name["P1_B"]["approximations"]
    assert any("moved right to the first free column" in a for a in why)
    assert report["totals"]["placed_by_ai"] == 0
