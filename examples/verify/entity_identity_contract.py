"""ADR-06 identity probe, deliberately outside the product code path.

This classifies candidates for review. It never transfers an approval.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

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
               member: str | None = None, signature: str | None = None) -> tuple:
    """Keep components separate so dots inside quoted names are never separators."""
    if not isinstance(kind, str) or not kind or not kind.isascii():
        raise ValueError("invalid object kind")
    return (kind.upper(), oracle_identifier(owner) if owner is not None else None,
            oracle_identifier(name), oracle_identifier(member) if member is not None else None,
            signature)


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
    same_symbol = [item for item in candidates
                   if item.root == before.root and item.key == before.key]
    comparable = [item for item in same_symbol
                  if item.engine == before.engine and item.source_digest == before.source_digest]
    if len(comparable) > 1:
        return "AMBIGUOUS", tuple(comparable)
    if comparable:
        item = comparable[0]
        return ("EXACT" if item.path == before.path else "MOVED_CANDIDATE"), (item,)
    if same_symbol:
        return "NOT_COMPARABLE", ()
    return "REMOVED", ()
