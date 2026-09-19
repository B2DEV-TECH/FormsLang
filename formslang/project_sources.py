"""Exact-byte local snapshots and composition of the existing source parsers."""

from __future__ import annotations

import copy
import hashlib
import tempfile
from collections import Counter, defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, fields, is_dataclass, replace
from pathlib import Path

from . import database, parser
from .model import FormModule
from .project_discovery import (
    DB_FAMILIES,
    MAX_SOURCE_BYTES,
    DiscoveryResult,
    SourceDiagnostic,
    authorized_roots,
    diagnostic,
)
from .project_manifest import ManifestEntry, fingerprint_sources, source_id
from .project_model import ProjectError

SOURCE_PIPELINE_VERSION = 'project-sources/1'


@dataclass(frozen=True)
class StagedSources:
    manifest: tuple[ManifestEntry, ...]
    paths: dict[str, Path]


@dataclass(frozen=True)
class ParsedSources:
    modules: list[FormModule]
    source_keys: list[str]
    database: database.DatabaseProject
    diagnostics: tuple[SourceDiagnostic, ...]
    inventory: dict


@contextmanager
def stage_sources(access, descriptor, discovery: DiscoveryResult, *, checkpoint):
    locations = authorized_roots(access, descriptor)
    directory = access.root / '.formslang' / 'runs'
    if directory.resolve() != directory:
        raise ProjectError('Project staging directory was redirected')
    checkpoint()
    directory.mkdir(parents=True, exist_ok=True)
    manifest, paths = [], {}
    with tempfile.TemporaryDirectory(prefix='formslang-stage-', dir=directory) as work:
        for entry in discovery.entries:
            checkpoint()
            candidate = entry.candidate
            fingerprint = fingerprint_sources(access.root, descriptor.source_roots,
                (candidate,), max_bytes=MAX_SOURCE_BYTES)[0]
            if candidate.selected and fingerprint.status == 'available':
                source = locations[candidate.root_id] / candidate.relative_path
                destination = Path(work) / (fingerprint.source_id + source.suffix.lower())
                try:
                    if not source.resolve().is_relative_to(locations[candidate.root_id]):
                        raise PermissionError('Source escaped authorized root')
                    digest = hashlib.sha256()
                    read = 0
                    with source.open('rb') as incoming, destination.open('xb') as outgoing:
                        while chunk := incoming.read(min(1024 * 1024, MAX_SOURCE_BYTES - read + 1)):
                            checkpoint()
                            read += len(chunk)
                            if read > MAX_SOURCE_BYTES:
                                break
                            digest.update(chunk)
                            outgoing.write(chunk)
                    if read == fingerprint.size_bytes and digest.hexdigest() == fingerprint.sha256:
                        paths[fingerprint.source_id] = destination
                    else:
                        fingerprint = replace(fingerprint, status='changed', sha256=None)
                except InterruptedError:
                    raise
                except (OSError, RuntimeError):
                    fingerprint = replace(fingerprint, status='unreadable', sha256=None)
            manifest.append(fingerprint)
        yield StagedSources(tuple(sorted(manifest, key=lambda e: e.source_id)), paths)


def _normalize_sources(value, logical: str):
    if is_dataclass(value):
        for field in fields(value):
            if field.name == 'source_file':
                setattr(value, field.name, logical)
            else:
                _normalize_sources(getattr(value, field.name), logical)
    elif isinstance(value, dict):
        for child in value.values():
            _normalize_sources(child, logical)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _normalize_sources(child, logical)


