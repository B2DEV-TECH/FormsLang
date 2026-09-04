"""formui: read-only Forms UI vs. APEX default-mapping preview."""

from __future__ import annotations

from formslang.formui import _css_color, render_html, write_report
from formslang.model import (
    Block,
    Canvas,
    FormModule,
    Graphic,
    Item,
    RadioButton,
    VisualAttribute,
    Window,
)
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
    item = Item(name="IMG1", item_type="Image")
    module = FormModule(name="M", blocks=[Block(name="B", items=[item])])

    html = render_html(module)

    assert "approx" in html


def test_radio_group_and_list_item_are_confirmed_mappings():
    """Both keywords were accepted by apex validate; the preview must not
    call them approximations any more."""
    items = [Item(name="RG1", item_type="Radio Group"), Item(name="LI1", item_type="List Item")]
    module = FormModule(name="M", blocks=[Block(name="B", items=items)])

    html = render_html(module)

    assert "approx" not in html
    assert "radioGroup" in html and "selectList" in html


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


def _point_module(**item_kw) -> FormModule:
    canvas = Canvas(name="CV", width=780, height=447)
    item = Item(name="CODIGO", item_type="Text Item", canvas="CV", x=67, y=31, width=61, height=15,
                **item_kw)
    module = FormModule(name="M", canvases=[canvas], blocks=[Block(name="B", items=[item])])
    module.coordinate_system, module.coordinate_unit = "Real", "Point"
    return module


def test_point_geometry_is_drawn_in_pixels_not_shrunk_to_three_quarters():
    """A 780pt canvas is 1040px wide. Drawing the raw number as pixels was the
    cramped, unreadable Forms mock."""
    html = render_html(_point_module())

    assert "width:1040px;height:596px" in html
    # 67pt,31pt / 61x15pt -> 89px,41px / 81x20px
    assert "left:89px;top:41px;width:81px;height:20px" in html
    assert "1 point = 1.33 px" in html


def test_prompt_is_painted_outside_the_field_on_its_attachment_edge():
    html = render_html(_point_module(prompt="Código", prompt_edge="Start"))

    assert '<div class="f-prompt start"' in html
    # the field itself stays empty -- the prompt is not stuffed inside the box
    assert '>Código</div>' in html
    assert 'title="CODIGO · Text Item · x 67 y 31 w 61 h 15"></div>' in html


def test_prompt_defaults_to_the_start_edge_left_of_the_field():
    """Forms2XML omits PromptAttachmentEdge at Forms' default, Start: the
    prompt sits to the LEFT of the field, top-aligned with it. Defaulting to
    Top painted every label over the field above."""
    html = render_html(_point_module(prompt="Código"))

    assert '<div class="f-prompt start"' in html
    assert "right:951px" in html  # anchored on the field's left edge: 1040 - 89
    assert "top:41px" in html


def test_prompt_on_the_top_edge_is_anchored_above_the_field():
    html = render_html(_point_module(prompt="Código", prompt_edge="Top"))

    assert '<div class="f-prompt top"' in html
    assert "bottom:555px" in html  # grows upward from the field's top: 596 - 41


def test_prompt_alignment_and_offsets_follow_the_fmb():
    """PromptAlign=Center with a -5pt align offset and a 3pt attachment gap."""
    html = render_html(_point_module(
        prompt="Qtd", prompt_edge="Top", prompt_align="Center", prompt_align_offset=-10,
        prompt_offset=3, prompt_color="darkblue", prompt_font_size=8, prompt_bold=True,
    ))

    assert "left:116px" in html  # 89 + 81//2 - 13
    assert "translateX(-50%)" in html
    assert "bottom:559px" in html  # 555 + 4
    assert 'font:bold 10.7px/1.15 "Arial"' in html
    assert "color:darkblue" in html


def test_a_negative_attachment_offset_is_drawn_touching_the_field():
    """Forms pulls the prompt into the field by its own font metrics; without
    them the honest rendering is a zero gap, not a prompt painted over the box."""
    html = render_html(_point_module(prompt="Código", prompt_offset=-12))

    assert "right:951px" in html


def test_multi_line_prompt_is_kept_on_the_forms_side_and_one_line_in_apex():
    html = render_html(_point_module(prompt="Empilhamento\nMáx."))

    assert ">Empilhamento\nMáx.</div>" in html
    assert '<span class="lbl">Empilhamento Máx.</span>' in html


