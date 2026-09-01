"""Deterministic golden dump for one fixture in the corpus.

Feeds a fixture module through the exact pipeline a reviewer's session
takes -- parse, task queue, dependency graph, offline proposal, export --
and reduces the result to a dict with every non-deterministic field
removed (wall-clock timestamps, filesystem paths). Two runs against the
same fixture and the same code always produce byte-identical JSON; see
tests/test_golden_corpus.py for how that is verified, and
tests/update_golden.py for the only sanctioned way to change a golden
file.

Nothing here calls a network provider: ``formslang.ai.EchoProvider`` is
offline and, by construction, its answer does not depend on its input --
see the module docstring there. Nothing here is content either: fixtures
are 100% synthetic PL/SQL, never real Form data.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import tempfile
from pathlib import Path

# Running a script by file path (``py tests/update_golden.py``) puts that
# script's own directory at sys.path[0], not the repo root -- so a plain
# ``from formslang import ...`` can silently resolve to whatever copy of
# formslang happens to be installed in site-packages instead of this
# checkout. Pin the repo root first so the local source always wins,
# regardless of how this module ends up being imported.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from formslang import rules
from formslang.ai import EchoProvider
from formslang.convert import build_tasks, propose_many
from formslang.depgraph import build as build_depgraph
from formslang.parser import parse_xml
from formslang.store import Store

CORPUS_DIR = Path(__file__).parent / "fixtures" / "corpus"
GOLDEN_DIR = Path(__file__).parent / "fixtures" / "golden"
TIERS = ("tiny", "small", "medium", "large", "pathological")

_EXPORTED_LINE = re.compile(r"^-- exported: .*$", re.MULTILINE)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _module_dump(mod) -> dict:
    """Facts a fixture is meant to prove, never its own filesystem path."""
    return {
        "name": mod.name,
        "title": mod.title,
        "first_block": mod.first_block,
        "blocks": len(mod.blocks),
        "items": len(mod.all_items),
        "triggers": len(mod.all_triggers),
        "program_units": len(mod.program_units),
        "relations": len(mod.relations),
        "record_groups": len(mod.record_groups),
        "lovs": len(mod.lovs),
        "attached_libraries": sorted(mod.attached_libraries),
        "parameters": sorted(mod.parameters),
        "canvases": sorted(mod.canvases),
        "windows": sorted(mod.windows),
        "alerts": sorted(mod.alerts),
        "editors": sorted(mod.editors),
        "object_groups": sorted(mod.object_groups),
        "reports": sorted(mod.reports),
        "tab_pages": sorted(mod.tab_pages),
        "graphics_count": mod.graphics_count,
        "plsql_lines": mod.plsql_lines,
        "convert_warnings": mod.convert_warnings,
    }


def _verdict_counts(tasks) -> dict:
    counts = {v: 0 for v in rules.VERDICT_ORDER}
    for t in tasks:
        counts[t.verdict] = counts.get(t.verdict, 0) + 1
    return counts


def _task_dump(tasks) -> list[dict]:
    """One row per task, ordered by id -- what a rules.py change moves."""
    return [
        {
            "id": t.id,
            "kind": t.kind,
            "owner": t.owner,
            "name": t.name,
            "verdict": t.verdict,
            "apex_hint": t.apex_hint,
            "lines": t.lines,
            "builtins": [{"name": n, "verdict": v, "apex": a} for n, v, a in t.builtins],
            "item_refs": t.item_refs,
            "globals_used": t.globals_used,
        }
        for t in sorted(tasks, key=lambda t: t.id)
    ]


def _proposal_dump(tasks) -> dict:
    """Every task run through the offline EchoProvider, keyed by task id."""
    proposals = propose_many(tasks, EchoProvider())
    return {task_id: p.to_dict() for task_id, p in sorted(proposals.items())}


def _export_manifest(mod, tasks, source_path: str, scratch: Path) -> dict:
    """Run the real export path once and reduce it to a files+checksum list.

    Excludes exactly the two fields that vary between runs on two
    machines: the ``-- exported: <timestamp>`` line in ``approved.sql``
    and the session's ``created_at`` in ``session.json``. Everything else
    in a fresh session (no proposal saved, no decision made) is already
    deterministic, so no other field needs stripping.
    """
    db_path = scratch / "session.db"
    out_dir = scratch / "export"
    store = Store(db_path)
    try:
        store.init_session(mod.name, source_path)
        store.add_tasks(tasks)
        sql_path, json_path = store.export(out_dir)
    finally:
        store.close()

    sql_text = _EXPORTED_LINE.sub("-- exported: <normalized>", sql_path.read_text(encoding="utf-8"))
    session_data = json.loads(json_path.read_text(encoding="utf-8"))
    session_data["session"]["created_at"] = "<normalized>"
    json_text = json.dumps(session_data, indent=2, sort_keys=True, ensure_ascii=False)

    files = sorted(p.name for p in out_dir.iterdir())
    return {
        "files": files,
        "approved_sql_sha256": _sha256(sql_text),
        "session_json_sha256": _sha256(json_text),
    }


def build_golden(tier: str) -> dict:
    """Run one corpus tier through the full pipeline as a plain, sorted dict."""
    fixture_dir = CORPUS_DIR / tier
    xml_path = fixture_dir / "module.xml"
    source_path = f"tests/fixtures/corpus/{tier}/module.xml"

    mod = parse_xml(xml_path)
    tasks = build_tasks(mod)
    task_ids = {f"{t.kind}|{t.owner}|{t.name}".upper(): t.id for t in tasks}
    graph = build_depgraph(mod, task_ids=task_ids)

    with tempfile.TemporaryDirectory(prefix="formslang-golden-") as tmp:
        export = _export_manifest(mod, tasks, source_path, Path(tmp))

    return {
        "tier": tier,
        "module": _module_dump(mod),
        "verdict_counts": _verdict_counts(tasks),
        "tasks": _task_dump(tasks),
        "graph_summary": graph.summary(),
        "proposals": _proposal_dump(tasks),
        "export": export,
    }


def golden_path(tier: str) -> Path:
    return GOLDEN_DIR / f"{tier}.json"


def dumps(golden: dict) -> str:
    """Canonical text form -- what both the runner and the updater diff."""
    return json.dumps(golden, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
