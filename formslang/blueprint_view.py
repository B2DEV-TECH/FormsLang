"""Bounded, evidence-linked reading paths for the Blueprint workbench.

This is a projection of the knowledge model, not a second analysis engine.
Ordering is explicit: stale reviews, integration/transaction decisions, rule
candidates, then other code. It is a reading order, never a new risk score.
"""

from collections import Counter


def overview(payload):
    nodes = {n["id"]: n for n in payload["entities"]}
    findings = {f["entity"]: f for f in payload["findings"]}
    incoming, outgoing = {}, {}
    for edge in payload["edges"]:
        incoming.setdefault(edge["target"], []).append(edge)
        outgoing.setdefault(edge["source"], []).append(edge)

    def component(n):
        f = findings.get(n["id"], {})
        return {"id": n["id"], "name": n["name"], "type": n["type"],
                "module": n["module"], "owner": n["attributes"].get("owner", ""),
                "recommendation": f.get("recommendation", "UNKNOWN"),
                "review": f.get("review_state", "PENDING"),
                "classification": f.get("classification", []),
                "reason": f.get("reason", ""),
                "dependency_count": sum(e["type"] != "CONTAINS" for e in outgoing.get(n["id"], []))}

    code = [n for n in nodes.values() if n["type"] in {"TRIGGER", "PROGRAM_UNIT"}]
    pending = [n for n in code if findings.get(n["id"], {}).get("review_state", "PENDING")
               not in {"APPROVE", "MODIFY"}]

    def order(n):
        f = findings.get(n["id"], {})
        categories = set(f.get("classification", []))
        priority = (0 if f.get("review_state") == "STALE" else
                    1 if categories & {"INTEGRATION", "TRANSACTION_CONTROL"} else
                    2 if "BUSINESS_RULE" in categories else 3)
        return priority, n["module"], n["name"], n["id"]

    # Collapse only genuine graph paths: source component -> dependency.
    # No implicit order of execution or invented Forms -> API -> database edges.
    relevant = {"CALLS", "READS", "WRITES", "USES_PROGRAM_UNIT", "OPENS_FORM",
                "NAVIGATES_TO", "COMMITS", "EXECUTES_QUERY"}
    paths = {}
    for e in payload["edges"]:
        if e["type"] not in relevant:
            continue
        key = (e["source"], e["target"], e["type"], e["level"])
        if key not in paths:
            paths[key] = {"source": component(nodes[e["source"]]),
                          "target": component(nodes[e["target"]]),
                          "relationship": e["type"], "level": e["level"], "evidence": []}
        paths[key]["evidence"].extend(e["evidence"])
    path_rows = sorted(paths.values(), key=lambda p: (
        order(nodes[p["source"]["id"]]), p["relationship"], p["target"]["name"]))
    for p in path_rows:
        p["evidence"] = sorted(set(p["evidence"]))

    return {"code_total": len(code), "code_pending": len(pending),
            "code_reviewed": len(code) - len(pending),
            "categories": dict(Counter(c for n in code for c in findings.get(n["id"], {}).get("classification", []))),
            "start_here": [component(n) for n in sorted(pending, key=order)[:6]],
            "reading_order": "Stale reviews first, then integrations and transactions, rule candidates, and other code. This is not a risk score.",
            "paths": path_rows[:24], "path_total": len(path_rows),
            "modules": [component(n) for n in nodes.values() if n["type"] == "FORM"],
            "references": [component(n) for n in sorted(nodes.values(), key=lambda n: (-len(incoming.get(n["id"], [])), n["name"], n["id"]))
                           if n["type"] in {"PACKAGE_REFERENCE", "TABLE_OR_VIEW_REFERENCE", "ROUTINE_REFERENCE"}][:12]}
