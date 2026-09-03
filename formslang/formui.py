"""Self-contained HTML visual preview: Forms UI vs. the APEX default mapping.

Same rendering philosophy as :mod:`formslang.formdoc` and
:mod:`formslang.formdiff`: no CDN, no remote fonts, no build step, own copy
of the small HTML-building helpers (each report is meant to stand alone).

Read-only by construction, on purpose. The top half mocks up every Forms
window the way the runtime paints it, from the look :mod:`formslang.parser`
keeps (see ``formslang/model.py``'s docstring): the module's own coordinate
unit converted to pixels, the boilerplate graphics under the items, each
item at its bevel/font/colour, as many instances as a multi-record block
shows, and every prompt hung on the edge the .fmb attaches it to with the
.fmb's own alignment and offsets -- nothing measured, nothing guessed. The
bottom half shows the page as APEX would receive it, drawn from the very
tree the exporter writes -- :func:`formslang.apexlayout.build_layout` for
the regions, rows, columns, captions and boilerplate text,
:func:`formslang.apexlang._item_type` and
:func:`formslang.apexlang._label_template` for each item -- so this report
can never drift from what an actual export produces: a region per canvas
and frame, items on the 12-column grid where the geometry puts them, the
label left of the field, above it or floating in it as the Forms prompt
sits, nothing invented. There is deliberately no control to pick a different APEX widget
for a Forms item: that choice belongs in APEX Builder, after export, never
here.
"""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from pathlib import Path

from .apexlang import _item_type, _label_template
from .apexlayout import GRID_COLUMNS, PageLayout, Placed, RegionNode, build_layout
from .model import Block, Canvas, FormModule, Graphic, Item, VisualAttribute