def test_a_hidden_prompt_display_style_is_not_painted():
    html = render_html(_point_module(prompt="Código", prompt_display="Hidden"))

    assert "f-prompt" not in html.split("<h2>Forms UI", 1)[1]


def test_pixel_module_is_drawn_one_to_one(sample_xml):
    module = parse_xml(sample_xml)  # no <Coordinate> -> pixels
    html = render_html(module)

    assert "width:640px;height:480px" in html
    assert "left:20px;top:20px;width:100px;height:17px" in html
    assert "declares no coordinate system" in html


def test_hidden_items_are_not_drawn_but_are_listed_and_flagged_on_the_apex_side():
    module = _point_module(visible=False)
    html = render_html(module)

    assert 'class="f-item' not in html
    assert "hidden in Forms (Visible=false) and are not drawn: CODIGO" in html
    assert "hidden in Forms</span>" in html
    assert "Hidden in Forms" in html  # overview card


def test_tabular_blocks_paint_one_instance_per_record_and_say_the_export_is_single_record():
    module = _point_module()
    module.blocks[0].records_displayed = 3
    html = render_html(module)

    assert html.count("f-instance") == 2
    assert "record 3" in html
    assert "Forms shows 3 records of block B at once here (tabular)" in html


def test_items_display_overrides_the_block_record_count():
    """The audit fields of a 6-record grid block carry ItemsDisplay=1: Forms
    paints them once. Painting six ran them over the neighbouring block."""
    module = _point_module(items_displayed=1)
    module.blocks[0].records_displayed = 6
    html = render_html(module)

    assert "f-instance" not in html
    assert html.count('class="f-item f-text') == 1


def test_item_look_comes_from_the_fmb_and_its_visual_attribute():
    module = _point_module(visual_attribute="VA_AZUL", bevel="Inset")
    module.visual_attributes["VA_AZUL"] = VisualAttribute(
        "VA_AZUL", fg_color="white", bg_color="r0g25b50", font_size=9, font_bold=True
    )
    html = render_html(module)

    assert 'class="f-item f-text b-inset"' in html
    assert "background:#004080" in html
    assert "color:white" in html
    assert 'font:bold 12px/1.15 "Arial"' in html


def test_a_transparent_fill_pattern_paints_no_background():
    html = render_html(_point_module(bg_color="white", fill="transparent", enabled=False))

    assert "background:white" not in html
    assert "f-off" in html


def test_the_current_record_wears_its_visual_attribute_on_the_first_instance_only():
    module = _point_module(record_visual_attribute="VA_AZUL")
    module.blocks[0].records_displayed = 3
    module.visual_attributes["VA_AZUL"] = VisualAttribute(
        "VA_AZUL", fg_color="white", bg_color="r0g25b50"
    )
    html = render_html(module)

    assert html.count("background:#004080") == 1


def test_css_color_understands_the_forms_colour_names():
    assert _css_color("gray20") == "#CCCCCC"
    assert _css_color("r0g25b50") == "#004080"
    assert _css_color("r255g128b0") == "#FF8000"
    assert _css_color("darkblue") == "darkblue"
    assert _css_color("canvas") == ""
    assert _css_color("") == ""


def test_check_box_and_button_use_the_forms_label_on_both_sides():
    """Forms keeps a control's caption in Label, not Prompt; showing the
    internal name title-cased ("Atsf 101Ender Pick") was the ugly APEX list."""
    check = Item(name="ATSF_101ENDER_PICK", item_type="Check Box", canvas="CV",
                 x=10, y=10, width=80, height=14, label="Ender. Pick")
    button = Item(name="BT_CONFIRMA", item_type="Push Button", canvas="CV",
                  x=10, y=40, width=60, height=18, label="Confirmar")
    canvas = Canvas(name="CV", width=200, height=100)
    module = FormModule(name="M", canvases=[canvas], blocks=[Block(name="B", items=[check, button])])

    html = render_html(module)

    assert "Atsf 101Ender Pick" not in html
    assert html.count("Ender. Pick") == 2  # Forms mock + APEX check box
    assert html.count("Confirmar") == 2  # Forms mock + APEX button in its own row
    assert 'class="a-btn"' in html


def test_iconic_button_shows_a_glyph_not_its_label():
    button = Item(name="BT_EXIT", item_type="Push Button", canvas="CV", x=10, y=2,
                  width=20, height=20, label="Sair", iconic=True, icon_name="exit")
    canvas = Canvas(name="CV", canvas_type="Horizontal Toolbar", width=200, height=24)
    module = FormModule(name="M", canvases=[canvas], blocks=[Block(name="B", items=[button])])

    html = render_html(module)

    assert 'class="f-item f-button b-raised f-icon"' in html
    assert ">⏻</div>" in html
    assert ">Sair</div>" not in html
    assert 'class="f-canvas f-toolbar"' in html


