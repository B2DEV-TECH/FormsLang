"""Measured inventory of the facts the 2.2 engine records, for the 2.3 ecosystem contract.

FormsLang 2.3 phase 1 (contract, inventory, fixtures). This script reads the
synthetic fixtures, parses them with the shipped parser and builds the shipped
Blueprint and hotspot projection. It changes nothing in the engine and it does
not open a project store.

For every corpus it records, side by side:

* what the Forms2XML source declares (read from the raw XML, so an attribute
  that is present can be told apart from one that is absent);
* what the parser model carries (``FormModule.canvases``, ``window_details``,
  ``Item.canvas`` / ``Item.tab_page``, including the defaults it fills in);
* what the Blueprint persists (entity and edge counts, canvas/window
  attributes, reference resolutions, frontiers, findings, hotspots).

The difference between those layers is the phase-2 enrichment inventory. The
output is deterministic: no timestamps, no absolute paths, sorted keys.

    python examples/verify/ecosystem_inventory.py --output inventory.json
    python examples/verify/ecosystem_inventory.py --check docs/design/ecosystem-explorer-2.3/inventory-2.2.json
"""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from formslang import blueprint, database, hotspots
from formslang.parser import parse_xml

NS = "{http://xmlns.oracle.com/Forms}"
DATABASE_SUFFIXES = {".sql", ".pks", ".pkb"}

# Corpora: name -> (forms, database sources). Paths are relative to the repository.
CORPORA = {
    "showcase": {
        "forms": ["tests/fixtures/showcase/module.xml"],
        "database": [],
        "note": "DEMO_ALL_ELEMENTS alone, as a single-module project (Case A).",
    },
    "modernization_lab": {
        "forms": "examples/modernization-lab/forms/xml",
        "database": "examples/modernization-lab/database",
        "exclude_database_parts": ["seed"],
        "note": "Four Forms plus DDL/packages/sequences/triggers/views, without seed/ (Case B).",
    },
    "case_c": {
        "forms": "tests/fixtures/ecosystem/case_c/forms",
        "database": "tests/fixtures/ecosystem/case_c/database",
        "note": "Two ORDER_API.SUBMIT routines in different schemas and one call without schema (Case C).",
    },
    "visual_hierarchy": {
        "forms": "tests/fixtures/ecosystem/visual_hierarchy",
        "database": [],
        "note": "Positive and negative window/canvas/tab/item declarations, OPEN_FORM and dynamic SQL frontiers.",
    },
}


def _paths(spec, *, suffixes, exclude_parts=()):
    if isinstance(spec, list):
        return [REPO / p for p in spec]
    root = REPO / spec
    return [p for p in sorted(root.rglob("*"))
            if p.is_file() and p.suffix.lower() in suffixes
            and not set(exclude_parts) & set(p.relative_to(root).parts)]


def _rel(path: Path) -> str:
    return path.resolve().relative_to(REPO).as_posix()


def _count(values) -> dict:
    return dict(sorted(Counter(values).items()))


# ---------------------------------------------------------------------------
# Source layer: what the XML actually declares.
# ---------------------------------------------------------------------------

def declared_visual(path: Path) -> dict:
    """Raw attribute presence for windows, canvases and items in one Forms2XML file."""
    root = ET.parse(path).getroot()
    module = root.find(f"{NS}FormModule")
    canvases, windows, items = [], [], []
    for el in module.iter(f"{NS}Canvas"):
        canvases.append({
            "name": el.get("Name", ""),
            "declared": sorted(k for k in ("WindowName", "CanvasType", "Visible") if k in el.attrib),
            "declared_tab_pages": [t.get("Name", "") for t in el.iter(f"{NS}TabPage")],
        })
    for el in module.iter(f"{NS}Window"):
        windows.append({
            "name": el.get("Name", ""),
            "declared": sorted(k for k in ("PrimaryCanvas",) if k in el.attrib),
        })
    for block in module.iter(f"{NS}Block"):
        for el in block.iter(f"{NS}Item"):
            items.append({
                "name": f"{block.get('Name', '')}.{el.get('Name', '')}",
                "declared": sorted(k for k in ("CanvasName", "TabPageName", "Visible") if k in el.attrib),
            })
    return {"canvases": canvases, "windows": windows, "items": items}


# ---------------------------------------------------------------------------
# Parser layer: what the model carries, and which values it cannot attribute.
# ---------------------------------------------------------------------------

