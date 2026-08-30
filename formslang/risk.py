"""Migration risk: how dangerous this unit is to move, not how much it costs.

FormsLang already answers "what does this cost" -- that is the verdict and
the effort weight in :mod:`formslang.rules`. This module answers a different
question with a different answer, and keeping the two apart is the whole
point:

``COMMIT_FORM`` is ``AUTO``. It converts mechanically, costs almost nothing,
and silently moves the transaction boundary of the whole page. Cheap and
dangerous. A single score cannot say both things, so there are two.

Everything here is deterministic. Every point in the score traces back to a
construct the static analysis actually found, and every factor carries the
evidence that produced it. The model is never asked what the risk is -- at
most it is asked to explain a risk the rules already established.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from . import rules
from .plsql import CodeAnalysis

VERSION = "risk/1"

LOW, MEDIUM, HIGH, CRITICAL = "LOW", "MEDIUM", "HIGH", "CRITICAL"
RISK_LEVELS = (LOW, MEDIUM, HIGH, CRITICAL)
_LEVEL_RANK = {level: i for i, level in enumerate(RISK_LEVELS)}

# Score thresholds. The score is a 0-100 projection of the raw points below,
# not a probability and not a percentage of anything.
THRESHOLDS = ((20.0, LOW), (45.0, MEDIUM), (70.0, HIGH))

# Raw points saturate: 12 raw points is the half-way mark, and no amount of
# evidence can push the score past 100. Without this, a 600-line trigger
# would score 400 and the number would stop meaning anything.
HALF_LIFE = 12.0

# Multipliers turning a 0..1 catalog weight into raw points.
BUILTIN_POINTS = 4.0
TRIGGER_POINTS = 8.0
SYSTEM_VAR_POINTS = 3.0

# Fixed costs for facts that are not a catalog entry.
DYNAMIC_SQL_POINTS = 6.0
DML_POINTS = 3.0
CROSS_MODULE_POINTS = 4.0
UNRESOLVED_INDIRECTION_POINTS = 5.0
GLOBAL_POINTS = 1.5
GLOBAL_CAP = 4.5
UNKNOWN_POINTS = 4.0
UNKNOWN_CAP = 8.0
UNQUALIFIED_CALL_POINTS = 1.0
UNQUALIFIED_CALL_CAP = 4.0
SIZE_CAP = 4.0
LINES_PER_SIZE_POINT = 60.0
NO_HANDLER_POINTS = 2.0

# A catalog weight at or above this makes the construct dangerous on its own,
# whatever else the unit does: the level is floored at HIGH. The floor never
# reaches CRITICAL -- CRITICAL means several dangerous things at once, and
# that has to be earned by the score.
FLOOR_WEIGHT = 0.80


@dataclass(frozen=True)
class RiskFactor:
    """One reason the score is what it is, with the evidence that caused it."""

    id: str
    title: str
    points: float
    detail: str
    evidence: tuple[str, ...] = ()
    review_area: str = ""
    floor: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "points": round(self.points, 2),
            "detail": self.detail,
            "evidence": list(self.evidence),
            "review_area": self.review_area,
            "floor": self.floor,
        }


@dataclass
class RiskResult:
    """The verdict of the risk engine for one code unit."""

    level: str = LOW
    score: float = 0.0
    raw: float = 0.0
    factors: list[RiskFactor] = field(default_factory=list)
    review_areas: list[str] = field(default_factory=list)
    version: str = VERSION

    def to_dict(self) -> dict:
        return {
            "level": self.level,
            "score": round(self.score, 1),
            "raw": round(self.raw, 2),
            "factors": [f.to_dict() for f in self.factors],
            "review_areas": self.review_areas,
            "version": self.version,
        }


def score_from_raw(raw: float) -> float:
    """Project raw points onto 0-100 through a saturating curve.

    ``score = 100 * (1 - 0.5 ** (raw / HALF_LIFE))``. Twelve raw points is 50,
    twenty-four is 75, and the curve never reaches 100. Printed in the UI so
    a reviewer can check the arithmetic instead of trusting it.
    """
    if raw <= 0:
        return 0.0
    # Capped just short of 100: a heuristic that prints a perfect score reads
    # as certainty, and this number is evidence, not certainty. (Far enough
    # out the float underflows to exactly 1.0 and would print 100.)
    return min(99.9, 100.0 * (1.0 - math.pow(0.5, raw / HALF_LIFE)))


def level_for(score: float) -> str:
    for limit, level in THRESHOLDS:
        if score < limit:
            return level
    return CRITICAL


def _occurrence_multiplier(count: int) -> float:
    """Ten calls are worse than one, but not ten times worse."""
    return 1.0 + math.log2(count) if count > 1 else 1.0


def assess(
    analysis: CodeAnalysis,
    *,
    kind: str = "trigger",
    trigger_name: str = "",
    verdict: str = "",
    source: str = "",
) -> RiskResult:
    """Score one code unit. Deterministic: same input, same answer, always."""
    factors: list[RiskFactor] = []

    def add(
        ident: str, title: str, points: float, detail: str,
        evidence: tuple[str, ...] = (), area: str = "", floor: str = "",
    ) -> None:
        if points > 0:
            factors.append(RiskFactor(ident, title, points, detail, evidence, area, floor))

    # -- the trigger point itself ----------------------------------------
    if kind == "trigger" and trigger_name:
        weight, why = rules.trigger_risk(trigger_name)
        if why:
            add(
                "trigger_point",
                f"Trigger point: {trigger_name.upper()}",
                weight * TRIGGER_POINTS,
                why,
                (trigger_name.upper(),),
                "Execution point of this trigger",
                HIGH if weight >= FLOOR_WEIGHT else "",
            )

    # -- built-ins, grouped by the family that explains them --------------
    by_category: dict[str, list[tuple[str, int, rules.BuiltinSpec]]] = {}
    for name, count in analysis.builtins.items():
        spec = rules.spec_for(name)
        by_category.setdefault(spec.category, []).append((name, count, spec))

    for category, hits in sorted(by_category.items()):
        cat = rules.CATEGORIES[category]
        points = sum(
            spec.risk * _occurrence_multiplier(count) * BUILTIN_POINTS
            for _, count, spec in hits
        )
        top = max(spec.risk for _, _, spec in hits)
        evidence = tuple(
            f"{name}{f' ×{count}' if count > 1 else ''}"
            for name, count, _ in sorted(hits)
        )
        add(
            f"builtin:{category}",
            cat.label,
            points,
            cat.risk_reason,
            evidence,
            cat.review_area,
            HIGH if top >= FLOOR_WEIGHT else "",
        )

    # -- Forms system variables -------------------------------------------
    if analysis.system_vars:
        points = sum(
            rules.spec_for(name).risk * _occurrence_multiplier(count) * SYSTEM_VAR_POINTS
            for name, count in analysis.system_vars.items()
        )
        add(
            "system_vars",
            "Forms runtime state",
            points,
            rules.CATEGORIES["system_var"].risk_reason,
            tuple(sorted(analysis.system_vars)),
            rules.CATEGORIES["system_var"].review_area,
        )

    # -- global state -----------------------------------------------------
    if analysis.globals_used:
        add(
            "globals",
            "Global variables",
            min(GLOBAL_CAP, GLOBAL_POINTS * len(analysis.globals_used)),
            "Reads or writes state shared with every other form in the application.",
            tuple(sorted(analysis.globals_used)),
            "Shared state ownership and lifetime",
        )

    # -- dynamic SQL ------------------------------------------------------
    dynamic = []
    if analysis.sql_verbs.get("execute_immediate"):
        dynamic.append("EXECUTE IMMEDIATE")
    if "FORMS_DDL" in analysis.builtins:
        dynamic.append("FORMS_DDL")
    if dynamic:
        add(
            "dynamic_sql",
            "Dynamic SQL",
            DYNAMIC_SQL_POINTS,
            rules.CATEGORIES["dynamic_sql"].risk_reason,
            tuple(dynamic),
            rules.CATEGORIES["dynamic_sql"].review_area,
            HIGH,
        )

    # -- database side effects --------------------------------------------
    writes = [v for v in ("insert", "update", "delete") if analysis.sql_verbs.get(v)]
    if writes:
        add(
            "dml",
            "Database side effects",
            DML_POINTS,
            "Writes to the database directly, outside the block's own DML.",
            tuple(v.upper() for v in writes),
            "Side effects and where they belong after migration",
        )
        if not analysis.has_exception_block:
            add(
                "dml_no_handler",
                "DML without an exception handler",
                NO_HANDLER_POINTS,
                "Errors surface somewhere else in APEX than they did in Forms.",
                (),
                "Error handling",
            )

    # -- other modules ----------------------------------------------------
    forms = sorted({r.value.upper() for r in analysis.literals if r.kind == "form"})
    calls_other_module = {"CALL_FORM", "OPEN_FORM", "NEW_FORM"} & set(analysis.builtins)
    if forms:
        add(
            "cross_module",
            "Calls another form",
            CROSS_MODULE_POINTS * len(forms),
            "Migrating this unit is not finished until the called form is migrated too.",
            tuple(forms),
            rules.CATEGORIES["module_nav"].review_area,
        )
    elif calls_other_module:
        add(
            "cross_module_unresolved",
            "Calls a form chosen at runtime",
            CROSS_MODULE_POINTS,
            "The called module is decided at runtime, so the dependency cannot be listed.",
            tuple(sorted(calls_other_module)),
            rules.CATEGORIES["module_nav"].review_area,
            HIGH,
        )

    # -- indirection whose target we could not read ------------------------
    indirect = {"NAME_IN", "COPY"} & set(analysis.builtins)
    if indirect:
        resolved = sum(1 for r in analysis.literals if r.builtin in indirect)
        unresolved = sum(analysis.builtins[b] for b in indirect) - resolved
        if unresolved > 0:
            add(
                "indirection_unresolved",
                "Indirect access with a computed target",
                UNRESOLVED_INDIRECTION_POINTS,
                "The item name is built at runtime; nothing can prove what this touches.",
                tuple(sorted(indirect)),
                rules.CATEGORIES["indirection"].review_area,
                HIGH,
            )

    # -- catalog debt ------------------------------------------------------
    unknown_names = [
        name for name in analysis.builtins if not rules.spec_for(name).known
    ]
    if verdict == rules.UNKNOWN and trigger_name:
        unknown_names.append(trigger_name.upper())
    if unknown_names:
        add(
            "catalog_debt",
            "Outside the catalog",
            min(UNKNOWN_CAP, UNKNOWN_POINTS * len(unknown_names)),
            "FormsLang has not classified this construct, so its risk is unproven.",
            tuple(sorted(set(unknown_names))),
            "Unclassified constructs -- confirm by hand",
        )

    # An unqualified call FormsLang does not recognise may be a local
    # procedure (harmless) or a built-in missing from the catalog (not).
    bare_calls = sorted(n for n in analysis.unknown_calls if "." not in n)
    if bare_calls:
        add(
            "unresolved_calls",
            "Unresolved local calls",
            min(UNQUALIFIED_CALL_CAP, UNQUALIFIED_CALL_POINTS * len(bare_calls)),
            "Called without a package name: could be a program unit, a library or a built-in.",
            tuple(bare_calls),
            "Where these procedures live",
        )

    # -- sheer size --------------------------------------------------------
    lines = analysis.lines or (source.count("\n") + 1 if source else 0)
    if lines > LINES_PER_SIZE_POINT:
        add(
            "size",
            "Size of the unit",
            min(SIZE_CAP, lines / LINES_PER_SIZE_POINT),
            f"{lines} lines in one body: more surface for a review to miss something.",
            (f"{lines} lines",),
            "Whether this should be split during migration",
        )

    raw = sum(f.points for f in factors)
    score = score_from_raw(raw)
    level = level_for(score)
    for factor in factors:
        if factor.floor and _LEVEL_RANK[factor.floor] > _LEVEL_RANK[level]:
            level = factor.floor

    areas: list[str] = []
    for factor in sorted(factors, key=lambda f: -f.points):
        if factor.review_area and factor.review_area not in areas:
            areas.append(factor.review_area)

    return RiskResult(
        level=level,
        score=score,
        raw=raw,
        factors=sorted(factors, key=lambda f: -f.points),
        review_areas=areas,
    )


def explain() -> dict:
    """The scoring model, stated rather than implied.

    The UI prints this next to the score. A number a reviewer cannot audit
    is a number a reviewer should not trust.
    """
    return {
        "version": VERSION,
        "formula": "score = 100 * (1 - 0.5 ** (raw / 12))",
        "thresholds": {
            "LOW": "score < 20",
            "MEDIUM": "20 <= score < 45",
            "HIGH": "45 <= score < 70, or forced by a construct weighing >= 0.80",
            "CRITICAL": "score >= 70 -- several dangerous constructs at once",
        },
        "inputs": [
            "catalog risk weight of every built-in found, damped by log2 of its count",
            "risk weight of the trigger point",
            "Forms system variables read",
            "global variables touched",
            "dynamic SQL and DDL",
            "direct DML and whether it is guarded by an exception handler",
            "other Forms modules called",
            "indirect access whose target is computed at runtime",
            "constructs outside the catalog",
            "size of the body",
        ],
        "not_inputs": [
            "the AI provider's opinion",
            "model confidence",
            "how long the conversion took",
        ],
    }
