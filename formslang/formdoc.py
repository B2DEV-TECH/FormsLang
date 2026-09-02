"""Self-contained HTML technical documentation for one Forms module.

Same rendering philosophy as :mod:`formslang.report`: no CDN, no remote
fonts, no build step -- a sibling of that module, except this one documents
one module's structure instead of a portfolio's conversion risk.

Deliberately absent: any diagram of block/canvas/relation structure. A
flowchart needs either a diagram library pulled from a CDN or one vendored
into the package; :mod:`formslang.model`'s own docstring already draws the
line on scope ("layout properties are deliberately ignored"), and the
workbench's own no-CDN rule (see ``formslang/ui/__init__.py``) rules out the
former. The relations table below carries the same information a flowchart
would, just as rows instead of boxes and arrows.
"""

from __future__ import annotations

import html
from datetime import datetime, timezone
from pathlib import Path

from .model import Block, FormModule, Item, Trigger

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
.wrap{max-width:1180px;margin:0 auto;padding:40px 24px 80px}
.kicker{color:var(--gold);font-size:11px;font-weight:700;text-transform:uppercase;
 letter-spacing:.14em;margin:0 0 10px}
.hero{position:relative;padding-bottom:24px;margin-bottom:8px}
.hero::after{content:"";position:absolute;left:0;bottom:0;width:64px;height:3px;
 background:linear-gradient(90deg,var(--gold),transparent);border-radius:2px}
h1{font-size:32px;margin:0 0 6px;letter-spacing:-.02em}
h2{font-size:19px;margin:48px 0 14px;letter-spacing:-.01em;
 border-bottom:1px solid var(--line);padding-bottom:8px;scroll-margin-top:64px}
h3{font-size:15px;margin:26px 0 8px;color:var(--gold)}
.sub{color:var(--mut);margin:0;font-size:14px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px}
.card{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:16px 18px;
 transition:transform .15s ease,border-color .15s ease,background .15s ease}
.card:hover{transform:translateY(-2px);border-color:var(--line2);background:var(--surface2)}
.card .n{font-size:27px;font-weight:600;color:var(--gold);letter-spacing:-.02em}
.card .l{color:var(--mut);font-size:12px;text-transform:uppercase;letter-spacing:.07em;margin-top:2px}
table{width:100%;border-collapse:collapse;font-size:13.5px;margin:6px 0 18px}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--mut);font-weight:500;font-size:11.5px;text-transform:uppercase;letter-spacing:.06em}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
tbody tr{transition:background .12s ease}
tbody tr:hover{background:var(--surface2)}
code,.mono{font-family:"JetBrains Mono",Consolas,monospace;font-size:12.5px}
pre.code{background:#0B0D11;border:1px solid var(--line);border-radius:8px;padding:12px 14px;
 overflow-x:auto;font-family:"JetBrains Mono",Consolas,monospace;font-size:12.5px;white-space:pre-wrap;
 word-break:break-word}
.tag{display:inline-block;padding:1px 8px;border-radius:999px;font-size:11px;font-weight:600;
 letter-spacing:.03em}
