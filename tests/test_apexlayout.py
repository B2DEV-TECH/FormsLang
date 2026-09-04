"""apexlayout: the exported APEX page follows the geometry of the Forms screen.

Synthetic modules only. Every APEXlang keyword asserted here was accepted
by ``apex validate`` on APEX 26.1 before it went into the exporter.
"""

from __future__ import annotations

import json

from formslang.apexlang import (
    _grid_lines,
    _label_template,
    _lovs_text,
    _page_items,
    export_apexlang,
)
from formslang.apexlayout import Grid, build_layout, frame_captions
from formslang.model import (
    Block,
    Canvas,
    FormModule,
    Graphic,
    Item,
    RadioButton,
    Window,
)
from formslang.store import Store


def _module(items, canvases=None, **kw) -> FormModule:
    module = FormModule(
        name="M",
        canvases=canvases or [Canvas(name="CV", width=600, height=200)],
        blocks=[Block(name="B", items=items)],
        **kw,
    )
    return module


def _item(name, x, y, width=50, height=14, canvas="CV", **kw) -> Item:
    return Item(name=name, item_type="Text Item", canvas=canvas, x=x, y=y, width=width,
                height=height, **kw)


def _page_text(module) -> str:
    chunks, _ = _page_items(module, 1)
    return "\n".join(chunks)


def _grids(node) -> dict[str, Grid]:
    return {p.apex_name: p.grid for p in node.body}


# -- rows and columns -----------------------------------------------------------


def test_items_land_in_the_row_and_column_their_position_maps_to():
    """On a 600-unit canvas one grid column is 50 units: x=0 w=100 is column 1
    span 2. A second field packs right after it -- column 3, span 3 -- with
    no grid gap left for the 50 units of whitespace Forms drew between them;
    a lower item opens a new row."""
    module = _module([
        _item("A", 0, 20, width=100),
        _item("B", 150, 20, width=150),
        _item("C", 0, 60, width=600),
    ])
    layout = build_layout(module)
    grids = _grids(layout.roots[0])

    assert (grids["P1_A"].new_row, grids["P1_A"].column, grids["P1_A"].span) == (True, 1, 2)
    assert (grids["P1_B"].new_row, grids["P1_B"].new_column) == (False, True)
    assert (grids["P1_B"].column, grids["P1_B"].span) == (3, 3)
    assert (grids["P1_C"].new_row, grids["P1_C"].column, grids["P1_C"].span) == (True, 1, 12)

    text = _page_text(module)
    assert "startNewRow: true\n            column: 1\n            columnSpan: 2" in text
    assert "startNewRow: false\n            newColumn: true\n            column: 3" in text


def test_two_adjacent_narrow_controls_pack_into_neighbouring_columns():
    """Forms paints two 20-unit check boxes side by side, 5 units apart; each
    rounds down to a single grid column, and they pack into adjacent columns
    (1 then 2) rather than leaving a gap where Forms' whitespace would
    otherwise land."""
    module = _module([
        Item(name="A", item_type="Check Box", canvas="CV", x=0, y=20, width=20, height=14),
        Item(name="B", item_type="Check Box", canvas="CV", x=25, y=20, width=20, height=14),
    ])
    grids = _grids(build_layout(module).roots[0])

    assert (grids["P1_A"].new_row, grids["P1_A"].column, grids["P1_A"].span) == (True, 1, 1)
    assert (
        grids["P1_B"].new_row,
        grids["P1_B"].new_column,
        grids["P1_B"].column,
        grids["P1_B"].span,
    ) == (False, True, 2, 1)
    assert "newColumn: true" in _page_text(module)


def test_rows_are_clustered_by_vertical_overlap_not_by_exact_y():
    """A field two units lower than its neighbour is on the same row; one
    drawn a full line below is not."""
    module = _module([
        _item("A", 0, 20, height=14),
        _item("B", 100, 22, height=14),
        _item("C", 0, 40, height=14),
    ])
    grids = _grids(build_layout(module).roots[0])

    assert not grids["P1_B"].new_row
    assert grids["P1_C"].new_row


