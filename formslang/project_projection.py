"""Bounded, deterministic read models over one persisted project assessment."""

from __future__ import annotations

import copy
import hashlib
import json
import math
from collections import Counter, OrderedDict, defaultdict
from dataclasses import dataclass, field
from pathlib import PurePosixPath, PureWindowsPath
from threading import RLock

from .hotspots import HOTSPOT_SEVERITIES, HOTSPOT_TYPES, detect_estate_hotspots, signal_codes
from .project_model import ProjectError, RevisionConflict

RISK_LEVELS = ("CRITICAL", "HIGH", "MEDIUM", "LOW", "UNKNOWN")
RECOMMENDATIONS = (
    "PRESERVE",
    "CONVERT",
    "REFACTOR",
    "MOVE_TO_PLSQL_API",
    "REPLACE_WITH_APEX_NATIVE",
    "MANUAL_REVIEW",
    "DROP",
    "UNKNOWN",
)
INTERVENTIONS = ("AUTO", "ASSISTED", "MANUAL", "UNKNOWN")
LIBRARY_SUFFIXES = {".pll", ".mmb", ".olb"}
FORM_SUFFIXES = {".xml", ".fmb", ".pll", ".mmb", ".olb"}
ROUTINE_TYPES = {"PACKAGE_SUBPROGRAM", "SUBPROGRAM_BODY", "PROGRAM_UNIT"}
RESOLVED_REVIEWS = {"APPROVE", "MODIFY"}
RISK_RANK = {value: index for index, value in enumerate(RISK_LEVELS)}
BASE_SEVERITY = {
    "CRITICAL": 100.0,
    "HIGH": 50.0,
    "MEDIUM": 20.0,
    "LOW": 5.0,
    "UNKNOWN": 1.0,
}
CATEGORIES = (
    "forms",
    "libraries",
    "packages",
    "routines",
    "views",
    "tables",
    "dependencies",
    "business_rules",
    "findings",
    "hotspots",
)
SORTS = {"name", "risk", "recommendation", "intervention", "module", "type", "priority"}
MAX_OVERVIEW_WARNINGS = 50
MAX_OVERVIEW_HOTSPOTS = 20


@dataclass(frozen=True)
class ProjectionKey:
    store_scope: str
    project_id: str
    analysis_revision: str
    review_revision: int
    target: tuple[str, str, str]
    freshness: str


@dataclass(frozen=True)
class PreparedProjection:
    key: ProjectionKey
    descriptor: dict
    assessment_meta: dict
    overview_data: dict
    rows: dict[str, tuple[dict, ...]]
    details: dict[tuple[str, str], dict]
    raw_blueprint: dict = field(default_factory=dict)


class ProjectionCache:
    """Small process-local LRU; the assessment/store remain authoritative."""

    def __init__(self, max_entries: int = 8):
        if type(max_entries) is not int or max_entries < 1:
            raise ValueError("Projection cache size must be positive")
        self.max_entries = max_entries
        self._lock = RLock()
        self._values = OrderedDict()

    def get_or_build(self, key: ProjectionKey, factory) -> PreparedProjection:
        with self._lock:
            cached = self._values.get(key)
            if cached is not None:
                self._values.move_to_end(key)
                return cached
        built = factory()
        if not isinstance(built, PreparedProjection) or built.key != key:
            raise ProjectError("Projection cache factory returned a different revision")
        with self._lock:
            cached = self._values.get(key)
            if cached is not None:
                self._values.move_to_end(key)
                return cached
            self._values[key] = built
            while len(self._values) > self.max_entries:
                self._values.popitem(last=False)
            return built

    def clear_project(self, store_scope: str, project_id: str) -> None:
        with self._lock:
            for key in tuple(self._values):
                if key.store_scope == store_scope and key.project_id == project_id:
                    self._values.pop(key)


def _bucket(value, allowed):
    normalized = value.strip().upper() if isinstance(value, str) else ""
    return normalized if normalized in allowed else "UNKNOWN"


def _logical_name(value) -> str:
    if not isinstance(value, str) or "\0" in value:
        return ""
    normalized = value.replace("\\", "/")
    posix = PurePosixPath(normalized)
    windows = PureWindowsPath(value)
    if posix.is_absolute() or windows.drive or any(part == ".." for part in posix.parts):
        return ""
    return normalized[:1000]


def _text(value, limit=1000) -> str:
    return value[:limit] if isinstance(value, str) else ""


def _target(descriptor, assessment):
    target = assessment.get("target", {}) if isinstance(assessment.get("target"), dict) else {}
    return {
        "platform": _text(target.get("platform") or descriptor.get("target_platform")),
        "version": _text(target.get("version") or descriptor.get("target_version")),
        "representation": _text(
            target.get("representation") or descriptor.get("target_representation")
        ),
    }


def projection_key(descriptor, assessment, freshness, *, store_scope):
    target = _target(descriptor, assessment)
    review_revision = assessment.get("review_revision", 0)
    review_revision = (
        review_revision if type(review_revision) is int and review_revision >= 0 else 0
    )
    return ProjectionKey(
        store_scope=_text(store_scope, 2000),
        project_id=_text(assessment.get("project_id") or descriptor.get("id"), 64),
        analysis_revision=_text(assessment.get("analysis_revision"), 64),
        review_revision=review_revision,
        target=(target["platform"], target["version"], target["representation"]),
        freshness=_bucket_freshness(
            freshness.get("status") if isinstance(freshness, dict) else None
        ),
    )


def _unique(values):
    result = {}
    for value in values if isinstance(values, list) else []:
        if isinstance(value, dict) and isinstance(value.get("id"), str):
            result.setdefault(value["id"], value)
    return result


def _safe_entity(node, findings_by_entity, dependency_count):
    identity = node["id"]
    attributes = node.get("attributes") if isinstance(node.get("attributes"), dict) else {}
    related = findings_by_entity.get(identity, ())
    risks = [_bucket(item.get("risk"), RISK_LEVELS) for item in related]
    rank = {level: index for index, level in enumerate(RISK_LEVELS)}
    highest = min(risks, key=lambda value: rank[value]) if risks else "UNKNOWN"
    return {
        "id": identity,
        "name": _text(node.get("name"), 500),
        "type": _text(node.get("type"), 100),
        "module": _logical_name(node.get("module")),
        "source_status": "ANALYZED",
        "dependencies": dependency_count,
        "findings": len(related),
        "highest_risk": highest,
        "columns": len(attributes.get("columns", ()))
        if isinstance(attributes.get("columns"), list)
        else None,
        "constraints": len(attributes.get("constraints", ()))
        if isinstance(attributes.get("constraints"), list)
        else None,
    }


