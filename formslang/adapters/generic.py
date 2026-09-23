"""Target-neutral assessment package (the "Generic Modernization" target).

The package is built exclusively from the normalized delivery snapshot that
Overview, Review and Reports already share (``ProjectReportService.capture``).
It never reads raw Blueprint entities, so it cannot lose module identity, risk,
review state or human decisions, and it cannot distribute source bodies, view
SQL, reviewer notes or host paths: every field crosses an explicit allowlist.

Semantics that must survive export:

* the engine recommendation stays the engine's, labelled ``PROPOSED``;
* a recorded human decision is shown next to it, never instead of it;
* review status, staleness and unresolved state are carried as recorded;
* missing evidence stays ``UNKNOWN`` -- never a safer-looking default.

The archive is deterministic for one logical snapshot: members are sorted,
timestamps and permissions fixed, and ``manifest.json`` inside the archive
hashes every other member. The archive's own digest is recorded outside it.
"""

from __future__ import annotations

import hashlib
import io
import json
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from ..project_model import GENERIC_TARGET, ProjectError, TargetProfile

PACKAGE_SCHEMA = "formslang-assessment-package/1"
PACKAGE_NAME = "assessment-package.zip"
ESTATE_SCOPE = "all"
MANIFEST = "manifest.json"
MEMBERS = (
    "README.md",
    "assessment/findings.json",
    "assessment/findings.csv",
    "assessment/hotspot-candidates.json",
    "assessment/investigation-groups.json",
    "assessment/investigation-groups.md",
    "assessment/decision-records.json",
    "assessment/decision-records.md",
    "assessment/interface-catalog.json",
)
FINDING_COLUMNS = (
    "finding_id", "finding_revision", "module", "component", "source_type", "observed_risk",
    "intervention", "engine_recommendation", "engine_recommendation_status", "engine_suggestion",
    "human_decision", "review_status", "stale", "unresolved", "signals", "hotspot_ids",
    "evidence_refs",
)
RISKS = frozenset({"CRITICAL", "HIGH", "MEDIUM", "LOW", "UNKNOWN"})
REVIEW_STATUSES = frozenset({"Pending", "Accepted", "Changed", "Needs Review", "Deferred",
                             "Needs Revalidation"})
MAX_MEMBERS = 32
MAX_MEMBER_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 128 * 1024 * 1024
LIMITATIONS = [
    "Target-neutral assessment material. No executable code is generated.",
    "Engine recommendations are PROPOSED until a human decision is recorded.",
    "Hotspots are candidates for architecture review, not verdicts.",
    "Investigation groups are not a migration schedule, effort or readiness estimate.",
    "Package validation checks structure and integrity only, not architecture or target syntax.",
    "Source bodies, view SQL, reviewer notes and host paths are not included.",
]


def _unknown(value):
    return value if isinstance(value, str) and value.strip() else "UNKNOWN"


def finding_rows(snapshot: dict) -> list[dict]:
    """One allowlisted row per finding, joined to its recorded review state."""
    from ..project_review import STATES

    decisions = {d["finding_id"]: d for d in snapshot["decisions"]}
    rows = []
    for row in snapshot["inventory"]["findings"]:
        decision = decisions.get(row["id"], {})
        state = row.get("review_state", "PENDING")
        rows.append({
            "finding_id": row["id"],
            "finding_revision": row.get("finding_revision") or decision.get("finding_revision"),
            "module": _unknown(row.get("module")),
            "component": _unknown(row.get("name")),
            "source_type": _unknown(row.get("source_type")),
            "observed_risk": row.get("risk") if row.get("risk") in RISKS else "UNKNOWN",
            "intervention": _unknown(row.get("intervention")),
            "engine_recommendation": _unknown(row.get("recommendation")),
            "engine_recommendation_status": "PROPOSED",
            "engine_suggestion": row.get("target") or "",
            "human_decision": decision.get("human_decision"),
            "review_status": STATES.get(state, "Needs Review"),
            "stale": state == "STALE",
            "unresolved": state not in {"APPROVE", "MODIFY"},
            "signals": list(row.get("signals", ())),
            "hotspot_ids": list(row.get("hotspot_ids", ())),
            "evidence_refs": list(row.get("evidence_refs", ())),
        })
    return sorted(rows, key=lambda r: r["finding_id"])