def test_grid_lines_write_only_the_keywords_each_placement_needs():
    assert _grid_lines(Grid(new_row=True, column=2, span=3)) == (
        "\n            startNewRow: true\n            column: 2\n            columnSpan: 3"
    )
    shared = _grid_lines(Grid(new_row=False, new_column=False, column=3, span=1))
    assert "newColumn: false" in shared and "column:" not in shared.replace("newColumn", "")
    assert _grid_lines(Grid(new_row=False, new_column=False, flow=True)) == (
        "\n            startNewRow: false\n            newColumn: false"
    )


# -- frames, captions, groups ---------------------------------------------------


def test_frames_become_sub_regions_nested_by_containment():
    outer = Graphic("FR_OUTER", "Frame", x=10, y=20, width=380, height=240, title="Outer")
    inner = Graphic("FR_INNER", "Frame", x=20, y=50, width=200, height=100, title="Inner")
    canvas = Canvas(name="CV", width=400, height=300, graphics=[outer, inner])
    module = _module([
        _item("Z", 10, 0),  # above every frame: the canvas region's own row
        _item("X", 30, 70),  # inside INNER
        _item("Y", 250, 30),  # inside OUTER only, on the row above INNER
    ], canvases=[canvas])
    layout = build_layout(module)
    root = layout.roots[0]

    assert [p.apex_name for p in root.body] == ["P1_Z"]
    assert [s.id for s in root.subs] == ["outer"]
    assert [p.apex_name for p in root.subs[0].body] == ["P1_Y"]
    assert [s.id for s in root.subs[0].subs] == ["inner"]
    assert [p.apex_name for p in root.subs[0].subs[0].body] == ["P1_X"]
    assert [r.id for r in layout.regions()] == ["cv", "outer", "inner"]

    text = _page_text(module)
    assert "region inner (" in text and '"FR_INNER"' in text and 'title: "Inner"' in text
    assert "parentRegion: @outer\n            slot: subRegions" in text
    assert "parentRegion: @cv\n            slot: subRegions" in text
    assert "region: @inner\n            slot: regionBody" in text  # P1_X


def test_a_rectangle_with_a_caption_on_its_top_edge_is_a_group_box():
    """The hand-drawn titled box: a Rectangle plus a Text sitting on its top
    line. A bare rectangle is decoration and makes no region."""
    graphics = [
        Graphic("RECT1", "Rectangle", x=10, y=20, width=200, height=80),
        Graphic("TXT1", "Text", x=20, y=20, width=60, height=12, text="Prazo (dias)",
                h_origin="Left", v_origin="Top"),
        Graphic("RECT2", "Rectangle", x=10, y=120, width=200, height=60),
    ]
    assert [(g.name, cap) for g, cap in frame_captions(graphics)] == [("RECT1", "Prazo (dias)")]

    canvas = Canvas(name="CV", width=400, height=300, graphics=graphics)
    layout = build_layout(_module([_item("A", 20, 40)], canvases=[canvas]))

    assert [s.id for s in layout.roots[0].subs] == ["prazo-dias"]
    assert layout.roots[0].subs[0].title == "Prazo (dias)"
    assert [p.apex_name for p in layout.roots[0].subs[0].body] == ["P1_A"]


def test_loose_items_below_a_frame_are_grouped_so_their_order_survives():
    """APEX renders a region's own items before its sub-regions, so items
    Forms drew *below* a frame would jump above it. They are wrapped in a
    chrome-less group placed after the frame instead."""
    frame = Graphic("FR", "Frame", x=10, y=10, width=380, height=60, title="Top")
    canvas = Canvas(name="CV", width=400, height=200, graphics=[frame])
    module = _module([
        _item("A", 20, 30),  # in the frame
        _item("B", 20, 100),
        _item("C", 100, 100),
    ], canvases=[canvas])
    root = build_layout(module).roots[0]

    assert root.body == []
    assert [s.id for s in root.subs] == ["top", "cv-row-1"]
    group = root.subs[1]
    assert group.template == "blank-with-attributes" and group.title == ""
    assert [p.apex_name for p in group.body] == ["P1_B", "P1_C"]
    assert "template: @/blank-with-attributes" in _page_text(module)


