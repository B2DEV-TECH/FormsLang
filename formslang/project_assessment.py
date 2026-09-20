"""Provenance and review projection around Blueprint, never another classifier."""

from __future__ import annotations

import copy
import re
from dataclasses import asdict

from . import blueprint
from .project_manifest import (
    ManifestEntry,
    analysis_revision,
    relative_source_path,
    source_id,
    source_revision,
)
from .project_model import ProjectDescriptor, ProjectError, canonical_json, validate_descriptor


def bind_assessment(descriptor: ProjectDescriptor, manifest: tuple[ManifestEntry, ...],
                    blueprint_payload: dict, *, engines: dict[str, str], options: dict,
                    analyzed_at: str, status: str) -> dict:
    validate_descriptor(descriptor)
    if "_target" in options:
        raise ProjectError("Reserved analysis option: _target")
    target = asdict(descriptor.target)
    configured = {**copy.deepcopy(options), "_target": target}
    source_rev = source_revision(manifest, options.get("intake", {}))
    revision = analysis_revision(source_rev, engines, configured)
    bound = copy.deepcopy(blueprint_payload)
    bound["source_revision"] = source_rev
    bound["project_analysis_revision"] = revision
    for finding in bound["findings"]:
        finding["engine_finding_revision"] = finding["revision"]
        finding["revision"] = blueprint.digest(["project-finding/1", revision, finding["engine_finding_revision"]])
    result = {"schema_version": "project-assessment/1", "project_id": descriptor.id,
        "source_manifest": [asdict(e) for e in manifest], "source_revision": source_rev,
        "analysis_revision": revision, "engine_identity": copy.deepcopy(engines),
        "analysis_options": configured, "target": target, "status": status,
        "analyzed_at": analyzed_at, "blueprint": bound}
    validate_assessment(descriptor, result)
    return result


def validate_assessment(descriptor: ProjectDescriptor, value: dict) -> None:
    """Persistence boundary, also used by the binder before any database write."""
    try:
        if value["schema_version"] != "project-assessment/1" or value["project_id"] != descriptor.id:
            raise ProjectError("Assessment belongs to another project or format")
        target = asdict(descriptor.target)
        options = value["analysis_options"]
        if value["target"] != target or options["_target"] != target:
            raise ProjectError("Assessment target mismatch")
        entries = tuple(ManifestEntry(**e) for e in value["source_manifest"])
        for entry in entries:
            if entry.source_id != source_id(entry.root_id, entry.relative_path):
                raise ProjectError("Invalid manifest identity")
            if entry.status not in {"available", "missing", "unreadable", "too_large", "changed", "blocked"}:
                raise ProjectError("Invalid manifest status")
        expected_source = source_revision(entries, options.get("intake", {}))
        expected_analysis = analysis_revision(expected_source, value["engine_identity"], options)
        if value["source_revision"] != expected_source or value["analysis_revision"] != expected_analysis:
            raise ProjectError("Assessment revision mismatch")
        if value["status"] not in {"Current", "Incomplete"}:
            raise ProjectError("Invalid assessment status")
        _validate_completion(value)
        if not isinstance(value["analyzed_at"], str) or not value["analyzed_at"].strip():
            raise ProjectError("Assessment timestamp is required")
        bp = value["blueprint"]
        if (bp["schema_version"] != blueprint.VERSION or bp["source_revision"] != expected_source
                or bp["project_analysis_revision"] != expected_analysis):
            raise ProjectError("Blueprint provenance mismatch")
        for finding in bp["findings"]:
            original = finding.get("engine_finding_revision")
            if not isinstance(original, str) or finding["revision"] != blueprint.digest([
                "project-finding/1", expected_analysis, original,
            ]):
                raise ProjectError("Finding revision does not match project analysis")
        if value["status"] == "Current" and (not entries or bp["failures"] or
                any(e.selected and e.status != "available" for e in entries)):
            raise ProjectError("Partial assessment cannot be Current")
        canonical_json(value)
    except (KeyError, TypeError, AttributeError) as exc:
        raise ProjectError("Malformed project assessment") from exc


def _validate_completion(value: dict) -> None:
    added = {'inventory', 'diagnostics', 'completion_state'}
    if not added.intersection(value):
        return  # Phase A snapshots remain readable without synthetic new fields.
    if not added <= value.keys() or not isinstance(value['inventory'], dict):
        raise ProjectError('Incomplete assessment coverage fields')
    completion = value['completion_state']
    diagnostics = value['diagnostics']
    if completion not in {'COMPLETE', 'COMPLETE_WITH_WARNINGS', 'INCOMPLETE'} or not isinstance(diagnostics, list):
        raise ProjectError('Invalid assessment completion or diagnostics')
    if ((completion == 'INCOMPLETE') != (value['status'] == 'Incomplete')
            or (completion == 'COMPLETE' and diagnostics)
            or (completion == 'COMPLETE_WITH_WARNINGS' and not diagnostics)):
        raise ProjectError('Assessment completion disagrees with evidence status')
    required = {'source_id', 'relative_path', 'stage', 'error_code', 'safe_message', 'remediation'}
    for item in diagnostics:
        if not isinstance(item, dict) or set(item) != required or any(not isinstance(v, str) for v in item.values()):
            raise ProjectError('Malformed source diagnostic')
        if not re.fullmatch('[a-f0-9]{64}', item['source_id']):
            raise ProjectError('Invalid diagnostic source identity')
        relative_source_path(item['relative_path'])
        if (any(not re.fullmatch('[A-Z][A-Z0-9_]{0,79}', item[k]) for k in ('stage', 'error_code'))
                or any(not item[k].strip() or len(item[k]) > 2000 or '\0' in item[k]
                       for k in ('safe_message', 'remediation'))):
            raise ProjectError('Invalid diagnostic code or remediation')


def current_assessment(store, *, expected_engines: dict[str, str], freshness=None) -> dict | None:
    # All projections must refer to one read snapshot, including external writers.
    db = store.session.db
    if db.in_transaction:
        raise ProjectError("Assessment read requires its own transaction")
    db.execute("BEGIN")
    try:
        saved = store.load_assessment()
        if saved is None:
            return None
        result = copy.deepcopy(saved)
        reviewed = store.session.blueprint()
        result["blueprint"] = reviewed
        result["review_revision"] = db.execute("SELECT review_revision FROM modernization_project WHERE id=1").fetchone()[0]
        if (saved["engine_identity"] != expected_engines or
                (freshness is not None and (freshness.get('status') != 'CURRENT' or
                 freshness.get('analysis_revision') != saved['analysis_revision']))):
            result["status"] = ("Incomplete" if freshness is not None and freshness.get('status') == 'INCOMPLETE'
                                and freshness.get('analysis_revision') == saved['analysis_revision']
                                and saved['engine_identity'] == expected_engines else "Stale")
            for finding in reviewed["findings"]:
                if finding.get("review_history"):
                    finding["review_state"] = "STALE"
                    finding.pop("human_decision", None)
                    original = next(f for f in saved["blueprint"]["findings"] if f["entity"] == finding["entity"])
                    finding["coverage"] = copy.deepcopy(original["coverage"])
            states = {f["entity"]: f["review_state"] for f in reviewed["findings"]}
            for entity in reviewed["entities"]:
                entity["review_state"] = states.get(entity["id"], states.get(entity["attributes"].get("source_entity"), "PENDING"))
            blueprint.summarize(reviewed)
        return result
    finally:
        db.rollback()