def _finding_rows(findings, entities, centrality, evidence_by_entity, fan_in=None,
                  hotspots_by_finding=None):
    rows = []
    fan_in = fan_in or {}
    hotspots_by_finding = hotspots_by_finding or {}
    for item in sorted(findings.values(), key=lambda value: value["id"]):
        entity = entities.get(item.get("entity"), {})
        attributes = (
            entity.get("attributes") if isinstance(entity.get("attributes"), dict) else {}
        )
        risk = attributes.get("risk") if isinstance(attributes.get("risk"), dict) else {}
        # The engine's structural signal codes are the only evidence read here.
        codes = signal_codes(item)
        evidence_factors = set(evidence_by_entity.get(item.get("entity"), ()))
        if "DIRECT_DML_BYPASSES_API" in codes:
            evidence_factors.add("API_BYPASS")
        if any(code.startswith("LOGIC_DUPLICATED_") for code in codes):
            evidence_factors.add("DUPLICATED_LOGIC")

        risk_level = _bucket(risk.get("level"), RISK_LEVELS)
        base = BASE_SEVERITY.get(risk_level, 1.0)
        eid = item.get("entity")
        fan_in_count = fan_in.get(eid, 0)
        fan_in_multiplier = 0.2 * math.log2(1.0 + fan_in_count)
        is_bypass = "API_BYPASS" in evidence_factors
        bypass_multiplier = 0.3 if is_bypass else 0.0
        # Both signals name an existing database subprogram the unit does not call.
        has_existing_api = is_bypass or "DUPLICATED_LOGIC" in evidence_factors
        api_multiplier = 0.25 if has_existing_api else 0.0
        priority_score = round(
            base * (1.0 + fan_in_multiplier + bypass_multiplier + api_multiplier), 1
        )

        breakdown = [f"Measured risk: {risk_level} (base {int(base)})"]
        if fan_in_count > 0:
            breakdown.append(
                f"Referenced by {fan_in_count} relationship(s) (+{fan_in_multiplier:.2f}x)"
            )
        if is_bypass:
            breakdown.append("Engine signal: possible API bypass (+0.30x)")
        if has_existing_api:
            breakdown.append("Existing database subprogram named by the signal (+0.25x)")
        breakdown.append(f"Priority score: {priority_score}")

        rows.append(
            {
                "id": item["id"],
                "entity_id": _text(item.get("entity"), 500),
                "name": _text(entity.get("name") or item.get("id"), 500),
                "module": _logical_name(entity.get("module")),
                "source_type": _text(entity.get("type"), 100),
                "risk": risk_level,
                "recommendation": _bucket(item.get("recommendation"), RECOMMENDATIONS),
                "intervention": _bucket(item.get("execution_verdict"), INTERVENTIONS),
                "review_state": _bucket_review(item.get("review_state")),
                "reason": _text(item.get("reason"), 2000),
                "classification": tuple(
                    sorted(
                        _text(value, 100)
                        for value in item.get("classification", [])
                        if isinstance(value, str)
                    )
                ),
                "evidence_factors": tuple(sorted(evidence_factors)),
                "signals": tuple(sorted(codes)),
                "hotspot_ids": tuple(hotspots_by_finding.get(item["id"], ())),
                "dependency_centrality": centrality.get(item.get("entity"), 0),
                "priority_score": priority_score,
                "priority_breakdown": tuple(breakdown),
                "fan_in": fan_in_count,
            }
        )
    return tuple(rows)


def _bucket_review(value):
    return value.strip().upper() if isinstance(value, str) and value.strip() else "PENDING"


def _priority_factors(row):
    unresolved = row["review_state"] not in RESOLVED_REVIEWS
    factors = []
    if unresolved and row["risk"] == "CRITICAL":
        factors.append("UNRESOLVED_CRITICAL")
    elif unresolved and row["risk"] == "HIGH":
        factors.append("UNRESOLVED_HIGH")
    elif unresolved:
        factors.append("UNRESOLVED_FINDING")
    if row["intervention"] == "MANUAL":
        factors.append("MANUAL_INTERVENTION")
    if row["review_state"] == "STALE":
        factors.append("STALE_DECISION")
    factors.extend(row.get("evidence_factors", ()))
    if row.get("hotspot_ids"):
        factors.append("HOTSPOT_CANDIDATE")
    if row.get("dependency_centrality", 0):
        factors.append("DEPENDENCY_CENTRALITY")
    return tuple(factors)


def _priority_key(row):
    unresolved = row["review_state"] not in RESOLVED_REVIEWS
    if unresolved and row["risk"] == "CRITICAL":
        group = 0
    elif unresolved and row["risk"] == "HIGH":
        group = 1
    elif unresolved:
        group = 2
    elif row["intervention"] == "MANUAL":
        group = 3
    elif row["review_state"] == "STALE":
        group = 4
    else:
        group = 5
    evidenced = bool(row.get("evidence_factors"))
    return (
        group,
        RISK_RANK[row["risk"]],
        -row.get("priority_score", 0.0),
        row["intervention"] != "MANUAL",
        row["review_state"] != "STALE",
        not evidenced,
        -row.get("dependency_centrality", 0),
        row["id"],
    )


def _package_rows(entities, findings_by_entity, edges):
    packages = {}
    for node in entities.values():
        if node.get("type") not in {"PACKAGE", "PACKAGE_SPEC", "PACKAGE_BODY"}:
            continue
        module = _logical_name(node.get("module"))
        root_scope = module.split("/", 1)[0].casefold() if "/" in module else ""
        name = _text(node.get("name"), 500)
        key = (root_scope, name.casefold())
        row = packages.setdefault(
            key,
            {
                "id": f"package:{root_scope}:{name.casefold()}",
                "name": name,
                "type": "PACKAGE",
                "module": root_scope,
                "spec": False,
                "body": False,
                "entity_ids": [],
                "_member_ids": [],
                "subprograms": 0,
                "findings": 0,
                "highest_risk": "UNKNOWN",
                "source_status": "ANALYZED",
            },
        )
        row["spec"] |= node.get("type") == "PACKAGE_SPEC"
        row["body"] |= node.get("type") == "PACKAGE_BODY"
        row["entity_ids"].append(node["id"])
        row["_member_ids"].append(node["id"])
    routine_counts = Counter()
    for node in entities.values():
        if node.get("type") in ROUTINE_TYPES:
            attributes = (
                node.get("attributes") if isinstance(node.get("attributes"), dict) else {}
            )
            package = _text(attributes.get("package"), 500)
            module = _logical_name(node.get("module"))
            root_scope = module.split("/", 1)[0].casefold() if "/" in module else ""
            key = (root_scope, package.casefold())
            routine_counts[key] += 1
            if key in packages:
                packages[key]["_member_ids"].append(node["id"])
    for key, row in packages.items():
        row["entity_ids"] = tuple(sorted(row["entity_ids"]))
        row["_member_ids"] = tuple(sorted(row["_member_ids"]))
        row["subprograms"] = routine_counts[key]
        related = [
            finding
            for entity_id in row["_member_ids"]
            for finding in findings_by_entity.get(entity_id, ())
        ]
        row["findings"] = len(related)
        risks = [finding["risk"] for finding in related]
        row["highest_risk"] = min(risks, key=RISK_RANK.__getitem__) if risks else "UNKNOWN"
        row["dependencies"] = sum(
            edge.get("source") in row["_member_ids"]
            or edge.get("target") in row["_member_ids"]
            for edge in edges
        )
    return tuple(
        sorted(packages.values(), key=lambda row: (row["name"].casefold(), row["id"]))
    )


