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


def test_multiline_is_read_and_defaults_to_false(tmp_path, sample_xml):
    """``MultiLine="true"`` decides textarea-vs-field on the APEX side, so
    the parser has to carry it; an item without the attribute is one line."""
    xml = sample_xml.read_text(encoding="utf-8").replace(
        'Name="CUSTOMER" ItemType="Text Item"',
        'Name="CUSTOMER" ItemType="Text Item" MultiLine="true"',
    )
    path = tmp_path / "MULTI_fmb.xml"
    path.write_text(xml, encoding="utf-8")
    mod = parse_xml(path)
    by_name = {i.name: i for i in mod.all_items}
    assert by_name["CUSTOMER"].multi_line is True
    assert by_name["ORDER_ID"].multi_line is False


def test_item_lov_name_is_read_case_correctly(sample_xml):
    """Forms2XML's real attribute is ``LovName``, not ``LOVName`` -- a case
    typo here matches nothing on a real export and silently drops the
    item's LOV edge in depgraph.py."""
    mod = parse_xml(sample_xml)
    customer = next(i for i in mod.all_items if i.name == "CUSTOMER")
    assert customer.lov_name == "LOV_CUSTOMER"


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


GEOMETRY_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Module xmlns="http://xmlns.oracle.com/Forms" version="12.2.1.4.0">
  <FormModule Name="GEO">
    <Coordinate CharacterCellWidth="5" RealUnit="Point" CharacterCellHeight="14" CoordinateSystem="Real"/>
    <Block Name="B" RecordsDisplayCount="6">
      <Item Name="CODIGO" ItemType="Text Item" CanvasName="CV" XPosition="67" YPosition="31"
            Width="61" Height="15" Prompt="C&#243;digo" PromptAttachmentEdge="Start"
            PromptAttachmentOffset="-12" DistanceBetweenRecords="2" TabPageName="TP1"
            ItemsDisplay="1" PromptAlign="Center" PromptAlignOffset="-5"
            PromptDisplayStyle="First Record" PromptForegroundColor="darkblue"
            PromptFontSize="900" PromptFontWeight="Bold" Bevel="Inset" FillPattern="transparent"
            BackColor="white" ForegroundColor="black" FontName="Tahoma" FontSize="800"
            FontWeight="Bold" VisualAttributeName="VA_BRANCO"
            RecordVisualAttributeGroupName="VA_AZUL" Enabled="false" Justification="Right"/>
      <Item Name="EMPILHA" ItemType="Text Item" CanvasName="CV"
            Prompt="Empilhamento&amp;#10;M&#225;x."/>
      <Item Name="BT_SAIR" ItemType="Push Button" CanvasName="CV" Iconic="true" IconName="exit"
            Label="Sair"/>
      <Item Name="CHK_ATIVO" ItemType="Check Box" CanvasName="CV" Label="Ativo"/>
      <Item Name="ID_OCULTO" ItemType="Text Item" CanvasName="CV" Visible="false"/>
      <Item Name="POSICAO" ItemType="List Item" CanvasName="CV">
        <ListItemElement Index="1" Name="Indiferente" Value="I"/>
        <ListItemElement Index="2" Name="Vertical" Value="V"/>
      </Item>
      <Item Name="TIPO" ItemType="Radio Group" CanvasName="CV">
        <RadioButton Name="RB_G" Label="Gancheira" Value="G" XPosition="10" YPosition="40"
                     Width="50" Height="14"/>
        <RadioButton Name="RB_E" Label="Estante" Value="E"/>
      </Item>
    </Block>
    <Canvas Name="CV" CanvasType="Tab" Width="780" Height="447" WindowName="WI"
            BackColor="gray20" Bevel="Raised">
      <Graphics Name="FRAME1" GraphicsType="Frame" XPosition="10" YPosition="20" Width="300"
                Height="100" Bevel="Raised" FillPattern="none" FrameTitle="Unidades"
                FrameTitleAlign="Center" FrameTitleFontSize="900" FrameTitleFontWeight="Bold"
                FrameTitleForegroundColor="darkblue"/>
      <Graphics Name="TEXT1" GraphicsType="Text" XPosition="100" YPosition="50" Width="60"
                Height="12" HorizontalOrigin="Center" VerticalOrigin="Center" FillPattern=""
                BackColor="gray20">
        <CompoundText>
          <TextSegment Text="  Cubagem  " FontSize="900" FontWeight="Bold"
                       ForegroundColor="darkblue"/>
        </CompoundText>
      </Graphics>
      <Graphics Name="LINE1" GraphicsType="Line" XPosition="0" YPosition="200" Width="400"
                Height="0"/>
      <Graphics Name="IMG1" GraphicsType="Image" ImageFilename="logo.gif" Width="40" Height="20"/>
      <TabPage Name="TP1"/>
      <TabPage Name="TP2"/>
    </Canvas>
    <Canvas Name="CV_ST" CanvasType="Stacked" Visible="false" Width="200" Height="100"/>
    <VisualAttribute Name="VA_AZUL" ForegroundColor="white" BackColor="r0g25b50" FontName="Arial"
                     FontSize="900" FontWeight="Bold"/>
    <Window Name="WI" Title="Unidade x Produto" Width="780" Height="447"
            HorizontalToolbarCanvasName="TB" PrimaryCanvas="CV"/>
  </FormModule>