def parsed_visual(module, declared: dict) -> dict:
    """The parser's visual model, with the origin of each value that could be a default."""
    decl_canvas = {c["name"].upper(): c for c in declared["canvases"]}
    decl_item = {i["name"].upper(): i for i in declared["items"]}
    canvas_names = {c.name.upper() for c in module.canvases}
    window_names = {w.upper() for w in module.windows}
    tabs_by_canvas = {c.name.upper(): {t.upper() for t in c.tab_pages} for c in module.canvases}

    canvases = []
    for canvas in module.canvases:
        declared_attrs = set(decl_canvas.get(canvas.name.upper(), {}).get("declared", []))
        canvases.append({
            "name": canvas.name,
            "window_name": canvas.window_name,
            "window_declared_in_module": (canvas.window_name.upper() in window_names) if canvas.window_name else None,
            "canvas_type": canvas.canvas_type,
            "canvas_type_origin": "DECLARED" if "CanvasType" in declared_attrs else "PARSER_DEFAULT",
            "visible": canvas.visible,
            # Only an explicit Visible="false" in the source can be said to be declared hidden.
            # A true value is indistinguishable from the parser default once in the model.
            "visible_origin": "DECLARED" if "Visible" in declared_attrs else "PARSER_DEFAULT",
            "tab_pages": list(canvas.tab_pages),
        })
    windows = []
    for name in module.windows:
        detail = module.window_details.get(name)
        primary = detail.primary_canvas if detail else ""
        windows.append({
            "name": name,
            "primary_canvas": primary,
            "primary_canvas_declared_in_module": (primary.upper() in canvas_names) if primary else None,
        })

    # Window <-> canvas agreement, from both declarations; nothing is chosen.
    by_window = defaultdict(set)
    for canvas in module.canvases:
        if canvas.window_name:
            by_window[canvas.window_name.upper()].add(canvas.name.upper())
    conflicts, primary_unset = [], []
    for window in windows:
        primary = window["primary_canvas"].upper()
        if not primary:
            primary_unset.append(window["name"])
            continue
        owner = next((c.window_name for c in module.canvases if c.name.upper() == primary), "")
        if owner and owner.upper() != window["name"].upper():
            conflicts.append({"window": window["name"], "primary_canvas": window["primary_canvas"],
                              "canvas_window_name": owner})

    items = {"total": 0, "without_canvas": [], "canvas_not_declared": [], "with_tab_page": 0,
             "tab_page_not_declared_on_canvas": [], "visible_origin": Counter()}
    block_canvases = {}
    for block in module.blocks:
        used = set()
        for item in block.items:
            qualified = f"{block.name}.{item.name}"
            items["total"] += 1
            decl = set(decl_item.get(qualified.upper(), {}).get("declared", []))
            items["visible_origin"]["DECLARED" if "Visible" in decl else "PARSER_DEFAULT"] += 1
            if not item.canvas:
                items["without_canvas"].append(qualified)
                continue
            used.add(item.canvas.upper())
            if item.canvas.upper() not in canvas_names:
                items["canvas_not_declared"].append({"item": qualified, "canvas": item.canvas})
            if item.tab_page:
                items["with_tab_page"] += 1
                if item.tab_page.upper() not in tabs_by_canvas.get(item.canvas.upper(), set()):
                    items["tab_page_not_declared_on_canvas"].append(
                        {"item": qualified, "canvas": item.canvas, "tab_page": item.tab_page})
        if len(used) > 1:
            block_canvases[block.name] = sorted(used)
    items["visible_origin"] = dict(sorted(items["visible_origin"].items()))
    return {
        "windows": windows,
        "canvases": canvases,
        "window_canvas_conflicts": conflicts,
        "windows_without_primary_canvas": primary_unset,
        "canvases_with_undeclared_window": sorted(
            c["name"] for c in canvases if c["window_declared_in_module"] is False),
        "items": items,
        "blocks_across_canvases": dict(sorted(block_canvases.items())),
    }


# ---------------------------------------------------------------------------
# Blueprint layer: what the 2.2 engine persists.
# ---------------------------------------------------------------------------

