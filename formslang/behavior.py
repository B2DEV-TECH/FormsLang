"""Behaviour classification: does the migrated unit still do the same thing?

Three answers, and the third one is the important one:

``PRESERVED``  the rules found nothing that changes observable behaviour.
``CHANGED``    something observably differs after migration, and we can name
               it: the transaction boundary moved, the locking model changed,
               a trigger point stops firing.
``UNCERTAIN``  the rules cannot tell. Not a hedge -- a finding. A body that
               builds an item name at runtime cannot be proven equivalent by
               anything short of running it.

Two invariants hold everywhere below:

1. Absence of evidence is never ``PRESERVED``. A body too small or too
   opaque to analyse comes back ``UNCERTAIN``.
2. The model may make this worse, never better. :func:`merge_ai` accepts an
   AI opinion only when it moves away from ``PRESERVED``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import rules
from .plsql import CodeAnalysis

VERSION = "behavior/1"

PRESERVED, CHANGED, UNCERTAIN = "PRESERVED", "CHANGED", "UNCERTAIN"
BEHAVIORS = (PRESERVED, UNCERTAIN, CHANGED)
# Severity order: the model may move a unit up this list and never down.
_RANK = {value: i for i, value in enumerate(BEHAVIORS)}

# Trigger points that stop firing because the cycle they belong to does not
# exist in APEX. Whatever they did, they will not do it any more.
_CYCLE_TRIGGERS = {
    "PRE-BLOCK": "Fires on block entry, and APEX has no block navigation cycle.",
    "POST-BLOCK": "Fires on block exit, and APEX has no block navigation cycle.",
    "PRE-RECORD": "Fires on record entry, and APEX has no record navigation cycle.",
    "POST-RECORD": "Fires on record exit, and APEX has no record navigation cycle.",
    "WHEN-NEW-BLOCK-INSTANCE": "Fires when the cursor enters the block; nothing does that in APEX.",
    "WHEN-NEW-RECORD-INSTANCE": "Fires when the cursor enters a record; nothing does that in APEX.",
    "PRE-TEXT-ITEM": "Part of the thick-client item cycle.",
    "WHEN-TIMER-EXPIRED": "Depends on a Forms timer; APEX has no server-side timer.",
    "WHEN-CUSTOM-ITEM-EVENT": "Driven by a Java bean or WebUtil event that will not exist.",
    "ON-LOCK": "Pessimistic locking is replaced by optimistic checksums.",
    "ON-COMMIT": "Replaces Forms commit processing, which APEX performs itself.",
    "ON-ROLLBACK": "Replaces Forms rollback processing, which APEX performs itself.",
}

# Trigger points that survive, but whose execution moment depends on a choice
# the reviewer has not made yet. Uncertain by construction, not by ignorance.
_RELOCATED_TRIGGERS = {
    "PRE-INSERT": "a page process or a table trigger",
    "PRE-UPDATE": "a page process or a table trigger",
    "PRE-DELETE": "a page process or a table trigger",
    "POST-INSERT": "a page process or a table trigger",
    "POST-UPDATE": "a page process or a table trigger",
    "POST-DELETE": "a page process or a table trigger",
    "PRE-COMMIT": "a page process before the DML",
    "POST-COMMIT": "a page process after the DML",
    "POST-FORMS-COMMIT": "a page process after the DML",
    "POST-QUERY": "the region query or a per-row process",
    "PRE-QUERY": "the region source WHERE clause",
}

# Built-in families whose presence changes what the user observes.
_CHANGING_CATEGORIES = {
    "transaction": "The transaction boundary moves: APEX commits at the end of page processing.",
    "timer": "Timed behaviour disappears; the scheduling model has to change.",
    "client_platform": "A thick-client capability is removed; the browser cannot do it at all.",
    "form_state": "Clearing or leaving the form treats unsaved changes differently.",
    "reporting": "Reporting moves to a different renderer with different output.",
}

# Families whose effect cannot be established statically.
_UNCERTAIN_CATEGORIES = {
    "indirection": "The item touched is named at runtime, so nothing can prove equivalence.",
    "dynamic_sql": "The statement is assembled at runtime; its effect is not knowable here.",
    "unknown": "Not classified yet, so its behaviour is not established.",
}

# Named built-ins whose behaviour change is worth stating on its own.
_CHANGING_BUILTINS = {
    "LOCK_RECORD": "Pessimistic row locking becomes optimistic checksum checking.",
    "SHOW_ALERT": "A Forms alert blocks until answered; APEX cannot block page processing.",
    "HOST": "Runs a command on the client operating system, which a browser cannot do.",
    "USER_EXIT": "Calls external 3GL code that will not exist after migration.",
    "SYNCHRONIZE": "",   # a redraw: removing it changes nothing observable
    "PAUSE": "",
}

MIN_ANALYSABLE_CHARS = 12


@dataclass
class BehaviorResult:
    """What happens to observable behaviour, and why we say so."""

    value: str = UNCERTAIN
    reasons: list[str] = field(default_factory=list)
    uncertainties: list[str] = field(default_factory=list)
    source: str = "rules"          # "rules" or "rules+ai"
    version: str = VERSION

    def to_dict(self) -> dict:
        return {
            "value": self.value,
            "reasons": self.reasons,
            "uncertainties": self.uncertainties,
            "source": self.source,
            "version": self.version,
        }


def classify(
    analysis: CodeAnalysis,
    *,
    kind: str = "trigger",
    trigger_name: str = "",
    verdict: str = "",
    source: str = "",
) -> BehaviorResult:
    """Decide PRESERVED / CHANGED / UNCERTAIN from the static evidence alone."""
    changed: list[str] = []
    uncertain: list[str] = []

    if not source or len(source.strip()) < MIN_ANALYSABLE_CHARS:
        return BehaviorResult(
            value=UNCERTAIN,
            uncertainties=["Body too small to analyse; nothing was established either way."],
        )

    trigger = (trigger_name or "").strip().upper()
    if kind == "trigger" and trigger:
        why = _CYCLE_TRIGGERS.get(trigger)
        if why:
            changed.append(f"{trigger}: {why}")
        relocated = _RELOCATED_TRIGGERS.get(trigger)
        if relocated:
            uncertain.append(
                f"{trigger} moves to {relocated}; which one is chosen decides "
                "whether the behaviour is identical."
            )
        if verdict == rules.UNKNOWN:
            uncertain.append(f"{trigger} is outside the catalog; its behaviour is not established.")

    seen_categories: set[str] = set()
    for name in sorted(analysis.builtins):
        spec = rules.spec_for(name)
        note = _CHANGING_BUILTINS.get(name)
        if note:
            changed.append(f"{name}: {note}")
        elif (
            note is None
            and spec.category in _CHANGING_CATEGORIES
            and spec.category not in seen_categories
        ):
            seen_categories.add(spec.category)
            changed.append(f"{name}: {_CHANGING_CATEGORIES[spec.category]}")
        if spec.category in _UNCERTAIN_CATEGORIES:
            reason = _UNCERTAIN_CATEGORIES[spec.category]
            if reason not in uncertain:
                uncertain.append(f"{name}: {reason}")
        if spec.migration_class == rules.UNSUPPORTED and not note:
            changed.append(f"{name}: no APEX equivalent exists, so this capability is lost.")

    if analysis.sql_verbs.get("execute_immediate"):
        reason = "EXECUTE IMMEDIATE: the statement is assembled at runtime."
        if reason not in uncertain:
            uncertain.append(reason)

    if analysis.globals_used:
        names = ", ".join(sorted(analysis.globals_used))
        uncertain.append(
            f"Global state ({names}) becomes an application item or a collection, "
            "whose lifetime is not the same as a Forms global."
        )

    unknown = sorted(n for n in analysis.builtins if not rules.spec_for(n).known)
    if unknown:
        uncertain.append(
            "Built-ins outside the catalog: " + ", ".join(unknown)
            + ". Their behaviour is not established."
        )

    if changed:
        return BehaviorResult(value=CHANGED, reasons=changed, uncertainties=uncertain)
    if uncertain:
        return BehaviorResult(value=UNCERTAIN, uncertainties=uncertain)
    return BehaviorResult(
        value=PRESERVED,
        reasons=["No construct in this body changes observable behaviour on its own."],
    )


def merge_ai(determined: BehaviorResult, ai_value: str, ai_reason: str = "") -> BehaviorResult:
    """Fold an AI opinion in -- but only when it makes the answer safer.

    The model is allowed to say "this is less certain than you think". It is
    never allowed to say "this is fine after all": promoting a CHANGED unit
    back to PRESERVED is exactly the silent failure this product exists to
    prevent.
    """
    value = (ai_value or "").strip().upper()
    if value not in _RANK or _RANK[value] <= _RANK[determined.value]:
        return determined
    note = ai_reason.strip() or "The model reported a behaviour difference the rules did not find."
    merged = BehaviorResult(
        value=value,
        reasons=list(determined.reasons),
        uncertainties=list(determined.uncertainties),
        source="rules+ai",
    )
    target = merged.reasons if value == CHANGED else merged.uncertainties
    target.append(f"AI (INFERENCE, not verified): {note}")
    return merged
