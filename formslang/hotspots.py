"""Estate Intelligence Hotspot Engine for FormsLang 2.1+.

Detects authoritative architectural anti-patterns across legacy Forms and
database schemas:
1. API_BYPASS_CANDIDATE: Direct DML on tables owned by DB packages
2. DUPLICATED_RULE_CLUSTER: Isomorphic validation rules across forms
3. GLOBAL_STATE_COUPLING: Unbounded state coupling via :GLOBAL.* variables
4. CROSS_LAYER_OWNERSHIP_CONFLICT: Divergent validation between Form and DB
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import asdict, dataclass

HOTSPOT_API_BYPASS = "API_BYPASS_CANDIDATE"
HOTSPOT_DUPLICATED_RULE = "DUPLICATED_RULE_CLUSTER"
HOTSPOT_GLOBAL_STATE = "GLOBAL_STATE_COUPLING"
HOTSPOT_OWNERSHIP_CONFLICT = "CROSS_LAYER_OWNERSHIP_CONFLICT"

HOTSPOT_TYPES = (
    HOTSPOT_API_BYPASS,
    HOTSPOT_DUPLICATED_RULE,
    HOTSPOT_GLOBAL_STATE,
    HOTSPOT_OWNERSHIP_CONFLICT,
)

TEMP_TABLE_PREFIXES = ("TMP_", "TEMP_", "GTT_", "WRK_", "SYS_")

_GLOBAL_VAR_PATTERN = re.compile(r":GLOBAL\.([A-Za-z0-9_$#]+)", re.IGNORECASE)
_GLOBAL_WRITE_PATTERN = re.compile(r":GLOBAL\.([A-Za-z0-9_$#]+)\s*:=", re.IGNORECASE)
_NAV_PATTERN = re.compile(r"\b(CALL_FORM|OPEN_FORM|NEW_FORM)\b", re.IGNORECASE)


@dataclass(frozen=True)
class HotspotFinding:
    """One detected estate-level architectural hotspot."""

    id: str
    hotspot_type: str
    severity: str
    title: str
    statement: str
    module: str
    entity_id: str | None
    affected_entities: tuple[str, ...]
    evidence: dict
    remediation: str

    def to_dict(self) -> dict:
        return asdict(self)


def is_temp_table(table_name: str) -> bool:
    """True if table is a scratch or global temporary table."""
    upper = table_name.upper().strip()
    return any(upper.startswith(p) for p in TEMP_TABLE_PREFIXES)


def detect_api_bypass_candidates(blueprint: dict) -> list[HotspotFinding]:
    """Detect direct DML in Form triggers that bypasses existing DB package APIs."""
    hotspots = []
    seen = set()
    entities = {n["id"]: n for n in blueprint.get("entities", []) if "id" in n}

    # 1. Inspect existing findings for DML bypass signals
    for finding in blueprint.get("findings", []):
        code = finding.get("code", "")
        if code in ("DIRECT_DML_BYPASSES_API", HOTSPOT_API_BYPASS):
            entity_id = finding.get("entity")
            entity = entities.get(entity_id, {})
            module = entity.get("module", "unknown")
            table = finding.get("target") or finding.get("duplicates") or "TABLE"
            if is_temp_table(str(table)):
                continue
            key = (module, entity_id, str(table))
            if key in seen:
                continue
            seen.add(key)
            pkg = finding.get("duplicates") or finding.get("target") or "Database API"
            hid = f"hotspot:bypass:{entity_id or 'f'}:{table}"
            hotspots.append(
                HotspotFinding(
                    id=hid,
                    hotspot_type=HOTSPOT_API_BYPASS,
                    severity="CRITICAL",
                    title=f"Direct DML Bypasses API: {table}",
                    statement=f"Form trigger '{entity.get('name', entity_id)}' in '{module}' executes direct DML on table '{table}', bypassing package '{pkg}'.",
                    module=module,
                    entity_id=entity_id,
                    affected_entities=(entity_id,) if entity_id else (),
                    evidence={"table": table, "bypassed_package": pkg, "reason": finding.get("reason", "")},
                    remediation=f"Route writes to '{table}' through the authoritative database package '{pkg}' rather than executing direct DML in UI triggers.",
                )
            )

    # 2. Graph-based detection over edges
    edges = blueprint.get("edges", [])
    table_writers = defaultdict(set)  # table_id -> set of writer entity_ids
    trigger_writes = defaultdict(set)  # trigger_id -> set of table_ids
    trigger_calls = defaultdict(set)  # trigger_id -> set of called entity_ids

    for edge in edges:
        etype = edge.get("type")
        source = edge.get("source")
        target = edge.get("target")
        if not source or not target:
            continue
        if etype == "WRITES":
            s_node = entities.get(source, {})
            t_node = entities.get(target, {})
            if t_node.get("type") in ("TABLE", "TABLE_OR_VIEW_REFERENCE"):
                table_writers[target].add(source)
                if s_node.get("type") == "TRIGGER":
                    trigger_writes[source].add(target)
        elif etype == "CALLS":
            trigger_calls[source].add(target)

    for trigger_id, tables in trigger_writes.items():
        trigger_node = entities.get(trigger_id, {})
        module = trigger_node.get("module", "unknown")
        called = trigger_calls.get(trigger_id, set())

        for tbl_id in tables:
            tbl_node = entities.get(tbl_id, {})
            tbl_name = tbl_node.get("name", tbl_id)
            if is_temp_table(tbl_name):
                continue
            key = (module, trigger_id, tbl_name)
            if key in seen:
                continue

            # Check if any writer is a database package
            pkg_writers = [
                w for w in table_writers.get(tbl_id, set())
                if entities.get(w, {}).get("type") in ("PACKAGE_SPEC", "PACKAGE_BODY", "PACKAGE_SUBPROGRAM")
            ]
            if pkg_writers:
                # Does the trigger call this package writer?
                uncalled_pkgs = [w for w in pkg_writers if w not in called]
                if uncalled_pkgs:
                    seen.add(key)
                    pkg_node = entities.get(uncalled_pkgs[0], {})
                    pkg_name = pkg_node.get("name", uncalled_pkgs[0])
                    hid = f"hotspot:bypass:{trigger_id}:{tbl_name}"
                    hotspots.append(
                        HotspotFinding(
                            id=hid,
                            hotspot_type=HOTSPOT_API_BYPASS,
                            severity="CRITICAL",
                            title=f"Direct DML Bypasses API: {tbl_name}",
                            statement=f"Trigger '{trigger_node.get('name', trigger_id)}' writes table '{tbl_name}' directly, bypassing package '{pkg_name}'.",
                            module=module,
                            entity_id=trigger_id,
                            affected_entities=(trigger_id, tbl_id, uncalled_pkgs[0]),
                            evidence={"table": tbl_name, "bypassed_package": pkg_name},
                            remediation=f"Route writes to '{tbl_name}' through '{pkg_name}' to centralize business rules and audit.",
                        )
                    )

    return sorted(hotspots, key=lambda h: (h.module, h.id))


def detect_duplicated_rule_clusters(blueprint: dict) -> list[HotspotFinding]:
    """Detect isomorphic or identical validation rules duplicated across modules."""
    hotspots = []
    entities = {n["id"]: n for n in blueprint.get("entities", []) if "id" in n}

    # Group duplication findings
    clusters = defaultdict(list)
    for finding in blueprint.get("findings", []):
        code = finding.get("code", "")
        if code in (
            "LOGIC_DUPLICATED_QUERY",
            "LOGIC_DUPLICATED_FORMULA",
            "LOGIC_DUPLICATED_PREDICATE",
            HOTSPOT_DUPLICATED_RULE,
        ):
            target = finding.get("target") or finding.get("duplicates") or finding.get("statement", "")
            entity_id = finding.get("entity")
            clusters[target].append((entity_id, finding))

    for target, items in clusters.items():
        if len(items) >= 2 or any(code in ("LOGIC_DUPLICATED_QUERY", "LOGIC_DUPLICATED_PREDICATE") for _, f in items for code in [f.get("code")]):
            modules = set()
            affected = []
            for eid, f in items:
                affected.append(eid)
                e = entities.get(eid, {})
                modules.add(e.get("module", "unknown"))
            mod_list = sorted(modules)
            lead_module = mod_list[0] if mod_list else "shared"
            hid = f"hotspot:cluster:{abs(hash(target)) % 1000000:06x}"
            hotspots.append(
                HotspotFinding(
                    id=hid,
                    hotspot_type=HOTSPOT_DUPLICATED_RULE,
                    severity="HIGH",
                    title=f"Duplicated Rule Cluster: {target}",
                    statement=f"Rule or calculation '{target}' is implemented across {len(items)} units in {len(modules)} module(s).",
                    module=lead_module,
                    entity_id=affected[0] if affected else None,
                    affected_entities=tuple(filter(None, affected)),
                    evidence={"occurrences": len(items), "modules": mod_list, "rule_target": target},
                    remediation=f"Extract and centralize '{target}' logic into a shared database package or domain service.",
                )
            )

    return sorted(hotspots, key=lambda h: (h.module, h.id))


def detect_global_state_couplings(blueprint: dict) -> list[HotspotFinding]:
    """Detect :GLOBAL.* state couplings used across multiple Forms modules."""
    hotspots = []
    entities = blueprint.get("entities", [])

    # Map variable -> {'readers': set(modules), 'writers': set(modules), 'entities': set()}
    var_map = defaultdict(lambda: {"readers": set(), "writers": set(), "entities": set(), "nav_modules": set()})

    for entity in entities:
        etype = entity.get("type", "")
        if etype not in ("TRIGGER", "PROGRAM_UNIT"):
            continue
        module = entity.get("module", "unknown")
        attrs = entity.get("attributes", {})
        source = attrs.get("source") or attrs.get("body") or ""
        if not source:
            continue

        reads = set()
        writes = set()
        for m in _GLOBAL_WRITE_PATTERN.finditer(source):
            writes.add(m.group(1).upper())
        for m in _GLOBAL_VAR_PATTERN.finditer(source):
            vname = m.group(1).upper()
            if vname not in writes:
                reads.add(vname)

        has_nav = bool(_NAV_PATTERN.search(source))

        for vname in writes:
            var_map[vname]["writers"].add(module)
            var_map[vname]["entities"].add(entity["id"])
            if has_nav:
                var_map[vname]["nav_modules"].add(module)
        for vname in reads:
            var_map[vname]["readers"].add(module)
            var_map[vname]["entities"].add(entity["id"])
            if has_nav:
                var_map[vname]["nav_modules"].add(module)

    for vname, data in sorted(var_map.items()):
        all_modules = data["readers"] | data["writers"]
        # Multi-module state coupling requires at least 2 distinct modules,
        # or writing and cross-module navigation in the same module.
        is_multi_module = len(all_modules) >= 2
        is_nav_coupled = bool(data["nav_modules"]) and (len(all_modules) >= 1)

        if is_multi_module or (is_nav_coupled and data["writers"]):
            severity = "HIGH" if is_nav_coupled else "MEDIUM"
            lead_module = min(all_modules) if all_modules else "unknown"
            hid = f"hotspot:global:{vname.lower()}"
            hotspots.append(
                HotspotFinding(
                    id=hid,
                    hotspot_type=HOTSPOT_GLOBAL_STATE,
                    severity=severity,
                    title=f"Global State Coupling: :GLOBAL.{vname}",
                    statement=f"Global variable ':GLOBAL.{vname}' coordinates state across modules: {', '.join(sorted(all_modules))}.",
                    module=lead_module,
                    entity_id=min(data["entities"]) if data["entities"] else None,
                    affected_entities=tuple(sorted(data["entities"])),
                    evidence={
                        "variable": f":GLOBAL.{vname}",
                        "readers": sorted(data["readers"]),
                        "writers": sorted(data["writers"]),
                        "cross_module_navigation": bool(data["nav_modules"]),
                    },
                    remediation=f"Replace :GLOBAL.{vname} with explicit parameter passing or scoped session state.",
                )
            )

    return hotspots


def detect_cross_layer_ownership_conflicts(blueprint: dict) -> list[HotspotFinding]:
    """Detect conflicting validation rules between Forms triggers and database constraints."""
    hotspots = []
    entities = {n["id"]: n for n in blueprint.get("entities", []) if "id" in n}

    for finding in blueprint.get("findings", []):
        code = finding.get("code", "")
        if code in (HOTSPOT_OWNERSHIP_CONFLICT, "CROSS_LAYER_CONFLICT"):
            entity_id = finding.get("entity")
            entity = entities.get(entity_id, {})
            module = entity.get("module", "unknown")
            hid = f"hotspot:conflict:{entity_id or 'f'}"
            hotspots.append(
                HotspotFinding(
                    id=hid,
                    hotspot_type=HOTSPOT_OWNERSHIP_CONFLICT,
                    severity="CRITICAL",
                    title="Cross-Layer Ownership Conflict",
                    statement=finding.get("statement") or "Validation in Form trigger conflicts with database check constraint.",
                    module=module,
                    entity_id=entity_id,
                    affected_entities=(entity_id,) if entity_id else (),
                    evidence={"reason": finding.get("reason", "")},
                    remediation="Reconcile Form validation boundary with authoritative database schema constraint.",
                )
            )

    return sorted(hotspots, key=lambda h: (h.module, h.id))


def detect_estate_hotspots(blueprint: dict) -> dict:
    """Run all 4 hotspot detectors deterministically across the blueprint."""
    bypasses = detect_api_bypass_candidates(blueprint)
    duplicated = detect_duplicated_rule_clusters(blueprint)
    globals_coupled = detect_global_state_couplings(blueprint)
    conflicts = detect_cross_layer_ownership_conflicts(blueprint)

    all_hotspots = bypasses + duplicated + globals_coupled + conflicts
    return {
        "total": len(all_hotspots),
        "by_type": {
            "api_bypass": len(bypasses),
            "duplicated_rules": len(duplicated),
            "global_state": len(globals_coupled),
            "cross_layer_conflict": len(conflicts),
        },
        "hotspots": [h.to_dict() for h in all_hotspots],
    }
