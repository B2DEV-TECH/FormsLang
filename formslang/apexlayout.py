"""Geometry-faithful APEX page layout derived from a Forms module.

Forms places every item at an absolute ``(x, y)`` on a canvas and draws
frames around groups of them; APEX's Universal Theme lays a page out on a
12-column grid of regions, sub-regions and items. This module bridges the
two. It reads the geometry the parser keeps -- canvases, frames, rectangles
with a caption, items, radio buttons -- and builds a tree of regions whose
rows and columns reproduce the original screen as closely as the grid
allows:

* a **content canvas** is a Standard region titled like its window; its
  **horizontal toolbar** is a chrome-less region above it whose buttons flow
  inline; a **stacked canvas** raised on demand (``Visible="false"``) is an
  Inline Dialog; a **tab canvas** is a Tabs Container with one region per
  tab page;
* a **frame** (or a rectangle whose top edge carries a text caption -- the
  hand-drawn group box every old form has) is a sub-region, nested by
  geometric containment;
* items are clustered into **rows** by their vertical position and given a
  ``columnSpan`` proportional to their own width against their container's
  real width, packed left to right with no gap between them -- the row
  keeps Forms' relative sizing without reproducing incidental whitespace
  as dead grid columns;
* a **prompt** left of its field (Forms' default edge, Start) claims the
  room it takes on the grid and becomes a label left of the field, with the
  same share of the cell (``labelColumnSpan``); a prompt on the top edge is
  a label above; an item the screen captions with nothing gets a hidden
  label rather than an invented one; boilerplate **text** drawn right
  before an uncaptioned field -- how screens were captioned before Forms
  had prompts -- is read as its prompt;
* any other boilerplate text is a chrome-less static region placed where it
  was drawn, so headings and help paragraphs survive;
* loose items drawn below the first frame of a container are wrapped in
  chrome-less groups so their vertical order against the frames survives
  (APEX renders a region's own items before its sub-regions);
* an item with no canvas or ``Visible="false"`` becomes a Hidden item under
  its block's home region.

:mod:`formslang.apexlang` writes this tree as APEXlang and
:mod:`formslang.formui` draws it, so the preview and the export can never
disagree. Every keyword the layout relies on (``parentRegion``, ``slot:
subRegions``/``tabs``, ``startNewRow``, ``newColumn``, ``column``,
``columnSpan``, ``labelColumnSpan``, the region and label templates, label
``alignment``, ``type: hidden``, shared static LOVs, a static region's
``source { htmlCode }``) was accepted by ``apex validate`` on APEX 26.1
before it was used here.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterator
from dataclasses import dataclass, field

from .model import Block, Canvas, FormModule, Graphic, Item

GRID_COLUMNS = 12

# Forms modules built on WebUtil carry the library's own block and canvas
# (bean areas for file transfer, an OLE bean, a dummy button): client-side
# plumbing with no place on an APEX page.
_WEBUTIL = re.compile(r"^WEBUTIL", re.IGNORECASE)
_APEX_NAME = re.compile(r"[^A-Z0-9_$#]")

# What Forms assumes when the .fmb omits a size (its own defaults are close).
_DEFAULT_WIDTH = 60
_DEFAULT_HEIGHT = 14
# Two boxes share a row when they overlap vertically by this much of the
# shorter one's height.
_ROW_OVERLAP = 0.7
# Average character width per coordinate unit when the module records no
# character cell: how much room a prompt takes beside its field.
_CHAR_WIDTH = {
    "character": 1.0,
    "cell": 1.0,
    "point": 5.0,
    "pixel": 7.0,
    "decipoint": 50.0,
    "inch": 0.07,
    "centimeter": 0.18,
}
# Text rows per coordinate unit for the same fallback: how many lines a
# multi-line item's height holds (a Forms text row is about 14 points).
_CHAR_HEIGHT = {
    "character": 1.0,
    "cell": 1.0,
    "point": 14.0,
    "pixel": 18.0,
    "decipoint": 140.0,
    "inch": 0.19,
    "centimeter": 0.5,
}
# Boilerplate text ending within this many characters of an uncaptioned
# item's left edge is that item's prompt.
_PROMPT_REACH = 4
# Forms data types as the column data types an Interactive Grid declares.
_DATA_TYPES = {
    "char": "varchar2",
    "alpha": "varchar2",
    "number": "number",
    "date": "date",
    "datetime": "timestamp",
    "long": "clob",
}
# Item types with no native APEX component: the field that takes their place
# is a placeholder, reported as unsupported rather than as a mapping.
_UNSUPPORTED_TYPES = ("image", "bean", "ole", "activex", "vbx", "sound", "tree", "chart", "custom")


def _slug(value: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-z0-9]+", "-", ascii_text.strip().lower()).strip("-")
    return text[:60].rstrip("-")


def slug(value: str, *, fallback: str = "formslang-app") -> str:
    """A filesystem-safe APEX alias and human-readable component id."""
    ascii_text = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-z0-9]+", "-", ascii_text.strip().lower()).strip("-")
    if not text or not text[0].isalpha():
        text = f"app-{text}" if text else fallback
    return text[:80].rstrip("-")


def sql_name(name: str, limit: int = 128) -> str:
    """A Forms name as the bare identifier APEXlang takes for a column or table."""
    return re.sub(r"[^A-Z0-9_$#]", "_", name.strip().replace('"', "").upper())[:limit]


def column_name(item: Item) -> str:
    """The identifier of the Interactive Grid column a Forms item becomes:
    its item name as a SQL identifier. The export writes it and the
    mapping report points at it, so a reader can find the column in the
    page file and in Page Designer by the same name."""
    return sql_name(item.name)


def button_id(placed: Placed) -> str:
    """The APEXlang identifier of the button a Push Button becomes
    (``block-item``), shared by the export and the mapping report."""
    return slug(f"{placed.block.name}-{placed.item.name}", fallback=f"button-{placed.sequence}")


def humanize(name: str) -> str:
    """``CV_PRINCIPAL`` -> ``Cv Principal``: a readable title from an object name."""
    return " ".join(name.replace("_", " ").split()).title()


def forms_caption(item: Item) -> tuple[str, str]:
    """What Forms writes for an item and where: ``(text, side)``.

    The prompt, on the edge it is attached to -- ``left`` is Forms' default,
    Start; with a ``Hidden`` prompt display style the text exists but is not
    drawn (side ``none``). Without a prompt, the ``Label`` a button or check
    box carries sits on the ``control`` itself. ``("", "none")`` means the
    screen shows no caption at all, and neither should APEX.
    """
    prompt = " ".join(item.prompt.split())
    if prompt:
        if item.prompt_display.lower() == "hidden":
            return prompt, "none"
        edge = item.prompt_edge.lower()
        return prompt, {"top": "above", "bottom": "below", "end": "right"}.get(edge, "left")
    label = " ".join(item.label.split())
    return (label, "control") if label else ("", "none")


@dataclass
class Grid:
    """Where a box lands on its parent's 12-column grid.

    ``flow`` means "no column arithmetic": the box just starts a new row or
    joins the previous cell -- a toolbar's buttons, or the fallback layout of
    a module without canvases.
    """

    new_row: bool = True
    new_column: bool = True
    column: int = 1
    span: int = GRID_COLUMNS
    flow: bool = False


@dataclass
class Placed:
    """An item or button at its place in a region body."""

    item: Item
    block: Block
    apex_name: str
    grid: Grid = field(default_factory=Grid)
    sequence: int = 0
    caption: str = ""  # what Forms writes for the item; "" when the screen shows nothing
    side: str = "none"  # where: left | right | above | below | control (its own label) | none
    align: str = "left"  # how the label text sits in its room: left | center | right
    box: tuple[float, float, float, float] | None = None  # the item plus its prompt's room
    label_span: int = 0  # a left label's share of the cell, in twelfths; 0 when not left
    note: str = ""  # how the caption was found, when not the obvious way
    radio_columns: int = 0  # radio buttons Forms paints side by side; 0 = geometry unknown

    @property
    def label(self) -> str:
        """The label APEX gets: the Forms caption, else the item name spelled
        out -- seen in Page Designer only, since the template is then hidden."""
        return self.caption or humanize(self.item.name)

    def bounds(self) -> tuple[float, float, float, float]:
        """The rectangle the item claims on the grid: its box plus prompt room."""
        return self.box or item_box(self.item)


@dataclass
class RegionNode:
    """One APEX region: a canvas, a frame, a tab page, or an implicit group."""

    id: str
    name: str
    title: str
    template: str  # Universal Theme template slug: standard, inline-dialog, ...
    source: str  # what in the .fmb this region stands for, for comments and the manifest
    x: float = 0
    y: float = 0
    width: float = 0
    height: float = 0
    slot: str = "body"  # body (page level) | subRegions | tabs
    grid: Grid | None = None  # placement inside the parent, sub-regions only
    sequence: int = 0
    flow: bool = False  # toolbar: everything inline, no columns
    body: list[Placed] = field(default_factory=list)
    subs: list[RegionNode] = field(default_factory=list)
    hidden: list[Placed] = field(default_factory=list)
    tabular: dict[str, int] = field(default_factory=dict)  # block -> records painted here
    note: str = ""
    text: str = ""  # boilerplate text this region shows (a static region, no items)
    text_bold: bool = False
    kind: str = "static"  # static (items and sub-regions) | grid (an Interactive Grid)
    options: list[str] = field(default_factory=list)  # template options besides #DEFAULT#
    columns: list[Placed] = field(default_factory=list)  # grid only: columns, left to right
    block: Block | None = None  # grid only: the block whose table the grid shows
    derived: bool = False  # a wrapper the layout invented (a row of loose items), not a Forms group

    @property
    def records(self) -> int:
        """The most records any block paints in this region (1 = single-record)."""
        return max(self.tabular.values(), default=1)

    def walk(self) -> Iterator[RegionNode]:
        yield self
        for sub in self.subs:
            yield from sub.walk()


@dataclass
class StaticLov:
    """A shared static list of values: the choices of a List Item or Radio Group."""

    id: str
    name: str
    entries: list[tuple[str, str]]  # (display, return)
    source: str
    declared: bool = False  # return values come from the .fmb (Value), not from the labels


@dataclass
class PageLayout:
    roots: list[RegionNode]
    hidden: list[Placed]  # hidden items whose block has no visible home region
    lovs: list[StaticLov]
    names: dict[str, str]  # "BLOCK.ITEM" -> APEX item name
    skipped: list[str]
    char_cell: tuple[float, float] | None  # units per character cell (width, height)
    unit: str = ""

    def regions(self) -> Iterator[RegionNode]:
        for root in self.roots:
            yield from root.walk()

    def placed(self) -> Iterator[Placed]:
        """Every visible control: region bodies, then grid columns."""
        for region in self.regions():
            yield from region.body
            yield from region.columns

    def chars(self, units: float | None, *, vertical: bool = False) -> int | None:
        """A Forms width/height as a character count, or None when there is
        no width at all to convert. When the module records no character
        cell, fall back to the same per-unit estimate ``build_layout`` uses
        for prompt room (:data:`_CHAR_WIDTH`) -- an APEX text field should
        never go without a ``width`` just because the .fmb used Points."""
        if not units:
            return None
        if self.char_cell is not None:
            cell = self.char_cell[1 if vertical else 0]
            return max(1, round(units / cell)) if cell else None
        table = _CHAR_HEIGHT if vertical else _CHAR_WIDTH
        cell = table.get(self.unit.lower(), 14.0 if vertical else 5.0)
        return max(1, round(units / cell))


# -- geometry helpers ---------------------------------------------------------


@dataclass
class _Box:
    x: float
    y: float
    w: float
    h: float
    ref: object  # Placed | RegionNode

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2

    @property
    def area(self) -> float:
        return self.w * self.h

    def contains(self, px: float, py: float) -> bool:
        return self.x <= px <= self.x + self.w and self.y <= py <= self.y + self.h


def item_box(item: Item) -> tuple[float, float, float, float]:
    """The rectangle an item occupies. Forms2XML omits a coordinate at its
    default (0); a Radio Group's own box is meaningless -- Forms paints only
    its buttons, so their union is where the group really is."""
    buttons = [rb for rb in item.radio_buttons if rb.x is not None and rb.y is not None]
    if buttons:
        x0 = min(rb.x for rb in buttons)
        y0 = min(rb.y for rb in buttons)
        x1 = max(rb.x + (rb.width or 40) for rb in buttons)
        y1 = max(rb.y + (rb.height or _DEFAULT_HEIGHT) for rb in buttons)
        return x0, y0, x1 - x0, y1 - y0
    return (
        item.x or 0,
        item.y or 0,
        item.width or _DEFAULT_WIDTH,
        item.height or _DEFAULT_HEIGHT,
    )


def _text_box(g: Graphic) -> tuple[float, float, float, float]:
    """A Text graphic is anchored on its origin, not its top-left corner."""
    x, y = float(g.x), float(g.y)
    ho, vo = g.h_origin.lower(), g.v_origin.lower()
    x -= g.width / 2 if ho == "center" else g.width if ho == "right" else 0
    y -= g.height / 2 if vo == "center" else g.height if vo == "bottom" else 0
    return x, y, g.width, g.height


def _captions(graphics: list[Graphic]) -> list[tuple[Graphic, str, Graphic | None]]:
    """Group boxes with their caption and, for a rectangle, the text that is it."""
    texts = [g for g in graphics if g.kind.lower() == "text" and g.text.strip()]
    used: set[int] = set()
    out: list[tuple[Graphic, str, Graphic | None]] = []
    for g in graphics:
        kind = g.kind.lower()
        if kind == "frame":
            out.append((g, " ".join(g.title.split()), None))
            continue
        if kind != "rectangle" or g.width <= 0 or g.height <= 0:
            continue
        for index, text in enumerate(texts):
            if index in used:
                continue
            tx, ty, tw, th = _text_box(text)
            on_top_edge = abs((ty + th / 2) - g.y) <= max(th, 12)
            inside = g.x - 2 <= tx + tw / 2 <= g.x + g.width + 2
            if on_top_edge and inside:
                used.add(index)
                out.append((g, " ".join(text.text.split()), text))
                break
    return out


def frame_captions(graphics: list[Graphic]) -> list[tuple[Graphic, str]]:
    """The boilerplate boxes that group items, each with its caption.

    A ``Frame`` is one by definition (its ``FrameTitle`` may be empty). A
    ``Rectangle`` counts only when a ``Text`` graphic sits on its top edge:
    that is how Forms developers hand-draw a titled group box, and a bare
    rectangle is just decoration.
    """
    return [(g, caption) for g, caption, _ in _captions(graphics)]


def _fit(placed: Placed, room: float) -> None:
    """Claim ``room`` units beside the item for its caption, and settle how
    the label text sits: a prompt left of the field ends at the field, so it
    hugs the field's edge; one above follows the .fmb's ``PromptAlign``."""
    x, y, w, h = item_box(placed.item)
    if placed.side == "left" and room > 0:
        placed.box = (x - room, y, w + room, h)
        share = round(room / (w + room) * GRID_COLUMNS)
        placed.label_span = min(GRID_COLUMNS - 1, max(1, share))
        placed.align = "right"
    elif placed.side == "right" and room > 0:
        placed.box = (x, y, w + room, h)
    else:
        placed.box = (x, y, w, h)
    if placed.side in {"above", "below"}:
        along = placed.item.prompt_align.lower()
        placed.align = {"center": "center", "end": "right"}.get(along, "left")


def _reconcile_label(placed: Placed) -> None:
    """Cap a left label's share of the cell below the ``columnSpan``
    :func:`_place_row` actually gave the item.

    :func:`_fit` sizes ``label_span`` against the item's own box, as if it
    were getting the row to itself -- before the row's crowding is known.
    On a crowded row ``_place_row`` can hand the item a ``columnSpan`` too
    narrow for that share; APEX rejects ``labelColumnSpan >= columnSpan`` at
    render time with ``WWV_FLOW_GRID_LAYOUT.LABEL_COLUMN_SPAN_TOO_BIG``,
    which neither ``apex validate`` nor ``apex import`` catches -- only
    actually opening the page does. Cap the share here, once the row is laid
    out; when the span is too narrow to leave the field even one column,
    drop the label's share entirely so
    :func:`formslang.apexlang._label_template` floats it instead of losing
    it (or the field) altogether.
    """
    if not placed.label_span or placed.grid.flow:
        return
    placed.label_span = max(0, min(placed.label_span, placed.grid.span - 1))


def _make_placed(item: Item, block: Block, apex_name: str, char_w: float) -> Placed:
    """An item with its Forms caption and the room that caption takes."""
    text, side = forms_caption(item)
    placed = Placed(item, block, apex_name, caption=text, side=side)
    room = 0.0
    if side in {"left", "right"}:
        room = len(text) * char_w + max(placed.item.prompt_offset, 0)
    _fit(placed, room)
    if "radio" in item.item_type.lower():
        placed.radio_columns = _radio_columns(item)
    return placed


def _radio_columns(item: Item) -> int:
    """How many radio buttons Forms paints side by side: the widest row of
    the group's buttons, each of which has its own place on the canvas.
    0 when the .fmb gives them no geometry, so APEX keeps its default."""
    boxes = [
        _Box(
            float(rb.x),
            float(rb.y),
            float(rb.width or _DEFAULT_WIDTH),
            float(rb.height or _DEFAULT_HEIGHT),
            rb,
        )
        for rb in item.radio_buttons
        if rb.x is not None and rb.y is not None
    ]
    if not boxes:
        return 0
    return max(len(row) for row in _rows(boxes))


def database_column(item: Item) -> str:
    """The table column a database item reads: ``ColumnName`` when the .fmb
    spells it out, else the item's own name -- Forms' default, which
    Forms2XML leaves out of the XML. A control item has none."""
    if not item.database_item:
        return ""
    return item.column_name or item.name


def apex_item_type(item: Item) -> str:
    """The native APEX item type a Forms item becomes.

    Every keyword here was accepted by ``apex validate`` on APEX 26.1, as a
    page item and as an Interactive Grid column: a List Item is a
    ``selectList`` and a Radio Group a ``radioGroup``, each fed by a shared
    static LOV built from the choices the .fmb declares; a Text Item
    declared ``MultiLine`` is a ``textarea``; a Text Item of data type Date
    or Datetime is a ``datePicker`` and one of data type Number a
    ``numberField``, so the format mask and the alignment Forms gave them
    land on the native properties. Item types APEX has no component for
    (Image, Bean Area, OLE, Tree ...) fall to a text placeholder and are
    reported as unsupported, never as mapped.
    """
    kind = item.item_type.lower()
    if "display" in kind:
        return "displayOnly"
    if "editor" in kind or "area" in kind:
        return "textarea"
    if "check" in kind:
        return "checkbox"
    if "radio" in kind:
        return "radioGroup"
    if "list" in kind:
        return "selectList"
    if item.multi_line:
        return "textarea"
    if "text" in kind:
        data = item.data_type.lower()
        if data in {"date", "datetime"}:
            return "datePicker"
        if data == "number":
            return "numberField"
    return "textField"


def unsupported_reason(item: Item) -> str:
    """Why an item has no native APEX component, or "" when it has one."""
    kind = item.item_type.lower()
    if "button" in kind or "text" in kind or "display" in kind:
        return ""
    if any(word in kind for word in _UNSUPPORTED_TYPES):
        return (
            f"APEX has no native component for a Forms {item.item_type}; a "
            f"{apex_item_type(item)} placeholder keeps its place on the grid"
        )
    return ""


def tabular_note(node: RegionNode, name: str, records: int) -> str:
    """The note both the exporter and the preview attach to a region where
    a multi-record block could not become an Interactive Grid: which block,
    how many records Forms shows, and why the grid was not built."""
    block = next(
        (p.block for p in node.body + node.hidden + node.columns if p.block.name == name), None
    )
    if block is None or not block.database_block:
        why = "the block is a control block, with no table behind it"
    elif not block.query_data_source_name:
        why = "the block declares no query data source"
    else:
        why = (
            f"its query data source is a {block.query_data_source_type}, not a table, "
            "and that query is business logic the .fmb only hints at"
        )
    return (
        f"Forms shows {records} records of block {name} at once here (tabular): the "
        f"first record's row is laid out as page items because {why}; an Interactive "
        "Grid on the block's query is the developer's next step."
    )


def _table_bound(block: Block) -> bool:
    """A block APEX can show as an Interactive Grid on its own table: a
    database block whose query source is a table (Forms' default, so an
    omitted type counts) with a name. Procedure, sub-query and FROM-clause
    blocks are not: their SQL is business logic the .fmb only hints at."""
    kind = (block.query_data_source_type or "table").lower()
    return bool(block.database_block and block.query_data_source_name and kind == "table")


def _records_shown(placed: Placed) -> int:
    """How many records of its block the item shows at once: ItemsDisplay
    when set (the audit fields of a grid block show once), else the
    block's record count."""
    return placed.item.items_displayed or placed.block.records_displayed or 1