def test_list_and_radio_choices_are_painted_on_the_forms_side():
    lst = Item(name="POS", item_type="List Item", canvas="CV", x=10, y=10, width=80, height=14,
               choices=["Indiferente", "Vertical"])
    radio = Item(name="TIPO", item_type="Radio Group", canvas="CV", x=10, y=40, width=160, height=18,
                 choices=["Gancheira", "Estante"])
    canvas = Canvas(name="CV", width=200, height=100)
    module = FormModule(name="M", canvases=[canvas], blocks=[Block(name="B", items=[lst, radio])])

    html = render_html(module)

    assert 'class="f-item f-list b-lowered"' in html and ">Indiferente</div>" in html
    assert 'class="f-item f-radio b-none"' in html and "<i></i>Gancheira <i></i>Estante" in html


def test_radio_buttons_with_their_own_geometry_are_painted_where_the_fmb_puts_them():
    """A Radio Group's box is never painted -- only its buttons, each at its place."""
    radio = Item(
        name="TIPO", item_type="Radio Group", canvas="CV", x=10, y=40, width=160, height=18,
        choices=["Sim", "Não"],
        radio_buttons=[
            RadioButton("RB_S", "Sim", x=10, y=40, width=40, height=14),
            RadioButton("RB_N", "Não", x=60, y=40, width=40, height=14),
        ],
    )
    canvas = Canvas(name="CV", width=200, height=100)
    module = FormModule(name="M", canvases=[canvas], blocks=[Block(name="B", items=[radio])])

    html = render_html(module)

    assert html.count('class="f-item f-radio b-none"') == 2
    assert "left:60px;top:40px;width:40px;height:14px" in html
    assert "<i></i>Não</div>" in html
    assert "width:160px" not in html  # the group's own box is not drawn


def test_boilerplate_is_painted_under_the_items():
    canvas = Canvas(name="CV", width=780, height=447, bg_color="gray20", graphics=[
        Graphic("FRAME1", "Frame", x=10, y=20, width=300, height=100, bevel="Raised", fill="none",
                title="Unidades", title_align="Center", title_size=9, title_bold=True,
                title_color="darkblue"),
        Graphic("TEXT1", "Text", x=100, y=50, width=60, height=12, text="  Cubagem  ",
                h_origin="Center", v_origin="Center", text_size=9, text_bold=True,
                text_color="darkblue", fill="", fill_color="gray20"),
        Graphic("LINE1", "Line", x=0, y=200, width=400, height=0),
        Graphic("IMG1", "Image", x=5, y=5, width=40, height=20, text="logo.gif"),
    ])
    module = FormModule(name="M", canvases=[canvas])
    module.coordinate_system, module.coordinate_unit = "Real", "Point"

    html = render_html(module)

    assert 'class="f-g g-frame b-raised"' in html
    assert ">Unidades</span>" in html and "left:50%;transform:translateX(-50%)" in html
    assert "background:#CCCCCC" in html  # the title masks the frame line in canvas grey
    # Text is anchored on its centre: 133px - 40, 67px - 8.
    assert 'class="f-g g-text" style="left:93px;top:59px;width:80px;height:16px' in html
    assert ">  Cubagem  </div>" in html
    assert 'class="f-g g-line-h" style="left:0px;top:267px;width:533px;height:2px' in html
    assert 'class="f-g g-image"' in html and ">logo.gif</div>" in html
    assert "4 boilerplate object(s)" in html


def test_window_chrome_and_toolbar_wrap_the_content_canvas():
    button = Item(name="BT_TB", item_type="Push Button", canvas="TB", x=2, y=2, width=20,
                  height=20, iconic=True, icon_name="save")
    field = Item(name="CODIGO", item_type="Text Item", canvas="CV", x=10, y=10, width=60,
                 height=14)
    module = FormModule(
        name="M",
        canvases=[
            Canvas(name="CV", window_name="WI", canvas_type="Content", width=400, height=200),
            Canvas(name="TB", window_name="WI", canvas_type="Horizontal Toolbar", width=300,
                   height=24),
            Canvas(name="CV_ST", window_name="WI", canvas_type="Stacked", visible=False,
                   width=100, height=50),
        ],
        blocks=[Block(name="B", items=[field, button])],
        window_details={"WI": Window("WI", title="Unidade x Produto", toolbar="TB")},
    )

    html = render_html(module)

    assert '<div class="f-titlebar"><span>Unidade x Produto</span>' in html
    assert "toolbar TB on top" in html
    assert "<b>TB</b>" not in html  # docked in its window, not an entity of its own
    assert "BT_TB" in html and 'class="f-canvas f-toolbar" style="width:400px' in html
    assert "hidden until raised (Visible=false)" in html