# -- canvases: toolbar, dialog, tabs -------------------------------------------------


def test_toolbar_flows_inline_right_above_its_window_content():
    button = Item(name="BT_SAVE", item_type="Push Button", canvas="TB", x=2, y=2, width=20,
                  height=20, label="Salvar")
    module = FormModule(
        name="M",
        canvases=[
            Canvas(name="CV", window_name="WI", canvas_type="Content", width=400, height=200),
            Canvas(name="TB", window_name="WI", canvas_type="Horizontal Toolbar", width=300,
                   height=24),
        ],
        blocks=[Block(name="B", items=[_item("A", 10, 10), button])],
        window_details={"WI": Window("WI", title="Cadastro", toolbar="TB")},
    )
    layout = build_layout(module)

    assert [r.id for r in layout.roots] == ["tb", "cv"]
    toolbar, content = layout.roots
    assert toolbar.template == "blank-with-attributes" and toolbar.flow and toolbar.title == ""
    assert content.template == "standard" and content.title == "Cadastro"
    assert toolbar.body[0].grid.flow

    text = _page_text(module)
    chunk = next(c for c in _page_items(module, 1)[0] if "button b-bt-save" in c)
    assert "region: @tb\n            slot: regionBody\n            startNewRow: true\n" in chunk
    assert "column:" not in chunk
    assert 'title: "Cadastro"' in text


def test_hidden_stacked_canvas_is_an_inline_dialog():
    stacked = Canvas(name="CV_AUD", canvas_type="Stacked", visible=False, width=200, height=100)
    module = _module([_item("A", 10, 10, canvas="CV_AUD")], canvases=[stacked])
    node = build_layout(module).roots[0]

    assert node.template == "inline-dialog"
    assert node.title == "Cv Aud"  # no window title: the canvas name, readable
    assert "SHOW_VIEW" in node.note
    assert "template: @/inline-dialog" in _page_text(module)


def test_tab_canvas_is_a_tabs_container_with_a_region_per_tab_page():
    tabs = Canvas(name="TABS", canvas_type="Tab", width=400, height=200,
                  tab_pages=["TP_GERAL", "TP_EXTRA"])
    module = _module([
        _item("A", 10, 10, canvas="TABS", tab_page="TP_GERAL"),
        _item("B", 10, 10, canvas="TABS", tab_page="TP_EXTRA"),
    ], canvases=[tabs])
    node = build_layout(module).roots[0]

    assert node.template == "tabs-container"
    assert [(s.id, s.slot, s.title) for s in node.subs] == [
        ("tp-geral", "tabs", "Tp Geral"),
        ("tp-extra", "tabs", "Tp Extra"),
    ]
    assert [p.apex_name for p in node.subs[1].body] == ["P1_B"]

    text = _page_text(module)
    assert "template: @/tabs-container" in text
    assert "parentRegion: @tabs\n            slot: tabs" in text


# -- hidden items, skipped objects, fallback -----------------------------------------


def test_invisible_and_canvasless_items_become_hidden_items_under_their_home_region():
    module = FormModule(
        name="M",
        canvases=[Canvas(name="CV", width=600, height=200)],
        blocks=[
            Block(name="B", items=[
                _item("A", 10, 10),
                _item("H1", 10, 30, visible=False),
                Item(name="H2", item_type="Text Item"),  # no canvas at all
            ]),
            Block(name="C", items=[Item(name="Q", item_type="Text Item")]),
        ],
    )
    layout = build_layout(module)
    root = layout.roots[0]

    assert [p.apex_name for p in root.body] == ["P1_A"]
    assert [p.apex_name for p in root.hidden] == ["P1_H1", "P1_H2"]
    assert [p.apex_name for p in layout.hidden] == ["P1_Q"]  # block C shows nothing

    chunks, _ = _page_items(module, 1)
    h1 = next(c for c in chunks if "pageItem P1_H1" in c)
    q = next(c for c in chunks if "pageItem P1_Q" in c)
    assert "type: hidden" in h1 and "region: @cv\n            slot: regionBody" in h1
    assert "type: hidden" in q and "slot: body" in q and "region:" not in q


