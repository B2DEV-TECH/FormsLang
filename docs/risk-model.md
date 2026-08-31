# How FormsLang measures risk, behaviour and readiness

Every number on this page is produced by rules in the repository, from the
source text of one Oracle Forms unit. No model is asked what the risk is, no
model votes on the behaviour classification, and no model contributes a
single point to the readiness score. A model may be asked to *explain* a
finding the rules already made; it may never create one.

If you disagree with a number here, you can open the file that produced it,
read the weight, and change it. That is the whole design.

---

## 1. Two questions that must not share an answer

FormsLang answers two different questions about the same unit, and it keeps
them in two different columns because they routinely disagree.

| | Question | Answers | Where |
|---|---|---|---|
| **Conversion mode** (verdict) | *What does this conversion cost?* | AUTO / ASSISTED / MANUAL / DROP / UNKNOWN | `rules.py`, documented in [methodology.md](methodology.md) |
| **Migration risk** | *How dangerous is it to get this wrong?* | LOW / MEDIUM / HIGH / CRITICAL | `risk.py` |

`COMMIT_FORM` is the canonical example. It is `AUTO`: it converts
mechanically and costs almost nothing. It also silently moves the
transaction boundary of an entire page. Cheap and dangerous. One number
cannot say both things, so there are two.

A third indicator, **AI confidence**, answers yet another question — *how
sure is the model about the code it just proposed?* — and comes from the
provider, not from the rules. Confidence is about the proposal. Risk is
about the Forms behaviour underneath it. A high-confidence proposal for a
CRITICAL unit is normal, and is exactly the case a reviewer must not skim.

The screen orders them the same way, always:
**Status → Conversion mode → Risk → Behaviour → Confidence.**

---

## 2. The compatibility catalog

Everything starts from a structured catalog (`rules.CATALOG`) — not from
knowledge embedded in a prompt. Each entry names a Forms built-in, what APEX
offers instead, the review area it belongs to, an effort weight and a risk
weight. Prompts read the catalog; the catalog never reads a prompt.

Every entry carries a **migration class**:

| Class | Meaning |
|---|---|
| `DIRECT_EQUIVALENT` | APEX or PL/SQL does the same thing, near enough to translate literally. |
| `SERVER_SIDE_REPLACEMENT` | The behaviour survives, as a page process, computation or validation. |
| `CLIENT_SIDE_REPLACEMENT` | The behaviour survives, as a Dynamic Action or JavaScript. |
| `ARCHITECTURAL_REDESIGN` | It cannot be translated unit-by-unit; the page has to be designed differently. |
| `MANUAL_REVIEW` | A person has to decide, because the right answer depends on context the code does not carry. |
| `UNSUPPORTED` | APEX has no equivalent, at all. Something has to be dropped or rebuilt outside APEX. |
| `NOT_REQUIRED` | The construct exists only to serve the Forms runtime and has no reason to exist in APEX. |

`NOT_REQUIRED` is deliberately not folded into `UNSUPPORTED`. `SYNCHRONIZE`
disappearing is not a gap in APEX, and counting it as one would inflate
every "missing feature" number in the product.

An unknown built-in is reported as unknown. It is never guessed at, never
silently dropped, and it costs risk points precisely because nobody has
classified it yet.

---

## 3. Migration risk

### 3.1 Raw points

Each factor adds raw points, and each factor carries the evidence that
produced it — the built-in name, the line, the trigger point. Nothing is
added without something to show for it.

| Factor | Points | Notes |
|---|---|---|
| Trigger point | `8.0 × trigger risk weight` | the firing point itself carries risk |
| Built-ins, grouped by family | `Σ (catalog risk weight × occurrence × 4.0)` | one factor per family, evidence lists every built-in in it |
| Forms system variables | `Σ (weight × occurrence × 3.0)` | `:SYSTEM.…` state that has no APEX counterpart |
| Global variables | 1.5 each, capped at 4.5 | state shared with every other form |
| Dynamic SQL (`EXECUTE IMMEDIATE`, `FORMS_DDL`) | 6.0 | effect not knowable statically; floors the level at HIGH |
| DML in the body | 3.0 | transaction behaviour is at stake |
| DML with no exception handler | +2.0 | a failure surfaces somewhere else in APEX |
| Calls another form | `4.0 × forms named` | not finished until the called form is migrated too |
| Calls a form chosen at runtime | 4.0 | the dependency cannot even be listed; floors at HIGH |
| Indirection with a computed target (`NAME_IN`, `COPY`) | 5.0 | nothing can prove what it touches; floors at HIGH |
| Outside the catalog | 4.0 each, capped at 8.0 | unclassified is not free |
| Unresolved local calls | 1.0 each, capped at 4.0 | may be a program unit, may be a missing built-in |
| Size | 1 point per 60 lines, capped at 4.0 | volume is a weak signal, so it is capped low |

Repeated calls count more, but not linearly: a built-in seen `n` times is
multiplied by `1 + log₂(n)`. Ten calls are worse than one, and not ten
times worse.

### 3.2 From points to a score

```
score = 100 × (1 − 0.5 ^ (raw / 12))
```

