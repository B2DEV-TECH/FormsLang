"""Bounded, deterministic read models over one persisted project assessment."""

from __future__ import annotations

import copy
import math
from collections import Counter, OrderedDict, defaultdict, deque
from dataclasses import dataclass, field
from pathlib import PurePosixPath, PureWindowsPath
from threading import RLock

from .hotspots import detect_estate_hotspots
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


def _statement_codes(item):
    codes = set()
    statements = item.get("statements") if isinstance(item.get("statements"), list) else []
    for statement in statements:
        text = statement.get("text") if isinstance(statement, dict) else None
        if not isinstance(text, str) or not text.startswith("[") or "]" not in text:
            continue
        code = text[1 : text.index("]")]
        if code and all(
            character.isupper() or character.isdigit() or character == "_"
            for character in code
        ):
            codes.add(code)
    return codes


def _finding_rows(findings, entities, centrality, evidence_by_entity, fan_in=None):
    rows = []
    fan_in = fan_in or {}
    for item in sorted(findings.values(), key=lambda value: value["id"]):
        entity = entities.get(item.get("entity"), {})
        attributes = (
            entity.get("attributes") if isinstance(entity.get("attributes"), dict) else {}
        )
        risk = attributes.get("risk") if isinstance(attributes.get("risk"), dict) else {}
        signal_codes = _statement_codes(item)
        evidence_factors = set(evidence_by_entity.get(item.get("entity"), ()))
        if "DIRECT_DML_BYPASSES_API" in signal_codes:
            evidence_factors.add("API_BYPASS")
        if any(code.startswith("LOGIC_DUPLICATED_") for code in signal_codes):
            evidence_factors.add("DUPLICATED_LOGIC")

        risk_level = _bucket(risk.get("level"), RISK_LEVELS)
        base = BASE_SEVERITY.get(risk_level, 1.0)
        eid = item.get("entity")
        fan_in_count = fan_in.get(eid, 0)
        fan_in_multiplier = 0.2 * math.log2(1.0 + fan_in_count)
        is_bypass = ("API_BYPASS" in evidence_factors) or (
            item.get("code") in ("DIRECT_DML_BYPASSES_API", "API_BYPASS_CANDIDATE")
        )
        bypass_multiplier = 0.3 if is_bypass else 0.0
        has_existing_api = bool(item.get("duplicates")) or (
            "DUPLICATED_LOGIC" in evidence_factors
        )
        api_multiplier = 0.25 if has_existing_api else 0.0
        priority_score = round(
            base * (1.0 + fan_in_multiplier + bypass_multiplier + api_multiplier), 1
        )

        breakdown = [f"Base Severity: {int(base)} ({risk_level})"]
        if fan_in_count > 0:
            breakdown.append(f"Fan-In: {fan_in_count} (+{fan_in_multiplier:.2f}x)")
        if is_bypass:
            breakdown.append("API Bypass: Yes (+0.30x)")
        if has_existing_api:
            breakdown.append("Existing API: Yes (+0.25x)")
        breakdown.append(f"Priority Score: {priority_score}")

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
        if edge.get("type") == "DUPLICATES_LOGIC":
            evidence_by_entity[source].add("DUPLICATED_LOGIC")
        source_module = _logical_name(entities.get(source, {}).get("module"))
        target_module = _logical_name(entities.get(target, {}).get("module"))
        if source_module and target_module and source_module != target_module:
            evidence_by_entity[source].add("CROSS_MODULE_IMPACT")
            evidence_by_entity[target].add("CROSS_MODULE_IMPACT")
    finding_rows = _finding_rows(findings, entities, centrality, evidence_by_entity, fan_in)
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
    blueprint = (
        assessment.get("blueprint", {})
        if isinstance(assessment.get("blueprint"), dict)
        else {}
    )
    hotspot_results = detect_estate_hotspots(blueprint)
    hotspot_rows = tuple(
        {
            **h,
            "entity_ids": h.get("affected_entities", ()),
            "_member_ids": h.get("affected_entities", ()),
        }
        for h in hotspot_results.get("hotspots", [])
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
            "items": hotspot_results["hotspots"][:20],
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


def _node_layer(entity_type: str) -> str:
    et = (entity_type or "").upper()
    if et in {"FORM", "MODULE", "CANVAS", "BLOCK", "ITEM", "TRIGGER"}:
        return "FORM"
    elif et in {
        "PACKAGE",
        "PACKAGE_BODY",
        "PACKAGE_SPEC",
        "PROCEDURE",
        "FUNCTION",
        "ROUTINE",
        "ROUTINE_REFERENCE",
        "PACKAGE_REFERENCE",
        "TABLE",
        "VIEW",
        "TABLE_OR_VIEW_REFERENCE",
        "SEQUENCE",
        "SEQUENCE_REFERENCE",
        "DATABASE",
    }:
        return "DATABASE"
    elif et in {"LIBRARY", "ATTACHED_LIBRARY", "PLL", "PL/SQL LIBRARY"}:
        return "LIBRARY"
    elif et in {"GLOBAL", "GLOBAL_REFERENCE", "GLOBAL_STATE"}:
        return "GLOBAL"
    return "EXTERNAL"


def _classify_edge(edge_type: str, target_name: str = "", *, is_bypass: bool = False) -> str:
    if is_bypass:
        return "DIRECT_DML"
    et = (edge_type or "").upper()
    if et in {"CALLS", "USES_PROGRAM_UNIT", "INVOKES_BUILTIN"}:
        return "CALLS"
    elif et in {"READS", "EXECUTES_QUERY"}:
        return "READS"
    elif et in {"WRITES", "COMMITS"}:
        return "WRITES"
    elif et in {"OPENS_FORM", "NAVIGATES_TO", "CALL_FORM"}:
        return "OPENS_FORM"
    elif "GLOBAL" in target_name.upper():
        return "SHARES_STATE"
    return "REFERENCES"


def system_map(
    prepared: PreparedProjection,
    *,
    focus: str | None = None,
    depth: int = 2,
    layer: str | None = None,
    edge_type: str | None = None,
    limit: int = 100,
) -> dict:
    """Return a bounded, explainable architecture topology around a focus module."""
    if not 1 <= depth <= 5:
        depth = 2
    if not 1 <= limit <= 200:
        limit = 100

    available_forms = tuple(
        {"id": f["id"], "name": f["name"]} for f in prepared.rows.get("forms", ())
    )

    blueprint = prepared.raw_blueprint or {}
    raw_entities = _unique(blueprint.get("entities", []))
    raw_edges = _unique(blueprint.get("edges", []))
    findings_by_entity = defaultdict(list)
    for f in prepared.rows.get("findings", ()):
        findings_by_entity[f.get("entity_id")].append(f)
        findings_by_entity[f.get("id")].append(f)

    bypass_tables_by_module = defaultdict(set)
    for h in prepared.rows.get("hotspots", ()):
        if h.get("type") == "API_BYPASS_CANDIDATE":
            det = h.get("details", {})
            table = det.get("table", "").upper()
            module = det.get("form_block_trigger", "").split(".")[0].upper()
            if table and module:
                bypass_tables_by_module[module].add(table)

    focus_id = None
    if focus:
        focus_id = next(
            (
                f["id"]
                for f in available_forms
                if f["id"] == focus or f["name"].casefold() == focus.casefold()
            ),
            None,
        )
        if not focus_id and focus in raw_entities:
            focus_id = focus
    if not focus_id and available_forms:
        focus_id = available_forms[0]["id"]
    if not focus_id and raw_entities:
        focus_id = next(iter(raw_entities.keys()))

    if not focus_id:
        return {
            "nodes": [],
            "edges": [],
            "focus": None,
            "depth": depth,
            "total_nodes": 0,
            "total_edges": 0,
            "total_estate_nodes": len(raw_entities),
            "total_estate_edges": len(raw_edges),
            "truncated": False,
            "available_forms": list(available_forms),
            **_page_meta(prepared),
        }

    all_dep_edges = []
    if raw_edges:
        for edge in raw_edges.values():
            if edge.get("type") == "CONTAINS":
                continue
            src = edge.get("source")
            tgt = edge.get("target")
            if src and tgt:
                all_dep_edges.append(edge)
    else:
        for dep in prepared.rows.get("dependencies", ()):
            all_dep_edges.append(
                {
                    "id": dep["id"],
                    "source": dep["source_id"],
                    "target": dep["target_id"],
                    "type": dep["relationship"],
                }
            )

    adj_out = defaultdict(list)
    adj_in = defaultdict(list)
    for edge in all_dep_edges:
        src = edge.get("source")
        tgt = edge.get("target")
        adj_out[src].append(tgt)
        adj_in[tgt].append(src)

    visited = {focus_id}
    queue = deque([(focus_id, 0)])
    truncated = False

    while queue:
        curr, curr_d = queue.popleft()
        if curr_d >= depth:
            continue
        neighbors = set(adj_out.get(curr, [])) | set(adj_in.get(curr, []))
        for n in sorted(neighbors):
            if n not in visited:
                if len(visited) >= limit:
                    truncated = True
                    break
                visited.add(n)
                queue.append((n, curr_d + 1))
        if truncated:
            break

    if layer:
        target_layer = layer.strip().upper()
        visited = {
            nid
            for nid in visited
            if nid == focus_id
            or _node_layer(raw_entities.get(nid, {}).get("type", "")) == target_layer
        }

    nodes = []
    for nid in sorted(visited):
        entity = raw_entities.get(nid, {})
        etype = entity.get("type", "UNKNOWN")
        name = entity.get("name") or nid
        n_layer = _node_layer(etype)
        related_findings = findings_by_entity.get(nid, [])
        risk = "UNKNOWN"
        for rk in RISK_LEVELS:
            if any(f.get("risk") == rk for f in related_findings):
                risk = rk
                break

        nodes.append(
            {
                "id": nid,
                "name": name,
                "type": etype,
                "layer": n_layer,
                "risk": risk if related_findings else "NONE",
                "fan_in": len(adj_in.get(nid, [])),
                "fan_out": len(adj_out.get(nid, [])),
                "findings_count": len(related_findings),
                "is_focus": nid == focus_id,
            }
        )

    tables_with_pkg_writer = {
        edge.get("target")
        for edge in all_dep_edges
        if edge.get("type") == "WRITES"
        and raw_entities.get(edge.get("source"), {}).get("type")
        in {
            "PACKAGE",
            "PACKAGE_SPEC",
            "PACKAGE_BODY",
        }
    }

    edges = []
    for edge in all_dep_edges:
        src = edge.get("source")
        tgt = edge.get("target")
        if src in visited and tgt in visited:
            src_name = raw_entities.get(src, {}).get("name", src)
            tgt_name = raw_entities.get(tgt, {}).get("name", tgt)
            src_type = raw_entities.get(src, {}).get("type", "")
            src_module = (raw_entities.get(src, {}).get("module") or src_name).upper()
            is_bypass = (
                edge.get("type") == "WRITES"
                and tgt in tables_with_pkg_writer
                and src_type in {"FORM", "TRIGGER", "PROGRAM_UNIT"}
            ) or (tgt_name.upper() in bypass_tables_by_module.get(src_module, set()))
            classification = _classify_edge(edge.get("type"), tgt_name, is_bypass=is_bypass)

            if edge_type and classification != edge_type.strip().upper():
                continue

            edges.append(
                {
                    "id": edge.get("id"),
                    "source": src,
                    "source_name": src_name,
                    "target": tgt,
                    "target_name": tgt_name,
                    "relationship": edge.get("type", ""),
                    "classification": classification,
                    "is_hotspot": is_bypass
                    or classification in {"DIRECT_DML", "SHARES_STATE"},
                    "evidence": edge.get("evidence", []),
                }
            )

    return {
        "nodes": nodes,
        "edges": edges,
        "focus": focus_id,
        "depth": depth,
        "layer_filter": layer,
        "edge_filter": edge_type,
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "total_estate_nodes": len(raw_entities),
        "total_estate_edges": len(raw_edges),
        "truncated": truncated,
        "available_forms": list(available_forms),
        **_page_meta(prepared),
    }


def search_project(prepared: PreparedProjection, query: str, limit: int = 20) -> dict:
    """Multi-category instant search across forms, packages, tables, hotspots, rules, and findings."""
    q = (query or "").strip().casefold()
    if not q:
        return {
            "query": query,
            "total": 0,
            "results": [],
            **_page_meta(prepared),
        }

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

    # 1. Forms
    for row in prepared.rows.get("forms", ()):
        name = row.get("name", "")
        module = row.get("module", "")
        score = _score(name, module)
        if score > 0:
            scored_results.append(
                (
                    score,
                    {
                        "id": row["id"],
                        "category": "forms",
                        "category_label": "Form Module",
                        "title": name,
                        "subtitle": f"Forms Module · {row.get('findings', 0)} findings · Risk: {row.get('highest_risk', 'None')}",
                        "risk": row.get("highest_risk", "UNKNOWN"),
                        "action": {
                            "view": "system-map",
                            "focus": row["id"],
                            "target_id": row["id"],
                        },
                    },
                )
            )

    # 2. Packages
    for row in prepared.rows.get("packages", ()):
        name = row.get("name", "")
        score = _score(name)
        if score > 0:
            scored_results.append(
                (
                    score,
                    {
                        "id": row["id"],
                        "category": "packages",
                        "category_label": "Database Package",
                        "title": name,
                        "subtitle": f"Database Package · {row.get('subprograms', 0)} subprograms",
                        "risk": row.get("highest_risk", "UNKNOWN"),
                        "action": {
                            "view": "inventory",
                            "category": "packages",
                            "target_id": row["id"],
                        },
                    },
                )
            )

    # 3. Tables
    for row in prepared.rows.get("tables", ()):
        name = row.get("name", "")
        score = _score(name)
        if score > 0:
            scored_results.append(
                (
                    score,
                    {
                        "id": row["id"],
                        "category": "tables",
                        "category_label": "Database Table",
                        "title": name,
                        "subtitle": f"Database Table · {row.get('columns', 0)} columns",
                        "risk": row.get("highest_risk", "UNKNOWN"),
                        "action": {
                            "view": "inventory",
                            "category": "tables",
                            "target_id": row["id"],
                        },
                    },
                )
            )

    # 4. Views
    for row in prepared.rows.get("views", ()):
        name = row.get("name", "")
        score = _score(name)
        if score > 0:
            scored_results.append(
                (
                    score,
                    {
                        "id": row["id"],
                        "category": "views",
                        "category_label": "Database View",
                        "title": name,
                        "subtitle": "Database View",
                        "risk": row.get("highest_risk", "UNKNOWN"),
                        "action": {
                            "view": "inventory",
                            "category": "views",
                            "target_id": row["id"],
                        },
                    },
                )
            )

    # 5. Hotspots
    for row in prepared.rows.get("hotspots", ()):
        title = row.get("title", "")
        pattern = row.get("pattern_name", "")
        loc = row.get("location", "")
        score = _score(title, f"{pattern} {loc}")
        if score > 0:
            scored_results.append(
                (
                    score,
                    {
                        "id": row["id"],
                        "category": "hotspots",
                        "category_label": "Architectural Hotspot",
                        "title": title,
                        "subtitle": f"{pattern} · {loc}",
                        "risk": row.get("severity", "HIGH"),
                        "action": {
                            "view": "overview",
                            "hotspot_id": row["id"],
                            "target_id": row["id"],
                        },
                    },
                )
            )

    # 6. Business Rules
    for row in prepared.rows.get("business_rules", ()):
        name = row.get("name", "")
        mod = row.get("module", "")
        score = _score(name, mod)
        if score > 0:
            scored_results.append(
                (
                    score,
                    {
                        "id": row["id"],
                        "category": "business_rules",
                        "category_label": "Business Rule",
                        "title": name,
                        "subtitle": f"Business Rule · {mod}",
                        "risk": row.get("risk", "UNKNOWN"),
                        "action": {
                            "view": "inventory",
                            "category": "business_rules",
                            "target_id": row["id"],
                        },
                    },
                )
            )

    # 7. Findings
    for row in prepared.rows.get("findings", ()):
        name = row.get("name", "")
        mod = row.get("module", "")
        reason = row.get("reason", "")
        fid = row.get("id", "")
        score = _score(f"{mod} {name}", f"{reason} {fid}")
        if score > 0:
            scored_results.append(
                (
                    score,
                    {
                        "id": fid,
                        "category": "findings",
                        "category_label": "Modernization Finding",
                        "title": f"{mod} · {name}",
                        "subtitle": f"Finding · Risk: {row.get('risk', '')} · {reason}",
                        "risk": row.get("risk", "UNKNOWN"),
                        "action": {"view": "review", "finding_id": fid, "target_id": fid},
                    },
                )
            )

    scored_results.sort(key=lambda x: (-x[0], x[1]["category"], x[1]["title"]))
    total = len(scored_results)
    results = [item for _, item in scored_results[:limit]]

    return {
        "query": query,
        "total": total,
        "results": results,
        **_page_meta(prepared),
    }
