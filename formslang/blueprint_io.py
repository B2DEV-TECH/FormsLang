"""Local Blueprint inputs and reproducible, self-contained review artifacts."""

from __future__ import annotations

import html
import json
import os
import tempfile
from pathlib import Path

from . import blueprint
from .oracle import convert_module, detect_toolchain
from .parser import parse_xml
from .store import Store

MAX_SOURCE_BYTES = 256 * 1024 * 1024


def load(source: Path, out: Path, *, title="", oracle_home=None, enterprise=False,
         metadata_path=None, recursive=True) -> dict:
    # Share directory collection/Forms2XML conventions with assessment.
    from .cli import _collect

    source, out = Path(source).resolve(), Path(out).resolve()
    if not source.exists():
        raise ValueError("Blueprint source does not exist")
    if source == out:
        raise ValueError("choose an output directory distinct from the source")
    paths = [p for p in _collect([str(source)], recursive) if out not in p.resolve().parents]
    if not paths:
        raise ValueError("No Forms .fmb/.xml sources found")
    base = source if source.is_dir() else source.parent
    modules, keys, failures = [], [], []
    tc = None
    for path in paths:
        key = path.relative_to(base).as_posix()
        try:
            if path.stat().st_size > MAX_SOURCE_BYTES:
                raise ValueError("source exceeds 256 MiB limit")
            if path.suffix.lower() == ".xml":
                xml, log = path, ""
            else:
                tc = tc or detect_toolchain(oracle_home)
                # Paths with matching basenames and changed binaries never share
                # an Oracle conversion cache entry.
                import hashlib

                cache = hashlib.sha256(path.read_bytes()).hexdigest()
                cache_dir = out / "xml" / cache
                if not cache_dir.resolve().is_relative_to(out):
                    raise ValueError("Blueprint conversion cache escapes output directory")
                xml, log = convert_module(path, cache_dir, tc)
            module = parse_xml(xml, convert_log=log)
            module.source_path = key
            modules.append(module)
            keys.append(key)
        except (OSError, ValueError, RuntimeError) as exc:
            failures.append({"source": key, "error": type(exc).__name__,
                             "detail": str(exc)[:500]})
        except Exception as exc:  # noqa: BLE001 -- preserve partial portfolio results
            failures.append({"source": key, "error": type(exc).__name__,
                             "detail": "Source could not be parsed; inspect the original input locally."})
    metadata = []
    if metadata_path:
        path = Path(metadata_path)
        if path.stat().st_size > 32 * 1024 * 1024:
            raise ValueError("metadata exceeds 32 MiB limit")
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(payload, dict) or not isinstance(payload.get("objects"), list):
            raise ValueError("metadata must contain an objects array")
        metadata = payload["objects"]
    return blueprint.build(modules, title=title or source.stem, source_keys=keys,
                           failures=failures, enterprise=enterprise, metadata=metadata)


def save_session(payload, out: Path, source: Path) -> Path:
    out = Path(out).resolve()
    path = out / "blueprint.session.db"
    if not path.resolve().is_relative_to(out):
        raise ValueError("Blueprint session path escapes output directory")
    store = Store(path)
    try:
        previous = store.session().get("source_path")
        if previous and Path(previous).resolve() != Path(source).resolve():
            raise ValueError("output already belongs to another Blueprint source; choose a separate output directory")
        store.init_session(payload["application"]["name"], str(Path(source).resolve()))
        store.save_blueprint(payload)
    finally:
        store.close()
    return path


def _md(value) -> str:
    # Markdown is a display artifact, not an opportunity for source HTML/links.
    text = html.escape(str(value)).replace("\\", "\\\\")
    for char in "`*_{}[]()#+!~":
        text = text.replace(char, "\\" + char)
    return text.replace("|", "&#124;").replace("\r", " ").replace("\n", " ")


def _table(headers, rows):
    return "| " + " | ".join(headers) + " |\n| " + " | ".join("---" for _ in headers) + " |\n" + "\n".join("| " + " | ".join(_md(x) for x in row) + " |" for row in rows) + "\n"