def _grid_nodes(
    container: RegionNode, items: list[Placed], ids: _Ids
) -> tuple[list[Placed], list[RegionNode]]:
    """Pull the multi-record items of table-bound blocks out of ``items``
    and return them as one Interactive Grid node per block, sized to the
    area Forms paints the records on, columns in left-to-right order.
    Items the block shows once (ItemsDisplay=1) stay page items, as they
    stay outside the record rows in Forms."""
    by_block: dict[str, list[Placed]] = {}
    rest: list[Placed] = []
    for placed in items:
        is_button = "button" in placed.item.item_type.lower()
        if _records_shown(placed) > 1 and _table_bound(placed.block) and not is_button:
            by_block.setdefault(placed.block.name, []).append(placed)
        else:
            rest.append(placed)
    grids: list[RegionNode] = []
    for name, columns in by_block.items():
        block = columns[0].block
        columns.sort(key=lambda p: (item_box(p.item)[0], item_box(p.item)[1]))
        x0 = min(p.bounds()[0] for p in columns)
        y0 = min(p.bounds()[1] for p in columns)
        x1 = max(p.bounds()[0] + p.bounds()[2] for p in columns)
        y1 = y0
        for placed in columns:
            _, y, _, h = placed.bounds()
            step = h + max(placed.item.records_distance, 0)
            y1 = max(y1, y + h + (_records_shown(placed) - 1) * step)
        for index, placed in enumerate(columns, 1):
            placed.sequence = index * 10
        grids.append(
            RegionNode(
                id=ids.take(name, "grid"),
                name=name,
                title="",
                template="interactive-report",
                source=(
                    f"block {name} ({block.records_displayed} records at once) on "
                    f"{container.source}"
                ),
                x=x0,
                y=y0,
                width=max(x1 - x0, 1),
                height=max(y1 - y0, 1),
                slot="subRegions",
                kind="grid",
                columns=columns,
                block=block,
            )
        )
    return rest, grids


