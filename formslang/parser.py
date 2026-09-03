"""Forms2XML output -> domain model.

Two details that break naive parsers, both handled here:

1. **Double-escaped newlines.** Forms2XML stores trigger and program-unit
   bodies in an XML ATTRIBUTE, escaping newline and tab as the literal
   entities ``&#10;`` / ``&#9;``. After the normal XML unescape the text
   still contains the seven-character string ``&#10;``. Without a second
   decoding pass every trigger collapses into a single line.

2. **Accent mojibake.** The .fmb stores text in cp1252; Forms2XML declares
   UTF-8 but emits the original bytes reinterpreted, so ``Conexão`` arrives
   as ``ConexÃ£o``. The repair is reversible and only applied when it yields
   valid text.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from .model import (
    Block,
    Canvas,
    FormModule,
    Graphic,
    Item,
    Lov,
    ProgramUnit,
    RadioButton,
    RecordGroup,
    Relation,
    Trigger,
    VisualAttribute,
    Window,
)

NS = "{http://xmlns.oracle.com/Forms}"

# Numeric entities that survive the XML unescape (see module docstring).
_ENTITY = re.compile(r"&#(x[0-9A-Fa-f]+|[0-9]+);")
_MOJIBAKE = re.compile(r"[ÂÃ][\x80-\xbf]")


def _fix_mojibake(text: str) -> str:
    """Undo cp1252-read-as-UTF8, but only when the result is valid."""
    if not text or not _MOJIBAKE.search(text):
        return text
    try:
        return text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


def decode_forms_text(raw: str | None) -> str:
    """Normalize a code body coming from a Forms XML attribute."""
    if not raw:
        return ""

    def sub(m: re.Match[str]) -> str:
        code = m.group(1)
        value = int(code[1:], 16) if code[0] in "xX" else int(code)
        return chr(value)

    text = _ENTITY.sub(sub, raw)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return _fix_mojibake(text)


def _s(el: ET.Element, attr: str, default: str = "") -> str:
    return _fix_mojibake(el.get(attr, default) or default)


def _b(el: ET.Element, attr: str, default: bool) -> bool:
    raw = el.get(attr)
    if raw is None:
        return default
    return raw.strip().lower() == "true"


def _i(el: ET.Element, attr: str, default: int | None = None) -> int | None:
    raw = el.get(attr)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _pt(el: ET.Element, attr: str) -> int:
    """A font size, which Forms2XML writes in hundredths of a point (900 = 9pt)."""
    raw = _i(el, attr)
    return round(raw / 100) if raw else 0


def _bold(el: ET.Element, attr: str) -> bool:
    return _s(el, attr).lower() in ("bold", "demibold", "extrabold", "ultrabold")


def _kids(el: ET.Element, tag: str) -> list[ET.Element]:
    return el.findall(f"{NS}{tag}")


def _names(el: ET.Element, tag: str) -> list[str]:
    return [_s(k, "Name") for k in el.iter(f"{NS}{tag}")]


def _parse_triggers(parent: ET.Element, scope: str, owner: str) -> list[Trigger]:
    return [
        Trigger(
            name=_s(t, "Name").upper(),
            text=decode_forms_text(t.get("TriggerText")),
            scope=scope,
            owner=owner,
        )
        for t in _kids(parent, "Trigger")
    ]


def _parse_item(el: ET.Element, block_name: str) -> Item:
    name = _s(el, "Name")
    return Item(
        name=name,
        item_type=_s(el, "ItemType"),
        data_type=_s(el, "DataType"),
        column_name=_s(el, "ColumnName"),
        database_item=_b(el, "DatabaseItem", True),
        required=_b(el, "Required", False),
        max_length=_i(el, "MaximumLength"),
        # Prompts can be multi-line ("Empilhamento&#10;Máx."): same double
        # escaping as trigger text, so the same decoder.
        prompt=decode_forms_text(el.get("Prompt")),
        canvas=_s(el, "CanvasName"),
        lov_name=_s(el, "LovName"),
        list_elements=len(_kids(el, "ListItemElement")),
        triggers=_parse_triggers(el, "item", f"{block_name}.{name}"),
        subclassed=bool(el.get("ParentName")),
        label=decode_forms_text(el.get("Label")),
        visible=_b(el, "Visible", True),
        choices=[_s(k, "Name") for k in _kids(el, "ListItemElement")]
        + [_s(k, "Label") or _s(k, "Name") for k in _kids(el, "RadioButton")],
        x=_i(el, "XPosition"),
        y=_i(el, "YPosition"),
        width=_i(el, "Width"),
        height=_i(el, "Height"),
        prompt_edge=_s(el, "PromptAttachmentEdge"),
        prompt_offset=_i(el, "PromptAttachmentOffset", 0) or 0,
        tab_page=_s(el, "TabPageName"),
        records_distance=_i(el, "DistanceBetweenRecords", 0) or 0,
        items_displayed=_i(el, "ItemsDisplay", 0) or 0,
        prompt_align=_s(el, "PromptAlign"),
        prompt_align_offset=_i(el, "PromptAlignOffset", 0) or 0,
        prompt_display=_s(el, "PromptDisplayStyle"),
        prompt_justify=_s(el, "PromptJustification"),
        prompt_color=_s(el, "PromptForegroundColor"),
        prompt_font_size=_pt(el, "PromptFontSize"),
        prompt_bold=_bold(el, "PromptFontWeight"),
        bevel=_s(el, "Bevel"),
        fill=_s(el, "FillPattern"),
        bg_color=_s(el, "BackColor"),
        fg_color=_s(el, "ForegroundColor"),
        font_name=_s(el, "FontName"),
        font_size=_pt(el, "FontSize"),
        font_bold=_bold(el, "FontWeight"),
        visual_attribute=_s(el, "VisualAttributeName"),
        record_visual_attribute=_s(el, "RecordVisualAttributeGroupName"),
        enabled=_b(el, "Enabled", True),
        iconic=_b(el, "Iconic", False),
        icon_name=_s(el, "IconName"),
        justification=_s(el, "Justification"),
        radio_buttons=[
            RadioButton(
                name=_s(k, "Name"),
                label=_s(k, "Label") or _s(k, "Name"),
                x=_i(k, "XPosition"),
                y=_i(k, "YPosition"),
                width=_i(k, "Width"),
                height=_i(k, "Height"),
            )
            for k in _kids(el, "RadioButton")
        ],
    )


def _parse_graphic(el: ET.Element) -> Graphic:
    # A Text graphic keeps its copy in TextSegment children (one per font
    # run); a segment ending in a newline entity starts the next line.
    segments = [
        seg for ct in _kids(el, "CompoundText") for seg in _kids(ct, "TextSegment")
    ]
    first = segments[0] if segments else el
    kind = _s(el, "GraphicsType")
    text = decode_forms_text("".join(seg.get("Text") or "" for seg in segments))
    if kind.lower() == "image":
        text = _s(el, "ImageFilename")
    return Graphic(
        name=_s(el, "Name"),
        kind=kind,
        x=_i(el, "XPosition", 0) or 0,
        y=_i(el, "YPosition", 0) or 0,
        width=_i(el, "Width", 0) or 0,
        height=_i(el, "Height", 0) or 0,
        bevel=_s(el, "Bevel"),
        fill=_s(el, "FillPattern"),
        fill_color=_s(el, "BackColor"),
        edge_color=_s(el, "EdgeForegroundColor"),
        title=decode_forms_text(el.get("FrameTitle")),
        title_align=_s(el, "FrameTitleAlign"),
        title_offset=_i(el, "FrameTitleOffset", 0) or 0,
        title_spacing=_i(el, "FrameTitleSpacing", 0) or 0,
        title_size=_pt(el, "FrameTitleFontSize"),
        title_bold=_bold(el, "FrameTitleFontWeight"),
        title_color=_s(el, "FrameTitleForegroundColor"),
        text=text,
        text_size=_pt(first, "FontSize") or _pt(el, "GraphicsFontSize"),
        text_bold=_bold(first, "FontWeight") or _bold(el, "GraphicsFontWeight"),
        text_color=_s(first, "ForegroundColor")
        or _s(el, "GraphicsFontColor")
        or _s(el, "ForegroundColor"),
        h_origin=_s(el, "HorizontalOrigin"),
        v_origin=_s(el, "VerticalOrigin"),
        h_justify=_s(el, "HorizontalJustification"),
        wrap=_b(el, "WrapText", False),
    )


def _parse_canvas(el: ET.Element) -> Canvas:
    return Canvas(
        name=_s(el, "Name"),
        window_name=_s(el, "WindowName"),
        canvas_type=_s(el, "CanvasType") or "Content",
        width=_i(el, "Width"),
        height=_i(el, "Height"),
        viewport_width=_i(el, "ViewportWidth"),
        viewport_height=_i(el, "ViewportHeight"),
        tab_pages=_names(el, "TabPage"),
        visible=_b(el, "Visible", True),
        bg_color=_s(el, "BackColor"),
        bevel=_s(el, "Bevel"),
        graphics=[_parse_graphic(g) for g in el.iter(f"{NS}Graphics")],
    )


def _parse_visual_attribute(el: ET.Element) -> VisualAttribute:
    return VisualAttribute(
        name=_s(el, "Name"),
        fg_color=_s(el, "ForegroundColor"),
        bg_color=_s(el, "BackColor"),
        font_name=_s(el, "FontName"),
        font_size=_pt(el, "FontSize"),
        font_bold=_bold(el, "FontWeight"),
    )


def _parse_window(el: ET.Element) -> Window:
    return Window(
        name=_s(el, "Name"),
        title=decode_forms_text(el.get("Title")),
        width=_i(el, "Width"),
        height=_i(el, "Height"),
        toolbar=_s(el, "HorizontalToolbarCanvasName"),
        primary_canvas=_s(el, "PrimaryCanvas"),
    )


def _parse_block(el: ET.Element) -> Block:
    name = _s(el, "Name")
    return Block(
        name=name,
        database_block=_b(el, "DatabaseBlock", True),
        query_data_source_name=_s(el, "QueryDataSourceName"),
        query_data_source_type=_s(el, "QueryDataSourceType"),
        where_clause=decode_forms_text(el.get("WhereClause")),
        order_by_clause=decode_forms_text(el.get("OrderByClause")),
        insert_allowed=_b(el, "InsertAllowed", True),
        update_allowed=_b(el, "UpdateAllowed", True),
        delete_allowed=_b(el, "DeleteAllowed", True),
        records_displayed=_i(el, "RecordsDisplayCount", 1) or 1,
        items=[_parse_item(i, name) for i in _kids(el, "Item")],
        triggers=_parse_triggers(el, "block", name),
    )


def parse_xml(path: str | Path, *, convert_log: str = "") -> FormModule:
    """Read a Forms module XML and return the normalized FormModule."""
    path = Path(path)
    root = ET.parse(path).getroot()
    fm = root.find(f"{NS}FormModule")
    if fm is None:
        raise ValueError(f"{path.name}: no <FormModule> element (menu or library?)")

    mod = FormModule(
        name=_s(fm, "Name"),
        source_path=str(path),
        title=_s(fm, "Title"),
        comment=_s(fm, "Comment"),
        menu_module=_s(fm, "MenuModule"),
        first_block=_s(fm, "FirstNavigationBlockName"),
        blocks=[_parse_block(b) for b in _kids(fm, "Block")],
        triggers=_parse_triggers(fm, "form", ""),
        program_units=[
            ProgramUnit(
                name=_s(p, "Name"),
                kind=_s(p, "ProgramUnitType"),
                text=decode_forms_text(p.get("ProgramUnitText")),
            )
            for p in _kids(fm, "ProgramUnit")
        ],
        relations=[
            Relation(
                name=_s(r, "Name"),
                detail_block=_s(r, "DetailBlock"),
                join_condition=decode_forms_text(r.get("JoinCondition")),
                deferred=_b(r, "Deferred", False),
                delete_record=_s(r, "DeleteRecord"),
            )
            for r in fm.iter(f"{NS}Relation")
        ],
        record_groups=[
            RecordGroup(
                name=_s(g, "Name"),
                kind=_s(g, "RecordGroupType"),
                query=decode_forms_text(g.get("RecordGroupQuery")),
            )
            for g in fm.iter(f"{NS}RecordGroup")
        ],
        lovs=[
            Lov(
                name=_s(v, "Name"),
                record_group=_s(v, "RecordGroupName"),
                title=_s(v, "Title"),
                columns=len(_kids(v, "LOVColumnMapping")),
            )
            for v in fm.iter(f"{NS}LOV")
        ],
        attached_libraries=_names(fm, "AttachedLibrary"),
        parameters=_names(fm, "ModuleParameter"),
        canvases=[_parse_canvas(c) for c in fm.iter(f"{NS}Canvas")],
        windows=_names(fm, "Window"),
        alerts=_names(fm, "Alert"),
        editors=_names(fm, "Editor"),
        object_groups=_names(fm, "ObjectGroup"),
        reports=_names(fm, "Report"),
        tab_pages=_names(fm, "TabPage"),
        graphics_count=len(list(fm.iter(f"{NS}Graphics"))),
        visual_attributes={
            va.name: va
            for va in (_parse_visual_attribute(v) for v in fm.iter(f"{NS}VisualAttribute"))
        },
        window_details={
            w.name: w for w in (_parse_window(x) for x in fm.iter(f"{NS}Window"))
        },
    )

    coordinate = fm.find(f"{NS}Coordinate")
    if coordinate is not None:
        mod.coordinate_system = _s(coordinate, "CoordinateSystem")
        mod.coordinate_unit = _s(coordinate, "RealUnit")
        mod.char_cell_width = _i(coordinate, "CharacterCellWidth")
        mod.char_cell_height = _i(coordinate, "CharacterCellHeight")

    if convert_log:
        mod.convert_warnings = [
            line.strip()
            for line in convert_log.splitlines()
            if line.strip().startswith("ERROR")
        ]
    return mod