_CSS = """
:root{
 --bg:#07090C;--surface:#12151A;--surface2:#161A21;--line:#242832;--line2:#2E333F;
 --fg:#F2F4F7;--mut:#8A9099;--gold:#F5A640;--gold-dim:rgba(245,166,64,.12);
 --good:#5BD98A;--bad:#F0736F
}
*{box-sizing:border-box}
::selection{background:rgba(245,166,64,.28);color:var(--fg)}
::-webkit-scrollbar{width:10px;height:10px}
::-webkit-scrollbar-track{background:var(--bg)}
::-webkit-scrollbar-thumb{background:var(--line);border-radius:6px}
::-webkit-scrollbar-thumb:hover{background:var(--line2)}
body{margin:0;background:var(--bg);color:var(--fg);
 font:15px/1.6 "Segoe UI",Inter,system-ui,sans-serif}
.wrap{max-width:1280px;margin:0 auto;padding:40px 24px 80px}
.kicker{color:var(--gold);font-size:11px;font-weight:700;text-transform:uppercase;
 letter-spacing:.14em;margin:0 0 10px}
.hero{position:relative;padding-bottom:24px;margin-bottom:8px}
.hero::after{content:"";position:absolute;left:0;bottom:0;width:64px;height:3px;
 background:linear-gradient(90deg,var(--gold),transparent);border-radius:2px}
h1{font-size:32px;margin:0 0 6px;letter-spacing:-.02em}
h2{font-size:19px;margin:36px 0 6px;letter-spacing:-.01em;
 border-bottom:1px solid var(--line);padding-bottom:8px}
.sub{color:var(--mut);margin:4px 0 0;font-size:12.5px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
.card{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:16px 18px}
.card .n{font-size:27px;font-weight:600;color:var(--gold);letter-spacing:-.02em}
.card .l{color:var(--mut);font-size:12px;text-transform:uppercase;letter-spacing:.07em;margin-top:2px}
.tag{display:inline-block;padding:1px 8px;border-radius:999px;font-size:11px;font-weight:600;
 letter-spacing:.03em;white-space:nowrap}
.yes{background:#123021;color:var(--good)}.no{background:#2A1418;color:var(--bad)}
.dim{background:#1C2028;color:var(--mut)}
.entity{background:var(--surface);border:1px solid var(--line);border-radius:10px;
 padding:14px 16px;margin:14px 0}
.entity>.hd{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}
.entity>.hd b{font-size:15px}
.none{color:var(--mut);font-style:italic;padding:8px 0;font-size:13px;overflow-wrap:anywhere}
.warn{background:#3A2E10;border:1px solid #5A4620;color:var(--gold);border-radius:8px;
 padding:10px 14px;margin:6px 0 20px;font-size:13px;overflow-wrap:anywhere}

/* Forms side: each window at real pixel size, scrolling sideways inside its
   own frame when it is wider than the page -- never shrunk into illegibility. */
.f-scroll{overflow:auto;margin-top:10px;border:1px solid var(--line2);border-radius:6px;
 background:#0B0D11;padding:16px}
.f-win{display:inline-block;vertical-align:top;border:1px solid #5C5C5C;background:#CCC;
 box-shadow:0 10px 30px rgba(0,0,0,.55)}
.f-titlebar{height:26px;padding:0 4px 0 9px;display:flex;align-items:center;gap:8px;
 background:linear-gradient(#4A78C2,#2C4F8A);color:#fff;white-space:nowrap;
 font:600 12px "Segoe UI",Tahoma,Arial,sans-serif}
.f-titlebar span{flex:1;overflow:hidden;text-overflow:ellipsis}
.f-titlebar i{width:18px;height:16px;border:1px solid #D7E1F2;border-radius:2px;flex:none;
 font:11px/14px Arial,sans-serif;font-style:normal;text-align:center;opacity:.9}
.f-canvas{position:relative;overflow:hidden;color:#000;font:12px/1.15 Arial,Helvetica,sans-serif}
.f-canvas.f-toolbar{border-bottom:1px solid #8C8C8C}
/* boilerplate */
.f-g{position:absolute}
.g-text{display:flex;align-items:center;white-space:pre;padding:0 1px}
.g-text.wrap{white-space:pre-wrap}
.g-image{border:1px dashed #7A7A7A;display:flex;align-items:center;justify-content:center;
 font:10px Arial,sans-serif;color:#333;overflow:hidden;white-space:nowrap}
.g-line-h{border-top:1px solid #808080;border-bottom:1px solid #FFF}
.g-line-v{border-left:1px solid #808080;border-right:1px solid #FFF}
.f-title{position:absolute;white-space:nowrap;line-height:1.15}
/* the five bevels Forms paints */
.b-lowered{border:1px solid;border-color:#6E6E6E #FFF #FFF #6E6E6E;box-shadow:inset 1px 1px 0 #A8A8A8}
.b-inset{border:1px solid;border-color:#808080 #FFF #FFF #808080}
.b-raised{border:1px solid;border-color:#FFF #6E6E6E #6E6E6E #FFF;box-shadow:inset -1px -1px 0 #A8A8A8}
.b-outset{border:1px solid;border-color:#FFF #808080 #808080 #FFF}
.b-plain{border:1px solid #000}
.b-none{border:1px solid transparent}
/* items */
.f-item{position:absolute;overflow:hidden;white-space:nowrap;padding:0 2px;
 display:flex;align-items:center}
.f-text,.f-list{background:#fff}
.f-list{padding-right:15px}
.f-list::after{content:"\\25BE";position:absolute;right:0;top:0;bottom:0;width:13px;
 display:flex;align-items:center;justify-content:center;background:#E0E0E0;
 border-left:1px solid #9A9A9A;font-size:9px;color:#222}
.f-display{background:transparent}
.f-check{padding:0;gap:4px;overflow:visible}
.f-check i{width:11px;height:11px;border:1px solid;border-color:#6E6E6E #FFF #FFF #6E6E6E;
 background:#fff;flex:none}
.f-radio{padding:0;gap:3px;overflow:visible;background:transparent}
.f-radio i{width:10px;height:10px;border:1px solid #555;border-radius:50%;background:#fff;flex:none}
.f-button{justify-content:center;background:#E4E4E4;color:#000;padding:0 3px}
.f-button.f-icon{padding:0;font-size:13px;background:#D8D8D8}
.f-other{background:repeating-linear-gradient(45deg,#BEBEBE,#BEBEBE 4px,#D2D2D2 4px,#D2D2D2 8px);
 border:1px dashed #666;color:#333;justify-content:center;font-style:italic}
.f-off{opacity:.55}
.f-prompt{position:absolute;white-space:pre;line-height:1.15;color:#000}

/* APEX side: the Universal Theme page as the export builds it -- a region
   per canvas and per frame, every item in the row and 12-column cell its
   Forms geometry maps to, the label left of the field, above it or floating
   in it as the Forms prompt sits, boilerplate text as static regions. */
.a-page{background:#F5F6F7;border:1px solid var(--line);border-radius:8px;padding:16px;
 color:#1B1F27;font:13px/1.4 "Segoe UI",Inter,system-ui,sans-serif;margin-top:14px}
.a-region{background:#fff;border:1px solid #E0E3E8;border-radius:4px;
 box-shadow:0 1px 2px rgba(0,0,0,.06);margin:0 0 14px;min-width:0}
.a-region>summary{list-style:none;cursor:pointer;display:flex;align-items:center;gap:10px;
 padding:10px 14px;border-bottom:1px solid #E7EAEE;font-weight:600;font-size:14px;flex-wrap:wrap}
.a-region>summary::-webkit-details-marker{display:none}
.a-region>summary .meta{margin-left:auto;display:flex;gap:6px;align-items:center;flex-wrap:wrap}
.a-region.a-blank>summary{background:#F8F9FA;font-weight:500;font-size:12px;
 color:#5A6270;padding:5px 14px}
.a-region.a-dialog{border:1px dashed #9AA1AC;background:#FBFBFC}
.a-region.a-tabs>summary{border-bottom:3px solid #1F5FBF}
.untitled{color:#8A9099;font-weight:500;font-style:italic}
.a-body{padding:12px 14px;display:flex;flex-direction:column;gap:8px}
.a-row{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:8px;align-items:end}
.a-row.a-flow{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.a-cell{min-width:0}
.a-row:not(.a-flow)>.a-cell{container-type:inline-size}
@container (max-width:150px){.kind:not(.no){display:none}.a-field .lbl{right:10px}}
.a-cell.shared{display:flex;gap:6px;align-items:end}
.a-cell.shared>.a-item{flex:1 1 0}
.a-cell:has(>.a-region){align-self:start}
.a-cell>.a-region{margin:0}
.a-item{min-width:0;overflow:hidden}
.a-row.a-flow .a-field{min-width:120px}
.a-field{position:relative;border:1px solid #C5CAD3;border-radius:2px;background:#fff;
 min-height:40px;padding:19px 10px 4px}
.a-field .lbl{position:absolute;left:10px;top:4px;right:58px;font-size:11px;color:#5A6270;
 overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.a-above>.lbl{display:block;font-size:11px;color:#5A6270;margin:0 0 2px;
 overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.a-above>.a-field{min-height:30px;padding-top:8px}
.a-above>.lbl{text-align:var(--al,left)}
.a-left{display:grid;grid-template-columns:calc(var(--lbl,3)/12*100%) minmax(0,1fr);
 gap:0 8px;align-items:center}
.a-left>.lbl{font-size:12px;color:#1B1F27;text-align:var(--al,right);overflow:hidden;
 text-overflow:ellipsis;white-space:nowrap}
.a-left>.a-field{min-height:32px;padding:8px 10px 4px}
.a-text{padding:6px 8px;background:transparent;border:1px dashed #D5D9E0;box-shadow:none;
 font-size:13px;color:#1B1F27;white-space:pre-wrap;overflow-wrap:normal;overflow:hidden}
.a-display{background:#F5F6F7;border-style:dashed}
.a-area{min-height:72px}
.a-select::after{content:"\\25BE";position:absolute;right:8px;bottom:6px;font-size:10px;color:#5A6270}
.a-check{position:relative;display:flex;align-items:center;gap:8px;min-height:32px}
.a-check .txt{min-width:0;line-height:1.25}
.a-check i{width:16px;height:16px;border:1px solid #9AA1AC;border-radius:3px;background:#fff;flex:none}
.a-radio{position:relative;display:flex;flex-wrap:wrap;gap:4px 14px;align-items:center;
 min-height:32px}
.a-check .kind:not(.no),.a-radio .kind:not(.no){display:none}
.a-check .kind.no,.a-radio .kind.no{position:static;flex:none;margin-left:auto}
.a-radio>.lbl{flex:1 0 100%;font-size:11px;color:#5A6270}
.a-radio span{display:inline-flex;align-items:center;gap:6px;white-space:nowrap}
.a-radio i{width:14px;height:14px;border:1px solid #9AA1AC;border-radius:50%;background:#fff;flex:none}
.a-btn{position:relative;display:inline-block;background:#fff;border:1px solid #C5CAD3;
 border-radius:2px;padding:5px 12px;font-size:12px;font-weight:600;color:#1B1F27;
 white-space:nowrap;max-width:100%;overflow:hidden;text-overflow:ellipsis}
.a-btn .kind{display:none}
.kind{position:absolute;right:6px;top:4px;font-size:9px;line-height:12px;color:#9AA1AC;
 white-space:nowrap}
.kind.no{color:var(--bad);font-weight:600}
.req{color:#C0392B;font-style:normal;margin-left:2px}
.a-chips{display:flex;flex-wrap:wrap;gap:6px}
.a-note{font-size:11.5px;color:#5A6270;background:#FFF7E6;border:1px solid #F5D7A1;
 border-radius:3px;padding:6px 10px;margin:0 0 4px;overflow-wrap:anywhere}
@media print{.card,.entity{background:#f6f6f6;border-color:#ccc}
 .f-scroll{overflow:visible}}
"""

