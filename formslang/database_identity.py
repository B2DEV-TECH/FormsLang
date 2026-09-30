"""Typed Oracle candidates and conservative static selection.

These records are source occurrences, not durable entity IDs or decision bindings.
The caller must supply the complete candidate scope; no default schema is inferred.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass

from . import database
from .project_manifest import analysis_revision, source_id, source_revision
from .project_model import canonical_json


@dataclass(frozen=True)
class SymbolOccurrence:
    key: tuple
    source_file: str
    line: int
    ordinal: tuple[int, int]


@dataclass(frozen=True)
class Resolution:
    status: str
    reason: str
    candidates: tuple[SymbolOccurrence, ...]


@dataclass(frozen=True)
class _AnalysisScope:
    """Internal namespace derived only at verified input boundaries."""

    basis: str
    identity: str | None
    sources: tuple[str, ...] = ()


def _analysis_scope(manifest, *, engines: dict, options: dict, required_source_ids,
                    project_revision: str | None = None) -> _AnalysisScope:
    """Use verified ingestion hashes; never reopen paths or retain source bytes."""
    entries = tuple(sorted(manifest, key=lambda entry: entry.source_id))
    if any(entry.source_id != source_id(entry.root_id, entry.relative_path) for entry in entries):
        raise ValueError('Invalid source identity')
    source = source_revision(entries, options.get('intake', {}))
    if project_revision is not None and project_revision != analysis_revision(source, engines, options):
        raise ValueError('Project analysis revision does not match input context')
    if (not entries or {entry.source_id for entry in entries} != set(required_source_ids)
            or any(entry.status != 'available' or not isinstance(entry.sha256, str)
                   or not re.fullmatch('[a-f0-9]{64}', entry.sha256)
                   or type(entry.size_bytes) is not int or entry.size_bytes < 0
                   for entry in entries)):
        return _AnalysisScope('UNAVAILABLE', None)
    if project_revision is not None:
        return _AnalysisScope('PROJECT_ANALYSIS_REVISION', project_revision,
                              tuple(entry.root_id + '/' + entry.relative_path for entry in entries))
    value = ['direct-blueprint-bytes/1', [asdict(entry) for entry in entries], engines, options]
    identity = hashlib.sha256(canonical_json(value).encode('utf-8')).hexdigest()
    return _AnalysisScope('DIRECT_BLUEPRINT_BYTES', identity,
                          tuple(entry.root_id + '/' + entry.relative_path for entry in entries))


def _entity_id(scope: _AnalysisScope, occurrence: SymbolOccurrence) -> str:
    """Internal identity, requiring explicit immutable input evidence."""
    if scope.identity is None:
        raise ValueError('Analysis identity unavailable')
    path = occurrence.source_file.replace('\\', '/')
    if (':' in path or any(part in {'', '.', '..'} for part in path.split('/'))
            or path not in scope.sources):
        raise ValueError('Entity identity requires a logical source locator')
    value = ['oracle-entity/1', scope.basis, scope.identity,
             {**asdict(occurrence), 'source_file': path}]
    return 'oracle-entity/1:' + hashlib.sha256(canonical_json(value).encode('utf-8')).hexdigest()


def package_symbols(project: database.DatabaseProject) -> list[SymbolOccurrence]:
    """Retain every inventoried package and member, including repeated CREATEs."""
    result = []
    for declaration in project.package_declarations:
        key = (declaration.kind, declaration.owner, declaration.name, None, None)
        result.append(SymbolOccurrence(key, declaration.source_file, declaration.line,
                                       (declaration.order, 0)))
        kind = ('PACKAGE_SUBPROGRAM' if declaration.kind == 'PACKAGE'
                else 'SUBPROGRAM_BODY')
        for ordinal, member in enumerate(declaration.parsed.subprograms, 1):
            signature = (member.subprogram_type,
                         tuple((p.mode, p.data_type) for p in member.parameters),
                         member.return_type)
            key = (kind, declaration.owner, declaration.name, member.name, signature)
            result.append(SymbolOccurrence(key, declaration.source_file,
                                           member.line_number, (declaration.order, ordinal)))
    return sorted(result, key=_order)


def package_occurrence_counts(project: database.DatabaseProject) -> dict[str, int]:
    """Add occurrence totals without changing legacy bare-name map counts."""
    if not project.package_declarations and project.coverage is None:
        return {}  # Older manually supplied models have no inventory evidence.
    return {'package_spec_occurrences': sum(d.kind == 'PACKAGE' for d in project.package_declarations),
            'package_body_occurrences': sum(d.kind == 'PACKAGE BODY' for d in project.package_declarations)}


def _order(item: SymbolOccurrence) -> tuple:
    return item.source_file, item.line, item.ordinal, repr(item.key)


def _reference_parts(reference: str) -> tuple[str, ...] | None:
    identifier = r'(?:"[^"\x00]+"|[A-Za-z][A-Za-z0-9_$#]*)'
    if not re.fullmatch(rf'\s*{identifier}(?:\s*\.\s*{identifier}){{0,2}}\s*', reference):
        return None
    return tuple(database._object_name(part) for part in re.findall(identifier, reference))


def resolve_package_reference(reference: str, candidates: list[SymbolOccurrence], *,
                              signature: tuple | None = None) -> Resolution:
    """Select supplied package-member evidence without inferring argument types."""
    parts = _reference_parts(reference)
    if parts is None or len(parts) not in {2, 3}:
        return Resolution('UNRESOLVED', 'UNSUPPORTED_REFERENCE', ())
    owner, name, member = (None, *parts) if len(parts) == 2 else parts
    matches = {item for item in candidates
               if item.key[0] in {'PACKAGE_SUBPROGRAM', 'SUBPROGRAM_BODY'}
               and item.key[2:4] == (name, member)
               and (owner is None or item.key[1] == owner)
               and (signature is None or item.key[4] is None or item.key[4] == signature)}
    # A declaration and its implementation are not competing callable symbols.
    # Prefer specs per owner so a missing spec in another owner remains visible.
    spec_owners = {item.key[1] for item in matches if item.key[0] == 'PACKAGE_SUBPROGRAM'}
    ordered = tuple(sorted((item for item in matches
                            if item.key[0] == 'PACKAGE_SUBPROGRAM'
                            or item.key[1] not in spec_owners), key=_order))
    if not ordered:
        return Resolution('UNRESOLVED', 'NO_COMPATIBLE_DECLARATION', ())
    if len(ordered) > 1:
        return Resolution('AMBIGUOUS', 'MULTIPLE_DECLARATIONS', ordered)
    if owner is None:
        return Resolution('UNRESOLVED', 'MISSING_SCHEMA_CONTEXT', ordered)
    if ordered[0].key[4] is None:
        return Resolution('UNRESOLVED', 'INCOMPLETE_SIGNATURE', ordered)
    return Resolution('RESOLVED', 'UNIQUE_STATIC_DECLARATION', ordered)
