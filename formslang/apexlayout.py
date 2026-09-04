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
# Boilerplate text ending within this many characters of an uncaptioned
# item's left edge is that item's prompt.
_PROMPT_REACH = 4


def _slug(value: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-z0-9]+", "-", ascii_text.strip().lower()).strip("-")
    return text[:60].rstrip("-")


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
        for region in self.regions():
            yield from region.body

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
        cell = _CHAR_WIDTH.get(self.unit.lower(), 5.0)
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
    return placed


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
        _arrange(node, items_of.get(id(node), []), kids)

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
                title=humanize(page_name),
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
            _arrange(tab, on_tab, [])
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
        if block.records_displayed > 1:
            node.tabular[block.name] = block.records_displayed
        roots.append(node)
    return roots


def _static_lovs(layout_items: list[Placed], ids: _Ids) -> list[StaticLov]:
    lovs: list[StaticLov] = []
    for placed in layout_items:
        item = placed.item
        kind = item.item_type.lower()
        if "radio" in kind and item.radio_buttons:
            entries = [(rb.label or rb.name, rb.name) for rb in item.radio_buttons]
        elif ("list" in kind or "radio" in kind) and item.choices:
            entries = [(choice, choice) for choice in item.choices]
        else:
            continue
        lovs.append(
            StaticLov(
                id=ids.take(f"lov-{placed.block.name}-{item.name}", "lov"),
                name=_APEX_NAME.sub("_", f"{placed.block.name}_{item.name}".upper())[:255],
                entries=entries,
                source=f"{placed.block.name}.{item.name}",
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
        for placed in region.body:
            home_of.setdefault(placed.block.name, region)
    loose: list[Placed] = []
    for placed in hidden:
        home = home_of.get(placed.block.name)
        (home.hidden if home is not None else loose).append(placed)

    layout = PageLayout(roots, loose, [], names, skipped, cell, unit)
    layout.lovs = _static_lovs(list(layout.placed()), ids)
    _number(layout)
    return layout
