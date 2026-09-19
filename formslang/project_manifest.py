"""Content-based provenance; callers authorize roots before reading sources."""

from __future__ import annotations

import hashlib
import importlib
import re
import stat
from dataclasses import asdict, dataclass
from importlib import resources
from pathlib import Path, PurePosixPath, PureWindowsPath

from .project_model import ProjectError, SourceRoot, canonical_json


@dataclass(frozen=True)
class SourceCandidate:
    root_id: str
    relative_path: str
    representation: str
    selected: bool = True


@dataclass(frozen=True)
class ManifestEntry:
    source_id: str
    root_id: str
    relative_path: str
    representation: str
    selected: bool
    status: str
    size_bytes: int | None
    sha256: str | None


def relative_source_path(value: str) -> str:
    if not isinstance(value, str) or not value or "\0" in value or ":" in value:
        raise ProjectError("Invalid relative source path")
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    if (path.is_absolute() or PureWindowsPath(value).drive
            or any(p in {"", ".", ".."} for p in normalized.split("/"))):
        raise ProjectError("Invalid relative source path")
    return normalized


def _digest(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def source_id(root_id: str, relative_path: str) -> str:
    if not isinstance(root_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", root_id):
        raise ProjectError("Invalid source root id")
    return _digest([root_id, relative_source_path(relative_path)])


def _identity(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def _fingerprint(root: Path, relative: str, max_bytes: int) -> tuple[str, int | None, str | None]:
    size = None
    try:
        path = (root / relative).resolve()
        if not path.is_relative_to(root):
            return "blocked", None, None
        before = path.stat()
        size = before.st_size
        if not stat.S_ISREG(before.st_mode):
            return "blocked", size, None
        if size > max_bytes:
            return "too_large", size, None
        digest = hashlib.sha256()
        read = 0
        with path.open("rb") as stream:
            while chunk := stream.read(min(1024 * 1024, max_bytes - read + 1)):
                read += len(chunk)
                if read > max_bytes:
                    return "too_large", read, None
                digest.update(chunk)
        if (root / relative).resolve() != path or _identity(before) != _identity(path.stat()):
            return "changed", read, None
        return "available", read, digest.hexdigest()
    except FileNotFoundError:
        return "missing", None, None
    except (OSError, RuntimeError):
        return "unreadable", size, None


def fingerprint_sources(project_root: Path, roots: tuple[SourceRoot, ...],
                        candidates: tuple[SourceCandidate, ...], *,
                        max_bytes: int = 268435456) -> tuple[ManifestEntry, ...]:
    if type(max_bytes) is not int or max_bytes < 0:
        raise ProjectError("Invalid source size limit")
    locations = {r.id: (Path(project_root) / r.path).resolve() for r in roots}
    if len(locations) != len(roots):
        raise ProjectError("Duplicate source roots")
    entries = {}
    for candidate in candidates:
        identity = source_id(candidate.root_id, candidate.relative_path)
        if identity in entries or candidate.root_id not in locations:
            raise ProjectError("Duplicate source or unknown root")
        if (candidate.representation not in {"xml", "binary", "database", "supporting"}
                or type(candidate.selected) is not bool):
            raise ProjectError("Invalid source representation")
        relative = relative_source_path(candidate.relative_path)
        status, size, digest = _fingerprint(locations[candidate.root_id], relative, max_bytes)
        entries[identity] = ManifestEntry(identity, candidate.root_id, relative,
            candidate.representation, candidate.selected, status, size, digest)
    return tuple(entries[key] for key in sorted(entries))


def source_revision(entries: tuple[ManifestEntry, ...], options: dict) -> str:
    if len({e.source_id for e in entries}) != len(entries):
        raise ProjectError("Duplicate manifest identities")
    return _digest({"sources": [asdict(e) for e in sorted(entries, key=lambda e: e.source_id)],
                    "options": options})


def engine_identity() -> dict[str, str]:
    names = ("parser", "database", "analysis", "plsql", "plsql_evidence", "rules",
             "risk", "modernization", "blueprint", "assess", "depgraph", "behavior",
             "dashboard", "testspec", "sensitive", "model", "store", "convert",
             "project_assessment", "project_manifest")
    result = {"project_analysis": "project-analysis/1"}
    try:
        package = resources.files("formslang")
        for name in names:
            result[name + ".sha256"] = hashlib.sha256(package.joinpath(name + ".py").read_bytes()).hexdigest()
            module = importlib.import_module("formslang." + name)
            for attr in sorted(name for name in vars(module) if name.isupper() and name.endswith("VERSION")):
                if isinstance(value := getattr(module, attr, None), str):
                    result[name + "." + attr] = value
    except (OSError, TypeError, ModuleNotFoundError) as exc:
        raise ProjectError("ENGINE_IDENTITY_UNAVAILABLE") from exc
    return result


def analysis_revision(source: str, engines: dict[str, str], options: dict) -> str:
    return _digest({"source": source, "engines": engines, "options": options})
