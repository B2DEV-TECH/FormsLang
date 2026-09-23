"""Visual projection of a saved assessment: labels, lanes, layouts and SVG.

This module is pure. It reads projections that already exist (module-level
architecture nodes and edges, finding rows, hotspot candidates) and never
parses source, calls an AI provider, touches storage or persists coordinates.
Every function returns the same output for the same input, independent of
``PYTHONHASHSEED`` and of input order.

Nothing here infers meaning. A lane is the architectural layer the engine
recorded; an Executive label is a plain-language name for the same
relationship; an investigation group organizes review work and is not a
migration wave, a dependency order, an effort estimate or a readiness claim.
"""

from __future__ import annotations

import html
from collections import Counter, defaultdict
from fractions import Fraction

from .estate_triage import investigation_groups

LAYOUT_ALGORITHM = "formslang-lanes/1"
NODE_WIDTH = 184
NODE_HEIGHT = 54
COLUMN_GAP = 64
ROW_GAP = 14
MARGIN = 28
HEADER = 40
MAX_ROWS = 18
BARYCENTER_SWEEPS = 2

# Semantic lanes, left to right. The lane is the recorded architecture layer.
LANES = (
    ("APPLICATION", "Application", "Application modules"),
    ("SHARED_LOGIC", "Shared logic and state", "Shared services and state"),
    ("DATA", "Data", "Data objects"),
    ("INTEGRATION", "Integration, unresolved and other", "External, unresolved and other references"),
)
LANE_IDS = tuple(lane for lane, _, _ in LANES)
_DATA_TYPES = frozenset({"TABLE", "VIEW", "SEQUENCE_REFERENCE"})

# Node type -> (technical label, executive label).
TYPE_LABELS = {
    "FORM": ("Form", "Application module"),
    "FORM_REFERENCE": ("Referenced Form", "Referenced application module"),
    "PACKAGE": ("PL/SQL package", "Shared PL/SQL service"),
    "SUBPROGRAM_BODY": ("PL/SQL routine", "Shared PL/SQL service"),
    "PACKAGE_SUBPROGRAM": ("PL/SQL routine", "Shared PL/SQL service"),
    "TABLE": ("Table", "Data object"),
    "VIEW": ("View", "Data object"),
    "SEQUENCE_REFERENCE": ("Sequence", "Data object"),
    "GLOBAL_REFERENCE": ("Global variable", "Shared global state"),
    "LIBRARY": ("PL/SQL library", "Shared client library"),
    "LIBRARY_REFERENCE": ("PL/SQL library", "Shared client library"),
    "MENU": ("Menu module", "Application menu"),
    "MENU_REFERENCE": ("Menu module", "Application menu"),
    "INTEGRATION_POINT": ("Integration point", "External integration"),
    "BUSINESS_RULE": ("Business rule candidate", "Business rule candidate"),
}
# Engine-derived entities that are candidates, not observed structure.
CANDIDATE_TYPES = frozenset({"BUSINESS_RULE"})
UNRESOLVED_LABELS = ("Unresolved reference", "Unresolved reference")
OTHER_LABELS = ("Other component", "Other component")

# Relationship classification -> (technical label, executive label).
RELATIONSHIP_LABELS = {
    "CALLS": ("Calls", "Uses service"),
    "READS": ("Reads", "Reads data"),
    "WRITES": ("Writes", "Changes data"),
    "OPENS_FORM": ("Opens Form", "Opens module"),
    "SHARES_STATE": ("Shares state", "Shares global state"),
    "DUPLICATES_LOGIC": ("Duplicates logic", "Similar logic observed"),
    "REFERENCES": ("References", "Refers to"),
}

# Epistemic statuses. Each keeps its own text so they are never interchangeable.
STATUSES = {
    "OBSERVED": "Observed in the supplied sources",
    "CANDIDATE": "Candidate that needs architecture review",
    "PROPOSED": "Engine proposal, not a decision",
    "DECIDED": "Human decision recorded",
    "UNRESOLVED": "Referenced but not found in the supplied sources",
}
RESOLVED_REVIEWS = frozenset({"APPROVE", "MODIFY"})
RISK_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "UNKNOWN": 4, "NONE": 5}
LENSES = ("ARCHITECTURE", "DATA_ACCESS", "SHARED_LOGIC", "HOTSPOTS", "REVIEW")
MATRIX_MAX_MODULES = 15
BOARD_MAX_MODULES = 8
BOUNDARY = ("Investigation groups organize review work. They are not migration waves, "
            "dependency order, effort estimates or readiness claims.")
