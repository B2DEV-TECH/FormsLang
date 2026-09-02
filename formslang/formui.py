"""Self-contained HTML visual preview: Forms UI vs. the APEX default mapping.

Same rendering philosophy as :mod:`formslang.formdoc` and
:mod:`formslang.formdiff`: no CDN, no remote fonts, no build step, own copy
of the small HTML-building helpers (each report is meant to stand alone).

Read-only by construction, on purpose: the left column mocks up every Forms
canvas from the item geometry :mod:`formslang.parser` now keeps (see
``formslang/model.py``'s docstring), and the right column shows every block
as APEX would receive it, using :func:`formslang.apexlang._item_type` --
the one function that decides that mapping -- so this report can never drift
from what an actual export produces. There is deliberately no control to
pick a different APEX widget for a Forms item: that choice belongs in APEX
Builder, after export, never here.
"""

from __future__ import annotations

import html
from datetime import datetime, timezone
from pathlib import Path

from .apexlang import _item_type
from .model import Canvas, FormModule, Item

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
h2{font-size:19px;margin:32px 0 14px;letter-spacing:-.01em;
 border-bottom:1px solid var(--line);padding-bottom:8px}
.sub{color:var(--mut);margin:4px 0 0;font-size:12.5px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
.card{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:16px 18px}
.card .n{font-size:27px;font-weight:600;color:var(--gold);letter-spacing:-.02em}
.card .l{color:var(--mut);font-size:12px;text-transform:uppercase;letter-spacing:.07em;margin-top:2px}
.tag{display:inline-block;padding:1px 8px;border-radius:999px;font-size:11px;font-weight:600;
 letter-spacing:.03em}
.yes{background:#123021;color:var(--good)}.no{background:#2A1418;color:var(--bad)}
.entity{background:var(--surface);border:1px solid var(--line);border-radius:10px;
 padding:14px 16px;margin:14px 0}
.entity>.hd{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}
.entity>.hd b{font-size:15px}
.none{color:var(--mut);font-style:italic;padding:8px 0;font-size:13px}
.warn{background:#3A2E10;border:1px solid #5A4620;color:var(--gold);border-radius:8px;
 padding:10px 14px;margin:6px 0 20px;font-size:13px;overflow-wrap:anywhere}
.compare{display:grid;grid-template-columns:1fr 1fr;gap:24px}
.compare>div{min-width:0}
.canvas-mock{position:relative;background:#0B0D11;border:1px solid var(--line);
 border-radius:6px;margin-top:10px;overflow:auto;max-width:100%}
.item-mock{position:absolute;border:1px solid var(--line2);border-radius:3px;
 background:var(--surface2);font-size:10px;line-height:1.4;padding:2px 4px;
 overflow:hidden;white-space:nowrap;color:var(--fg)}
.item-mock.it-button{background:var(--gold-dim);border-color:var(--gold);
 text-align:center;color:var(--gold)}
.item-mock.it-display{opacity:.65;font-style:italic}
.item-mock.it-checkbox{background:transparent}
.apex-block{display:flex;flex-direction:column;gap:8px;margin-top:10px}
.apex-row{display:flex;align-items:center;gap:8px}
.mock-field{flex:1;min-width:0;background:#0B0D11;border:1px solid var(--line);border-radius:6px;
 padding:6px 10px;font-size:12.5px;color:var(--mut);min-height:16px;overflow-wrap:anywhere}
.mock-field.mock-area{min-height:44px;align-items:flex-start}
.mock-field.mock-display{border-style:dashed;font-style:italic}
.mock-check{flex:1;min-width:0;display:flex;align-items:center;gap:6px;font-size:12.5px;
 color:var(--mut);overflow-wrap:anywhere}
.mock-btn{background:var(--gold-dim);border:1px solid var(--gold);color:var(--gold);
 border-radius:6px;padding:6px 14px;font-size:12.5px;cursor:default;overflow-wrap:anywhere}
@media print{.compare{grid-template-columns:1fr}
 .card,.entity,.canvas-mock{background:#f6f6f6;border-color:#ccc}}
"""

# Widget shapes this report has direct evidence for -- everything else
# lands on the same textField fallback _item_type() itself falls back to,
# and is flagged "approx" rather than silently claimed as a real mapping.
_CONFIRMED_HINTS = ("button", "display", "check", "editor", "area")


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


def _canvas_box_size(canvas: Canvas, items: list[Item]) -> tuple[int, int]:
    if canvas.width and canvas.height:
        return canvas.width, canvas.height
    xs = [(it.x or 0) + (it.width or 0) for it in items]
    ys = [(it.y or 0) + (it.height or 0) for it in items]
    return max(xs, default=400) or 400, max(ys, default=300) or 300


def _scale(width: int, *, max_width: int = 600) -> float:
    return min(1.0, max_width / width) if width else 1.0


def _forms_item_mock(item: Item, scale: float) -> str:
    kind = _apex_kind(item)
    css_kind = kind if kind in ("button", "display", "checkbox") else "text"
    left = round((item.x or 0) * scale)
    top = round((item.y or 0) * scale)
    width = max(6, round((item.width or 60) * scale))
    height = max(6, round((item.height or 16) * scale))
    label = _esc(item.prompt or item.name)
    style = f"left:{left}px;top:{top}px;width:{width}px;height:{height}px"
    title = _esc(f"{item.name} ({item.item_type})")
    return f'<div class="item-mock it-{css_kind}" style="{style}" title="{title}">{label}</div>'


def _forms_column(module: FormModule) -> str:
    canvas_names = {c.name for c in module.canvases}
    out = []
    for canvas in module.canvases:
        items_on = [it for b in module.blocks for it in b.items if it.canvas == canvas.name]
        positioned = [it for it in items_on if it.x is not None and it.y is not None]
        unpositioned = [it for it in items_on if it.x is None or it.y is None]
        box_w, box_h = _canvas_box_size(canvas, positioned)
        scale = _scale(box_w)
        mocks = "".join(_forms_item_mock(it, scale) for it in positioned)
        meta = (
            f'<div class="sub">{_esc(canvas.canvas_type or "Content")} canvas'
            f" &middot; {box_w}&times;{box_h}px"
            + (f" &middot; window {_esc(canvas.window_name)}" if canvas.window_name else "")
            + "</div>"
        )
        caption = ""
        if unpositioned:
            names = ", ".join(_esc(it.name) for it in unpositioned)
            caption = (
                f'<div class="none">{len(unpositioned)} item(s) on this canvas have '
                f"no recorded position: {names}</div>"
            )
        out.append(
            '<div class="entity"><div class="hd">'
            f"<b>{_esc(canvas.name)}</b>"
            f'<span class="tag no">{len(items_on)} item(s)</span></div>'
            f"{meta}"
            f'<div class="canvas-mock" style="width:{round(box_w * scale)}px;'
            f'height:{round(box_h * scale)}px">{mocks}</div>'
            f"{caption}</div>"
        )
    orphans = [it for b in module.blocks for it in b.items if it.canvas not in canvas_names]
    if orphans:
        chips = "".join(
            f'<span class="tag no">{_esc(it.name)} ({_esc(it.item_type)})</span> ' for it in orphans
        )
        out.append(
            '<div class="entity"><div class="hd"><b>Not on a known canvas</b>'
            f'<span class="tag no">{len(orphans)} item(s)</span></div><div>{chips}</div></div>'
        )
    return "".join(out) if out else '<div class="none">no canvases in this module</div>'


def _label(item: Item) -> str:
    """A readable caption -- never the raw underscored identifier.

    Forms prompts are sometimes left as the developer's internal code
    (``ATSF_101ENDERECO_COMPLEMENTO``) rather than real copy: with no space
    to break on, that string is one unbroken word that blows out a fixed-
    width layout instead of wrapping. Spacing out underscores fixes both
    the readability and the overflow at once; ``.title()`` is applied only
    to the item-name fallback, never to an author-written prompt, so real
    prompt wording/casing is left alone.
    """
    if item.prompt:
        return item.prompt.replace("_", " ")
    return item.name.replace("_", " ").title()


def _apex_item_row(item: Item) -> str:
    kind = _apex_kind(item)
    approx = not _has_confirmed_mapping(item)
    badge = f'<span class="tag {"no" if approx else "yes"}">{_esc(kind)}{" &middot; approx" if approx else ""}</span>'
    label = _esc(_label(item))
    if kind == "button":
        control = f'<button class="mock-btn" disabled>{label}</button>'
    elif kind == "checkbox":
        control = f'<span class="mock-check"><input type="checkbox" disabled> {label}</span>'
    elif kind == "textArea":
        control = f'<div class="mock-field mock-area">{label}</div>'
    elif kind == "displayOnly":
        control = f'<div class="mock-field mock-display">{label}</div>'
    else:
        control = f'<div class="mock-field">{label}</div>'
    return f'<div class="apex-row">{control}{badge}</div>'


def _apex_column(module: FormModule) -> str:
    if not module.blocks:
        return '<div class="none">no blocks in this module</div>'
    out = []
    for block in module.blocks:
        rows = "".join(_apex_item_row(it) for it in block.items) or '<div class="none">no items</div>'
        out.append(
            '<div class="entity"><div class="hd">'
            f"<b>{_esc(block.name)}</b>"
            f'<span class="tag no">{len(block.items)} item(s)</span></div>'
            f'<div class="apex-block">{rows}</div></div>'
        )
    return "".join(out)


def _overview(module: FormModule) -> str:
    items = module.all_items
    positioned = sum(1 for it in items if it.x is not None and it.y is not None)
    confirmed = sum(1 for it in items if _has_confirmed_mapping(it))
    cards = [
        ("Canvases", len(module.canvases)),
        ("Blocks", len(module.blocks)),
        ("Items", len(items)),
        ("Positioned", positioned),
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
    body = (
        f'<div class="grid">{_overview(module)}</div>'
        '<div class="warn">This shows the automatic default mapping only -- there is no '
        "picker here. To use a different APEX item type, change it in APEX Builder after "
        "export.</div>"
        '<div class="compare">'
        f'<div><h2>Forms UI (source)</h2>{_forms_column(module)}</div>'
        f'<div><h2>APEX preview (destination, default mapping)</h2>{_apex_column(module)}</div>'
        "</div>"
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
