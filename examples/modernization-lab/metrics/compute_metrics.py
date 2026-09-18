#!/usr/bin/env python3
"""
Compute structural metrics for the LOM modernization lab directly from the
committed artifacts (forms/xml/*.xml via formslang.parser, database/**/*.sql
via plain text counting). Stdlib + formslang only -- no third-party deps.

Every number this script prints is measured from the files in this lab at
run time, not copied from documentation. If a fixture changes, re-run this
script and update any doc that quotes a stale count -- do not hand-edit a
count without checking it here first.

Usage (from the repo root):
    python examples/modernization-lab/metrics/compute_metrics.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = LAB_ROOT.parent.parent

sys.path.insert(0, str(REPO_ROOT))

import formslang.parser as formslang_parser  # noqa: E402

FORMS = ["CUSTOMERS", "ORDERS", "INVENTORY", "APPROVALS"]


def form_metrics(name: str) -> dict:
    path = LAB_ROOT / "forms" / "xml" / f"{name}.xml"
    module = formslang_parser.parse_xml(str(path))

    items = sum(len(b.items) for b in module.blocks)
    block_triggers = sum(len(b.triggers) for b in module.blocks)
    item_triggers = sum(sum(len(i.triggers) for i in b.items) for b in module.blocks)
    module_triggers = len(module.triggers)

    return {
        "blocks": len(module.blocks),
        "items": items,
        "module_triggers": module_triggers,
        "block_triggers": block_triggers,
        "item_triggers": item_triggers,
        "total_triggers": module_triggers + block_triggers + item_triggers,
        "lovs": len(module.lovs),
        "relations": len(module.relations),
        "alerts": len(module.alerts),
        "record_groups": len(module.record_groups),
        "parameters": len(module.parameters),
    }


def count_lom_mod_refs() -> dict:
    """Every LOM-MOD-### id referenced anywhere under database/ or forms/,
    independent of the ground-truth JSON, so drift between "case exists in
    fixtures" and "case exists in the registry" is directly detectable."""
    pattern = re.compile(r"LOM-MOD-(\d{3})")
    ids_by_file: dict[str, set[str]] = {}
    for sub in ("database", "forms"):
        for path in (LAB_ROOT / sub).rglob("*"):
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            found = set(pattern.findall(text))
            if found:
                ids_by_file[str(path.relative_to(LAB_ROOT))] = found

    all_ids = sorted({i for ids in ids_by_file.values() for i in ids}, key=int)
    return {"referenced_ids": all_ids, "count": len(all_ids)}


def count_registry_cases() -> dict:
    ground_truth = LAB_ROOT / "expected" / "modernization-ground-truth.json"
    if not ground_truth.exists():
        return {"count": 0, "ids": []}
    data = json.loads(ground_truth.read_text(encoding="utf-8"))
    cases = data.get("cases", [])
    ids = sorted((c["id"] for c in cases), key=lambda s: int(s.rsplit("-", 1)[1]))
    by_classification: dict[str, int] = {}
    by_risk: dict[str, int] = {}
    for c in cases:
        by_classification[c["classification"]] = by_classification.get(c["classification"], 0) + 1
        by_risk[c["risk"]] = by_risk.get(c["risk"], 0) + 1
    return {
        "count": len(cases),
        "ids": ids,
        "by_classification": by_classification,
        "by_risk": by_risk,
    }


def count_sql_objects() -> dict:
    ddl_files = sorted((LAB_ROOT / "database" / "ddl").glob("*.sql"))
    tables = 0
    for path in ddl_files:
        text = path.read_text(encoding="utf-8")
        tables += len(re.findall(r"(?im)^create table\s", text))

    pkg_specs = sorted((LAB_ROOT / "database" / "packages").glob("*.pks"))
    pkg_bodies = sorted((LAB_ROOT / "database" / "packages").glob("*.pkb"))
    procedures = 0
    functions = 0
    for path in pkg_specs:
        text = path.read_text(encoding="utf-8")
        procedures += len(re.findall(r"(?im)^\s*procedure\s", text))
        functions += len(re.findall(r"(?im)^\s*function\s", text))

    return {
        "tables": tables,
        "ddl_files": len(ddl_files),
        "packages": len(pkg_specs),
        "package_bodies": len(pkg_bodies),
        "public_procedures": procedures,
        "public_functions": functions,
        "seed_scripts": len(list((LAB_ROOT / "database" / "seed").glob("*.sql"))),
    }


def main() -> None:
    forms = {name: form_metrics(name) for name in FORMS}

    totals = {
        key: sum(f[key] for f in forms.values())
        for key in next(iter(forms.values())).keys()
    }

    report = {
        "forms": forms,
        "forms_totals": totals,
        "database": count_sql_objects(),
        "lom_mod_ids_referenced_in_fixtures": count_lom_mod_refs(),
        "lom_mod_cases_in_registry": count_registry_cases(),
    }

    print(json.dumps(report, indent=2))

    referenced = set(report["lom_mod_ids_referenced_in_fixtures"]["referenced_ids"])
    registered = {i.rsplit("-", 1)[1] for i in report["lom_mod_cases_in_registry"]["ids"]}
    missing_from_registry = sorted(referenced - registered, key=int)
    if missing_from_registry:
        print(
            f"\nWARNING: {len(missing_from_registry)} LOM-MOD id(s) are referenced in "
            f"forms/ or database/ but have no entry in modernization-ground-truth.json: "
            f"{', '.join('LOM-MOD-' + i for i in missing_from_registry)}",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