REPORT_MAP_MAX_NODES = 60
REPORT_MAP_MAX_EDGES = 120


def lane_of(layer: str, node_type: str) -> str:
    """Semantic lane for one module-level node; unknown types never become services."""
    if layer in {"FORM", "LIBRARY"}:
        return "APPLICATION"
    if layer == "GLOBAL":
        return "SHARED_LOGIC"
    if layer == "DATABASE":
        return "DATA" if node_type in _DATA_TYPES else "SHARED_LOGIC"
    return "INTEGRATION"


def type_labels(layer: str, node_type: str) -> dict:
    if layer == "UNRESOLVED":
        technical, executive = UNRESOLVED_LABELS
    else:
        technical, executive = TYPE_LABELS.get(node_type, OTHER_LABELS)
    return {"technical": technical, "executive": executive}


def relationship_labels(classification: str) -> dict:
    technical, executive = RELATIONSHIP_LABELS.get(
        classification, (classification.replace("_", " ").capitalize(), "Related to"))
    return {"technical": technical, "executive": executive}


def labels_catalog() -> dict:
    """Every presentation label the UI needs, so the browser holds no second copy."""
    return {
        "lanes": [{"id": lane, "technical": technical, "executive": executive}
                  for lane, technical, executive in LANES],
        "relationships": {key: relationship_labels(key) for key in RELATIONSHIP_LABELS},
        "types": {key: {"technical": t, "executive": e} for key, (t, e) in TYPE_LABELS.items()},
        "unresolved": {"technical": UNRESOLVED_LABELS[0], "executive": UNRESOLVED_LABELS[1]},
        "statuses": dict(STATUSES),
        "lenses": list(LENSES),
    }


def review_summary(states: Counter | dict | None) -> dict:
    """Review state of the findings folded into one node; every count is observed."""
    states = Counter(states or {})
    total = sum(states.values())
    decided = sum(states[s] for s in RESOLVED_REVIEWS)
    return {"total": total, "decided": decided, "open": total - decided,
            "stale": states["STALE"], "deferred": states["DEFER"]}


def visual_node(node: dict, *, fan_in: int, fan_out: int) -> dict:
    """The 2.2 node contract; 2.1 fields are kept unchanged beside it."""
    unresolved = node["layer"] == "UNRESOLVED"
    return {
        **{k: v for k, v in node.items() if k != "review"},
        "presentation_type": type_labels(node["layer"], node["type"]),
        "lane": lane_of(node["layer"], node["type"]),
        "status": ("UNRESOLVED" if unresolved else
                   "CANDIDATE" if node["type"] in CANDIDATE_TYPES else "OBSERVED"),
        "unresolved": unresolved,
        "dependency_count": fan_in + fan_out,
        "review_summary": review_summary(node.get("review")),
    }


def visual_edge(edge: dict) -> dict:
    """The 2.2 edge contract; ``evidence`` stays for 2.1 clients."""
    return {
        **edge,
        "presentation_label": relationship_labels(edge["classification"]),
        "status": "OBSERVED" if edge.get("level") == "FACT" else "CANDIDATE",
        "evidence_refs": list(edge.get("evidence", ())),
    }


def _name_key(node):
    return (str(node.get("name", "")).casefold(), str(node["id"]))


def _order_by_barycenter(members, neighbours, rows, nodes):
    """Stable barycenter order: exact rational means, then name, then identity."""
    def key(identity):
        placed = sorted(rows[n] for n in neighbours.get(identity, ()) if n in rows)
        centre = Fraction(sum(placed), len(placed)) if placed else None
        return (centre is None, centre if centre is not None else 0, *_name_key(nodes[identity]))
    return sorted(members, key=key)


def _pack(columns, nodes, labels):
    """Assign coordinates; a column taller than MAX_ROWS wraps into sub-columns."""
    positions, headers, x = {}, [], MARGIN
    tallest = 1
    for (column_id, label), members in zip(labels, columns):
        chunks = [members[i:i + MAX_ROWS] for i in range(0, len(members), MAX_ROWS)] or [[]]
        start = x
        for chunk in chunks:
            for row, identity in enumerate(chunk):
                positions[identity] = {
                    "x": x, "y": MARGIN + HEADER + row * (NODE_HEIGHT + ROW_GAP),
                    "column": column_id,
                }
            tallest = max(tallest, len(chunk))
            x += NODE_WIDTH + COLUMN_GAP
        headers.append({"id": column_id, "label": label, "x": start,
                        "width": x - COLUMN_GAP - start, "count": len(members)})
    width = max(x - COLUMN_GAP + MARGIN, NODE_WIDTH + 2 * MARGIN)
    height = MARGIN * 2 + HEADER + tallest * (NODE_HEIGHT + ROW_GAP)
    return {"positions": {k: positions[k] for k in sorted(positions)}, "columns": headers,
            "width": width, "height": height}


