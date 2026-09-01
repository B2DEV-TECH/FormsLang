"""Structural diff between two versions of the same Forms module.

Entities are matched by name only, at every level (blocks, items, triggers,
program units, LOVs, record groups, relations) -- a rename shows up as one
entity removed and a different one added, never as a match. That is a
deliberate v1 limitation, not an oversight: rename detection needs a
similarity heuristic (e.g. comparing renamed items' surviving properties or
trigger bodies) that has no obvious "right" threshold, and getting it wrong
silently hides real changes. Ship the honest version first.

Two kinds of change get reported per entity:

- property changes, found by walking ``dataclasses.fields()`` and comparing
  values -- reflection instead of a hand-maintained field list, so a new
  field on a model class is diffed automatically instead of silently
  skipped.
- code changes (trigger/program-unit text, record-group query), found with
  :class:`difflib.SequenceMatcher` over lines. ``autojunk=False`` is not
  optional: autojunk treats any line that recurs "too often" as noise and
  drops it from matching, which corrupts diffs of PL/SQL full of repeated
  short lines like ``END IF;``.

Blocks (and items) nest their own collections -- a block's items and
triggers, an item's triggers. A block whose own properties are unchanged
but whose items or triggers changed underneath it is still reported as
modified, tagged ``forced``, so a reviewer scanning only the top-level list
never misses a change buried two levels down.
"""

from __future__ import annotations

import dataclasses
import html
from dataclasses import dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from .model import FormModule

# -- result types ------------------------------------------------------------


@dataclass
class Hunk:
    tag: str
    a_start: int
    a_end: int
    b_start: int
    b_end: int
    a_lines: list[str]
    b_lines: list[str]


@dataclass
class EntityChange:
    name: str
    a: Any
    b: Any
    props: list[tuple[str, Any, Any]] = field(default_factory=list)
    code_changed: bool = False
    hunks: list[Hunk] = field(default_factory=list)
    children: dict[str, CollectionChange] = field(default_factory=dict)
    forced: bool = False


@dataclass
class CollectionChange:
    added: list[Any] = field(default_factory=list)
    removed: list[Any] = field(default_factory=list)
    modified: list[EntityChange] = field(default_factory=list)
    unchanged: int = 0

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.removed or self.modified)


@dataclass
class ModuleDiff:
    name_a: str
    name_b: str
    blocks: CollectionChange
    triggers: CollectionChange
    program_units: CollectionChange
    lovs: CollectionChange
    record_groups: CollectionChange
    relations: CollectionChange

    @property
    def has_changes(self) -> bool:
        return any(
            c.has_changes
            for c in (
                self.blocks,
                self.triggers,
                self.program_units,
                self.lovs,
                self.record_groups,
                self.relations,
            )
        )


# -- code diff -----------------------------------------------------------


def diff_code(a_text: str, b_text: str) -> tuple[bool, list[Hunk]]:
    """Line-level hunks between two code strings. See module docstring
    for why ``autojunk=False`` is load-bearing here."""
    a_lines = (a_text or "").splitlines()
    b_lines = (b_text or "").splitlines()
    sm = SequenceMatcher(None, a_lines, b_lines, autojunk=False)
    hunks = [
        Hunk(tag, i1, i2, j1, j2, a_lines[i1:i2], b_lines[j1:j2])
        for tag, i1, i2, j1, j2 in sm.get_opcodes()
        if tag != "equal"
    ]
    return bool(hunks), hunks


# -- generic collection / property diff -----------------------------------


def _key_by_name(a_list: list, b_list: list):
    a_map = {x.name: x for x in a_list}
    b_map = {x.name: x for x in b_list}
    added = [b_map[k] for k in b_map if k not in a_map]
    removed = [a_map[k] for k in a_map if k not in b_map]
    common = [k for k in a_map if k in b_map]
    return a_map, b_map, added, removed, common