def persisted(bp: dict) -> dict:
    entities = {e["id"]: e for e in bp["entities"]}
    edges = bp["edges"]

    def kind(identity):
        return entities.get(identity, {}).get("type", "")

    canvas_attrs = sorted({k for e in entities.values() if e["type"] == "CANVAS" for k in e["attributes"]})
    window_attrs = sorted({k for e in entities.values() if e["type"] == "WINDOW" for k in e["attributes"]})
    visual_edges = Counter(
        f"{kind(e['source'])} {e['type']} {kind(e['target'])}" for e in edges
        if {kind(e["source"]), kind(e["target"])} & {"CANVAS", "WINDOW"})

    resolutions = Counter()
    for e in entities.values():
        if e["type"].endswith("_REFERENCE"):
            state = e.get("resolution") or e["attributes"].get("resolution") or "NONE"
            resolutions[f"{e['type']} {state}"] += 1

    finding_entities = {f["entity"] for f in bp["findings"]}
    frontiers = Counter()
    for e in entities.values():
        risk = e["attributes"].get("risk") if isinstance(e["attributes"].get("risk"), dict) else {}
        for factor in risk.get("factors", []):
            if factor.get("id") in {"dynamic_sql", "cross_module_unresolved"}:
                frontiers[f"risk_factor:{factor['id']}"] += 1
    for f in bp["findings"]:
        for question in f.get("unresolved_questions", []):
            if question.startswith("Runtime target unresolved"):
                frontiers["finding_question:runtime_target_unresolved"] += 1

    estate = hotspots.detect_estate_hotspots(bp)
    return {
        "engine_version": bp["engine_version"],
        "schema_version": bp["schema_version"],
        "entities_by_type": _count(e["type"] for e in entities.values()),
        "edges_by_type_and_level": _count(f"{e['type']} {e['level']}" for e in edges),
        "visual_edges": dict(sorted(visual_edges.items())),
        "canvas_attributes_persisted": canvas_attrs,
        "window_attributes_persisted": window_attrs,
        "tab_page_entities": sum(e["type"] == "TAB_PAGE" for e in entities.values()),
        "reference_resolutions": dict(sorted(resolutions.items())),
        "database_bridge_edges": sum(
            1 for e in edges if kind(e["target"]) in {"TABLE", "VIEW", "PACKAGE_SPEC", "PACKAGE_BODY",
                                                       "PACKAGE_SUBPROGRAM", "SUBPROGRAM_BODY"}
            and kind(e["source"]) in {"TABLE_OR_VIEW_REFERENCE", "ROUTINE_REFERENCE", "PACKAGE_REFERENCE"}),
        "findings": len(bp["findings"]),
        "entities_without_finding_by_type": _count(
            e["type"] for e in entities.values() if e["id"] not in finding_entities),
        "frontiers_outside_graph": dict(sorted(frontiers.items())),
        "hotspots_by_type": dict(sorted(estate["by_type"].items())),
    }


# ---------------------------------------------------------------------------
# Demonstration cases, traced through the persisted edges only.
# ---------------------------------------------------------------------------

# Contract ecosystem/1 §5.1. The 2.1/2.2 engines key packages and tables by bare
# name, so a same-named object in another schema is dropped before the Blueprint
# is written (G-SCHEMA-COLLIDE). A resolution saved by such an engine cannot be
# checked for that collision. Only an engine that keeps the schema may present
# it as resolved; no released engine does, and phase 2 defines the flag.
DATABASE_REFERENCE_TYPES = {"TABLE_OR_VIEW_REFERENCE", "ROUTINE_REFERENCE", "PACKAGE_REFERENCE"}


def explorer_resolution(target_type: str, raw_resolution: str, *, schema_aware: bool) -> dict | None:
    """How the explorer presents a database reference target (contract §5 and §5.1)."""
    if target_type not in DATABASE_REFERENCE_TYPES:
        return None
    if raw_resolution == "RESOLVED_TO_DATABASE_OBJECT":
        if schema_aware:
            return {"resolution": "RESOLVED"}
        return {"resolution": "LEGACY_RESOLVED", "caveat": "SCHEMA_COLLISION_NOT_VERIFIABLE"}
    if raw_resolution == "SYMBOLIC_REFERENCE":
        return {"resolution": "UNRESOLVED"}
    return None


def _outgoing(bp, entity_id, *, skip=("INVOKES_BUILTIN",), schema_aware=False):
    names = {e["id"]: e for e in bp["entities"]}
    rows = []
    for edge in bp["edges"]:
        if edge["source"] != entity_id or edge["type"] in skip:
            continue
        target = names[edge["target"]]
        rows.append({
            "type": edge["type"],
            "level": edge["level"],
            "target_type": target["type"],
            "target": target["name"],
            "resolution": target.get("resolution") or target["attributes"].get("resolution") or "",
            "resolved_target": names[target["resolved_target"]]["name"] if target.get("resolved_target") else "",
        })
        explorer = explorer_resolution(target["type"], rows[-1]["resolution"], schema_aware=schema_aware)
        if explorer:
            rows[-1]["explorer_resolution"] = explorer
    return sorted(rows, key=lambda r: (r["type"], r["target_type"], r["target"]))