def documents(bp) -> dict[str, str]:
    names = {n["id"]: n["name"] for n in bp["entities"]}
    evidence = {p["id"]: p for p in bp["evidence"]}
    findings = {f["entity"]: f for f in bp["findings"]}
    intro = f"# {_md(bp['application']['name'])} — Modernization Blueprint\n\n"
    caveat = "\nLocal static analysis. Recommendations require human review. Coverage is not verified functional parity.\n\n"
    summary = intro + caveat + _table(["Entity", "Count"], bp["summary"]["entities"].items())
    summary += "\nMigration work progress: " + str(bp["readiness"]["score"]) + "/100. " + bp["readiness"]["explanation"]["caveat"] + "\n"
    summary += "\nFailed sources: " + str(len(bp["failures"])) + ". Inspect blueprint.json before using portfolio totals.\n"
    plan = intro + caveat + _table(["Component", "Recommendation (INFERENCE)", "Reason", "Human review"],
        [(names[f["entity"]], f["recommendation"], f["reason"], f.get("review_state", "PENDING")) for f in bp["findings"]])
    plan += "\nEvidence and epistemic distinctions\n\n"
    for f in bp["findings"]:
        plan += f"\n## {_md(names[f['entity']])}\n\n"
        for stmt in f["statements"]:
            plan += f"- **{stmt['level']}**: {_md(stmt['text'])}\n"
        for pid in f["evidence"]:
            p = evidence[pid]
            plan += f"- **{p['level']}**: {_md(p['source'])} / {_md(p['component'])} / body line {p.get('location', {}).get('line', 'n/a')}: {_md(p['text'])}\n"
    deps = intro + _table(["Source", "Relationship", "Target", "Evidence level"],
        [(names[e["source"]], e["type"], names[e["target"]], e["level"]) for e in bp["edges"]])
    rules = intro + caveat + _table(["Candidate (INFERENCE)", "Module", "Inputs"],
        [(n["name"], n["module"], ", ".join(n["attributes"].get("inputs", []))) for n in bp["entities"] if n["type"] == "BUSINESS_RULE"])
    coverage = intro + caveat + _table(["Capability", "Target", "Declared coverage", "Implementation evidence"],
        [(names[f["entity"]], f["coverage"]["target"], f["coverage"]["status"], f["coverage"]["evidence"]) for f in bp["findings"]])
    risk_report = intro + caveat + _table(["Component", "Risk", "Points", "Unresolved questions"],
        [(n["name"], n["attributes"].get("risk", {}).get("level", "UNKNOWN"), n["attributes"].get("risk", {}).get("score", "unmeasured"),
          "; ".join(findings.get(n["id"], {}).get("unresolved_questions", []))) for n in bp["entities"] if "risk" in n["attributes"]])
    risk_report += "\n" + "\n".join("- " + _md(x) for x in bp["limitations"]) + "\n"
    architecture = intro + caveat + "## Current — FACT (observed scope only)\n\n" + _table(["Layer", "Entities"], [(g["name"], len(g["entities"])) for g in bp["architecture"]["current"]])
    architecture += "\n## Target — INFERENCE\n\n" + _table(["Proposed layer", "Reason"], [(g["name"], g["reason"]) for g in bp["architecture"]["target"]])
    return {"executive-summary.md": summary, "application-architecture.md": architecture,
            "dependency-analysis.md": deps, "business-rule-inventory.md": rules,
            "modernization-plan.md": plan, "risk-report.md": risk_report,
            "modernization-coverage.md": coverage}