def _manifest_rows(assessment):
    entries = assessment.get("source_manifest")
    libraries = []
    form_representations = 0
    database_sources = 0
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict):
            continue
        path = _logical_name(entry.get("relative_path"))
        suffix = PurePosixPath(path).suffix.casefold()
        if suffix in FORM_SUFFIXES and entry.get("selected") is True:
            form_representations += 1
        if entry.get("representation") == "database" and entry.get("selected") is True:
            database_sources += 1
        if suffix in LIBRARY_SUFFIXES:
            libraries.append(
                {
                    "id": _text(entry.get("source_id"), 500),
                    "name": PurePosixPath(path).name,
                    "type": suffix.removeprefix(".").upper(),
                    "module": path,
                    "representation": _text(entry.get("representation"), 100),
                    "selected": entry.get("selected") is True,
                    "source_status": _text(entry.get("status"), 100).upper() or "UNKNOWN",
                    "semantic_support": "AVAILABLE"
                    if entry.get("selected") is True
                    else "UNREPRESENTED",
                }
            )
    libraries.sort(key=lambda row: (row["name"].casefold(), row["id"]))
    return tuple(libraries), form_representations, database_sources


def _warnings(assessment, freshness):
    warnings = []
    seen = set()
    diagnostics = assessment.get("diagnostics")
    for item in diagnostics if isinstance(diagnostics, list) else []:
        if not isinstance(item, dict):
            continue
        code = _text(item.get("error_code"), 100) or "SOURCE_WARNING"
        key = (code, _text(item.get("source_id"), 500))
        if key in seen:
            continue
        seen.add(key)
        warnings.append(
            {
                "code": code,
                "severity": "WARNING",
                "message": _text(item.get("safe_message"), 1000),
                "remediation": _text(item.get("remediation"), 1000),
                "source_id": _text(item.get("source_id"), 500),
                "target": "inventory",
            }
        )
    state = _bucket_freshness(freshness.get("status") if isinstance(freshness, dict) else None)
    if state != "CURRENT":
        warnings.insert(
            0,
            {
                "code": f"ASSESSMENT_{state}",
                "severity": "WARNING",
                "message": "Saved assessment source state requires attention.",
                "remediation": "Refresh source status or continue viewing the saved assessment.",
                "source_id": "",
                "target": "overview",
            },
        )
    total = len(warnings)
    bounded = warnings[:MAX_OVERVIEW_WARNINGS]
    return bounded, {
        "total": total,
        "shown": len(bounded),
        "truncated": total > len(bounded),
    }


def _bucket_freshness(value):
    allowed = {"CURRENT", "STALE", "INCOMPLETE", "MISSING_SOURCE", "UNVERIFIED"}
    normalized = value.strip().upper() if isinstance(value, str) else "UNVERIFIED"
    return normalized if normalized in allowed else "UNVERIFIED"


