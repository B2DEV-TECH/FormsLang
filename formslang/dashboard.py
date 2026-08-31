"""The project view: what the session actually says, counted rather than judged.

Everything on this page is arithmetic over rows that already exist -- the
deterministic analysis, the reviewer's decisions, the dependency graph and
the test specifications. No model is consulted, and no number here is a
model's opinion presented as a measurement.

The readiness score is the one figure that could be mistaken for a verdict,
so it is defined in :data:`COMPONENTS`, published by :func:`explain` and
printed on the screen beside the number itself. It is a weighted count of
things a person can go and verify -- how much was reviewed, how much was
approved, how much of the risk mass is low, how much of the behaviour is
settled, how much of the specification has been answered -- and nothing else.
A unit nobody measured contributes zero to every component: an unmeasured
unit is not evidence of readiness, and quietly excluding it would inflate
the score of the least finished sessions.

None of this says a migration is safe. It says how much of the work has
been done and how much of what is left is known to be hard.
"""

from __future__ import annotations

from . import behavior as behavior_mod
from . import risk as risk_mod
from . import rules, testspec
from .analysis import ENGINE_VERSION, summarize
from .store import APPROVED, PENDING, STATES

READINESS_VERSION = "readiness/1"

# How much of the risk mass each level carries, on a 0..1 scale. LOW is not
# free of risk, it is the floor of what this catalog can distinguish.
_RISK_WEIGHT = {
    risk_mod.LOW: 0.0,
    risk_mod.MEDIUM: 0.34,
    risk_mod.HIGH: 0.67,
    risk_mod.CRITICAL: 1.0,
}

# CHANGED counts as half: a difference that has been described and accepted
# is not the same problem as one nobody has established yet.
_BEHAVIOR_CREDIT = {
    behavior_mod.PRESERVED: 1.0,
    behavior_mod.CHANGED: 0.5,
    behavior_mod.UNCERTAIN: 0.0,
}

# The readiness formula, in full. Each entry is a share of 100 points and a
# sentence a reviewer can check against the counts on the same screen.
COMPONENTS = (
    {
        "key": "reviewed",
        "weight": 30,
        "title": "Units a person has decided on",
        "detail": "Units whose state is no longer pending, over every unit in the "
                  "session. Approval is a human act; nothing else moves this.",
    },
    {
        "key": "approved",
        "weight": 25,
        "title": "Units approved",
        "detail": "Units in the approved state, over every unit in the session. "
                  "Rejected and needs-work units count as not approved.",
    },
    {
        "key": "risk_clear",
        "weight": 20,
        "title": "Risk mass that is low",
        "detail": "1 - (sum of risk weights / unit count), weighting LOW 0, "
                  "MEDIUM 0.34, HIGH 0.67, CRITICAL 1.0. A unit with no analysis "
                  "carries the full weight of 1.0.",
    },
    {
        "key": "behavior_settled",
        "weight": 15,
        "title": "Behaviour that is settled",
        "detail": "PRESERVED counts 1, CHANGED counts 0.5, UNCERTAIN counts 0, "
                  "over every unit. A unit with no analysis counts 0.",
    },
    {
        "key": "tests_reviewed",
        "weight": 10,
        "title": "Test cases answered",
        "detail": "Cases accepted, rejected or marked needs-modification, over "
                  "every generated case. A session with no cases scores 0 here.",
    },
)
_TOTAL_WEIGHT = sum(c["weight"] for c in COMPONENTS)

_HOT_UNITS = 8  # how many units each ranking names before it stops


def explain() -> dict:
    """The formula, verbatim, for printing next to the score."""
    return {
        "version": READINESS_VERSION,
        "engine_version": ENGINE_VERSION,
        "total_weight": _TOTAL_WEIGHT,
        "components": [dict(c) for c in COMPONENTS],
        "formula": "readiness = sum(weight x component) over the components above, "
                   "each component a ratio in 0..1 measured over every unit in the "
                   "session -- not only the measured ones.",
        "caveat": "A count of work done, not a judgement that the migration is safe. "
                  "No model contributes to this number.",
    }