def interface_catalog(snapshot: dict) -> dict:
    """Database interface identities and module relationships -- never definitions."""
    inventory = snapshot["inventory"]
    return {
        "packages": [{"name": r["name"], "specification": r.get("spec"), "body": r.get("body"),
                      "subprograms": r.get("subprograms"), "findings": r.get("findings"),
                      "highest_risk": r.get("highest_risk")} for r in inventory["packages"]],
        "tables": [{"name": r["name"], "columns": r.get("columns"), "constraints": r.get("constraints"),
                    "findings": r.get("findings"), "highest_risk": r.get("highest_risk")}
                   for r in inventory["tables"]],
        "views": [{"name": r["name"], "findings": r.get("findings"), "highest_risk": r.get("highest_risk")}
                  for r in inventory["views"]],
        "module_relationships": snapshot["relationships"],
    }


def _zip(members: dict[str, bytes]) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(members):
            entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o644 << 16
            entry.create_system = 3
            archive.writestr(entry, members[name])
    return stream.getvalue()


def build_package(snapshot: dict) -> tuple[bytes, dict]:
    """Deterministic package bytes and the manifest recorded inside them."""
    from ..estate_triage import investigation_markdown
    from ..project_report_render import (
        csv_bytes,
        decision_records,
        decision_records_markdown,
        markdown,
        public_value,
    )
    from ..project_reports import SNAPSHOT_SCHEMA, json_bytes

    if not isinstance(snapshot, dict) or snapshot.get("schema") != SNAPSHOT_SCHEMA:
        raise ProjectError("The assessment package requires the normalized delivery snapshot.")
    snapshot = public_value(snapshot)
    overview = snapshot["overview"]
    findings = finding_rows(snapshot)
    hotspots = list(snapshot["inventory"]["hotspots"])
    groups = snapshot["investigation_groups"]
    records = decision_records(snapshot["decisions"], hotspots)
    provenance = {
        "project_id": overview["project"]["id"],
        "project_name": overview["project"]["name"],
        "target": overview["project"]["target"],
        "formslang_version": snapshot["formslang_version"],
        "snapshot_revision": snapshot["snapshot_revision"],
        **{key: overview["assessment"][key] for key in (
            "analysis_revision", "source_revision", "review_revision", "assessment_timestamp", "freshness")},
    }
    members = {
        "README.md": (
            b"# Target-neutral modernization assessment package\n\n"
            b"Built from one saved FormsLang assessment snapshot. Start with assessment/findings.csv\n"
            b"and assessment/decision-records.md. Engine recommendations are PROPOSED; recorded\n"
            b"human decisions appear beside them. No executable code, schedule or estimate is included.\n"
        ),
        "assessment/findings.json": json_bytes({"metadata": provenance, "rows": findings}),
        "assessment/findings.csv": csv_bytes(findings, list(FINDING_COLUMNS)),
        "assessment/hotspot-candidates.json": json_bytes({"metadata": provenance, "rows": hotspots}),
        "assessment/investigation-groups.json": json_bytes(groups),
        "assessment/investigation-groups.md": investigation_markdown(groups, markdown).encode("utf-8"),
        "assessment/decision-records.json": json_bytes({"metadata": provenance, "rows": records}),
        "assessment/decision-records.md": decision_records_markdown(overview, records).encode("utf-8"),
        "assessment/interface-catalog.json": json_bytes(interface_catalog(snapshot)),
    }
    manifest = {
        "schema": PACKAGE_SCHEMA,
        "scope": ESTATE_SCOPE,
        "provenance": provenance,
        "limitations": LIMITATIONS,
        "counts": {"findings": len(findings), "hotspot_candidates": len(hotspots),
                   "recorded_decisions": sum(r["kind"] == "RECORDED" for r in records),
                   "proposed_decisions": sum(r["kind"] == "PROPOSED" for r in records)},
        "covers": "every archive member except manifest.json",
        "files": {name: hashlib.sha256(data).hexdigest() for name, data in sorted(members.items())},
    }
    members[MANIFEST] = json_bytes(manifest)
    return _zip(members), manifest