def prepare_projection(
    descriptor: dict, assessment: dict, freshness: dict, *, store_scope: str
) -> PreparedProjection:
    """Prepare safe rows once; no source parsing or analysis is performed here."""
    entities = _unique(assessment.get("blueprint", {}).get("entities", []))
    findings = _unique(assessment.get("blueprint", {}).get("findings", []))
    raw_edges = _unique(assessment.get("blueprint", {}).get("edges", []))
    edges = tuple(
        sorted(
            (edge for edge in raw_edges.values() if edge.get("type") != "CONTAINS"),
            key=lambda edge: edge["id"],
        )
    )
    centrality = Counter()
    fan_in = Counter()
    dependency_counts = Counter()
    evidence_by_entity = defaultdict(set)
    for edge in edges:
        source = edge.get("source")
        target = edge.get("target")
        centrality[source] += 1
        centrality[target] += 1
        if target:
            fan_in[target] += 1
        for endpoint in {source, target}:
            dependency_counts[endpoint] += 1
        source_module = _logical_name(entities.get(source, {}).get("module"))
        target_module = _logical_name(entities.get(target, {}).get("module"))
        if source_module and target_module and source_module != target_module:
            evidence_by_entity[source].add("CROSS_MODULE_IMPACT")
            evidence_by_entity[target].add("CROSS_MODULE_IMPACT")
    blueprint = (
        assessment.get("blueprint", {})
        if isinstance(assessment.get("blueprint"), dict)
        else {}
    )
    hotspot_results = detect_estate_hotspots(blueprint)
    hotspots_by_finding = defaultdict(list)
    for hotspot in hotspot_results["hotspots"]:
        for finding_id in hotspot["finding_ids"]:
            hotspots_by_finding[finding_id].append(hotspot["id"])
    finding_rows = _finding_rows(
        findings, entities, centrality, evidence_by_entity, fan_in, hotspots_by_finding
    )
    finding_rows = tuple(
        {**row, "priority_factors": _priority_factors(row)} for row in finding_rows
    )
    findings_by_entity = defaultdict(list)
    for row in finding_rows:
        findings_by_entity[row["entity_id"]].append(row)
    entity_rows = {
        identity: _safe_entity(node, findings_by_entity, dependency_counts[identity])
        for identity, node in entities.items()
    }
    forms = tuple(
        sorted(
            (
                row
                for identity, row in entity_rows.items()
                if entities[identity].get("type") == "FORM"
            ),
            key=lambda row: (row["name"].casefold(), row["id"]),
        )
    )
    routines = tuple(
        sorted(
            (
                row
                for identity, row in entity_rows.items()
                if entities[identity].get("type") in ROUTINE_TYPES
            ),
            key=lambda row: (row["name"].casefold(), row["id"]),
        )
    )
    views = tuple(
        sorted(
            (
                row
                for identity, row in entity_rows.items()
                if entities[identity].get("type") == "VIEW"
            ),
            key=lambda row: (row["name"].casefold(), row["id"]),
        )
    )
    tables = tuple(
        sorted(
            (
                row
                for identity, row in entity_rows.items()
                if entities[identity].get("type") == "TABLE"
            ),
            key=lambda row: (row["name"].casefold(), row["id"]),
        )
    )
    libraries, form_representations, database_sources = _manifest_rows(assessment)
    packages = _package_rows(entities, findings_by_entity, edges)
    dependency_rows = tuple(
        {
            "id": edge["id"],
            "source_id": _text(edge.get("source"), 500),
            "source": _text(entities.get(edge.get("source"), {}).get("name"), 500),
            "target_id": _text(edge.get("target"), 500),
            "target": _text(entities.get(edge.get("target"), {}).get("name"), 500),
            "relationship": _text(edge.get("type"), 100),
        }
        for edge in edges
    )
    business_rules = tuple(
        {**row, "candidate_kind": "Observed business rule candidate"}
        for row in finding_rows
        if "BUSINESS_RULE" in row["classification"]
    )
    hotspot_rows = tuple(
        {
            **copy.deepcopy(h),
            "name": h["title"],
            "source_type": h["label"],
            "entity_ids": tuple(h["affected_entities"]),
            "_member_ids": tuple(h["affected_entities"]),
        }
        for h in hotspot_results["hotspots"]
    )
    rows = {
        "forms": forms,
        "libraries": libraries,
        "packages": packages,
        "routines": routines,
        "views": views,
        "tables": tables,
        "dependencies": dependency_rows,
        "business_rules": business_rules,
        "findings": finding_rows,
        "hotspots": hotspot_rows,
    }
    inventory = (
        assessment.get("inventory") if isinstance(assessment.get("inventory"), dict) else {}
    )
    inventory_forms = (
        inventory.get("forms") if isinstance(inventory.get("forms"), dict) else {}
    )
    inventory_db = (
        inventory.get("database") if isinstance(inventory.get("database"), dict) else {}
    )
    target = _target(descriptor, assessment)
    freshness_state = _bucket_freshness(
        freshness.get("status") if isinstance(freshness, dict) else None
    )
    analysis_revision = _text(assessment.get("analysis_revision"), 64)
    review_revision = assessment.get("review_revision", 0)
    review_revision = (
        review_revision if type(review_revision) is int and review_revision >= 0 else 0
    )
    key = projection_key(descriptor, assessment, freshness, store_scope=store_scope)
    risk_counts = Counter(row["risk"] for row in finding_rows)
    recommendation_counts = Counter(row["recommendation"] for row in finding_rows)
    intervention_counts = Counter(row["intervention"] for row in finding_rows)
    distributions = {
        "risk_distribution": {value: risk_counts[value] for value in RISK_LEVELS},
        "recommendation_distribution": {
            value: recommendation_counts[value] for value in RECOMMENDATIONS
        },
        "intervention_distribution": {
            value: intervention_counts[value] for value in INTERVENTIONS
        },
    }
    total = len(finding_rows)
    automation = {
        value: {
            "count": distributions["intervention_distribution"][value],
            "percent": round(
                distributions["intervention_distribution"][value] * 100 / total, 1
            )
            if total
            else 0.0,
        }
        for value in INTERVENTIONS
    }
    warning_rows, warning_summary = _warnings(assessment, freshness)
    overview_data = {
        "project": {
            "id": _text(descriptor.get("id"), 64),
            "name": _text(descriptor.get("name"), 200),
            "description": _text(descriptor.get("description"), 4000),
            "client_label": _text(descriptor.get("client_label"), 200),
            "target": target,
        },
        "assessment": {
            "status": _text(assessment.get("status"), 100),
            "completion_state": _text(assessment.get("completion_state"), 100),
            "analysis_revision": analysis_revision,
            "source_revision": _text(assessment.get("source_revision"), 64),
            "review_revision": review_revision,
            "assessment_timestamp": _text(assessment.get("analyzed_at"), 100),
            "freshness": freshness_state,
        },
        "inventory": {
            "forms_modules": len(forms),
            "forms_representations": form_representations,
            "libraries": len(libraries),
            "database_packages": len(packages),
            "package_specs": sum(row["spec"] for row in packages),
            "package_bodies": sum(row["body"] for row in packages),
            "views": len(views),
            "tables": len(tables),
            "triggers": sum(node.get("type") == "TRIGGER" for node in entities.values()),
            "program_units": len(routines),
            "dependencies": len(dependency_rows),
            "business_rule_candidates": len(business_rules),
            "modernization_findings": len(finding_rows),
            "architectural_hotspots": hotspot_results["total"],
        },
        **distributions,
        "automation_potential": automation,
        "priority": _priority_summary(finding_rows),
        "hotspots": {
            "total": hotspot_results["total"],
            "by_type": hotspot_results["by_type"],
            "by_severity": {
                value: sum(h["severity"] == value for h in hotspot_results["hotspots"])
                for value in HOTSPOT_SEVERITIES
            },
            "types": list(HOTSPOT_TYPES),
            "classification": "CANDIDATE",
            "items": [
                _hotspot_summary(h)
                for h in hotspot_results["hotspots"][:MAX_OVERVIEW_HOTSPOTS]
            ],
            "shown": min(hotspot_results["total"], MAX_OVERVIEW_HOTSPOTS),
        },
        "source_coverage": {
            "forms": {
                "discovered": inventory_forms.get("discovered"),
                "parseable": inventory_forms.get("parseable"),
                "analyzed": inventory_forms.get("analyzed"),
                "representations": form_representations,
            },
            "database": {
                "sources": database_sources,
                "analyzed": inventory_db.get("analyzed"),
            },
            "libraries": {
                "discovered": len(libraries),
                "without_semantic_representation": sum(
                    row.get("semantic_support") == "UNREPRESENTED" for row in libraries
                ),
            },
        },
        "warnings": warning_rows,
        "warning_summary": warning_summary,
        "review_progress": {
            "total": total,
            "reviewed": sum(
                row["review_state"] in {"APPROVE", "MODIFY"} for row in finding_rows
            ),
            "critical_total": sum(row["risk"] == "CRITICAL" for row in finding_rows),
            "critical_resolved": sum(
                row["risk"] == "CRITICAL" and row["review_state"] in RESOLVED_REVIEWS
                for row in finding_rows
            ),
            "manual_total": sum(row["intervention"] == "MANUAL" for row in finding_rows),
            "manual_resolved": sum(
                row["intervention"] == "MANUAL" and row["review_state"] in RESOLVED_REVIEWS
                for row in finding_rows
            ),
        },
        "analysis_metadata": {
            "engine_identity": dict(assessment.get("engine_identity", {}))
            if isinstance(assessment.get("engine_identity"), dict)
            else {},
        },
    }
    return PreparedProjection(
        key,
        dict(descriptor),
        overview_data["assessment"],
        overview_data,
        rows,
        {},
        raw_blueprint=blueprint,
    )


def _hotspot_summary(hotspot):
    """The bounded Overview card: what, where, why, and where the evidence is."""
    return {
        "id": hotspot["id"],
        "hotspot_type": hotspot["hotspot_type"],
        "label": hotspot["label"],
        "classification": hotspot["classification"],
        "severity": hotspot["severity"],
        "title": hotspot["title"],
        "statement": hotspot["statement"],
        "module": _logical_name(hotspot["module"]),
        "finding_ids": list(hotspot["finding_ids"][:10]),
        "evidence_count": len(hotspot["evidence_refs"]) + len(hotspot["edge_refs"]),
        "uncertainty": list(hotspot["uncertainty"][:3]),
        "recommended_action": hotspot["recommended_action"],
    }


def overview(prepared: PreparedProjection) -> dict:
    """Return a fresh bounded overview dictionary safe for adapter serialization."""
    result = {}
    for key, value in prepared.overview_data.items():
        if isinstance(value, dict):
            result[key] = {
                child: dict(item) if isinstance(item, dict) else item
                for child, item in value.items()
            }
        elif isinstance(value, list):
            result[key] = [dict(item) for item in value]
        else:
            result[key] = value
    return result


