"""Domain model of an Oracle Forms module.

Only what matters for analysis and conversion -- with one carefully fenced
exception: *look*. Geometry (item x/y/width/height, canvas size), prompt
placement, fonts, colors, bevels and the boilerplate graphics a canvas
paints exist here solely so the read-only visual preview
(:mod:`formslang.formui`) can draw the screen the way Forms draws it. None
of it survives a migration to APEX, and none of it ever feeds analysis,
conversion or the exported APEXlang; every such field is marked below.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Trigger:
    """A Forms trigger, at any scope."""

    name: str
    text: str
    scope: str  # "form" | "block" | "item"
    owner: str  # owning block or item name; "" at form scope

    @property
    def lines(self) -> int:
        return self.text.count("\n") + 1 if self.text else 0


@dataclass
class ProgramUnit:
    """Procedure/function/package declared inside the .fmb."""

    name: str
    kind: str  # Procedure | Function | Package Spec | Package Body
    text: str

    @property
    def lines(self) -> int:
        return self.text.count("\n") + 1 if self.text else 0


@dataclass
class RadioButton:
    """One button of a Radio Group. Preview only: it has its own place on the
    canvas, independent of the group's box, and Forms paints only the buttons."""

    name: str
    label: str = ""
    x: int | None = None
    y: int | None = None
    width: int | None = None
    height: int | None = None


@dataclass
class VisualAttribute:
    """A named look (``<VisualAttribute>``) items refer to. Preview only."""

    name: str
    fg_color: str = ""
    bg_color: str = ""
    font_name: str = ""
    font_size: int = 0  # points
    font_bold: bool = False


@dataclass
class Item:
    name: str
    item_type: str = ""
    data_type: str = ""
    column_name: str = ""
    database_item: bool = True
    required: bool = False
    max_length: int | None = None
    prompt: str = ""
    canvas: str = ""
    lov_name: str = ""
    list_elements: int = 0
    triggers: list[Trigger] = field(default_factory=list)
    subclassed: bool = False
    # Caption Forms paints on a button / check box / radio group (``Label``);
    # distinct from ``prompt``, which is the text next to a field.
    label: str = ""
    # ``Visible="false"`` -- the item exists (holds data, has triggers) but
    # the user never sees it. Analysis and conversion still count it.
    visible: bool = True
    # Choices of a List Item (ListItemElement) or Radio Group (RadioButton),
    # in the order the .fmb declares them.
    choices: list[str] = field(default_factory=list)
    # Geometry, for the visual preview only -- see the module docstring.
    # Values are in the module's coordinate unit (``FormModule.coordinate_unit``),
    # which Forms2XML writes as points far more often than as pixels.
    x: int | None = None
    y: int | None = None
    width: int | None = None
    height: int | None = None
    # PromptAttachmentEdge: "Top" | "Start" | "End" | "Bottom". Forms2XML omits
    # the attribute at Forms' default, which is Start (prompt to the left).
    prompt_edge: str = ""
    prompt_offset: int = 0  # PromptAttachmentOffset, same unit as x/y
    tab_page: str = ""  # TabPageName, when the canvas is a Tab canvas
    records_distance: int = 0  # DistanceBetweenRecords, tabular blocks only
    # ItemsDisplay ("Number of Items Displayed"): how many instances of this
    # item a multi-record block paints; 0 means "as many as the block".
    items_displayed: int = 0
    prompt_align: str = ""  # PromptAlign along the edge: "Start" | "Center" | "End"
    prompt_align_offset: int = 0  # PromptAlignOffset, same unit as x/y
    prompt_display: str = ""  # PromptDisplayStyle: "First Record" | "All Records" | "Hidden"
    prompt_justify: str = ""  # PromptJustification (multi-line prompts)
    prompt_color: str = ""  # PromptForegroundColor
    prompt_font_size: int = 0  # points
    prompt_bold: bool = False
    # What Forms paints the control itself with -- see the module docstring.
    bevel: str = ""  # "Lowered" | "Raised" | "Inset" | "Outset" | "None" | "Plain"
    fill: str = ""  # FillPattern: "transparent" / "none" mean the background is not painted
    bg_color: str = ""  # BackColor
    fg_color: str = ""  # ForegroundColor
    font_name: str = ""
    font_size: int = 0  # points
    font_bold: bool = False
    visual_attribute: str = ""  # VisualAttributeName, resolved through FormModule.visual_attributes
    record_visual_attribute: str = ""  # RecordVisualAttributeGroupName (current record's look)
    enabled: bool = True
    iconic: bool = False
    icon_name: str = ""
    justification: str = ""  # "Start" | "Center" | "Right" | "End" ...
    radio_buttons: list[RadioButton] = field(default_factory=list)


@dataclass
class Block:
    name: str
    database_block: bool = True
    query_data_source_name: str = ""
    query_data_source_type: str = ""
    where_clause: str = ""
    order_by_clause: str = ""
    insert_allowed: bool = True
    update_allowed: bool = True
    delete_allowed: bool = True
    records_displayed: int = 1
    items: list[Item] = field(default_factory=list)
    triggers: list[Trigger] = field(default_factory=list)

    @property
    def is_tabular(self) -> bool:
        return self.records_displayed > 1


