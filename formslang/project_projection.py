"""Bounded, deterministic read models over one persisted project assessment."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import PurePosixPath, PureWindowsPath

RISK_LEVELS = ("CRITICAL", "HIGH", "MEDIUM", "LOW", "UNKNOWN")
RECOMMENDATIONS = (
    "PRESERVE", "CONVERT", "REFACTOR", "MOVE_TO_PLSQL_API",
    "REPLACE_WITH_APEX_NATIVE", "MANUAL_REVIEW", "DROP", "UNKNOWN",
)
INTERVENTIONS = ("AUTO", "ASSISTED", "MANUAL", "UNKNOWN")
LIBRARY_SUFFIXES = {".pll", ".mmb", ".olb"}
FORM_SUFFIXES = {".xml", ".fmb", ".pll", ".mmb", ".olb"}
ROUTINE_TYPES = {"PACKAGE_SUBPROGRAM", "SUBPROGRAM_BODY", "PROGRAM_UNIT"}


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


def _unique(values):
    result = {}
    for value in values if isinstance(values, list) else []:
        if isinstance(value, dict) and isinstance(value.get("id"), str):
            result.setdefault(value["id"], value)
    return result


def _safe_entity(node, findings_by_entity, edges):
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
        "dependencies": sum(
            edge.get("source") == identity or edge.get("target") == identity for edge in edges
        ),
        "findings": len(related),
        "highest_risk": highest,
        "columns": len(attributes.get("columns", ()))
        if isinstance(attributes.get("columns"), list) else None,
        "constraints": len(attributes.get("constraints", ()))
        if isinstance(attributes.get("constraints"), list) else None,
    }


def _finding_rows(findings, entities, centrality):
    rows = []
    for item in sorted(findings.values(), key=lambda value: value["id"]):
        entity = entities.get(item.get("entity"), {})
        attributes = entity.get("attributes") if isinstance(entity.get("attributes"), dict) else {}
        risk = attributes.get("risk") if isinstance(attributes.get("risk"), dict) else {}
        rows.append({
            "id": item["id"],
            "entity_id": _text(item.get("entity"), 500),
            "name": _text(entity.get("name") or item.get("id"), 500),
            "module": _logical_name(entity.get("module")),
            "source_type": _text(entity.get("type"), 100),
            "risk": _bucket(risk.get("level"), RISK_LEVELS),
            "recommendation": _bucket(item.get("recommendation"), RECOMMENDATIONS),
            "intervention": _bucket(item.get("execution_verdict"), INTERVENTIONS),
            "review_state": _bucket_review(item.get("review_state")),
            "reason": _text(item.get("reason"), 2000),
            "classification": tuple(sorted(
                _text(value, 100) for value in item.get("classification", [])
                if isinstance(value, str)
            )),
            "dependency_centrality": centrality.get(item.get("entity"), 0),
        })
    return tuple(rows)


def _bucket_review(value):
    return value.strip().upper() if isinstance(value, str) and value.strip() else "PENDING"


def _package_rows(entities, findings_by_entity, edges):
    packages = {}
    for node in entities.values():
        if node.get("type") not in {"PACKAGE_SPEC", "PACKAGE_BODY"}:
            continue
        module = _logical_name(node.get("module"))
        root_scope = module.split("/", 1)[0].casefold() if "/" in module else ""
        name = _text(node.get("name"), 500)
        key = (root_scope, name.casefold())
        row = packages.setdefault(key, {
            "id": f"package:{root_scope}:{name.casefold()}",
            "name": name,
            "type": "PACKAGE",
            "module": root_scope,
            "spec": False,
            "body": False,
            "entity_ids": [],
            "subprograms": 0,
            "findings": 0,
            "highest_risk": "UNKNOWN",
            "source_status": "ANALYZED",
        })
        row["spec"] |= node.get("type") == "PACKAGE_SPEC"
        row["body"] |= node.get("type") == "PACKAGE_BODY"
        row["entity_ids"].append(node["id"])
    routine_counts = Counter()
    for node in entities.values():
        if node.get("type") in ROUTINE_TYPES:
            attributes = node.get("attributes") if isinstance(node.get("attributes"), dict) else {}
            package = _text(attributes.get("package"), 500)
            module = _logical_name(node.get("module"))
            root_scope = module.split("/", 1)[0].casefold() if "/" in module else ""
            routine_counts[(root_scope, package.casefold())] += 1
    for key, row in packages.items():
        row["entity_ids"] = tuple(sorted(row["entity_ids"]))
        row["subprograms"] = routine_counts[key]
        related = [finding for entity_id in row["entity_ids"]
                   for finding in findings_by_entity.get(entity_id, ())]
        row["findings"] = len(related)
        row["dependencies"] = sum(
            edge.get("source") in row["entity_ids"] or edge.get("target") in row["entity_ids"]
            for edge in edges
        )
    return tuple(sorted(packages.values(), key=lambda row: (row["name"].casefold(), row["id"])))


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
        if suffix in FORM_SUFFIXES:
            form_representations += 1
        if entry.get("representation") == "database":
            database_sources += 1
        if suffix in LIBRARY_SUFFIXES:
            libraries.append({
                "id": _text(entry.get("source_id"), 500),
                "name": PurePosixPath(path).name,
                "type": suffix.removeprefix(".").upper(),
                "module": path,
                "representation": _text(entry.get("representation"), 100),
                "selected": entry.get("selected") is True,
                "source_status": _text(entry.get("status"), 100).upper() or "UNKNOWN",
                "semantic_support": "AVAILABLE" if entry.get("selected") is True else "UNREPRESENTED",
            })
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
        warnings.append({
            "code": code,
            "severity": "WARNING",
            "message": _text(item.get("safe_message"), 1000),
            "remediation": _text(item.get("remediation"), 1000),
            "source_id": _text(item.get("source_id"), 500),
            "target": "inventory",
        })
    state = _bucket_freshness(freshness.get("status") if isinstance(freshness, dict) else None)
    if state != "CURRENT":
        warnings.insert(0, {
            "code": f"ASSESSMENT_{state}", "severity": "WARNING",
            "message": "Saved assessment source state requires attention.",
            "remediation": "Refresh source status or continue viewing the saved assessment.",
            "source_id": "", "target": "overview",
        })
    return warnings


def _bucket_freshness(value):
    allowed = {"CURRENT", "STALE", "INCOMPLETE", "MISSING_SOURCE", "UNVERIFIED"}
    normalized = value.strip().upper() if isinstance(value, str) else "UNVERIFIED"
    return normalized if normalized in allowed else "UNVERIFIED"


def prepare_projection(descriptor: dict, assessment: dict, freshness: dict, *,
                       store_scope: str) -> PreparedProjection:
    """Prepare safe rows once; no source parsing or analysis is performed here."""
    entities = _unique(assessment.get("blueprint", {}).get("entities", []))
    findings = _unique(assessment.get("blueprint", {}).get("findings", []))
    raw_edges = _unique(assessment.get("blueprint", {}).get("edges", []))
    edges = tuple(sorted(
        (edge for edge in raw_edges.values() if edge.get("type") != "CONTAINS"),
        key=lambda edge: edge["id"],
    ))
    centrality = Counter()
    for edge in edges:
        centrality[edge.get("source")] += 1
        centrality[edge.get("target")] += 1
    finding_rows = _finding_rows(findings, entities, centrality)
    findings_by_entity = defaultdict(list)
    for row in finding_rows:
        findings_by_entity[row["entity_id"]].append(row)
    entity_rows = {
        identity: _safe_entity(node, findings_by_entity, edges)
        for identity, node in entities.items()
    }
    forms = tuple(sorted(
        (row for identity, row in entity_rows.items() if entities[identity].get("type") == "FORM"),
        key=lambda row: (row["name"].casefold(), row["id"]),
    ))
    routines = tuple(sorted(
        (row for identity, row in entity_rows.items()
         if entities[identity].get("type") in ROUTINE_TYPES),
        key=lambda row: (row["name"].casefold(), row["id"]),
    ))
    views = tuple(sorted(
        (row for identity, row in entity_rows.items() if entities[identity].get("type") == "VIEW"),
        key=lambda row: (row["name"].casefold(), row["id"]),
    ))
    tables = tuple(sorted(
        (row for identity, row in entity_rows.items() if entities[identity].get("type") == "TABLE"),
        key=lambda row: (row["name"].casefold(), row["id"]),
    ))
    libraries, form_representations, database_sources = _manifest_rows(assessment)
    packages = _package_rows(entities, findings_by_entity, edges)
    dependency_rows = tuple({
        "id": edge["id"],
        "source_id": _text(edge.get("source"), 500),
        "source": _text(entities.get(edge.get("source"), {}).get("name"), 500),
        "target_id": _text(edge.get("target"), 500),
        "target": _text(entities.get(edge.get("target"), {}).get("name"), 500),
        "relationship": _text(edge.get("type"), 100),
    } for edge in edges)
    business_rules = tuple(
        {**row, "candidate_kind": "Observed business rule candidate"}
        for row in finding_rows if "BUSINESS_RULE" in row["classification"]
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
    }
    inventory = assessment.get("inventory") if isinstance(assessment.get("inventory"), dict) else {}
    inventory_forms = inventory.get("forms") if isinstance(inventory.get("forms"), dict) else {}
    inventory_db = inventory.get("database") if isinstance(inventory.get("database"), dict) else {}
    target = _target(descriptor, assessment)
    freshness_state = _bucket_freshness(
        freshness.get("status") if isinstance(freshness, dict) else None
    )
    analysis_revision = _text(assessment.get("analysis_revision"), 64)
    review_revision = assessment.get("review_revision", 0)
    review_revision = review_revision if type(review_revision) is int and review_revision >= 0 else 0
    key = ProjectionKey(
        store_scope=_text(store_scope, 2000),
        project_id=_text(assessment.get("project_id") or descriptor.get("id"), 64),
        analysis_revision=analysis_revision,
        review_revision=review_revision,
        target=(target["platform"], target["version"], target["representation"]),
        freshness=freshness_state,
    )
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
        value: {"count": distributions["intervention_distribution"][value],
                "percent": round(distributions["intervention_distribution"][value] * 100 / total, 1)
                if total else 0.0}
        for value in INTERVENTIONS
    }
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
        },
        **distributions,
        "automation_potential": automation,
        "priority": {
            "critical": distributions["risk_distribution"]["CRITICAL"],
            "high": distributions["risk_distribution"]["HIGH"],
            "manual": distributions["intervention_distribution"]["MANUAL"],
            "total": sum(row["review_state"] not in {"APPROVE", "MODIFY"}
                         for row in finding_rows),
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
                    row["semantic_support"] == "UNREPRESENTED" for row in libraries
                ),
            },
        },
        "warnings": _warnings(assessment, freshness),
        "review_progress": {
            "total": total,
            "reviewed": sum(row["review_state"] in {"APPROVE", "MODIFY"}
                            for row in finding_rows),
        },
        "analysis_metadata": {
            "engine_identity": dict(assessment.get("engine_identity", {}))
            if isinstance(assessment.get("engine_identity"), dict) else {},
        },
    }
    return PreparedProjection(key, dict(descriptor), overview_data["assessment"],
                              overview_data, rows, {})


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