def _priority_summary(finding_rows):
    unresolved = [row for row in finding_rows if row["review_state"] not in RESOLVED_REVIEWS]
    ordered = sorted(unresolved, key=_priority_key)
    return {
        "critical": sum(row["risk"] == "CRITICAL" for row in unresolved),
        "high": sum(row["risk"] == "HIGH" for row in unresolved),
        "manual": sum(row["intervention"] == "MANUAL" for row in unresolved),
        "stale": sum(row["review_state"] == "STALE" for row in unresolved),
        "total": len(unresolved),
        "first_finding_id": ordered[0]["id"] if ordered else None,
        "highest_score": ordered[0].get("priority_score", 0.0) if ordered else 0.0,
        "start_here": [
            {
                "id": r["id"],
                "name": r.get("name"),
                "module": r.get("module"),
                "risk": r.get("risk"),
                "score": r.get("priority_score", 0.0),
                "factors": r.get("priority_factors", ()),
                "breakdown": r.get("priority_breakdown", ()),
                "signals": r.get("signals", ()),
                "hotspot_ids": r.get("hotspot_ids", ()),
                "review_state": r.get("review_state"),
            }
            for r in ordered[:5]
        ],
    }


def _validate_page(category, offset, limit, expected_revision, prepared):
    if category not in CATEGORIES:
        raise ProjectError("Unknown inventory category")
    if (
        type(offset) is not int
        or type(limit) is not int
        or offset < 0
        or not 1 <= limit <= 200
    ):
        raise ProjectError("Use a nonnegative offset and limit between 1 and 200")
    if expected_revision is not None and expected_revision != prepared.key.analysis_revision:
        raise RevisionConflict("Assessment changed; reload inventory from the first page")


def _filtered(rows, *, query, filters):
    if not isinstance(query, str) or len(query) > 500:
        raise ProjectError("Inventory search must be bounded text")
    if filters is None:
        filters = {}
    if not isinstance(filters, dict) or set(filters) - {
        "risk",
        "recommendation",
        "intervention",
        "module",
        "source_type",
        "review",
        "priority",
    }:
        raise ProjectError("Unknown inventory filter")
    if any(not isinstance(value, str) or len(value) > 500 for value in filters.values()):
        raise ProjectError("Inventory filters must be bounded text")
    if "risk" in filters and filters["risk"] not in RISK_LEVELS:
        raise ProjectError("Unknown risk filter")
    if "recommendation" in filters and filters["recommendation"] not in RECOMMENDATIONS:
        raise ProjectError("Unknown recommendation filter")
    if "intervention" in filters and filters["intervention"] not in INTERVENTIONS:
        raise ProjectError("Unknown intervention filter")
    if "priority" in filters and filters["priority"] != "unresolved":
        raise ProjectError("Unknown priority filter")
    needle = query.casefold().strip()
    result = []
    for row in rows:
        searchable = " ".join(
            _text(row.get(field), 2000)
            for field in (
                "name",
                "module",
                "reason",
                "source",
                "target",
                "relationship",
            )
        ).casefold()
        if needle and needle not in searchable:
            continue
        if filters.get("risk") and row.get("risk", row.get("highest_risk")) != filters["risk"]:
            continue
        if (
            filters.get("recommendation")
            and row.get("recommendation") != filters["recommendation"]
        ):
            continue
        if filters.get("intervention") and row.get("intervention") != filters["intervention"]:
            continue
        if (
            filters.get("module")
            and filters["module"].casefold() not in _text(row.get("module")).casefold()
        ):
            continue
        if (
            filters.get("source_type")
            and row.get("source_type", row.get("type")) != filters["source_type"]
        ):
            continue
        if filters.get("review") and row.get("review_state") != filters["review"]:
            continue
        if (
            filters.get("priority") == "unresolved"
            and row.get("review_state") in RESOLVED_REVIEWS
        ):
            continue
        result.append(row)
    return result, dict(filters)


def _sort_rows(rows, sort, *, priority=False):
    if sort not in SORTS:
        raise ProjectError("Unknown inventory sort")
    if priority or sort == "priority":
        return sorted(rows, key=_priority_key)
    if sort == "risk":
        return sorted(
            rows,
            key=lambda row: (
                RISK_RANK.get(row.get("risk", row.get("highest_risk", "UNKNOWN")), 4),
                row["id"],
            ),
        )
    field = {"type": "source_type"}.get(sort, sort)
    return sorted(
        rows,
        key=lambda row: (
            _text(row.get(field, row.get("type"))).casefold(),
            row["id"],
        ),
    )


def _page_meta(prepared):
    return {
        "analysis_revision": prepared.key.analysis_revision,
        "source_revision": prepared.assessment_meta.get("source_revision", ""),
        "review_revision": prepared.key.review_revision,
        "assessment_timestamp": prepared.assessment_meta.get("assessment_timestamp", ""),
        "freshness": prepared.key.freshness,
    }


def _public_row(row):
    return copy.deepcopy(
        {
            key: value
            for key, value in row.items()
            if not key.startswith("_") and key != "entity_ids"
        }
    )


def inventory_page(
    prepared: PreparedProjection,
    category: str,
    *,
    query: str = "",
    filters: dict | None = None,
    sort: str = "name",
    offset: int = 0,
    limit: int = 50,
    expected_revision: str | None = None,
) -> dict:
    """Return one stable, filtered inventory page for a single assessment revision."""
    _validate_page(category, offset, limit, expected_revision, prepared)
    values, applied = _filtered(prepared.rows[category], query=query, filters=filters)
    values = _sort_rows(values, sort, priority=applied.get("priority") == "unresolved")
    return {
        "category": category,
        "query": query,
        "filters": applied,
        "sort": "priority" if applied.get("priority") == "unresolved" else sort,
        "offset": offset,
        "limit": limit,
        "total": len(values),
        "rows": [_public_row(row) for row in values[offset : offset + limit]],
        **_page_meta(prepared),
    }


def inventory_detail(
    prepared: PreparedProjection,
    category: str,
    item_id: str,
    *,
    expected_revision: str | None = None,
) -> dict:
    """Return bounded technical context without source bodies or filesystem authority."""
    _validate_page(category, 0, 50, expected_revision, prepared)
    if not isinstance(item_id, str) or len(item_id) > 500:
        raise LookupError(item_id)
    item = next((row for row in prepared.rows[category] if row["id"] == item_id), None)
    if item is None:
        raise LookupError(item_id)
    entity_ids = set(item.get("_member_ids", item.get("entity_ids", ()))) | {
        item.get("id"),
        item.get("entity_id"),
    }
    entity_ids.discard(None)
    dependencies = [
        row
        for row in prepared.rows["dependencies"]
        if row.get("source_id") in entity_ids or row.get("target_id") in entity_ids
    ]
    related = [
        row
        for row in prepared.rows["findings"]
        if row.get("entity_id") in entity_ids or row.get("id") == item_id
    ]
    return {
        "category": category,
        "item": _public_row(item),
        "dependencies": copy.deepcopy(dependencies[:100]),
        "dependencies_total": len(dependencies),
        "related_findings": copy.deepcopy(related[:100]),
        "related_findings_total": len(related),
        **_page_meta(prepared),
    }


