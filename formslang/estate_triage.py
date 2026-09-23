"""Suggested investigation groups: one triage projection for every deliverable.

This replaces the earlier "migration waves". A group says where a reviewer
should look first and why; it is **not** a migration schedule, a dependency
order, an effort estimate or a readiness claim. Risk says nothing about
coupling, so no group is called independent, foundational or a quick win.

Inputs are the delivery snapshot rows already shared by Overview, Review and
Reports: finding rows (measured risk, intervention, review state, hotspot
links) and hotspot candidates. Every module lands in exactly one group, chosen
by its strongest *unresolved* evidence, and carries the explicit reasons.
"""

from __future__ import annotations

from collections import defaultdict

RESOLVED = frozenset({"APPROVE", "MODIFY"})
DISCLAIMER = ("Investigation groups order review work by observed, unresolved evidence. They are "
              "not a migration schedule, dependency order, effort estimate or readiness claim.")
GROUPS = (
    ("INVESTIGATE_FIRST", "Investigate first",
     "Unresolved CRITICAL findings, or a HIGH-severity hotspot candidate."),
    ("ARCHITECTURE_DECISIONS", "Architecture decisions pending",
     "Unresolved HIGH findings, manual interventions or hotspot candidates."),
    ("EVIDENCE_INCOMPLETE", "Evidence incomplete",
     "Unresolved findings whose risk could not be measured (UNKNOWN)."),
    ("REMAINING_REVIEW", "Remaining review",
     "Other findings that still need a human decision."),
    ("REVIEWED", "Reviewed",
     "Every finding in the module carries an accepted or changed human decision."),
)


def investigation_groups(findings, hotspots) -> dict:
    """Group modules by their strongest unresolved evidence, deterministically."""
    hotspot_severity = {h["id"]: h.get("severity", "") for h in hotspots}
    modules = defaultdict(lambda: {"findings": 0, "unresolved": 0, "reasons": set(), "stale": 0,
                                   "hotspots": set()})
    for row in findings:
        module = row.get("module") or "UNKNOWN"
        data = modules[module]
        data["findings"] += 1
        state = row.get("review_state", "PENDING")
        if state in RESOLVED:
            continue
        data["unresolved"] += 1
        if state == "STALE":
            data["stale"] += 1
            data["reasons"].add("STALE_DECISION")
        risk = row.get("risk", "UNKNOWN")
        if risk in {"CRITICAL", "HIGH", "UNKNOWN"}:
            data["reasons"].add(f"UNRESOLVED_{risk}")
        if row.get("intervention") == "MANUAL":
            data["reasons"].add("MANUAL_INTERVENTION")
        for hotspot in row.get("hotspot_ids", ()):
            data["hotspots"].add(hotspot)
            data["reasons"].add(f"HOTSPOT_{hotspot_severity.get(hotspot, 'CANDIDATE')}")
    grouped = {key: [] for key, _, _ in GROUPS}
    for module, data in sorted(modules.items()):
        reasons = data["reasons"]
        if data["unresolved"] == 0:
            key = "REVIEWED"
        elif reasons & {"UNRESOLVED_CRITICAL", "HOTSPOT_HIGH"}:
            key = "INVESTIGATE_FIRST"
        elif reasons & {"UNRESOLVED_HIGH", "MANUAL_INTERVENTION", "HOTSPOT_MEDIUM", "HOTSPOT_CANDIDATE"}:
            key = "ARCHITECTURE_DECISIONS"
        elif "UNRESOLVED_UNKNOWN" in reasons:
            key = "EVIDENCE_INCOMPLETE"
        else:
            key = "REMAINING_REVIEW"
        grouped[key].append({"module": module, "findings": data["findings"],
                             "unresolved": data["unresolved"], "stale_decisions": data["stale"],
                             "hotspot_candidates": len(data["hotspots"]),
                             "reasons": sorted(reasons)})
    return {
        "schema": "formslang-investigation-groups/1",
        "disclaimer": DISCLAIMER,
        "groups": [{"id": key, "name": name, "rule": rule, "modules": grouped[key]}
                   for key, name, rule in GROUPS],
    }


def investigation_markdown(groups: dict, escape=str) -> str:
    """Plain Markdown rendering; ``escape`` neutralizes Markdown in values."""
    lines = ["# Suggested investigation groups", "", f"> {groups['disclaimer']}", ""]
    for group in groups["groups"]:
        lines += [f"## {group['name']}", "", f"_{group['rule']}_", ""]
        if not group["modules"]:
            lines += ["No modules in this group.", ""]
            continue
        for item in group["modules"]:
            reasons = ", ".join(item["reasons"]) or "none"
            lines.append(f"- **{escape(item['module'])}**: {item['unresolved']} of {item['findings']} "
                         f"findings unresolved; {item['hotspot_candidates']} hotspot candidate(s); "
                         f"reasons: {escape(reasons)}")
        lines.append("")
    return "\n".join(lines)
