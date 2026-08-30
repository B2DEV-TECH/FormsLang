"""What else breaks if this unit changes.

A Forms module is a graph long before it is a list of triggers: a button
calls a program unit, the program unit navigates to a block, the block is
bound to a table, the table is queried by a record group behind an LOV on a
third block. Converting any one of those in isolation is how a migration
starts producing regressions nobody can explain.

This module builds that graph from what is actually written down -- the
parsed module structure and a lexical read of the PL/SQL -- and answers two
questions about any node:

* **What does this depend on?** (:meth:`DepGraph.depends_on`, outbound)
* **What depends on this?** (:meth:`DepGraph.impact`, inbound)

Three rules keep it honest:

1. Every edge carries its evidence -- the literal, the bind reference, the
   SQL statement that produced it. An edge you cannot trace is an opinion.
2. A name built at runtime (``GO_BLOCK('ORD' || :CTL.SUF)``) produces no
   edge at all. It is recorded on the source node as an unresolved target,
   because a graph that quietly omits it would read as "nothing here".
3. A reference to something the module does not contain is kept and marked
   ``missing`` rather than dropped. It is usually the interesting one: a
   block that lives in another form, or a typo that Forms tolerated.

There is no graph library here and no drawing. The explorer is a list a
reviewer can read, sort and check by hand.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from .model import FormModule
from .plsql import LITERAL_TARGETS, analyze

VERSION = "depgraph/1"

# -- node kinds ----------------------------------------------------------

MODULE = "module"
BLOCK = "block"
ITEM = "item"
TRIGGER = "trigger"
PROGRAM_UNIT = "program_unit"
PACKAGE = "package"
PROCEDURE = "procedure"
TABLE = "table"
LOV = "lov"
RECORD_GROUP = "record_group"
RELATION = "relation"
ALERT = "alert"
TIMER = "timer"
REPORT = "report"
LIBRARY = "library"
MENU = "menu"
FORM = "form"
GLOBAL = "global"
PARAMETER = "parameter"
EXTERNAL = "external"

NODE_LABEL = {
    MODULE: "Form module",
    BLOCK: "Block",
    ITEM: "Item",
    TRIGGER: "Trigger",
    PROGRAM_UNIT: "Program unit",
    PACKAGE: "Package",
    PROCEDURE: "Procedure",
    TABLE: "Table or view",
    LOV: "LOV",
    RECORD_GROUP: "Record group",
    RELATION: "Relation",
    ALERT: "Alert",
    TIMER: "Timer",
    REPORT: "Report",
    LIBRARY: "PL/SQL library",
    MENU: "Menu",
    FORM: "Other form",
    GLOBAL: "Global variable",
    PARAMETER: "Parameter",
    EXTERNAL: "External integration",
}

# -- edge kinds ----------------------------------------------------------

CONTAINS = "contains"
NAVIGATES = "navigates"
REFERENCES = "references"
CALLS = "calls"
QUERIES = "queries"
USES = "uses"
OPENS = "opens"
SHARES = "shares"
RUNS = "runs"
RELATES = "relates"

EDGE_LABEL = {
    CONTAINS: "contains",
    NAVIGATES: "navigates to",
    REFERENCES: "reads or writes",
    CALLS: "calls",
    QUERIES: "queries",
    USES: "uses",
    OPENS: "opens",
    SHARES: "shares state through",
    RUNS: "runs",
    RELATES: "master-detail with",
}

# How a captured literal maps onto the graph. Anything not listed keeps its
# literal on the source node without inventing a relationship for it.
_LITERAL_EDGES: dict[str, tuple[str, str]] = {
    "block": (BLOCK, NAVIGATES),
    "item": (ITEM, REFERENCES),
    "form": (FORM, OPENS),
    "lov": (LOV, USES),
    "alert": (ALERT, USES),
    "record_group": (RECORD_GROUP, USES),
    "relation": (RELATION, USES),
    "timer": (TIMER, USES),
    "report": (REPORT, RUNS),
    "menu": (MENU, USES),
    "menu_item": (MENU, USES),
    "os_command": (EXTERNAL, RUNS),
    "user_exit": (EXTERNAL, RUNS),
    "url": (EXTERNAL, RUNS),
}

# Node kinds that always live outside the module under review.
_ALWAYS_EXTERNAL = {FORM, LIBRARY, PACKAGE, EXTERNAL, GLOBAL, MENU, TABLE, REPORT}

MAX_DEPTH = 4
MAX_RESULTS = 250


def node_id(kind: str, name: str) -> str:
    return f"{kind}:{name.strip().upper()}"


@dataclass
class Node:
    """One thing a migration can break."""

    id: str
    kind: str
    name: str
    owner: str = ""
    task_id: str = ""
    external: bool = False
    missing: bool = False
    risk: str = ""
    unresolved_targets: list[str] = field(default_factory=list)
    attrs: dict = field(default_factory=dict)

    @property
    def label(self) -> str:
        return NODE_LABEL.get(self.kind, self.kind)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "kind": self.kind, "name": self.name, "owner": self.owner,
            "task_id": self.task_id, "external": self.external, "missing": self.missing,
            "risk": self.risk, "unresolved_targets": list(self.unresolved_targets),
            "attrs": dict(self.attrs),
        }

    @classmethod
    def from_dict(cls, raw: dict) -> Node:
        return cls(
            id=raw.get("id", ""), kind=raw.get("kind", ""), name=raw.get("name", ""),
            owner=raw.get("owner", ""), task_id=raw.get("task_id", ""),
            external=bool(raw.get("external")), missing=bool(raw.get("missing")),
            risk=raw.get("risk", ""),
            unresolved_targets=list(raw.get("unresolved_targets") or []),
            attrs=dict(raw.get("attrs") or {}),
        )


@dataclass(frozen=True)
class Edge:
    """A dependency, and the evidence that it exists."""

    src: str
    dst: str
    kind: str
    evidence: str = ""
    task_id: str = ""

    def to_dict(self) -> dict:
        return {
            "src": self.src, "dst": self.dst, "kind": self.kind,
            "evidence": self.evidence, "task_id": self.task_id,
        }

    @classmethod
    def from_dict(cls, raw: dict) -> Edge:
        return cls(
            src=raw.get("src", ""), dst=raw.get("dst", ""), kind=raw.get("kind", ""),
            evidence=raw.get("evidence", ""), task_id=raw.get("task_id", ""),
        )


class DepGraph:
    """Nodes, edges, and the two walks a reviewer actually needs."""

    def __init__(self, module: str = "", version: str = VERSION):
        self.module = module
        self.version = version
        self.nodes: dict[str, Node] = {}
        self.edges: list[Edge] = []
        self._out: dict[str, list[int]] = {}
        self._in: dict[str, list[int]] = {}
        self._seen: set[tuple[str, str, str, str]] = set()

    # -- building ---------------------------------------------------------

    def add_node(self, node: Node) -> Node:
        """Add, or enrich what is already there.

        Structure is discovered before code, so a node created from a
        literal (``GO_BLOCK('ORDERS')``) may already exist as a real block.
        Facts accumulate; ``missing`` is cleared as soon as the real object
        turns up, never the other way round.
        """
        existing = self.nodes.get(node.id)
        if existing is None:
            self.nodes[node.id] = node
            return node
        existing.task_id = existing.task_id or node.task_id
        existing.owner = existing.owner or node.owner
        existing.risk = existing.risk or node.risk
        existing.external = existing.external or node.external
        existing.missing = existing.missing and node.missing
        for target in node.unresolved_targets:
            if target not in existing.unresolved_targets:
                existing.unresolved_targets.append(target)
        existing.attrs.update(node.attrs)
        return existing

    def add_edge(self, src: str, dst: str, kind: str, evidence: str = "", task_id: str = "") -> None:
        if src == dst or src not in self.nodes or dst not in self.nodes:
            return
        key = (src, dst, kind, evidence)
        if key in self._seen:
            return
        self._seen.add(key)
        index = len(self.edges)
        self.edges.append(Edge(src, dst, kind, evidence, task_id))
        self._out.setdefault(src, []).append(index)
        self._in.setdefault(dst, []).append(index)

    # -- reading ----------------------------------------------------------

    def node(self, node_id_: str) -> Node | None:
        return self.nodes.get(node_id_)

    def outbound(self, node_id_: str) -> list[Edge]:
        return [self.edges[i] for i in self._out.get(node_id_, [])]

    def inbound(self, node_id_: str) -> list[Edge]:
        return [self.edges[i] for i in self._in.get(node_id_, [])]

    def by_task(self, task_id: str) -> Node | None:
        for node in self.nodes.values():
            if node.task_id == task_id:
                return node
        return None

    def _walk(self, start: str, *, forward: bool, depth: int) -> list[dict]:
        """Breadth-first, bounded, and never revisiting a node.

        The bounds are not decoration: a form with a shared library reaches
        most of itself within three hops, and an unbounded list is not an
        explorer, it is a wall of text.
        """
        if start not in self.nodes:
            return []
        depth = max(1, min(int(depth or 1), MAX_DEPTH))
        out: list[dict] = []
        seen = {start}
        queue: deque[tuple[str, int]] = deque([(start, 0)])
        while queue and len(out) < MAX_RESULTS:
            current, level = queue.popleft()
            if level >= depth:
                continue
            edges = self.outbound(current) if forward else self.inbound(current)
            for edge in edges:
                other = edge.dst if forward else edge.src
                if other in seen:
                    continue
                seen.add(other)
                node = self.nodes.get(other)
                if node is None:
                    continue
                out.append({
                    "id": node.id, "kind": node.kind, "name": node.name,
                    "label": node.label, "task_id": node.task_id, "risk": node.risk,
                    "external": node.external, "missing": node.missing,
                    "depth": level + 1, "via": edge.kind,
                    "via_label": EDGE_LABEL.get(edge.kind, edge.kind),
                    "evidence": edge.evidence,
                    "from": current if level else "",
                })
                queue.append((other, level + 1))
        return out

    def depends_on(self, node_id_: str, depth: int = 2) -> list[dict]:
        """What this node needs in order to keep working."""
        return self._walk(node_id_, forward=True, depth=depth)

    def impact(self, node_id_: str, depth: int = 2) -> list[dict]:
        """What breaks if this node changes: everything pointing at it."""
        return self._walk(node_id_, forward=False, depth=depth)

    def explore(self, node_id_: str, depth: int = 2) -> dict:
        node = self.nodes.get(node_id_)
        if node is None:
            return {}
        return {
            "node": node.to_dict(),
            "label": node.label,
            "depends_on": self.depends_on(node_id_, depth),
            "impact": self.impact(node_id_, depth),
            "direct_out": len(self._out.get(node_id_, [])),
            "direct_in": len(self._in.get(node_id_, [])),
        }

    def for_task(self, task_id: str, depth: int = 2) -> dict:
        node = self.by_task(task_id)
        return self.explore(node.id, depth) if node else {}

    # -- rollup -----------------------------------------------------------

    def summary(self) -> dict:
        """Counts, and the handful of nodes the whole form leans on."""
        by_kind: dict[str, int] = {}
        for node in self.nodes.values():
            by_kind[node.kind] = by_kind.get(node.kind, 0) + 1
        hubs = sorted(
            (
                {
                    "id": n.id, "kind": n.kind, "name": n.name, "label": n.label,
                    "in": len(self._in.get(n.id, [])), "out": len(self._out.get(n.id, [])),
                    "risk": n.risk,
                }
                for n in self.nodes.values()
                if n.kind != MODULE
            ),
            key=lambda d: (-d["in"], -d["out"], d["name"]),
        )
        return {
            "module": self.module,
            "version": self.version,
            "nodes": len(self.nodes),
            "edges": len(self.edges),
            "by_kind": dict(sorted(by_kind.items())),
            "external": sum(1 for n in self.nodes.values() if n.external),
            "missing": sum(1 for n in self.nodes.values() if n.missing),
            "unresolved": sum(len(n.unresolved_targets) for n in self.nodes.values()),
            "hubs": [h for h in hubs[:8] if h["in"]],
        }

    # -- persistence ------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "module": self.module,
            "version": self.version,
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "edges": [e.to_dict() for e in self.edges],
        }

    @classmethod
    def from_dict(cls, raw: dict) -> DepGraph:
        graph = cls(raw.get("module", ""), raw.get("version", VERSION))
        for item in raw.get("nodes") or []:
            graph.add_node(Node.from_dict(item))
        for item in raw.get("edges") or []:
            edge = Edge.from_dict(item)
            graph.add_edge(edge.src, edge.dst, edge.kind, edge.evidence, edge.task_id)
        return graph


# -- building from a parsed module ---------------------------------------


def _tables_in(sql: str) -> list[str]:
    return sorted(analyze(sql).tables) if sql and sql.strip() else []


def _unresolved_targets(code_analysis) -> list[str]:
    """Built-ins that name an object we could not read off the source.

    ``GO_BLOCK('ORDERS')`` resolves; ``GO_BLOCK(v_name)`` does not, and the
    difference decides whether the dependency exists in this graph at all.
    """
    resolved = {ref.builtin for ref in code_analysis.literals}
    return sorted(
        name for name in code_analysis.builtins
        if name in LITERAL_TARGETS and name not in resolved
    )


def build(module: FormModule, *, task_ids: dict[str, str] | None = None,
          risks: dict[str, str] | None = None) -> DepGraph:
    """Build the graph for one parsed module.

    ``task_ids`` maps ``(kind, owner, name)`` -- as
    :func:`formslang.convert.build_tasks` numbers them -- onto task ids, so
    a node the reviewer is looking at can be found from the queue. ``risks``
    maps those same task ids onto a risk level, which is what lets the
    explorer say *this dependency is the dangerous one*.
    """
    task_ids = task_ids or {}
    risks = risks or {}
    graph = DepGraph(module.name)

    def task_of(kind: str, owner: str, name: str) -> str:
        return task_ids.get(f"{kind}|{owner}|{name}".upper(), "")

    root = graph.add_node(Node(node_id(MODULE, module.name), MODULE, module.name,
                               attrs={"title": module.title}))

    # -- structure -------------------------------------------------------
    known_blocks: set[str] = set()
    for block in module.blocks:
        bid = node_id(BLOCK, block.name)
        known_blocks.add(block.name.upper())
        graph.add_node(Node(bid, BLOCK, block.name, attrs={
            "database_block": block.database_block,
            "records_displayed": block.records_displayed,
        }))
        graph.add_edge(root.id, bid, CONTAINS)
        source = block.query_data_source_name.strip()
        if block.database_block and source and " " not in source:
            tid = node_id(TABLE, source)
            graph.add_node(Node(tid, TABLE, source.upper(), external=True))
            graph.add_edge(bid, tid, QUERIES, evidence="block data source")
        for clause_name, clause in (("WHERE", block.where_clause), ("ORDER BY", block.order_by_clause)):
            for table in _tables_in(clause):
                tid = node_id(TABLE, table)
                graph.add_node(Node(tid, TABLE, table, external=True))
                graph.add_edge(bid, tid, QUERIES, evidence=f"block {clause_name} clause")
        for item in block.items:
            iid = node_id(ITEM, f"{block.name}.{item.name}")
            graph.add_node(Node(iid, ITEM, f"{block.name}.{item.name}", owner=block.name,
                                attrs={"item_type": item.item_type,
                                       "database_item": item.database_item,
                                       "column_name": item.column_name}))
            graph.add_edge(bid, iid, CONTAINS)
            if item.lov_name:
                lid = node_id(LOV, item.lov_name)
                graph.add_node(Node(lid, LOV, item.lov_name, missing=True))
                graph.add_edge(iid, lid, USES, evidence="LOV property")

    for group in module.record_groups:
        gid = node_id(RECORD_GROUP, group.name)
        graph.add_node(Node(gid, RECORD_GROUP, group.name, attrs={"kind": group.kind}))
        graph.add_edge(root.id, gid, CONTAINS)
        for table in _tables_in(group.query):
            tid = node_id(TABLE, table)
            graph.add_node(Node(tid, TABLE, table, external=True))
            graph.add_edge(gid, tid, QUERIES, evidence="record group query")

    for lov in module.lovs:
        lid = node_id(LOV, lov.name)
        graph.add_node(Node(lid, LOV, lov.name, missing=False, attrs={"title": lov.title}))
        graph.add_edge(root.id, lid, CONTAINS)
        if lov.record_group:
            gid = node_id(RECORD_GROUP, lov.record_group)
            graph.add_node(Node(gid, RECORD_GROUP, lov.record_group, missing=True))
            graph.add_edge(lid, gid, USES, evidence="LOV record group")

    for relation in module.relations:
        rid = node_id(RELATION, relation.name)
        graph.add_node(Node(rid, RELATION, relation.name,
                            attrs={"deferred": relation.deferred,
                                   "delete_record": relation.delete_record}))
        graph.add_edge(root.id, rid, CONTAINS)
        if relation.detail_block:
            bid = node_id(BLOCK, relation.detail_block)
            graph.add_node(Node(bid, BLOCK, relation.detail_block,
                                missing=relation.detail_block.upper() not in known_blocks))
            graph.add_edge(rid, bid, RELATES, evidence=relation.join_condition or "detail block")

    for name in module.attached_libraries:
        nid = node_id(LIBRARY, name)
        graph.add_node(Node(nid, LIBRARY, name, external=True))
        graph.add_edge(root.id, nid, USES, evidence="attached library")

    for name in module.alerts:
        graph.add_node(Node(node_id(ALERT, name), ALERT, name))
        graph.add_edge(root.id, node_id(ALERT, name), CONTAINS)

    for name in module.parameters:
        graph.add_node(Node(node_id(PARAMETER, name), PARAMETER, name))
        graph.add_edge(root.id, node_id(PARAMETER, name), CONTAINS)

    for name in module.reports:
        graph.add_node(Node(node_id(REPORT, name), REPORT, name, external=True))
        graph.add_edge(root.id, node_id(REPORT, name), RUNS, evidence="report object")

    if module.menu_module:
        mid = node_id(MENU, module.menu_module)
        graph.add_node(Node(mid, MENU, module.menu_module, external=True))
        graph.add_edge(root.id, mid, USES, evidence="menu module")

    known_units = {p.name.upper() for p in module.program_units}
    # Registered before any code is read: a trigger routinely calls a program
    # unit that comes later in the list, and an edge whose target does not
    # exist yet is dropped -- which would read as "nothing calls this".
    for program_unit in module.program_units:
        graph.add_node(Node(node_id(PROGRAM_UNIT, program_unit.name), PROGRAM_UNIT,
                            program_unit.name))

    # -- code ------------------------------------------------------------
    units: list[tuple[str, str, str, str, str]] = []  # id, kind, name, owner, text
    for trigger in module.all_triggers:
        owner = trigger.owner
        name = f"{owner}.{trigger.name}" if owner else trigger.name
        units.append((node_id(TRIGGER, name), TRIGGER, trigger.name, owner, trigger.text))
    for unit in module.program_units:
        units.append((node_id(PROGRAM_UNIT, unit.name), PROGRAM_UNIT, unit.name, "", unit.text))

    for uid, kind, name, owner, text in units:
        task_id = task_of(kind, owner, name)
        code = analyze(text or "")
        graph.add_node(Node(uid, kind, f"{owner}.{name}" if owner else name, owner=owner,
                            task_id=task_id, risk=risks.get(task_id, ""),
                            unresolved_targets=_unresolved_targets(code),
                            attrs={"lines": code.lines}))
        # The owning object contains the trigger; program units hang off the form.
        parent = root.id
        if kind == TRIGGER and owner:
            parent = node_id(ITEM, owner) if "." in owner else node_id(BLOCK, owner)
            if parent not in graph.nodes:
                parent = root.id
        graph.add_edge(parent, uid, CONTAINS)

        for ref in code.literals:
            mapping = _LITERAL_EDGES.get(ref.kind)
            if mapping is None:
                continue
            target_kind, edge_kind = mapping
            value = ref.value.strip()
            if not value:
                continue
            tid = node_id(target_kind, value)
            missing = target_kind in (BLOCK, ITEM, LOV, RECORD_GROUP, ALERT, RELATION) \
                and tid not in graph.nodes
            graph.add_node(Node(tid, target_kind, value, external=target_kind in _ALWAYS_EXTERNAL,
                                missing=missing))
            graph.add_edge(uid, tid, edge_kind, evidence=f"{ref.builtin}('{value}')",
                           task_id=task_id)

        for ref in code.item_refs:
            if "." not in ref:
                continue
            tid = node_id(ITEM, ref)
            graph.add_node(Node(tid, ITEM, ref, owner=ref.split(".")[0],
                                missing=tid not in graph.nodes))
            graph.add_edge(uid, tid, REFERENCES, evidence=f":{ref}", task_id=task_id)

        for ref in code.globals_used:
            tid = node_id(GLOBAL, ref)
            graph.add_node(Node(tid, GLOBAL, ref, external=True))
            graph.add_edge(uid, tid, SHARES, evidence=f":{ref}", task_id=task_id)

        for table in code.tables:
            tid = node_id(TABLE, table)
            graph.add_node(Node(tid, TABLE, table, external=True))
            graph.add_edge(uid, tid, QUERIES, evidence="SQL in this body", task_id=task_id)

        for call in code.unknown_calls:
            if "." in call:
                package = call.split(".")[0]
                tid = node_id(PACKAGE, package)
                graph.add_node(Node(tid, PACKAGE, package, external=True))
                graph.add_edge(uid, tid, CALLS, evidence=f"{call}(...)", task_id=task_id)
            elif call in known_units:
                graph.add_edge(uid, node_id(PROGRAM_UNIT, call), CALLS,
                               evidence=f"{call}(...)", task_id=task_id)
            else:
                tid = node_id(PROCEDURE, call)
                graph.add_node(Node(tid, PROCEDURE, call, external=True, missing=True))
                graph.add_edge(uid, tid, CALLS, evidence=f"{call}(...)", task_id=task_id)

    return graph
