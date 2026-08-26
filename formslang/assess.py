"""Assessment: from Forms module to defensible numbers.

Three honesty rules are built into this module, because migration assessment
is the classic place where numbers get invented:

1. **Effort is reported in POINTS, not hours.** A point is derived from what
   was actually counted in the XML. Turning points into hours requires a
   calibration factor (``hours_per_point``) that can only come from measured
   real conversions. The default is declared in the report as an ASSUMPTION,
   never as a measurement.

2. **``UNKNOWN`` never becomes ``AUTO``.** Whatever the catalog does not know
   is weighted as expensive and is named in the report, so the catalog grows
   against reality instead of against imagination.

3. **Copy-paste is charged once.** Legacy Forms systems are built by cloning
   a template form, so the same boilerplate exists in every module. Counting
   it once per module inflates the total by whatever the boilerplate is
   worth. Every code body is fingerprinted; blocks that appear in more than
   one module are solved once at portfolio level and only reviewed in the
   copies. Both totals are reported -- raw and deduplicated -- so nothing is
   hidden by the correction.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from . import rules
from .model import FormModule
from .plsql import CodeAnalysis, analyze, fingerprint

# Calibration ASSUMPTION, not a measurement. Overridable via --hours-per-point.
HOURS_PER_POINT_DEFAULT = 0.25

# Reviewing a line of PL/SQL costs time even when every built-in in it is
# portable. Weight per line of code.
VOLUME_PER_LINE = 0.06

# What a duplicated code block still costs after the original was converted:
# someone must confirm it really is identical and wire it into its module.
# ASSUMPTION, same status as hours_per_point.
DUPLICATE_REVIEW_FACTOR = 0.15

# Complexity tiers, in deduplicated points per module.
TIERS = (
    (0, 120, "SIMPLE", "Straight CRUD: table block, few rules of its own"),
    (120, 300, "MODERATE", "CRUD with validation and LOVs; assisted conversion"),
    (300, 700, "COMPLEX", "Heavy business logic in the screen; review case by case"),
    (700, 10**9, "REWRITE", "Converting costs about as much as rewriting"),
)


@dataclass
class CodeUnit:
    """One trigger or program unit, priced on its own.

    Pricing per instance (instead of per module) is what makes portfolio
    deduplication possible: a shared block can be discounted exactly where it
    is, without disturbing the rest of the module.
    """

    kind: str  # "trigger" | "program_unit"
    name: str
    owner: str
    verdict: str
    lines: int
    points: float
    fingerprint: str = ""
    modules_sharing: int = 1  # filled in by the portfolio pass


@dataclass
class ModuleAssessment:
    """Full verdict for a single .fmb."""

    name: str
    source_path: str = ""

    # Structure
    blocks: int = 0
    database_blocks: int = 0
    items: int = 0
    database_items: int = 0
    triggers: int = 0
    program_units: int = 0
    lovs: int = 0
    record_groups: int = 0
    relations: int = 0
    canvases: int = 0
    windows: int = 0
    alerts: int = 0
    tab_pages: int = 0
    reports: int = 0
    attached_libraries: list[str] = field(default_factory=list)
    plsql_lines: int = 0

    # Classification
    trigger_verdicts: Counter[str] = field(default_factory=Counter)
    builtin_verdicts: Counter[str] = field(default_factory=Counter)
    code: CodeAnalysis = field(default_factory=CodeAnalysis)
    units: list[CodeUnit] = field(default_factory=list)

    # Result
    structure_points: float = 0.0
    points: float = 0.0  # raw, before portfolio deduplication
    net_points: float = 0.0  # after deduplication; equals points until finalize()
    shared_lines: int = 0  # PL/SQL lines living in blocks shared with other modules
    tier: str = ""
    tier_note: str = ""
    automatable_pct: float = 0.0
    blockers: list[tuple[str, str, int]] = field(default_factory=list)
    manual_triggers: list[tuple[str, str]] = field(default_factory=list)
    unknown_triggers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def hours(self, hours_per_point: float = HOURS_PER_POINT_DEFAULT) -> float:
        return round(self.net_points * hours_per_point, 1)

    def to_dict(self, hours_per_point: float = HOURS_PER_POINT_DEFAULT) -> dict:
        return {
            "name": self.name,
            "source_path": self.source_path,
            "structure": {
                "blocks": self.blocks,
                "database_blocks": self.database_blocks,
                "items": self.items,
                "database_items": self.database_items,
                "triggers": self.triggers,
                "program_units": self.program_units,
                "lovs": self.lovs,
                "record_groups": self.record_groups,
                "relations": self.relations,
                "canvases": self.canvases,
                "windows": self.windows,
                "alerts": self.alerts,
                "tab_pages": self.tab_pages,
                "reports": self.reports,
                "attached_libraries": self.attached_libraries,
                "plsql_lines": self.plsql_lines,
                "shared_plsql_lines": self.shared_lines,
            },
            "triggers_by_verdict": dict(self.trigger_verdicts),
            "builtins_by_verdict": dict(self.builtin_verdicts),
            "top_builtins": self.code.builtins.most_common(15),
            "globals": self.code.globals_used.most_common(10),
            "sql": dict(self.code.sql_verbs),
            "points_raw": round(self.points, 1),
            "points": round(self.net_points, 1),
            "estimated_hours": self.hours(hours_per_point),
            "tier": self.tier,
            "tier_note": self.tier_note,
            "automatable_pct": self.automatable_pct,
            "blockers": [
                {"builtin": b, "reason": r, "occurrences": n} for b, r, n in self.blockers
            ],
            "manual_triggers": [
                {"trigger": t, "reason": r} for t, r in self.manual_triggers
            ],
            "unknown_triggers": self.unknown_triggers,
            "warnings": self.warnings,
        }


def _tier(points: float) -> tuple[str, str]:
    for lo, hi, name, note in TIERS:
        if lo <= points < hi:
            return name, note
    return TIERS[-1][2], TIERS[-1][3]


def _unit_points(verdict_weight: float, lines: int, code: CodeAnalysis) -> float:
    """Cost of a single code body.

    Built-ins inside one body are damped: the first SET_ITEM_PROPERTY costs a
    decision, the tenth in the same body is the same pattern repeated.
    """
    total = verdict_weight + lines * VOLUME_PER_LINE
    for name, n in code.builtins.items():
        weight = rules.VERDICT_WEIGHT[rules.classify_builtin(name)[0]]
        total += weight * (1.0 + math.log2(n))
    return total


def assess_module(mod: FormModule) -> ModuleAssessment:
    """Classify a whole module and compute its effort points."""
    a = ModuleAssessment(name=mod.name, source_path=mod.source_path)

    # -- structure ---------------------------------------------------------
    a.blocks = len(mod.blocks)
    a.database_blocks = sum(1 for b in mod.blocks if b.database_block)
    items = mod.all_items
    a.items = len(items)
    a.database_items = sum(1 for i in items if i.database_item)
    triggers = mod.all_triggers
    a.triggers = len(triggers)
    a.program_units = len(mod.program_units)
    a.lovs = len(mod.lovs)
    a.record_groups = len(mod.record_groups)
    a.relations = len(mod.relations)
    a.canvases = len(mod.canvases)
    a.windows = len(mod.windows)
    a.alerts = len(mod.alerts)
    a.tab_pages = len(mod.tab_pages)
    a.reports = len(mod.reports)
    a.attached_libraries = list(mod.attached_libraries)
    a.plsql_lines = mod.plsql_lines

    # What APEX generates on its own is cheap; what does not exist in APEX
    # (windows, canvases) costs a layout decision.
    a.structure_points = (
        a.database_blocks * 3.0
        + (a.blocks - a.database_blocks) * 1.5
        + a.database_items * 0.15
        + (a.items - a.database_items) * 0.4
        + a.lovs * 1.0
        + a.record_groups * 1.5
        + a.relations * 3.0
        + max(0, a.canvases - 1) * 2.0
        + max(0, a.windows - 1) * 2.0
        + a.tab_pages * 1.0
        + a.reports * 8.0
    )

    # -- code, one unit at a time ------------------------------------------
    for t in triggers:
        verdict, reason = rules.classify_trigger(t.name)
        a.trigger_verdicts[verdict] += 1
        if verdict == rules.MANUAL:
            a.manual_triggers.append((t.name, reason))
        elif verdict == rules.UNKNOWN:
            a.unknown_triggers.append(t.name)

        an = analyze(t.text)
        a.code.merge(an)
        a.units.append(
            CodeUnit(
                kind="trigger",
                name=t.name,
                owner=t.owner,
                verdict=verdict,
                lines=t.lines,
                points=_unit_points(rules.VERDICT_WEIGHT[verdict], t.lines, an),
                fingerprint=fingerprint(t.text),
            )
        )

    for p in mod.program_units:
        an = analyze(p.text)
        a.code.merge(an)
        # A program unit has no trigger verdict: it is plain PL/SQL that
        # mostly moves to a package. Its cost is volume plus what it calls.
        a.units.append(
            CodeUnit(
                kind="program_unit",
                name=p.name,
                owner="",
                verdict="",
                lines=p.lines,
                points=_unit_points(0.0, p.lines, an),
                fingerprint=fingerprint(p.text),
            )
        )

    a.manual_triggers = sorted(set(a.manual_triggers))
    a.unknown_triggers = sorted(set(a.unknown_triggers))
    a.builtin_verdicts = a.code.verdict_counts()
    a.blockers = a.code.blockers()

    a.points = a.structure_points + sum(u.points for u in a.units)
    # Until a portfolio pass runs, nothing is known to be shared.
    a.net_points = a.points
    a.tier, a.tier_note = _tier(a.net_points)

    # -- automatable share -------------------------------------------------
    total = sum(a.trigger_verdicts.values()) + sum(a.builtin_verdicts.values())
    if total:
        favourable = (
            a.trigger_verdicts[rules.AUTO]
            + a.trigger_verdicts[rules.DROP]
            + a.builtin_verdicts[rules.AUTO]
            + a.builtin_verdicts[rules.DROP]
        )
        a.automatable_pct = round(100.0 * favourable / total, 1)

    # -- warnings ----------------------------------------------------------
    if mod.convert_warnings:
        a.warnings.append(
            f"{len(mod.convert_warnings)} broken reference(s) reported by Forms2XML"
        )
    if a.code.unknown_calls:
        external = sum(1 for k in a.code.unknown_calls if "." in k)
        if external:
            a.warnings.append(
                f"{external} call(s) to external packages: database dependency to inventory"
            )
    if a.blocks == 0:
        a.warnings.append("Module has no blocks: likely a utility or flow-control form")
    if a.code.globals_used:
        a.warnings.append(
            f"{len(a.code.globals_used)} :GLOBAL variable(s) -- state shared across screens"
        )
    return a


# --------------------------------------------------------------------------
# Portfolio
# --------------------------------------------------------------------------
@dataclass
class SharedBlock:
    """One code body that exists, byte for byte, in more than one module."""

    fingerprint: str
    sample_name: str
    kind: str
    lines: int
    unit_points: float
    modules: int
    instances: int

    @property
    def redundant_points(self) -> float:
        """Points charged for the copies, over and above solving it once."""
        return self.unit_points * (self.instances - 1)


@dataclass
class PortfolioAssessment:
    """Aggregated view of an entire module portfolio."""

    modules: list[ModuleAssessment] = field(default_factory=list)
    failures: list[tuple[str, str]] = field(default_factory=list)
    hours_per_point: float = HOURS_PER_POINT_DEFAULT
    shared_blocks: list[SharedBlock] = field(default_factory=list)
    shared_once_points: float = 0.0
    finalized: bool = False

    # -- deduplication -----------------------------------------------------
    def finalize(self) -> None:
        """Second pass: find copy-paste across modules and reprice.

        A block present in two or more modules is real work exactly once. The
        copies keep only a review cost (``DUPLICATE_REVIEW_FACTOR``), and the
        one full price is held at portfolio level instead of being charged to
        an arbitrarily chosen module.
        """
        by_print: dict[str, list[tuple[ModuleAssessment, CodeUnit]]] = defaultdict(list)
        for m in self.modules:
            for u in m.units:
                if u.fingerprint:
                    by_print[u.fingerprint].append((m, u))

        self.shared_blocks = []
        self.shared_once_points = 0.0
        for fp, pairs in by_print.items():
            owners = {m.name for m, _ in pairs}
            if len(owners) < 2:
                continue
            sample = pairs[0][1]
            for _m, u in pairs:
                u.modules_sharing = len(owners)
            self.shared_blocks.append(
                SharedBlock(
                    fingerprint=fp,
                    sample_name=sample.name,
                    kind=sample.kind,
                    lines=sample.lines,
                    unit_points=sample.points,
                    modules=len(owners),
                    instances=len(pairs),
                )
            )
            self.shared_once_points += sample.points

        self.shared_blocks.sort(key=lambda s: -s.redundant_points)

        for m in self.modules:
            net = m.structure_points
            shared_lines = 0
            for u in m.units:
                if u.modules_sharing > 1:
                    net += u.points * DUPLICATE_REVIEW_FACTOR
                    shared_lines += u.lines
                else:
                    net += u.points
            m.net_points = net
            m.shared_lines = shared_lines
            m.tier, m.tier_note = _tier(net)

        self.modules.sort(key=lambda m: -m.net_points)
        self.finalized = True

    # -- totals ------------------------------------------------------------
    @property
    def raw_points(self) -> float:
        """Total before deduplication: every copy charged in full."""
        return sum(m.points for m in self.modules)

    @property
    def total_points(self) -> float:
        """Total after deduplication, including solving each shared block once."""
        return sum(m.net_points for m in self.modules) + self.shared_once_points

    @property
    def duplication_savings(self) -> float:
        return max(0.0, self.raw_points - self.total_points)

    @property
    def total_hours(self) -> float:
        return round(self.total_points * self.hours_per_point, 1)

    @property
    def shared_instances(self) -> int:
        return sum(s.instances for s in self.shared_blocks)

    def by_tier(self) -> Counter[str]:
        return Counter(m.tier for m in self.modules)

    def aggregate_builtins(self) -> Counter[str]:
        out: Counter[str] = Counter()
        for m in self.modules:
            out.update(m.code.builtins)
        return out

    def aggregate_blockers(self) -> Counter[str]:
        """MANUAL built-in -> in how many MODULES it appears (not occurrences)."""
        out: Counter[str] = Counter()
        for m in self.modules:
            for name, _reason, _n in m.blockers:
                out[name] += 1
        return out

    def aggregate_trigger_verdicts(self) -> Counter[str]:
        out: Counter[str] = Counter()
        for m in self.modules:
            out.update(m.trigger_verdicts)
        return out

    def aggregate_builtin_verdicts(self) -> Counter[str]:
        out: Counter[str] = Counter()
        for m in self.modules:
            out.update(m.builtin_verdicts)
        return out

    def unknown_catalog_debt(self) -> tuple[Counter[str], Counter[str]]:
        """What the catalog does not know yet: (triggers, calls)."""
        trig: Counter[str] = Counter()
        calls: Counter[str] = Counter()
        for m in self.modules:
            trig.update(m.unknown_triggers)
            for name, n in m.code.unknown_calls.items():
                calls[name] += n
        return trig, calls

    def automatable_pct(self) -> float:
        tv = self.aggregate_trigger_verdicts()
        bv = self.aggregate_builtin_verdicts()
        total = sum(tv.values()) + sum(bv.values())
        if not total:
            return 0.0
        fav = tv[rules.AUTO] + tv[rules.DROP] + bv[rules.AUTO] + bv[rules.DROP]
        return round(100.0 * fav / total, 1)

    def to_dict(self) -> dict:
        trig_debt, call_debt = self.unknown_catalog_debt()
        total_units = sum(len(m.units) for m in self.modules)
        return {
            "summary": {
                "modules_analyzed": len(self.modules),
                "modules_failed": len(self.failures),
                "total_points": round(self.total_points, 1),
                "raw_points": round(self.raw_points, 1),
                "duplication_savings": round(self.duplication_savings, 1),
                "hours_per_point": self.hours_per_point,
                "duplicate_review_factor": DUPLICATE_REVIEW_FACTOR,
                "estimated_hours": self.total_hours,
                "automatable_pct": self.automatable_pct(),
                "by_tier": dict(self.by_tier()),
                "catalog": rules.catalog_size(),
            },
            "totals": {
                "blocks": sum(m.blocks for m in self.modules),
                "items": sum(m.items for m in self.modules),
                "triggers": sum(m.triggers for m in self.modules),
                "program_units": sum(m.program_units for m in self.modules),
                "lovs": sum(m.lovs for m in self.modules),
                "relations": sum(m.relations for m in self.modules),
                "reports": sum(m.reports for m in self.modules),
                "plsql_lines": sum(m.plsql_lines for m in self.modules),
                "shared_plsql_lines": sum(m.shared_lines for m in self.modules),
            },
            "duplication": {
                "code_units": total_units,
                "shared_blocks": len(self.shared_blocks),
                "shared_instances": self.shared_instances,
                "shared_once_points": round(self.shared_once_points, 1),
                "top": [
                    {
                        "name": s.sample_name,
                        "kind": s.kind,
                        "lines": s.lines,
                        "modules": s.modules,
                        "instances": s.instances,
                        "unit_points": round(s.unit_points, 1),
                        "redundant_points": round(s.redundant_points, 1),
                    }
                    for s in self.shared_blocks[:30]
                ],
            },
            "triggers_by_verdict": dict(self.aggregate_trigger_verdicts()),
            "builtins_by_verdict": dict(self.aggregate_builtin_verdicts()),
            "top_builtins": self.aggregate_builtins().most_common(30),
            "blockers_by_module": self.aggregate_blockers().most_common(30),
            "catalog_debt": {
                "unknown_triggers": trig_debt.most_common(30),
                "uncatalogued_calls": call_debt.most_common(40),
            },
            "failures": [{"file": f, "error": e} for f, e in self.failures],
            "modules": [m.to_dict(self.hours_per_point) for m in self.modules],
        }