MAP_MODE = "MODULE_ARCHITECTURE"
MAP_LAYERS = ("FORM", "DATABASE", "GLOBAL", "LIBRARY", "INTEGRATION", "UNRESOLVED", "OTHER")
MAP_RELATIONSHIPS = (
    "CALLS", "READS", "WRITES", "OPENS_FORM", "SHARES_STATE", "DUPLICATES_LOGIC", "REFERENCES",
)
MAP_MAX_DEPTH = 5
MAP_MAX_NODES = 200
MAP_MAX_EDGES = 400
MAP_DEFAULT_EDGES = 200
MAP_MAX_SELECTOR = 200
MAP_MAX_SAMPLES = 5
# Structure and runtime plumbing, not architectural dependencies between modules.
MAP_SKIPPED_RELATIONSHIPS = frozenset({"CONTAINS", "DECLARES", "IMPLEMENTS"})
MAP_SKIPPED_TYPES = frozenset({"APPLICATION", "BUILTIN"})
_PACKAGE_MEMBERS = frozenset({"SUBPROGRAM_BODY", "PACKAGE_SUBPROGRAM", "CONSTANT_DECLARATION"})
_OWN_NODE_TYPES = frozenset({
    "FORM", "FORM_REFERENCE", "TABLE", "VIEW", "SEQUENCE_REFERENCE", "GLOBAL_REFERENCE",
    "LIBRARY", "LIBRARY_REFERENCE", "MENU", "MENU_REFERENCE", "INTEGRATION_POINT",
    "TABLE_OR_VIEW_REFERENCE", "ROUTINE_REFERENCE", "PACKAGE_REFERENCE",
    "DATABASE_OBJECT_REFERENCE",
})
MAX_SEARCH_QUERY = 200
MAX_SEARCH_LIMIT = 50


def _map_layer(entity_type: str) -> str:
    """Architecture layer of one map node; an unknown type is never promoted to a service."""
    et = (entity_type or "").upper()
    if et in {"FORM", "FORM_REFERENCE"}:
        return "FORM"
    if et in {"PACKAGE", "PACKAGE_SPEC", "PACKAGE_BODY", "SUBPROGRAM_BODY",
              "PACKAGE_SUBPROGRAM", "TABLE", "VIEW", "SEQUENCE_REFERENCE"}:
        return "DATABASE"
    if et == "GLOBAL_REFERENCE":
        return "GLOBAL"
    if et in {"LIBRARY", "LIBRARY_REFERENCE", "MENU", "MENU_REFERENCE"}:
        return "LIBRARY"
    if et == "INTEGRATION_POINT":
        return "INTEGRATION"
    if et in {"TABLE_OR_VIEW_REFERENCE", "ROUTINE_REFERENCE", "PACKAGE_REFERENCE",
              "DATABASE_OBJECT_REFERENCE"}:
        return "UNRESOLVED"
    return "OTHER"


def _map_relationship(edge_type: str, target_layer: str) -> str:
    et = (edge_type or "").upper()
    if et in {"CALLS", "USES_PROGRAM_UNIT"}:
        return "CALLS"
    if et == "READS":
        return "READS"
    if et == "WRITES":
        return "WRITES"
    if et in {"OPENS_FORM", "NAVIGATES_TO"}:
        return "OPENS_FORM"
    if et == "DUPLICATES_LOGIC":
        return "DUPLICATES_LOGIC"
    if target_layer == "GLOBAL":
        return "SHARES_STATE"
    return "REFERENCES"


def _architecture_graph(prepared: PreparedProjection) -> dict:
    """Fold the component-level Blueprint graph into module-level architecture.

    A Form node stands for the Form and every component it contains (blocks,
    items, triggers, program units, rule candidates), so a relationship that a
    trigger inside the Form has with a table becomes a relationship of the Form.
    A package node stands for its specification, body and subprograms. A
    symbolic reference that resolved to a supplied database object is drawn as
    that object; an unresolved one stays a visibly unresolved node.
    Containment itself is never drawn as a dependency.
    """
    blueprint = prepared.raw_blueprint or {}
    entities = _unique(blueprint.get("entities", []))
    raw_edges = sorted(_unique(blueprint.get("edges", [])).values(), key=lambda e: e["id"])
    form_by_module = {}
    for identity, entity in sorted(entities.items()):
        if entity.get("type") == "FORM" and entity.get("module"):
            form_by_module.setdefault(entity["module"], identity)
    packages = {}
    for identity, entity in sorted(entities.items()):
        if entity.get("type") in {"PACKAGE_SPEC", "PACKAGE_BODY"}:
            name = _text(entity.get("name"), 500).upper()
            current = packages.get(name)
            # One package node; the specification represents it when supplied.
            if current is None or (entity.get("type") == "PACKAGE_SPEC"
                                   and entities[current].get("type") != "PACKAGE_SPEC"):
                packages[name] = identity
    owners = {}

    def owner(identity, seen=()):
        if identity in owners:
            return owners[identity]
        entity = entities.get(identity)
        result = None
        if entity is not None and entity.get("type") not in MAP_SKIPPED_TYPES:
            etype = entity.get("type")
            attributes = entity.get("attributes") if isinstance(entity.get("attributes"), dict) else {}
            target = entity.get("resolved_target")
            if (entity.get("resolution") == "RESOLVED_TO_DATABASE_OBJECT"
                    and target in entities and target not in seen):
                result = owner(target, (*seen, identity))
            elif etype in {"PACKAGE_SPEC", "PACKAGE_BODY"}:
                result = packages.get(_text(entity.get("name"), 500).upper(), identity)
            elif etype in _PACKAGE_MEMBERS:
                result = packages.get(_text(attributes.get("package"), 500).upper(), identity)
            elif etype in _OWN_NODE_TYPES:
                result = identity
            else:
                result = form_by_module.get(entity.get("module"), identity)
        owners[identity] = result
        return result

    hotspots_by_edge = defaultdict(set)
    for hotspot in prepared.rows.get("hotspots", ()):
        for edge_id in hotspot.get("edge_refs", ()):
            hotspots_by_edge[edge_id].add(hotspot["id"])
    aggregated = {}
    for edge in raw_edges:
        if edge.get("type") in MAP_SKIPPED_RELATIONSHIPS:
            continue
        source, target = owner(edge.get("source")), owner(edge.get("target"))
        if source is None or target is None or source == target:
            continue
        target_layer = _map_layer(entities[target].get("type"))
        relationship = _map_relationship(edge.get("type"), target_layer)
        key = (source, target, relationship)
        row = aggregated.get(key)
        if row is None:
            row = aggregated[key] = {
                "id": "map-edge:" + digest_text(list(key)),
                "source": source, "target": target, "classification": relationship,
                "count": 0, "fact": False, "edge_ids": [], "evidence": [],
                "components": set(), "relationships": set(), "hotspot_ids": set(),
            }
        row["count"] += 1
        row["fact"] |= edge.get("level", "FACT") == "FACT"
        row["relationships"].add(_text(edge.get("type"), 100))
        row["hotspot_ids"] |= hotspots_by_edge.get(edge["id"], set())
        if len(row["edge_ids"]) < MAP_MAX_SAMPLES:
            row["edge_ids"].append(edge["id"])
        for proof in edge.get("evidence", ()) if isinstance(edge.get("evidence"), list) else ():
            if isinstance(proof, str) and len(row["evidence"]) < MAP_MAX_SAMPLES and proof not in row["evidence"]:
                row["evidence"].append(proof)
        component = entities.get(edge.get("source"), {})
        if edge.get("source") != source and len(row["components"]) < MAP_MAX_SAMPLES:
            row["components"].add(_text(component.get("name"), 200))
    nodes = {}
    for identity in sorted({owner(i) for i in entities} - {None}):
        entity = entities[identity]
        etype = entity.get("type", "UNKNOWN")
        is_package = etype in {"PACKAGE_SPEC", "PACKAGE_BODY"}
        nodes[identity] = {
            "id": identity,
            "name": _text(entity.get("name") or identity, 500),
            "type": "PACKAGE" if is_package else _text(etype, 100),
            "layer": _map_layer(etype),
            "module": _logical_name(entity.get("module")),
            "resolution": "UNRESOLVED_REFERENCE" if _map_layer(etype) == "UNRESOLVED" else "OBSERVED",
            "members": 0, "findings_count": 0, "highest_risk": "NONE", "hotspot_count": 0,
        }
    for identity in entities:
        node = owner(identity)
        if node in nodes and node != identity:
            nodes[node]["members"] += 1
    # One finding counts once, on the node its component folds into.
    for row in prepared.rows.get("findings", ()):
        node = nodes.get(owner(row.get("entity_id")))
        if node is None:
            continue
        node["findings_count"] += 1
        if node["highest_risk"] == "NONE" or RISK_RANK[row["risk"]] < RISK_RANK[node["highest_risk"]]:
            node["highest_risk"] = row["risk"]
    for hotspot in prepared.rows.get("hotspots", ()):
        for node_id in {owner(e) for e in hotspot.get("affected_entities", ())} - {None}:
            if node_id in nodes:
                nodes[node_id]["hotspot_count"] += 1
    edges = []
    for row in aggregated.values():
        edges.append({
            **{k: v for k, v in row.items() if k not in {"components", "relationships", "hotspot_ids", "fact"}},
            "source_name": nodes[row["source"]]["name"],
            "target_name": nodes[row["target"]]["name"],
            "level": "FACT" if row["fact"] else "INFERENCE",
            "components": sorted(row["components"]),
            "relationships": sorted(row["relationships"]),
            "hotspot_ids": sorted(row["hotspot_ids"]),
            "is_hotspot": bool(row["hotspot_ids"]),
        })
    edges.sort(key=lambda e: e["id"])
    return {"nodes": nodes, "edges": edges}