def _safe_member(name: str) -> bool:
    path = PurePosixPath(name)
    return (bool(name) and not path.is_absolute() and ".." not in path.parts and "\\" not in name
            and ":" not in name and not name.startswith("/") and "\0" not in name)


def validate_package(data: bytes) -> dict:
    """Inspect a package without extracting it; every failure is a diagnostic."""
    diagnostics: list[str] = []

    def fail(message):
        diagnostics.append(message)

    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        return {"valid": False, "diagnostics": [f"Not a readable ZIP archive: {exc}"]}
    with archive:
        entries = archive.infolist()
        names = [e.filename for e in entries]
        if len(entries) > MAX_MEMBERS:
            fail(f"Too many members: {len(entries)} > {MAX_MEMBERS}")
        if len(set(names)) != len(names):
            fail("Duplicate archive members")
        total = 0
        for entry in entries:
            total += entry.file_size
            if not _safe_member(entry.filename):
                fail(f"Unsafe member path: {entry.filename!r}")
            if stat.S_ISLNK(entry.external_attr >> 16):
                fail(f"Symbolic link member: {entry.filename}")
            if entry.flag_bits & 0x1:
                fail(f"Encrypted member: {entry.filename}")
            if entry.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
                fail(f"Unsupported compression: {entry.filename}")
            if entry.file_size > MAX_MEMBER_BYTES:
                fail(f"Member exceeds size limit: {entry.filename}")
        if total > MAX_TOTAL_BYTES:
            fail("Package exceeds decompressed size limit")
        expected = set(MEMBERS) | {MANIFEST}
        if set(names) != expected:
            missing, extra = sorted(expected - set(names)), sorted(set(names) - expected)
            fail(f"Package members differ from the contract: missing {missing}, unexpected {extra}")
        if diagnostics:
            return {"valid": False, "diagnostics": diagnostics}
        content = {name: archive.read(name) for name in names}
    documents = {}
    for name, value in content.items():
        if name.endswith(".json"):
            try:
                documents[name] = json.loads(value.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                fail(f"Malformed JSON in {name}: {exc}")
    if diagnostics:
        return {"valid": False, "diagnostics": diagnostics}
    manifest = documents[MANIFEST]
    if not isinstance(manifest, dict) or manifest.get("schema") != PACKAGE_SCHEMA:
        return {"valid": False, "diagnostics": ["Unsupported or missing manifest schema"]}
    files = manifest.get("files")
    if not isinstance(files, dict) or set(files) != set(MEMBERS):
        fail("Manifest does not cover exactly the package members")
    else:
        for name, digest in files.items():
            if hashlib.sha256(content[name]).hexdigest() != digest:
                fail(f"Hash mismatch for {name}")
    findings = documents["assessment/findings.json"]
    rows = findings.get("rows") if isinstance(findings, dict) else None
    hotspots_doc = documents["assessment/hotspot-candidates.json"]
    hotspots = hotspots_doc.get("rows") if isinstance(hotspots_doc, dict) else None
    groups = documents["assessment/investigation-groups.json"]
    records_doc = documents["assessment/decision-records.json"]
    records = records_doc.get("rows") if isinstance(records_doc, dict) else None
    if not isinstance(rows, list):
        fail("findings.json must hold a rows list")
        rows = []
    if not isinstance(hotspots, list):
        fail("hotspot-candidates.json must hold a rows list")
        hotspots = []
    if not isinstance(records, list):
        fail("decision-records.json must hold a rows list")
        records = []
    if not isinstance(groups, dict) or not isinstance(groups.get("groups"), list):
        fail("investigation-groups.json must hold a groups list")
        groups = {"groups": []}
    finding_ids, hotspot_ids = set(), set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != set(FINDING_COLUMNS):
            fail("A finding row does not match the declared columns")
            continue
        finding_ids.add(row["finding_id"])
        if row["observed_risk"] not in RISKS:
            fail(f"Unknown risk value in {row['finding_id']}")
        if row["review_status"] not in REVIEW_STATUSES:
            fail(f"Unknown review status in {row['finding_id']}")
        if row["engine_recommendation_status"] != "PROPOSED":
            fail(f"Engine recommendation must stay PROPOSED in {row['finding_id']}")
    for hotspot in hotspots:
        if not isinstance(hotspot, dict) or not isinstance(hotspot.get("id"), str):
            fail("A hotspot row has no identity")
            continue
        hotspot_ids.add(hotspot["id"])
        if set(hotspot.get("finding_ids", [])) - finding_ids:
            fail(f"Hotspot {hotspot['id']} references unknown findings")
    for row in rows:
        if isinstance(row, dict) and set(row.get("hotspot_ids", [])) - hotspot_ids:
            fail(f"Finding {row.get('finding_id')} references unknown hotspots")
    for record in records:
        if not isinstance(record, dict) or record.get("kind") not in {"RECORDED", "PROPOSED"}:
            fail("A decision record has an unknown kind")
        elif record["kind"] == "RECORDED" and record.get("finding_id") not in finding_ids:
            fail("A recorded decision references an unknown finding")
    counts = manifest.get("counts", {})
    if counts.get("findings") != len(rows) or counts.get("hotspot_candidates") != len(hotspots):
        fail("Manifest counts disagree with package content")
    return {"valid": not diagnostics, "diagnostics": diagnostics}


class GenericModernizationAdapter:
    """Target-neutral assessment package. Experimental adapter surface for 2.1.

    Production generation calls ``generate_deliverables`` through
    ``ProjectGenerationService``; there is no second generation pipeline.
    """

    id: str = "generic_modernize"
    display_name: str = "Target-neutral assessment package"
    target_version: str = GENERIC_TARGET.version
    target_profile: TargetProfile = GENERIC_TARGET

    def capabilities(self) -> dict[str, bool]:
        return {
            "supports_code_generation": False,
            "supports_offline_validation": True,
            "supports_layout_fidelity": False,
            "supports_wave_planning": False,
            "supports_backlog_export": True,
        }

    def interpret_intent(self, intent: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        raise ProjectError("Target-neutral packages keep the engine recommendation; no intent mapping is applied.")

    def evaluate_eligibility(self, module_id: str, project_state: dict[str, Any]) -> dict[str, Any]:
        blockers = []
        if module_id != ESTATE_SCOPE:
            blockers.append({"code": "SCOPE_NOT_SUPPORTED",
                             "message": "The assessment package covers the whole analyzed estate."})
        if not project_state.get("snapshot"):
            blockers.append({"code": "NO_SNAPSHOT", "message": "Analyze the project first."})
        return {"eligible": not blockers, "blockers": blockers, "warnings": []}

    def generate_deliverables(self, module_id: str, reviewed_scope: dict[str, Any],
                              output_path: str) -> dict[str, Any]:
        if module_id != ESTATE_SCOPE:
            raise ProjectError("The assessment package scope must be the explicit whole estate ('all').")
        data, manifest = build_package(reviewed_scope.get("snapshot"))
        output = Path(output_path)
        output.mkdir(parents=True, exist_ok=True)
        package = output / PACKAGE_NAME
        package.write_bytes(data)
        return {"manifest": manifest, "package_path": str(package),
                "sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)}

    def validate_deliverables(self, package_path: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        path = Path(package_path)
        if not path.is_file():
            return {"valid": False, "status": "NOT_VALIDATED", "engine_name": "FormsLang package check",
                    "diagnostics": ["Package not found."]}
        verdict = validate_package(path.read_bytes())
        return {**verdict, "status": "PACKAGE_VERIFIED" if verdict["valid"] else "PACKAGE_INVALID",
                "engine_name": "FormsLang package check"}


__all__ = ["PACKAGE_NAME", "PACKAGE_SCHEMA", "GenericModernizationAdapter", "build_package", "validate_package"]