def _collapse_grid(node: RegionNode, grid: RegionNode) -> None:
    """A frame (or tab page) that holds nothing but one block's record rows
    is that block's Interactive Grid itself: its caption becomes the grid's
    title, and no empty region is left around it."""
    node.kind = "grid"
    node.template = "interactive-report"
    node.columns = grid.columns
    node.block = grid.block
    node.source = f"{node.source}, showing {grid.source.split(' on ', 1)[0]}"


def _adopt_boilerplate(texts: list[Graphic], pairs: list[Placed], char_w: float) -> list[Graphic]:
    """Boilerplate text drawn right before, or right above, an item that has
    no caption of its own is that item's prompt -- how screens were captioned
    before Forms had prompts. A text beside a field wins over one above it;
    among those, the nearest. Bold text above a field is a heading, not a
    prompt, and keeps its weight as a text region. Returns the texts that
    caption nothing."""
    adopted: set[int] = set()
    # Rightmost text first: the one nearest a field claims it.
    for g in sorted(texts, key=lambda t: _text_box(t)[0], reverse=True):
        line = " ".join(g.text.split())
        if "\n" in g.text.strip() or len(line) > 60:
            continue
        tx, ty, tw, th = _text_box(g)
        best: tuple[tuple[int, float], str, Placed] | None = None
        for placed in pairs:
            if placed.caption:
                continue
            x, y, w, h = item_box(placed.item)
            beside = min(ty + th, y + h) - max(ty, y) >= 0.5 * min(th, h)
            gap = x - (tx + tw)
            if beside and -char_w <= gap <= _PROMPT_REACH * char_w:
                rank, side = (0, gap), "left"
            else:
                over = min(tx + tw, x + w) - max(tx, x) > 0 and tw <= w + _PROMPT_REACH * char_w
                drop = y - (ty + th)
                if g.text_bold or not (over and -0.5 * th <= drop <= th):
                    continue
                rank, side = (1, drop), "above"
            if best is None or rank < best[0]:
                best = (rank, side, placed)
        if best is None:
            continue
        adopted.add(id(g))
        _, side, placed = best
        placed.caption, placed.side = line, side
        _fit(placed, max(item_box(placed.item)[0] - tx, char_w) if side == "left" else 0.0)
        justify = g.h_justify.lower()
        placed.align = {"center": "center", "right": "right", "end": "right"}.get(justify, "left")
        where = "beside" if side == "left" else "above"
        placed.note = f"prompt read from boilerplate text {g.name}, drawn {where} the field in Forms"
    return [g for g in texts if id(g) not in adopted]


