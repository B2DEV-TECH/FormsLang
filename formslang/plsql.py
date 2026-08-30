"""Static analysis of the PL/SQL embedded in a Forms module.

This is not a full PL/SQL parser -- it is a lexical extractor calibrated to
answer the three questions that decide migration cost:

1. Which Forms built-ins does this code use?
2. Which screen references (``:BLOCK.ITEM``, ``:GLOBAL.X``) does it carry?
3. How much business logic (SQL, cursors, branching) lives here?

Comments and string literals are blanked out before any scan. Without that,
a commented-out ``-- HOST('...')`` would count as an operating-system
dependency and poison the whole assessment.

Blanking the literals costs something, though: ``GO_BLOCK('ORDERS')`` keeps
the call and loses the target. A second, narrower pass runs before that --
over code with the comments removed but the literals intact -- and recovers
the argument for the built-ins whose literal argument names another object.
That is what turns "this calls GO_BLOCK" into "this depends on ORDERS".
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from dataclasses import dataclass, field

from . import rules

# Line comment, block comment and string literal.
_LINE_COMMENT = re.compile(r"--[^\n]*")
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_STRING = re.compile(r"'(?:[^']|'')*'")

# Subprogram call: identifier (optionally dotted) followed by a parenthesis.
_CALL = re.compile(r"\b([A-Za-z_][A-Za-z0-9_$#]*(?:\.[A-Za-z_][A-Za-z0-9_$#]*)?)\s*\(")
# Built-ins used without parentheses (e.g. COMMIT_FORM;  EXIT_FORM;)
_BARE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_$#]*)\s*;")
# Screen references: :BLOCK.ITEM, :GLOBAL.X, :SYSTEM.X, :PARAMETER.X, :ITEM
_BIND = re.compile(r":([A-Za-z_][A-Za-z0-9_$#]*(?:\.[A-Za-z_][A-Za-z0-9_$#]*)?)")

_SQL_VERBS = {
    "select": re.compile(r"\bselect\b", re.IGNORECASE),
    "insert": re.compile(r"\binsert\s+into\b", re.IGNORECASE),
    "update": re.compile(r"\bupdate\s+\w", re.IGNORECASE),
    "delete": re.compile(r"\bdelete\b", re.IGNORECASE),
    "cursor": re.compile(r"\bcursor\s+\w", re.IGNORECASE),
    "execute_immediate": re.compile(r"\bexecute\s+immediate\b", re.IGNORECASE),
}
# Tables and views named in static SQL. A lexical reader cannot see through
# EXECUTE IMMEDIATE and does not pretend to: dynamic SQL stays reported as
# dynamic SQL, never as a table nobody could name.
_OBJ = r"([A-Za-z_][A-Za-z0-9_$#]*(?:\.[A-Za-z_][A-Za-z0-9_$#]*)?)"
_TABLE_REFS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bfrom\s+" + _OBJ,
        r"\bjoin\s+" + _OBJ,
        r"\binsert\s+into\s+" + _OBJ,
        r"\bupdate\s+" + _OBJ,
        r"\bmerge\s+into\s+" + _OBJ,
    )
)
# Never a table: PL/SQL syntax that follows the same keywords, and the one
# table everybody selects from without depending on it.
_NOT_A_TABLE = {"DUAL", "TABLE", "SELECT", "SET", "WHERE", "DELETE", "VALUES", "THE"}

_BRANCH = re.compile(r"\b(if|elsif|case|when|loop|while|for)\b", re.IGNORECASE)
_EXCEPTION = re.compile(r"\bexception\b", re.IGNORECASE)
_WHITESPACE = re.compile(r"\s+")

# A body shorter than this carries no signal: "NULL;" is everywhere and
# proves nothing about code reuse.
_MIN_FINGERPRINT_CHARS = 24

# Words a lexical extractor would read as a "call" but that are syntax.
_NOT_A_CALL = {
    "IF", "ELSIF", "WHILE", "FOR", "LOOP", "CASE", "WHEN", "AND", "OR", "NOT",
    "IN", "OUT", "VALUES", "INTO", "FROM", "WHERE", "SELECT", "INSERT",
    "UPDATE", "DELETE", "SET", "DECLARE", "BEGIN", "END", "RETURN", "RAISE",
    "EXCEPTION", "THEN", "ELSE", "IS", "AS", "NULL", "EXIT", "GOTO", "ORDER",
    "GROUP", "HAVING", "UNION", "CONNECT", "START", "BY", "ON", "USING",
    # Standard SQL/PL-SQL functions: portable, not Forms built-ins.
    "NVL", "NVL2", "DECODE", "SUBSTR", "INSTR", "LENGTH", "UPPER", "LOWER",
    "INITCAP", "TRIM", "LTRIM", "RTRIM", "LPAD", "RPAD", "REPLACE",
    "TO_CHAR", "TO_DATE", "TO_NUMBER", "TRUNC", "ROUND", "MOD", "ABS",
    "GREATEST", "LEAST", "COUNT", "SUM", "MIN", "MAX", "AVG", "SYSDATE",
    "ADD_MONTHS", "MONTHS_BETWEEN", "LAST_DAY", "NEXT_DAY", "COALESCE",
    "SIGN", "POWER", "CEIL", "FLOOR", "CHR", "ASCII", "RAWTOHEX", "USERENV",
    "REGEXP_REPLACE", "REGEXP_SUBSTR", "REGEXP_INSTR", "REGEXP_LIKE",
    "EXTRACT", "CAST", "TABLE", "EXISTS", "SQLCODE", "SQLERRM",
}


# Built-ins whose literal argument names another object, and which argument
# carries it (1-based). Anything not listed here keeps the old behaviour:
# the call is counted, the literal is dropped.
LITERAL_TARGETS: dict[str, tuple[str, int]] = {
    "GO_BLOCK": ("block", 1),
    "NEXT_BLOCK": ("block", 1),
    "PREVIOUS_BLOCK": ("block", 1),
    "FIND_BLOCK": ("block", 1),
    "SET_BLOCK_PROPERTY": ("block", 1),
    "GET_BLOCK_PROPERTY": ("block", 1),
    "CLEAR_BLOCK": ("block", 1),
    "GO_ITEM": ("item", 1),
    "FIND_ITEM": ("item", 1),
    "SET_ITEM_PROPERTY": ("item", 1),
    "GET_ITEM_PROPERTY": ("item", 1),
    "SET_ITEM_INSTANCE_PROPERTY": ("item", 1),
    "GET_ITEM_INSTANCE_PROPERTY": ("item", 1),
    "CLEAR_ITEM": ("item", 1),
    "DEFAULT_VALUE": ("item", 2),
    "NAME_IN": ("item", 1),
    "COPY": ("item", 2),
    "CALL_FORM": ("form", 1),
    "OPEN_FORM": ("form", 1),
    "NEW_FORM": ("form", 1),
    "SHOW_LOV": ("lov", 1),
    "FIND_LOV": ("lov", 1),
    "SET_LOV_PROPERTY": ("lov", 1),
    "SHOW_ALERT": ("alert", 1),
    "FIND_ALERT": ("alert", 1),
    "SET_ALERT_PROPERTY": ("alert", 1),
    "SET_ALERT_BUTTON_PROPERTY": ("alert", 1),
    "CREATE_GROUP_FROM_QUERY": ("record_group", 1),
    "POPULATE_GROUP": ("record_group", 1),
    "POPULATE_GROUP_WITH_QUERY": ("record_group", 1),
    "FIND_GROUP": ("record_group", 1),
    "DELETE_GROUP": ("record_group", 1),
    "FIND_RELATION": ("relation", 1),
    "CREATE_TIMER": ("timer", 1),
    "SET_TIMER": ("timer", 1),
    "DELETE_TIMER": ("timer", 1),
    "FIND_TIMER": ("timer", 1),
    "RUN_REPORT_OBJECT": ("report", 1),
    "FIND_REPORT_OBJECT": ("report", 1),
    "FIND_MENU_ITEM": ("menu_item", 1),
    "SET_MENU_ITEM_PROPERTY": ("menu_item", 1),
    "REPLACE_MENU": ("menu", 1),
    "HOST": ("os_command", 1),
    "USER_EXIT": ("user_exit", 1),
    "WEB.SHOW_DOCUMENT": ("url", 1),
    "DO_KEY": ("key", 1),
}


@dataclass(frozen=True)
class LiteralRef:
    """A literal argument that names something outside this code body."""

    builtin: str
    kind: str
    value: str

    def to_dict(self) -> dict:
        return {"builtin": self.builtin, "kind": self.kind, "value": self.value}


@dataclass
class CodeAnalysis:
    """Result of scanning one block of PL/SQL."""

    lines: int = 0
    builtins: Counter[str] = field(default_factory=Counter)
    unknown_calls: Counter[str] = field(default_factory=Counter)
    system_vars: Counter[str] = field(default_factory=Counter)
    globals_used: Counter[str] = field(default_factory=Counter)
    item_refs: Counter[str] = field(default_factory=Counter)
    sql_verbs: Counter[str] = field(default_factory=Counter)
    tables: Counter[str] = field(default_factory=Counter)
    literals: list[LiteralRef] = field(default_factory=list)
    branches: int = 0
    has_exception_block: bool = False

    def verdict_counts(self) -> Counter[str]:
        """How many built-in occurrences fall under each verdict."""
        out: Counter[str] = Counter()
        for name, n in self.builtins.items():
            out[rules.classify_builtin(name)[0]] += n
        return out

    def blockers(self) -> list[tuple[str, str, int]]:
        """Built-ins classified as MANUAL -- what blocks automation."""
        out = []
        for name, n in self.builtins.items():
            verdict, target = rules.classify_builtin(name)
            if verdict == rules.MANUAL:
                out.append((name, target, n))
        return sorted(out, key=lambda t: -t[2])

    def merge(self, other: CodeAnalysis) -> None:
        self.lines += other.lines
        self.builtins.update(other.builtins)
        self.unknown_calls.update(other.unknown_calls)
        self.system_vars.update(other.system_vars)
        self.globals_used.update(other.globals_used)
        self.item_refs.update(other.item_refs)
        self.sql_verbs.update(other.sql_verbs)
        self.tables.update(other.tables)
        seen = {(r.builtin, r.kind, r.value) for r in self.literals}
        for ref in other.literals:
            if (ref.builtin, ref.kind, ref.value) not in seen:
                self.literals.append(ref)
                seen.add((ref.builtin, ref.kind, ref.value))
        self.branches += other.branches
        self.has_exception_block = self.has_exception_block or other.has_exception_block


def _blank(m: re.Match[str]) -> str:
    return re.sub(r"[^\n]", " ", m.group(0))


def strip_comments(code: str) -> str:
    """Blank out comments only, keeping literals and line breaks.

    This is what the literal pass reads: a commented-out call must still not
    count, but the arguments of a live call must survive.
    """
    code = _BLOCK_COMMENT.sub(_blank, code)
    return _LINE_COMMENT.sub(_blank, code)


def strip_noise(code: str) -> str:
    """Blank out comments and literals while preserving line breaks."""
    code = _BLOCK_COMMENT.sub(_blank, code)
    code = _STRING.sub(_blank, code)
    return _LINE_COMMENT.sub(_blank, code)


def _split_args(text: str, start: int) -> list[str]:
    """Split the argument list that opens at ``start`` (the '(' index).

    A hand-written scanner rather than a regex: arguments nest, and a comma
    inside a literal or inside a nested call is not a separator. Returns []
    when the list never closes -- truncated source must not raise.
    """
    args: list[str] = []
    depth = 0
    in_str = False
    buf: list[str] = []
    i = start
    n = len(text)
    while i < n:
        ch = text[i]
        if in_str:
            if ch == "'":
                if i + 1 < n and text[i + 1] == "'":  # escaped quote
                    buf.append("''")
                    i += 2
                    continue
                in_str = False
            buf.append(ch)
        elif ch == "'":
            in_str = True
            buf.append(ch)
        elif ch == "(":
            depth += 1
            if depth > 1:
                buf.append(ch)
        elif ch == ")":
            depth -= 1
            if depth == 0:
                args.append("".join(buf))
                return args
            buf.append(ch)
        elif ch == "," and depth == 1:
            args.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
        i += 1
    return []


def _literal_value(arg: str) -> str:
    """The literal a single argument carries, or "" when it is an expression."""
    text = arg.strip()
    if len(text) < 2 or not text.startswith("'") or not text.endswith("'"):
        return ""
    inner = text[1:-1].replace("''", "'").strip()
    # A literal with a quote left inside was two literals concatenated: the
    # value is computed, and naming half of it would be a lie.
    return "" if "'" in inner else inner


def literal_refs(code: str) -> list[LiteralRef]:
    """Recover the literal arguments that name other Forms objects.

    Only the built-ins in ``LITERAL_TARGETS`` are read, and only when the
    argument is a plain literal. ``GO_BLOCK(v_name)`` yields nothing --
    deliberately: an unresolved target is reported as unresolved elsewhere,
    never guessed at here.
    """
    clean = strip_comments(code)
    out: list[LiteralRef] = []
    seen: set[tuple[str, str, str]] = set()
    for m in _CALL.finditer(clean):
        name = m.group(1).upper()
        target = LITERAL_TARGETS.get(name)
        if target is None:
            continue
        kind, index = target
        args = _split_args(clean, m.end() - 1)
        if len(args) < index:
            continue
        value = _literal_value(args[index - 1])
        if not value:
            continue
        key = (name, kind, value.upper())
        if key in seen:
            continue
        seen.add(key)
        out.append(LiteralRef(builtin=name, kind=kind, value=value))
    return out


def fingerprint(code: str) -> str:
    """Stable hash of a code body, ignoring comments and formatting.

    Only literal copy-paste collides. String literals, identifiers and column
    names are preserved, so two blocks that differ in a message or a table
    name are correctly seen as different work. Returns "" for bodies too
    small to mean anything.

    This is what lets an assessment tell "N modules of unique logic" apart
    from "one boilerplate block pasted into N modules" -- a distinction worth
    a large fraction of the migration budget.
    """
    if not code or not code.strip():
        return ""
    body = _BLOCK_COMMENT.sub(" ", code)
    body = _LINE_COMMENT.sub(" ", body)
    body = _WHITESPACE.sub(" ", body).strip().upper()
    if len(body) < _MIN_FINGERPRINT_CHARS:
        return ""
    return hashlib.sha1(body.encode("utf-8")).hexdigest()[:16]


def _is_forms_builtin(name: str) -> bool:
    upper = name.upper()
    if upper in rules.BUILTINS:
        return True
    return any(upper.startswith(p.upper()) for p in rules.CLIENT_SIDE_PREFIXES)


def analyze(code: str) -> CodeAnalysis:
    """Scan a PL/SQL body and return what matters for the migration."""
    res = CodeAnalysis()
    if not code or not code.strip():
        return res

    res.lines = code.count("\n") + 1
    clean = strip_noise(code)

    for raw in _CALL.findall(clean):
        name = raw.upper()
        if name in _NOT_A_CALL or name.split(".")[0] in _NOT_A_CALL:
            continue
        if _is_forms_builtin(name):
            res.builtins[name] += 1
        else:
            res.unknown_calls[name] += 1

    for raw in _BARE.findall(clean):
        name = raw.upper()
        if name in rules.BUILTINS:
            res.builtins[name] += 1

    for raw in _BIND.findall(clean):
        ref = raw.upper()
        if ref.startswith("SYSTEM."):
            res.system_vars[ref] += 1
        elif ref.startswith("GLOBAL."):
            res.globals_used[ref] += 1
        else:
            res.item_refs[ref] += 1

    for verb, pattern in _SQL_VERBS.items():
        n = len(pattern.findall(clean))
        if n:
            res.sql_verbs[verb] = n

    for pattern in _TABLE_REFS:
        for raw in pattern.findall(clean):
            name = raw.upper()
            if name in _NOT_A_TABLE or name.split(".")[0] in _NOT_A_CALL:
                continue
            res.tables[name] += 1

    res.literals = literal_refs(code)
    res.branches = len(_BRANCH.findall(clean))
    res.has_exception_block = bool(_EXCEPTION.search(clean))
    return res