def test_webutil_block_and_canvas_are_skipped_not_exported():
    module = FormModule(
        name="M",
        canvases=[
            Canvas(name="CV", width=600, height=200),
            Canvas(name="WEBUTIL_CANVAS", width=100, height=100),
        ],
        blocks=[
            Block(name="B", items=[_item("A", 10, 10)]),
            Block(name="WEBUTIL", items=[
                Item(name="WEBUTIL_FILE_TRANSFER", item_type="Bean Area",
                     canvas="WEBUTIL_CANVAS", x=0, y=0),
            ]),
        ],
    )
    layout = build_layout(module)

    assert [r.id for r in layout.regions()] == ["cv"]
    assert [p.apex_name for p in layout.placed()] == ["P1_A"]
    assert layout.hidden == []
    assert any("block WEBUTIL" in s for s in layout.skipped)
    assert any("canvas WEBUTIL_CANVAS" in s for s in layout.skipped)
    assert "WEBUTIL" not in _page_text(module)


def test_a_module_without_canvases_falls_back_to_one_region_per_block():
    module = FormModule(
        name="M",
        blocks=[Block(name="ORDERS", records_displayed=5, items=[
            Item(name="A", item_type="Text Item"),
            Item(name="H", item_type="Text Item", visible=False),
        ])],
    )
    layout = build_layout(module)
    node = layout.roots[0]

    assert (node.id, node.title, node.flow) == ("orders", "Orders", True)
    assert [p.apex_name for p in node.body] == ["P1_A"] and node.body[0].grid.flow
    assert [p.apex_name for p in node.hidden] == ["P1_H"]
    assert node.tabular == {"ORDERS": 5}
    assert "Forms shows 5 records of block ORDERS" in _page_text(module)


def test_tabular_note_names_the_block_and_honours_items_display():
    module = FormModule(
        name="M",
        canvases=[Canvas(name="CV", width=600, height=200)],
        blocks=[Block(name="GRID", records_displayed=6, items=[
            _item("A", 10, 10),
            _item("AUDIT", 10, 100, items_displayed=1),
        ])],
    )
    node = build_layout(module).roots[0]

    assert node.tabular == {"GRID": 6}
    assert node.records == 6


# -- labels, width, item types, LOVs -----------------------------------------------


def test_label_template_follows_where_forms_draws_the_caption():
    def template(kind="textField", *, label_span=3, **kw):
        return _label_template(Item(name="X", **kw), kind, label_span=label_span)

    # Start, Forms' default edge: a label left of the field, as on the screen
    assert template(prompt="X") == "optional"
    assert template(prompt="X", required=True) == "required"
    assert template(prompt="X", prompt_edge="Top") == "optional-above"
    assert template(prompt="X", required=True, prompt_edge="Top") == "required-above"
    # Universal Theme has no label right of or below a field: it floats
    assert template(prompt="X", prompt_edge="End") == "optional-floating"
    # a check box's caption is the control: never above or left
    assert template("checkbox", prompt="X", prompt_edge="Top") == "optional-floating"
    assert template("checkbox", label="Ativo") == "optional-floating"
    # Display Only has no Value Required: the optional template
    assert template("displayOnly", prompt="X", required=True) == "optional"
    assert template(prompt="X", prompt_display="Hidden") == "hidden"
    # no prompt and no label: Forms shows nothing, so neither does APEX
    assert template() == "hidden"
    # a label left of the field with nowhere to put it (the row was too
    # crowded to leave it a labelColumnSpan) floats instead of overflowing
    assert template(prompt="X", label_span=0) == "optional-floating"