.yes{background:#123021;color:var(--good)}.no{background:#2A1418;color:var(--bad)}
.entity{background:var(--surface);border:1px solid var(--line);border-radius:10px;
 padding:14px 16px;margin:14px 0;transition:border-color .15s ease}
.entity:hover{border-color:var(--line2)}
.entity>.hd{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}
.entity>.hd b{font-size:15px}
.none{color:var(--mut);font-style:italic;padding:8px 0}
nav.toc{position:sticky;top:0;background:rgba(7,9,12,.85);backdrop-filter:blur(8px);
 -webkit-backdrop-filter:blur(8px);border-bottom:1px solid var(--line);
 padding:10px 0;margin-bottom:8px;display:flex;gap:4px;flex-wrap:wrap;z-index:5}
nav.toc a{color:var(--mut);text-decoration:none;font-size:12.5px;padding:4px 9px;
 border-radius:999px;border:1px solid transparent;
 transition:color .12s ease,border-color .12s ease,background .12s ease}
nav.toc a:hover{color:var(--fg);border-color:var(--line)}
nav.toc a.active{color:var(--gold);border-color:rgba(245,166,64,.35);background:var(--gold-dim)}
.warn{background:#3A2E10;border:1px solid #5A4620;color:var(--gold);border-radius:8px;
 padding:10px 14px;margin:6px 0;font-size:13px}
@media print{nav.toc{display:none}body{background:#fff;color:#111}
 .hero::after{display:none}
 .card,.entity,pre.code{background:#f6f6f6;border-color:#ccc}}
"""

_SCROLLSPY_JS = """
(function(){
  var links = Array.prototype.slice.call(document.querySelectorAll('nav.toc a'));
  var sections = links
    .map(function(a){ return document.getElementById(a.getAttribute('href').slice(1)); })
    .filter(Boolean);
  if (!sections.length) return;
  var obs = new IntersectionObserver(function(entries){
    entries.forEach(function(entry){
      if (!entry.isIntersecting) return;
      var id = entry.target.id;
      links.forEach(function(a){ a.classList.toggle('active', a.getAttribute('href') === '#' + id); });
    });
  }, {rootMargin: '-15% 0px -70% 0px', threshold: 0});
  sections.forEach(function(s){ obs.observe(s); });
})();
"""


def _esc(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _yn(flag: bool) -> str:
    return f'<span class="tag {"yes" if flag else "no"}">{"Y" if flag else "N"}</span>'


def _code(text: str) -> str:
    return f'<pre class="code">{_esc(text)}</pre>' if text and text.strip() else '<div class="none">&mdash;</div>'


def _table(headers: list[str], rows: list[list[str]], *, numeric_cols: set[int] = frozenset()) -> str:
    if not rows:
        return '<div class="none">nothing to show</div>'
    thead = "".join(
        f'<th class="{"n" if i in numeric_cols else ""}">{_esc(h)}</th>' for i, h in enumerate(headers)
    )
    body = ""
    for row in rows:
        cells = "".join(
            f'<td class="{"n" if i in numeric_cols else ""}">{cell}</td>' for i, cell in enumerate(row)
        )
        body += f"<tr>{cells}</tr>"
    return f"<table><thead><tr>{thead}</tr></thead><tbody>{body}</tbody></table>"


def _section(anchor: str, title: str, body: str) -> str:
    return f'<h2 id="{anchor}">{_esc(title)}</h2>\n{body}\n'


# -- overview --------------------------------------------------------------


def _overview(m: FormModule) -> str:
    cards = [
        ("Blocks", len(m.blocks)),
        ("Items", len(m.all_items)),
        ("Triggers", len(m.all_triggers)),
        ("Program units", len(m.program_units)),
        ("LOVs", len(m.lovs)),
        ("Record groups", len(m.record_groups)),
        ("Relations", len(m.relations)),
        ("PL/SQL lines", f"{m.plsql_lines:,}"),
    ]
    grid = "".join(f'<div class="card"><div class="n">{c[1]}</div><div class="l">{_esc(c[0])}</div></div>' for c in cards)
    props = [
        ("Title", m.title),
        ("Comment", m.comment),
        ("First block", m.first_block),
        ("Menu module", m.menu_module),
        ("Source", m.source_path),
    ]
    prop_rows = [[_esc(k), _esc(v) or '<span class="none">&mdash;</span>'] for k, v in props if v or k in ("Title", "First block")]
    return f'<div class="grid">{grid}</div>\n{_table(["Property", "Value"], prop_rows)}'


# -- blocks (and their items / triggers) ------------------------------------


def _item_row(it: Item) -> list[str]:
    return [
        f"<b>{_esc(it.name)}</b>" + (' <span class="tag no">subclassed</span>' if it.subclassed else ""),
        _esc(it.item_type),
        _esc(it.data_type),
        _esc(it.column_name) or '<span class="none">&mdash;</span>',
        _yn(it.database_item),
        _yn(it.required),
        str(it.max_length) if it.max_length is not None else "",
        _esc(it.prompt),
        _esc(it.lov_name) or "",
    ]


def _trigger_entity(t: Trigger) -> str:
    return (
        '<div class="entity">'
        f'<div class="hd"><b>{_esc(t.name)}</b>'
        f'<span class="tag no">{t.lines} line(s)</span></div>'
        f"{_code(t.text)}</div>"
    )


def _triggers_list(triggers: list[Trigger]) -> str:
    if not triggers:
        return '<div class="none">no triggers at this scope</div>'
    return "".join(_trigger_entity(t) for t in triggers)


def _block_section(b: Block) -> str:
    props = [
        ("Database block", _yn(b.database_block)),
        ("Query source", _esc(b.query_data_source_name) or "&mdash;"),
        ("Source type", _esc(b.query_data_source_type) or "&mdash;"),
        ("Insert / Update / Delete", f"{_yn(b.insert_allowed)} {_yn(b.update_allowed)} {_yn(b.delete_allowed)}"),
        ("Records displayed", str(b.records_displayed) + (" (tabular)" if b.is_tabular else "")),
    ]
    if b.where_clause:
        props.append(("WHERE", f"<code>{_esc(b.where_clause)}</code>"))
    if b.order_by_clause:
        props.append(("ORDER BY", f"<code>{_esc(b.order_by_clause)}</code>"))
    prop_rows = [[k, v] for k, v in props]

    items_table = _table(
        ["Item", "Type", "Data type", "Column", "DB item", "Required", "Max len", "Prompt", "LOV"],
        [_item_row(it) for it in b.items],
    )
    item_triggers = [t for it in b.items for t in it.triggers]

    body = (
        f'<div class="entity"><div class="hd"><b>{_esc(b.name)}</b>'
        f'<span class="tag no">{len(b.items)} item(s)</span>'
        f'<span class="tag no">{len(b.triggers)} block trigger(s)</span></div>'
        f'{_table(["Property", "Value"], prop_rows)}'
        f"<h3>Items</h3>{items_table}"
        f"<h3>Block-level triggers</h3>{_triggers_list(b.triggers)}"
        + (f"<h3>Item-level triggers</h3>{_triggers_list(item_triggers)}" if item_triggers else "")
        + "</div>"
    )
    return body


def _blocks(m: FormModule) -> str:
    if not m.blocks:
        return '<div class="none">no blocks</div>'
    return "".join(_block_section(b) for b in m.blocks)


# -- program units / lovs / record groups / relations -----------------------


def _program_units(m: FormModule) -> str:
    if not m.program_units:
        return '<div class="none">no program units</div>'
    out = []
    for p in m.program_units:
        out.append(
            '<div class="entity">'
            f'<div class="hd"><b>{_esc(p.name)}</b>'
            f'<span class="tag no">{_esc(p.kind)}</span>'
            f'<span class="tag no">{p.lines} line(s)</span></div>'
            f"{_code(p.text)}</div>"
        )
    return "".join(out)


def _lovs(m: FormModule) -> str:
    rows = [[_esc(lv.name), _esc(lv.record_group) or "&mdash;", _esc(lv.title), str(lv.columns)] for lv in m.lovs]
    return _table(["LOV", "Record group", "Title", "Columns"], rows, numeric_cols={3})


def _record_groups(m: FormModule) -> str:
    if not m.record_groups:
        return '<div class="none">no record groups</div>'
    out = []
    for rg in m.record_groups:
        out.append(
            '<div class="entity">'
            f'<div class="hd"><b>{_esc(rg.name)}</b><span class="tag no">{_esc(rg.kind)}</span></div>'
            + (_code(rg.query) if rg.query else "")
            + "</div>"
        )
    return "".join(out)


def _relations(m: FormModule) -> str:
    rows = [
        [_esc(r.name), _esc(r.detail_block), f"<code>{_esc(r.join_condition)}</code>", _yn(r.deferred), _esc(r.delete_record) or "&mdash;"]
        for r in m.relations
    ]
    return _table(["Relation", "Detail block", "Join condition", "Deferred", "On delete"], rows)


def _misc_lists(m: FormModule) -> str:
    groups = [
        ("Canvases", [c.name for c in m.canvases]),
        ("Windows", m.windows),
        ("Alerts", m.alerts),
        ("Parameters", m.parameters),
        ("Attached libraries", m.attached_libraries),
        ("Editors", m.editors),
        ("Object groups", m.object_groups),
        ("Reports", m.reports),
        ("Tab pages", m.tab_pages),
    ]
    out = []
    for title, names in groups:
        if not names:
            continue
        chips = "".join(f'<span class="tag no">{_esc(n)}</span> ' for n in names)
        out.append(f"<h3>{_esc(title)} ({len(names)})</h3><div>{chips}</div>")
    if m.graphics_count:
        out.append(f"<h3>Graphics</h3><div>{m.graphics_count} object(s)</div>")
    return "".join(out) if out else '<div class="none">nothing recorded</div>'


def _warnings(m: FormModule) -> str:
    if not m.convert_warnings:
        return ""
    items = "".join(f'<div class="warn">{_esc(w)}</div>' for w in m.convert_warnings)
    return _section("warnings", "Conversion warnings", items)


_TOC = [
    ("overview", "Overview"),
    ("blocks", "Blocks"),
    ("triggers", "Form triggers"),
    ("units", "Program units"),
    ("lovs", "LOVs"),
    ("groups", "Record groups"),
    ("relations", "Relations"),
    ("other", "Other objects"),
]


def render_html(module: FormModule, *, generated_at: str = "") -> str:
    """Render one self-contained HTML page documenting ``module``."""
    generated_at = generated_at or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    toc = "".join(f'<a href="#{a}">{_esc(t)}</a>' for a, t in _TOC)
    body = (
        _section("overview", "Overview", _overview(module))
        + _section("blocks", "Blocks", _blocks(module))
        + _section("triggers", "Form-level triggers", _triggers_list(module.triggers))
        + _section("units", "Program units", _program_units(module))
        + _section("lovs", "LOVs", _lovs(module))
        + _section("groups", "Record groups", _record_groups(module))
        + _section("relations", "Relations", _relations(module))
        + _section("other", "Other objects", _misc_lists(module))
        + _warnings(module)
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(module.name)} &mdash; FormsLang documentation</title>
<style>{_CSS}</style>
</head>
<body>
<div class="wrap">
<div class="hero">
<p class="kicker">FormsLang &middot; Technical Documentation</p>
<h1>{_esc(module.name)}</h1>
<p class="sub">generated {_esc(generated_at)}</p>
</div>
<nav class="toc">{toc}</nav>
{body}
</div>
<script>{_SCROLLSPY_JS}</script>
</body>
</html>"""


def write_report(module: FormModule, out_dir: Path, *, generated_at: str = "") -> Path:
    """Render and write the doc next to ``out_dir``; return the file's path."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{module.name}.doc.html"
    path.write_text(render_html(module, generated_at=generated_at), encoding="utf-8")
    return path