def diagrams(bp):
    # Source names never enter Mermaid syntax: IDs map back to blueprint.json.
    nodes = {n["id"]: n for n in bp["entities"]}
    chosen = [e for e in bp["edges"] if e["type"] != "CONTAINS"][:200]
    involved = sorted({e[k] for e in chosen for k in ("source", "target")})
    aliases = {nid: "n" + str(i) for i, nid in enumerate(involved)}
    graph = ["flowchart LR", "%% First 200 dependency edges; full graph in dependencies.json"]
    graph += [f'  {aliases[nid]}["{nodes[nid]["type"]}: {nid}"]' for nid in involved]
    graph += [f'  {aliases[e["source"]]} -->|{e["type"]}| {aliases[e["target"]]}' for e in chosen]
    current = ["flowchart LR", "%% Observed layer membership; links are containment, not runtime calls", '  app["Observed application"]']
    for i, group in enumerate(bp["architecture"]["current"]):
        current.append(f'  app --> c{i}["{group["name"]}: {len(group["entities"])}"]')
    target = ["flowchart LR", "%% RECOMMENDATION, requires human approval", '  apex["Oracle APEX (proposed)"] --> db["Existing PL/SQL / Oracle Database (review)"]']
    if bp["api_candidates"]:
        target += ['  apex --> api["Controlled domain API (candidate)"]', "  api --> db"]
    return {"dependencies.mmd": "\n".join(graph) + "\n", "current-architecture.mmd": "\n".join(current) + "\n", "target-architecture.mmd": "\n".join(target) + "\n"}


def render_html(bp):
    esc = html.escape
    reports = documents(bp)
    sections = "".join(f'<details><summary>{esc(name)}</summary><pre>{esc(body)}</pre></details>' for name, body in reports.items())
    # JSON is data in an inert element and escapes script termination. No fetch,
    # library, CDN, generated links or source-provided markup.
    data = json.dumps(bp, ensure_ascii=False, sort_keys=True).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>FormsLang Blueprint</title><style>body{font:16px system-ui;max-width:1100px;margin:2rem auto;padding:1rem;background:#101820;color:#e7eef5}h1{color:#f5a640}pre{white-space:pre-wrap;overflow-wrap:anywhere}summary,button{cursor:pointer;padding:.7rem}details{border:1px solid #52606c;margin:1rem 0;padding:.7rem}input{padding:.7rem;width:90%}li{margin:.7rem 0}small{color:#bdcbd7}</style><h1>Modernization Blueprint</h1><h2>' + esc(bp["application"]["name"]) + '</h2><p>FACT · INFERENCE · ASSUMPTION · UNKNOWN remain distinct. Human decisions required.</p><p>Source failures: ' + str(len(bp["failures"])) + '</p><label>Find an entity <input id="search" placeholder="Module, name or entity type"></label><p id="count"></p><ul id="results"></ul>' + sections + '<script type="application/json" id="blueprint-data">' + data + '</script><script>const bp=JSON.parse(document.getElementById("blueprint-data").textContent);const input=document.getElementById("search");function render(){const q=input.value.toLowerCase();const rows=bp.entities.filter(n=>(n.name+" "+n.module+" "+n.type).toLowerCase().includes(q));document.getElementById("count").textContent="Showing "+Math.min(rows.length,100)+" of "+rows.length+" entities. Full evidence in JSON and reports below.";const ul=document.getElementById("results");ul.replaceChildren();for(const n of rows.slice(0,100)){const li=document.createElement("li");li.textContent=n.type+" · "+n.module+" · "+n.name+" · "+n.review_state;ul.appendChild(li)}}input.addEventListener("input",render);render();</script></html>'


def write(payload, out: Path) -> Path:
    out = Path(out).resolve()
    root = out / "modernization"
    if not root.resolve().is_relative_to(out):
        raise ValueError("Blueprint output path escapes output directory")
    root.mkdir(parents=True, exist_ok=True)
    root = root.resolve()
    files = {"blueprint.json": payload, "architecture.json": payload["architecture"],
             "dependencies.json": {"entities": payload["entities"], "edges": payload["edges"], "evidence": payload["evidence"]},
             "business-rules.json": [n for n in payload["entities"] if n["type"] == "BUSINESS_RULE"],
             "modernization-plan.json": {"findings": payload["findings"], "api_candidates": payload["api_candidates"]}}
    rendered = {name: json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n" for name, value in files.items()}
    rendered["blueprint.html"] = render_html(payload)
    rendered.update({"reports/" + k: v for k, v in documents(payload).items()})
    rendered.update({"diagrams/" + k: v for k, v in diagrams(payload).items()})
    for name, content in rendered.items():
        target = root / name
        if not target.resolve().is_relative_to(root):
            raise ValueError("Blueprint output path escapes output directory")
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".blueprint-", dir=target.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(content)
            os.replace(tmp, target)
        finally:
            Path(tmp).unlink(missing_ok=True)
    return root
