"""Estate Intelligence: architectural hotspot candidates over the saved Blueprint.

This module is a *projection*. It never parses sources and never runs a second
analysis engine: every hotspot is derived from what the persisted Blueprint
already records -- the structural signal codes the reasoning pass wrote into
``finding.statements[].text`` as ``[CODE] ...``, the typed graph edges, the
resolved symbolic references and the unit attributes the builder stored
(``source_text``, ``bind_references``, ``inputs``).

Every hotspot is a *candidate* for architecture review, not a verdict. Each
type below declares:

* evidence contract -- what must be present in the Blueprint for it to fire;
* severity rule     -- how much the evidence supports, never more;
* uncertainty       -- what the evidence cannot establish.

POSSIBLE_API_BYPASS (``API_BYPASS_CANDIDATE``)
    Evidence: the engine signal ``DIRECT_DML_BYPASSES_API`` on a Forms unit,
    whose unit writes a table reference that resolves to a supplied TABLE which
    at least one packaged database subprogram also writes, and the unit does not
    call that subprogram. Co-writing alone proves only that two layers write the
    same table; it does not prove that the package is the authoritative owner.
    Severity: MEDIUM for co-writing only; HIGH when the co-writing subprogram
    carries measurably more guards (locking, explicit failure, affected-row
    checks) than the unit. Never CRITICAL by itself -- the unit's measured risk
    stays visible separately on its finding.

DUPLICATED_RULE_CLUSTER
    Evidence: engine signals ``LOGIC_DUPLICATED_QUERY``, ``_FORMULA`` or
    ``_PREDICATE`` naming the same packaged subprogram. The match is structural
    (same query shape, arithmetic skeleton or literal set), not semantic
    equivalence. Severity: MEDIUM for one copy; HIGH when copies exist in two
    or more modules.

GLOBAL_STATE_COUPLING
    Evidence: Forms units in two or more modules reference the same
    ``:GLOBAL`` variable (the lexer already excluded comments and literals).
    Severity: MEDIUM when shared; HIGH when one module is observed assigning it
    and a different module references it. A unit that both assigns and reads a
    variable is recorded as a reference only, so write access is a lower bound.

Identities are SHA-256 digests of the hotspot type and its anchoring Blueprint
identities, so they are independent of process, hash seed and input order.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict

from .modernization import guard_strength

HOTSPOT_API_BYPASS = "API_BYPASS_CANDIDATE"
HOTSPOT_DUPLICATED_RULE = "DUPLICATED_RULE_CLUSTER"
HOTSPOT_GLOBAL_STATE = "GLOBAL_STATE_COUPLING"

HOTSPOT_TYPES = (HOTSPOT_API_BYPASS, HOTSPOT_DUPLICATED_RULE, HOTSPOT_GLOBAL_STATE)
HOTSPOT_LABELS = {
    HOTSPOT_API_BYPASS: "Possible API bypass",
    HOTSPOT_DUPLICATED_RULE: "Duplicated business-rule candidate",
    HOTSPOT_GLOBAL_STATE: "Global state coupling",
}
HOTSPOT_SEVERITIES = ("HIGH", "MEDIUM")
SUMMARY_KEYS = {
    HOTSPOT_API_BYPASS: "api_bypass",
    HOTSPOT_DUPLICATED_RULE: "duplicated_rules",
    HOTSPOT_GLOBAL_STATE: "global_state",
}

# Units the Forms layer owns; database subprograms are the other side of a pair.
FORMS_UNIT_TYPES = frozenset({"TRIGGER", "PROGRAM_UNIT"})
DATABASE_WRITER_TYPES = frozenset({"SUBPROGRAM_BODY"})
DUPLICATION_CODES = ("LOGIC_DUPLICATED_QUERY", "LOGIC_DUPLICATED_FORMULA",
                     "LOGIC_DUPLICATED_PREDICATE")
_CODE = re.compile(r"^\[([A-Z][A-Z0-9_]*)\]")
MAX_LISTED = 25  # bounded member lists inside one hotspot


def signal_codes(finding: dict) -> frozenset:
    """The structural signal codes the engine recorded on one finding.

    The reasoning pass writes each signal as a statement ``[CODE] text``; that
    prefix is the canonical carrier. Explanatory prose is never read as proof.
    """
    codes = set()
    statements = finding.get("statements") if isinstance(finding, dict) else None
    for statement in statements if isinstance(statements, list) else ():
        text = statement.get("text") if isinstance(statement, dict) else None
        match = _CODE.match(text) if isinstance(text, str) else None
        if match:
            codes.add(match.group(1))
    return frozenset(codes)


def hotspot_id(kind: str, *anchors: str) -> str:
    """Stable identity: SHA-256 over the type and its anchoring identities."""
    payload = json.dumps([kind, *sorted(anchors)], ensure_ascii=False, separators=(",", ":"))
    return "hotspot:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


class _Estate:
    """Read-only indexes over one Blueprint, built once per projection."""

    def __init__(self, blueprint: dict):
        blueprint = blueprint if isinstance(blueprint, dict) else {}
        self.entities = {e["id"]: e for e in _rows(blueprint.get("entities"))}
        self.findings = {f["id"]: f for f in _rows(blueprint.get("findings"))}
        self.edges = sorted(_rows(blueprint.get("edges")), key=lambda e: e["id"])
        self.findings_by_entity = defaultdict(list)
        for finding in self.findings.values():
            self.findings_by_entity[finding.get("entity")].append(finding)
        self.out = defaultdict(list)
        for edge in self.edges:
            self.out[edge.get("source")].append(edge)
        # A Forms module is identified by its logical source; its FORM entity names it.
        self.form_names = {}
        for entity in self.entities.values():
            if entity.get("type") == "FORM" and entity.get("module"):
                self.form_names.setdefault(entity["module"], entity.get("name") or entity["module"])
        self.subprograms = {}
        for entity in self.entities.values():
            if entity.get("type") in DATABASE_WRITER_TYPES:
                self.subprograms.setdefault(str(entity.get("name", "")).upper(), entity["id"])

    def entity(self, identity) -> dict:
        return self.entities.get(identity, {})

    def attributes(self, identity) -> dict:
        value = self.entity(identity).get("attributes")
        return value if isinstance(value, dict) else {}

    def resolved(self, identity) -> str | None:
        """The supplied database object a symbolic reference resolves to, if unique."""
        entity = self.entity(identity)
        if entity.get("type") in {"TABLE", "VIEW"}:
            return identity
        target = entity.get("resolved_target")
        if entity.get("resolution") == "RESOLVED_TO_DATABASE_OBJECT" and target in self.entities:
            return target
        return None

    def written_tables(self, unit_id) -> dict:
        """Resolved TABLE id -> WRITES edge ids for one unit."""
        tables = defaultdict(list)
        for edge in self.out.get(unit_id, ()):
            if edge.get("type") != "WRITES":
                continue
            table = self.resolved(edge.get("target"))
            if table and self.entity(table).get("type") == "TABLE":
                tables[table].append(edge["id"])
        return tables

    def called_names(self, unit_id) -> set:
        """Qualified names of the database subprograms a unit calls.

        A call resolves to the specification; the writer is the body. Both carry
        the same qualified name, which is the identity compared here.
        """
        called = set()
        for edge in self.out.get(unit_id, ()):
            if edge.get("type") == "CALLS":
                target = self.resolved(edge.get("target"))
                if target:
                    called.add(str(self.entity(target).get("name", "")).upper())
        return called

    def unit_label(self, unit_id) -> str:
        entity = self.entity(unit_id)
        owner = self.attributes(unit_id).get("owner")
        name = str(entity.get("name") or unit_id)
        return f"{owner}.{name}" if owner else name

    def module_label(self, module: str) -> str:
        return self.form_names.get(module) or module


def _rows(values):
    return [v for v in values if isinstance(v, dict) and isinstance(v.get("id"), str)] \
        if isinstance(values, list) else []


def _source(estate: _Estate, identity) -> str:
    text = estate.attributes(identity).get("source_text")
    return text if isinstance(text, str) else ""


def _finding_refs(estate: _Estate, unit_ids) -> tuple[list, list]:
    finding_ids, evidence = set(), set()
    for unit in unit_ids:
        for finding in estate.findings_by_entity.get(unit, ()):
            finding_ids.add(finding["id"])
            evidence.update(e for e in finding.get("evidence", []) if isinstance(e, str))
    return sorted(finding_ids), sorted(evidence)[:MAX_LISTED]


def _hotspot(kind, *, anchors, severity, title, statement, module, entity_id, affected,
             finding_ids, evidence_refs, edge_refs, evidence, uncertainty, action):
    return {
        "id": hotspot_id(kind, *anchors),
        "hotspot_type": kind,
        "label": HOTSPOT_LABELS[kind],
        "classification": "CANDIDATE",
        "severity": severity,
        "title": title,
        "statement": statement,
        "module": module,
        "entity_id": entity_id,
        "affected_entities": sorted(set(affected))[:MAX_LISTED],
        "finding_ids": finding_ids[:MAX_LISTED],
        "evidence_refs": evidence_refs,
        "edge_refs": sorted(set(edge_refs))[:MAX_LISTED],
        "evidence": evidence,
        "uncertainty": list(uncertainty),
        "recommended_action": action,
    }


def detect_api_bypass_candidates(blueprint: dict, estate: _Estate | None = None) -> list[dict]:
    """Forms units writing a table a packaged database subprogram also writes."""
    estate = estate or _Estate(blueprint)
    writers_by_table = defaultdict(dict)  # TABLE id -> {subprogram id: [edge ids]}
    for identity, entity in estate.entities.items():
        if entity.get("type") in DATABASE_WRITER_TYPES:
            for table, edges in estate.written_tables(identity).items():
                writers_by_table[table][identity] = edges
    hotspots = []
    for finding in sorted(estate.findings.values(), key=lambda f: f["id"]):
        unit = finding.get("entity")
        if (estate.entity(unit).get("type") not in FORMS_UNIT_TYPES
                or "DIRECT_DML_BYPASSES_API" not in signal_codes(finding)):
            continue
        called = estate.called_names(unit)
        unit_guards = guard_strength(_source(estate, unit))
        for table, unit_edges in sorted(estate.written_tables(unit).items()):
            co_writers = {w: e for w, e in writers_by_table.get(table, {}).items()
                          if str(estate.entity(w).get("name", "")).upper() not in called}
            if not co_writers:
                continue
            ranked = sorted(((guard_strength(_source(estate, w)), estate.entity(w).get("name", w), w)
                             for w in co_writers), key=lambda r: (-r[0], r[1], r[2]))
            best_guards, best_name, _ = ranked[0]
            guard_gap = best_guards - unit_guards
            severity = "HIGH" if guard_gap >= 1 else "MEDIUM"
            table_name = str(estate.entity(table).get("name", table))
            module = str(estate.entity(unit).get("module", ""))
            label = estate.unit_label(unit)
            finding_ids, evidence_refs = _finding_refs(estate, [unit])
            writer_edges = [edge for w in co_writers for edge in co_writers[w]]
            uncertainty = [
                ("Co-writing shows two layers write the same table; it does not prove which "
                 "one is the authoritative owner."),
                ("Guards are counted lexically (locking, explicit failure, affected-row checks); "
                 "their business meaning requires review."),
                "Database triggers, grants and callers outside the supplied sources are unknown.",
            ]
            hotspots.append(_hotspot(
                HOTSPOT_API_BYPASS,
                anchors=[unit, table],
                severity=severity,
                title=f"Possible API bypass: {table_name}",
                statement=(f"{label} in {estate.module_label(module)} writes {table_name} directly; "
                           f"{best_name} also writes {table_name} and is not called by this unit."),
                module=module,
                entity_id=unit,
                affected=[unit, table, *co_writers],
                finding_ids=finding_ids,
                evidence_refs=evidence_refs,
                edge_refs=[*unit_edges, *writer_edges],
                evidence={
                    "table": table_name,
                    "potential_existing_api_owners": [r[1] for r in ranked][:MAX_LISTED],
                    "unit_guard_strength": unit_guards,
                    "co_writer_guard_strength": best_guards,
                    "guard_gap": guard_gap,
                    "unit_calls_co_writer": False,
                    "engine_signal": "DIRECT_DML_BYPASSES_API",
                },
                uncertainty=uncertainty,
                action=(f"Architecture review required: confirm whether writes to {table_name} "
                        f"must go through {best_name} before choosing a target design."),
            ))
    return hotspots


def detect_duplicated_rule_clusters(blueprint: dict, estate: _Estate | None = None) -> list[dict]:
    """Units the engine matched structurally against one packaged subprogram."""
    estate = estate or _Estate(blueprint)
    clusters = defaultdict(lambda: {"units": set(), "codes": set()})
    for finding in estate.findings.values():
        codes = signal_codes(finding) & set(DUPLICATION_CODES)
        if not codes:
            continue
        owner = str(finding.get("suggested_target", "")).strip().upper()
        if not owner:
            continue
        clusters[owner]["units"].add(finding.get("entity"))
        clusters[owner]["codes"].update(codes)
    hotspots = []
    for owner, data in sorted(clusters.items()):
        units = sorted(u for u in data["units"] if u in estate.entities)
        if not units:
            continue
        modules = sorted({str(estate.entity(u).get("module", "")) for u in units})
        owner_id = estate.subprograms.get(owner)
        severity = "HIGH" if len(modules) >= 2 else "MEDIUM"
        finding_ids, evidence_refs = _finding_refs(estate, units)
        edge_refs = [e["id"] for u in units for e in estate.out.get(u, ())
                     if e.get("type") == "DUPLICATES_LOGIC" and e.get("target") == owner_id]
        hotspots.append(_hotspot(
            HOTSPOT_DUPLICATED_RULE,
            anchors=[owner_id or owner],
            severity=severity,
            title=f"Duplicated business-rule candidate: {owner}",
            statement=(f"{len(units)} Forms unit(s) in {len(modules)} module(s) re-implement the "
                       f"structure of {owner}."),
            module=modules[0] if len(modules) == 1 else "",
            entity_id=owner_id,
            affected=[*units, *([owner_id] if owner_id else [])],
            finding_ids=finding_ids,
            evidence_refs=evidence_refs,
            edge_refs=edge_refs,
            evidence={
                "database_subprogram": owner,
                "match_kinds": sorted(data["codes"]),
                "occurrences": len(units),
                "modules": [estate.module_label(m) for m in modules][:MAX_LISTED],
                "units": [estate.unit_label(u) for u in units][:MAX_LISTED],
            },
            uncertainty=[
                ("The match is structural (query shape, arithmetic skeleton or literal set), "
                 "not proof that both copies implement the same business rule."),
                "Legitimate local variations may exist; confirm with the business owner.",
            ],
            action=(f"Architecture review required: decide whether {owner} is the single home "
                    "for this rule before re-implementing it in a target."),
        ))
    return hotspots


def detect_global_state_couplings(blueprint: dict, estate: _Estate | None = None) -> list[dict]:
    """``:GLOBAL`` variables referenced by Forms units in two or more modules."""
    estate = estate or _Estate(blueprint)
    variables = defaultdict(lambda: {"units": set(), "writers": set(), "readers": set(), "edges": []})
    for identity, entity in estate.entities.items():
        if entity.get("type") not in FORMS_UNIT_TYPES:
            continue
        attributes = estate.attributes(identity)
        references = attributes.get("bind_references")
        inputs = attributes.get("inputs")
        references = set(references) if isinstance(references, list) else set()
        inputs = set(inputs) if isinstance(inputs, list) else set()
        module = str(entity.get("module", ""))
        for edge in estate.out.get(identity, ()):
            target = estate.entity(edge.get("target"))
            if edge.get("type") != "REFERENCES" or target.get("type") != "GLOBAL_REFERENCE":
                continue
            name = str(target.get("name", "")).upper()
            if name not in references:
                continue
            data = variables[name]
            data["units"].add(identity)
            data["edges"].append(edge["id"])
            (data["writers"] if name not in inputs else data["readers"]).add(module)
    hotspots = []
    for name, data in sorted(variables.items()):
        modules = sorted({str(estate.entity(u).get("module", "")) for u in data["units"]})
        if len(modules) < 2:
            continue
        cross_flow = any(w != r for w in data["writers"] for r in data["readers"])
        severity = "HIGH" if cross_flow else "MEDIUM"
        units = sorted(data["units"])
        finding_ids, evidence_refs = _finding_refs(estate, units)
        variable = ":" + name
        hotspots.append(_hotspot(
            HOTSPOT_GLOBAL_STATE,
            anchors=[name],
            severity=severity,
            title=f"Global state coupling: {variable}",
            statement=f"{variable} is referenced by Forms units in {len(modules)} modules.",
            module="",
            entity_id=units[0],
            affected=units,
            finding_ids=finding_ids,
            evidence_refs=evidence_refs,
            edge_refs=data["edges"],
            evidence={
                "variable": variable,
                "modules": [estate.module_label(m) for m in modules][:MAX_LISTED],
                "observed_writers": [estate.module_label(m) for m in sorted(data["writers"])],
                "observed_readers": [estate.module_label(m) for m in sorted(data["readers"])],
                "units": [estate.unit_label(u) for u in units][:MAX_LISTED],
            },
            uncertainty=[
                "Static references only: runtime order, initialization and lifetime are unknown.",
                ("A unit that both assigns and reads the variable is recorded as a reference, "
                 "so observed writers are a lower bound."),
            ],
            action=(f"Architecture review required: decide how {variable} is passed between "
                    "modules (parameters, page state or session context)."),
        ))
    return hotspots


def detect_estate_hotspots(blueprint: dict) -> dict:
    """All hotspot candidates, in one deterministic order."""
    estate = _Estate(blueprint)
    detected = (detect_api_bypass_candidates(blueprint, estate)
                + detect_duplicated_rule_clusters(blueprint, estate)
                + detect_global_state_couplings(blueprint, estate))
    rank = {value: index for index, value in enumerate(HOTSPOT_SEVERITIES)}
    order = {value: index for index, value in enumerate(HOTSPOT_TYPES)}
    detected.sort(key=lambda h: (rank[h["severity"]], order[h["hotspot_type"]], h["title"], h["id"]))
    by_type = {SUMMARY_KEYS[kind]: sum(h["hotspot_type"] == kind for h in detected)
               for kind in HOTSPOT_TYPES}
    return {"total": len(detected), "by_type": by_type, "hotspots": detected}
