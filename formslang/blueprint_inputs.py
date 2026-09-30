"""Bounded exact-byte staging for direct Blueprint input, outside the parser."""

from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import fields, is_dataclass
from importlib import resources
from pathlib import Path

from .project_manifest import ManifestEntry, engine_identity, source_id
from .project_model import ProjectError


def _direct_engine_identity():
    """Direct-only ingestion changes must not invalidate project assessments."""
    engines = engine_identity()
    try:
        package = resources.files('formslang')
        for name in ('blueprint_inputs', 'blueprint_io'):
            engines[name + '.sha256'] = hashlib.sha256(package.joinpath(name + '.py').read_bytes()).hexdigest()
    except (OSError, TypeError, ModuleNotFoundError) as exc:
        raise ProjectError('ENGINE_IDENTITY_UNAVAILABLE') from exc
    return engines


class _InputSnapshot:
    def __init__(self):
        self._temporary = tempfile.TemporaryDirectory(prefix='formslang-blueprint-')
        self._entries = {}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self._temporary.cleanup()

    @property
    def manifest(self):
        return tuple(self._entries[key] for key in sorted(self._entries))

    def capture(self, root, relative, path, representation, *, max_bytes=256 * 1024 * 1024):
        identity = source_id(root, relative)
        if identity in self._entries:
            raise ValueError('Duplicate direct source identity')
        path = Path(path)
        staged = Path(self._temporary.name) / (identity + path.suffix.lower())
        status, size, digest = 'available', None, None
        try:
            before = path.stat()
            if before.st_size > max_bytes:
                status = 'too_large'
            else:
                size, hasher = 0, hashlib.sha256()
                with path.open('rb') as incoming, staged.open('xb') as outgoing:
                    while chunk := incoming.read(min(1024 * 1024, max_bytes - size + 1)):
                        size += len(chunk)
                        if size > max_bytes:
                            status = 'too_large'
                            break
                        hasher.update(chunk)
                        outgoing.write(chunk)
                after = path.stat()
                if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                        after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                    status = 'changed'
                if status == 'available':
                    digest = hasher.hexdigest()
        except FileNotFoundError:
            status = 'missing'
        except OSError:
            status = 'unreadable'
        self._entries[identity] = ManifestEntry(identity, root, relative, representation,
                                                True, status, size, digest)
        return staged if status == 'available' else None


def _database_inputs(sources):
    """List every supplied SQL input once, retaining paths that cannot be read."""
    paths = [sources] if isinstance(sources, (str, Path)) else sources or []
    files = set()
    for value in paths:
        path = Path(value).resolve()
        if path.is_dir():
            files.update(p for p in path.rglob('*')
                         if p.is_file() and p.suffix.lower() in {'.sql', '.pks', '.pkb'})
        else:
            files.add(path)
    groups = {}
    for path in sorted(files):
        groups.setdefault(path.anchor, []).append(path)
    result = []
    for index, paths in enumerate(groups.values()):
        base = Path(os.path.commonpath([str(p.parent) for p in paths]))
        root = 'database' if len(groups) == 1 else f'database_{index + 1}'
        result.extend((root, p.relative_to(base).as_posix(), p) for p in paths)
    return result


def _logical_sources(value, mapping):
    """Replace staging locations only in provenance fields, never Oracle text."""
    if is_dataclass(value):
        for field in fields(value):
            current = getattr(value, field.name)
            if field.name == 'source_file':
                setattr(value, field.name, mapping.get(current, current))
            elif field.name == 'files':
                setattr(value, field.name, [mapping.get(path, path) for path in current])
            else:
                _logical_sources(current, mapping)
    elif isinstance(value, dict):
        for child in value.values():
            _logical_sources(child, mapping)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _logical_sources(child, mapping)