def _rows(boxes: list[_Box]) -> list[list[_Box]]:
    """Cluster boxes into visual rows.

    A box joins the first row (top to bottom) whose anchor -- the row's
    topmost box -- it overlaps vertically by most of the shorter of the two
    heights. Forms screens often stack controls a few units apart with
    taller neighbours (a select list beside a check box) straddling both
    lines; the threshold keeps those on their own rows without splitting a
    frame from the small fields drawn along its top edge.
    """
    rows: list[tuple[_Box, list[_Box]]] = []
    for box in sorted(boxes, key=lambda b: (b.y, b.x)):
        for anchor, members in rows:
            overlap = min(anchor.y + anchor.h, box.y + box.h) - max(anchor.y, box.y)
            if overlap >= _ROW_OVERLAP * min(anchor.h, box.h):
                members.append(box)
                break
        else:
            rows.append((box, [box]))
    return [sorted(members, key=lambda b: (b.x, b.y)) for _, members in rows]


def _place_row(row: list[_Box], origin_x: float, width: float, *, first: bool) -> list[Grid]:
    """Column arithmetic for one row of boxes against a container ``width``
    units wide. Each box gets a ``columnSpan`` proportional to its own width
    against the container's -- so a lone narrow field stays narrow instead
    of stretching to fill the row -- and boxes pack contiguously left to
    right in the row's order (:func:`_rows` already sorted them by x). A
    box never starts a column short of where the previous one ended: Forms'
    incidental whitespace between fields is not a grid gap APEX should
    reproduce. A row whose boxes outnumber the twelve columns overflows
    onto as many 12-wide grid rows as it takes.
    """
    del origin_x  # column is now derived from packing order, not x position
    unit = max(width, 1.0) / GRID_COLUMNS
    grids: list[Grid] = []
    next_free = 1
    for index, box in enumerate(row):
        span = min(GRID_COLUMNS, max(1, round(box.w / unit)))
        if next_free > GRID_COLUMNS:
            next_free = 1
            grid = Grid(new_row=True, new_column=False, column=1, span=span)
        else:
            grid = Grid(new_row=False, new_column=index > 0, column=next_free, span=span)
        grid.span = min(grid.span, GRID_COLUMNS + 1 - grid.column)
        next_free = grid.column + grid.span
        grids.append(grid)
    if grids and first:
        grids[0].new_row = True
    return grids


def _union(boxes: list[_Box]) -> tuple[float, float, float, float]:
    x0 = min(b.x for b in boxes)
    y0 = min(b.y for b in boxes)
    x1 = max(b.x + b.w for b in boxes)
    y1 = max(b.y + b.h for b in boxes)
    return x0, y0, max(x1 - x0, 1.0), max(y1 - y0, 1.0)


class _Ids:
    def __init__(self) -> None:
        self.taken: set[str] = set()

    def take(self, name: str, fallback: str) -> str:
        base = _slug(name) or fallback
        candidate, n = base, 1
        while candidate in self.taken:
            n += 1
            candidate = f"{base}-{n}"
        self.taken.add(candidate)
        return candidate


# -- tree building -------------------------------------------------------------