def _undirected(edges, kept):
    neighbours = defaultdict(set)
    for edge in edges:
        s, t = edge["source"], edge["target"]
        if s in kept and t in kept and s != t:
            neighbours[s].add(t)
            neighbours[t].add(s)
    return neighbours


def estate_layout(nodes: dict, edges: list) -> dict:
    """Lane layout for the whole bounded view: Application -> Shared logic -> Data -> Integration."""
    lanes = {lane: [] for lane in LANE_IDS}
    for identity in sorted(nodes, key=lambda i: _name_key(nodes[i])):
        node = nodes[identity]
        lanes[node.get("lane") or lane_of(node["layer"], node["type"])].append(identity)
    neighbours = _undirected(edges, nodes)
    order = [list(lanes[lane]) for lane in LANE_IDS]
    for _ in range(BARYCENTER_SWEEPS):
        for sweep in (range(1, len(order)), range(len(order) - 2, -1, -1)):
            for index in sweep:
                rows = {i: r for j, lane in enumerate(order) if j != index for r, i in enumerate(lane)}
                order[index] = _order_by_barycenter(order[index], neighbours, rows, nodes)
    packed = _pack(order, nodes, [(lane, technical) for lane, technical, _ in LANES])
    return {"mode": "ESTATE", "algorithm": LAYOUT_ALGORITHM, "node_width": NODE_WIDTH,
            "node_height": NODE_HEIGHT, "cycle_nodes": [], **packed}


def _distances(start, adjacency):
    distance, frontier = {start: 0}, [start]
    while frontier:
        following = []
        for current in frontier:
            for nxt in sorted(adjacency.get(current, ())):
                if nxt not in distance:
                    distance[nxt] = distance[current] + 1
                    following.append(nxt)
        frontier = following
    return distance


def focus_layout(nodes: dict, edges: list, focus: str) -> dict:
    """Focus in the centre; what it reaches to the right, what reaches it to the left."""
    if focus not in nodes:
        return estate_layout(nodes, edges)
    forward, backward = defaultdict(set), defaultdict(set)
    for edge in edges:
        s, t = edge["source"], edge["target"]
        if s in nodes and t in nodes and s != t:
            forward[s].add(t)
            backward[t].add(s)
    out_dist, in_dist = _distances(focus, forward), _distances(focus, backward)
    column, cycles = {focus: 0}, []
    for identity in nodes:
        if identity == focus:
            continue
        o, i = out_dist.get(identity), in_dist.get(identity)
        if o is not None and i is not None:
            cycles.append(identity)
        if o is not None and (i is None or o <= i):
            column[identity] = o
        elif i is not None:
            column[identity] = -i
    # Nodes linked only indirectly take the side of the neighbour that reached them.
    neighbours = _undirected(edges, nodes)
    frontier = sorted(column, key=lambda i: (abs(column[i]), _name_key(nodes[i])))
    while frontier:
        following = []
        for current in frontier:
            for nxt in sorted(neighbours.get(current, ()), key=lambda i: _name_key(nodes[i])):
                if nxt not in column:
                    side = -1 if column[current] < 0 else 1
                    column[nxt] = column[current] + side
                    following.append(nxt)
        frontier = following
    for identity in sorted(set(nodes) - set(column), key=lambda i: _name_key(nodes[i])):
        column[identity] = max(column.values()) + 1  # disconnected; kept visible on the far right
    low, high = min(column.values()), max(column.values())
    order = [sorted((i for i in nodes if column[i] == c), key=lambda i: _name_key(nodes[i]))
             for c in range(low, high + 1)]
    centre = -low
    for _ in range(BARYCENTER_SWEEPS):
        for index in [*range(centre + 1, len(order)), *range(centre - 1, -1, -1)]:
            nearer = index - 1 if index > centre else index + 1
            rows = {i: r for r, i in enumerate(order[nearer])}
            order[index] = _order_by_barycenter(order[index], neighbours, rows, nodes)
    labels = []
    for c in range(low, high + 1):
        if c == 0:
            labels.append(("FOCUS", "Focus"))
        elif c < 0:
            labels.append((f"IN_{-c}", f"Reaches focus ({-c} {'hop' if c == -1 else 'hops'})"))
        else:
            labels.append((f"OUT_{c}", f"Reached from focus ({c} {'hop' if c == 1 else 'hops'})"))
    packed = _pack(order, nodes, labels)
    return {"mode": "FOCUS", "algorithm": LAYOUT_ALGORITHM, "node_width": NODE_WIDTH,
            "node_height": NODE_HEIGHT, "focus": focus, "cycle_nodes": sorted(cycles), **packed}


