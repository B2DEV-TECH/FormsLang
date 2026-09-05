"""AI layout assistant: places the controls of the regions the rules could not.

The deterministic rules in :mod:`formslang.apexlayout` decide every grid
cell from the Forms geometry alone, and for most screens that is the whole
story: a field lands on the column its position maps to, with the width
and the label room it had. A screen denser than twelve columns can hold,
or drawn with fields that round onto each other's columns, makes the rules
give somewhere -- push a field right, wrap it, narrow it, move a label
above -- and each concession is recorded on the control
(:attr:`formslang.apexlayout.Placed.flags`).

With the export's ``ai_layout`` switch on, this module asks the configured
AI provider -- the one the conversion workbench uses, under the same egress
policy -- to redraw exactly those regions, as a front-end developer would:
a JSON plan naming, row by row, each control's ``column``, ``columnSpan``,
``labelColumnSpan`` and label side. The plan is validated strictly (every
control exactly once, columns inside the grid, no overlaps, label narrower
than the cell), applied to the layout, and cached on the session keyed by a
digest of the request, so the next export and the preview replay it
without another call. An invalid plan, a provider error or the offline
provider leave the rules' placement in place and say so in the manifest:
the export never depends on the model answering well.

What is sent: region ids, titles and sizes, control names, Forms item
types, APEX item types, geometry in Forms units, caption text and side, and
the rules' own placement. What is never sent: PL/SQL, trigger code, table
or column names, LOV queries, help text, data.
"""

from __future__ import annotations

import hashlib
import json
import re

from . import policy
from .ai import Message, Provider, ProviderError, provider_from_env
from .apexlayout import (
    GRID_COLUMNS,
    Grid,
    PageLayout,
    Placed,
    RegionNode,
    _Box,
    _rows,
    apex_item_type,
)
from .store import Store

#: Bumped whenever the request or the plan format changes, so a cached plan
#: written for an older prompt is never replayed against a newer one.
PLAN_VERSION = 1

#: A region whose Forms row holds this many controls or more is dense
#: enough to be worth a second opinion even when the rules found room.
DENSE_ROW = 5

SETTING_PREFIX = "ai_layout_plan:"

_SYSTEM = """You are a senior front-end developer recreating an Oracle Forms screen as an Oracle APEX page on Universal Theme's 12-column grid.

You receive, per region, the controls Forms draws in it, grouped in the visual rows Forms draws them in (top to bottom, left to right), each with its Forms geometry (x, y, width, height in the module's units, relative to the region's own box), its caption and where Forms draws that caption, and the placement the deterministic rules produced ("rules": column, columnSpan, labelColumnSpan, and the compromises they had to make, in "flags").

Redraw each region so a user of the Forms screen recognises it:
- keep the reading order and the visual rows; a Forms row may become two grid rows when twelve columns cannot hold it, never the other way round;
- controls that align vertically in Forms (same x) start in the same column;
- a control's columnSpan is proportional to its width against the region's width, at least 1, and at least 2 when its label sits left of it;
- a caption drawn left of a field is a label left of it ("label": "left", labelColumnSpan >= 1, and always < columnSpan) when the row has room; otherwise put the label above ("label": "above", labelColumnSpan 0). Keep one choice per row: all left, or all above;
- a control with no caption, a button, a check box or a radio group has labelColumnSpan 0 and no "label";
- buttons keep their row and their order;
- a gap between controls is fine: columns you leave empty render as empty space, so whitespace in Forms can stay whitespace.

Hard constraints, or the plan is rejected and the rules' placement is kept:
- every control of a region appears exactly once, under its exact name; no other names;
- column is 1..12, columnSpan is 1..(13 - column), cells in a row are listed left to right and never overlap (column >= previous column + previous columnSpan);
- labelColumnSpan is 0 or an integer below columnSpan.

Answer with JSON only -- no prose, no markdown fence -- in this shape:
{"regions":[{"id":"<region id>","rows":[{"cells":[{"name":"<control name>","column":1,"columnSpan":4,"labelColumnSpan":1,"label":"left"}]}]}],"notes":"<one or two sentences on what you changed and why>"}"""