def apex_item_names(module: FormModule, page: int) -> dict[str, str]:
    """``BLOCK.ITEM`` -> ``P<page>_ITEM``, block-prefixed when two blocks share a name."""
    counts: dict[str, int] = {}
    for block in module.blocks:
        for item in block.items:
            counts[item.name.upper()] = counts.get(item.name.upper(), 0) + 1
    names: dict[str, str] = {}
    for block in module.blocks:
        for item in block.items:
            bare = item.name.upper()
            suffix = bare if counts[bare] == 1 else f"{block.name}_{bare}".upper()
            names[f"{block.name}.{item.name}".upper()] = _APEX_NAME.sub(
                "_", f"P{page}_{suffix}"
            )[:255]
    return names


def _arrange(
    node: RegionNode,
    items: list[Placed],
    children: list[RegionNode],
    *,
    ref_x: float | None = None,
    ref_width: float | None = None,
) -> None:
    """Lay ``items`` and ``children`` (sub-regions) out inside ``node``.

    ``ref_x``/``ref_width`` are the container ``columnSpan`` is computed
    against -- ``node``'s own geometry by default. A chrome-less wrapper
    group for loose items below a frame (below) is sized to only its own
    items' tight bounding box; if spans were computed against that box, a
    single item alone in the group would always claim the full grid width
    regardless of how it actually compares to the real page. Passing the
    true ancestor's ``x``/``width`` down for that recursive call keeps
    spans proportional to the container Forms actually drew it on.
    """
    if ref_x is None:
        ref_x = node.x
    if ref_width is None:
        ref_width = node.width
    boxes = [_Box(*p.bounds(), p) for p in items]
    boxes += [_Box(c.x, c.y, c.width, c.height, c) for c in children]
    for placed in items:
        # ItemsDisplay caps how many records an item shows (the audit fields
        # of a grid block show once); otherwise the block's record count.
        shown = placed.item.items_displayed or placed.block.records_displayed
        if shown > 1:
            name = placed.block.name
            node.tabular[name] = max(node.tabular.get(name, 1), shown)
    if node.flow:
        # A toolbar's buttons flow inline with no column arithmetic, but
        # still cluster by real row (Forms often docks a second rank of
        # buttons/fields a few units below the first) rather than all
        # flattening onto one line just because none of them carry columns.
        node.body = []
        for row in _rows(boxes):
            for index, box in enumerate(row):
                box.ref.grid = Grid(new_row=index == 0, new_column=index > 0, flow=True)
                node.body.append(box.ref)
        return

    rows = _rows(boxes)
    first_sub_row = next(
        (i for i, row in enumerate(rows) if any(isinstance(b.ref, RegionNode) for b in row)),
        len(rows),
    )
    # Rows above the first frame are the region's own body ...
    for index, row in enumerate(rows[:first_sub_row]):
        for box, grid in zip(row, _place_row(row, ref_x, ref_width, first=True)):
            box.ref.grid = grid
            _reconcile_label(box.ref)
            node.body.append(box.ref)
    # ... everything from there on is a sub-region: real frames as they are,
    # runs of loose items wrapped in a chrome-less group so vertical order
    # against the frames survives.
    sub_boxes: list[_Box] = []
    group_count = 0
    for row in rows[first_sub_row:]:
        run: list[_Box] = []
        for box in row + [None]:  # type: ignore[list-item]
            if box is not None and isinstance(box.ref, Placed):
                run.append(box)
                continue
            if run:
                group_count += 1
                gx, gy, gw, gh = _union(run)
                group = RegionNode(
                    id=f"{node.id}-row-{group_count}",
                    name=f"{node.name} row {group_count}",
                    title="",
                    template="blank-with-attributes",
                    source=f"items of {node.source} drawn beside or below its frames",
                    x=gx,
                    y=gy,
                    width=gw,
                    height=gh,
                    slot="subRegions",
                    derived=True,
                )
                _arrange(group, [b.ref for b in run], [], ref_x=ref_x, ref_width=ref_width)
                sub_boxes.append(_Box(gx, gy, gw, gh, group))
                run = []
            if box is not None:
                sub_boxes.append(box)
    for row in _rows(sub_boxes):
        for box, grid in zip(row, _place_row(row, ref_x, ref_width, first=True)):
            box.ref.grid = grid
            node.subs.append(box.ref)


def _frame_nodes(
    canvas: Canvas, pairs: list[Placed], root: RegionNode, ids: _Ids, char_w: float
) -> None:
    """Frames and captioned rectangles as sub-regions, nested by containment;
    every item -- and every loose boilerplate text, as a static region -- goes
    to the smallest box around its centre."""
    captions = _captions(canvas.graphics)
    frames: list[tuple[_Box, RegionNode]] = []
    for g, caption, _ in captions:
        node = RegionNode(
            id=ids.take(caption or g.name, f"{root.id}-frame"),
            name=g.name,
            title=caption,
            template="standard",
            source=f"{g.kind.lower()} {g.name} on canvas {canvas.name}",
            x=g.x,
            y=g.y,
            width=max(g.width, 1),
            height=max(g.height, 1),
            slot="subRegions",
        )
        frames.append((_Box(g.x, g.y, g.width, g.height, node), node))

    def smallest_around(px: float, py: float, exclude: _Box | None = None) -> RegionNode | None:
        best: tuple[float, RegionNode] | None = None
        for box, node in frames:
            if box is exclude or not box.contains(px, py):
                continue
            if exclude is not None and box.area <= exclude.area:
                continue
            if best is None or box.area < best[0]:
                best = (box.area, node)
        return best[1] if best else None

    parent_of: dict[int, RegionNode] = {}
    children: dict[int, list[RegionNode]] = {id(root): []}
    for box, node in frames:
        parent = smallest_around(box.cx, box.cy, exclude=box) or root
        parent_of[id(node)] = parent
        children.setdefault(id(parent), []).append(node)
        children.setdefault(id(node), [])

    items_of: dict[int, list[Placed]] = {id(root): []}
    for placed in pairs:
        x, y, w, h = item_box(placed.item)
        home = smallest_around(x + w / 2, y + h / 2) or root
        items_of.setdefault(id(home), []).append(placed)

    consumed = {id(text) for _, _, text in captions if text is not None}
    texts = [
        g
        for g in canvas.graphics
        if g.kind.lower() == "text" and g.text.strip() and id(g) not in consumed
    ]
    for g in _adopt_boilerplate(texts, pairs, char_w):
        tx, ty, tw, th = _text_box(g)
        node = RegionNode(
            id=ids.take(" ".join(g.text.split())[:40], "text"),
            name=g.name,
            title="",
            template="blank-with-attributes",
            source=f"text {g.name} on canvas {canvas.name}",
            x=tx,
            y=ty,
            width=max(tw, 1),
            height=max(th, 1),
            slot="subRegions",
            text=g.text.strip(),
            text_bold=g.text_bold,
        )
        parent = smallest_around(tx + tw / 2, ty + th / 2) or root
        children.setdefault(id(parent), []).append(node)

    def arrange(node: RegionNode) -> None:
        kids = children.get(id(node), [])
        for kid in kids:
            arrange(kid)
        items, grids = _grid_nodes(node, items_of.get(id(node), []), ids)
        if node is not root and not items and not kids and len(grids) == 1:
            _collapse_grid(node, grids[0])
            return
        _arrange(node, items, kids + grids)

    arrange(root)