def attention_rank(node: dict) -> tuple:
    """Inclusion order when an estate view exceeds its node budget.

    Observed attention first (hotspot candidates, then highest finding risk,
    then relationship count); name and identity make the order total. It is a
    viewing order, not an importance or criticality score.
    """
    return (-int(node.get("hotspot_count", 0)), RISK_ORDER.get(node.get("highest_risk"), 5),
            -int(node.get("dependency_count", 0)), *_name_key(node))


def estate_glance(nodes: dict) -> list[dict]:
    """Module-level counts per lane and per recorded type."""
    counts = {lane: Counter() for lane in LANE_IDS}
    for node in nodes.values():
        counts[lane_of(node["layer"], node["type"])][
            "UNRESOLVED" if node["layer"] == "UNRESOLVED" else node["type"]] += 1
    result = []
    for lane, technical, executive in LANES:
        types = counts[lane]
        result.append({"lane": lane, "technical": technical, "executive": executive,
                       "count": sum(types.values()),
                       "types": [{"type": t, "count": types[t],
                                  **(type_labels("UNRESOLVED", t) if t == "UNRESOLVED"
                                     else type_labels("", t))}
                                 for t in sorted(types)]})
    return result


def attention_matrix(hotspots, hotspot_types, hotspot_labels) -> dict:
    """Modules x hotspot types; counts of candidates, bounded and ordered."""
    cells = defaultdict(Counter)
    for hotspot in hotspots:
        cells[hotspot.get("module") or "UNKNOWN"][hotspot["hotspot_type"]] += 1
    ordered = sorted(cells, key=lambda m: (-sum(cells[m].values()), m.casefold(), m))
    return {
        "types": [{"id": t, "label": hotspot_labels.get(t, t)} for t in hotspot_types],
        "rows": [{"module": m, "total": sum(cells[m].values()),
                  "cells": [cells[m][t] for t in hotspot_types]}
                 for m in ordered[:MATRIX_MAX_MODULES]],
        "total_modules": len(ordered),
        "truncated": len(ordered) > MATRIX_MAX_MODULES,
        "classification": "CANDIDATE",
    }


def investigation_board(findings, hotspots) -> dict:
    groups = investigation_groups(findings, hotspots)
    return {
        "schema": groups["schema"],
        "boundary": BOUNDARY,
        "groups": [{"id": g["id"], "name": g["name"], "rule": g["rule"],
                    "total": len(g["modules"]),
                    "modules": g["modules"][:BOARD_MAX_MODULES],
                    "truncated": len(g["modules"]) > BOARD_MAX_MODULES}
                   for g in groups["groups"]],
    }


def journey(overview_data: dict) -> list[dict]:
    """What each stage has to look at now. A map of the work, not a progress tracker."""
    inv = overview_data.get("inventory", {})
    review = overview_data.get("review_progress", {})
    hot = overview_data.get("hotspots", {})
    return [
        {"id": "UNDERSTAND", "label": "Understand", "section": "system-map",
         "question": "What is in the estate and how is it connected?",
         "facts": {"forms_modules": inv.get("forms_modules"),
                   "database_packages": inv.get("database_packages"),
                   "dependencies": inv.get("dependencies")}},
        {"id": "ASSESS", "label": "Assess", "section": "hotspots",
         "question": "Where does observed evidence ask for attention?",
         "facts": {"modernization_findings": inv.get("modernization_findings"),
                   "hotspot_candidates": hot.get("total")}},
        {"id": "DECIDE", "label": "Decide", "section": "review",
         "question": "Which recommendations need a human decision?",
         "facts": {"decided": review.get("reviewed"), "findings": review.get("total")}},
        {"id": "DELIVER", "label": "Deliver", "section": "reports",
         "question": "What can be handed to the modernization team?",
         "facts": {}},
    ]


