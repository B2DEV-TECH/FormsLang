"""Generic Forms-to-target-platform modernization reasoning.

Every rule here is expressed over *shapes*: trigger timing, item metadata,
statement structure, and the relationship between a form unit and whatever
database dictionary was supplied. No application, schema, package, table or
case identifier from any particular corpus appears in this module; a rule that
cannot be stated structurally does not belong here.

The module is pure and deterministic: same evidence in, same signals out.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from . import plsql

VERSION = "modernization/1"

# Recommendations this module can produce, beyond the blueprint core set.
MOVE_TO_PLSQL_API = "MOVE_TO_PLSQL_API"
REPLACE_WITH_APEX_NATIVE = "REPLACE_WITH_APEX_NATIVE"

AUTO, ASSISTED, MANUAL = "AUTO", "ASSISTED", "MANUAL"
LOW, MEDIUM, HIGH, CRITICAL = "LOW", "MEDIUM", "HIGH", "CRITICAL"
FACT, INFERENCE = "FACT", "INFERENCE"

# Priority decides which signal wins when several fire on one unit (the caller
# applies the highest). Safety-relevant findings outrank convenience findings
# so a native-replacement shortcut can never mask a bypass of an authoritative
# API.
P_DML_BYPASS = 100
P_DUPLICATED_LOGIC = 90
P_UNSERIALIZED_KEY = 80
P_MODAL_NAVIGATION = 74
P_NON_MODAL_NAVIGATION = 72
P_UNOWNED_DML = 70
P_HARDCODED_FILTER = 64
P_CROSS_RECORD_STATE = 60
P_MIRRORS_CONSTRAINT = 52
P_NATIVE_REPLACEMENT = 44
P_MECHANICAL_CONVERT = 40
P_API_DELEGATION = 30


@dataclass(frozen=True)
class Signal:
    """One structural conclusion about a unit, with its safety consequences."""

    code: str
    priority: int
    recommendation: str
    target: str
    reason: str
    verdict: str
    risk_level: str
    risk_basis: str
    level: str = INFERENCE
    duplicates: str = ""  # qualified subprogram name this unit re-implements
    questions: tuple[str, ...] = ()
    statement: str = ""


# --------------------------------------------------------------------------
# Lexical helpers. All operate on comment-stripped text so that prose in a
# comment can never be read as evidence of behavior.
# --------------------------------------------------------------------------

_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_$#]*")
_PREFIX = re.compile(r"^(?:GC|GV|P|V|L|C|G)_")
_STRING_LIT = re.compile(r"'(?:[^']|'')*'")

# Words that are syntax, not data, when reading a WHERE clause.
_SQL_NOISE = frozenset({
    "AND", "OR", "NOT", "IN", "IS", "NULL", "LIKE", "BETWEEN", "EXISTS", "SELECT",
    "FROM", "WHERE", "ORDER", "GROUP", "BY", "HAVING", "ROWNUM", "SYSDATE", "USER",
    "CASE", "WHEN", "THEN", "ELSE", "END", "TRUE", "FALSE", "ASC", "DESC", "FOR",
    "UPDATE", "OF", "NOWAIT", "DUAL",
})


def clean(source: str) -> str:
    """Comment-free source; comments are documentation, never evidence."""
    return plsql.strip_comments(source or "")


def leaf(name: str) -> str:
    """Bare column-ish identity: drop qualifiers and conventional prefixes.

    A form bind, a procedure parameter and a local variable may all denote the
    same concept across layers; comparing leaves is what lets a duplication
    rule survive the naming conventions of either side.
    """
    bare = name.strip().lstrip(":").rsplit(".", 1)[-1].upper()
    return _PREFIX.sub("", bare)


def skeleton(expression: str) -> str:
    """Structure of an expression with every name and number erased.

    Two layers written in different vocabularies collapse onto the same
    skeleton when they compute the same thing, which is the only honest way to
    claim duplication without knowing either vocabulary.
    """
    text = _STRING_LIT.sub("#", expression or "")
    text = _WORD.sub("#", text)
    text = re.sub(r"\b\d+(?:\.\d+)?\b", "#", text)
    text = text.replace(":", "")
    text = re.sub(r"#(?:\s*\.\s*#)+", "#", text)  # a qualified name is one leaf
    text = re.sub(r"#(?:\s+#)+", "#", text)
    return re.sub(r"\s+", "", text)


def arithmetic_weight(expression: str) -> int:
    """How much arithmetic structure an expression carries.

    Used as a significance floor: a skeleton match only means something when
    there is enough structure for the coincidence to be implausible.
    """
    stripped = _STRING_LIT.sub("", expression or "")
    return sum(stripped.count(op) for op in "+-*/")


@dataclass
class SelectShape:
    """A SELECT ... INTO reduced to what two layers could share."""

    table: str
    projection: str
    filters: frozenset
    has_rownum_limit: bool = False
    locks: bool = False

    def key(self) -> tuple:
        return (self.table, self.projection, self.filters)


_SELECT_INTO = re.compile(
    r"\bSELECT\b(?P<proj>.*?)\bINTO\b(?P<into>.*?)\bFROM\b\s+"
    r"(?P<table>[A-Za-z_][A-Za-z0-9_$#]*(?:\.[A-Za-z_][A-Za-z0-9_$#]*)?)"
    r"(?P<tail>[^;]*)",
    re.IGNORECASE | re.DOTALL,
)
_COMPARISON = re.compile(
    r"([A-Za-z_][A-Za-z0-9_$#.]*)\s*(?:=|<>|!=|>=|<=|>|<|\bnot\s+in\b|\bin\b|\blike\b)",
    re.IGNORECASE,
)


def select_shapes(source: str) -> list:
    """Every SELECT ... INTO in a body, reduced to comparable structure."""
    shapes = []
    for m in _SELECT_INTO.finditer(clean(source)):
        tail = m.group("tail")
        where = ""
        wpos = re.search(r"\bWHERE\b", tail, re.IGNORECASE)
        if wpos:
            where = tail[wpos.end():]
        filters = set()
        for cm in _COMPARISON.finditer(where):
            token = leaf(cm.group(1))
            if token and token not in _SQL_NOISE and not token.isdigit():
                filters.add(token)
        shapes.append(SelectShape(
            table=m.group("table").rsplit(".", 1)[-1].upper(),
            projection=skeleton(m.group("proj")),
            filters=frozenset(filters),
            has_rownum_limit=bool(re.search(r"\bROWNUM\b", where, re.IGNORECASE)),
            locks=bool(re.search(r"\bFOR\s+UPDATE\b", tail, re.IGNORECASE)),
        ))
    return shapes


_ASSIGNMENT = re.compile(r"(:?[A-Za-z_][A-Za-z0-9_$#.]*)\s*:=\s*([^;]+);", re.DOTALL)
_RETURN_KEYWORD = re.compile(r"\bRETURN\b", re.IGNORECASE)


def assignments(source: str) -> list:
    return [(m.group(1), m.group(2)) for m in _ASSIGNMENT.finditer(clean(source))]


def returned_expressions(source: str) -> list:
    """Expressions a body hands back, one per RETURN statement.

    A function header carries the word RETURN too -- its type -- so the value is
    taken from the last RETURN inside each statement, never the first.
    """
    out = []
    for fragment in clean(source).split(";"):
        parts = _RETURN_KEYWORD.split(fragment)
        if len(parts) > 1 and parts[-1].strip():
            out.append(parts[-1].strip())
    return out


_LITERAL_SET = re.compile(
    r"([A-Za-z_][A-Za-z0-9_$#.]*)\s*(NOT\s+IN|IN|=)\s*\(?\s*"
    r"((?:'(?:[^']|'')*'\s*,?\s*)+)\)?",
    re.IGNORECASE,
)


def literal_sets(source: str) -> list:
    """(column leaf, operator, literal set) triples compared in a body."""
    out = []
    for m in _LITERAL_SET.finditer(clean(source)):
        op = re.sub(r"\s+", " ", m.group(2).upper())
        values = frozenset(v.strip().strip("'").upper()
                           for v in _STRING_LIT.findall(m.group(3)))
        if values:
            out.append((leaf(m.group(1)), op, values))
    return out


_DML_TARGET = re.compile(
    r"\b(INSERT\s+INTO|UPDATE|DELETE\s+FROM|MERGE\s+INTO)\s+(?:\w+\.)?"
    r"([A-Za-z_][A-Za-z0-9_$#]*)",
    re.IGNORECASE,
)


def written_tables(source: str) -> list:
    """(verb, table) pairs a body writes, read from its own statements.

    Read from the statements rather than matched against a table dictionary, so
    ownership is still established when no DDL was supplied.
    """
    return [(m.group(1).upper().split()[0], m.group(2).upper())
            for m in _DML_TARGET.finditer(clean(source))]


def writes_table(source: str, table: str) -> bool:
    return any(t == table.upper() for _, t in written_tables(source))


def guard_strength(source: str) -> int:
    """How much protective work a body performs around its own DML.

    Counts the observable guards an authoritative routine tends to carry:
    pessimistic locking, explicit failure, affected-row checks and delegation
    to another layer. A caller that writes the same table carrying none of
    them is bypassing them, whatever either side is called.
    """
    text = clean(source).upper()
    score = 0
    if re.search(r"\bFOR\s+UPDATE\b", text):
        score += 1
    if "RAISE_APPLICATION_ERROR" in text:
        score += 1
    if re.search(r"\bSQL%ROWCOUNT\b", text):
        score += 1
    if re.search(r"\b[A-Z_][A-Z0-9_$#]*\.[A-Z_][A-Z0-9_$#]*\s*\(", text):
        score += 1
    return score


# --------------------------------------------------------------------------
# Structural index over whatever database dictionary was supplied. Nothing
# here knows any schema; it only records which shapes exist and who owns them.
# --------------------------------------------------------------------------


@dataclass
class ApiIndex:
    writers: dict          # TABLE -> [(qualified name, guard strength)]
    mutators: frozenset    # TABLEs some writer updates or deletes from
    selects: dict          # select shape key -> qualified name
    expressions: dict      # expression skeleton -> qualified name
    predicates: dict       # (leaf, operator, literals) -> qualified name
    packages: frozenset
    tables: dict           # TABLE -> database.Table
    referenced: frozenset  # every identifier the database layer mentions

    @property
    def known(self) -> bool:
        """Whether any database layer was supplied at all.

        A package body alone is enough: it tells us what the database owns even
        when no DDL came with it.
        """
        return bool(self.packages or self.tables or self.writers or self.selects
                    or self.expressions or self.predicates)


EMPTY_INDEX = ApiIndex({}, frozenset(), {}, {}, {}, frozenset(), {}, frozenset())


def build_index(db) -> ApiIndex:
    """Index the supplied database sources by shape, not by name."""
    writers: dict = {}
    mutators: set = set()
    selects: dict = {}
    expressions: dict = {}
    predicates: dict = {}
    referenced = set()
    for pkg_name, body in getattr(db, "package_bodies", {}).items():
        for sub in body.subprograms:
            qualified = f"{pkg_name}.{sub.name}".upper()
            text = sub.body_text or ""
            strength = guard_strength(text)
            for verb, table in written_tables(text):
                owners = writers.setdefault(table, [])
                if qualified not in [name for name, _ in owners]:
                    owners.append((qualified, strength))
                if verb in {"UPDATE", "DELETE", "MERGE"}:
                    mutators.add(table)
            for shape in select_shapes(text):
                selects.setdefault(shape.key(), qualified)
            for expression in returned_expressions(text):
                if arithmetic_weight(expression) >= 2:
                    expressions.setdefault(skeleton(expression), qualified)
            for _, expression in assignments(text):
                if arithmetic_weight(expression) >= 2:
                    expressions.setdefault(skeleton(expression), qualified)
            for triple in literal_sets(text):
                if len(triple[2]) >= 2:
                    predicates.setdefault(triple, qualified)
            referenced.update(w.upper() for w in _WORD.findall(clean(text)))
    for view in getattr(db, "views", {}).values():
        referenced.update(w.upper() for w in _WORD.findall(clean(view.query_text or "")))
    for table in getattr(db, "tables", {}).values():
        for constraint in table.constraints:
            referenced.update(w.upper() for w in _WORD.findall(constraint.check_condition or ""))
            referenced.update(c.upper() for c in constraint.columns)
    return ApiIndex(
        writers=writers, mutators=frozenset(mutators),
        selects=selects, expressions=expressions,
        predicates=predicates,
        packages=frozenset(n.upper() for n in getattr(db, "package_specs", {})),
        tables={k.upper(): v for k, v in getattr(db, "tables", {}).items()},
        referenced=frozenset(referenced),
    )


# --------------------------------------------------------------------------
# Trigger reasoning
# --------------------------------------------------------------------------


@dataclass
class UnitContext:
    """Everything a rule may look at about one form unit."""

    name: str                 # trigger name, upper case
    scope: str                # "form" | "block" | "item"
    block: str
    item: str
    source: str
    calls: frozenset
    writes: frozenset
    reads: frozenset
    base_table: str = ""
    item_column: str = ""
    item_is_database: bool = True
    display_only_items: frozenset = frozenset()

    @property
    def body(self) -> str:
        return clean(self.source)

    @property
    def upper(self) -> str:
        return self.body.upper()

    @property
    def package_calls(self) -> list:
        return sorted(c for c in self.calls if "." in c)


# Built-ins whose presence does not constitute business behavior: a body made
# only of these is pure form navigation.
_NAVIGATION_ONLY = frozenset({
    "GO_BLOCK", "GO_ITEM", "EXECUTE_QUERY", "ENTER_QUERY", "CLEAR_FORM",
    "CREATE_RECORD", "NEXT_RECORD", "PREVIOUS_RECORD", "FIRST_RECORD",
    "LAST_RECORD", "CLEAR_BLOCK", "NEXT_ITEM", "PREVIOUS_ITEM",
})
_PROPERTY_BUILTINS = frozenset({"SET_ITEM_PROPERTY", "SET_BLOCK_PROPERTY"})
_MESSAGE_BUILTINS = frozenset({"MESSAGE", "SHOW_ALERT", "RAISE_APPLICATION_ERROR"})
_INSERT_TIME = frozenset({"PRE-INSERT", "PRE-COMMIT", "WHEN-VALIDATE-RECORD"})


def _fails_fast(ctx: UnitContext) -> bool:
    return "FORM_TRIGGER_FAILURE" in ctx.upper or "RAISE_APPLICATION_ERROR" in ctx.upper


def _touches_transaction(ctx: UnitContext) -> bool:
    return bool(re.search(r"\b(COMMIT|ROLLBACK|COMMIT_FORM|POST)\b", ctx.upper))


def escalate(verdict: str, ctx: UnitContext) -> str:
    """Never let a mechanically-translatable body claim AUTO while it also
    controls a transaction, leaves the module, or mutates session-wide state.
    Those three change meaning on the target platform even when the statements
    survive unchanged, so a human has to look."""
    if verdict != AUTO:
        return verdict
    leaves_module = bool(ctx.calls & {"CALL_FORM", "OPEN_FORM", "NEW_FORM", "POST"})
    mutates_global = bool(re.search(r":GLOBAL\.[A-Z0-9_$#]+\s*:=", ctx.upper))
    if leaves_module or mutates_global or _touches_transaction(ctx):
        return ASSISTED
    return verdict


def _duplication_signal(ctx: UnitContext, api: ApiIndex):
    """Does this unit re-implement something the database layer already owns?"""
    already_called = {c.upper() for c in ctx.calls}

    for shape in select_shapes(ctx.source):
        owner = api.selects.get(shape.key())
        if owner and owner not in already_called:
            return Signal(
                code="LOGIC_DUPLICATED_QUERY", priority=P_DUPLICATED_LOGIC,
                recommendation=MOVE_TO_PLSQL_API, target=owner,
                reason=("Trigger re-derives the same result from the same table and "
                        f"filter columns that {owner} already computes. Two independent "
                        "implementations of one rule diverge as soon as either is "
                        "changed; route the caller through the API instead."),
                verdict=MANUAL, risk_level=HIGH,
                risk_basis="Query duplicated against an existing database API subprogram",
                duplicates=owner,
                statement="Identical query shape exists in the database API layer.")

    for _, expression in assignments(ctx.source):
        if arithmetic_weight(expression) < 2:
            continue
        owner = api.expressions.get(skeleton(expression))
        if owner and owner not in already_called:
            return Signal(
                code="LOGIC_DUPLICATED_FORMULA", priority=P_DUPLICATED_LOGIC,
                recommendation=MOVE_TO_PLSQL_API, target=owner,
                reason=("Trigger computes an expression whose structure matches "
                        f"{owner}. The calculation has two homes, so a correction to "
                        "one silently leaves the other wrong; call the API."),
                verdict=MANUAL, risk_level=HIGH,
                risk_basis="Calculation duplicated against an existing database API function",
                duplicates=owner,
                statement="Identical arithmetic structure exists in the database API layer.")

    for triple in literal_sets(ctx.source):
        if len(triple[2]) < 2:
            continue
        owner = api.predicates.get(triple)
        if owner and owner not in already_called:
            values = ", ".join(sorted(triple[2]))
            return Signal(
                code="LOGIC_DUPLICATED_PREDICATE", priority=P_DUPLICATED_LOGIC,
                recommendation=MOVE_TO_PLSQL_API, target=owner,
                reason=(f"Trigger tests {triple[0]} against the literal set ({values}) "
                        f"that {owner} already encodes. Whichever copy is edited first "
                        "puts the two layers into disagreement."),
                verdict=MANUAL, risk_level=HIGH,
                risk_basis="Business predicate duplicated against a database API subprogram",
                duplicates=owner,
                statement="Identical literal predicate exists in the database API layer.")
    return None


def _dml_signal(ctx: UnitContext, api: ApiIndex):
    """DML written in the form against a table the database layer owns."""
    if not ctx.writes:
        return None
    own_guards = guard_strength(ctx.source)
    bypassed = []
    for table in sorted(ctx.writes):
        owners = api.writers.get(table.upper())
        if not owners:
            continue
        owner, strength = max(owners, key=lambda pair: (pair[1], pair[0]))
        if owner.upper() in {c.upper() for c in ctx.calls}:
            continue
        bypassed.append((strength - own_guards, table, owner))
    if bypassed:
        # Report the worst bypass, not whichever table sorts first.
        missing, table, owner = max(bypassed)
        level = CRITICAL if missing >= 2 else HIGH if missing >= 1 else MEDIUM
        # Committing here as well means the form is deciding durability for an
        # entity the database owns, which is a step worse than writing it.
        if _touches_transaction(ctx):
            level = {MEDIUM: HIGH, HIGH: CRITICAL}.get(level, level)
        # Losing guards and losing ownership are different findings, and only the
        # first one may cite guards: say what was measured, not what is typical.
        if missing >= 1:
            detail = (f"{owner} owns the same table and carries guards this trigger "
                      "does not (locking, explicit failure, affected-row checks or "
                      "delegation to another layer)")
            basis = "Direct DML bypasses the guards of the API that owns this table"
        else:
            detail = (f"{owner} already owns writes to that table, leaving the rule "
                      "for this entity with two independent implementations")
            basis = "Direct DML bypasses the API that owns this table"
        return Signal(
            code="DIRECT_DML_BYPASSES_API", priority=P_DML_BYPASS,
            recommendation="MANUAL_REVIEW", target=owner,
            reason=(f"Trigger writes {table} directly while {detail}. Translating "
                    "these statements mechanically carries the bypass into the new "
                    "platform intact."),
            verdict=MANUAL, risk_level=level,
            risk_basis=basis,
            duplicates=owner,
            questions=(f"Confirm whether {table} may be written outside {owner}.",),
            statement="Form-layer DML competes with an authoritative database API.")

    table = min(ctx.writes)
    if api.known:
        return Signal(
            code="DML_WITHOUT_OWNING_API", priority=P_UNOWNED_DML,
            recommendation=MOVE_TO_PLSQL_API,
            target=f"New API subprogram owning writes to {table}",
            reason=(f"Trigger writes {table} directly and no supplied package owns "
                    "writes to it, so the rule lives only in the form. The target "
                    "platform needs an owner for this behavior before the call site "
                    "can move."),
            verdict=MANUAL, risk_level=HIGH,
            risk_basis="Business write has no database API owner",
            questions=(f"Decide which package should own writes to {table}.",),
            statement="No database API owns this table's writes.")
    return None


def _concurrency_signal(ctx: UnitContext):
    """Key derivation that only holds while one session writes at a time."""
    body = ctx.body
    if not re.search(r"\bMAX\s*\(", body, re.IGNORECASE):
        return None
    if not re.search(r"\bMAX\s*\([^)]*\)[^;]*?\+\s*1", body, re.IGNORECASE | re.DOTALL):
        return None
    if ctx.name not in _INSERT_TIME:
        return None
    return Signal(
        code="UNSERIALIZED_KEY_DERIVATION", priority=P_UNSERIALIZED_KEY,
        recommendation="REFACTOR", target="Sequence, identity column or serialized allocation",
        reason=("Next key value is derived with MAX()+1 under the assumption that one "
                "session inserts at a time. Forms held that by locking the record "
                "during entry; a multi-session web runtime does not, so two "
                "concurrent inserts can read the same maximum and collide."),
        verdict=MANUAL, risk_level=MEDIUM,
        risk_basis="Read-then-insert key allocation is not safe under concurrency",
        questions=("Confirm the replacement allocation strategy for this key.",),
        statement="Key allocation relies on single-session serialization.")


def _navigation_signal(ctx: UnitContext):
    if "CALL_FORM" in ctx.calls:
        return Signal(
            code="MODAL_MODULE_CALL", priority=P_MODAL_NAVIGATION,
            recommendation="MANUAL_REVIEW", target="Modal page, inline region or navigation link",
            reason=("CALL_FORM names its target module in code and suspends the caller "
                    "until the callee closes, inside one shared session. The target "
                    "platform has no equivalent of that arrangement: modal page, "
                    "inline region and plain link each trade away something different, "
                    "and the in-memory parameter list survives none of them."),
            verdict=MANUAL, risk_level=MEDIUM,
            risk_basis="Modal cross-module call has no direct target-platform equivalent",
            questions=(("Choose between a modal page, an inline region or a link, "
                        "and decide how the caller's state is restored on return."),),
            statement="Caller-blocking cross-module navigation requires a human decision.")
    if ctx.calls & {"OPEN_FORM", "NEW_FORM"}:
        return Signal(
            code="NON_MODAL_MODULE_OPEN", priority=P_NON_MODAL_NAVIGATION,
            recommendation="REFACTOR", target="Link to a filtered page with URL parameters",
            reason=("The module is opened alongside the caller in a shared multi-form "
                    "session. There is no multi-form session to preserve on the target "
                    "platform, so this becomes a link to a filtered page and the "
                    "parameter list has to travel as URL or page items."),
            verdict=ASSISTED, risk_level=MEDIUM,
            risk_basis="Multi-module session state does not survive the target platform",
            statement="Non-modal module navigation becomes parameterised page navigation.")
    return None


_DEFAULT_WHERE = re.compile(
    r"SET_BLOCK_PROPERTY\s*\([^;]*?\bDEFAULT_WHERE\b\s*,\s*(?P<clause>[^;]*?)\)\s*;",
    re.IGNORECASE | re.DOTALL,
)


def _filter_signal(ctx: UnitContext):
    """A query filter compiled into code rather than exposed to the user."""
    matches = list(_DEFAULT_WHERE.finditer(ctx.body))
    if not matches:
        return None
    # A clause built only from a parameter is a mechanical filter; a clause
    # that carries its own literal encodes policy that a user cannot change
    # without a code change.
    policy = [m for m in matches if re.search(r"''[^']+''|'[^']*=[^']*'[^|]*$", m.group("clause"))]
    literal_policy = [m for m in matches
                      if re.search(r"''[A-Za-z0-9_ -]+''", m.group("clause"))]
    if literal_policy or (policy and not re.search(r"\|\|", matches[0].group("clause"))):
        return Signal(
            code="FILTER_POLICY_IN_CODE", priority=P_HARDCODED_FILTER,
            recommendation="REFACTOR", target="Page-level filter, report condition or parameter",
            reason=("The default query restriction is written as a literal predicate "
                    "inside the trigger, so the definition of which rows belong in "
                    "this list can only be changed by editing and recompiling code. "
                    "Expose it as a filter or parameter on the target platform."),
            verdict=ASSISTED, risk_level=MEDIUM,
            risk_basis="Row-selection policy is compiled into the form rather than configured",
            statement="Query restriction is a hardcoded literal predicate.")
    return None


def _cross_record_state_signal(ctx: UnitContext):
    """Session-wide state used to carry a per-record value between triggers."""
    if not re.search(r":GLOBAL\.[A-Z0-9_$#]+\s*:=", ctx.upper):
        return None
    if ctx.writes or ctx.reads or [c for c in ctx.calls if "." in c]:
        return None
    if re.search(r"GET_APPLICATION_PROPERTY", ctx.upper):
        return None
    targets = [t for t, _ in assignments(ctx.source)]
    if not targets or not all(t.upper().startswith(":GLOBAL.") for t in targets):
        return None
    return Signal(
        code="CROSS_RECORD_SESSION_STATE", priority=P_CROSS_RECORD_STATE,
        recommendation="REFACTOR", target="Row-level old value or explicit page state",
        reason=("A session-wide global is used as a per-record baseline because the "
                "form has no old-value accessor. Session state on the target platform "
                "is shared by every row the page touches, so the value has to be "
                "carried explicitly or read from the row itself."),
        verdict=ASSISTED, risk_level=MEDIUM,
        risk_basis="Per-record baseline held in session-wide state",
        statement="Session global substitutes for a missing old-value accessor.")


_LITERAL_VALUE = re.compile(r"'(?:[^']|'')*'|\b\d+(?:\.\d+)?\b")


def compared_values(text: str, column: str) -> frozenset:
    """Literals this text compares the named column against.

    Direction and operator are deliberately ignored: a trigger mirrors a CHECK
    constraint by testing its negation, so "credit_limit >= 0" in the schema and
    "IF credit_limit < 0 THEN fail" in the form are the same rule.
    """
    name = re.escape(column)
    pattern = re.compile(
        r"\b" + name + r"\b\s*(?:[<>]=?|!=|<>|=|NOT\s+IN|IN)\s*(?P<right>[^;)\n]{0,80})"
        r"|(?P<left>[^;(\n]{0,80}?)\s*(?:[<>]=?|!=|<>|=)\s*\b" + name + r"\b",
        re.IGNORECASE)
    values = set()
    for match in pattern.finditer(text):
        chunk = match.group("right") or match.group("left") or ""
        values.update(v.strip().strip("'").upper() for v in _LITERAL_VALUE.findall(chunk))
    return frozenset(values)


def _owning_table(ctx: UnitContext, api: ApiIndex):
    """The table whose column this item edits.

    The block usually declares its own base table. When it does not, a column
    carried by exactly one supplied table is unambiguous enough to use -- and
    only then, because two candidates mean no evidence at all.
    """
    if ctx.base_table:
        return api.tables.get(ctx.base_table.upper())
    column = (ctx.item_column or ctx.item).upper()
    if not column:
        return None
    owners = [t for t in api.tables.values()
              if column in {c.name.upper() for c in t.columns}]
    return owners[0] if len(owners) == 1 else None


def _constraint_signal(ctx: UnitContext, api: ApiIndex):
    """A validation that only restates a guarantee the schema already makes."""
    if not ctx.item:
        return None
    table = _owning_table(ctx, api)
    if table is None:
        return None
    column = (ctx.item_column or ctx.item).upper()
    if column not in {c.name.upper() for c in table.columns}:
        return None
    body = ctx.body.upper()
    if not _fails_fast(ctx):
        return None
    for constraint in table.constraints:
        if constraint.constraint_type.upper() != "CHECK":
            continue
        text = (constraint.check_condition or constraint.raw_sql or "").upper()
        if not text or column not in text:
            continue
        declared = compared_values(text, column)
        if declared and declared & compared_values(body, column):
            return Signal(
                code="MIRRORS_SCHEMA_CONSTRAINT", priority=P_MIRRORS_CONSTRAINT,
                recommendation="CONVERT", target="Native item validation",
                reason=("Validation restates a CHECK constraint the schema already "
                        "enforces; it exists to fail early with a readable message. "
                        "It maps one-to-one onto a declarative item validation and "
                        "nothing is centralised or lost."),
                verdict=AUTO, risk_level=LOW,
                risk_basis="Condition is already guaranteed by a schema constraint",
                level=FACT if ctx.base_table else INFERENCE,
                statement="Trigger condition duplicates a declarative CHECK constraint.")
    return None


def _native_signal(ctx: UnitContext):
    """Behaviour the target platform provides declaratively, with no code."""
    body, upper = ctx.body, ctx.upper
    business_calls = [c for c in ctx.calls if "." in c]

    if re.search(r"REGEXP_LIKE\s*\([^;]*'[^']*@[^']*'", body, re.IGNORECASE):
        return Signal(
            code="NATIVE_FORMAT_VALIDATION", priority=P_NATIVE_REPLACEMENT,
            recommendation=REPLACE_WITH_APEX_NATIVE, target="Built-in e-mail validation type",
            reason=("A hand-written pattern check for an address-shaped value. The "
                    "target platform ships this validation declaratively, so the "
                    "PL/SQL disappears rather than being translated."),
            verdict=AUTO, risk_level=LOW,
            risk_basis="Format check replaced by a declarative platform validation",
            statement="Hand-rolled format check has a declarative equivalent.")

    if "COPY" in ctx.calls and not _fails_fast(ctx) and not ctx.writes:
        return Signal(
            code="NATIVE_DEFAULT_SUGGESTION", priority=P_NATIVE_REPLACEMENT,
            recommendation=REPLACE_WITH_APEX_NATIVE,
            target="Item default or cascading list of values",
            reason=("The trigger only suggests a default without rejecting anything, "
                    "writing indirectly so it does not re-fire its own validation. "
                    "An item default or cascading list achieves the same behaviour "
                    "declaratively."),
            verdict=AUTO, risk_level=LOW,
            risk_basis="Default suggestion replaced by a declarative item default",
            statement="Trigger only supplies a default value.")

    if (ctx.name == "POST-QUERY" and not ctx.writes and not business_calls
            and not select_shapes(ctx.source)):
        targets = {leaf(t) for t, _ in assignments(ctx.source)}
        if targets and targets <= {leaf(i) for i in ctx.display_only_items}:
            return Signal(
                code="NATIVE_DISPLAY_DERIVATION", priority=P_NATIVE_REPLACEMENT,
                recommendation=REPLACE_WITH_APEX_NATIVE,
                target="Report column expression or highlight rule",
                reason=("The trigger derives a non-database display value from columns "
                        "already on the row. That is presentation, not business logic: "
                        "a computed column or highlight rule on the report replaces the "
                        "trigger entirely."),
                verdict=AUTO, risk_level=LOW,
                risk_basis="Presentation-only derivation with no persisted effect",
                statement="Derived value is display-only and never stored.")

    if ("SHOW_ALERT" in ctx.calls and not ctx.writes and not business_calls
            and not select_shapes(ctx.source) and not _touches_transaction(ctx)):
        return Signal(
            code="NATIVE_CONFIRMATION", priority=P_NATIVE_REPLACEMENT,
            recommendation=REPLACE_WITH_APEX_NATIVE, target="Confirm dynamic action",
            reason=("The whole body is a confirmation prompt and a branch on the "
                    "answer. The target platform expresses that as a confirm action "
                    "on the button, with no PL/SQL at all."),
            verdict=AUTO, risk_level=LOW,
            risk_basis="Confirmation dialog replaced by a declarative confirm action",
            statement="Body is a confirmation prompt with no other effect.")

    property_calls = re.findall(r"SET_ITEM_PROPERTY\s*\(", upper)
    if (property_calls and not ctx.writes and not business_calls
            and not assignments(ctx.source)
            and ctx.calls <= _PROPERTY_BUILTINS | _NAVIGATION_ONLY):
        return Signal(
            code="NATIVE_ITEM_STATE", priority=P_NATIVE_REPLACEMENT,
            recommendation=REPLACE_WITH_APEX_NATIVE,
            target="Item read-only or display-only attribute",
            reason=("The body only switches item state at runtime. Those are "
                    "declarative item attributes on the target platform, so the "
                    "trigger has no code to carry forward."),
            verdict=AUTO, risk_level=LOW,
            risk_basis="Runtime property assignment replaced by a declarative attribute",
            statement="Body only sets declarative item properties.")
    return None


def _mechanical_signal(ctx: UnitContext, api: ApiIndex):
    """Idioms that translate statement for statement with nothing to lose."""
    upper = ctx.upper
    business_calls = [c for c in ctx.calls if "." in c]

    if re.search(r"\.\s*NEXTVAL\b", upper) and not ctx.writes:
        return Signal(
            code="SEQUENCE_KEY_ASSIGNMENT", priority=P_MECHANICAL_CONVERT,
            recommendation="CONVERT", target="Identity column or before-insert process",
            reason=("Primary key drawn from a sequence at insert time, plus the usual "
                    "audit stamps. The idiom has a direct counterpart on the target "
                    "platform and carries no business rule."),
            verdict=AUTO, risk_level=LOW,
            risk_basis="Sequence-assigned key maps directly to the target platform",
            level=FACT,
            statement="Key assignment is a mechanical translation.")

    if ctx.calls and ctx.calls <= _NAVIGATION_ONLY and not ctx.writes:
        return Signal(
            code="NAVIGATION_TOOLBAR", priority=P_MECHANICAL_CONVERT,
            recommendation="CONVERT", target="Report search, reset or create action",
            reason=("The body is query and record navigation only. Those are report "
                    "and page actions on the target platform; there is no business "
                    "logic to preserve."),
            verdict=AUTO, risk_level=LOW,
            risk_basis="Query and record navigation maps onto built-in page actions",
            level=FACT,
            statement="Body is form navigation with no business effect.")

    shapes = select_shapes(ctx.source)
    if (ctx.name == "WHEN-VALIDATE-ITEM" and shapes and not ctx.writes
            and not business_calls and _fails_fast(ctx)):
        return Signal(
            code="LOOKUP_VALIDATION", priority=P_MECHANICAL_CONVERT,
            recommendation="CONVERT", target="List of values with an existence validation",
            reason=("The trigger looks a value up and rejects it when absent, filling "
                    "descriptive items from the same row. A list of values plus a "
                    "validation expresses the same contract declaratively."),
            verdict=ASSISTED, risk_level=LOW,
            risk_basis="Lookup and reject translates into a list of values with validation",
            statement="Lookup validation with descriptive fill.")

    if ctx.scope == "form" and re.search(r"GET_APPLICATION_PROPERTY", upper):
        return Signal(
            code="SESSION_IDENTITY_SEED", priority=P_MECHANICAL_CONVERT,
            recommendation="CONVERT", target="Built-in application user and page load process",
            reason=("Module startup seeds the end-user identity into a global and then "
                    "positions and queries the first block. The target platform "
                    "supplies the authenticated user as a built-in substitution and "
                    "renders the region itself; only the optional filtering survives "
                    "as a page process."),
            verdict=ASSISTED, risk_level=LOW,
            risk_basis="Startup identity and query bootstrap have platform equivalents",
            statement="Startup trigger seeds identity and opens the first block.")
    return None


def _delegation_signal(ctx: UnitContext, api: ApiIndex):
    calls = [c for c in ctx.package_calls if c.split(".")[0].upper() in api.packages]
    if not calls or ctx.writes:
        return None
    return Signal(
        code="DELEGATES_TO_API", priority=P_API_DELEGATION,
        recommendation="PRESERVE", target=", ".join(sorted(calls)),
        reason=("The trigger delegates its business logic to the database API rather "
                "than restating it, so the rule already lives where it should. Only "
                "the call site moves; the logic does not change."),
        verdict=AUTO, risk_level=LOW,
        risk_basis="Business logic already centralised behind a database API",
        level=FACT,
        statement="Call site delegates cleanly to the authoritative API.")


def trigger_signals(ctx: UnitContext, api: ApiIndex = EMPTY_INDEX) -> list:
    """Every structural conclusion that holds for this unit, highest first."""
    found = [
        _dml_signal(ctx, api),
        _duplication_signal(ctx, api),
        _concurrency_signal(ctx),
        _navigation_signal(ctx),
        _filter_signal(ctx),
        _cross_record_state_signal(ctx),
        _constraint_signal(ctx, api),
        _native_signal(ctx),
        _mechanical_signal(ctx, api),
        _delegation_signal(ctx, api),
    ]
    signals = [s for s in found if s is not None]
    signals.sort(key=lambda s: (-s.priority, s.code))
    return [Signal(**{**s.__dict__, "verdict": escalate(s.verdict, ctx)}) for s in signals]


# --------------------------------------------------------------------------
# Database-layer reasoning. Same discipline: shapes only.
# --------------------------------------------------------------------------

P_IDENTITY_DEFAULT = 90
P_STATE_MATRIX = 80
P_NONDETERMINISTIC_ROW = 70
P_DEAD_SCHEMA = 50
P_UNFILTERED_VIEW = 45
P_APPEND_ONLY = 40


def _unique_column_sets(table) -> list:
    if table is None:
        return []
    return [frozenset(c.upper() for c in k.columns) for k in table.constraints
            if k.constraint_type.upper() in {"PRIMARY KEY", "UNIQUE"} and k.columns]


def subprogram_signals(qualified: str, sub, api: ApiIndex) -> list:
    """Structural conclusions about one packaged subprogram."""
    signals = []
    body = sub.body_text or ""
    upper = clean(body).upper()

    for param in sub.parameters:
        if (param.default_value or "").strip().upper() == "USER":
            signals.append(Signal(
                code="IDENTITY_DEFAULTS_TO_DB_SESSION", priority=P_IDENTITY_DEFAULT,
                recommendation="MANUAL_REVIEW",
                target="Explicit application user parameter supplied by the caller",
                reason=(f"Parameter {param.name} falls back to the database session "
                        "user when the caller omits it. Under a pooled connection the "
                        "session user is the pool account, not the person acting, so "
                        "every record written through this default is attributed to "
                        "the wrong identity."),
                verdict=MANUAL, risk_level=CRITICAL,
                risk_basis="Audit identity defaults to the database session account",
                questions=(("Decide how the end-user identity reaches this "
                            "subprogram once connections are pooled."),),
                statement="Identity default resolves to the database session user."))
            break

    by_leaf: dict = {}
    for name, op, values in literal_sets(body):
        if op in {"=", "IN"}:
            by_leaf.setdefault(name, set()).update(values)
    crowded = [n for n, v in by_leaf.items() if len(v) >= 4]
    if crowded and not re.search(r"\b(INSERT|UPDATE|DELETE)\b", upper):
        biggest = max(crowded, key=lambda n: (len(by_leaf[n]), n))
        signals.append(Signal(
            code="RULE_TABLE_ENCODED_IN_CODE", priority=P_STATE_MATRIX,
            recommendation="MANUAL_REVIEW",
            target="Preserved procedural rule or a table-driven matrix",
            reason=(f"The subprogram enumerates {len(by_leaf[biggest])} permitted values "
                    f"of {biggest} as a hand-written boolean expression. The rule is "
                    "data wearing the shape of code: it cannot be inspected or changed "
                    "without a recompile, and no automated rewrite can prove a "
                    "table-driven version admits exactly the same combinations."),
            verdict=MANUAL, risk_level=HIGH,
            risk_basis="Enumerated business rule enforced procedurally, not declaratively",
            questions=(("Decide whether this matrix stays procedural or becomes "
                        "a configurable table."),),
            statement="Rule matrix is enumerated in code rather than stored as data."))

    for shape in select_shapes(body):
        if not shape.has_rownum_limit:
            continue
        uniques = _unique_column_sets(api.tables.get(shape.table))
        if any(u <= shape.filters for u in uniques):
            continue
        signals.append(Signal(
            code="NONDETERMINISTIC_SINGLE_ROW", priority=P_NONDETERMINISTIC_ROW,
            recommendation="MANUAL_REVIEW",
            target="Uniqueness guarantee in the schema, or an explicit ordering",
            reason=(f"The subprogram takes one arbitrary row from {shape.table} with a "
                    "row limit, but nothing in the schema stops more than one row from "
                    "matching. Which row comes back is unspecified today and may "
                    "change with the plan; callers silently inherit that."),
            verdict=MANUAL, risk_level=MEDIUM,
            risk_basis="Single-row selection is not guaranteed unique by the schema",
            questions=((f"Decide whether {shape.table} needs a uniqueness "
                        "constraint or a defined ordering."),),
            statement="Single-row read is not backed by a uniqueness guarantee."))
        break

    signals.sort(key=lambda s: (-s.priority, s.code))
    return signals


def table_signals(table, api: ApiIndex, referenced: frozenset) -> list:
    """Structural conclusions about one table."""
    signals = []
    used = api.referenced | referenced
    dead = sorted(c.name.upper() for c in table.columns if c.name.upper() not in used)
    if dead:
        signals.append(Signal(
            code="UNREFERENCED_COLUMN", priority=P_DEAD_SCHEMA,
            recommendation="MANUAL_REVIEW",
            target="Drop the column, or implement the behaviour it was meant to carry",
            reason=("No supplied package, view, constraint or form unit reads or writes "
                    + ", ".join(dead) + ". Either the behaviour was never built or it "
                    "lives outside the analysed corpus; carrying the column forward "
                    "without deciding which just moves the ambiguity."),
            verdict=MANUAL, risk_level=LOW,
            risk_basis="Schema element with no observed reader or writer",
            questions=("Confirm whether " + ", ".join(dead) + " is dead or fed from "
                       "outside the analysed sources.",),
            statement="Column has no observed consumer in the supplied corpus."))

    has_fk = any(k.constraint_type.upper() == "FOREIGN KEY" for k in table.constraints)
    writers = api.writers.get(table.name.upper(), [])
    if (writers and not has_fk and not dead
            and table.name.upper() not in api.mutators):
        signals.append(Signal(
            code="APPEND_ONLY_UNCONSTRAINED_TABLE", priority=P_APPEND_ONLY,
            recommendation="PRESERVE", target="Existing table",
            reason=("The table carries no referential constraints and every writer "
                    "only inserts. That is the shape of a deliberately generic "
                    "append-only record: constraining it would couple it to the "
                    "entities it describes."),
            verdict=AUTO, risk_level=LOW,
            risk_basis="Deliberately unconstrained append-only structure",
            level=INFERENCE,
            statement="Table is append-only and intentionally unconstrained."))
    signals.sort(key=lambda s: (-s.priority, s.code))
    return signals


def view_signals(view) -> list:
    """Structural conclusions about one view."""
    if re.search(r"\bWHERE\b", clean(view.query_text or ""), re.IGNORECASE):
        return []
    return [Signal(
        code="UNFILTERED_QUERY_SOURCE", priority=P_UNFILTERED_VIEW,
        recommendation="MANUAL_REVIEW",
        target="Row-level policy, session context filter or authorisation scheme",
        reason=(f"{view.name} selects without any restriction, so it returns every row "
                "to anyone holding SELECT. In the form that was acceptable because the "
                "module decided what to show; a page built directly on this view has "
                "no such gatekeeper."),
        verdict=MANUAL, risk_level=MEDIUM,
        risk_basis="Query source exposes all rows with no row-level restriction",
        questions=(f"Decide the access boundary for {view.name} on the target platform.",),
        statement="View applies no row-level restriction.")]