def _diff_props(a: Any, b: Any, *, exclude: frozenset[str] = frozenset()) -> list[tuple[str, Any, Any]]:
    skip = exclude | {"name"}
    changed = []
    for f in dataclasses.fields(a):
        if f.name in skip:
            continue
        va, vb = getattr(a, f.name), getattr(b, f.name)
        if va != vb:
            changed.append((f.name, va, vb))
    return changed


def _diff_flat(a_list: list, b_list: list, *, code_field: str | None = None, prop_exclude: frozenset[str] = frozenset()) -> CollectionChange:
    """Diff a collection of entities with no nested sub-collections."""
    a_map, b_map, added, removed, common = _key_by_name(a_list, b_list)
    exclude = prop_exclude | ({code_field} if code_field else frozenset())
    modified = []
    for k in common:
        a, b = a_map[k], b_map[k]
        props = _diff_props(a, b, exclude=exclude)
        code_changed, hunks = (False, [])
        if code_field:
            code_changed, hunks = diff_code(getattr(a, code_field), getattr(b, code_field))
        if props or code_changed:
            modified.append(EntityChange(k, a, b, props, code_changed, hunks))
    return CollectionChange(added, removed, modified, len(common) - len(modified))


def _diff_items(a_items: list, b_items: list) -> CollectionChange:
    a_map, b_map, added, removed, common = _key_by_name(a_items, b_items)
    modified = []
    for k in common:
        a, b = a_map[k], b_map[k]
        props = _diff_props(a, b, exclude=frozenset({"triggers"}))
        trig_diff = _diff_flat(a.triggers, b.triggers, code_field="text")
        if props or trig_diff.has_changes:
            children = {"triggers": trig_diff} if trig_diff.has_changes else {}
            modified.append(EntityChange(k, a, b, props, children=children, forced=not props and trig_diff.has_changes))
    return CollectionChange(added, removed, modified, len(common) - len(modified))


def _diff_blocks(a_blocks: list, b_blocks: list) -> CollectionChange:
    a_map, b_map, added, removed, common = _key_by_name(a_blocks, b_blocks)
    modified = []
    for k in common:
        a, b = a_map[k], b_map[k]
        props = _diff_props(a, b, exclude=frozenset({"items", "triggers"}))
        items_diff = _diff_items(a.items, b.items)
        trig_diff = _diff_flat(a.triggers, b.triggers, code_field="text")
        children: dict[str, CollectionChange] = {}
        if items_diff.has_changes:
            children["items"] = items_diff
        if trig_diff.has_changes:
            children["triggers"] = trig_diff
        if props or children:
            modified.append(EntityChange(k, a, b, props, children=children, forced=not props and bool(children)))
    return CollectionChange(added, removed, modified, len(common) - len(modified))


def compare_modules(a: FormModule, b: FormModule) -> ModuleDiff:
    """Structural diff of ``a`` (before) against ``b`` (after)."""
    return ModuleDiff(
        name_a=a.name,
        name_b=b.name,
        blocks=_diff_blocks(a.blocks, b.blocks),
        triggers=_diff_flat(a.triggers, b.triggers, code_field="text"),
        program_units=_diff_flat(a.program_units, b.program_units, code_field="text"),
        lovs=_diff_flat(a.lovs, b.lovs),
        record_groups=_diff_flat(a.record_groups, b.record_groups, code_field="query"),
        relations=_diff_flat(a.relations, b.relations),
    )


# -- HTML rendering -----------------------------------------------------