def test_a_prompt_left_of_the_field_claims_its_room_on_the_grid():
    """"Código" is 6 characters of a 5-point cell plus a 5-point attachment
    offset: 35 points of room left of a 100-point field at x=100. The pair
    spans 65..200, 135 points wide -- on a 600-point canvas (50 points a
    column) that is a span of 3; alone on its row it packs into column 1.
    The label wants round(35/135*12) = 3 twelfths of the cell -- but
    _reconcile_label caps it at span - 1 = 2, leaving the field a column of
    its own (APEX rejects labelColumnSpan >= columnSpan at render time)."""
    module = _module(
        [_item("A", 100, 20, width=100, prompt="Código", prompt_offset=5)],
        coordinate_system="Real", coordinate_unit="Point",
        char_cell_width=5, char_cell_height=14,
    )
    placed = build_layout(module).roots[0].body[0]

    assert (placed.caption, placed.side, placed.align) == ("Código", "left", "right")
    assert placed.bounds() == (65, 20, 135, 14)
    assert (placed.grid.column, placed.grid.span, placed.label_span) == (1, 3, 2)
    text = _page_text(module)
    assert "template: @/optional\n" in text
    assert "labelColumnSpan: 2" in text and "alignment: right" in text


def test_boilerplate_text_before_an_uncaptioned_field_is_its_prompt_the_rest_static():
    """Old screens caption fields with Text graphics: a text ending just
    before a field that has no prompt is read as that prompt (the pair's
    room starts where the text does), one sitting right above such a field
    as a prompt above it. Any other text is a chrome-less static region
    placed by its own geometry -- here a bold heading right above a field,
    which is a heading and keeps its weight rather than becoming a label."""
    canvas = Canvas(name="CV", width=600, height=200, graphics=[
        Graphic("T_NOME", "Text", x=10, y=20, width=40, height=14, text="Nome"),
        Graphic("T_TITULO", "Text", x=10, y=60, width=200, height=14,
                text="Dados do produto", text_bold=True),
        Graphic("T_QTDE", "Text", x=300, y=63, width=30, height=14, text="Qtde."),
    ])
    items = [
        _item("NOME", 55, 20, width=100),
        _item("OBS", 10, 80, width=200),
        _item("QTDE", 300, 80, width=60),
    ]
    layout = build_layout(_module(items, canvases=[canvas]))
    root = layout.roots[0]
    nome, obs, qtde = (p for p in layout.placed() if p.item.name in {"NOME", "OBS", "QTDE"})

    assert (nome.caption, nome.side, nome.bounds()) == ("Nome", "left", (10, 20, 145, 14))
    assert "boilerplate text T_NOME, drawn beside" in nome.note
    assert (qtde.caption, qtde.side, qtde.bounds()) == ("Qtde.", "above", (300, 80, 60, 14))
    assert "boilerplate text T_QTDE, drawn above" in qtde.note
    assert (obs.caption, obs.side) == ("", "none")
    heading = root.subs[0]
    assert (heading.text, heading.text_bold) == ("Dados do produto", True)
    assert (heading.grid.column, heading.grid.span) == (1, 4)
    assert root.subs[1].id == "cv-row-1"  # OBS, drawn below the heading, stays below it
    text = _page_text(_module(items, canvases=[canvas]))
    assert 'label: "Nome"' in text and 'label: "Qtde."' in text
    assert "template: @/optional-above" in text and text.count("htmlCode") == 1
    assert "<p><strong>Dados do produto</strong></p>" in text


def test_an_item_the_screen_captions_with_nothing_gets_a_hidden_label():
    """No prompt, no label: Forms shows nothing beside the field, so APEX
    hides the label instead of inventing one from the item name -- and says
    ``labelColumnSpan: 0`` outright. Universal Theme's Hidden template still
    puts the (invisible) label on the grid, and an unset span falls back to
    the page template's default of 2, which a 2-column field cannot fit
    (``LABEL_COLUMN_SPAN_TOO_BIG`` at render time)."""
    text = _page_text(_module([_item("DSP_DESCRICAO", 100, 20, width=100)]))

    assert 'label: "Dsp Descricao"' in text and "template: @/hidden" in text
    assert "columnSpan: 2\n            labelColumnSpan: 0" in text
    assert "no caption shown" in text and "label template is hidden" in text