@dataclass
class Relation:
    name: str
    detail_block: str = ""
    join_condition: str = ""
    deferred: bool = False
    delete_record: str = ""


@dataclass
class RecordGroup:
    name: str
    kind: str = ""
    query: str = ""


@dataclass
class Lov:
    name: str
    record_group: str = ""
    title: str = ""
    columns: int = 0


@dataclass
class Graphic:
    """Boilerplate a canvas paints under its items -- frame, rectangle, line,
    text, image. Preview only; analysis keeps counting them through
    ``FormModule.graphics_count``."""

    name: str
    kind: str = ""  # GraphicsType: "Frame" | "Rectangle" | "Line" | "Text" | "Image" | ...
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    bevel: str = ""
    fill: str = ""  # FillPattern
    fill_color: str = ""  # BackColor
    edge_color: str = ""  # EdgeForegroundColor
    title: str = ""  # FrameTitle
    title_align: str = ""  # FrameTitleAlign: "Start" | "Center" | "End"
    title_offset: int = 0  # FrameTitleOffset, same unit as x/y
    title_spacing: int = 0  # FrameTitleSpacing, same unit as x/y
    title_size: int = 0  # points
    title_bold: bool = False
    title_color: str = ""
    text: str = ""  # Text graphics: every TextSegment joined; images: the file name
    text_size: int = 0  # points
    text_bold: bool = False
    text_color: str = ""
    h_origin: str = ""  # HorizontalOrigin: where x sits on the box: "Left" | "Center" | "Right"
    v_origin: str = ""  # VerticalOrigin: "Top" | "Center" | "Bottom"
    h_justify: str = ""  # HorizontalJustification
    wrap: bool = False  # WrapText


@dataclass
class Window:
    """A Forms window: what frames a content canvas. Preview only."""

    name: str
    title: str = ""
    width: int | None = None
    height: int | None = None
    toolbar: str = ""  # HorizontalToolbarCanvasName
    primary_canvas: str = ""


@dataclass
class Canvas:
    """A Forms canvas, geometry and look only -- see the module docstring."""

    name: str
    window_name: str = ""
    canvas_type: str = ""  # "Content" | "Stacked" | "Horizontal Toolbar" | ...
    width: int | None = None
    height: int | None = None
    viewport_width: int | None = None
    viewport_height: int | None = None
    tab_pages: list[str] = field(default_factory=list)  # Tab canvases only
    visible: bool = True  # Visible="false": a stacked canvas raised on demand
    bg_color: str = ""  # BackColor
    bevel: str = ""
    graphics: list[Graphic] = field(default_factory=list)


@dataclass
class FormModule:
    """A whole .fmb, already normalized."""

    name: str
    source_path: str = ""
    # <Coordinate> of the module: the unit every x/y/width/height above is
    # expressed in. "Real" + "Point" is what Forms2XML emits for most real
    # modules; the preview converts to pixels from here and nowhere else.
    coordinate_system: str = ""  # "Real" | "Character"
    coordinate_unit: str = ""  # "Point" | "Pixel" | "Inch" | "Centimeter" | "Decipoint"
    char_cell_width: int | None = None
    char_cell_height: int | None = None
    title: str = ""
    comment: str = ""
    menu_module: str = ""
    first_block: str = ""
    blocks: list[Block] = field(default_factory=list)
    triggers: list[Trigger] = field(default_factory=list)  # form scope
    program_units: list[ProgramUnit] = field(default_factory=list)
    relations: list[Relation] = field(default_factory=list)
    record_groups: list[RecordGroup] = field(default_factory=list)
    lovs: list[Lov] = field(default_factory=list)
    attached_libraries: list[str] = field(default_factory=list)
    parameters: list[str] = field(default_factory=list)
    canvases: list[Canvas] = field(default_factory=list)
    windows: list[str] = field(default_factory=list)
    alerts: list[str] = field(default_factory=list)
    editors: list[str] = field(default_factory=list)
    object_groups: list[str] = field(default_factory=list)
    reports: list[str] = field(default_factory=list)
    tab_pages: list[str] = field(default_factory=list)
    graphics_count: int = 0
    convert_warnings: list[str] = field(default_factory=list)
    # Preview only (module docstring): named looks and the windows' chrome.
    visual_attributes: dict[str, VisualAttribute] = field(default_factory=dict)
    window_details: dict[str, Window] = field(default_factory=dict)

    # -- aggregates used by the assessment -------------------------------

    @property
    def all_triggers(self) -> list[Trigger]:
        out = list(self.triggers)
        for b in self.blocks:
            out.extend(b.triggers)
            for it in b.items:
                out.extend(it.triggers)
        return out

    @property
    def all_items(self) -> list[Item]:
        return [it for b in self.blocks for it in b.items]

    @property
    def plsql_lines(self) -> int:
        return sum(t.lines for t in self.all_triggers) + sum(
            p.lines for p in self.program_units
        )

    @property
    def plsql_text(self) -> str:
        parts = [t.text for t in self.all_triggers]
        parts += [p.text for p in self.program_units]
        return "\n".join(p for p in parts if p)