</Module>
"""


def test_coordinate_unit_and_the_ui_attributes_the_preview_needs(tmp_path):
    """Forms2XML positions everything in the module's <Coordinate> unit -- points
    for most real modules -- and keeps a control's caption in Label, not Prompt.
    A preview that ignored either drew every canvas three quarters too small and
    every check box under its internal name."""
    path = tmp_path / "GEO_fmb.xml"
    path.write_text(GEOMETRY_XML, encoding="utf-8")
    mod = parse_xml(path)

    assert (mod.coordinate_system, mod.coordinate_unit) == ("Real", "Point")
    assert (mod.char_cell_width, mod.char_cell_height) == (5, 14)

    by_name = {it.name: it for it in mod.all_items}
    codigo = by_name["CODIGO"]
    assert codigo.prompt == "Código"
    assert (codigo.prompt_edge, codigo.prompt_offset) == ("Start", -12)
    assert (codigo.records_distance, codigo.tab_page) == (2, "TP1")
    assert codigo.visible is True

    assert by_name["CHK_ATIVO"].label == "Ativo"
    assert by_name["ID_OCULTO"].visible is False
    assert by_name["POSICAO"].choices == ["Indiferente", "Vertical"]
    assert by_name["TIPO"].choices == ["Gancheira", "Estante"]
    assert mod.canvases[0].tab_pages == ["TP1", "TP2"]


def test_the_look_the_preview_paints_is_read_but_fenced_off(tmp_path):
    """Everything :mod:`formslang.formui` needs to draw the screen the way
    Forms does -- instance counts, prompt placement, fonts, colours, bevels,
    boilerplate, visual attributes, window chrome -- and nothing else uses."""
    path = tmp_path / "GEO_fmb.xml"
    path.write_text(GEOMETRY_XML, encoding="utf-8")
    mod = parse_xml(path)
    by_name = {it.name: it for it in mod.all_items}

    codigo = by_name["CODIGO"]
    assert codigo.items_displayed == 1
    assert (codigo.prompt_align, codigo.prompt_align_offset) == ("Center", -5)
    assert codigo.prompt_display == "First Record"
    assert (codigo.prompt_color, codigo.prompt_font_size, codigo.prompt_bold) == ("darkblue", 9, True)
    assert (codigo.bevel, codigo.fill) == ("Inset", "transparent")
    assert (codigo.bg_color, codigo.fg_color) == ("white", "black")
    assert (codigo.font_name, codigo.font_size, codigo.font_bold) == ("Tahoma", 8, True)
    assert (codigo.visual_attribute, codigo.record_visual_attribute) == ("VA_BRANCO", "VA_AZUL")
    assert (codigo.enabled, codigo.justification) == (False, "Right")
    # Forms2XML double-escapes line breaks inside prompts: &amp;#10; -> a real newline.
    assert by_name["EMPILHA"].prompt == "Empilhamento\nMáx."
    sair = by_name["BT_SAIR"]
    assert (sair.iconic, sair.icon_name, sair.label) == (True, "exit", "Sair")
    buttons = by_name["TIPO"].radio_buttons
    assert [(b.name, b.label) for b in buttons] == [("RB_G", "Gancheira"), ("RB_E", "Estante")]
    assert (buttons[0].x, buttons[0].y, buttons[0].width, buttons[0].height) == (10, 40, 50, 14)
    assert buttons[1].x is None

    cv = mod.canvases[0]
    assert (cv.window_name, cv.bg_color, cv.bevel, cv.visible) == ("WI", "gray20", "Raised", True)
    assert [(g.name, g.kind) for g in cv.graphics] == [
        ("FRAME1", "Frame"), ("TEXT1", "Text"), ("LINE1", "Line"), ("IMG1", "Image"),
    ]
    frame, text, line, image = cv.graphics
    assert (frame.x, frame.y, frame.width, frame.height) == (10, 20, 300, 100)
    assert (frame.bevel, frame.fill, frame.title, frame.title_align) == (
        "Raised", "none", "Unidades", "Center",
    )
    assert (frame.title_size, frame.title_bold, frame.title_color) == (9, True, "darkblue")
    assert text.text == "  Cubagem  "  # padding kept: it is how the text masks a frame line
    assert (text.text_size, text.text_bold, text.text_color) == (9, True, "darkblue")
    assert (text.h_origin, text.v_origin, text.fill, text.fill_color) == (
        "Center", "Center", "", "gray20",
    )
    assert (line.width, line.height) == (400, 0)
    assert image.text == "logo.gif"
    assert mod.canvases[1].visible is False

    va = mod.visual_attributes["VA_AZUL"]
    assert (va.fg_color, va.bg_color, va.font_name, va.font_size, va.font_bold) == (
        "white", "r0g25b50", "Arial", 9, True,
    )
    win = mod.window_details["WI"]
    assert (win.title, win.width, win.height) == ("Unidade x Produto", 780, 447)
    assert (win.toolbar, win.primary_canvas) == ("TB", "CV")
    assert "WI" in mod.windows
    assert mod.graphics_count == 4


def test_a_module_without_a_coordinate_element_reports_no_unit(sample_xml):
    mod = parse_xml(sample_xml)
    assert (mod.coordinate_system, mod.coordinate_unit) == ("", "")
    assert all(it.visible for it in mod.all_items)