def _ratios(views, cases) -> dict[str, float]:
    """Each component as a plain ratio, over every unit in the session."""
    total = len(views)
    if not total:
        return {c["key"]: 0.0 for c in COMPONENTS}

    decided = sum(1 for v in views if v.state != PENDING)
    approved = sum(1 for v in views if v.state == APPROVED)

    risk_mass = 0.0
    behavior_credit = 0.0
    for view in views:
        item = view.analysis or {}
        level = (item.get("risk") or {}).get("level")
        value = (item.get("behavior") or {}).get("value")
        # No analysis means no evidence, and no evidence is not good news.
        risk_mass += _RISK_WEIGHT.get(level, 1.0)
        behavior_credit += _BEHAVIOR_CREDIT.get(value, 0.0)

    answered = sum(1 for c in cases if c.get("state", PENDING) != testspec.PENDING)
    return {
        "reviewed": decided / total,
        "approved": approved / total,
        "risk_clear": 1.0 - (risk_mass / total),
        "behavior_settled": behavior_credit / total,
        "tests_reviewed": (answered / len(cases)) if cases else 0.0,
    }


def readiness(views, cases) -> dict:
    """The score, its parts, and the numbers each part was computed from."""
    ratios = _ratios(views, cases)
    parts = []
    score = 0.0
    for component in COMPONENTS:
        ratio = max(0.0, min(1.0, ratios[component["key"]]))
        points = component["weight"] * ratio
        score += points
        parts.append({
            **component,
            "ratio": round(ratio, 4),
            "points": round(points, 1),
        })
    return {
        "score": round(score, 1),
        "of": _TOTAL_WEIGHT,
        "components": parts,
        "version": READINESS_VERSION,
    }


def _blockers(views, summary, coverage, test_coverage, graph_summary) -> list[dict]:
    """What stands between this session and a finished migration.

    Deliberately kept out of the score: a blocker is a thing to go and do,
    and folding it into a percentage would hide it behind arithmetic.
    """
    out: list[dict] = []
    if coverage.get("missing"):
        out.append({
            "kind": "unanalysed",
            "count": coverage["missing"],
            "detail": "unit(s) with no deterministic analysis -- reopen the module "
                      "to compute one",
        })
    if coverage.get("stale"):
        out.append({
            "kind": "stale_analysis",
            "count": coverage["stale"],
            "detail": "unit(s) analysed under an older rule set",
        })
    unproposed = sum(1 for v in views if not v.proposal)
    if unproposed:
        out.append({
            "kind": "unproposed",
            "count": unproposed,
            "detail": "unit(s) with no conversion proposal yet",
        })
    pending = sum(1 for v in views if v.state == PENDING)
    if pending:
        out.append({
            "kind": "unreviewed",
            "count": pending,
            "detail": "unit(s) nobody has decided on",
        })
    uncertain = summary.get("behavior", {}).get(behavior_mod.UNCERTAIN, 0)
    if uncertain:
        out.append({
            "kind": "uncertain_behavior",
            "count": uncertain,
            "detail": "unit(s) whose behaviour after migration the rules could not "
                      "establish",
        })
    unsupported = summary.get("unsupported", {})
    if unsupported:
        out.append({
            "kind": "unsupported",
            "count": sum(unsupported.values()),
            "detail": "call(s) to constructs with no APEX equivalent: "
                      + ", ".join(list(unsupported)[:5]),
        })
    missing_nodes = (graph_summary or {}).get("missing", 0)
    if missing_nodes:
        out.append({
            "kind": "missing_dependency",
            "count": missing_nodes,
            "detail": "object(s) referenced by this form and not declared in it",
        })
    open_cases = test_coverage.get("states", {}).get(testspec.PENDING, 0)
    if open_cases:
        out.append({
            "kind": "unanswered_tests",
            "count": open_cases,
            "detail": "test case(s) nobody has accepted or rejected",
        })
    return out


def _riskiest(views) -> list[dict]:
    """The units to look at first, ranked by the score the rules produced."""
    rows = []
    for view in views:
        item = view.analysis or {}
        risk = item.get("risk") or {}
        if not risk.get("level"):
            continue
        rows.append({
            "task_id": view.task["id"],
            "title": view.task.get("title", ""),
            "kind": view.task.get("kind", ""),
            "verdict": view.task.get("verdict", ""),
            "level": risk.get("level", ""),
            "score": round(risk.get("score", 0.0), 1),
            "behavior": (item.get("behavior") or {}).get("value", ""),
            "state": view.state,
            "factors": len(risk.get("factors") or []),
        })
    rows.sort(key=lambda r: (-r["score"], r["title"]))
    return rows[:_HOT_UNITS]