# Widget shapes this report has direct evidence for (each APEXlang keyword
# accepted by ``apex validate``) -- everything else (Image, Bean Area, OLE,
# Tree, ...) lands on the same textField fallback _item_type() itself falls
# back to, and is flagged "approx" rather than silently claimed as a mapping.
_CONFIRMED_HINTS = ("button", "display", "check", "editor", "area", "radio", "list")

# How the APEX side names a region's template when it is not the plain
# Standard one; keyed on the slugs apexlayout assigns.
_TEMPLATE_BADGES = {
    "inline-dialog": "inline dialog",
    "tabs-container": "tabs container",
    "blank-with-attributes": "no chrome",
}

# CSS pixels per Forms real unit (CSS defines 1in = 96px, 1pt = 1/72in).
_UNIT_PX = {
    "point": 96 / 72,
    "pixel": 1.0,
    "inch": 96.0,
    "centimeter": 96 / 2.54,
    "decipoint": 96 / 720,
}

# What Forms falls back to when the .fmb states nothing: the grey canvas of
# the Oracle look-and-feel, 9pt text (real modules set 900 = 9pt everywhere).
_DEFAULT_CANVAS_BG = "#D4D4D4"
_DEFAULT_FONT_PT = 9
_FONT_ALIASES = {"ms sans serif": "Microsoft Sans Serif"}

# A multi-record block paints one instance per record; cap runaway counts.
_MAX_INSTANCES = 60

# Iconic buttons carry a .gif/.ico the module does not ship; a glyph keyed on
# the icon or button name is the closest honest stand-in.
_ICON_GLYPHS = (
    ("exit", "⏻"),
    ("sair", "⏻"),
    ("print", "⎙"),
    ("impr", "⎙"),
    ("commit", "\U0001f4be"),
    ("save", "\U0001f4be"),
    ("salv", "\U0001f4be"),
    ("grav", "\U0001f4be"),
    ("query", "\U0001f50d"),
    ("find", "\U0001f50d"),
    ("consul", "\U0001f50d"),
    ("pesq", "\U0001f50d"),
    ("exec", "▶"),
    ("delete", "✖"),
    ("remove", "✖"),
    ("excl", "✖"),
    ("insert", "＋"),
    ("incl", "＋"),
    ("add", "＋"),
    ("new", "＋"),
    ("first", "⏮"),
    ("prev", "◀"),
    ("ant", "◀"),
    ("next", "▶"),
    ("prox", "▶"),
    ("last", "⏭"),
    ("help", "?"),
    ("ajuda", "?"),
    ("clear", "⌫"),
    ("limp", "⌫"),
    ("lov", "☰"),
    ("list", "☰"),
    ("edit", "✎"),
    ("cancel", "↶"),
)

_GRAY = re.compile(r"gray(\d{1,3})")
_RGB = re.compile(r"r(\d{1,3})g(\d{1,3})b(\d{1,3})")
_KEYWORD = re.compile(r"[a-z]+")


