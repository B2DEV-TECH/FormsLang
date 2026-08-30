"""Conversion: from a classified Forms module to reviewable APEX proposals.

The unit of work is one code body -- a trigger or a program unit -- not a
whole form. That is what makes the output reviewable: a human approves or
rejects something small enough to actually read, and the audit trail records
which human approved what.

Two rules shape everything here:

1. **The model proposes, a human decides.** Nothing produced in this module
   is applied anywhere. A proposal is a suggestion attached to a task until
   somebody approves it in the workbench.

2. **Copy-paste is converted once.** Bodies are keyed by the same
   fingerprint the assessment uses, so a block pasted into four hundred
   modules is sent to the model once and its proposal is reused. The saving
   the report predicts is the saving the pipeline actually takes.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field

from . import rules
from .ai import DEFAULT_MAX_TOKENS, Message, Provider, ProviderError
from .analysis import analyze_task
from .model import FormModule
from .plsql import analyze, fingerprint

# Bodies below this size are noise ("NULL;", "COMMIT_FORM;") -- they cost a
# model call and produce nothing a reviewer needs.
MIN_SOURCE_CHARS = 12


SYSTEM_PROMPT = """\
You convert Oracle Forms code to Oracle APEX (24.2+). You are one step in a
pipeline: your output is reviewed by an Oracle engineer before it is used
anywhere. Optimise for a proposal that is easy to verify, not for one that
looks finished.

CONVERSION DOCTRINE

- Preserve the business rule exactly. Do not simplify it, do not "improve"
  it, do not fix bugs you think you see. Report them in `notes` instead.
- Forms item references (`:BLOCK.ITEM`) become APEX page items. The page
  number is not known at this stage: use `:P0_<ITEM>` and add an
  `open_question` naming the items that must be re-pointed.
- `:GLOBAL.X` has no APEX equivalent. Propose an application item or a
  collection, and say which one you chose and why.
- Trigger points do not map one to one. A per-row `POST-QUERY` lookup is
  normally a join in the region source, not a loop -- if you see that, say
  so in `notes`; it is usually the largest single win in the module.
- `WHEN-VALIDATE-ITEM` becomes a page validation; `WHEN-BUTTON-PRESSED`
  becomes a page process or dynamic action; `KEY-*` triggers usually
  disappear with the Forms runtime.
- Navigation built-ins (`GO_BLOCK`, `GO_ITEM`, `NEXT_RECORD`) have no
  server-side equivalent. Remove them and note what the code was steering,
  or propose focus handling in JavaScript when it carries real intent.
- `COMMIT_FORM` / `POST` are handled by the APEX page processing model.
  Remove them and say so rather than inventing an API call.
- `MESSAGE`/`ALERT` become `apex_error.add_error`, an inline item error, or
  a success message -- pick one and justify it in a note.
- WebUtil, `HOST`, OLE and Oracle Reports calls have NO equivalent. Do not
  fabricate one. Describe the APEX-native redesign (file upload region,
  `apex_web_service`, BI Publisher, ORDS) and set a low confidence.

HONESTY RULES -- these outrank everything above

- Never invent an APEX package, procedure or attribute. If you are not
  certain an API exists with that exact name, do not write it: describe the
  intent in `notes` and lower `confidence`.
- Never silently drop code. Anything you removed must appear in `notes`
  with the reason.
- If the source is ambiguous, ship the ambiguity: list it in
  `open_questions` and set `confidence` at or below 0.4.
- `confidence` is your estimate that an Oracle engineer would approve this
  unchanged. 0.9+ means mechanical. Anything touching architecture,
  external systems or global state is below 0.5.
- Write every human-readable string -- `apex_target`, `notes`,
  `open_questions` and code comments -- in English, whatever language the
  source code, its comments or the user's environment use.
- When a note affects migration safety, label what kind of statement it is:
  start it with FACT (in the source you were given), INFERENCE (derived from
  it), ASSUMPTION (you needed it and it is unverified) or RECOMMENDATION.
  A reviewer must be able to tell what you read from what you decided.

WHAT YOU ARE GIVEN, AND WHAT YOU MAY NOT CONTRADICT

The message includes a deterministic analysis produced by a rule engine:
built-in classifications, a risk level and a behaviour classification. Those
are measured facts about the Forms source, not opinions, and they are shown
to the reviewer next to your answer.

- Do not restate them and do not argue with them.
- `behavior` in your output is a second opinion, used only if it is more
  conservative than the rules. Answer PRESERVED only when you are certain
  nothing observable differs. If the engine already said CHANGED or
  UNCERTAIN, saying PRESERVED will be ignored.

OUTPUT

Return one JSON object and nothing else -- no prose, no markdown fence:

{
  "apex_target": "short phrase: where this lives in APEX",
  "code": "the PL/SQL / JavaScript to put there",
  "notes": ["what changed and why"],
  "open_questions": ["what a human must decide"],
  "behavior": "PRESERVED | CHANGED | UNCERTAIN",
  "behavior_reason": "one sentence, only if it is not PRESERVED",
  "confidence": 0.0
}
"""


@dataclass
class ConversionTask:
    """One code body queued for conversion."""

    id: str
    module: str
    kind: str  # "trigger" | "program_unit"
    name: str
    owner: str
    verdict: str
    apex_hint: str
    source: str
    lines: int
    fingerprint: str = ""
    builtins: list[tuple[str, str, str]] = field(default_factory=list)
    item_refs: list[str] = field(default_factory=list)
    globals_used: list[str] = field(default_factory=list)

    @property
    def title(self) -> str:
        return f"{self.owner}.{self.name}" if self.owner else self.name

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "module": self.module,
            "kind": self.kind,
            "name": self.name,
            "owner": self.owner,
            "title": self.title,
            "verdict": self.verdict,
            "apex_hint": self.apex_hint,
            "source": self.source,
            "lines": self.lines,
            "fingerprint": self.fingerprint,
            "builtins": [
                {"name": n, "verdict": v, "apex": a} for n, v, a in self.builtins
            ],
            "item_refs": self.item_refs,
            "globals": self.globals_used,
        }


@dataclass
class Proposal:
    """What the model came back with. Never applied without approval."""

    apex_target: str = ""
    code: str = ""
    notes: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    confidence: float = 0.0
    provider: str = ""
    model: str = ""
    error: str = ""
    raw: str = ""
    # The model's own read on behaviour. Advisory only: it is folded into the
    # analysis through behavior.merge_ai, which ignores it unless it is more
    # conservative than what the rules already found.
    behavior: str = ""
    behavior_reason: str = ""

    @property
    def ok(self) -> bool:
        return not self.error

    def to_dict(self) -> dict:
        return {
            "apex_target": self.apex_target,
            "code": self.code,
            "notes": self.notes,
            "open_questions": self.open_questions,
            "confidence": self.confidence,
            "provider": self.provider,
            "model": self.model,
            "error": self.error,
            "behavior": self.behavior,
            "behavior_reason": self.behavior_reason,
        }


def _task_id(module: str, kind: str, owner: str, name: str) -> str:
    key = f"{module}|{kind}|{owner}|{name}".upper()
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


def build_tasks(mod: FormModule) -> list[ConversionTask]:
    """Turn a parsed module into the queue a reviewer will work through.

    Ordered the way a human reads a form: form-level triggers, then block by
    block, then the program units.
    """
    tasks: list[ConversionTask] = []

    def add(kind: str, name: str, owner: str, text: str, verdict: str, hint: str) -> None:
        if not text or len(text.strip()) < MIN_SOURCE_CHARS:
            return
        an = analyze(text)
        tasks.append(
            ConversionTask(
                id=_task_id(mod.name, kind, owner, name),
                module=mod.name,
                kind=kind,
                name=name,
                owner=owner,
                verdict=verdict,
                apex_hint=hint,
                source=text,
                lines=text.count("\n") + 1,
                fingerprint=fingerprint(text),
                builtins=[
                    (b, *rules.classify_builtin(b)) for b in sorted(an.builtins)
                ],
                item_refs=sorted(an.item_refs),
                globals_used=sorted(an.globals_used),
            )
        )

    for t in mod.triggers:
        verdict, hint = rules.classify_trigger(t.name)
        add("trigger", t.name, "", t.text, verdict, hint)
    for b in mod.blocks:
        for t in b.triggers:
            verdict, hint = rules.classify_trigger(t.name)
            add("trigger", t.name, b.name, t.text, verdict, hint)
        for it in b.items:
            for t in it.triggers:
                verdict, hint = rules.classify_trigger(t.name)
                add("trigger", t.name, f"{b.name}.{it.name}", t.text, verdict, hint)
    for p in mod.program_units:
        add("program_unit", p.name, "", p.text, "", f"{p.kind} -- normally moves to a database package")

    return tasks


def build_prompt(task: ConversionTask, analysis=None) -> list[Message]:
    """Everything the model needs, and nothing that would bias it.

    ``analysis`` is the deterministic result for this unit (a
    :class:`formslang.analysis.UnitAnalysis`). When present it replaces the
    flat built-in list with the structured catalog view -- migration class,
    APEX strategy, resolved targets -- and states the risk and behaviour the
    rules already established. Passing facts costs a few hundred tokens and
    removes the whole class of answers where the model re-derives, badly,
    something the engine already knows.
    """
    lines = [
        f"Module: {task.module}",
        f"Unit: {task.kind} {task.title}",
    ]
    if task.verdict:
        lines.append(f"Catalog verdict: {task.verdict} -- {task.apex_hint}")
    elif task.apex_hint:
        lines.append(f"Catalog note: {task.apex_hint}")

    if analysis is not None:
        lines.append(
            f"\nDeterministic analysis (rule engine {analysis.engine_version}) -- "
            "these are measured facts about the source, not opinions:"
        )
        lines.append(
            f"  Risk: {analysis.risk.level} ({analysis.risk.score:.0f}/100)"
        )
        for factor in analysis.risk.factors[:6]:
            lines.append(f"    - {factor.title}: {factor.detail}")
        lines.append(f"  Behaviour after migration: {analysis.behavior.value}")
        for reason in (analysis.behavior.reasons + analysis.behavior.uncertainties)[:6]:
            lines.append(f"    - {reason}")
        # A body with no built-ins still has a risk and a behaviour worth
        # stating; only the construct list depends on there being findings.
        if analysis.findings:
            lines.append("\nForms constructs found, with the catalog's migration strategy:")
            for finding in analysis.findings:
                times = f" x{finding.count}" if finding.count > 1 else ""
                targets = f" -> {', '.join(finding.targets)}" if finding.targets else ""
                lines.append(
                    f"  {finding.name}{times}  [{finding.verdict}/{finding.migration_class}]"
                    f" {finding.apex}{targets}"
                )
    elif task.builtins:
        lines.append("\nForms built-ins used, with the catalog's classification:")
        for name, verdict, apex in task.builtins:
            lines.append(f"  {name}  [{verdict}] {apex}")

    if task.item_refs:
        lines.append("\nScreen items referenced: " + ", ".join(task.item_refs[:40]))
    if task.globals_used:
        lines.append("Global variables: " + ", ".join(task.globals_used))

    lines.append("\nSource:\n```plsql\n" + task.source.strip() + "\n```")
    lines.append("\nReturn the JSON object described in your instructions.")
    return [Message("system", SYSTEM_PROMPT), Message("user", "\n".join(lines))]


_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def parse_proposal(text: str) -> Proposal:
    """Read the model's answer defensively.

    A model that returns prose, a fenced block, or malformed JSON produces a
    Proposal carrying the error and zero confidence -- never a silently empty
    conversion that a tired reviewer might approve.
    """
    raw = (text or "").strip()
    if not raw:
        return Proposal(error="model returned empty text")

    candidate = raw
    if candidate.startswith("```"):
        candidate = re.sub(r"^```[a-zA-Z]*\s*", "", candidate)
        candidate = re.sub(r"\s*```$", "", candidate)
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError:
        m = _JSON_BLOCK.search(candidate)
        if not m:
            return Proposal(error="no JSON object in the answer", raw=raw[:2000])
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError as e:
            return Proposal(error=f"malformed JSON: {e}", raw=raw[:2000])

    if not isinstance(data, dict):
        return Proposal(error="answer was JSON but not an object", raw=raw[:2000])

    def as_list(value) -> list[str]:
        if isinstance(value, list):
            return [str(x) for x in value if str(x).strip()]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return []

    try:
        confidence = float(data.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0

    # An answer outside the three values is dropped rather than normalised:
    # merge_ai would ignore it anyway, and storing it would suggest the model
    # said something usable about behaviour when it did not.
    behavior = str(data.get("behavior", "")).strip().upper()
    if behavior not in ("PRESERVED", "CHANGED", "UNCERTAIN"):
        behavior = ""

    return Proposal(
        apex_target=str(data.get("apex_target", "")).strip(),
        code=str(data.get("code", "")),
        notes=as_list(data.get("notes")),
        open_questions=as_list(data.get("open_questions")),
        confidence=max(0.0, min(1.0, confidence)),
        behavior=behavior,
        behavior_reason=str(data.get("behavior_reason", "")).strip(),
        raw=raw[:4000],
    )


def propose(
    task: ConversionTask,
    provider: Provider,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    analysis=None,
) -> Proposal:
    """Ask the provider for one proposal. Failure is data, not an exception."""
    try:
        answer = provider.complete(build_prompt(task, analysis), max_tokens=max_tokens)
    except ProviderError as e:
        return Proposal(error=str(e), provider=provider.type_id, model=provider.model)
    p = parse_proposal(answer)
    p.provider = provider.type_id
    p.model = provider.model
    return p


def propose_many(
    tasks: list[ConversionTask],
    provider: Provider,
    on_progress=None,
    reuse_shared: bool = True,
) -> dict[str, Proposal]:
    """Convert a whole queue, converting each distinct body only once.

    ``reuse_shared`` is the pipeline half of the deduplication the assessment
    reports: identical bodies share one model call. Reused proposals are
    marked in ``notes`` so a reviewer always knows this text was written for
    a sibling copy, not for the unit in front of them.
    """
    out: dict[str, Proposal] = {}
    by_print: dict[str, Proposal] = {}
    for i, task in enumerate(tasks, 1):
        cached = by_print.get(task.fingerprint) if (reuse_shared and task.fingerprint) else None
        if cached is not None and cached.ok:
            p = Proposal(**{**cached.__dict__, "notes": list(cached.notes)})
            p.notes.append("Reused: identical body already converted in this run.")
        else:
            # Analysing here costs nothing (no provider call) and gives the
            # model the same measured facts the workbench shows the reviewer.
            p = propose(task, provider, analysis=analyze_task(task))
            if reuse_shared and task.fingerprint and p.ok:
                by_print[task.fingerprint] = p
        out[task.id] = p
        if on_progress:
            on_progress(i, len(tasks), task, p)
    return out