# -- what needs the assistant -------------------------------------------------


def _region_rows(node: RegionNode) -> list[list[Placed]]:
    boxes = [_Box(*p.bounds(), p) for p in node.body]
    return [[b.ref for b in row] for row in _rows(boxes)]


def hard_regions(layout: PageLayout) -> list[RegionNode]:
    """The regions the rules could not lay out cleanly: a control they had
    to push, wrap, narrow or relabel, or a Forms row of :data:`DENSE_ROW`
    controls or more. Flow regions (toolbars) and Interactive Grids have
    no grid cells to plan."""
    found: list[RegionNode] = []
    for node in layout.regions():
        if node.flow or node.kind == "grid" or not node.body:
            continue
        if any(p.flags for p in node.body) or any(
            len(row) >= DENSE_ROW for row in _region_rows(node)
        ):
            found.append(node)
    return found


def _control(placed: Placed, node: RegionNode) -> dict:
    item = placed.item
    x, y, w, h = placed.bounds()
    grid = placed.grid
    entry: dict = {
        "name": placed.apex_name,
        "kind": item.item_type,
        "type": "button" if "button" in item.item_type.lower() else apex_item_type(item),
        "x": round(x - node.x, 1),
        "y": round(y - node.y, 1),
        "width": round(w, 1),
        "height": round(h, 1),
        "caption": placed.caption,
        "captionSide": placed.side,
        "rules": {
            "column": grid.column,
            "columnSpan": grid.span,
            "labelColumnSpan": placed.label_span,
            "flags": list(placed.flags),
        },
    }
    if placed.label_room:
        entry["labelRoom"] = round(placed.label_room, 1)
    return entry


def request(layout: PageLayout, regions: list[RegionNode]) -> dict:
    """The compact, code-free description of ``regions`` the model gets."""
    return {
        "version": PLAN_VERSION,
        "grid": GRID_COLUMNS,
        "unit": layout.unit or "unit",
        "regions": [
            {
                "id": node.id,
                "title": node.title,
                "width": round(node.width, 1),
                "height": round(node.height, 1),
                "rows": [[_control(p, node) for p in row] for row in _region_rows(node)],
            }
            for node in regions
        ],
    }