_CSS = """
:root{--bg:#07090C;--surface:#12151A;--line:#242832;--fg:#F2F4F7;--mut:#8A9099;--gold:#F5A640}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
 font:15px/1.6 "Segoe UI",Inter,system-ui,sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:40px 24px 80px}
h1{font-size:26px;margin:0 0 4px;letter-spacing:-.02em}
h2{font-size:19px;margin:44px 0 14px;letter-spacing:-.01em;
 border-bottom:1px solid var(--line);padding-bottom:8px;scroll-margin-top:16px}
h3{font-size:14px;margin:18px 0 8px;color:var(--gold)}
.sub{color:var(--mut);margin:6px 0 0;font-size:13px}
table{width:100%;border-collapse:collapse;font-size:13.5px;margin:6px 0 18px}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--mut);font-weight:500;font-size:11.5px;text-transform:uppercase;letter-spacing:.06em}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
tbody tr:hover{background:#0E1116}
pre.code{background:#0B0D11;border:1px solid var(--line);border-radius:8px;padding:10px 12px;
 overflow-x:auto;font-family:"JetBrains Mono",Consolas,monospace;font-size:12.5px;white-space:pre-wrap;
 word-break:break-word;margin:0}
.tag{display:inline-block;padding:1px 8px;border-radius:999px;font-size:11px;font-weight:600;
 letter-spacing:.03em}
.yes{background:#123021;color:#5BD98A}.no{background:#2A1418;color:#F0736F}
.entity{background:var(--surface);border:1px solid var(--line);border-radius:10px;
 padding:14px 16px;margin:10px 0}
.entity>.hd{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}
.entity>.hd b{font-size:14.5px}
.none{color:var(--mut);font-style:italic;padding:4px 0}
.chg-lbl{color:var(--mut);font-size:11.5px;text-transform:uppercase;letter-spacing:.06em;margin:14px 0 6px}
.chg-group{margin:6px 0}
.hunk{margin:8px 0}
.hunk-hd{color:var(--mut);font-size:11px;margin-bottom:2px;font-family:"JetBrains Mono",Consolas,monospace}
.del{color:#F0736F}
.add{color:#5BD98A}
nav.toc{position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--line);
 padding:10px 0;margin-bottom:8px;display:flex;gap:4px;flex-wrap:wrap;z-index:5}
nav.toc a{color:var(--mut);text-decoration:none;font-size:12.5px;padding:4px 9px;
 border-radius:999px;border:1px solid transparent}
nav.toc a:hover{color:var(--fg);border-color:var(--line)}
@media print{nav.toc{display:none}body{background:#fff;color:#111}
 .entity,pre.code{background:#f6f6f6;border-color:#ccc}}
"""


