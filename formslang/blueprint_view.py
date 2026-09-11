"""Bounded, evidence-linked reading paths for the Blueprint workbench.

This is a projection of the knowledge model, not a second analysis engine.
Ordering is explicit: stale reviews, integration/transaction decisions, rule
candidates, then other code. It is a reading order, never a new risk score.
"""

from collections import Counter
from heapq import nsmallest


def overview(payload):
    nodes = {n["id"]: n for n in payload["entities"]}
    findings = {f["entity"]: f for f in payload["findings"]}
    incoming, outgoing = Counter(), Counter()
    for edge in payload["edges"]:
        incoming[edge["target"]] += 1
        outgoing[edge["source"]] += edge["type"] != "CONTAINS"

    def component(n):
        f = findings.get(n["id"], {})
        return {"id": n["id"], "name": n["name"], "type": n["type"],
                "module": n["module"], "owner": n["attributes"].get("owner", ""),
                "recommendation": f.get("recommendation", "UNKNOWN"),
                "review": f.get("review_state", "PENDING"),
                "classification": f.get("classification", []),
                "reason": f.get("reason", ""),
                "dependency_count": outgoing[n["id"]]}

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
            paths[key] = set()
        paths[key].update(e["evidence"])

    def path_order(key):
        return order(nodes[key[0]]), key[2], nodes[key[1]]["name"], key

    # Show different kinds of connections first, then fill the bounded sample
    # in the documented reading order. A page of repeated commits is not a map.
    representatives = {}
    for key in paths:
        kind = key[2], nodes[key[0]]["type"]
        previous = representatives.get(kind)
        if previous is None or path_order(key) < path_order(previous):
            representatives[kind] = key
    chosen = nsmallest(24, representatives.values(), key=path_order)
    chosen_set = set(chosen)
    chosen.extend(nsmallest(24 - len(chosen), (k for k in paths if k not in chosen_set), key=path_order))
    path_rows = [{"source": component(nodes[k[0]]), "target": component(nodes[k[1]]),
                  "relationship": k[2], "level": k[3], "evidence": sorted(paths[k])}
                 for k in chosen]

    return {"code_total": len(code), "code_pending": len(pending),
            "code_reviewed": len(code) - len(pending),
            "categories": dict(Counter(c for n in code for c in findings.get(n["id"], {}).get("classification", []))),
            "start_here": [component(n) for n in sorted(pending, key=order)[:6]],
            "reading_order": "Stale reviews first, then integrations and transactions, rule candidates, and other code. This is not a risk score.",
            "paths": path_rows, "path_total": len(paths),
            "modules": [component(n) for n in nodes.values() if n["type"] == "FORM"],
            "references": [component(n) for n in nsmallest(12,
                           (n for n in nodes.values() if n["type"] in {"PACKAGE_REFERENCE", "TABLE_OR_VIEW_REFERENCE", "ROUTINE_REFERENCE"}),
                           key=lambda n: (-incoming[n["id"]], n["name"], n["id"]))]}
