"""One analysis pass over one code unit: compatibility, risk, behaviour.

This module is the seam between the deterministic layers and everything
that consumes them (the store, the UI, the dashboard, the exporter). It
answers three questions about a single trigger or program unit, and it
answers all three from the source text alone:

* **What Forms constructs are in here, and what does APEX do about them?**
  -- :class:`CompatFinding`, one per built-in found, straight out of the
  structured catalog in :mod:`formslang.rules`.
* **How dangerous is it to get this wrong?** -- :mod:`formslang.risk`.
* **Does it still behave the same way afterwards?** -- :mod:`formslang.behavior`.

No AI call happens here, and none should. The model may later enrich the
explanations through :func:`formslang.behavior.merge_ai`, which can only
make the answer more conservative.

Every result carries :data:`ENGINE_VERSION`, a fingerprint of the rules that
produced it. When the catalog or a scoring weight changes, the version
changes with it and stored analyses are known to be stale -- an analysis
that cannot say which rules produced it is not auditable.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from . import behavior as behavior_mod
from . import risk as risk_mod
from . import rules
from . import sensitive as sensitive_mod
from .behavior import BehaviorResult
from .plsql import CodeAnalysis, analyze
from .risk import RiskResult
from .sensitive import ScanResult


def _engine_version() -> str:
    """Identity of the rule set, not just of the code that runs it.

    A stored analysis is only trustworthy if you can tell whether the rules
    have moved since. Hashing the catalog rows and the trigger weights means
    changing one risk number invalidates every cached analysis, which is the
    behaviour we want -- silently serving a score computed under older rules
    is the kind of quiet drift this product exists to prevent.
    """
    parts = [
        f"{s.name}:{s.verdict}:{s.migration_class}:{s.risk:.2f}"
        for s in rules.CATALOG.values()
    ]
    parts.append("--triggers--")
    parts += [f"{k}:{v[0]:.2f}" for k, v in sorted(rules.TRIGGER_RISK.items())]
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:10]
    return (
        f"analysis/1+{risk_mod.VERSION}+{behavior_mod.VERSION}"
        f"+{sensitive_mod.VERSION}+catalog:{digest}"
    )


ENGINE_VERSION = _engine_version()


@dataclass(frozen=True)
class CompatFinding:
    """One Forms construct found in the body, with its migration strategy."""

    name: str
    category: str
    category_label: str
    migration_class: str
    verdict: str
    apex: str
    forms_behavior: str
    risk: float
    count: int = 1
    known: bool = True
    targets: tuple[str, ...] = ()   # literal arguments captured from the call

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "category": self.category,
            "category_label": self.category_label,
            "migration_class": self.migration_class,
            "verdict": self.verdict,
            "apex": self.apex,
            "forms_behavior": self.forms_behavior,
            "risk": round(self.risk, 2),
            "count": self.count,
            "known": self.known,
            "targets": list(self.targets),
        }

    @classmethod
    def from_dict(cls, raw: dict) -> CompatFinding:
        return cls(
            name=raw.get("name", ""),
            category=raw.get("category", "unknown"),
            category_label=raw.get("category_label", ""),
            migration_class=raw.get("migration_class", rules.MANUAL_REVIEW),
            verdict=raw.get("verdict", rules.UNKNOWN),
            apex=raw.get("apex", ""),
            forms_behavior=raw.get("forms_behavior", ""),
            risk=float(raw.get("risk", 0.0)),
            count=int(raw.get("count", 1)),
            known=bool(raw.get("known", True)),
            targets=tuple(raw.get("targets", ())),
        )


@dataclass
class UnitAnalysis:
    """Everything the deterministic layers know about one code unit."""

    task_id: str = ""
    module: str = ""
    kind: str = "trigger"
    name: str = ""
    owner: str = ""
    verdict: str = rules.UNKNOWN
    fingerprint: str = ""
    risk: RiskResult = field(default_factory=RiskResult)
    behavior: BehaviorResult = field(default_factory=BehaviorResult)
    findings: list[CompatFinding] = field(default_factory=list)
    sensitive: ScanResult = field(default_factory=ScanResult)
    engine_version: str = ENGINE_VERSION

    @property
    def title(self) -> str:
        return f"{self.owner}.{self.name}" if self.owner else self.name

    @property
    def review_areas(self) -> list[str]:
        return list(self.risk.review_areas)

    @property
    def unsupported(self) -> list[CompatFinding]:
        """Findings APEX has no answer for. The honest bad news of a portfolio."""
        return [f for f in self.findings if f.migration_class == rules.UNSUPPORTED]

    @property
    def stale(self) -> bool:
        """True when the rules have moved since this analysis was computed."""
        return self.engine_version != ENGINE_VERSION

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "module": self.module,
            "kind": self.kind,
            "name": self.name,
            "owner": self.owner,
            "title": self.title,
            "verdict": self.verdict,
            "fingerprint": self.fingerprint,
            "risk": self.risk.to_dict(),
            "behavior": self.behavior.to_dict(),
            "findings": [f.to_dict() for f in self.findings],
            "sensitive": self.sensitive.to_dict(),
            "review_areas": self.review_areas,
            "engine_version": self.engine_version,
            "stale": self.stale,
        }

    @classmethod
    def from_dict(cls, raw: dict) -> UnitAnalysis:
        """Rebuild from what the store persisted, tolerating older shapes."""
        risk_raw = raw.get("risk") or {}
        beh_raw = raw.get("behavior") or {}
        risk = RiskResult(
            level=risk_raw.get("level", risk_mod.LOW),
            score=float(risk_raw.get("score", 0.0)),
            raw=float(risk_raw.get("raw", 0.0)),
            factors=[
                risk_mod.RiskFactor(
                    id=f.get("id", ""),
                    title=f.get("title", ""),
                    points=float(f.get("points", 0.0)),
                    detail=f.get("detail", ""),
                    evidence=tuple(f.get("evidence", ())),
                    review_area=f.get("review_area", ""),
                    floor=f.get("floor", ""),
                )
                for f in risk_raw.get("factors", [])
            ],
            review_areas=list(risk_raw.get("review_areas", [])),
            version=risk_raw.get("version", risk_mod.VERSION),
        )
        beh = BehaviorResult(
            value=beh_raw.get("value", behavior_mod.UNCERTAIN),
            reasons=list(beh_raw.get("reasons", [])),
            uncertainties=list(beh_raw.get("uncertainties", [])),
            source=beh_raw.get("source", "rules"),
            version=beh_raw.get("version", behavior_mod.VERSION),
        )
        sens_raw = raw.get("sensitive") or {}
        sens = ScanResult(
            findings=[
                sensitive_mod.Finding(
                    id=f.get("id", ""),
                    category=f.get("category", sensitive_mod.CREDENTIAL),
                    title=f.get("title", ""),
                    severity=f.get("severity", sensitive_mod.LOW),
                    confidence=f.get("confidence", sensitive_mod.POSSIBLE),
                    line=int(f.get("line", 0)),
                    excerpt=f.get("excerpt", ""),
                    detail=f.get("detail", ""),
                    in_comment=bool(f.get("in_comment", False)),
                )
                for f in sens_raw.get("findings", [])
            ],
            counts=dict(sens_raw.get("counts", {})),
            level=sens_raw.get("level", sensitive_mod.LOW),
            version=sens_raw.get("version", sensitive_mod.VERSION),
        )
        return cls(
            task_id=raw.get("task_id", ""),
            module=raw.get("module", ""),
            kind=raw.get("kind", "trigger"),
            name=raw.get("name", ""),
            owner=raw.get("owner", ""),
            verdict=raw.get("verdict", rules.UNKNOWN),
            fingerprint=raw.get("fingerprint", ""),
            risk=risk,
            behavior=beh,
            findings=[CompatFinding.from_dict(f) for f in raw.get("findings", [])],
            sensitive=sens,
            engine_version=raw.get("engine_version", "unknown"),
        )


def compat_findings(code: CodeAnalysis) -> list[CompatFinding]:
    """Turn the built-ins found in a body into catalog-backed findings.

    Ordered by risk, then by how often the construct appears, then by name --
    so the first row a reviewer reads is the one most likely to hurt.
    """
    targets: dict[str, list[str]] = {}
    for ref in code.literals:
        if ref.value:
            bucket = targets.setdefault(ref.builtin, [])
            if ref.value not in bucket:
                bucket.append(ref.value)

    out: list[CompatFinding] = []
    for name, count in code.builtins.items():
        spec = rules.spec_for(name)
        category = rules.CATEGORIES.get(spec.category)
        out.append(
            CompatFinding(
                name=name,
                category=spec.category,
                category_label=category.label if category else spec.category,
                migration_class=spec.migration_class,
                verdict=spec.verdict,
                apex=spec.apex,
                forms_behavior=spec.forms_behavior,
                risk=spec.risk,
                count=count,
                known=spec.known,
                targets=tuple(targets.get(name, ())),
            )
        )
    out.sort(key=lambda f: (-f.risk, -f.count, f.name))
    return out


def analyze_unit(
    source: str,
    *,
    kind: str = "trigger",
    name: str = "",
    owner: str = "",
    module: str = "",
    verdict: str = "",
    task_id: str = "",
    fingerprint: str = "",
    code: CodeAnalysis | None = None,
) -> UnitAnalysis:
    """Run the deterministic stack over one body of PL/SQL.

    ``code`` may be passed in when the caller already parsed the body, which
    is the common case during a module load: parsing twice would change no
    answer and only cost time.
    """
    text = source or ""
    parsed = code if code is not None else analyze(text)
    trigger_name = name if kind == "trigger" else ""
    if not verdict:
        verdict = rules.classify_trigger(name)[0] if kind == "trigger" else rules.ASSISTED
    return UnitAnalysis(
        task_id=task_id,
        module=module,
        kind=kind,
        name=name,
        owner=owner,
        verdict=verdict,
        fingerprint=fingerprint,
        risk=risk_mod.assess(
            parsed, kind=kind, trigger_name=trigger_name, verdict=verdict, source=text
        ),
        behavior=behavior_mod.classify(
            parsed, kind=kind, trigger_name=trigger_name, verdict=verdict, source=text
        ),
        findings=compat_findings(parsed),
        sensitive=sensitive_mod.scan(text),
        engine_version=ENGINE_VERSION,
    )


def analyze_task(task) -> UnitAnalysis:
    """Analyse a :class:`formslang.convert.ConversionTask`.

    Typed loosely on purpose: importing ``convert`` here would close a cycle,
    since ``convert`` reads analyses when it builds prompts.
    """
    return analyze_unit(
        task.source,
        kind=task.kind,
        name=task.name,
        owner=task.owner,
        module=task.module,
        verdict=task.verdict,
        task_id=task.id,
        fingerprint=getattr(task, "fingerprint", ""),
    )


def summarize(analyses) -> dict:
    """Aggregate counts over many units, for the dashboard and the CLI.

    Counts only what was measured. A unit whose analysis is missing is not
    silently filed as LOW risk -- it is simply not in the totals, and the
    caller can tell by comparing ``total`` against its own task count.
    """
    risk_counts = {level: 0 for level in risk_mod.RISK_LEVELS}
    behavior_counts = {value: 0 for value in behavior_mod.BEHAVIORS}
    classes = {name: 0 for name in rules.MIGRATION_CLASSES}
    unsupported: dict[str, int] = {}
    categories: dict[str, int] = {}
    stale = 0
    score_total = 0.0
    total = 0

    for item in analyses:
        total += 1
        risk_counts[item.risk.level] = risk_counts.get(item.risk.level, 0) + 1
        behavior_counts[item.behavior.value] = behavior_counts.get(item.behavior.value, 0) + 1
        score_total += item.risk.score
        if item.stale:
            stale += 1
        for finding in item.findings:
            classes[finding.migration_class] = classes.get(finding.migration_class, 0) + 1
            categories[finding.category] = categories.get(finding.category, 0) + finding.count
            if finding.migration_class == rules.UNSUPPORTED:
                unsupported[finding.name] = unsupported.get(finding.name, 0) + finding.count

    return {
        "total": total,
        "risk": risk_counts,
        "behavior": behavior_counts,
        "migration_classes": classes,
        "categories": dict(sorted(categories.items(), key=lambda kv: -kv[1])),
        "unsupported": dict(sorted(unsupported.items(), key=lambda kv: -kv[1])),
        "avg_score": round(score_total / total, 1) if total else 0.0,
        "stale": stale,
        "engine_version": ENGINE_VERSION,
    }
