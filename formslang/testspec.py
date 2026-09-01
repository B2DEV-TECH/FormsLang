"""Test specifications, written from the Forms behaviour and not from the APEX code.

A test generated from a generated conversion proves only that the generator
is self-consistent. It passes on the day the model quietly dropped a commit,
because the test was written from the code that dropped it. So every case
below is derived from the *original* module -- the trigger point, the items
it touches, the SQL it runs, the built-ins it calls -- and the migrated
implementation is what has to satisfy it.

Each case says where its expectation comes from, which is the part a
reviewer cannot afford to guess:

``FORMS_BEHAVIOR``      Forms did this, and APEX must keep doing it.
``MODERNIZATION``       APEX does this differently on purpose. The case
                        exists so the difference is noticed, not so it is
                        prevented.
``NEEDS_CONFIRMATION``  the rules cannot establish it from the source. A
                        person has to answer before the case is worth running.

Nothing here is executable, and it does not pretend to be: these are
specifications a developer or a QA analyst turns into whatever their shop
runs. Generating runnable SQL from a lexical read of PL/SQL would be a much
more confident claim than the evidence supports.

Every case carries the evidence that produced it, and every case is
reviewable -- pending, accepted, rejected or needs work. An accepted case is
a statement by a human that this is genuinely what the system must do.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from . import rules
from .plsql import CodeAnalysis, analyze

VERSION = "testspec/1"

# -- where an expectation comes from -------------------------------------

FROM_FORMS = "FORMS_BEHAVIOR"
FROM_MIGRATION = "MODERNIZATION"
NEEDS_CONFIRMATION = "NEEDS_CONFIRMATION"
ORIGINS = (FROM_FORMS, FROM_MIGRATION, NEEDS_CONFIRMATION)
ORIGIN_LABEL = {
    FROM_FORMS: "Inherited from Forms",
    FROM_MIGRATION: "Introduced by the migration",
    NEEDS_CONFIRMATION: "Needs confirmation",
}

# -- what a case exercises -----------------------------------------------

NORMAL = "normal"
BOUNDARY = "boundary"
NULLS = "null_handling"
TRANSACTION = "transaction"
SIDE_EFFECT = "side_effect"
EXCEPTION = "exception"
REGRESSION = "regression"
KINDS = (NORMAL, BOUNDARY, NULLS, TRANSACTION, SIDE_EFFECT, EXCEPTION, REGRESSION)
KIND_LABEL = {
    NORMAL: "Normal path",
    BOUNDARY: "Boundary",
    NULLS: "Null handling",
    TRANSACTION: "Transaction behaviour",
    SIDE_EFFECT: "Side effects",
    EXCEPTION: "Exception path",
    REGRESSION: "Regression",
}
_KIND_ORDER = {kind: i for i, kind in enumerate(KINDS)}

# -- reviewer states ------------------------------------------------------

PENDING, ACCEPTED, REJECTED, NEEDS_WORK = "pending", "accepted", "rejected", "needs_work"
CASE_STATES = (PENDING, ACCEPTED, REJECTED, NEEDS_WORK)
STATE_LABEL = {
    PENDING: "Pending review",
    ACCEPTED: "Accepted",
    REJECTED: "Rejected",
    NEEDS_WORK: "Needs modification",
}

# -- execution states -------------------------------------------------------
# A reviewer's accept/reject is a judgement about the wording of the case.
# Whether the case was actually run against the migrated unit, and what
# happened, is a separate fact -- one a case can go on collecting long after
# it was accepted, and one that a regeneration must not erase (see
# Store.save_test_cases, which only ever touches the reviewer columns).

NOT_RUN, RUN_PASS, RUN_FAIL, RUN_BLOCKED = "not_run", "pass", "fail", "blocked"
RUN_STATES = (NOT_RUN, RUN_PASS, RUN_FAIL, RUN_BLOCKED)
RUN_STATE_LABEL = {
    NOT_RUN: "Not run",
    RUN_PASS: "Passed",
    RUN_FAIL: "Failed",
    RUN_BLOCKED: "Blocked",
}

# How many named items or tables a sentence lists before it stops naming and
# starts counting. A case nobody finishes reading is a case nobody runs.
_LIST_CAP = 6

# When a trigger fires, in the words a tester would use. Anything not listed
# falls back to the shape of its name, which is enough to write a case
# against without inventing a firing rule Forms does not have.
_FIRES_WHEN = {
    "WHEN-BUTTON-PRESSED": "the user presses the button",
    "WHEN-NEW-FORM-INSTANCE": "the form is opened",
    "WHEN-NEW-BLOCK-INSTANCE": "the cursor enters the block",
    "WHEN-NEW-RECORD-INSTANCE": "the cursor enters a record",
    "WHEN-NEW-ITEM-INSTANCE": "the cursor enters the item",
    "WHEN-VALIDATE-ITEM": "the item is changed and validation runs",
    "WHEN-VALIDATE-RECORD": "the record is changed and validation runs",
    "WHEN-CREATE-RECORD": "a new record is created in the block",
    "WHEN-REMOVE-RECORD": "a record is removed from the block",
    "WHEN-LIST-CHANGED": "the list value is changed",
    "WHEN-CHECKBOX-CHANGED": "the checkbox is toggled",
    "WHEN-RADIO-CHANGED": "the radio group is changed",
    "WHEN-MOUSE-DOUBLECLICK": "the user double-clicks the item",
    "WHEN-TIMER-EXPIRED": "a Forms timer expires",
    "WHEN-CUSTOM-ITEM-EVENT": "a bean or WebUtil item raises its event",
    "PRE-QUERY": "the block query is about to run",
    "POST-QUERY": "each queried row has been fetched",
    "PRE-INSERT": "each new row is about to be inserted",
    "POST-INSERT": "each new row has been inserted",
    "PRE-UPDATE": "each changed row is about to be updated",
    "POST-UPDATE": "each changed row has been updated",
    "PRE-DELETE": "each row is about to be deleted",
    "POST-DELETE": "each row has been deleted",
    "PRE-COMMIT": "the transaction is about to commit",
    "POST-COMMIT": "the transaction has committed",
    "POST-FORMS-COMMIT": "Forms has posted its changes and not yet committed",
    "PRE-BLOCK": "the cursor is about to enter the block",
    "POST-BLOCK": "the cursor is about to leave the block",
    "PRE-RECORD": "the cursor is about to enter a record",
    "POST-RECORD": "the cursor is about to leave a record",
    "PRE-FORM": "the form is about to be entered",
    "POST-FORM": "the form is about to be left",
    "ON-LOCK": "Forms would lock the row",
    "ON-COMMIT": "Forms would commit the transaction",
    "ON-ROLLBACK": "Forms would roll the transaction back",
    "ON-INSERT": "Forms would insert the row",
    "ON-UPDATE": "Forms would update the row",
    "ON-DELETE": "Forms would delete the row",
    "ON-ERROR": "Forms raises an error",
    "ON-MESSAGE": "Forms issues a message",
    "KEY-COMMIT": "the user asks to save",
    "KEY-EXEQRY": "the user asks to execute the query",
    "KEY-CLRFRM": "the user asks to clear the form",
    "KEY-NXTREC": "the user asks for the next record",
}

_WRITE_VERBS = ("insert", "update", "delete")

# Categories whose test case is worth writing even when the built-in itself
# is classified as a straightforward replacement: the observable behaviour
# is what moves, not the call.
_REGRESSION_CLASSES = {
    rules.ARCHITECTURAL_REDESIGN: FROM_MIGRATION,
    rules.CLIENT_SIDE_REPLACEMENT: FROM_MIGRATION,
    rules.UNSUPPORTED: NEEDS_CONFIRMATION,
    rules.MANUAL_REVIEW: NEEDS_CONFIRMATION,
}


def case_id(task_id: str, kind: str, title: str) -> str:
    """Stable across regeneration, so a review survives a rule change.

    Derived from the content rather than from a counter: a case whose text
    did not change keeps its id, and with it whatever a reviewer decided
    about it. A case whose text did change is a different case, and it
    should come back pending.
    """
    digest = hashlib.sha1(f"{task_id}|{kind}|{title}".encode()).hexdigest()
    return digest[:12]


@dataclass
class TestCase:
    """One thing the migrated unit has to do, and why we believe it."""

    id: str = ""
    task_id: str = ""
    kind: str = NORMAL
    origin: str = FROM_FORMS
    title: str = ""
    given: list[str] = field(default_factory=list)
    when: list[str] = field(default_factory=list)
    then: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    version: str = VERSION

    @property
    def kind_label(self) -> str:
        return KIND_LABEL.get(self.kind, self.kind)

    @property
    def origin_label(self) -> str:
        return ORIGIN_LABEL.get(self.origin, self.origin)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "task_id": self.task_id, "kind": self.kind,
            "kind_label": self.kind_label, "origin": self.origin,
            "origin_label": self.origin_label, "title": self.title,
            "given": list(self.given), "when": list(self.when),
            "then": list(self.then), "evidence": list(self.evidence),
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, raw: dict) -> TestCase:
        return cls(
            id=raw.get("id", ""), task_id=raw.get("task_id", ""),
            kind=raw.get("kind", NORMAL), origin=raw.get("origin", FROM_FORMS),
            title=raw.get("title", ""), given=list(raw.get("given") or []),
            when=list(raw.get("when") or []), then=list(raw.get("then") or []),
            evidence=list(raw.get("evidence") or []),
            version=raw.get("version", VERSION),
        )


def _listing(names, cap: int = _LIST_CAP) -> str:
    """Name a few, then say how many more rather than printing all of them."""
    names = list(names)
    if len(names) <= cap:
        return ", ".join(names)
    return ", ".join(names[:cap]) + f" and {len(names) - cap} more"


def _shorten(text: str, cap: int = 72) -> str:
    """A title-length version of a sentence, cut on a word boundary.

    Two open questions on the same unit have to reach the reviewer as two
    cases, and a case is identified by its title -- so the title has to say
    which question it is. The full note stays in ``given`` and ``evidence``.
    """
    text = " ".join(str(text).split())
    if len(text) <= cap:
        return text
    return text[:cap].rsplit(" ", 1)[0].rstrip(".,;:") + "..."


def fires_when(kind: str, name: str, owner: str = "") -> str:
    """The sentence a tester would write for "when does this run?"."""
    if kind != "trigger":
        return f"{name} is called"
    key = (name or "").upper()
    known = _FIRES_WHEN.get(key)
    if known:
        return known
    where = f" on {owner}" if owner else ""
    if key.startswith("KEY-"):
        return f"the user presses the key mapped to {key}{where}"
    if key.startswith("PRE-"):
        return f"Forms reaches the {key} point{where}"
    if key.startswith("POST-"):
        return f"Forms has passed the {key} point{where}"
    if key.startswith("ON-"):
        return f"Forms would perform the action {key} replaces{where}"
    return f"the {key} trigger point is reached{where}"


def _items_touched(code: CodeAnalysis, items: dict | None) -> tuple[list, list, list]:
    """Split the items this body reads into required, bounded and unverified.

    ``items`` is the module's own item metadata. Without it nothing here can
    be asserted, so every item lands in the third list and its case comes
    back as something a person has to confirm.
    """
    required, bounded, unverified = [], [], []
    for ref in sorted(code.item_refs):
        if ref.upper().startswith(("GLOBAL.", "PARAMETER.", "SYSTEM.")):
            continue
        meta = (items or {}).get(ref.upper())
        if meta is None:
            unverified.append(ref)
            continue
        if getattr(meta, "required", False):
            required.append(ref)
        if getattr(meta, "max_length", None) or (
            (getattr(meta, "data_type", "") or "").upper() in ("NUMBER", "INT", "INTEGER")
        ):
            bounded.append((ref, meta))
    return required, bounded, unverified


def _normal_case(task, code: CodeAnalysis, analysis) -> TestCase:
    title = getattr(task, "title", "") or getattr(task, "name", "")
    given = [f"the migrated {task.kind.replace('_', ' ')} for {title} is in place"]
    if task.owner:
        given.append(f"a record is loaded in {task.owner}")
    then = ["the unit runs to completion without raising"]
    written = [v for v in _WRITE_VERBS if code.sql_verbs.get(v)]
    if written:
        then.append(f"the {', '.join(written)} statements it contains have run once")
    if code.item_refs:
        then.append(
            f"the values it assigns are visible on the page: {_listing(sorted(code.item_refs))}"
        )
    return TestCase(
        task_id=task.id, kind=NORMAL, origin=FROM_FORMS,
        title=f"{title} does what it did in Forms",
        given=given,
        when=[fires_when(task.kind, task.name, task.owner)],
        then=then,
        evidence=[f"{task.kind} {title}, {task.lines} line(s) of PL/SQL"],
    )


def _null_cases(task, code: CodeAnalysis, items: dict | None) -> list[TestCase]:
    required, _bounded, unverified = _items_touched(code, items)
    out: list[TestCase] = []
    if required:
        out.append(TestCase(
            task_id=task.id, kind=NULLS, origin=FROM_FORMS,
            title="Required items still refuse a null",
            given=[f"the page holds the migrated items {_listing(required)}"],
            when=["one of them is left empty and the page is submitted"],
            then=["the save is refused, as Forms refused it",
                  "the message names the item, not the column"],
            evidence=[f"{ref} is declared Required in the form" for ref in required],
        ))
    if unverified:
        out.append(TestCase(
            task_id=task.id, kind=NULLS, origin=NEEDS_CONFIRMATION,
            title="Null behaviour of the remaining items is unverified",
            given=[f"this unit reads {_listing(unverified)}"],
            when=["any of them is null"],
            then=["a reviewer states what should happen, because the form does not say"],
            evidence=["no Required or Length property was found for these items"],
        ))
    return out


def _boundary_cases(task, code: CodeAnalysis, items: dict | None) -> list[TestCase]:
    _required, bounded, _unverified = _items_touched(code, items)
    if not bounded:
        return []
    lengths, numbers = [], []
    for ref, meta in bounded:
        limit = getattr(meta, "max_length", None)
        if limit:
            lengths.append(f"{ref} (max {limit})")
        else:
            numbers.append(ref)
    given, then, evidence = [], [], []
    if lengths:
        given.append(f"items with a declared maximum length: {_listing(lengths)}")
        then.append("a value at the limit is accepted and one past it is refused")
        evidence += [f"{name} declared in the form" for name in lengths]
    if numbers:
        given.append(f"numeric items: {_listing(numbers)}")
        then.append("zero, a negative value and the largest the column accepts all behave")
        evidence += [f"{ref} has a numeric data type" for ref in numbers]
    return [TestCase(
        task_id=task.id, kind=BOUNDARY, origin=FROM_FORMS,
        title="Values at the edge of what the items accept",
        given=given, when=["the unit runs with those values in place"],
        then=then, evidence=evidence,
    )]


def _transaction_cases(task, code: CodeAnalysis, analysis) -> list[TestCase]:
    findings = [f for f in (getattr(analysis, "findings", None) or [])
                if f.category == "transaction"]
    writes = [v for v in _WRITE_VERBS if code.sql_verbs.get(v)]
    trigger = (task.name or "").upper() if task.kind == "trigger" else ""
    in_commit = trigger in {
        "PRE-INSERT", "POST-INSERT", "PRE-UPDATE", "POST-UPDATE", "PRE-DELETE",
        "POST-DELETE", "PRE-COMMIT", "POST-COMMIT", "POST-FORMS-COMMIT",
        "ON-COMMIT", "ON-ROLLBACK", "ON-INSERT", "ON-UPDATE", "ON-DELETE", "ON-LOCK",
    }
    if not findings and not writes and not in_commit:
        return []

    given, evidence = [], []
    if findings:
        names = [f.name for f in findings]
        given.append(f"this unit controls the transaction itself: {_listing(names)}")
        evidence += [f"{f.name} x{f.count}: {f.forms_behavior}" for f in findings]
    if writes:
        given.append(f"it performs {', '.join(writes)}")
        evidence.append(f"SQL verbs found in the body: {', '.join(sorted(code.sql_verbs))}")
    if in_commit:
        given.append(f"in Forms it ran inside the commit cycle, at {trigger}")
        evidence.append(f"{trigger} fires inside the Forms transaction")
    return [TestCase(
        task_id=task.id, kind=TRANSACTION, origin=FROM_MIGRATION,
        title="The commit happens where APEX commits, not where Forms did",
        given=given,
        when=["the migrated unit runs and the page is submitted"],
        then=[
            "the change is committed once, at the end of page processing",
            "an error later in the same submission leaves nothing half-written",
            "the reviewer confirms the new boundary is the one the business expects",
        ],
        evidence=evidence,
    )]


def _side_effect_cases(task, code: CodeAnalysis, analysis) -> list[TestCase]:
    out: list[TestCase] = []
    writes = [v for v in _WRITE_VERBS if code.sql_verbs.get(v)]
    if writes and code.tables:
        tables = sorted(code.tables)
        out.append(TestCase(
            task_id=task.id, kind=SIDE_EFFECT, origin=FROM_FORMS,
            title="The same rows are still touched",
            given=[f"the tables named in this body: {_listing(tables)}"],
            when=["the migrated unit runs once"],
            then=["the same rows are affected, and no others",
                  "running it twice does what running it twice did in Forms"],
            evidence=[f"{', '.join(writes)} against {_listing(tables)}"],
        ))
    if code.globals_used:
        names = sorted(code.globals_used)
        out.append(TestCase(
            task_id=task.id, kind=SIDE_EFFECT, origin=FROM_MIGRATION,
            title="Shared state survives the move off Forms globals",
            given=[f"this unit reads or writes {_listing(names)}"],
            when=["the migrated unit runs"],
            then=["whatever consumed those globals reads the same value from its APEX equivalent",
                  "the value does not leak between sessions"],
            evidence=[f"{name} referenced in the body" for name in names],
        ))
    if code.sql_verbs.get("execute_immediate"):
        out.append(TestCase(
            task_id=task.id, kind=SIDE_EFFECT, origin=NEEDS_CONFIRMATION,
            title="What the dynamic statement does cannot be read from the source",
            given=["the statement is assembled at runtime"],
            when=["the unit runs"],
            then=["a reviewer states which objects it touches before this case can be run"],
            evidence=["EXECUTE IMMEDIATE found in this body"],
        ))
    return out


def _exception_cases(task, code: CodeAnalysis) -> list[TestCase]:
    title = getattr(task, "title", "") or getattr(task, "name", "")
    if code.has_exception_block:
        return [TestCase(
            task_id=task.id, kind=EXCEPTION, origin=FROM_FORMS,
            title="The existing handler still catches what it caught",
            given=["the condition the handler was written for"],
            when=[f"{title} runs and that condition occurs"],
            then=["the handler runs and the user sees the same outcome",
                  "nothing is committed that the handler meant to prevent"],
            evidence=["an EXCEPTION section is present in this body"],
        )]
    if code.sql_verbs or code.branches:
        return [TestCase(
            task_id=task.id, kind=EXCEPTION, origin=FROM_MIGRATION,
            title="An unhandled error surfaces differently now",
            given=["nothing in this body handles an exception"],
            when=["the SQL it runs raises one"],
            then=["Forms showed FRM-40735 with the ORA- error underneath",
                  "the reviewer confirms what the APEX page shows instead"],
            evidence=["no EXCEPTION section, and SQL or branching present"],
        )]
    return []


def _regression_cases(task, analysis) -> list[TestCase]:
    """One case per family of construct whose behaviour moves, not per call."""
    findings = list(getattr(analysis, "findings", None) or [])
    grouped: dict[tuple[str, str], list] = {}
    for finding in findings:
        origin = _REGRESSION_CLASSES.get(finding.migration_class)
        if origin is None:
            continue
        grouped.setdefault((finding.category, origin), []).append(finding)

    out: list[TestCase] = []
    for (category, origin), group in sorted(grouped.items()):
        label = group[0].category_label or category
        names = [f.name for f in group]
        targets = sorted({t for f in group for t in f.targets})
        then = [group[0].apex or "the reviewer states what replaces it"]
        if origin == NEEDS_CONFIRMATION:
            then.append("no APEX equivalent is claimed here; a person decides what happens")
        else:
            then.append("the observable outcome is compared against the Forms one, side by side")
        if targets:
            then.append(f"the objects it named still exist or have a replacement: {_listing(targets)}")
        out.append(TestCase(
            task_id=task.id, kind=REGRESSION, origin=origin,
            title=f"{label} behaves as agreed after the move",
            given=[f"this unit uses {_listing(names)}"],
            when=["the migrated unit runs the same scenario"],
            then=then,
            evidence=[f"{f.name} x{f.count} [{f.migration_class}]: {f.forms_behavior}"
                      for f in group],
        ))

    for note in getattr(getattr(analysis, "behavior", None), "uncertainties", None) or []:
        out.append(TestCase(
            task_id=task.id, kind=REGRESSION, origin=NEEDS_CONFIRMATION,
            title=f"Open question: {_shorten(note)}",
            given=[note],
            when=["the scenario that exercises it is identified"],
            then=["a reviewer confirms the behaviour before this unit is signed off"],
            evidence=[note],
        ))
    return out


def generate(task, *, analysis=None, items: dict | None = None,
             code: CodeAnalysis | None = None) -> list[TestCase]:
    """Write the specification for one code unit.

    ``task`` is a :class:`formslang.convert.ConversionTask`, typed loosely to
    keep the import graph one-way. ``items`` maps ``BLOCK.ITEM`` onto the
    module's own item metadata; without it, nothing about required values or
    lengths is asserted -- those cases come back as needing confirmation
    instead of being quietly skipped.
    """
    parsed = code if code is not None else analyze(task.source or "")
    cases = [_normal_case(task, parsed, analysis)]
    cases += _null_cases(task, parsed, items)
    cases += _boundary_cases(task, parsed, items)
    cases += _transaction_cases(task, parsed, analysis)
    cases += _side_effect_cases(task, parsed, analysis)
    cases += _exception_cases(task, parsed)
    cases += _regression_cases(task, analysis)

    seen: set[str] = set()
    out: list[TestCase] = []
    for case in sorted(cases, key=lambda c: (_KIND_ORDER.get(c.kind, 99), c.title)):
        case.id = case_id(task.id, case.kind, case.title)
        if case.id in seen:
            continue
        seen.add(case.id)
        out.append(case)
    return out


def items_of(module) -> dict:
    """Item metadata keyed the way :func:`generate` looks it up."""
    return {
        f"{block.name}.{item.name}".upper(): item
        for block in getattr(module, "blocks", [])
        for item in block.items
    }


def summarize(rows) -> dict:
    """Counts for the dashboard: by kind, by origin, by reviewer state.

    ``rows`` are stored case dicts, which carry the reviewer state that a
    freshly generated :class:`TestCase` does not have yet.
    """
    rows = list(rows)
    kinds = {kind: 0 for kind in KINDS}
    origins = {origin: 0 for origin in ORIGINS}
    states = {state: 0 for state in CASE_STATES}
    runs = {state: 0 for state in RUN_STATES}
    stale = 0
    for row in rows:
        kinds[row.get("kind", "")] = kinds.get(row.get("kind", ""), 0) + 1
        origins[row.get("origin", "")] = origins.get(row.get("origin", ""), 0) + 1
        states[row.get("state", PENDING)] = states.get(row.get("state", PENDING), 0) + 1
        runs[row.get("run_state", NOT_RUN)] = runs.get(row.get("run_state", NOT_RUN), 0) + 1
        if row.get("stale"):
            stale += 1
    total = len(rows)
    reviewed = total - states.get(PENDING, 0)
    executed = total - runs.get(NOT_RUN, 0)
    return {
        "total": total,
        "kinds": kinds,
        "origins": origins,
        "states": states,
        "runs": runs,
        "reviewed": reviewed,
        "executed": executed,
        "stale": stale,
        "version": VERSION,
    }


def render_markdown(session_title: str, units: list[dict]) -> str:
    """The exported specification, as something a person reads and runs.

    ``units`` is a list of ``{"title", "kind", "risk", "behavior", "cases"}``
    where each case is a stored row: the generated case plus its reviewer
    state. Rejected cases are kept and marked, because a reviewer deciding a
    case does not apply is itself a reviewed fact.
    """
    lines = [
        f"# Test specification -- {session_title}",
        "",
        "Written from the original Oracle Forms behaviour, before any conversion.",
        "Nothing here has been executed by FormsLang. Each case says where its",
        "expectation comes from:",
        "",
    ]
    for origin in ORIGINS:
        lines.append(f"- **{origin}** -- {ORIGIN_LABEL[origin]}.")
    lines.append("")

    all_rows = [case for unit in units for case in unit.get("cases", [])]
    totals = summarize(all_rows)
    lines += [
        (
            f"**{totals['total']} case(s)** across {len(units)} unit(s); "
            f"{totals['reviewed']} reviewed, {totals['states'][PENDING]} pending; "
            f"{totals['executed']} executed, {totals['runs'][RUN_PASS]} passed, "
            f"{totals['runs'][RUN_FAIL]} failed."
        ),
        "",
    ]

    for unit in units:
        cases = unit.get("cases", [])
        if not cases:
            continue
        head = f"## {unit.get('title', '')}"
        meta = [unit.get("kind", ""), unit.get("risk", ""), unit.get("behavior", "")]
        meta = [m for m in meta if m]
        lines += [head, ""]
        if meta:
            lines += [f"`{' | '.join(meta)}`", ""]
        for case in cases:
            state = case.get("state", PENDING)
            mark = {ACCEPTED: "[x]", REJECTED: "[-]", NEEDS_WORK: "[!]"}.get(state, "[ ]")
            run_state = case.get("run_state", NOT_RUN)
            run_tag = (
                f" · {RUN_STATE_LABEL.get(run_state, run_state)}"
                if run_state != NOT_RUN else ""
            )
            lines.append(
                f"### {mark} {case.get('title', '')}  "
                f"<sub>{case.get('kind_label') or case.get('kind', '')} · "
                f"{case.get('origin', '')}{run_tag}</sub>"
            )
            lines.append("")
            for label, key in (("Given", "given"), ("When", "when"), ("Then", "then")):
                rows = case.get(key) or []
                if not rows:
                    continue
                lines.append(f"**{label}**")
                lines += [f"- {row}" for row in rows]
                lines.append("")
            evidence = case.get("evidence") or []
            if evidence:
                lines.append("<details><summary>Evidence</summary>")
                lines.append("")
                lines += [f"- {row}" for row in evidence]
                lines.append("")
                lines.append("</details>")
                lines.append("")
            if state != PENDING:
                who = case.get("reviewer") or "unnamed reviewer"
                note = f" -- {case['comment']}" if case.get("comment") else ""
                lines.append(f"> {STATE_LABEL.get(state, state)} by {who}{note}")
                lines.append("")
            if run_state != NOT_RUN:
                ran_by = case.get("run_by") or "unnamed tester"
                run_note = f" -- {case['run_notes']}" if case.get("run_notes") else ""
                run_when = f" ({case['run_at']})" if case.get("run_at") else ""
                lines.append(
                    f"> Run: {RUN_STATE_LABEL.get(run_state, run_state)} "
                    f"by {ran_by}{run_when}{run_note}"
                )
                lines.append("")
    return "\n".join(lines).rstrip() + "\n"