# ---------------------------------------------------------------------------
# Static SVG for reports. No script, no external reference, no foreignObject;
# every text value is escaped and every identifier is derived from position.


def _svg_text(value, limit=None):
    text = str(value)
    if limit and len(text) > limit:
        text = text[:limit - 1] + "…"
    return html.escape(text, quote=True)


def report_estate_svg(relationships: list[dict], *, title="Estate architecture by lane") -> str:
    """Lane map of the module relationships already cleared for delivery.

    ``relationships`` are ``module_relationships`` rows, where literal-named
    targets are renamed before they reach this function. The view is
    bounded; the omitted counts are stated in the figure caption.
    """
    nodes, degree = {}, Counter()
    for row in relationships:
        for side in ("source", "target"):
            name, layer = row[side], row[f"{side}_layer"]
            key = f"{layer}\x00{name}"
            nodes.setdefault(key, {"id": key, "name": name, "layer": layer,
                                   "type": "UNRESOLVED" if layer == "UNRESOLVED" else "",
                                   "hotspot_count": 0})
            degree[key] += int(row.get("count", 1))
            if row.get("hotspot_ids"):
                nodes[key]["hotspot_count"] += 1
    for key, node in nodes.items():
        node["dependency_count"] = degree[key]
        node["lane"] = _report_lane(node["layer"])
    ranked = sorted(nodes.values(), key=attention_rank)[:REPORT_MAP_MAX_NODES]
    kept = {n["id"]: n for n in ranked}
    edges = []
    for row in relationships:
        s, t = f"{row['source_layer']}\x00{row['source']}", f"{row['target_layer']}\x00{row['target']}"
        if s in kept and t in kept:
            edges.append({"source": s, "target": t, "classification": row["relationship"],
                          "level": row.get("level"), "hotspot": bool(row.get("hotspot_ids"))})
    edges.sort(key=lambda e: (not e["hotspot"], e["classification"], e["source"], e["target"]))
    shown_edges = edges[:REPORT_MAP_MAX_EDGES]
    layout = estate_layout(kept, shown_edges)
    order = sorted(kept, key=lambda i: (layout["positions"][i]["x"], layout["positions"][i]["y"]))
    index = {identity: n for n, identity in enumerate(order)}
    parts = [(f'<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="estate-map-title" '
              f'viewBox="0 0 {layout["width"]} {layout["height"]}" width="100%" class="fl-estate-map">'
              f'<title id="estate-map-title">{_svg_text(title)}</title>')]
    for column in layout["columns"]:
        parts.append(f'<text x="{column["x"]}" y="{MARGIN + 14}" class="fl-lane">'
                     f'{_svg_text(column["label"])} ({column["count"]})</text>')
    for n, edge in enumerate(shown_edges):
        a, b = layout["positions"][edge["source"]], layout["positions"][edge["target"]]
        x1, y1 = a["x"] + NODE_WIDTH, a["y"] + NODE_HEIGHT // 2
        x2, y2 = b["x"], b["y"] + NODE_HEIGHT // 2
        if b["x"] <= a["x"]:
            x1, x2 = a["x"], b["x"] + NODE_WIDTH
        dash = ' stroke-dasharray="5 4"' if edge["level"] != "FACT" else ""
        klass = "fl-edge fl-hot" if edge["hotspot"] else "fl-edge"
        parts.append(f'<path id="e{n}" class="{klass}" d="M{x1} {y1} C{(x1 + x2) // 2} {y1} '
                     f'{(x1 + x2) // 2} {y2} {x2} {y2}"{dash}/>')
    for identity in order:
        node, p = kept[identity], layout["positions"][identity]
        unresolved = node["layer"] == "UNRESOLVED"
        klass = "fl-node fl-unresolved" if unresolved else "fl-node"
        parts.append(f'<g id="n{index[identity]}" class="{klass}"><title>{_svg_text(node["name"])}</title>'
                     f'<rect x="{p["x"]}" y="{p["y"]}" width="{NODE_WIDTH}" height="{NODE_HEIGHT}" rx="6"/>'
                     f'<text x="{p["x"] + 10}" y="{p["y"] + 22}">{_svg_text(node["name"], 24)}</text>'
                     f'<text x="{p["x"] + 10}" y="{p["y"] + 40}" class="fl-sub">'
                     f'{_svg_text("Unresolved reference" if unresolved else node["layer"].title())}'
                     f'{" · hotspot candidate" if node["hotspot_count"] else ""}</text></g>')
    parts.append("</svg>")
    caption = (f"Showing {len(kept)} of {len(nodes)} modules and {len(shown_edges)} of "
               f"{len(relationships)} relationships, ordered by observed attention. "
               "Dashed lines are inferred relationships; red lines are linked to hotspot candidates. "
               "Unresolved references were not found in the supplied sources.")
    return (f'<figure class="fl-figure">{"".join(parts)}'
            f'<figcaption>{_svg_text(caption)}</figcaption></figure>')