def _window_title(module: FormModule, canvas: Canvas) -> str:
    window = module.window_details.get(canvas.window_name)
    return " ".join(window.title.split()) if window and window.title else ""


def _canvas_node(
    canvas: Canvas, pairs: list[Placed], module: FormModule, ids: _Ids, char_w: float
) -> RegionNode:
    kind = (canvas.canvas_type or "content").lower()
    title = _window_title(module, canvas)
    width = float(canvas.width or max([p.bounds()[0] + p.bounds()[2] for p in pairs] or [400]))
    height = float(canvas.height or 300)
    node = RegionNode(
        id=ids.take(canvas.name, "canvas"),
        name=canvas.name,
        title=title,
        template="standard",
        source=f"{kind} canvas {canvas.name}"
        + (f" in window {canvas.window_name}" if canvas.window_name else ""),
        width=width,
        height=height,
    )
    if "toolbar" in kind:
        node.template = "blank-with-attributes"
        node.title = ""
        node.flow = True
        node.note = "Forms toolbar: its buttons flow inline above the window's content."
        _arrange(node, pairs, [])
        return node
    if "tab" in kind:
        node.template = "tabs-container"
        node.title = title or humanize(canvas.name)
        node.note = "Forms tab canvas: one tab per tab page, in the .fmb's order."
        pages = canvas.tab_pages or sorted({p.item.tab_page for p in pairs if p.item.tab_page})
        for page_name in pages or ["TAB_1"]:
            tab = RegionNode(
                id=ids.take(page_name, "tab"),
                name=page_name,
                title=" ".join(canvas.tab_page_labels.get(page_name, "").split())
                or humanize(page_name),
                template="standard",
                source=f"tab page {page_name} of canvas {canvas.name}",
                width=width,
                height=height,
                slot="tabs",
            )
            on_tab = [
                p for p in pairs
                if p.item.tab_page == page_name
                or (not p.item.tab_page and page_name == pages[0] if pages else True)
            ]
            items, grids = _grid_nodes(tab, on_tab, ids)
            if not items and len(grids) == 1:
                _collapse_grid(tab, grids[0])
            else:
                _arrange(tab, items, grids)
            node.subs.append(tab)
        return node
    window = module.window_details.get(canvas.window_name)
    if "stacked" in kind and not canvas.visible:
        node.template = "inline-dialog"
        node.title = title or humanize(canvas.name)
        node.note = (
            "Stacked canvas raised on demand in Forms (Visible=false): an inline dialog "
            "here; add a dynamic action that opens it where Forms called SHOW_VIEW."
        )
    elif window is not None and window.modal:
        node.template = "inline-dialog"
        node.title = title or humanize(canvas.name)
        node.note = (
            f"Forms opens window {window.name} as its own modal dialog"
            + (f" (WindowStyle={window.style}, Modal=true)" if window.style else " (Modal=true)")
            + f": an inline dialog here; add a dynamic action that opens it where Forms "
            f"called SHOW_WINDOW/GO_ITEM into {window.name}."
        )
    _frame_nodes(canvas, pairs, node, ids, char_w)
    return node


def _flow_layout(
    module: FormModule, blocks: list[Block], names: dict[str, str], ids: _Ids, char_w: float
) -> list[RegionNode]:
    """No canvas in the module: one region per block, one item per row --
    the only honest layout when the geometry is not there to read."""
    roots: list[RegionNode] = []
    for block in blocks:
        node = RegionNode(
            id=ids.take(block.name, "block"),
            name=block.name,
            title=humanize(block.name),
            template="standard",
            source=f"block {block.name} (module declares no canvases)",
            flow=True,
        )
        for item in block.items:
            placed = _make_placed(item, block, names[f"{block.name}.{item.name}".upper()], char_w)
            if item.visible:
                placed.grid = Grid(new_row=True, flow=True)
                node.body.append(placed)
            else:
                node.hidden.append(placed)
        if block.records_displayed > 1 and _table_bound(block):
            # Declaration order is the only column order there is.
            columns = [p for p in node.body if "button" not in p.item.item_type.lower()]
            for index, placed in enumerate(columns, 1):
                placed.sequence = index * 10
            node.body = [p for p in node.body if p not in columns]
            grid = RegionNode(
                id=ids.take(block.name, "grid"),
                name=block.name,
                title="",
                template="interactive-report",
                source=f"block {block.name} ({block.records_displayed} records at once)",
                slot="subRegions",
                kind="grid",
                columns=columns,
                block=block,
            )
            if node.body:
                # The block's buttons keep the block region; its records go
                # in a grid right under them.
                grid.grid = Grid(new_row=True, flow=True)
                node.subs.append(grid)
            else:
                node.flow = False
                _collapse_grid(node, grid)
        elif block.records_displayed > 1:
            node.tabular[block.name] = block.records_displayed
        roots.append(node)
    return roots


def _static_lovs(layout_items: list[Placed], ids: _Ids) -> list[StaticLov]:
    lovs: list[StaticLov] = []
    for placed in layout_items:
        item = placed.item
        kind = item.item_type.lower()
        if "radio" in kind and item.radio_buttons:
            entries = [(rb.label or rb.name, rb.value or rb.name) for rb in item.radio_buttons]
            declared = any(rb.value for rb in item.radio_buttons)
        elif ("list" in kind or "radio" in kind) and item.choices:
            values = item.choice_values
            entries = [
                (choice, values[i] if i < len(values) and values[i] else choice)
                for i, choice in enumerate(item.choices)
            ]
            declared = any(values)
        else:
            continue
        lovs.append(
            StaticLov(
                id=ids.take(f"lov-{placed.block.name}-{item.name}", "lov"),
                name=_APEX_NAME.sub("_", f"{placed.block.name}_{item.name}".upper())[:255],
                entries=entries,
                source=f"{placed.block.name}.{item.name}",
                declared=declared,
            )
        )
    return lovs


def _number(layout: PageLayout) -> None:
    """Sequences: 10, 20, ... per parent, hidden items after the visible ones."""

    def number(node: RegionNode, sequence: int) -> None:
        node.sequence = sequence
        for index, placed in enumerate(node.body, 1):
            placed.sequence = index * 10
        for index, placed in enumerate(node.hidden, len(node.body) + 1):
            placed.sequence = index * 10
        for index, sub in enumerate(node.subs, 1):
            number(sub, index * 10)

    for index, root in enumerate(layout.roots, 1):
        number(root, index * 10)
    for index, placed in enumerate(layout.hidden, 1):
        placed.sequence = 1000 + index * 10