def _esc(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _yn(flag: bool) -> str:
    return f'<span class="tag {"yes" if flag else "no"}">{"Y" if flag else "N"}</span>'


def _fmt_val(v: Any) -> str:
    if isinstance(v, bool):
        return _yn(v)
    if isinstance(v, (list, tuple)):
        return _esc(", ".join(str(x) for x in v)) if v else '<span class="none">&mdash;</span>'
    if v in (None, ""):
        return '<span class="none">&mdash;</span>'
    return _esc(v)


def _table(headers: list[str], rows: list[list[str]], *, numeric_cols: frozenset[int] = frozenset()) -> str:
    if not rows:
        return '<div class="none">nothing to show</div>'
    thead = "".join(f'<th class="{"n" if i in numeric_cols else ""}">{_esc(h)}</th>' for i, h in enumerate(headers))
    body = "".join(
        "<tr>" + "".join(f'<td class="{"n" if i in numeric_cols else ""}">{c}</td>' for i, c in enumerate(row)) + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{thead}</tr></thead><tbody>{body}</tbody></table>"


def _section(anchor: str, title: str, body: str) -> str:
    return f'<h2 id="{anchor}">{_esc(title)}</h2>\n{body}\n'


def _prop_diff_table(props: list[tuple[str, Any, Any]]) -> str:
    if not props:
        return ""
    rows = [[f"<code>{_esc(name)}</code>", _fmt_val(a), _fmt_val(b)] for name, a, b in props]
    return _table(["Property", "Before", "After"], rows)


def _hunk_block(h: Hunk) -> str:
    lines = "".join(f'<div class="del">- {_esc(ln)}</div>' for ln in h.a_lines)
    lines += "".join(f'<div class="add">+ {_esc(ln)}</div>' for ln in h.b_lines)
    header = f"@@ -{h.a_start + 1},{len(h.a_lines)} +{h.b_start + 1},{len(h.b_lines)} @@"
    return f'<div class="hunk"><div class="hunk-hd">{_esc(header)}</div><pre class="code">{lines}</pre></div>'


def _entity_change_block(ec: EntityChange) -> str:
    badge = ' <span class="tag no">cascaded from nested change</span>' if ec.forced else ""
    out = f'<div class="entity"><div class="hd"><b>{_esc(ec.name)}</b>{badge}</div>'
    out += _prop_diff_table(ec.props)
    if ec.hunks:
        out += "".join(_hunk_block(h) for h in ec.hunks)
    elif ec.code_changed:
        out += '<div class="none">code changed</div>'
    for child_name, child_coll in ec.children.items():
        out += f"<h3>{_esc(child_name.title())}</h3>"
        out += _render_collection(child_coll)
    out += "</div>"
    return out


def _render_collection(coll: CollectionChange) -> str:
    parts = []
    if coll.added:
        chips = "".join(f'<span class="tag yes">{_esc(x.name)}</span> ' for x in coll.added)
        parts.append(f'<div class="chg-lbl">Added ({len(coll.added)})</div><div class="chg-group">{chips}</div>')
    if coll.removed:
        chips = "".join(f'<span class="tag no">{_esc(x.name)}</span> ' for x in coll.removed)
        parts.append(f'<div class="chg-lbl">Removed ({len(coll.removed)})</div><div class="chg-group">{chips}</div>')
    if coll.modified:
        parts.append(f'<div class="chg-lbl">Modified ({len(coll.modified)})</div>')
        parts.extend(_entity_change_block(ec) for ec in coll.modified)
    if not parts:
        return f'<div class="none">no changes ({coll.unchanged} unchanged)</div>'
    parts.append(f'<p class="sub">{coll.unchanged} unchanged, not shown</p>')
    return "".join(parts)


_SECTIONS = [
    ("blocks", "Blocks"),
    ("triggers", "Form-level triggers"),
    ("units", "Program units"),
    ("lovs", "LOVs"),
    ("groups", "Record groups"),
    ("relations", "Relations"),
]


def _summary_table(diff: ModuleDiff) -> str:
    field_of = {
        "blocks": diff.blocks,
        "triggers": diff.triggers,
        "units": diff.program_units,
        "lovs": diff.lovs,
        "groups": diff.record_groups,
        "relations": diff.relations,
    }
    rows = []
    for key, title in _SECTIONS:
        c = field_of[key]
        rows.append([title, str(len(c.added)), str(len(c.removed)), str(len(c.modified)), str(c.unchanged)])
    return _table(["Section", "Added", "Removed", "Modified", "Unchanged"], rows, numeric_cols=frozenset({1, 2, 3, 4}))


def render_html(diff: ModuleDiff, *, generated_at: str = "") -> str:
    """Render one self-contained HTML page reporting ``diff``."""
    generated_at = generated_at or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    field_of = {
        "blocks": diff.blocks,
        "triggers": diff.triggers,
        "units": diff.program_units,
        "lovs": diff.lovs,
        "groups": diff.record_groups,
        "relations": diff.relations,
    }
    toc = "".join(f'<a href="#{a}">{_esc(t)}</a>' for a, t in _SECTIONS)
    if diff.has_changes:
        body = "".join(_section(a, t, _render_collection(field_of[a])) for a, t in _SECTIONS)
    else:
        body = '<div class="none">the two modules are structurally identical</div>'
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(diff.name_a)} vs {_esc(diff.name_b)} &mdash; FormsLang diff</title>
<style>{_CSS}</style>
</head>
<body>
<div class="wrap">
<h1>{_esc(diff.name_a)} &rarr; {_esc(diff.name_b)}</h1>
<p class="sub">FormsLang structural diff &middot; generated {_esc(generated_at)}</p>
<nav class="toc">{toc}</nav>
{_summary_table(diff)}
{body}
</div>
</body>
</html>"""


def write_report(diff: ModuleDiff, out_dir: Path, *, generated_at: str = "") -> Path:
    """Render and write the diff next to ``out_dir``; return the file's path."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{diff.name_a}_vs_{diff.name_b}.diff.html"
    path.write_text(render_html(diff, generated_at=generated_at), encoding="utf-8")
    return path