def test_apex_side_puts_the_item_in_the_grid_cell_its_geometry_maps_to():
    """The canvas is the region; alone on its row, a 61pt field on a 780pt
    canvas (65pt a column) packs into column 1, one column wide. With no
    prompt in Forms there is no label either: the template is hidden."""
    module = _point_module()
    html = render_html(module)
    apex = html.split("<h2>APEX preview", 1)[1]

    assert html.count('<details class="a-region" open>') == 1
    assert html.count('class="a-item"') == 1
    assert 'style="grid-column:1/span 1"' in apex
    assert '<span class="lbl">' not in apex and "no caption in Forms: label hidden" in apex
    assert '<div class="a-field">' in apex


def test_apex_side_puts_a_start_prompt_left_of_the_field_with_the_prompts_room():
    """"Código" on the Start edge is 6 characters of a 5pt cell: 30pt left of
    the field, so the pair starts at x=37 (column 1) and the label wants
    round(30/91*12) = 4 twelfths of the cell -- but the field only got a
    columnSpan of 1, no room to also carve out a label column, so it floats
    instead of overflowing (APEX rejects labelColumnSpan >= columnSpan)."""
    apex = render_html(_point_module(prompt="Código")).split("<h2>APEX preview", 1)[1]

    assert 'style="grid-column:1/span 1"' in apex
    assert '<div class="a-field"><span class="lbl">Código</span>' in apex
    assert '<div class="a-left"' not in apex


def test_apex_side_draws_boilerplate_text_as_a_static_region_where_it_was_drawn():
    canvas = Canvas(name="CV", width=600, height=200, graphics=[
        Graphic("T_TITULO", "Text", x=10, y=10, width=200, height=14,
                text="Dados do produto", text_bold=True),
    ])
    items = [
        Item(name="NOME", item_type="Text Item", canvas="CV", x=10, y=40, width=200, height=14,
             prompt="Nome", prompt_edge="Top"),
    ]
    module = FormModule(name="M", canvases=[canvas], blocks=[Block(name="B", items=items)])
    apex = render_html(module).split("<h2>APEX preview", 1)[1]

    assert (
        '<div class="a-region a-text" title="region dados-do-produto · text T_TITULO on '
        'canvas CV"><strong>Dados do produto</strong></div>'
    ) in apex


def test_apex_side_draws_the_export_tree_frames_dialogs_and_hidden_items():
    """Frame -> sub-region, hidden stacked canvas -> inline dialog, an
    invisible item -> a hidden chip under its block's home region."""
    items = [
        Item(name="CODIGO", item_type="Text Item", canvas="CV", x=20, y=30, width=100, height=14,
             prompt="Código", prompt_edge="Top", required=True),
        Item(name="NOME", item_type="Text Item", canvas="CV", x=140, y=30, width=200, height=14),
        Item(name="OCULTO", item_type="Text Item", canvas="CV", visible=False),
        Item(name="OBS", item_type="Text Item", canvas="CV_ST", x=10, y=10, width=100, height=14),
    ]
    module = FormModule(
        name="M",
        canvases=[
            Canvas(name="CV", window_name="WI", width=400, height=200, graphics=[
                Graphic("FR_DADOS", "Frame", x=10, y=10, width=380, height=60, title="Dados"),
            ]),
            Canvas(name="CV_ST", window_name="WI", canvas_type="Stacked", visible=False,
                   width=200, height=100),
        ],
        blocks=[Block(name="B", items=items)],
        window_details={"WI": Window("WI", title="Cadastro")},
    )

    html = render_html(module)
    apex = html.split("<h2>APEX preview", 1)[1]

    assert "<span>Cadastro</span>" in apex and "<span>Dados</span>" in apex
    assert 'class="a-region a-dialog"' in apex and "inline dialog" in apex
    assert '<div class="a-above"><span class="lbl">Código<em class="req">*</em></span>' in apex
    assert "P1_OCULTO &middot; hidden in Forms</span>" in apex
    assert "APEX regions" in html