def build_layout(module: FormModule, page: int = 1) -> PageLayout:
    """The APEX page as the geometry of ``module`` dictates it."""
    names = apex_item_names(module, page)
    ids = _Ids()
    skipped: list[str] = []
    blocks = []
    for block in module.blocks:
        if _WEBUTIL.match(block.name):
            skipped.append(f"block {block.name}: WebUtil library plumbing, no APEX equivalent")
        else:
            blocks.append(block)
    canvases = []
    for canvas in module.canvases:
        if _WEBUTIL.match(canvas.name):
            skipped.append(f"canvas {canvas.name}: WebUtil library plumbing, no APEX equivalent")
        else:
            canvases.append(canvas)

    cell = None
    if module.coordinate_system.lower() == "character":
        cell = (1.0, 1.0)
    elif module.char_cell_width and module.char_cell_height:
        cell = (float(module.char_cell_width), float(module.char_cell_height))
    unit = module.coordinate_unit or ("cell" if module.coordinate_system else "")
    char_w = cell[0] if cell else _CHAR_WIDTH.get(unit.lower(), 5.0)

    if not canvases:
        roots = _flow_layout(module, blocks, names, ids, char_w)
        layout = PageLayout(roots, [], [], names, skipped, cell, unit)
        layout.lovs = _static_lovs(list(layout.placed()), ids)
        _number(layout)
        _decorate(layout)
        return layout

    known = {c.name for c in canvases}
    on_canvas: dict[str, list[Placed]] = {name: [] for name in known}
    hidden: list[Placed] = []
    for block in blocks:
        for item in block.items:
            placed = _make_placed(item, block, names[f"{block.name}.{item.name}".upper()], char_w)
            if item.visible and item.canvas in known:
                on_canvas[item.canvas].append(placed)
            else:
                hidden.append(placed)

    # A window's horizontal toolbar goes right above its content canvas, the
    # way the runtime docks it -- the same pairing the visual preview draws.
    hosted: dict[str, str] = {}  # content canvas -> toolbar canvas
    for window in module.window_details.values():
        if window.toolbar not in known or window.toolbar in hosted.values():
            continue
        for canvas in canvases:
            if (
                canvas.window_name == window.name
                and canvas.name != window.toolbar
                and "toolbar" not in (canvas.canvas_type or "").lower()
            ):
                hosted[canvas.name] = window.toolbar
                break
    by_name = {c.name: c for c in canvases}
    roots: list[RegionNode] = []
    for canvas in canvases:
        if canvas.name in hosted.values():
            continue
        if canvas.name in hosted:
            toolbar = by_name[hosted[canvas.name]]
            roots.append(_canvas_node(toolbar, on_canvas[toolbar.name], module, ids, char_w))
        roots.append(_canvas_node(canvas, on_canvas[canvas.name], module, ids, char_w))

    # Hidden items live under the first region that shows an item of their
    # block, so Page Designer keeps the block together; page level otherwise.
    home_of: dict[str, RegionNode] = {}
    for region in (r for root in roots for r in root.walk()):
        for placed in region.body + region.columns:
            home_of.setdefault(placed.block.name, region)
    loose: list[Placed] = []
    for placed in hidden:
        home = home_of.get(placed.block.name)
        (home.hidden if home is not None else loose).append(placed)

    layout = PageLayout(roots, loose, [], names, skipped, cell, unit)
    layout.lovs = _static_lovs(list(layout.placed()), ids)
    _number(layout)
    _decorate(layout)
    return layout


def _decorate(layout: PageLayout) -> None:
    """Universal Theme template options, per region, from what the region
    is (every value verified against ``apex validate`` on 26.1):

    * a Standard region with no caption -- a frame drawn without a title, a
      canvas in a window without one -- drops its header bar
      (``t-Region--removeHeader js-removeLandmark``) instead of showing an
      empty one;
    * a region holding fields (Standard, Blank with Attributes or Inline
      Dialog) stretches them to their grid cells (``t-Form--stretchInputs``),
      so a field's width is its share of the row -- the proportion Forms
      drew -- rather than a character count;
    * an Interactive Grid with no caption hides its header the same way
      (``t-IRR-region--hideHeader js-addHiddenHeadingRoleDesc``).
    """
    for node in layout.regions():
        options: list[str] = []
        if node.kind == "grid":
            if not node.title:
                options.append("t-IRR-region--hideHeader js-addHiddenHeadingRoleDesc")
        else:
            if node.template == "standard" and not node.title:
                options.append("t-Region--removeHeader js-removeLandmark")
            if (
                node.template in {"standard", "blank-with-attributes", "inline-dialog"}
                and not node.flow
                and any("button" not in p.item.item_type.lower() for p in node.body)
            ):
                options.append("t-Form--stretchInputs")
        node.options = options


#: The desktop viewport the grid placement is designed and checked against.
DESKTOP_VIEWPORT = (
    "desktop, 1280 CSS px wide, Universal Theme Standard page template, 12-column "
    "grid; on narrow screens Universal Theme stacks the cells of a row, one per line"
)

FAITHFUL = "faithful"
APPROXIMATION = "approximation"
UNSUPPORTED = "unsupported"


def _geometry(item: Item) -> dict | None:
    if item.x is None and item.y is None and not item.radio_buttons:
        return None
    x, y, w, h = item_box(item)
    return {"x": x, "y": y, "width": w, "height": h}


def _grid_dict(grid: Grid | None) -> dict:
    if grid is None:
        return {}
    if grid.flow:
        return {"flow": True, "startNewRow": grid.new_row}
    return {
        "startNewRow": grid.new_row,
        "newColumn": grid.new_column,
        "column": grid.column,
        "columnSpan": grid.span,
    }