Twelve raw points is 50, twenty-four is 75, and the result is capped at
99.9 — a heuristic that prints a perfect score reads as certainty, and this
number is evidence, not certainty. The saturation is the point: without it,
a 600-line trigger would score 400 and the number would stop meaning
anything. `risk.explain()` returns this formula and the thresholds below,
and the UI prints them next to the score so a reviewer can check the
arithmetic rather than trust it.

### 3.3 From a score to a level

| Score | Level |
|---|---|
| < 20 | LOW |
| < 45 | MEDIUM |
| < 70 | HIGH |
| ≥ 70 | CRITICAL |

One override, applied after the score: some factors floor the level at
HIGH whatever else the unit does — a catalog entry weighing 0.80 or more, a
trigger point weighing 0.80 or more, dynamic SQL, a form chosen at runtime,
or indirection with a computed target. A unit that calls `HOST` is not low
risk because it is short. The floor never reaches CRITICAL: CRITICAL means
several dangerous things at once, and that has to be earned by the score.

---

## 4. Behaviour classification

Three answers, and the third one is the load-bearing one.

| Value | Meaning |
|---|---|
| `PRESERVED` | The rules found nothing that changes observable behaviour. |
| `CHANGED` | Something observably differs, and we can name it: the transaction boundary moved, the locking model changed, a trigger point stops firing. |
| `UNCERTAIN` | The rules cannot tell. Not a hedge — a finding. |

Two invariants hold everywhere:

1. **Absence of evidence is never `PRESERVED`.** A body too small or too
   opaque to analyse comes back `UNCERTAIN`.
2. **The model may make this worse, never better.** `behavior.merge_ai`
   accepts an AI opinion only when it moves *away* from `PRESERVED`.

Three families drive the classification:

- **Cycle triggers** that stop firing because the cycle does not exist in
  APEX (`PRE-BLOCK`, `WHEN-NEW-RECORD-INSTANCE`, `ON-LOCK`, `WHEN-TIMER-EXPIRED`, …)
  → `CHANGED`, with the reason stated.
- **Relocated triggers** that survive but whose moment of execution depends
  on a decision the reviewer has not made yet (`PRE-INSERT` → page process
  or table trigger?) → `UNCERTAIN`, by construction rather than by ignorance.
- **Built-in families**: `transaction`, `timer`, `client_platform`,
  `form_state`, `reporting` change what the user observes; `indirection`,
  `dynamic_sql` and `unknown` cannot be established statically.

---

## 5. Test specifications

Test cases are written from the **original Forms body**, before and
independently of any conversion — a test derived from generated code can
only prove the generator agrees with itself.

Each case carries an origin, and the origin is the honest part:

| Origin | Meaning |
|---|---|
| `FORMS_BEHAVIOR` | Behaviour inherited from the form. It must still hold afterwards. |
| `MODERNIZATION` | Behaviour introduced by the move to APEX. It is new, and it is expected. |
| `NEEDS_CONFIRMATION` | Something the source does not settle. A person has to answer it. |

FormsLang does not run these cases. It writes specifications a person or a
test framework can execute, and the screen says so. A reviewer marks each
case accepted, rejected or needs-modification; the decision is keyed by the
content of the case, so it survives regeneration whenever the wording is
unchanged.

---

## 6. Readiness

The one figure on the dashboard that could be mistaken for a verdict. It is
a weighted count of work a person can go and verify, and it is printed next
to its own arithmetic, weight by weight, on the same screen.

| Component | Weight | Measured as |
|---|---|---|
| Units a person has decided on | 30 | units not pending ÷ every unit |
| Units approved | 25 | approved units ÷ every unit |
| Risk mass that is low | 20 | `1 − (Σ risk weight ÷ unit count)`, weighting LOW 0, MEDIUM 0.34, HIGH 0.67, CRITICAL 1.0 |
| Behaviour that is settled | 15 | PRESERVED 1, CHANGED 0.5, UNCERTAIN 0, ÷ every unit |
| Test cases answered | 10 | answered cases ÷ every generated case |

```
readiness = Σ (weight × component), each component a ratio in 0..1
            measured over every unit in the session — not only the
            measured ones.
```

Three deliberate choices:

- **A unit nobody analysed contributes zero to every component.** It carries
  the full risk weight of 1.0 and zero behaviour credit. Excluding it would
  make the least finished session score the highest, which is the exact
  failure mode this number exists to avoid.
- **CHANGED counts half.** A difference that has been described and accepted
  is not the same problem as one nobody has established yet.
- **Blockers are not in the score.** Unsupported built-ins, missing
  analyses, pending reviews and unanswered cases are listed separately, as
  work to do. Folding them into a percentage would hide them behind
  arithmetic.

The score is versioned (`readiness/1`) and travels with the engine version
of the rules that produced the analyses behind it. It is a count of work
done, not a judgement that the migration is safe.

---

## 7. What none of this claims

- It does not claim the migration is correct. It claims what the rules found.
- It does not claim a percentage of anything physical. The risk score is a
  projection onto 0–100, not a probability.
- It does not claim completeness. An unknown built-in stays unknown and says
  so; a form that cannot be parsed reports a parse failure rather than an
  empty result.
- It does not replace the reviewer. Every number here exists to tell a person
  where to look first.