def _esc(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _apex_kind(item: Item) -> str:
    """The widget this item becomes in APEX -- the exporter's own answer.

    Push buttons never reach :func:`_item_type` in the real exporter (see
    ``apexlang.py::_page_items``); mirror that special case here so this
    report never invents a mapping the exporter itself does not make.
    """
    if "button" in item.item_type.lower():
        return "button"
    return _item_type(item)


def _has_confirmed_mapping(item: Item) -> bool:
    kind = item.item_type.lower().strip()
    return kind == "text item" or any(h in kind for h in _CONFIRMED_HINTS)


# -- look: units, colours, fonts ---------------------------------------------


def _px_factors(module: FormModule) -> tuple[float, float]:
    """CSS pixels per coordinate unit, horizontally and vertically.

    Forms2XML keeps every position in the module's ``<Coordinate>`` unit and
    real modules overwhelmingly use points, so drawing the raw numbers as
    pixels squeezes every canvas to three quarters of its size -- that was
    the illegible preview. A "Character" system counts character cells,
    whose size the module states in the real unit.
    """
    unit = _UNIT_PX.get(module.coordinate_unit.lower(), 1.0)
    if module.coordinate_system.lower() == "character":
        return (module.char_cell_width or 6) * unit, (module.char_cell_height or 14) * unit
    return unit, unit


def _unit_note(module: FormModule) -> str:
    fx, fy = _px_factors(module)
    if not module.coordinate_unit and not module.coordinate_system:
        return "The module declares no coordinate system; geometry is drawn as pixels."
    if module.coordinate_system.lower() == "character":
        return (
            f"Geometry is in character cells ({module.coordinate_unit or 'point'} cells, "
            f"{fx:.2f}×{fy:.2f} px each). Drawn at real size; scroll a window that is "
            "wider than the page."
        )
    unit = module.coordinate_unit or "unknown unit"
    return (
        f"Geometry is in {unit.lower()}s (1 {unit.lower()} = {fx:.2f} px). Drawn at "
        "real size; scroll a window that is wider than the page."
    )


def _css_color(name: str) -> str:
    """A Forms colour name as CSS.

    ``grayNN`` is NN% ink -- ``gray20`` is the light canvas grey real modules
    use for everything that must blend with the canvas; ``rNNgNNbNN`` is
    percentages (or 0-255 when a component exceeds 100); the rest are the
    X11-style keywords CSS knows under the same names. Anything else, and
    the "use the default" names, come back empty so the caller's default
    applies.
    """
    n = (name or "").strip().lower()
    if not n or n in ("canvas", "default", "none"):
        return ""
    m = _GRAY.fullmatch(n)
    if m:
        v = max(0, min(255, 255 - round(int(m.group(1)) * 255 / 100)))
        return f"#{v:02X}{v:02X}{v:02X}"
    m = _RGB.fullmatch(n)
    if m:
        parts = [int(g) for g in m.groups()]
        as_255 = max(parts) > 100
        return "#" + "".join(
            f"{min(255, p if as_255 else round(p * 255 / 100)):02X}" for p in parts
        )
    if _KEYWORD.fullmatch(n):
        return n
    return ""


def _font_px(pt: int) -> float:
    return round((pt or _DEFAULT_FONT_PT) * 96 / 72, 1)


def _font_css(name: str, pt: int, bold: bool) -> str:
    family = _FONT_ALIASES.get(name.lower(), name) if name else "Arial"
    weight = "bold " if bold else ""
    return f'font:{weight}{_font_px(pt):g}px/1.15 "{family}",Arial,sans-serif'


def _line_px(pt: int) -> int:
    """Height of one line of text at ``pt`` points, as the CSS above lays it out."""
    return round(_font_px(pt) * 1.15)


def _item_look(item: Item, module: FormModule) -> tuple[str, str, str, int, bool]:
    """(fg, bg, font family, font points, bold), item over its visual attribute.

    A ``transparent``/``none`` fill pattern means Forms does not paint the
    background at all, whatever colour the item names.
    """
    va = module.visual_attributes.get(item.visual_attribute) or VisualAttribute("")
    fg = _css_color(item.fg_color or va.fg_color)
    bg = ""
    if item.fill.lower() not in ("transparent", "none"):
        bg = _css_color(item.bg_color or va.bg_color)
    return (
        fg,
        bg,
        item.font_name or va.font_name,
        item.font_size or va.font_size,
        item.font_bold or va.font_bold,
    )


def _bevel_class(item: Item, widget: str) -> str:
    bevel = item.bevel.lower()
    if bevel in ("lowered", "raised", "inset", "outset", "none", "plain"):
        return f"b-{bevel}"
    return {"button": "b-raised", "check": "b-none", "radio": "b-none"}.get(widget, "b-lowered")


def _icon_glyph(item: Item) -> str:
    key = f"{item.icon_name} {item.name}".lower()
    for needle, glyph in _ICON_GLYPHS:
        if needle in key:
            return glyph
    return (item.icon_name or item.name.replace("BT_", ""))[:1].upper() or "▣"


# -- Forms side ----------------------------------------------------------------


def _canvas_box_size(canvas: Canvas, items: list[Item]) -> tuple[int, int]:
    if canvas.width and canvas.height:
        return canvas.width, canvas.height
    xs = [(it.x or 0) + (it.width or 0) for it in items]
    ys = [(it.y or 0) + (it.height or 0) for it in items]
    return max(xs, default=400) or 400, max(ys, default=300) or 300


def _forms_widget(item: Item) -> str:
    """Which classic Forms control to paint. Purely visual; unrelated to the APEX mapping."""
    kind = item.item_type.lower()
    if "button" in kind:
        return "button"
    if "check" in kind:
        return "check"
    if "radio" in kind:
        return "radio"
    if "list" in kind:
        return "list"
    if "display" in kind:
        return "display"
    if "text" in kind or "editor" in kind:
        return "text"
    return "other"  # Bean Area, Image, OLE, Tree, Chart, ...


def _instances(item: Item, block: Block) -> int:
    """How many copies of the item Forms paints: ``ItemsDisplay`` when the
    .fmb sets it (the audit fields and buttons of a grid block show once),
    else as many as the block's records."""
    return max(1, min(_MAX_INSTANCES, item.items_displayed or block.records_displayed))


def _item_box(item: Item, fx: float, fy: float, instance: int) -> tuple[int, int, int, int]:
    step = ((item.height or 14) + item.records_distance) * instance
    return (
        round((item.x or 0) * fx),
        round(((item.y or 0) + step) * fy),
        max(8, round((item.width or 60) * fx)),
        max(8, round((item.height or 14) * fy)),
    )


def _forms_item_mock(
    item: Item, module: FormModule, fx: float, fy: float, *, instance: int = 0
) -> str:
    """One item (or one record's instance of a tabular item) at its real place."""
    widget = _forms_widget(item)
    if widget == "radio" and any(rb.x is not None and rb.y is not None for rb in item.radio_buttons):
        return _forms_radio_mocks(item, module, fx, fy, instance)
    left, top, width, height = _item_box(item, fx, fy, instance)
    fg, bg, font_name, font_pt, bold = _item_look(item, module)
    # The current record wears its own visual attribute; with no data loaded
    # that is the first instance, exactly as the runtime starts.
    record_va = module.visual_attributes.get(item.record_visual_attribute)
    if instance == 0 and record_va and widget in ("text", "display", "list"):
        bg = _css_color(record_va.bg_color) or bg
        fg = _css_color(record_va.fg_color) or fg
    # What Forms paints inside the control; fields stay empty, like a fresh record.
    if widget == "button":
        caption = _esc(_icon_glyph(item)) if item.iconic else _esc(item.label or item.name)
    elif widget == "check":
        caption = f"<i></i>{_esc(item.label)}"
    elif widget == "list":
        caption = _esc(item.choices[0] if item.choices else "")
    elif widget == "radio":
        caption = " ".join(f"<i></i>{_esc(c)}" for c in item.choices) or _esc(item.label)
    elif widget == "other":
        caption = _esc(item.item_type)
    else:
        caption = ""
    style = [f"left:{left}px;top:{top}px;width:{width}px;height:{height}px"]
    if bg:
        style.append(f"background:{bg}")
    if fg:
        style.append(f"color:{fg}")
    if font_name or font_pt or bold:
        style.append(_font_css(font_name, font_pt, bold))
    just = item.justification.lower()
    if just in ("right", "end", "center"):
        style.append(f"justify-content:{'center' if just == 'center' else 'flex-end'}")
    classes = ["f-item", f"f-{widget}", _bevel_class(item, widget)]
    if item.iconic:
        classes.append("f-icon")
    if instance:
        classes.append("f-instance")
    if not item.enabled:
        classes.append("f-off")
    title = _esc(
        f"{item.name} · {item.item_type} · x {item.x} y {item.y} "
        f"w {item.width} h {item.height}" + (f" · record {instance + 1}" if instance else "")
    )
    return (
        f'<div class="{" ".join(classes)}" style="{";".join(style)}" title="{title}">'
        f"{caption}</div>"
    )


def _forms_radio_mocks(
    item: Item, module: FormModule, fx: float, fy: float, instance: int
) -> str:
    """A Radio Group paints nothing itself: only its buttons, each at its own place."""
    fg, _bg, font_name, font_pt, bold = _item_look(item, module)
    step = ((item.height or 14) + item.records_distance) * instance
    out = []
    for rb in item.radio_buttons:
        if rb.x is None or rb.y is None:
            continue
        left, top = round(rb.x * fx), round((rb.y + step) * fy)
        width, height = max(8, round((rb.width or 40) * fx)), max(8, round((rb.height or 14) * fy))
        style = [f"left:{left}px;top:{top}px;width:{width}px;height:{height}px"]
        if fg:
            style.append(f"color:{fg}")
        if font_name or font_pt or bold:
            style.append(_font_css(font_name, font_pt, bold))
        classes = ["f-item", "f-radio", "b-none"] + (["f-instance"] if instance else [])
        if not item.enabled:
            classes.append("f-off")
        title = _esc(
            f"{item.name} · {item.item_type} · button {rb.name} · x {rb.x} y {rb.y} "
            f"w {rb.width} h {rb.height}" + (f" · record {instance + 1}" if instance else "")
        )
        out.append(
            f'<div class="{" ".join(classes)}" style="{";".join(style)}" title="{title}">'
            f"<i></i>{_esc(rb.label)}</div>"
        )
    return "".join(out)


def _forms_prompt_mock(
    item: Item,
    fx: float,
    fy: float,
    canvas_w: int,
    canvas_h: int,
    *,
    instance: int = 0,
) -> str:
    """The prompt hung on its attachment edge, placed by Forms' own rules.

    ``PromptAttachmentEdge`` says which side (Forms2XML omits it at the
    default, **Start** -- to the left of the field), ``PromptAlign`` where
    along that side (Start/Center/End), ``PromptAlignOffset`` how far from
    there, ``PromptAttachmentOffset`` the gap from the field. The box is
    anchored with CSS on the side that touches the field, so it grows away
    from it with the real text width and no width is ever estimated. A
    negative attachment offset (the prompt pulled into its field) is drawn
    touching the field instead: it depends on Forms' own font metrics.
    """
    text = item.prompt
    if not text or item.prompt_display.lower() == "hidden":
        return ""
    left, top, width, height = _item_box(item, fx, fy, instance)
    edge = (item.prompt_edge or "Start").lower()
    align = (item.prompt_align or "Start").lower()
    across_edge = edge in ("top", "bottom")
    gap = round(max(0, item.prompt_offset) * (fy if across_edge else fx))
    shift = round(item.prompt_align_offset * (fx if across_edge else fy))
    transform = ""
    if across_edge:
        pos_v = f"bottom:{canvas_h - top + gap}px" if edge == "top" else f"top:{top + height + gap}px"
        if align == "center":
            pos_h, transform = f"left:{left + width // 2 + shift}px", "translateX(-50%)"
        elif align == "end":
            pos_h = f"right:{canvas_w - (left + width) - shift}px"
        else:
            pos_h = f"left:{left + shift}px"
    else:
        if edge == "end":
            pos_h = f"left:{left + width + gap}px"
        else:
            edge = "start"
            pos_h = f"right:{canvas_w - left + gap}px"
        if align == "center":
            pos_v, transform = f"top:{top + height // 2 + shift}px", "translateY(-50%)"
        elif align == "end":
            pos_v = f"bottom:{canvas_h - (top + height) - shift}px"
        else:
            pos_v = f"top:{top + shift}px"
    style = [pos_h, pos_v]
    if transform:
        style.append(f"transform:{transform}")
    style.append(_font_css("Arial", item.prompt_font_size, item.prompt_bold))
    color = _css_color(item.prompt_color)
    if color:
        style.append(f"color:{color}")
    just = item.prompt_justify.lower()
    if just in ("center", "right", "end"):
        style.append(f"text-align:{'center' if just == 'center' else 'right'}")
    title = _esc(f"prompt of {item.name} · {item.prompt_edge or 'Start'} edge")
    return (
        f'<div class="f-prompt {edge}" style="{";".join(style)}" title="{title}">'
        f"{_esc(text)}</div>"
    )


def _graphic_mock(g: Graphic, fx: float, fy: float, canvas_bg: str) -> str:
    """Boilerplate under the items: frame, rectangle, line, text, image."""
    kind = g.kind.lower()
    w, h = round(g.width * fx), round(g.height * fy)
    x, y = g.x * fx, g.y * fy
    if kind == "text":
        # Text is anchored on its origin, not its top-left corner.
        ho, vo = g.h_origin.lower(), g.v_origin.lower()
        x -= w / 2 if ho == "center" else w if ho == "right" else 0
        y -= h / 2 if vo == "center" else h if vo == "bottom" else 0
    left, top = round(x), round(y)
    title = _esc(f"{g.name} · {g.kind}")
    painted = g.fill.lower() not in ("none", "transparent")
    fill = _css_color(g.fill_color) if painted else ""

    if kind == "line":
        color = _css_color(g.edge_color) or "#808080"
        if h == 0 or (w and h and w >= h * 8):
            return (
                f'<div class="f-g g-line-h" style="left:{left}px;top:{top}px;width:{max(1, w)}px;'
                f'height:2px;border-top-color:{color}" title="{title}"></div>'
            )
        if w == 0 or (w and h and h >= w * 8):
            return (
                f'<div class="f-g g-line-v" style="left:{left}px;top:{top}px;width:2px;'
                f'height:{max(1, h)}px;border-left-color:{color}" title="{title}"></div>'
            )
        return (
            f'<svg class="f-g" style="left:{left}px;top:{top}px" width="{w}" height="{h}">'
            f'<title>{title}</title><line x1="0" y1="0" x2="{w}" y2="{h}" stroke="{color}"/></svg>'
        )
    if kind == "text":
        size = g.text_size or _DEFAULT_FONT_PT
        style = [
            f"left:{left}px;top:{top}px;width:{max(w, 1)}px;height:{max(h, 1)}px",
            _font_css("Arial", size, g.text_bold),
        ]
        color = _css_color(g.text_color)
        if color:
            style.append(f"color:{color}")
        if fill:
            style.append(f"background:{fill}")
        hj = g.h_justify.lower()
        if hj in ("center", "right", "end"):
            style.append(f"justify-content:{'center' if hj == 'center' else 'flex-end'}")
        wrap = " wrap" if g.wrap else ""
        return (
            f'<div class="f-g g-text{wrap}" style="{";".join(style)}" title="{title}">'
            f"{_esc(g.text)}</div>"
        )
    if kind == "image":
        return (
            f'<div class="f-g g-image" style="left:{left}px;top:{top}px;width:{max(w, 8)}px;'
            f'height:{max(h, 8)}px" title="{title}">{_esc(g.text or g.name)}</div>'
        )
    # Frame or rectangle (and anything else with a box): a bevelled outline.
    bevel = g.bevel.lower()
    if bevel not in ("lowered", "raised", "inset", "outset", "plain", "none"):
        bevel = "lowered"
    style = [f"left:{left}px;top:{top}px;width:{max(w, 2)}px;height:{max(h, 2)}px"]
    if fill:
        style.append(f"background:{fill}")
    body = ""
    if kind == "frame" and g.title:
        size = g.title_size or _DEFAULT_FONT_PT
        spacing = round(g.title_spacing * fx) or 3
        align = g.title_align.lower()
        if align == "center":
            place = "left:50%;transform:translateX(-50%)"
        elif align == "end":
            place = f"right:{round(g.title_offset * fx)}px"
        else:
            place = f"left:{round(g.title_offset * fx)}px"
        tstyle = [
            place,
            f"top:{-(_line_px(size) // 2)}px",
            f"padding:0 {spacing}px",
            f"background:{canvas_bg}",
            _font_css("Arial", size, g.title_bold),
        ]
        color = _css_color(g.title_color)
        if color:
            tstyle.append(f"color:{color}")
        body = f'<span class="f-title" style="{";".join(tstyle)}">{_esc(g.title)}</span>'
    return (
        f'<div class="f-g g-{"frame" if kind == "frame" else "rect"} b-{bevel}" '
        f'style="{";".join(style)}" title="{title}">{body}</div>'
    )


def _forms_canvas_html(
    canvas: Canvas,
    placed: list[tuple[Item, Block]],
    module: FormModule,
    fx: float,
    fy: float,
    *,
    min_width: int = 0,
) -> tuple[str, int, int]:
    """The canvas itself: boilerplate, then items, then prompts. Returns (html, px_w, px_h)."""
    positioned = [
        (it, b) for it, b in placed if it.visible and it.x is not None and it.y is not None
    ]
    box_w, box_h = _canvas_box_size(canvas, [it for it, _ in positioned])
    px_w, px_h = max(min_width, round(box_w * fx)), round(box_h * fy)
    bg = _css_color(canvas.bg_color) or _DEFAULT_CANVAS_BG

    parts = [_graphic_mock(g, fx, fy, bg) for g in canvas.graphics]
    prompts: list[str] = []
    for it, block in positioned:
        for instance in range(_instances(it, block)):
            parts.append(_forms_item_mock(it, module, fx, fy, instance=instance))
            if instance == 0 or it.prompt_display.lower() == "all records":
                prompts.append(_forms_prompt_mock(it, fx, fy, px_w, px_h, instance=instance))
    parts.extend(prompts)
    toolbar = " f-toolbar" if "toolbar" in (canvas.canvas_type or "").lower() else ""
    markup = (
        f'<div class="f-canvas{toolbar}" style="width:{px_w}px;height:{px_h}px;'
        f'background:{bg}">{"".join(parts)}</div>'
    )
    return markup, px_w, px_h


def _forms_window(
    canvas: Canvas,
    placed: list[tuple[Item, Block]],
    module: FormModule,
    fx: float,
    fy: float,
    unit: str,
    toolbar: tuple[Canvas, list[tuple[Item, Block]]] | None,
) -> str:
    """One canvas inside its window's chrome, as an entity of the report."""
    items_on = [it for it, _ in placed]
    hidden = [it for it, _ in placed if not it.visible]
    unpositioned = [it for it, _ in placed if it.visible and (it.x is None or it.y is None)]
    window = module.window_details.get(canvas.window_name)
    body, px_w, px_h = _forms_canvas_html(canvas, placed, module, fx, fy)
    box_w, box_h = _canvas_box_size(canvas, [it for it, _ in placed])

    chrome = ""
    if window is not None or toolbar is not None:
        title = (window.title if window and window.title else canvas.window_name) or canvas.name
        chrome = (
            f'<div class="f-titlebar"><span>{_esc(title)}</span>'
            "<i>_</i><i>□</i><i>✕</i></div>"
        )
    if toolbar is not None:
        tb_canvas, tb_placed = toolbar
        tb_html, _w, _h = _forms_canvas_html(
            tb_canvas, tb_placed, module, fx, fy, min_width=px_w
        )
        chrome += tb_html
    frame = f'<div class="f-win">{chrome}{body}</div>'

    meta_bits = [
        f"{_esc(canvas.canvas_type or 'Content')} canvas",
        f"{box_w}&times;{box_h} {_esc(unit)} &asymp; {px_w}&times;{px_h}px",
    ]
    if canvas.window_name:
        label = f"window {_esc(canvas.window_name)}"
        if window and window.title:
            label += f" &ldquo;{_esc(window.title)}&rdquo;"
        meta_bits.append(label)
    if toolbar is not None:
        meta_bits.append(f"toolbar {_esc(toolbar[0].name)} on top")
    if not canvas.visible:
        meta_bits.append("hidden until raised (Visible=false)")
    if canvas.tab_pages:
        meta_bits.append(f"tab pages: {_esc(', '.join(canvas.tab_pages))}")
    if canvas.graphics:
        meta_bits.append(f"{len(canvas.graphics)} boilerplate object(s)")
    meta = f'<div class="sub">{" &middot; ".join(meta_bits)}</div>'

    captions = ""
    if hidden:
        names = ", ".join(_esc(it.name) for it in hidden)
        captions += (
            f'<div class="none">{len(hidden)} item(s) on this canvas are hidden in Forms '
            f"(Visible=false) and are not drawn: {names}</div>"
        )
    if unpositioned:
        names = ", ".join(_esc(it.name) for it in unpositioned)
        captions += (
            f'<div class="none">{len(unpositioned)} item(s) on this canvas have '
            f"no recorded position: {names}</div>"
        )
    return (
        '<div class="entity"><div class="hd">'
        f"<b>{_esc(canvas.name)}</b>"
        f'<span class="tag dim">{len(items_on)} item(s)</span></div>'
        f"{meta}"
        f'<div class="f-scroll">{frame}</div>'
        f"{captions}</div>"
    )


def _forms_column(module: FormModule) -> str:
    fx, fy = _px_factors(module)
    unit = module.coordinate_unit or ("cells" if module.coordinate_system else "px")
    canvases = {c.name: c for c in module.canvases}
    pairs = [(it, b) for b in module.blocks for it in b.items]
    on = {name: [p for p in pairs if p[0].canvas == name] for name in canvases}

    # A window's horizontal toolbar is painted above its first content
    # canvas, the way the runtime docks it -- not as a canvas of its own.
    hosted: dict[str, str] = {}  # content canvas -> toolbar canvas
    for window in module.window_details.values():
        if window.toolbar not in canvases or window.toolbar in hosted.values():
            continue
        for canvas in module.canvases:
            if (
                canvas.window_name == window.name
                and canvas.name != window.toolbar
                and "toolbar" not in (canvas.canvas_type or "").lower()
            ):
                hosted[canvas.name] = window.toolbar
                break

    out = []
    for canvas in module.canvases:
        if canvas.name in hosted.values():
            continue
        toolbar = None
        if canvas.name in hosted:
            tb = canvases[hosted[canvas.name]]
            toolbar = (tb, on[tb.name])
        out.append(_forms_window(canvas, on[canvas.name], module, fx, fy, unit, toolbar))

    orphans = [it for it, _ in pairs if it.canvas not in canvases]
    if orphans:
        chips = "".join(
            f'<span class="tag no">{_esc(it.name)} ({_esc(it.item_type)})</span> ' for it in orphans
        )
        out.append(
            '<div class="entity"><div class="hd"><b>Not on a known canvas</b>'
            f'<span class="tag no">{len(orphans)} item(s)</span></div><div>{chips}</div></div>'
        )
    return "".join(out) if out else '<div class="none">no canvases in this module</div>'


# -- APEX side -----------------------------------------------------------------


def _label(placed: Placed) -> str:
    """The caption APEX gets -- the exporter's own text, made readable.

    :attr:`formslang.apexlayout.Placed.label` decides the wording (the Forms
    prompt, else the ``Label`` a button or check box carries, else the name
    spelled out -- and then the label template is hidden, as the screen
    shows nothing). Forms prompts are sometimes left as the developer's internal code
    (``ATSF_101ENDERECO_COMPLEMENTO``) rather than real copy: with no space
    to break on, that string is one unbroken word that blows out a fixed-
    width layout instead of wrapping. Spacing out underscores fixes both the
    readability and the overflow at once, without touching an author-written
    prompt's wording or casing. A multi-line prompt becomes one line, as the
    exporter itself writes it.
    """
    return " ".join(placed.label.replace("_", " ").split())


def _apex_item_html(placed: Placed) -> str:
    """One item or button, drawn as the Universal Theme widget the export names.

    The widget comes from :func:`_apex_kind`, the label template from
    :func:`formslang.apexlang._label_template` -- the exporter's own
    answers -- so a label sits left of the field (with the prompt's share of
    the cell), above it, floats inside it or is left out exactly as the
    written page will show it.
    """
    item = placed.item
    kind = _apex_kind(item)
    approx = not _has_confirmed_mapping(item)
    label = _esc(_label(placed))
    grid = placed.grid
    where = (
        "inline"
        if grid.flow
        else f"column {grid.column}, span {grid.span}"
        + ("" if grid.new_row or grid.new_column else " (shares the cell)")
    )
    title = _esc(
        f"{placed.block.name}.{item.name} · {item.item_type} → {kind}"
        f"{' (approximated)' if approx else ''} · {where}"
        + (f" · {placed.note}" if placed.note else "")
    )
    if kind == "button":
        return f'<div class="a-item" title="{title}"><span class="a-btn">{label}</span></div>'

    template = _label_template(item, kind, side=placed.side, label_span=placed.label_span)
    if template == "hidden" and not placed.caption:
        title += _esc(" · no caption in Forms: label hidden")
    kind_tag = (
        f'<small class="kind{" no" if approx else ""}">{_esc(kind)}'
        f'{" &middot; approx" if approx else ""}</small>'
    )
    mark = '<em class="req">*</em>' if template.startswith("required") else ""
    lbl = "" if template == "hidden" else f'<span class="lbl">{label}{mark}</span>'
    if kind == "checkbox":
        control = f'<div class="a-check"><i></i><span class="txt">{label}{mark}</span>{kind_tag}</div>'
    elif kind == "radioGroup":
        entries = [rb.label or rb.name for rb in item.radio_buttons] or item.choices or [label]
        options = "".join(f"<span><i></i>{_esc(entry)}</span>" for entry in entries)
        control = f'<div class="a-radio">{lbl}{options}{kind_tag}</div>'
    else:
        shape = {
            "textarea": " a-area",
            "displayOnly": " a-display",
            "selectList": " a-select",
        }.get(kind, "")
        field = f'<div class="a-field{shape}">{kind_tag}</div>'
        if template.endswith("-above"):
            align = f' style="--al:{placed.align}"' if placed.align != "left" else ""
            control = f'<div class="a-above"{align}>{lbl}{field}</div>'
        elif template in {"optional", "required"}:
            share = f"--lbl:{placed.label_span or 3};--al:{placed.align}"
            control = f'<div class="a-left" style="{share}">{lbl}{field}</div>'
        else:
            control = f'<div class="a-field{shape}">{lbl}{kind_tag}</div>'
    return f'<div class="a-item" title="{title}">{control}</div>'


def _apex_cells(entries: list[tuple[Placed | RegionNode, str]], *, flow: bool) -> str:
    """Boxes on the 12-column grid, row by row, as APEX will place them.

    ``startNewRow`` opens a row; ``newColumn: false`` joins the previous
    cell (two narrow controls Forms painted side by side). A flow region --
    a toolbar, or the no-canvas fallback -- just lines its boxes up.
    """
    rows: list[list[tuple[Placed | RegionNode, list[str]]]] = []
    for ref, markup in entries:
        grid = ref.grid
        if grid is None or grid.new_row or not rows:
            rows.append([(ref, [markup])])
        elif not grid.new_column and not grid.flow:
            rows[-1][-1][1].append(markup)
        else:
            rows[-1].append((ref, [markup]))
    out = []
    for row in rows:
        if flow:
            out.append(f'<div class="a-row a-flow">{"".join("".join(m) for _, m in row)}</div>')
            continue
        cells = []
        for ref, markup in row:
            grid = ref.grid
            column, span = (grid.column, grid.span) if grid else (1, GRID_COLUMNS)
            shared = " shared" if len(markup) > 1 else ""
            cells.append(
                f'<div class="a-cell{shared}" style="grid-column:{column}/span {span}">'
                f'{"".join(markup)}</div>'
            )
        out.append(f'<div class="a-row">{"".join(cells)}</div>')
    return "".join(out)


def _hidden_chip(placed: Placed) -> str:
    item = placed.item
    why = "hidden in Forms" if not item.visible else "not on a canvas"
    title = _esc(f"{placed.block.name}.{item.name} · {item.item_type} → hidden")
    return f'<span class="tag dim" title="{title}">{_esc(placed.apex_name)} &middot; {why}</span>'


def _apex_region_html(node: RegionNode) -> str:
    """One region of the export's tree, with its own rows, then its sub-regions;
    a boilerplate text is just its text, chrome-less, where it was drawn."""
    if node.text:
        text = "<br>".join(_esc(line.strip()) for line in node.text.splitlines())
        if node.text_bold:
            text = f"<strong>{text}</strong>"
        text_title = _esc(f"region {node.id} · {node.source}")
        return f'<div class="a-region a-text" title="{text_title}">{text}</div>'
    classes = ["a-region"]
    if node.template == "inline-dialog":
        classes.append("a-dialog")
    elif node.template == "tabs-container":
        classes.append("a-tabs")
    elif node.template == "blank-with-attributes":
        classes.append("a-blank")
    title = (
        _esc(node.title) if node.title else f'<span class="untitled">{_esc(node.name)}</span>'
    )
    badges = []
    if node.slot == "tabs":
        badges.append("tab page")
    elif node.template in _TEMPLATE_BADGES:
        badges.append(_TEMPLATE_BADGES[node.template])
    badge_html = "".join(f'<span class="tag yes">{_esc(b)}</span>' for b in badges)
    count = len(node.body) + len(node.hidden)
    count_html = f'<span class="tag dim">{count} item(s)</span>' if count else ""

    notes = ""
    if node.note:
        notes += f'<div class="a-note">{_esc(node.note)}</div>'
    for block_name, records in node.tabular.items():
        notes += (
            f'<div class="a-note">Forms shows {records} records of block {_esc(block_name)} at '
            "once here (tabular): the first record's row is laid out; an Interactive Grid on "
            "the block's table is the next stage.</div>"
        )
    body = _apex_cells([(p, _apex_item_html(p)) for p in node.body], flow=node.flow)
    chips = ""
    if node.hidden:
        chips = f'<div class="a-chips">{"".join(_hidden_chip(p) for p in node.hidden)}</div>'
    subs = _apex_cells([(s, _apex_region_html(s)) for s in node.subs], flow=False)
    if not (body or chips or subs):
        body = '<div class="none">no items</div>'
    region_title = _esc(f"region {node.id} · {node.source}")
    return (
        f'<details class="{" ".join(classes)}" open><summary title="{region_title}">'
        f'<span>{title}</span><span class="meta">{badge_html}{count_html}</span></summary>'
        f'<div class="a-body">{notes}{body}{chips}{subs}</div></details>'
    )


def _apex_column(module: FormModule, layout: PageLayout) -> str:
    if not module.blocks:
        return '<div class="none">no blocks in this module</div>'
    parts = []
    if layout.skipped:
        parts.append(
            '<div class="a-note">Not exported: '
            f"{'; '.join(_esc(reason) for reason in layout.skipped)}.</div>"
        )
    parts.extend(_apex_region_html(root) for root in layout.roots)
    if layout.hidden:
        parts.append(
            '<details class="a-region a-blank" open><summary><span>Hidden items at page '
            f'level</span><span class="meta"><span class="tag dim">{len(layout.hidden)} '
            'item(s)</span></span></summary><div class="a-body"><div class="a-chips">'
            f'{"".join(_hidden_chip(p) for p in layout.hidden)}</div></div></details>'
        )
    if layout.lovs:
        names = ", ".join(
            f"{_esc(lov.name)} ({len(lov.entries)} entries)" for lov in layout.lovs
        )
        parts.append(
            f'<div class="a-note">{len(layout.lovs)} static list(s) of values written to '
            f"shared-components/lovs.apx from the choices the .fmb declares: {names}.</div>"
        )
    return f'<div class="a-page">{"".join(parts)}</div>'


def _overview(module: FormModule, layout: PageLayout) -> str:
    items = module.all_items
    positioned = sum(1 for it in items if it.x is not None and it.y is not None)
    confirmed = sum(1 for it in items if _has_confirmed_mapping(it))
    hidden = sum(1 for it in items if not it.visible)
    cards = [
        ("Canvases", len(module.canvases)),
        ("Blocks", len(module.blocks)),
        ("Items", len(items)),
        ("Positioned", positioned),
        ("Hidden in Forms", hidden),
        ("APEX regions", sum(1 for _ in layout.regions())),
        ("Mapped (confirmed)", confirmed),
        ("Approximated", len(items) - confirmed),
    ]
    return "".join(
        f'<div class="card"><div class="n">{n}</div><div class="l">{_esc(label)}</div></div>'
        for label, n in cards
    )


def render_html(module: FormModule, *, generated_at: str = "") -> str:
    """Render one self-contained HTML page: Forms UI vs. APEX default mapping."""
    generated_at = generated_at or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    layout = build_layout(module, 1)
    body = (
        f'<div class="grid">{_overview(module, layout)}</div>'
        '<div class="warn">This shows the automatic default mapping only -- there is no '
        "picker here. To use a different APEX item type, change it in APEX Builder after "
        "export.</div>"
        "<h2>Forms UI (source)</h2>"
        f'<p class="sub">{_esc(_unit_note(module))} Boilerplate, fonts, colours, bevels '
        "and prompt placement come from the .fmb; fields are empty, as on a fresh record. "
        "Hover anything for its name and geometry.</p>"
        f"{_forms_column(module)}"
        "<h2>APEX preview (destination, default mapping)</h2>"
        '<p class="sub">The page exactly as the export writes it: a region per canvas and '
        "per frame, a toolbar above its window, a hidden stacked canvas as an inline "
        "dialog, and every item in the row and 12-column cell its Forms position maps to. "
        "Labels sit left of, above or inside the field as the Forms prompt sat, boilerplate "
        "text keeps its place as a caption or a text region. Hover an item "
        "for its APEX type and cell, a region header for what in the .fmb it stands "
        "for.</p>"
        f"{_apex_column(module, layout)}"
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(module.name)} &mdash; FormsLang preview</title>
<style>{_CSS}</style>
</head>
<body>
<div class="wrap">
<div class="hero">
<p class="kicker">FormsLang &middot; Visual Preview</p>
<h1>{_esc(module.name)}</h1>
<p class="sub">generated {_esc(generated_at)}</p>
</div>
{body}
</div>
</body>
</html>"""


def write_report(module: FormModule, out_dir: Path, *, generated_at: str = "") -> Path:
    """Render and write the preview next to ``out_dir``; return the file's path."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{module.name}.preview.html"
    path.write_text(render_html(module, generated_at=generated_at), encoding="utf-8")
    return path