def _report_lane(layer):
    if layer in {"FORM", "LIBRARY"}:
        return "APPLICATION"
    if layer == "GLOBAL":
        return "SHARED_LOGIC"
    if layer == "DATABASE":
        # Delivery rows carry the layer, not the type; database nodes are drawn together.
        return "DATA"
    return "INTEGRATION"


def report_matrix_svg(matrix: dict, *, title="Hotspot candidates by module") -> str:
    """Modules x hotspot types as a static figure with a text equivalent in every cell."""
    types, rows = matrix["types"], matrix["rows"]
    label_w, cell_w, cell_h, top = 260, 150, 30, 56
    width = label_w + cell_w * max(len(types), 1) + 2 * MARGIN
    height = top + cell_h * max(len(rows), 1) + MARGIN
    parts = [(f'<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="matrix-title" '
              f'viewBox="0 0 {width} {height}" width="100%" class="fl-matrix">'
              f'<title id="matrix-title">{_svg_text(title)}</title>')]
    for c, kind in enumerate(types):
        parts.append(f'<text x="{MARGIN + label_w + c * cell_w + 6}" y="{top - 12}" class="fl-lane">'
                     f'{_svg_text(kind["label"], 22)}</text>')
    if not rows:
        parts.append(f'<text x="{MARGIN}" y="{top + 20}">No hotspot candidates in the saved assessment.</text>')
    peak = max((v for r in rows for v in r["cells"]), default=0) or 1
    for r, row in enumerate(rows):
        y = top + r * cell_h
        # Module ids are "<root scope>/<file>"; the figure shows the file and keeps the id in <title>.
        # A candidate spanning several modules has no single module row.
        label = "Across modules" if row["module"] == "UNKNOWN" else row["module"].rsplit("/", 1)[-1]
        parts.append(f'<text x="{MARGIN}" y="{y + 20}"><title>{_svg_text(label if row["module"] == "UNKNOWN" else row["module"])}</title>'
                     f'{_svg_text(label, 34)}</text>')
        for c, value in enumerate(row["cells"]):
            level = 0 if not value else 1 + (3 * value) // (peak + 1)
            parts.append(f'<rect x="{MARGIN + label_w + c * cell_w}" y="{y + 2}" width="{cell_w - 6}" '
                         f'height="{cell_h - 6}" class="fl-cell fl-l{level}"/>'
                         f'<text x="{MARGIN + label_w + c * cell_w + 10}" y="{y + 20}">{value}</text>')
    parts.append("</svg>")
    note = (f"{len(rows)} of {matrix['total_modules']} modules shown. " if matrix["truncated"] else "")
    caption = note + "Counts of hotspot candidates. A candidate is not a verdict."
    return f'<figure class="fl-figure">{"".join(parts)}<figcaption>{_svg_text(caption)}</figcaption></figure>'


REPORT_SVG_CSS = (
        # The figure keeps its own light panel so it reads the same on the dark report page and on paper.
    ".fl-figure{margin:16px 0;overflow-x:auto}.fl-figure svg{min-width:640px;font:12px system-ui,sans-serif;background:#fff;border-radius:8px}"
    ".fl-figure figcaption{font-size:12px;color:var(--mut,#555);margin-top:6px}"
    ".fl-node rect{fill:#fff;stroke:#555;stroke-width:1}.fl-unresolved rect{stroke-dasharray:4 3;fill:#f4f4f4}"
    ".fl-node text{fill:#111}.fl-sub{fill:#555!important;font-size:10px}.fl-lane{font-weight:700;fill:#333}"
    ".fl-edge{fill:none;stroke:#888;stroke-width:1.2}.fl-hot{stroke:#c0392b;stroke-width:2}"
    ".fl-cell{stroke:#999}.fl-l0{fill:#fafafa}.fl-l1{fill:#fde2c8}.fl-l2{fill:#f9b97d}.fl-l3{fill:#f08a3c}"
)
