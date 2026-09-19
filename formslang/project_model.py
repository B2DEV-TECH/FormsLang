"""Portable, allowlisted modernization-project metadata (no filesystem authority)."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass


class ProjectError(ValueError):
    """Invalid or unavailable project state; safe for caller remediation."""


class RevisionConflict(ProjectError):
    """The caller's revision is no longer current."""


class ProjectBusy(ProjectError):
    """Another operation holds the project; retry after it finishes."""


@dataclass(frozen=True)
class TargetProfile:
    platform: str = "Oracle APEX"
    version: str = "26.1"
    representation: str = "APEXlang"


@dataclass(frozen=True)
class SourceRoot:
    id: str
    kind: str
    path: str


@dataclass(frozen=True)
class ProjectDescriptor:
    id: str
    name: str
    source_roots: tuple[SourceRoot, ...] = ()
    description: str = ""
    client_label: str = ""
    target: TargetProfile = TargetProfile()
    project_version: str = "formslang-project/1"
    store: str = "project.session.db"
    analysis_revision: str | None = None
    engine_version: str | None = None


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def _text(value, field: str, limit: int, *, required=False) -> None:
    if (not isinstance(value, str) or "\0" in value or len(value) > limit
            or (required and not value.strip())):
        raise ProjectError(f"Invalid project field: {field}")


def validate_descriptor(value: ProjectDescriptor) -> None:
    if not isinstance(value, ProjectDescriptor):
        raise ProjectError("Invalid project descriptor")
    _text(value.id, "id", 32, required=True)
    if not re.fullmatch(r"[a-f0-9]{32}", value.id):
        raise ProjectError("Invalid project id")
    _text(value.name, "name", 200, required=True)
    _text(value.description, "description", 4000)
    _text(value.client_label, "client_label", 200)
    if value.project_version != "formslang-project/1":
        raise ProjectError("Unsupported project format")
    if value.store != "project.session.db":
        raise ProjectError("Invalid project store location")
    if not isinstance(value.target, TargetProfile) or value.target != TargetProfile():
        raise ProjectError("Unsupported target profile")
    if value.analysis_revision is not None:
        _text(value.analysis_revision, "analysis_revision", 64)
        if not re.fullmatch(r"[a-f0-9]{64}", value.analysis_revision):
            raise ProjectError("Invalid analysis revision")
    if value.engine_version is not None:
        _text(value.engine_version, "engine_version", 1000, required=True)
    if not isinstance(value.source_roots, tuple) or len(value.source_roots) > 128:
        raise ProjectError("Invalid source roots")
    seen = set()
    for root in value.source_roots:
        if not isinstance(root, SourceRoot):
            raise ProjectError("Invalid source root")
        _text(root.id, "source root id", 128, required=True)
        if not re.fullmatch(r"[A-Za-z0-9_-]+", root.id) or root.id in seen:
            raise ProjectError("Invalid or duplicate source root id")
        seen.add(root.id)
        if root.kind not in ("forms", "database", "supporting"):
            raise ProjectError("Invalid source root kind")
        _text(root.path, "source root path", 32768, required=True)


def descriptor_to_dict(value: ProjectDescriptor) -> dict:
    validate_descriptor(value)
    payload = asdict(value)
    payload.pop("target")
    payload["source_roots"] = [asdict(root) for root in value.source_roots]
    payload.update(target_platform=value.target.platform, target_version=value.target.version,
                   target_representation=value.target.representation)
    return payload


def descriptor_from_dict(payload: dict) -> ProjectDescriptor:
    allowed = {"id", "name", "description", "client_label", "source_roots", "store",
               "project_version", "analysis_revision", "engine_version", "target_platform",
               "target_version", "target_representation"}
    if not isinstance(payload, dict) or set(payload) - allowed:
        raise ProjectError("Invalid or unknown project fields")
    if not {"id", "name"} <= payload.keys():
        raise ProjectError("Project id and name are required")
    roots = payload.get("source_roots", [])
    if not isinstance(roots, list) or len(roots) > 128:
        raise ProjectError("Invalid source roots")
    if any(not isinstance(r, dict) or set(r) != {"id", "kind", "path"} for r in roots):
        raise ProjectError("Invalid source root fields")
    values = {k: v for k, v in payload.items() if k not in {
        "source_roots", "target_platform", "target_version", "target_representation",
    }}
    project = ProjectDescriptor(**values, source_roots=tuple(SourceRoot(**r) for r in roots),
        target=TargetProfile(payload.get("target_platform", "Oracle APEX"),
                             payload.get("target_version", "26.1"),
                             payload.get("target_representation", "APEXlang")))
    validate_descriptor(project)
    return project