def _trigger(bp, module, name, owner):
    return next(e for e in bp["entities"] if e["type"] == "TRIGGER" and e["module"] == module
                and e["name"] == name and e["attributes"].get("owner", "") == owner)


def case_a(bp) -> dict:
    trigger = _trigger(bp, "module.xml", "POST-COMMIT", "")
    locals_ = sorted({e["name"] for e in bp["entities"] if e["type"] == "PROGRAM_UNIT"})
    return {
        "unit": "DEMO_ALL_ELEMENTS / POST-COMMIT",
        "source_text": trigger["attributes"].get("source_text", ""),
        "outgoing": _outgoing(bp, trigger["id"]),
        "local_program_units": locals_,
        "risk_factor_titles": sorted(f["title"] for f in trigger["attributes"]["risk"]["factors"]),
    }


def case_b(bp) -> dict:
    rows = {}
    for owner in ("BK_APPROVAL.BT_APPROVE", "BK_APPROVAL.BT_REJECT"):
        trigger = _trigger(bp, "APPROVALS.xml", "WHEN-BUTTON-PRESSED", owner)
        rows[owner] = _outgoing(bp, trigger["id"])
    bypass = [
        {"severity": h["severity"], "title": h["title"], "module": h["module"],
         "unit": next(e["attributes"].get("owner") for e in bp["entities"] if e["id"] == h["entity_id"]),
         "potential_existing_api_owners": h["evidence"]["potential_existing_api_owners"],
         "unit_calls_co_writer": h["evidence"]["unit_calls_co_writer"]}
        for h in hotspots.detect_api_bypass_candidates(bp)
    ]
    return {"triggers": rows, "api_bypass_candidates": sorted(bypass, key=lambda r: r["unit"])}


def case_c(bp) -> dict:
    triggers = {}
    for owner in ("CTL.BT_SALES", "CTL.BT_BILLING", "CTL.BT_UNQUALIFIED"):
        trigger = _trigger(bp, "SUBMIT_DESK.xml", "WHEN-BUTTON-PRESSED", owner)
        triggers[owner] = [r for r in _outgoing(bp, trigger["id"]) if r["type"] == "CALLS"]
    database_side = sorted(
        ({"type": e["type"], "name": e["name"]} for e in bp["entities"]
         if e["type"] in {"PACKAGE_SPEC", "PACKAGE_BODY", "PACKAGE_SUBPROGRAM", "SUBPROGRAM_BODY", "TABLE"}),
        key=lambda r: (r["type"], r["name"]))
    return {"calls": triggers, "database_entities": database_side}


CASES = {"showcase": case_a, "modernization_lab": case_b, "case_c": case_c}


def measure_corpus(name: str, spec: dict) -> dict:
    forms = _paths(spec["forms"], suffixes={".xml"})
    db_paths = _paths(spec["database"], suffixes=DATABASE_SUFFIXES,
                      exclude_parts=spec.get("exclude_database_parts", ()))
    modules = [parse_xml(p) for p in forms]
    bp = blueprint.build(modules, title=name, source_keys=[p.name for p in forms],
                         database_sources=database.parse_database_sources(db_paths) if db_paths else None)
    visual = {}
    for path, module in zip(forms, modules):
        visual[module.name] = parsed_visual(module, declared_visual(path))
    result = {
        "note": spec["note"],
        "sources": {"forms": [_rel(p) for p in forms], "database": [_rel(p) for p in db_paths]},
        "parser_visual": dict(sorted(visual.items())),
        "blueprint": persisted(bp),
    }
    if name in CASES:
        result["case"] = CASES[name](bp)
    return result


def inventory() -> dict:
    return {
        "schema": "ecosystem-inventory/1",
        "purpose": ("Measured 2.2 facts for the FormsLang 2.3 ecosystem/1 contract. "
                    "Synthetic fixtures only; no runtime claim."),
        "corpora": {name: measure_corpus(name, spec) for name, spec in CORPORA.items()},
    }


def render(data: dict) -> str:
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--output", type=Path, help="write the inventory JSON here")
    group.add_argument("--check", type=Path, help="fail if the inventory differs from this file")
    args = parser.parse_args(argv)
    text = render(inventory())
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        print(f"Wrote {args.output}")
        return 0
    expected = args.check.read_text(encoding="utf-8")
    if expected != text:
        print(f"Inventory differs from {args.check}; regenerate it with --output and review the diff.")
        return 1
    print(f"Inventory matches {args.check}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
