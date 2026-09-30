"""ADR-06 identity probe, deliberately outside the product code path.

This classifies candidates for review. It never transfers an approval.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass

_UNQUOTED = re.compile(r"[A-Za-z][A-Za-z0-9_$#]*\Z")
_QUOTED = re.compile(r'"[^"\x00]+"\Z')


def oracle_identifier(raw: str) -> str:
    """Decode the parser-supported Oracle identifier subset for a typed key."""
    if not isinstance(raw, str):
        raise TypeError("identifier must be text")
    if _QUOTED.fullmatch(raw):
        return raw[1:-1]
    if _UNQUOTED.fullmatch(raw):
        return raw.upper()
    raise ValueError("unsupported identifier spelling")


def symbol_key(kind: str, owner: str | None, name: str, *,
               member: str | None = None, signature: str | tuple | None = None) -> tuple:
    """Keep components separate so dots inside quoted names are never separators."""
    if not isinstance(kind, str) or not kind or not kind.isascii():
        raise ValueError("invalid object kind")
    return (kind.upper(), oracle_identifier(owner) if owner is not None else None,
            oracle_identifier(name), oracle_identifier(member) if member is not None else None,
            signature)


def declaration_key(declaration, *, member=None) -> tuple:
    """Use raw header spelling and already-decoded member names exactly once."""
    from formslang import database

    header = database._package_header(declaration.header_text,
                                      body=declaration.kind == 'PACKAGE BODY')
    if header is None:
        raise ValueError('package header has no supported identity')
    key = symbol_key(declaration.kind, header.group('owner'), header.group('name'))
    if member is None:
        return key
    signature = (member.subprogram_type,
                 tuple((p.mode, p.data_type) for p in member.parameters), member.return_type)
    kind = 'PACKAGE_SUBPROGRAM' if declaration.kind == 'PACKAGE' else 'SUBPROGRAM_BODY'
    return kind, key[1], key[2], member.name, signature


@dataclass(frozen=True)
class Occurrence:
    root: str
    path: str
    line: int
    ordinal: int
    key: tuple

    def __post_init__(self):
        path = self.path.replace('\\', '/')
        if (not re.fullmatch(r'[A-Za-z0-9_-]+', self.root) or ':' in path or '\0' in path
                or any(part in {'', '.', '..'} for part in path.split('/'))
                or type(self.line) is not int or self.line < 1
                or type(self.ordinal) is not int or self.ordinal < 1):
            raise ValueError('occurrence requires a logical source locator')
        object.__setattr__(self, 'path', path)


def entity_id(analysis: str, occurrence: Occurrence) -> str:
    """An analysis-bound identity, never a cross-analysis decision binding."""
    value = ['oracle-entity/1', analysis, asdict(occurrence)]
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    return 'oracle-entity/1:' + hashlib.sha256(encoded.encode('utf-8')).hexdigest()


@dataclass(frozen=True)
class Resolution:
    status: str
    reason: str
    candidates: tuple[Occurrence, ...]


def resolve(reference: tuple, candidates: list[Occurrence]) -> Resolution:
    """Probe static candidates without a default schema or argument inference."""
    kind, owner, name, member, signature = reference
    compatible = {item for item in candidates
                  if item.key[0] == kind and item.key[2:4] == (name, member)
                  and (owner is None or item.key[1] == owner)
                  and (signature is None or item.key[4] is None or item.key[4] == signature)}
    ordered = tuple(sorted(compatible, key=lambda item: (
        item.root, item.path, item.line, item.ordinal, repr(item.key))))
    if not ordered:
        return Resolution('UNRESOLVED', 'NO_COMPATIBLE_DECLARATION', ())
    if len(ordered) > 1:
        return Resolution('AMBIGUOUS', 'MULTIPLE_DECLARATIONS', ordered)
    if owner is None:
        return Resolution('UNRESOLVED', 'MISSING_SCHEMA_CONTEXT', ordered)
    if (member is not None or signature is not None) and ordered[0].key[4] is None:
        return Resolution('UNRESOLVED', 'INCOMPLETE_SIGNATURE', ordered)
    return Resolution('RESOLVED', 'UNIQUE_STATIC_DECLARATION', ordered)


@dataclass(frozen=True)
class Entity:
    analysis: str
    engine: str
    root: str
    path: str
    source_digest: str
    key: tuple


def classify(before: Entity, candidates: list[Entity]) -> tuple[str, tuple[Entity, ...]]:
    """Find reviewable correspondence without granting a decision binding."""
    matching_key = [item for item in candidates if item.key == before.key]
    same_symbol = [item for item in matching_key if item.root == before.root]
    comparable = [item for item in same_symbol
                  if item.engine == before.engine and item.source_digest == before.source_digest]
    comparable = sorted(set(comparable),
                        key=lambda item: (item.path != before.path, item.path, item.analysis))
    if len(comparable) > 1:
        return "AMBIGUOUS", tuple(comparable)
    if comparable:
        item = comparable[0]
        return ("EXACT" if item.path == before.path else "MOVED_CANDIDATE"), (item,)
    if same_symbol:
        return "NOT_COMPARABLE", ()
    if matching_key:
        return "NOT_COMPARABLE", ()
    if any(item.root == before.root and item.path == before.path for item in candidates):
        # A file can contain many entities. A changed key at that source locator
        # proves neither removal nor which other declaration is a rename.
        return "NOT_COMPARABLE", ()
    if candidates and not any(item.root == before.root for item in candidates):
        # A populated scope from different roots says nothing about removal
        # from the original source namespace, even if every key also changed.
        return "NOT_COMPARABLE", ()
    return "REMOVED", ()