def _control_entry(
    placed: Placed, region: RegionNode, layout: PageLayout, *, column_index: int = 0
) -> dict:
    """One visible control's line in the report: where it came from, where
    it landed, which rule put it there, and how faithful that is."""
    item, block = placed.item, placed.block
    kind = item.item_type.lower()
    is_button = "button" in kind
    lov = next(
        (l for l in layout.lovs if l.source.upper() == f"{block.name}.{item.name}".upper()), None
    )
    preserved: list[str] = ["name", "reading order"]
    approximations: list[str] = []
    unsupported: list[str] = []
    missing: list[str] = []
    if _geometry(item) is None:
        missing.append("geometry")
        approximations.append(
            "no position or size in the .fmb: placed after its neighbours, full width"
        )
    if placed.caption:
        preserved.append("caption")
    if column_index:
        component = "gridColumn"
        target_type = apex_item_type(item)
        rule = (
            f"{item.item_type} of a multi-record block on a table: Interactive Grid "
            f"column {column_index} of {len(region.columns)}, in the left-to-right "
            "order Forms draws the record"
        )
    elif is_button:
        component = "button"
        target_type = "button"
        rule = "Push Button: button in the region, at the row and column Forms draws it"
    else:
        component = "pageItem"
        target_type = apex_item_type(item)
        rule = f"{item.item_type}: {target_type} item in the region, at the row and column Forms draws it"
        if placed.side in {"left", "above"}:
            preserved.append("caption side")
        elif placed.side == "right":
            approximations.append(
                "prompt right of the field floats inside it: Universal Theme has no label "
                "template on that side"
            )
        elif placed.side == "below":
            approximations.append(
                "prompt below the field floats inside it: Universal Theme has no label "
                "template on that side"
            )
        if placed.side == "left" and placed.grid is not None and not placed.grid.flow:
            if placed.label_span:
                preserved.append("label share of the row")
            else:
                approximations.append(
                    "label floats inside the field: its row was too crowded to give the "
                    "label its own grid columns"
                )
        if placed.note:
            approximations.append(placed.note[0].upper() + placed.note[1:])
        if block.name in region.tabular:
            approximations.append(
                f"first record's row only: Forms shows {region.tabular[block.name]} records "
                "of this block here and no Interactive Grid could be built (see the region)"
            )
        if _records_shown(placed) == 1 and block.records_displayed > 1 and any(
            r.block is block for r in layout.regions()
        ):
            approximations.append(
                "shown once, outside the block's grid: ItemsDisplay=1 keeps it out of the "
                "record rows in Forms too"
            )
    if not is_button:
        if item.width:
            preserved.append("width")
        if item.multi_line and item.height:
            preserved.append("height")
        if item.required and target_type != "displayOnly":
            preserved.append("required")
        if item.format_mask and target_type in {"numberField", "datePicker"}:
            preserved.append("format mask")
        elif item.data_type.lower() == "datetime" and target_type == "datePicker":
            approximations.append(
                "Datetime without a format mask: the date picker shows the application "
                "date format until a mask is set"
            )
        if item.tooltip or item.hint:
            preserved.append("help text")
        if item.case_restriction.lower() in {"upper", "lower"} and target_type == "textField":
            preserved.append("case restriction")
        if not item.enabled:
            preserved.append("disabled (read only)")
        if lov is not None:
            preserved.append("static choices" + ("" if lov.declared else " (return values need review)"))
            if not lov.declared:
                approximations.append(
                    "the .fmb declares no return values for the choices: labels stand in"
                )
        if placed.radio_columns > 1:
            preserved.append("radio buttons per row")
        if column_index and item.primary_key:
            preserved.append("primary key")
        if column_index and not item.database_item:
            preserved.append("no database column")
    if not column_index and placed.grid is not None and placed.grid.flow:
        approximations.append(
            "toolbar flow: controls keep their order and rows, not their exact positions"
        )
    reason = unsupported_reason(item)
    if reason:
        unsupported.append(reason)
    status = UNSUPPORTED if unsupported else APPROXIMATION if approximations else FAITHFUL
    # The name is the identifier the page file uses for the component, so
    # the report and the export can be read side by side.
    if column_index:
        target_name = column_name(item)
    elif is_button:
        target_name = button_id(placed)
    else:
        target_name = placed.apex_name
    target: dict = {
        "component": component,
        "type": target_type,
        "name": target_name,
        "region": region.id,
        "sequence": placed.sequence,
    }
    if column_index:
        target["column"] = column_index
    else:
        target["grid"] = _grid_dict(placed.grid)
        if not is_button:
            target["label"] = {
                "text": placed.label,
                "side": placed.side,
                "labelColumnSpan": placed.label_span,
                "alignment": placed.align,
            }
    return {
        "source": f"{block.name}.{item.name}",
        "kind": item.item_type,
        "canvas": item.canvas,
        "tab_page": item.tab_page,
        "geometry": _geometry(item),
        "target": target,
        "rule": rule,
        "preserved": preserved,
        "approximations": approximations,
        "unsupported": unsupported,
        "missing": missing,
        "status": status,
    }


def _group_entry(node: RegionNode, parent: RegionNode | None) -> dict:
    """A region's line in the report: the Forms group it stands for."""
    approximations: list[str] = []
    if node.template == "inline-dialog":
        approximations.append(
            "shown on demand in Forms (a stacked canvas or secondary window): the inline "
            "dialog needs a dynamic action, added by the developer, to open it"
        )
    if node.flow:
        approximations.append("toolbar: controls flow inline, in their rows and order")
    for name, records in node.tabular.items():
        approximations.append(
            f"block {name}: Forms shows {records} records here, the first record's row "
            "is laid out (no table to build an Interactive Grid on)"
        )
    if node.kind == "grid":
        approximations.append(
            "Interactive Grid: record rows, paging and row height are the grid's own; "
            "editing is off until the developer confirms the block's DML"
        )
    status = APPROXIMATION if approximations else FAITHFUL
    return {
        "id": node.id,
        "name": node.name,
        "title": node.title,
        "source": node.source,
        "kind": node.kind,
        "template": node.template,
        "template_options": list(node.options),
        "parent": parent.id if parent is not None else "",
        "slot": node.slot,
        "grid": _grid_dict(node.grid),
        "geometry": {"x": node.x, "y": node.y, "width": node.width, "height": node.height},
        "controls": len(node.body) + len(node.columns),
        "hidden_items": len(node.hidden),
        "derived": node.derived,
        "approximations": approximations,
        "status": status,
    }


def _hidden_target(placed: Placed, node: RegionNode) -> dict:
    """Where a hidden item went, named as the page file names it: a hidden
    column of the block's grid when a database column stands behind it
    (the exporter writes it inside the grid), otherwise a hidden page item."""
    if node.kind == "grid" and database_column(placed.item):
        return {
            "component": "gridColumn",
            "type": "hidden",
            "name": column_name(placed.item),
            "region": node.id,
        }
    return {"component": "pageItem", "type": "hidden", "name": placed.apex_name, "region": node.id}


def layout_report(layout: PageLayout) -> dict:
    """The layout mapping report: every visible Forms control and every
    Forms group, where it landed and how faithfully, with explicit
    denominators (no percentage is derived).

    * ``controls`` counts every visible item, button and grid column once
      -- the denominator is the number of visible controls the .fmb draws;
    * ``groups`` counts the regions that stand for a Forms group (canvas,
      frame, tab page, block grid, boilerplate text); the row wrappers the
      layout invents to keep vertical order are listed but not counted;
    * hidden items are listed, not scored: nothing of them is visible.
    """
    controls: list[dict] = []
    groups: list[dict] = []
    hidden: list[dict] = []

    def walk(node: RegionNode, parent: RegionNode | None) -> None:
        groups.append(_group_entry(node, parent))
        for placed in node.body:
            controls.append(_control_entry(placed, node, layout))
        for index, placed in enumerate(node.columns, 1):
            controls.append(_control_entry(placed, node, layout, column_index=index))
        for placed in node.hidden:
            hidden.append(
                {
                    "source": f"{placed.block.name}.{placed.item.name}",
                    "kind": placed.item.item_type,
                    "target": _hidden_target(placed, node),
                    "database_column": database_column(placed.item),
                }
            )
        for sub in node.subs:
            walk(sub, node)

    for root in layout.roots:
        walk(root, None)
    for placed in layout.hidden:
        hidden.append(
            {
                "source": f"{placed.block.name}.{placed.item.name}",
                "kind": placed.item.item_type,
                "target": {"component": "pageItem", "type": "hidden", "name": placed.apex_name, "region": ""},
                "database_column": database_column(placed.item),
            }
        )
    names = [c["target"]["name"] for c in controls]
    duplicates = sorted({n for n in names if names.count(n) > 1})
    counted = [g for g in groups if not g["derived"]]

    def tally(entries: list[dict]) -> dict:
        return {
            "total": len(entries),
            FAITHFUL: sum(e["status"] == FAITHFUL for e in entries),
            APPROXIMATION: sum(e["status"] == APPROXIMATION for e in entries),
            UNSUPPORTED: sum(e["status"] == UNSUPPORTED for e in entries),
        }

    return {
        "viewport": DESKTOP_VIEWPORT,
        "totals": {
            "controls": tally(controls),
            "groups": tally(counted),
            "derived_groups": len(groups) - len(counted),
            "hidden_items": len(hidden),
            "skipped": len(layout.skipped),
            "controls_placed_twice": duplicates,
        },
        "controls": controls,
        "groups": groups,
        "hidden": hidden,
        "skipped": list(layout.skipped),
    }
