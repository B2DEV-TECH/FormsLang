"""Offset-preserving lexical evidence used by :mod:`formslang.plsql`.

This is deliberately not a compiler or a name resolver. In particular, a dotted
invocation may be a package call, an object method or an indexed collection.
Evidence describes syntax; the Blueprint qualifies the architectural inference.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

VERSION = "plsql-evidence/1"
_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_$#]*")


@dataclass(frozen=True)
class Token:
    kind: str
    value: str
    start: int
    end: int
    line: int


def tokens(source: str) -> list[Token]:
    """Comments are absent; strings/quoted identifiers remain atomic tokens."""
    out = []
    i, line, size = 0, 1, len(source)
    while i < size:
        start, at_line = i, line
        c = source[i]
        if c.isspace():
            line += c == "\n"
            i += 1
            continue
        if source.startswith("--", i):
            end = source.find("\n", i)
            i = size if end < 0 else end
            continue
        kind = "symbol"
        if source.startswith("/*", i):
            end = source.find("*/", i + 2)
            i = size if end < 0 else end + 2
            kind = "comment" if end >= 0 else "incomplete"
        elif c.lower() == "q" and source[i + 1:i + 2] == "'" and i + 2 < size:
            opener = source[i + 2]
            closer = {"[": "]", "{": "}", "(": ")", "<": ">"}.get(opener, opener)
            end = source.find(closer + "'", i + 3)
            i = size if end < 0 else end + 2
            kind = "string" if end >= 0 else "incomplete"
        elif c in "'\"":
            quote = c
            i += 1
            closed = False
            while i < size:
                if source[i] == quote:
                    i += 1
                    if i < size and source[i] == quote:
                        i += 1
                        continue
                    closed = True
                    break
                i += 1
            kind = ("string" if quote == "'" else "quoted") if closed else "incomplete"
        elif match := _WORD.match(source, i):
            i = match.end()
            kind = "word"
        else:
            i += 1
        value = source[start:i]
        if kind != "comment":
            out.append(Token(kind, value.upper() if kind == "word" else value,
                             start, i, at_line))
        line += value.count("\n")
    return out


def extract(source: str, not_calls: set[str], not_tables: set[str],
            literal_targets: dict) -> dict:
    ts = tokens(source)
    events, unknown = [], []
    excluded_calls: set[int] = set()
    words = {t.value for t in ts if t.kind == "word"}

    def emit(kind, name, first, last=None, **extra):
        last = last or first
        events.append({"kind": kind, "name": name, "line": first.line,
                       "start": first.start, "end": last.end, **extra})

    def name_at(i):
        if i >= len(ts) or ts[i].kind != "word":
            return "", i
        parts = [ts[i].value]
        j = i + 1
        while j + 1 < len(ts) and ts[j].value == "." and ts[j + 1].kind == "word":
            parts.append(ts[j + 1].value)
            j += 2
        return ".".join(parts), j

    # CTE names are local query symbols, not database dependencies.
    ctes = {ts[i].value for i in range(len(ts) - 2)
            if ts[i].kind == "word" and ts[i + 1].value == "AS"
            and ts[i + 2].value == "(" and "WITH" in words}
    expression_stack = []
    statement_start = 0
    for i, t in enumerate(ts):
        v = t.value
        prev = ts[i - 1].value if i else ""
        nxt = ts[i + 1].value if i + 1 < len(ts) else ""
        kind, pos = "", i + 1
        if t.kind != "word":
            if v == "(" and t.kind == "symbol":
                expression_stack.append(prev)
            elif v == ")" and expression_stack:
                expression_stack.pop()
            elif v == ";":
                statement_start = i + 1
            if t.kind in {"quoted", "incomplete"}:
                unknown.append({"line": t.line, "reason": "Quoted or incomplete syntax needs review"})
            continue
        if v in {"FROM", "JOIN"}:
            if not expression_stack or expression_stack[-1] not in {"EXTRACT", "TRIM", "SUBSTRING"}:
                kind = "WRITES" if prev == "DELETE" else "READS"
        elif v == "USING" and any(x.value == "MERGE" for x in ts[statement_start:i]):
            kind = "READS"
        elif (v == "UPDATE" and prev not in {"FOR", "THEN", "BEFORE", "AFTER"}
              or v == "INTO" and prev in {"INSERT", "MERGE"}
              or v == "DELETE" and nxt != "FROM"):
            kind = "WRITES"
        if kind:
            name, end = name_at(pos)
            excluded_calls.add(pos)
            if name and name not in not_tables | ctes and name not in {"OF", "RETURNING"}:
                if end < len(ts) and (ts[end].value == "@" or ts[end].value == "(" and kind == "READS"):
                    unknown.append({"line": t.line, "reason": "Remote or computed SQL source"})
                else:
                    emit(kind, name, t, ts[end - 1])
        if v == "EXECUTE" and nxt == "IMMEDIATE":
            emit("DYNAMIC_SQL", "EXECUTE IMMEDIATE", t, ts[i + 1])
        if v in {"IF", "ELSIF"} and prev != "END":
            stop = i
            while stop + 1 < len(ts) and ts[stop].value not in {"THEN", ";"}:
                stop += 1
            emit("CONDITION", v, t, ts[stop])
        if v == "RAISE" and nxt == "FORM_TRIGGER_FAILURE":
            emit("REJECTION", nxt, t, ts[i + 1])
        if v in {"COMMIT", "ROLLBACK"}:
            emit("TRANSACTION", v, t)
        if v in {"NEXTVAL", "CURRVAL"} and prev == ".":
            start = i - 2
            while start >= 2 and ts[start - 1].value == ".":
                start -= 2
            name, _ = name_at(start)
            emit("SEQUENCE", name.rsplit(".", 1)[0], ts[start], t)

    for i, t in enumerate(ts):
        prev = ts[i - 1].value if i else ""
        name, end = name_at(i)
        if t.value == ":":
            bind, stop = name_at(i + 1)
            if bind:
                assignment = stop + 1 < len(ts) and ts[stop].value == ":" and ts[stop + 1].value == "="
                emit("BIND", bind, t, ts[stop - 1], access="WRITE" if assignment else "REFERENCE")
        if not name or prev in {".", ":"} or i in excluded_calls:
            continue
        if prev in {"PROCEDURE", "FUNCTION", "CURSOR", "TYPE", "PACKAGE", "END", "RAISE"}:
            continue
        after = ts[end].value if end < len(ts) else ""
        bare = after == ";" and prev in {"", ";", "BEGIN", "THEN", "ELSE", "LOOP"}
        if after != "(" and not bare:
            continue
        if name in not_calls | {"VARCHAR2", "VARCHAR", "CHAR", "NUMBER", "RAW",
                                    "TIMESTAMP", "INTERVAL", "SAVEPOINT"}:
            continue
        emit("CALL", name, t, ts[end - 1])
        # Catalog target positions are reused, except runtime modes that never
        # name objects (CLEAR_BLOCK(NO_VALIDATE), NEXT_BLOCK, PREVIOUS_BLOCK).
        mapping = literal_targets.get(name)
        if not mapping or name in {"CLEAR_BLOCK", "CLEAR_ITEM", "NEXT_BLOCK", "PREVIOUS_BLOCK"}:
            continue
        args, current, depth, j = [], [], 0, end + 1
        while after == "(" and j < len(ts):
            item = ts[j]
            if item.value == ")" and depth == 0:
                args.append(current)
                break
            if item.value == "," and depth == 0:
                args.append(current)
                current = []
            else:
                current.append(item)
                if item.kind == "symbol":
                    depth += (item.value == "(") - (item.value == ")")
            j += 1
        target_kind, position = mapping
        arg = args[position - 1] if len(args) >= position else []
        if len(arg) == 1 and arg[0].kind == "string":
            literal = arg[0].value
            value = literal[3:-2] if literal[:2].lower() == "q'" else literal[1:-1].replace("''", "'")
            emit("LITERAL_TARGET", value, t, arg[0], target_kind=target_kind, builtin=name)
        else:
            emit("UNRESOLVED_TARGET", name, t, target_kind=target_kind)
    return {"version": VERSION, "events": sorted(events, key=lambda e: (e["start"], e["kind"])),
            "unknown": unknown, "tokens": ts}