def test_text_field_width_is_written_in_characters_of_the_module_cell():
    module = _module([_item("A", 10, 10, width=61)], coordinate_system="Real",
                     coordinate_unit="Point", char_cell_width=5, char_cell_height=14)
    layout = build_layout(module)

    assert layout.chars(61) == 12
    assert "width: 12" in _page_text(module)

    cells = _module([_item("A", 10, 10, width=20)], coordinate_system="Character")
    assert build_layout(cells).chars(20) == 20

    # No char-cell metadata and no coordinate unit at all: fall back to the
    # same per-unit estimate build_layout uses for prompt room, rather than
    # leaving the field with no ``width`` -- a text field should never
    # default to APEX's 100%-of-cell stretch just because the .fmb recorded
    # no character cell. ``chars`` still returns None with nothing to
    # convert in the first place.
    unknown = _module([_item("A", 10, 10, width=61)])
    unknown_layout = build_layout(unknown)
    assert unknown_layout.chars(61) == 12
    assert unknown_layout.chars(None) is None
    assert "width: 12" in _page_text(unknown)


def test_list_item_and_radio_group_get_shared_static_lovs_from_the_fmb_choices():
    module = _module([
        Item(name="POS", item_type="List Item", canvas="CV", x=10, y=10, width=100, height=16,
             choices=["Indiferente", "Vertical"]),
        Item(name="TIPO", item_type="Radio Group", canvas="CV", x=10, y=40, width=100,
             height=16, radio_buttons=[
                 RadioButton("RB_S", "Sim", x=10, y=40, width=40, height=14),
                 RadioButton("RB_N", "Não", x=60, y=40, width=40, height=14),
             ]),
    ])
    layout = build_layout(module)

    assert [(lov.id, lov.name, lov.entries) for lov in layout.lovs] == [
        ("lov-b-pos", "B_POS", [("Indiferente", "Indiferente"), ("Vertical", "Vertical")]),
        ("lov-b-tipo", "B_TIPO", [("Sim", "RB_S"), ("Não", "RB_N")]),
    ]
    lovs = _lovs_text(layout.lovs)
    assert "lov lov-b-tipo (\n    name: B_TIPO" in lovs
    assert "location: staticValues" in lovs
    assert 'display: "Sim"\n        return: "RB_S"' in lovs

    chunks, _ = _page_items(module, 1)
    pos = next(c for c in chunks if "pageItem P1_POS" in c)
    tipo = next(c for c in chunks if "pageItem P1_TIPO" in c)
    assert "type: selectList" in pos
    assert "lov: @lov-b-pos\n            displayNullValue: false" in pos
    assert "type: radioGroup" in tipo and "lov: @lov-b-tipo" in tipo
    assert "displayNullValue" not in tipo


def test_export_appends_the_static_lovs_to_lovs_apx_with_lf_line_endings(tmp_path):
    module = _module([
        Item(name="POS", item_type="List Item", canvas="CV", x=10, y=10, width=100, height=16,
             choices=["Sim", "Não"]),
    ])
    store = Store(tmp_path / "M.session.db")
    store.init_session(module.name, "M.xml")
    try:
        result = export_apexlang(store, module, tmp_path / "export", {"alias": "lovs-demo"})
    finally:
        store.close()

    lovs = (result.project / "shared-components" / "lovs.apx").read_bytes()
    assert b"\r\n" not in lovs
    assert b"lov lov-b-pos (" in lovs
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["layout"]["regions"][0]["id"] == "cv"
    assert manifest["layout"]["static_lovs"][0]["id"] == "lov-b-pos"
