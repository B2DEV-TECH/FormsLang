"""
Compute structural metrics for the LOM modernization lab directly from the
committed artifacts (forms/xml/*.xml via formslang.parser, database/**/*.sql
via plain text counting). Stdlib + formslang only -- no third-party deps.

Every number this script prints is measured from the files in this lab at
run time, not copied from documentation. If a fixture changes, re-run this
script and update any doc that quotes a stale count -- do not hand-edit a
count without checking it here first. tests/test_fixtures.py asserts that
the tables in assessment/complexity-and-risk-rollup.md equal what this
script computes, so a stale doc fails the suite rather than going unnoticed.

Usage (from the repo root or from the lab root):
    python examples/modernization-lab/metrics/compute_metrics.py
    python metrics/compute_metrics.py

Exit status is 1 if any LOM-MOD-### id referenced in the fixtures or the
narrative docs has no entry in the ground-truth registry.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = LAB_ROOT.parent.parent

sys.path.insert(0, str(REPO_ROOT))

import formslang.parser as formslang_parser

FORMS = ["CUSTOMERS", "ORDERS", "INVENTORY", "APPROVALS"]

LOM_MOD_REF = re.compile(r"LOM-MOD-(\d{3})")

# Where LOM-MOD ids are the answer key (fixtures) versus where they are
# narrative cross-references. Both must resolve against the registry.
FIXTURE_DIRS = ("database", "forms")
DOC_SOURCES = (
    "docs",
    "blueprint",
    "assessment",
    "README.md",
    "HANDOFF.md",
    "REVIEW.md",
)

# IDs the registry's `id_notes` documents as reserved during drafting and then
# dropped. The narrative docs may mention them (README.md, HANDOFF.md); the
# fixtures under forms/ and database/ must not, and tests/test_fixtures.py
# checks that each one is really described in `id_notes` and has no case.
DOCUMENTED_UNFILLED_IDS = frozenset({"040"})

# The "By module" attribution rule used by assessment/complexity-and-risk-rollup.md:
# a case belongs to the FIRST file its `source` field cites.
_SOURCE_FILE = re.compile(r"(forms|database)/[\w./-]+")


def module_for_source(source: str) -> str:
    """Map a case's `source` string to the module the rollup attributes it to.

    forms/xml/<M>.xml            -> "<M>.fmb"
    forms/libraries/OM_SHARED.*  -> "OM_SHARED.pll"
    database/packages/<pkg>.*    -> "<pkg>"
    anything else under database -> "database DDL/views"
    """
    m = _SOURCE_FILE.search(source)
    if m is None:
        raise ValueError(f"no forms/ or database/ path in source: {source!r}")
    first = m.group(0)
    if first.startswith("forms/xml/"):
        return Path(first).stem + ".fmb"
    if first.startswith("forms/libraries/OM_SHARED"):
        return "OM_SHARED.pll"
    if first.startswith("database/packages/"):
        return Path(first).stem
    return "database DDL/views"


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


def _lom_mod_ids_under(roots: tuple[str, ...]) -> dict[str, set[str]]:
    ids_by_file: dict[str, set[str]] = {}
    for sub in roots:
        top = LAB_ROOT / sub
        paths = top.rglob("*") if top.is_dir() else [top]
        for path in paths:
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            found = set(LOM_MOD_REF.findall(text))
            if found:
                ids_by_file[str(path.relative_to(LAB_ROOT))] = found
    return ids_by_file


def count_lom_mod_refs(roots: tuple[str, ...] = FIXTURE_DIRS) -> dict:
    """Every LOM-MOD-### id referenced anywhere under the given roots,
    independent of the ground-truth JSON, so drift between "case exists in
    fixtures/docs" and "case exists in the registry" is directly detectable."""
    ids_by_file = _lom_mod_ids_under(roots)
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
    by_category: dict[str, int] = {}
    by_module: dict[str, dict[str, int]] = {}
    for c in cases:
        by_classification[c["classification"]] = by_classification.get(c["classification"], 0) + 1
        by_risk[c["risk"]] = by_risk.get(c["risk"], 0) + 1
        by_category[c["category"]] = by_category.get(c["category"], 0) + 1
        per_module = by_module.setdefault(module_for_source(c["source"]), {})
        per_module[c["classification"]] = per_module.get(c["classification"], 0) + 1
    return {
        "count": len(cases),
        "ids": ids,
        "by_classification": by_classification,
        "by_risk": by_risk,
        "by_category": by_category,
        # module -> {classification -> count}; sum of the inner dict is the
        # "Cases" column of the rollup's "By module" table.
        "by_module": by_module,
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
        for key in next(iter(forms.values()))
    }

    report = {
        "forms": forms,
        "forms_totals": totals,
        "database": count_sql_objects(),
        "lom_mod_ids_referenced_in_fixtures": count_lom_mod_refs(FIXTURE_DIRS),
        "lom_mod_ids_referenced_in_docs": count_lom_mod_refs(DOC_SOURCES),
        "lom_mod_cases_in_registry": count_registry_cases(),
    }

    print(json.dumps(report, indent=2))

    in_fixtures = set(report["lom_mod_ids_referenced_in_fixtures"]["referenced_ids"])
    in_docs = set(report["lom_mod_ids_referenced_in_docs"]["referenced_ids"])
    registered = {i.rsplit("-", 1)[1] for i in report["lom_mod_cases_in_registry"]["ids"]}
    missing_from_registry = sorted(
        (in_fixtures - registered) | (in_docs - registered - DOCUMENTED_UNFILLED_IDS), key=int
    )
    if missing_from_registry:
        print(
            f"\nWARNING: {len(missing_from_registry)} LOM-MOD id(s) are referenced in "
            f"the fixtures or docs but have no entry in modernization-ground-truth.json: "
            f"{', '.join('LOM-MOD-' + i for i in missing_from_registry)}",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