def parse_staged(descriptor, discovery: DiscoveryResult, staged: StagedSources, *,
                 checkpoint, progress) -> ParsedSources:
    modules, keys, diagnostics = [], [], list(discovery.diagnostics)
    merged = database.DatabaseProject()
    definitions = defaultdict(list)
    manifest = {e.source_id: e for e in staged.manifest}
    selected = sorted((e.candidate for e in discovery.entries if e.candidate.selected),
        key=lambda c: (c.representation != 'xml', c.root_id, c.relative_path))
    totals = Counter('FORMS_PARSING' if c.representation == 'xml' else 'DATABASE_PARSING' for c in selected)
    processed = Counter()
    current_phase = None
    content_seen = {}

    def warn(candidate, code, message, remediation='Correct this source and refresh analysis.'):
        diagnostics.append(diagnostic(candidate.root_id, candidate.relative_path,
            code, message, remediation, 'FORMS_PARSING' if candidate.representation == 'xml' else 'DATABASE_PARSING'))

    for candidate in selected:
        checkpoint()
        identity = source_id(candidate.root_id, candidate.relative_path)
        entry = manifest[identity]
        phase = 'FORMS_PARSING' if candidate.representation == 'xml' else 'DATABASE_PARSING'
        if current_phase is not None and current_phase != phase:
            progress({'phase': current_phase, 'processed': processed[current_phase],
                      'total': totals[current_phase], 'warnings_count': len(diagnostics)})
        current_phase = phase
        progress({'phase': phase, 'processed': processed[phase], 'total': totals[phase],
                  'warnings_count': len(diagnostics)})
        processed[phase] += 1
        logical = candidate.root_id + '/' + candidate.relative_path
        if entry.status != 'available' or identity not in staged.paths:
            code = {'missing': 'SOURCE_MISSING', 'too_large': 'SOURCE_TOO_LARGE',
                    'changed': 'SOURCE_CHANGED', 'blocked': 'SOURCE_BLOCKED'}.get(entry.status, 'SOURCE_UNREADABLE')
            warn(candidate, code, 'The selected source could not be safely staged.')
            continue
        if entry.sha256 in content_seen:
            warn(candidate, 'IDENTICAL_CONTENT', 'Another logical source has identical content; both identities are retained.',
                 'Confirm that both source locations belong to the intended scope.')
        content_seen[entry.sha256] = identity
        try:
            path = staged.paths[identity]
            if candidate.representation == 'xml':
                module = parser.parse_xml(path)
                module.source_path = logical
                modules.append(module)
                keys.append(logical)
            elif candidate.representation == 'database':
                parsed = database.parse_database_file(path)
                if not any(getattr(parsed, family) for family in DB_FAMILIES):
                    warn(candidate, 'UNSUPPORTED_SQL', 'No supported database objects were parsed.',
                         'Supply table/view/package source; unsupported SQL requires human review.')
                else:
                    _normalize_sources(parsed, logical)
                    merged.files.append(logical)
                    for family in DB_FAMILIES:
                        for name, obj in getattr(parsed, family).items():
                            definitions[(family, name)].append((candidate, obj))
        except ValueError as exc:
            position = getattr(exc.__cause__, 'position', None)
            detail = f' at line {position[0]}, column {position[1]}' if position else ''
            code = 'UNSUPPORTED_XML' if 'no <FormModule>' in str(exc) else 'INVALID_XML' if candidate.representation == 'xml' else 'INVALID_DATABASE_SOURCE'
            warn(candidate, code, 'Source could not be parsed' + detail + '.',
                 'Check the exported representation and retry.')
        except OSError:
            warn(candidate, 'STAGED_SOURCE_UNREADABLE', 'Staged source could not be read.')
    for (family, name), objects in sorted(definitions.items()):
        if len(objects) > 1:
            for candidate, _ in objects:
                warn(candidate, 'DUPLICATE_DB_OBJECT', 'Conflicting database object definitions were excluded from reasoning.',
                     'Select the authoritative definition and refresh analysis.')
        else:
            getattr(merged, family)[name] = objects[0][1]
    merged.files.sort()
    inventory = copy.deepcopy(discovery.inventory)
    inventory['forms']['analyzed'] = len(modules)
    inventory['database'] = {family: len(getattr(merged, family)) for family in DB_FAMILIES}
    inventory['database']['packages'] = len(set(merged.package_specs) | set(merged.package_bodies))
    # Deduplicate preview/parse diagnostics without changing immutable source content.
    diagnostics = sorted(set(diagnostics), key=lambda d: (d.source_id, d.stage, d.error_code))
    inventory['warnings'] = len(diagnostics)
    if current_phase is not None:
        progress({'phase': current_phase, 'processed': processed[current_phase], 'total': totals[current_phase],
                  'warnings_count': len(diagnostics)})
    return ParsedSources(modules, keys, merged, tuple(diagnostics), inventory)