def digest(req: dict) -> str:
    canonical = json.dumps(req, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def messages(req: dict) -> list[Message]:
    return [
        Message("system", _SYSTEM),
        Message("user", json.dumps(req, ensure_ascii=False, indent=1)),
    ]


# -- the plan -----------------------------------------------------------------


def parse_plan(text: str) -> dict | None:
    """The first JSON object in a model's answer, fences and prose stripped."""
    body = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", body, re.DOTALL)
    if fenced:
        body = fenced.group(1)
    start = body.find("{")
    if start < 0:
        return None
    decoder = json.JSONDecoder()
    for index in range(start, len(body)):
        if body[index] != "{":
            continue
        try:
            value, _ = decoder.raw_decode(body[index:])
        except ValueError:
            continue
        return value if isinstance(value, dict) else None
    return None


def _int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def validate_plan(plan: dict | None, regions: list[RegionNode]) -> list[str]:
    """Everything wrong with ``plan`` against the regions it was asked for;
    an empty list means it can be applied as is."""
    errors: list[str] = []
    if not isinstance(plan, dict) or not isinstance(plan.get("regions"), list):
        return ["plan is not an object with a regions list"]
    wanted = {node.id: node for node in regions}
    seen_regions: set[str] = set()
    for entry in plan["regions"]:
        if not isinstance(entry, dict) or entry.get("id") not in wanted:
            errors.append(f"unknown region {entry.get('id') if isinstance(entry, dict) else entry!r}")
            continue
        node = wanted[entry["id"]]
        if node.id in seen_regions:
            errors.append(f"region {node.id} planned twice")
            continue
        seen_regions.add(node.id)
        controls = {p.apex_name: p for p in node.body}
        placed_names: list[str] = []
        rows = entry.get("rows")
        if not isinstance(rows, list) or not rows:
            errors.append(f"region {node.id}: no rows")
            continue
        for row_index, row in enumerate(rows, 1):
            cells = row.get("cells") if isinstance(row, dict) else None
            if not isinstance(cells, list) or not cells:
                errors.append(f"region {node.id} row {row_index}: no cells")
                continue
            next_free = 1
            for cell in cells:
                if not isinstance(cell, dict):
                    errors.append(f"region {node.id} row {row_index}: cell is not an object")
                    continue
                name = cell.get("name")
                where = f"region {node.id} row {row_index} {name}"
                if name not in controls:
                    errors.append(f"{where}: unknown control")
                    continue
                placed_names.append(name)
                column, span = _int(cell.get("column")), _int(cell.get("columnSpan"))
                label_span = _int(cell.get("labelColumnSpan", 0))
                if column is None or not 1 <= column <= GRID_COLUMNS:
                    errors.append(f"{where}: column must be 1..{GRID_COLUMNS}")
                    continue
                if span is None or not 1 <= span <= GRID_COLUMNS + 1 - column:
                    errors.append(f"{where}: columnSpan must be 1..{GRID_COLUMNS + 1 - column}")
                    continue
                if column < next_free:
                    errors.append(f"{where}: overlaps the cell before it")
                next_free = column + span
                if label_span is None or label_span < 0 or label_span >= span:
                    errors.append(f"{where}: labelColumnSpan must be 0 or below columnSpan")
                side = cell.get("label")
                if side not in (None, "left", "above"):
                    errors.append(f"{where}: label must be left or above")
                elif side == "left" and not label_span:
                    errors.append(f"{where}: a left label needs labelColumnSpan >= 1")
        missing = sorted(set(controls) - set(placed_names))
        twice = sorted({n for n in placed_names if placed_names.count(n) > 1})
        if missing:
            errors.append(f"region {node.id}: controls not placed: {', '.join(missing)}")
        if twice:
            errors.append(f"region {node.id}: controls placed twice: {', '.join(twice)}")
    for node_id in wanted:
        if node_id not in seen_regions:
            errors.append(f"region {node_id}: not in the plan")
    return errors


def _labelled(placed: Placed) -> bool:
    """Whether the control has a caption a label template could show beside
    or above it (a check box's caption is the control; none means hidden)."""
    kind = apex_item_type(placed.item)
    return bool(placed.caption) and placed.side not in {"none", "control"} and kind not in {
        "checkbox",
        "radioGroup",
    }


def apply_plan(plan: dict, regions: list[RegionNode]) -> None:
    """Put the plan's cells on the layout: grid, label side and share, body
    order and sequences. Call only after :func:`validate_plan` passed."""
    by_id = {node.id: node for node in regions}
    for entry in plan["regions"]:
        node = by_id[entry["id"]]
        controls = {p.apex_name: p for p in node.body}
        body: list[Placed] = []
        for row in entry["rows"]:
            for index, cell in enumerate(row["cells"]):
                placed = controls[cell["name"]]
                column, span = _int(cell["column"]), _int(cell["columnSpan"])
                label_span = _int(cell.get("labelColumnSpan", 0)) or 0
                placed.grid = Grid(
                    new_row=index == 0, new_column=index > 0, column=column, span=span
                )
                if _labelled(placed):
                    if cell.get("label") == "left" and label_span:
                        placed.side, placed.label_span, placed.align = "left", label_span, "right"
                    else:
                        placed.side, placed.label_span = "above", 0
                        if placed.align == "right" and cell.get("label") != "left":
                            placed.align = "left"
                else:
                    placed.label_span = 0
                placed.flags = []
                placed.placement = "ai"
                body.append(placed)
        node.body = body
        for sequence, placed in enumerate(node.body, 1):
            placed.sequence = sequence * 10
        for sequence, placed in enumerate(node.hidden, len(node.body) + 1):
            placed.sequence = sequence * 10


# -- the session cache --------------------------------------------------------


def cached_plan(store: Store, page: int) -> dict | None:
    raw = store.setting(f"{SETTING_PREFIX}{page}")
    if not raw:
        return None
    try:
        cached = json.loads(raw)
    except ValueError:
        return None
    return cached if isinstance(cached, dict) and "plan" in cached else None


def apply_cached(layout: PageLayout, cached: dict | None) -> bool:
    """Replay a cached plan on a freshly built layout when it still matches
    the layout's request (same regions, same geometry, same rules), as the
    preview does to show the page the last export wrote. False when the
    cache is stale or was never written."""
    if not cached:
        return False
    regions = hard_regions(layout)
    if not regions or cached.get("digest") != digest(request(layout, regions)):
        return False
    plan = cached.get("plan")
    if validate_plan(plan, regions):
        return False
    apply_plan(plan, regions)
    layout.ai = {
        "enabled": True,
        "status": "cached",
        "regions": [node.id for node in regions],
        "digest": cached["digest"],
        "provider": cached.get("provider", ""),
        "model": cached.get("model", ""),
        "notes": cached.get("notes", ""),
    }
    return True


# -- the export-time entry point ---------------------------------------------


def assist(
    layout: PageLayout, provider: Provider | None, store: Store, page: int
) -> dict:
    """Ask the provider about the hard regions of ``layout`` and apply its
    plan, or replay the cached one; ``layout.ai`` says what happened.

    Raises :class:`formslang.policy.PolicyViolation` when the enterprise
    egress policy forbids the provider -- the export then fails rather than
    silently keeping the rules' placement the user asked to improve.
    """
    regions = hard_regions(layout)
    summary: dict = {
        "enabled": True,
        "status": "not-needed",
        "regions": [node.id for node in regions],
        "digest": "",
        "provider": "",
        "model": "",
        "notes": "",
        "reason": "",
    }
    if not regions:
        summary["reason"] = "the deterministic rules laid every region out without a compromise"
        layout.ai = summary
        return summary
    req = request(layout, regions)
    summary["digest"] = digest(req)
    cached = cached_plan(store, page)
    if cached and cached.get("digest") == summary["digest"] and not validate_plan(
        cached.get("plan"), regions
    ):
        apply_plan(cached["plan"], regions)
        summary.update(
            status="cached",
            provider=cached.get("provider", ""),
            model=cached.get("model", ""),
            notes=cached.get("notes", ""),
        )
        layout.ai = summary
        return summary

    if provider is None:
        provider = provider_from_env()
    policy.check(provider.type_id, getattr(provider, "base_url", ""))
    summary["provider"] = provider.type_id
    summary["model"] = getattr(provider, "model", "")
    if provider.type_id == "echo":
        summary.update(
            status="offline",
            reason="no AI provider configured (offline provider): the rules' placement stands",
        )
        layout.ai = summary
        return summary
    try:
        answer = provider.complete(messages(req), max_tokens=8192)
    except ProviderError as exc:
        summary.update(status="error", reason=f"provider error: {exc}")
        layout.ai = summary
        return summary
    plan = parse_plan(answer)
    errors = validate_plan(plan, regions)
    if errors:
        summary.update(
            status="rejected",
            reason="plan rejected: " + "; ".join(errors[:6]) + (" ..." if len(errors) > 6 else ""),
        )
        layout.ai = summary
        return summary
    apply_plan(plan, regions)
    notes = plan.get("notes")
    summary.update(status="applied", notes=notes if isinstance(notes, str) else "")
    store.set_setting(
        f"{SETTING_PREFIX}{page}",
        json.dumps(
            {
                "version": PLAN_VERSION,
                "digest": summary["digest"],
                "provider": summary["provider"],
                "model": summary["model"],
                "notes": summary["notes"],
                "plan": plan,
            },
            ensure_ascii=False,
        ),
    )
    layout.ai = summary
    return summary