def _unsupported_units(views) -> list[dict]:
    """Each unsupported construct, and the units that actually call it.

    The count alone reads as a statistic; the unit names make it a work list.
    """
    found: dict[str, dict] = {}
    for view in views:
        for finding in (view.analysis or {}).get("findings", []) or []:
            if finding.get("migration_class") != rules.UNSUPPORTED:
                continue
            row = found.setdefault(finding["name"], {
                "name": finding["name"],
                "count": 0,
                "apex": finding.get("apex", ""),
                "category": finding.get("category_label") or finding.get("category", ""),
                "units": [],
            })
            row["count"] += finding.get("count", 1)
            title = view.task.get("title", "")
            if title and title not in row["units"]:
                row["units"].append(title)
    rows = sorted(found.values(), key=lambda r: (-r["count"], r["name"]))
    for row in rows:
        row["units"] = row["units"][:_HOT_UNITS]
    return rows


def _entangled(graph_summary, views) -> dict:
    """Where the dependency weight sits, for one module at a time.

    A session holds one form, so "the forms with the highest dependency
    complexity" is answered here at the level the data supports: the objects
    inside this form that the most other things lean on.
    """
    if not graph_summary:
        return {"available": False, "reason": "no dependency graph for this session"}
    risky = {
        v.task["id"]: ((v.analysis or {}).get("risk") or {}).get("level", "")
        for v in views
    }
    hubs = []
    for hub in graph_summary.get("hubs", []):
        hubs.append({**hub, "degree": hub.get("in", 0) + hub.get("out", 0)})
    return {
        "available": True,
        "module": graph_summary.get("module", ""),
        "nodes": graph_summary.get("nodes", 0),
        "edges": graph_summary.get("edges", 0),
        "external": graph_summary.get("external", 0),
        "missing": graph_summary.get("missing", 0),
        "unresolved": graph_summary.get("unresolved", 0),
        "by_kind": graph_summary.get("by_kind", {}),
        "hubs": hubs,
        "risk_by_task": {k: v for k, v in risky.items() if v},
    }


def build(store, graph=None) -> dict:
    """The whole dashboard, from the session as it stands right now."""
    views = store.all_views()
    analyses = store.all_analyses()
    summary = summarize(analyses)
    coverage = store.analysis_coverage()
    test_coverage = store.test_coverage()
    cases = store.all_test_cases()
    graph_summary = graph.summary() if graph is not None else None

    total = len(views)
    decisions = {state: 0 for state in STATES}
    modes = {verdict: 0 for verdict in rules.VERDICT_ORDER}
    for view in views:
        decisions[view.state] = decisions.get(view.state, 0) + 1
        verdict = view.task.get("verdict") or rules.UNKNOWN
        modes[verdict] = modes.get(verdict, 0) + 1

    proposed = sum(1 for v in views if v.proposal)
    reviewed = total - decisions.get(PENDING, 0)
    return {
        "session": store.session(),
        "totals": {
            "units": total,
            "proposed": proposed,
            "unproposed": total - proposed,
            "lines": sum(v.task.get("lines", 0) for v in views),
        },
        "conversion_modes": modes,
        "decisions": decisions,
        "percent": {
            # Rounded for display only; the raw counts are right above.
            "reviewed": round(100 * reviewed / total, 1) if total else 0.0,
            "approved": round(100 * decisions.get(APPROVED, 0) / total, 1) if total else 0.0,
            "proposed": round(100 * proposed / total, 1) if total else 0.0,
        },
        "risk": summary.get("risk", {}),
        "behavior": summary.get("behavior", {}),
        "avg_risk_score": summary.get("avg_score", 0.0),
        "migration_classes": summary.get("migration_classes", {}),
        "categories": summary.get("categories", {}),
        "coverage": coverage,
        "test_coverage": test_coverage,
        "readiness": readiness(views, cases),
        "readiness_model": explain(),
        "highest_risk": _riskiest(views),
        "unsupported": _unsupported_units(views),
        "dependencies": _entangled(graph_summary, views),
        "blockers": _blockers(views, summary, coverage, test_coverage, graph_summary),
    }