def digest_text(value) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def _bounded_int(value, name, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ProjectError(f"System Map {name} must be an integer between {low} and {high}")
    return value


def system_map(
    prepared: PreparedProjection,
    *,
    focus: str | None = None,
    depth: int = 2,
    layer: str | None = None,
    edge_type: str | None = None,
    limit: int = 100,
    edge_limit: int = MAP_DEFAULT_EDGES,
) -> dict:
    """Bounded module-level architecture around one focus node.

    Node, edge and selector budgets are independent server-side limits; every
    cut is reported in ``truncation`` with the counts that were available.
    """
    depth = _bounded_int(depth, "depth", 1, MAP_MAX_DEPTH)
    limit = _bounded_int(limit, "node limit", 1, MAP_MAX_NODES)
    edge_limit = _bounded_int(edge_limit, "edge limit", 1, MAP_MAX_EDGES)
    layer = layer.strip().upper() if isinstance(layer, str) and layer.strip() else None
    edge_type = edge_type.strip().upper() if isinstance(edge_type, str) and edge_type.strip() else None
    if layer is not None and layer not in MAP_LAYERS:
        raise ProjectError("Unknown System Map layer")
    if edge_type is not None and edge_type not in MAP_RELATIONSHIPS:
        raise ProjectError("Unknown System Map relationship")
    if focus is not None and (not isinstance(focus, str) or len(focus) > 500):
        raise ProjectError("System Map focus must be bounded text")
    graph = _architecture_graph(prepared)
    nodes, all_edges = graph["nodes"], graph["edges"]
    forms = sorted((n for n in nodes.values() if n["type"] == "FORM"),
                   key=lambda n: (n["name"].casefold(), n["id"]))
    focus_id = None
    if focus:
        if focus in nodes:
            focus_id = focus
        else:
            focus_id = next((n["id"] for n in forms if n["name"].casefold() == focus.casefold()), None)
        if focus_id is None:
            raise ProjectError("Unknown System Map focus; choose a Form from the selector or search")
    elif forms:
        focus_id = forms[0]["id"]
    elif nodes:
        focus_id = min(nodes)
    selector = forms[:MAP_MAX_SELECTOR]
    if focus_id and nodes.get(focus_id, {}).get("type") == "FORM" and all(f["id"] != focus_id for f in selector):
        selector = [*selector, nodes[focus_id]]
    truncation = []
    if len(forms) > MAP_MAX_SELECTOR:
        truncation.append({"reason": "SELECTOR_LIMIT", "limit": MAP_MAX_SELECTOR, "available": len(forms)})
    base = {
        "mode": MAP_MODE,
        "description": ("Module-level architecture: a Form includes its blocks, items, triggers "
                        "and program units; a package includes its subprograms. Containment is "
                        "not drawn as a dependency."),
        "focus": focus_id,
        "depth": depth,
        "layer_filter": layer,
        "edge_filter": edge_type,
        "layers": list(MAP_LAYERS),
        "relationships": list(MAP_RELATIONSHIPS),
        "limits": {"nodes": limit, "edges": edge_limit, "selector": MAP_MAX_SELECTOR},
        "available_forms": [{"id": f["id"], "name": f["name"]} for f in selector],
        "selector": {"total": len(forms), "shown": len(selector),
                     "truncated": len(forms) > MAP_MAX_SELECTOR},
        "total_estate_nodes": len(nodes),
        "total_estate_edges": len(all_edges),
        **_page_meta(prepared),
    }
    if focus_id is None:
        return {**base, "nodes": [], "edges": [], "total_nodes": 0, "total_edges": 0,
                "reachable_nodes": 0, "available_edges": 0,
                "truncated": bool(truncation), "truncation": truncation}
    adjacency = defaultdict(set)
    for edge in all_edges:
        if edge_type and edge["classification"] != edge_type:
            continue
        adjacency[edge["source"]].add(edge["target"])
        adjacency[edge["target"]].add(edge["source"])
    order = lambda identity: (nodes[identity]["name"].casefold(), identity)
    reachable, frontier = {focus_id}, [focus_id]
    for _ in range(depth):
        frontier = sorted({n for current in frontier for n in adjacency[current]} - reachable, key=order)
        reachable.update(frontier)
    if layer:
        reachable = {n for n in reachable if n == focus_id or nodes[n]["layer"] == layer}
    # Keep the focus, then the nearest nodes in breadth-first, name order.
    visited, frontier = [focus_id], [focus_id]
    seen = {focus_id}
    while frontier and len(visited) < limit:
        following = []
        for current in frontier:
            for neighbour in sorted(adjacency[current] & reachable - seen, key=order):
                seen.add(neighbour)
                following.append(neighbour)
        for neighbour in following:
            if len(visited) >= limit:
                break
            visited.append(neighbour)
        frontier = following
    if layer:
        # Layer filtering keeps matching nodes reachable through filtered-out ones.
        for identity in sorted(reachable - set(visited), key=order):
            if len(visited) >= limit:
                break
            visited.append(identity)
    kept = set(visited)
    if len(reachable) > len(kept):
        truncation.append({"reason": "NODE_LIMIT", "limit": limit, "available": len(reachable)})
    candidates = [e for e in all_edges
                  if e["source"] in kept and e["target"] in kept
                  and (not edge_type or e["classification"] == edge_type)]
    candidates.sort(key=lambda e: (focus_id not in {e["source"], e["target"]}, not e["is_hotspot"],
                                   e["classification"], e["source_name"].casefold(),
                                   e["target_name"].casefold(), e["id"]))
    edges = candidates[:edge_limit]
    if len(candidates) > len(edges):
        truncation.append({"reason": "EDGE_LIMIT", "limit": edge_limit, "available": len(candidates)})
    degree_in, degree_out = Counter(), Counter()
    for edge in all_edges:
        degree_out[edge["source"]] += 1
        degree_in[edge["target"]] += 1
    result_nodes = [{**nodes[n], "fan_in": degree_in[n], "fan_out": degree_out[n],
                     "risk": nodes[n]["highest_risk"], "is_focus": n == focus_id}
                    for n in sorted(kept, key=order)]
    return {
        **base,
        "nodes": result_nodes,
        "edges": [copy.deepcopy(e) for e in edges],
        "total_nodes": len(result_nodes),
        "total_edges": len(edges),
        "reachable_nodes": len(reachable),
        "available_edges": len(candidates),
        "truncated": bool(truncation),
        "truncation": truncation,
    }


def search_project(prepared: PreparedProjection, query: str, limit: int = 20) -> dict:
    """Multi-category instant search across forms, packages, tables, hotspots, rules, and findings."""
    if not isinstance(query, str) or len(query) > MAX_SEARCH_QUERY or "\0" in query:
        raise ProjectError(f"Search query must be text of at most {MAX_SEARCH_QUERY} characters")
    if type(limit) is not int or not 1 <= limit <= MAX_SEARCH_LIMIT:
        raise ProjectError(f"Search limit must be an integer between 1 and {MAX_SEARCH_LIMIT}")
    meta = {"project_id": prepared.key.project_id, "limit": limit, **_page_meta(prepared)}
    q = query.strip().casefold()
    if not q:
        return {"query": query, "total": 0, "results": [], **meta}

    scored_results = []

    def _score(target: str, context: str = "") -> int:
        t = target.casefold()
        if q == t:
            return 100
        if t.startswith(q):
            return 80
        if q in t:
            return 50
        if context and q in context.casefold():
            return 20
        return 0

    for row in prepared.rows.get("forms", ()):
        name = row.get("name", "")
        score = _score(name, row.get("module", ""))
        if score > 0:
            scored_results.append((score, {
                "id": row["id"], "category": "forms", "category_label": "Form Module",
                "title": name,
                "subtitle": f"Forms module · {row.get('findings', 0)} findings",
                "risk": row.get("highest_risk", "UNKNOWN"),
                "action": {"view": "system-map", "focus": row["id"], "target_id": row["id"]},
            }))
    for row in prepared.rows.get("packages", ()):
        name = row.get("name", "")
        score = _score(name)
        if score > 0:
            scored_results.append((score, {
                "id": row["id"], "category": "packages", "category_label": "Database Package",
                "title": name,
                "subtitle": f"Database package · {row.get('subprograms', 0)} subprograms",
                "risk": row.get("highest_risk", "UNKNOWN"),
                "action": {"view": "inventory", "category": "packages", "target_id": row["id"]},
            }))
    for category, label in (("tables", "Database Table"), ("views", "Database View")):
        for row in prepared.rows.get(category, ()):
            name = row.get("name", "")
            score = _score(name)
            if score > 0:
                scored_results.append((score, {
                    "id": row["id"], "category": category, "category_label": label,
                    "title": name, "subtitle": label,
                    "risk": row.get("highest_risk", "UNKNOWN"),
                    "action": {"view": "inventory", "category": category, "target_id": row["id"]},
                }))
    for row in prepared.rows.get("hotspots", ()):
        title = row.get("title", "")
        score = _score(title, f"{row.get('label', '')} {row.get('module', '')}")
        if score > 0:
            scored_results.append((score, {
                "id": row["id"], "category": "hotspots", "category_label": "Hotspot candidate",
                "title": title,
                "subtitle": f"{row.get('label', '')} · {row.get('severity', '')} severity candidate",
                "risk": row.get("severity", "UNKNOWN"),
                "action": {"view": "inventory", "category": "hotspots", "target_id": row["id"]},
            }))
    for row in prepared.rows.get("business_rules", ()):
        name, module = row.get("name", ""), row.get("module", "")
        score = _score(name, module)
        if score > 0:
            scored_results.append((score, {
                "id": row["id"], "category": "business_rules", "category_label": "Business Rule",
                "title": name, "subtitle": f"Business rule candidate · {module}",
                "risk": row.get("risk", "UNKNOWN"),
                "action": {"view": "inventory", "category": "business_rules", "target_id": row["id"]},
            }))
    for row in prepared.rows.get("findings", ()):
        name, module, fid = row.get("name", ""), row.get("module", ""), row.get("id", "")
        score = _score(f"{module} {name}", f"{row.get('reason', '')} {fid}")
        if score > 0:
            scored_results.append((score, {
                "id": fid, "category": "findings", "category_label": "Modernization Finding",
                "title": f"{module} · {name}",
                "subtitle": f"Finding · Risk: {row.get('risk', '')}",
                "risk": row.get("risk", "UNKNOWN"),
                "action": {"view": "review", "finding_id": fid, "target_id": fid},
            }))

    scored_results.sort(key=lambda x: (-x[0], x[1]["category"], x[1]["title"], x[1]["id"]))
    return {
        "query": query,
        "total": len(scored_results),
        "results": [item for _, item in scored_results[:limit]],
        **meta,
    }
