"""Evidence-first application knowledge and modernization recommendations.

No I/O, providers, generated code or runtime assertions belong in this engine.
The output is a versioned, deterministic JSON document, suitable for human review.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path

from . import dashboard, depgraph, plsql, risk, rules
from .analysis import ENGINE_VERSION as ANALYSIS_ENGINE_VERSION
from .analysis import analyze_unit
from .assess import PortfolioAssessment, assess_module
from .model import FormModule
from .plsql_evidence import VERSION as LEXER_VERSION
from .store import PENDING, TaskView

VERSION = "blueprint/1"
ENGINE_VERSION = f"blueprint-analysis/1+{LEXER_VERSION}+{ANALYSIS_ENGINE_VERSION}"
DECISIONS = ("PRESERVE", "CONVERT", "REFACTOR", "WRAP_AS_API", "DROP",
             "MANUAL_REVIEW", "UNKNOWN")
CATEGORIES = ("UI_BEHAVIOR", "BUSINESS_RULE", "DATA_ACCESS", "NAVIGATION",
              "TRANSACTION_CONTROL", "INTEGRATION", "FRAMEWORK_OR_INFRASTRUCTURE", "UNKNOWN")
REVIEW_ACTIONS = ("APPROVE", "MODIFY", "REJECT", "DEFER")
COVERAGE = ("PRESERVED", "CONVERTED", "REFACTORED", "DROPPED_INTENTIONALLY",
            "REQUIRES_REVIEW", "UNSUPPORTED", "UNKNOWN")
FACT, INFERENCE, ASSUMPTION, UNKNOWN = "FACT", "INFERENCE", "ASSUMPTION", "UNKNOWN"

LIMITATIONS = [
    "Static syntax is evidence of a reference, not proof that a call executes or an object exists.",
    "Unqualified names are shared symbolic references; schema, synonym and overload resolution are unknown.",
    "Invocation syntax may denote a subprogram, object method or indexed collection; no type resolution is performed.",
    "Callee bodies, external callers, privileges, database state and runtime behavior are unknown unless supplied.",
    "SQL extraction is lexical: dynamic SQL, quoted identifiers, remote sources and complex SQL require review.",
    "Code locations are lines/offsets within decoded PL/SQL bodies, not XML or FMB file lines.",
    "Modernization coverage records human declarations; it does not verify functional parity.",
    "Existing catalog scores and fingerprints retain their published legacy lexical semantics.",
]


def canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def identifier(kind: str, *parts: str) -> str:
    return kind.lower() + ":" + digest(list(parts))[:24]


def statement(level: str, text: str, evidence=()) -> dict:
    return {"level": level, "text": text, "evidence": list(evidence)}


def _classify(events: list[dict], tokens, kind: str) -> tuple[list[str], str]:
    names = {e["name"] for e in events if e["kind"] == "CALL"}
    words = [t.value for t in tokens if t.kind == "word"]
    categories = set()
    # Co-occurrence is a candidate signal, explicitly not a control-flow proof.
    rejection = "FORM_TRIGGER_FAILURE" in words or "RAISE_APPLICATION_ERROR" in names
    if ("IF" in words or "CASE" in words) and rejection:
        categories.add("BUSINESS_RULE")
    if any(e["kind"] in {"READS", "WRITES", "SEQUENCE", "DYNAMIC_SQL"} for e in events):
        categories.add("DATA_ACCESS")
    if any(e["kind"] == "TRANSACTION" for e in events):
        categories.add("TRANSACTION_CONTROL")
    for name in names:
        spec = rules.spec_for(name)
        category = spec.category
        if category in {"external", "client_platform", "reporting"} or name in {"HOST", "USER_EXIT", "WEB.SHOW_DOCUMENT"}:
            categories.add("INTEGRATION")
        elif category in {"navigation", "form_navigation"} or name.startswith(("GO_", "NEXT_", "PREVIOUS_")):
            categories.add("NAVIGATION")
        elif "transaction" in category or name in {"COMMIT_FORM", "DO_COMMIT", "POST", "ROLLBACK"}:
            categories.add("TRANSACTION_CONTROL")
        elif category == "dynamic_sql":
            categories.add("DATA_ACCESS")
        elif name in rules.BUILTINS or any(name.startswith(p) for p in rules.CLIENT_SIDE_PREFIXES):
            categories.add("UI_BEHAVIOR")
    if not categories and any(name.startswith(("DBMS_OUTPUT.", "DBMS_APPLICATION_INFO.", "DBMS_UTILITY.")) for name in names):
        categories.add("FRAMEWORK_OR_INFRASTRUCTURE")
    if not categories:
        categories.add("UNKNOWN")
    primary = next(c for c in ("BUSINESS_RULE", "INTEGRATION", "TRANSACTION_CONTROL",
                               "DATA_ACCESS", "NAVIGATION", "UI_BEHAVIOR",
                               "FRAMEWORK_OR_INFRASTRUCTURE", "UNKNOWN") if c in categories)
    return sorted(categories), primary


class _Builder:
    def __init__(self, title: str):
        self.title = title
        self.entities: dict[str, dict] = {}
        self.edges: dict[str, dict] = {}
        self.evidence: dict[str, dict] = {}
        self.findings: dict[str, dict] = {}
        self.units: dict[str, dict] = {}
        self.local: dict[tuple[str, str, str], str] = {}
        self.forms: dict[str, list[str]] = defaultdict(list)
        self.app = self.node("APPLICATION", title, "", evidence=[])

    def proof(self, module, component, text, *, source="", event=None, level=FACT):
        row = {"level": level, "module": module, "component": component,
               "source": source, "text": text}
        if event:
            row["location"] = {"basis": "decoded_body", "line": event["line"],
                               "start": event["start"], "end": event["end"]}
        eid = identifier("evidence", canonical(row))
        self.evidence[eid] = {"id": eid, **row}
        return eid

    def node(self, entity_type, name, module, *, evidence=(), identity="", **attrs):
        nid = identifier(entity_type, module, identity or name)
        if nid not in self.entities:
            self.entities[nid] = {"id": nid, "type": entity_type, "name": name,
                                  "module": module, "evidence": [], "attributes": {},
                                  "review_state": "PENDING"}
        node = self.entities[nid]
        node["evidence"] = sorted(set(node["evidence"]) | set(evidence))
        node["attributes"].update(attrs)
        return nid

    def edge(self, src, dst, kind, proof, *, level=FACT):
        row = {"source": src, "target": dst, "type": kind, "level": level,
               "evidence": [proof]}
        eid = identifier("edge", src, dst, kind, proof)
        self.edges[eid] = {"id": eid, **row}

    def reference(self, kind, name, proof):
        return self.node(kind, name.upper(), "", evidence=[proof], external=True,
                         resolution="SYMBOLIC_REFERENCE")

    def structure(self, mod, key):
        graph = depgraph.build(mod, include_code=False)
        root = None
        names = {"module": "FORM", "table": "TABLE_OR_VIEW_REFERENCE"}
        mapping = {}
        # Query edges are replaced by the evidence extractor below. The existing
        # graph remains the single structural relationships implementation.
        for n in graph.nodes.values():
            if n.kind == depgraph.TABLE:
                continue
            typ = names.get(n.kind, n.kind.upper())
            if n.missing:
                typ += "_REFERENCE"
            proof = self.proof(key, n.name, "Forms2XML object or property reference: " + n.name,
                               source=key)
            shared = n.external and typ in {"LIBRARY", "MENU"}
            nid = self.node(typ, n.name, "" if shared else key, evidence=[proof],
                            **n.attrs, missing=n.missing, external=n.external)
            self.local[key, n.kind, n.name.upper()] = nid
            mapping[n.id] = nid
            if typ == "FORM":
                root = nid
                self.forms[mod.name.upper()].append(nid)
                self.edge(self.app, nid, "CONTAINS", proof)
        for edge in graph.edges:
            if edge.kind == depgraph.QUERIES or edge.src not in mapping or edge.dst not in mapping:
                continue
            src, dst = mapping[edge.src], mapping[edge.dst]
            proof = self.proof(key, self.entities[src]["name"], edge.evidence or "Forms2XML containment",
                               source=key)
            kind = "USES_LOV" if self.entities[dst]["type"] in {"LOV", "LOV_REFERENCE"} else edge.kind.upper()
            self.edge(src, dst, kind, proof)
        for typ, objects in (("CANVAS", mod.canvases), ("WINDOW", mod.windows)):
            for obj in objects:
                name = obj if isinstance(obj, str) else obj.name
                proof = self.proof(key, name, f"Forms2XML {typ} declaration", source=key)
                nid = self.node(typ, name, key, evidence=[proof])
                self.local[key, typ.lower(), name.upper()] = nid
                self.edge(root, nid, "CONTAINS", proof)
        for b in mod.blocks:
            bid = self.local[key, "block", b.name.upper()]
            if b.database_block and b.query_data_source_name:
                name = b.query_data_source_name.strip()
                proof = self.proof(key, b.name, "QueryDataSourceName: " + name, source=key)
                # A query data source may be a procedure; don't call it a table.
                self.entities[bid]["evidence"].append(proof)
                if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_$#]*(?:\.[A-Za-z_][A-Za-z0-9_$#]*){0,2}", name):
                    typ = "TABLE_OR_VIEW_REFERENCE" if b.query_data_source_type.upper() in {"TABLE", "VIEW"} else "DATABASE_OBJECT_REFERENCE"
                    tid = self.reference(typ, name, proof)
                    self.edge(bid, tid, "REFERENCES", proof)
                    self.entities[tid]["attributes"]["query_source_type"] = b.query_data_source_type
                else:
                    self.entities[bid]["attributes"]["unresolved_query_source"] = name
                    self.sql(bid, key, "QueryDataSourceName", name)
            for prop, sql in (("WhereClause", b.where_clause), ("OrderByClause", b.order_by_clause)):
                self.sql(bid, key, prop, sql)
            for item in b.items:
                if item.canvas:
                    iid = self.local[key, "item", f"{b.name}.{item.name}".upper()]
                    canvas = self.local.get((key, "canvas", item.canvas.upper()))
                    if canvas:
                        proof = self.proof(key, item.name, "CanvasName: " + item.canvas, source=key)
                        self.edge(iid, canvas, "REFERENCES", proof)
        for rg in mod.record_groups:
            self.sql(self.local[key, "record_group", rg.name.upper()], key, "RecordGroupQuery", rg.query)
        return root

    def sql(self, nid, module, component, source):
        for event in plsql.evidence(source)["events"]:
            if event["kind"] in {"READS", "WRITES", "SEQUENCE"}:
                proof = self.proof(module, component, source[event["start"]:event["end"]],
                                   source=module, event=event)
                typ = "SEQUENCE_REFERENCE" if event["kind"] == "SEQUENCE" else "TABLE_OR_VIEW_REFERENCE"
                dst = self.reference(typ, event["name"], proof)
                self.edge(nid, dst, "REFERENCES" if event["kind"] == "SEQUENCE" else event["kind"], proof)

    def register_units(self, mod, key, root):
        for kind, values in (("TRIGGER", mod.all_triggers), ("PROGRAM_UNIT", mod.program_units)):
            for obj in values:
                owner = getattr(obj, "owner", "")
                subtype = getattr(obj, "kind", "")
                proof = self.proof(key, f"{owner}.{obj.name}".strip("."),
                                   f"Forms2XML {kind} declaration", source=key)
                identity = f"{owner}|{obj.name}|{subtype}"
                nid = self.node(kind, obj.name, key, evidence=[proof], identity=identity,
                                owner=owner, subtype=subtype)
                parent = self.local.get((key, "item" if "." in owner else "block", owner.upper()), root)
                self.edge(parent, nid, "CONTAINS", proof)
                if kind == "PROGRAM_UNIT":
                    self.local[key, "program_unit", obj.name.upper()] = nid
                self.units[nid] = {"source": obj.text, "kind": kind, "name": obj.name,
                                   "module": key, "owner": owner, "subtype": subtype}

    def unit(self, nid, unit):
        source, key = unit["source"], unit["module"]
        lexical = plsql.evidence(source)
        events = lexical["events"]
        proofs, unresolved = [], []
        for e in events:
            proof = self.proof(key, unit["name"], source[e["start"]:e["end"]], source=key, event=e)
            proofs.append(proof)
            typ, name = e["kind"], e["name"]
            if typ == "CALL":
                local = self.local.get((key, "program_unit", name))
                spec = rules.spec_for(name)
                if local:
                    self.edge(nid, local, "USES_PROGRAM_UNIT", proof)
                elif spec.known:
                    dst = self.reference("BUILTIN", name, proof)
                    self.edge(nid, dst, "INVOKES_BUILTIN", proof)
                    if name in {"COMMIT_FORM", "DO_COMMIT"}:
                        self.edge(nid, dst, "COMMITS", proof)
                    elif name == "EXECUTE_QUERY":
                        self.edge(nid, dst, "EXECUTES_QUERY", proof)
                else:
                    dst = self.reference("ROUTINE_REFERENCE", name, proof)
                    self.edge(nid, dst, "CALLS", proof)
                    if "." in name:
                        package = self.reference("PACKAGE_REFERENCE", name.rsplit(".", 1)[0], proof)
                        self.edge(dst, package, "REFERENCES", proof, level=INFERENCE)
                    unresolved.append("Callee resolution/body unavailable: " + name)
            elif typ in {"READS", "WRITES", "SEQUENCE"}:
                dst = self.reference("SEQUENCE_REFERENCE" if typ == "SEQUENCE" else "TABLE_OR_VIEW_REFERENCE", name, proof)
                self.edge(nid, dst, "REFERENCES" if typ == "SEQUENCE" else typ, proof)
            elif typ == "BIND":
                dst = self.local.get((key, "item", name))
                if not dst:
                    shared = name.startswith("GLOBAL.")
                    dst = self.node("GLOBAL_REFERENCE" if shared else "BIND_REFERENCE", name,
                                    "" if shared else key, evidence=[proof], missing=True)
                self.edge(nid, dst, "REFERENCES", proof)
            elif typ == "LITERAL_TARGET":
                target_kind = e["target_kind"]
                if target_kind == "form":
                    matches = self.forms.get(Path(name.replace("\\", "/")).stem.upper(), [])
                    dst = matches[0] if len(matches) == 1 else self.reference("FORM_REFERENCE", name, proof)
                    self.edge(nid, dst, "OPENS_FORM", proof)
                elif target_kind in {"os_command", "url", "user_exit"}:
                    dst = self.node("INTEGRATION_POINT", name, key, evidence=[proof])
                    self.edge(nid, dst, "DEPENDS_ON", proof)
                else:
                    dst = self.local.get((key, target_kind, name.upper()))
                    if not dst:
                        dst = self.node(target_kind.upper() + "_REFERENCE", name, key,
                                        evidence=[proof], missing=True)
                    self.edge(nid, dst, "NAVIGATES_TO" if e["builtin"].startswith("GO_") else "REFERENCES", proof)
            elif typ in {"UNRESOLVED_TARGET", "DYNAMIC_SQL"}:
                unresolved.append("Runtime target unresolved: " + name)
            elif typ == "TRANSACTION":
                dst = self.reference("BUILTIN", name, proof)
                self.edge(nid, dst, "COMMITS" if name == "COMMIT" else "INVOKES_BUILTIN", proof)
        categories, primary = _classify(events, lexical["tokens"], unit["kind"])
        analysis = analyze_unit(source, kind=unit["kind"].lower(), name=unit["name"],
                                owner=unit["owner"], module=key, task_id=nid,
                                verdict=rules.classify_trigger(unit["name"])[0] if unit["kind"] == "TRIGGER" else rules.UNKNOWN,
                                fingerprint=plsql.fingerprint(source),
                                code=plsql.analyze_evidence(source, lexical)).to_dict()
        calls = {e["name"] for e in events if e["kind"] == "CALL"}
        binds = sorted({e["name"] for e in events if e["kind"] == "BIND"})
        inputs = sorted({e["name"] for e in events if e["kind"] == "BIND" and e.get("access") != "WRITE"})
        coupling = bool(binds or any(rules.spec_for(n).known for n in calls))
        categories = sorted(categories)
        self.entities[nid]["attributes"].update(
            classification=categories, fingerprint=plsql.fingerprint(source),
            source_text=source[:64000], source_truncated=len(source) > 64000,
            source_hash=hashlib.sha256(source.encode()).hexdigest(),
            risk=analysis["risk"], behavior=analysis["behavior"], migration_verdict=analysis["verdict"],
            observed_forms_coupling=coupling, inputs=inputs, bind_references=binds)
        self.entities[nid]["evidence"] = sorted(set(self.entities[nid]["evidence"] + proofs))
        unit.update(analysis=analysis, events=events, coupling=coupling, categories=categories)
        unresolved.extend(x["reason"] for x in lexical["unknown"])
        if unit.get("subtype", "").lower().endswith("spec"):
            unresolved.append("Package specification does not establish implementation behavior.")
        if "BUSINESS_RULE" in categories:
            rid = self.node("BUSINESS_RULE", "Conditional rejection candidate: " + unit["name"],
                            key, evidence=proofs, identity=nid, inputs=inputs,
                            classification=INFERENCE, lifecycle=unit["kind"], source_entity=nid)
            if proofs:
                self.edge(nid, rid, "CONTAINS", proofs[0], level=INFERENCE)
            unit["rule_id"] = rid
        classes = {f["migration_class"] for f in analysis["findings"]}
        decision, target, reason = "MANUAL_REVIEW", "Human architecture review", "Available evidence does not establish a direct conversion."
        if not lexical["tokens"]:
            decision, reason = "UNKNOWN", "Empty body; no behavioral evidence."
        elif calls and all(rules.spec_for(c).verdict == rules.DROP for c in calls) and all(
            t.value in calls | {"BEGIN", "END", "NULL"} for t in lexical["tokens"] if t.kind == "word"
        ) and not any(e["kind"] in {"BIND", "WRITES", "READS", "TRANSACTION"} for e in events):
            decision, target = "DROP", "Omit obsolete Forms runtime behavior after review"
            reason = "The complete observed body consists only of catalog NOT_REQUIRED calls; a human must confirm intentional removal."
        elif "INTEGRATION" in categories or rules.UNSUPPORTED in classes or "TRANSACTION_CONTROL" in categories:
            reason = "Integration or transaction behavior requires an explicit architecture decision."
        elif "BUSINESS_RULE" in categories or rules.ARCHITECTURAL_REDESIGN in classes:
            decision, target = "REFACTOR", "Reviewed APEX validation or domain PL/SQL"
            reason = "Conditional rejection or catalog redesign signal is coupled to the current lifecycle."
        elif unit["kind"] == "PROGRAM_UNIT" and not coupling and not unresolved:
            decision, target = "PRESERVE", "Existing PL/SQL, subject to deployment review"
            reason = "No Forms-specific coupling was detected by the available analysis. This is not a safety guarantee."
        elif unresolved:
            reason = "Unresolved calls or runtime targets require investigation."
        elif analysis["verdict"] in {rules.AUTO, rules.ASSISTED}:
            decision, target, reason = "CONVERT", "Oracle APEX", "Catalog supports a conversion approach; semantic review remains required."
        elif primary == "UNKNOWN":
            decision, reason = "UNKNOWN", "No supported semantic signal was identified."
        self.findings[nid] = {"id": nid, "entity": nid, "recommendation": decision,
            "suggested_target": target, "reason": reason, "classification": categories,
            "execution_verdict": analysis["verdict"], "migration_classes": sorted(classes),
            "human_review_required": True, "evidence": sorted(set(proofs)),
            "statements": [statement(INFERENCE, reason, proofs),
                statement(ASSUMPTION, "The proposed target and required database privileges are available."),
                statement(UNKNOWN, "Runtime equivalence has not been verified.")],
            "unresolved_questions": sorted(set(unresolved)), "source_components": [nid],
            "coverage": {"status": "REQUIRES_REVIEW", "target": "", "evidence": ""}}


def build(modules: list[FormModule], *, title="Forms application", source_keys=None,
          enterprise=False, failures=None, metadata=None) -> dict:
    keys = source_keys or [Path(m.source_path).name or m.name for m in modules]
    if len(keys) != len(modules) or len(set(keys)) != len(keys):
        raise ValueError("source keys must uniquely identify every module")
    b = _Builder(title)
    ordered = sorted(zip(keys, modules), key=lambda pair: pair[0])
    for key, module in ordered:
        root = b.structure(module, key)
        b.register_units(module, key, root)
    for nid, unit in list(b.units.items()):
        b.unit(nid, unit)
    _metadata(b, metadata or [])
    api = _api_candidates(b)
    _structure_findings(b)
    outgoing = defaultdict(set)
    for edge in b.edges.values():
        if edge["type"] != "CONTAINS":
            outgoing[edge["source"]].add(edge["target"])
    for finding in b.findings.values():
        finding["dependencies"] = sorted(outgoing[finding["entity"]])
        # Re-review when any application evidence changes, including shared
        # caller reuse and supplied metadata; never carry an obsolete approval.
    context_hash = digest({"modules": [(key, {**asdict(m), "source_path": key}) for key, m in ordered],
                           "metadata": metadata or [], "enterprise": enterprise,
                           "failures": failures or [], "engine": ENGINE_VERSION})
    for finding in b.findings.values():
        finding["revision"] = digest([VERSION, context_hash, finding])
    assessments = []
    for key, module in ordered:
        assessment = assess_module(module)
        assessment.name = key  # Distinct source files can declare the same module name.
        assessments.append(assessment)
    pf = PortfolioAssessment(modules=assessments)
    pf.finalize()
    assessment = pf.to_dict()
    # Machine-local absolute paths do not belong in reproducible reports.
    for item, (key, _) in zip(assessment["modules"], ordered):
        item["source_path"] = key
    views = [TaskView(task={"id": nid}, proposal=None, state=PENDING, code="", comment="",
                      reviewer="", decided_at="", analysis=u["analysis"]) for nid, u in b.units.items()]
    result = {"schema_version": VERSION, "engine_version": ENGINE_VERSION,
        "application": {"id": b.app, "name": title, "sources": sorted(keys)},
        "source_revision": context_hash, "failures": failures or [],
        "entities": sorted(b.entities.values(), key=lambda n: n["id"]),
        "edges": sorted(b.edges.values(), key=lambda e: e["id"]),
        "evidence": sorted(b.evidence.values(), key=lambda e: e["id"]),
        "findings": sorted(b.findings.values(), key=lambda f: f["id"]),
        "api_candidates": api, "enterprise_context": _enterprise(b) if enterprise else {"enabled": False},
        "assessment": assessment,
        "catalog_coverage": {
            "trigger_units": sum(u["kind"] == "TRIGGER" for u in b.units.values()),
            "unknown_trigger_units": sum(u["kind"] == "TRIGGER" and u["analysis"]["verdict"] == rules.UNKNOWN for u in b.units.values()),
            "uncatalogued_invocations": sum(f["count"] for u in b.units.values() for f in u["analysis"]["findings"] if not f["known"]),
            "note": "Uncatalogued invocations include application packages; they are investigation work, not necessarily missing Forms built-ins."},
        "readiness": {**dashboard.readiness(views, []),
            "label": "Migration work progress", "explanation": dashboard.explain(),
            "scope": "Fresh static analysis; no conversion approvals or executed tests inferred."},
        "risk_model": risk.explain(), "limitations": LIMITATIONS,
        "architecture": _architecture(b, api)}
    return summarize(result)


def session_progress(payload, store):
    """Reuse readiness/1 and actual conversion reviews, with fresh static facts.

    Architecture reviews never move this score. Only exact source bodies can
    inherit conversion decisions; cached AI behavior assessments are not used.
    """
    views, matching_tasks = [], set()
    by_source = defaultdict(list)
    for view in store.all_views():
        t = view.task
        key = (t["kind"].upper(), t["owner"], t["name"],
               hashlib.sha256(t["source"].encode()).hexdigest())
        by_source[key].append(view)
    for entity in payload["entities"]:
        attrs = entity["attributes"]
        if "risk" not in attrs:
            continue
        key = (entity["type"], attrs.get("owner", ""), entity["name"], attrs["source_hash"])
        matches = by_source.get(key, [])
        view = matches[0] if len(matches) == 1 else TaskView(
            task={"id": entity["id"]}, proposal=None, state=PENDING, code="", comment="",
            reviewer="", decided_at="")
        if len(matches) == 1:
            matching_tasks.add(view.task["id"])
        view.analysis = {"risk": attrs["risk"], "behavior": attrs["behavior"]}
        views.append(view)
    cases = [c for c in store.all_test_cases() if c["task_id"] in matching_tasks and not c["stale"]]
    payload["readiness"] = {**dashboard.readiness(views, cases),
        "label": "Migration work progress", "explanation": dashboard.explain(),
        "scope": "Existing conversion reviews on identical source bodies and current test specifications; fresh deterministic risk/behavior. Architecture approvals do not affect this score."}
    return payload


def _structure_findings(b):
    for nid, entity in b.entities.items():
        if nid in b.findings or entity["type"] in {"APPLICATION", "BUILTIN", "BUSINESS_RULE"}:
            continue
        typ = entity["type"]
        decision = "CONVERT" if typ in {"FORM", "BLOCK", "ITEM", "LOV", "RECORD_GROUP", "CANVAS", "WINDOW"} else "MANUAL_REVIEW"
        target = "Oracle APEX mapping, subject to human review" if decision == "CONVERT" else "Existing database/integration boundary, subject to review"
        reason = "A Forms2XML component has a modernization mapping to review." if decision == "CONVERT" else "A reference alone cannot establish implementation, ownership or safe reuse."
        b.findings[nid] = {"id": nid, "entity": nid, "recommendation": decision,
            "suggested_target": target, "reason": reason, "classification": [],
            "human_review_required": True, "evidence": entity["evidence"],
            "source_components": [nid], "unresolved_questions": ["Confirm target behavior and ownership."],
            "statements": [statement(INFERENCE, reason, entity["evidence"]),
                           statement(UNKNOWN, "Runtime behavior and external consumers are not established.")],
            "coverage": {"status": "REQUIRES_REVIEW", "target": "", "evidence": ""}}


def _api_candidates(b):
    out = []
    incoming = defaultdict(set)
    for e in b.edges.values():
        if e["type"] == "CALLS":
            incoming[e["target"]].add(e["source"])
    for nid, callers in incoming.items():
        entity = b.entities[nid]
        forms = sorted({b.entities[c]["module"] for c in callers})
        # An integer prioritization index, not a probability or safety score.
        encapsulated = "." in entity["name"]
        parts = {"form_reuse": min(4, max(0, len(forms) - 1)) * 2,
                 "caller_reuse": min(4, max(0, len(callers) - 1)),
                 "qualified_invocation": int(encapsulated)}
        score = sum(parts.values())
        if len(forms) < 2 or not encapsulated:
            continue
        out.append({"entity": nid, "recommendation": "API_CANDIDATE", "level": INFERENCE,
                    "score": score, "maximum": 13, "components": parts,
                    "formula": "2*min(4, forms-1) + min(4, callers-1) + qualified_invocation",
                    "forms": forms, "callers": sorted(callers), "evidence": entity["evidence"],
                    "observed_callee_coupling": UNKNOWN,
                    "unresolved_questions": ["Callee Forms/runtime coupling, parameter types, transaction ownership, privileges and external consumers must be reviewed."],
                    "suggested_target": "Controlled PL/SQL API boundary; ORDS only if an HTTP consumer justifies it.",
                    "human_review_required": True})
    return sorted(out, key=lambda x: (-x["score"], x["entity"]))


def _metadata(b, objects):
    """Optional user-supplied metadata proves only what the supplied file states."""
    seen = set()
    for obj in objects:
        if not isinstance(obj, dict) or not isinstance(obj.get("name"), str) or obj.get("type") not in {"TABLE", "VIEW", "PACKAGE", "PROCEDURE", "FUNCTION", "SEQUENCE"}:
            raise ValueError("metadata objects require name and TABLE/VIEW/PACKAGE/PROCEDURE/FUNCTION/SEQUENCE type")
        name, typ = obj["name"].upper(), obj["type"]
        if not name.strip() or name in seen:
            raise ValueError("metadata names must be nonempty and unique")
        seen.add(name)
        proof = b.proof("metadata", name, f"User-supplied metadata declares {typ} {name}",
                        source=str(obj.get("source", "metadata.json")))
        nid = b.node("DATABASE_OBJECT", name, "", evidence=[proof], object_type=typ,
                     provenance="USER_SUPPLIED_METADATA")
        for entity in list(b.entities.values()):
            if entity["name"].upper() == name and entity["type"].endswith("REFERENCE"):
                b.edge(entity["id"], nid, "REFERENCES", proof)
        body = obj.get("body", "")
        if not isinstance(body, str):
            raise ValueError("metadata body must be a string")  # noqa: TRY004 -- invalid input document
        if body:
            unit = {"source": body, "kind": "PROGRAM_UNIT", "name": name,
                    "module": "metadata:" + name, "owner": ""}
            b.units[nid] = unit
            b.unit(nid, unit)


def _enterprise(b):
    domains = {"FND": "Application foundation", "AP": "Payables", "AR": "Receivables",
               "PO": "Purchasing", "GL": "General ledger", "FA": "Fixed assets",
               "INV": "Inventory", "ONT": "Order management", "HR": "Human resources"}
    detections = []
    for n in b.entities.values():
        if not n["type"].endswith("REFERENCE"):
            continue
        parts = n["name"].upper().split(".")
        matches = [part for part in parts if "_" in part and part.split("_")[0] in domains]
        custom = any(part.startswith("XX") for part in parts)
        if matches or custom:
            prefix = matches[0].split("_")[0] if matches else ""
            detections.append({"entity": n["id"], "level": INFERENCE,
                "pattern": prefix + "_" if prefix else "XX custom naming",
                "potential_domain": domains.get(prefix, "Unknown"),
                "reference_style": "CUSTOM_LOOKING" if custom else "STANDARD_LOOKING",
                "evidence": n["evidence"],
                "modules": sorted({b.evidence[e]["module"] for e in n["evidence"]})})
    return {"enabled": True, "detections": sorted(detections, key=lambda x: x["entity"]),
            "statement": "Naming patterns only; they do not establish Oracle E-Business Suite installation or domain ownership."}


def _architecture(b, api):
    groups = {"Forms": {"FORM"}, "Embedded PL/SQL": {"TRIGGER", "PROGRAM_UNIT"},
              "Database references": {"DATABASE_OBJECT_REFERENCE", "TABLE_OR_VIEW_REFERENCE", "SEQUENCE_REFERENCE"},
              "PL/SQL references": {"ROUTINE_REFERENCE", "PACKAGE_REFERENCE"},
              "Integrations": {"INTEGRATION_POINT", "REPORT", "LIBRARY", "MENU"}}
    current = [{"name": name, "level": FACT, "entities": sorted(n["id"] for n in b.entities.values() if n["type"] in types)} for name, types in groups.items()]
    targets = [{"name": "Oracle APEX", "level": INFERENCE, "reason": "Candidate replacement for observed Forms UI."},
               {"name": "Existing PL/SQL and Oracle Database", "level": INFERENCE,
                "reason": "Review observed data and routine dependencies before preserving them."}]
    if api:
        targets.append({"name": "Controlled domain API boundary", "level": INFERENCE,
                        "reason": "Repeated qualified invocations are candidates for a reviewed boundary; ORDS is optional."})
    return {"current": [g for g in current if g["entities"]], "target": targets,
            "assumptions": [statement(ASSUMPTION, "Target platform availability and organizational constraints require human confirmation.")],
            "unknowns": [statement(UNKNOWN, "Unprovided applications, databases and consumers are outside observed scope.")]}


def summarize(bp):
    bp["summary"] = {"entities": dict(sorted(Counter(n["type"] for n in bp["entities"]).items())),
                     "dependency_edges": sum(e["type"] != "CONTAINS" for e in bp["edges"]),
                     "decisions": dict(sorted(Counter(f["recommendation"] for f in bp["findings"]).items())),
                     "coverage": dict(sorted(Counter(f["coverage"]["status"] for f in bp["findings"]).items())),
                     "review": dict(sorted(Counter(f.get("review_state", "PENDING") for f in bp["findings"]).items())),
                     "unresolved_findings": sum(bool(f["unresolved_questions"]) for f in bp["findings"]),
                     "failed_sources": len(bp["failures"])}
    return bp


def explore(bp, *, node="", module="", entity_type="", dependency_type="",
            decision="", review="", domain="", risk_level="", query="", offset=0, limit=100):
    """A bounded, textual explorer; all counts state their filtered denominator."""
    limit, offset = min(200, max(1, int(limit))), max(0, int(offset))
    findings = {f["entity"]: f for f in bp["findings"]}
    context = {d["entity"]: d for d in bp["enterprise_context"].get("detections", [])}
    involved = {e[k] for e in bp["edges"] if not dependency_type or e["type"] == dependency_type for k in ("source", "target")}
    module_evidence = {e["id"] for e in bp["evidence"] if e["module"] == module} if module else set()
    nodes = [n for n in bp["entities"] if
             (not module or n["module"] == module or module_evidence.intersection(n["evidence"]))
             and (not entity_type or n["type"] == entity_type)
             and (not dependency_type or n["id"] in involved)
             and (not decision or findings.get(n["id"], {}).get("recommendation") == decision)
             and (not review or findings.get(n["id"], {}).get("review_state", "PENDING") == review)
             and (not domain or context.get(n["id"], {}).get("potential_domain") == domain)
             and (not risk_level or n["attributes"].get("risk", {}).get("level") == risk_level)
             and (not query or query.casefold() in n["name"].casefold())]
    result = {"nodes": sorted(nodes, key=lambda n: (n["name"], n["id"]))[offset:offset + limit],
              "total": len(nodes), "offset": offset, "limit": limit}
    if node:
        selected = next((n for n in bp["entities"] if n["id"] == node), None)
        if selected is None:
            raise ValueError("unknown Blueprint entity")
        edges = [e for e in bp["edges"] if node in (e["source"], e["target"])
                 and (not dependency_type or e["type"] == dependency_type)]
        shown = edges[:limit]
        ids = {p for e in shown for p in e["evidence"]} | set(selected["evidence"])
        neighbor_ids = {e[k] for e in shown for k in ("source", "target")}
        source_entity = next((n for n in bp["entities"] if n["id"] == selected["attributes"].get("source_entity")), selected)
        result["selected"] = {"entity": selected, "source_context": {
                "text": source_entity["attributes"].get("source_text", ""),
                "truncated": source_entity["attributes"].get("source_truncated", False),
                "owner": source_entity["attributes"].get("owner", ""),
                "basis": "decoded_body"},
            "finding": findings.get(node) or findings.get(selected["attributes"].get("source_entity")),
            "inbound": [e for e in shown if e["target"] == node],
            "outbound": [e for e in shown if e["source"] == node],
            "neighbors": [n for n in bp["entities"] if n["id"] in neighbor_ids],
            "edge_total": len(edges), "truncated": len(edges) > limit,
            "evidence": [p for p in bp["evidence"] if p["id"] in ids][:limit],
            "evidence_total": len(ids)}
    return result
