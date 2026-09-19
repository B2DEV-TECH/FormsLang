# FormsLang Modernization Benchmark: v1 vs. v2 vs. v3 Baseline Comparison

**Date**: 2026-09-19
**Protocol Version**: 1.0
**Source commits** -- each baseline's `manifest.json` records the commit the
working tree was *based on* when the run executed, not the commit that later
contains the frozen artifacts. The two differ by one, because a baseline is
frozen and only then committed:

| Baseline | Source commit (HEAD at run time) | Commit that contains the baseline |
|:---|:---|:---|
| v1 | `22f24805d0f8b277368723306565b94c5e2d25b0` | `9005c4389834ffcdf132734d04f6843a6b657cdf` |
| v2 | `9005c4389834ffcdf132734d04f6843a6b657cdf` | `af2d4ff977ba50ed4ff26ec3e4046d2a6129e8ff` |
| v3 | `af2d4ff977ba50ed4ff26ec3e4046d2a6129e8ff` | the commit that adds this file (it cannot name its own hash) |

**Ground Truth SHA256**: `4b43e879e6124c7b2821ffedfc64c3ff19a825f61b39d7b911d9da209ce69615` (byte-identical across all three runs)

---

## 1. Read This First

Two findings outrank every number in this document.

**The v2 figure did not measure what it claimed to measure.** The v2 engine contained
rules keyed to this laboratory: case identifiers, fixture object names, and the file names
of the four Forms modules appeared in the reasoning code itself. A benchmark cannot be
scored by an engine that can recognise the benchmark, so **68.4% was a measurement of this
corpus, not of the engine's ability to reason about Oracle Forms portfolios in general**.
Every such identifier was removed before the v3 run; the audit that proves it is in §6.
The v3 number is therefore the first figure in this benchmark's history that is honest
about what it measures — and it went **up**, not down.

**v3 costs four cases that v2 got right, all of them in the same direction.** Where a
human architect judged "leave this alone", v3 now proposes work: three `PRESERVE` cases
became `REFACTOR`, `MOVE_TO_PLSQL_API` and `MANUAL_REVIEW`, and the single `DROP` case
became `MANUAL_REVIEW`. No safety metric moved, but an engine that over-flags costs its
operator trust just as an engine that under-flags costs them an incident. §5 names all
four and says what is needed to fix each.

---

## 2. Quantitative Metric Comparison

| Benchmark Metric | v1 (Forms only) | v2 (Forms + Database) | v3 (Structural reasoning) | Δ v2→v3 |
|:---|---:|---:|---:|---:|
| **Total Cases** | 41 | 41 | 41 | 0 |
| **Fully Observable** | 16 (39.0%) | 38 (92.7%) | 38 (92.7%) | 0 |
| **Partially Observable** | 12 | 0 | 0 | 0 |
| **Not Observable** | 13 | 3 | 3 | 0 |
| **Observable Cases Evaluated** | 28 | 38 | 38 | 0 |
| **Exact Classification Accuracy (Observable)** | 21.4% (6/28) | 68.4% (26/38) | **73.7% (28/38)** | **+5.3 pp** |
| **Exact Classification Accuracy (Fully Obs)** | 25.0% (4/16) | 68.4% (26/38) | **73.7% (28/38)** | **+5.3 pp** |
| **Macro F1 Score** | 0.1333 | 0.6257 | **0.6418** | **+0.0161** |
| **Exact Risk Accuracy** | 21.4% (6/28) | 68.4% (26/38) | **79.0% (30/38)** | **+10.6 pp** |
| **Critical Risk Recall** | 0.0% (0/2) | 100.0% (4/4) | **100.0% (4/4)** | 0 |
| **High Risk Recall** | 0.0% (0/4) | 75.0% (3/4) | 75.0% (3/4) | 0 |
| **High + Critical Risk Recall** | 33.3% (2/6) | 87.5% (7/8) | 87.5% (7/8) | 0 |
| **Execution Verdict Exact Matches** | 0/5 | 5/11 | **7/11** | **+2** |
| **Manual Review Recall** | 60.0% (3/5) | 80.0% (8/10) | 80.0% (8/10) | 0 |
| **False Automation Rate** | 40.0% (2/5) | 20.0% (2/10) | 20.0% (2/10) | 0 |
| **Critical Safety Misses** | 0 | 0 | **0** | 0 |

The safety row is the one that had to hold, and it held exactly: the same two cases are
automated when they should not be (`LOM-MOD-004`, `LOM-MOD-018`), no new ones joined them,
and no critical-risk case was missed.

---

## 3. Per-Class F1

| Modernization Class | Truth n | v1 F1 | v2 F1 | v3 F1 | Δ v2→v3 |
|:---|---:|---:|---:|---:|---:|
| `PRESERVE` | 8 | 0.0000 | 0.9412 | 0.7143 | **-0.2269** |
| `CONVERT` | 4 | 0.4000 | 0.5000 | **0.8000** | **+0.3000** |
| `REFACTOR` | 6 | 0.0000 | 0.2500 | **0.6667** | **+0.4167** |
| `MOVE_TO_PLSQL_API` | 5 | 0.0000 | 0.8889 | 0.8000 | **-0.0889** |
| `REPLACE_WITH_APEX_NATIVE` | 4 | 0.0000 | 0.0000 | **0.7500** | **+0.7500** |
| `MANUAL_REVIEW` | 10 | 0.4000 | 0.8000 | 0.7619 | -0.0381 |
| `DROP` | 1 | 0.0000 | 1.0000 | 0.0000 | **-1.0000** |

`REPLACE_WITH_APEX_NATIVE` is the headline gain: v1 and v2 could not name this class at
all, predicting it zero times in 38 cases. v3 predicts it four times and is right on three,
because it now recognises the *shape* of behaviour the target platform supplies natively —
a format check, a confirmation prompt, a runtime property switch, a display-only derivation
— instead of looking for the vocabulary of one particular application.

`DROP` collapsing from 1.00 to 0.00 is a single case (`LOM-MOD-038`) and is discussed in §5.
With a class of size one, F1 is a coin toss and should be read as such.

---

## 4. What Changed in the Engine

All v3 reasoning lives in one new module, `formslang/modernization.py`, and every rule in it
is written against structure rather than names:

1. **Structural signatures.** Expressions are compared by *skeleton* (identifiers and
   numbers erased, operators and nesting kept), SELECT statements by *shape*
   (table, projection, filter columns), and predicates by *literal set*
   (column, operator, values). `(:bk.qty * :bk.price) - nvl(:bk.disc, 0)` in a trigger and
   `(p_qty * p_rate) - nvl(p_waiver, 0)` in a package body are recognised as one formula in
   two vocabularies, which is what lets the engine say "this logic already has an owner".
2. **Leaf naming.** Item, parameter, variable and global names are reduced to their leaf
   concept, with qualifiers and the conventional `P_`/`V_`/`G_`/`GC_`/`GV_`/`L_`/`C_`
   prefixes stripped, so `:bk_order.status`, `p_status` and `g_status` compare equal.
3. **Measured guard strength.** An API's protections are counted, not assumed:
   `FOR UPDATE`, `RAISE_APPLICATION_ERROR`, `SQL%ROWCOUNT` checks and delegation to another
   package each count one. A form-layer write is scored by *how many guards it loses*
   relative to the API that owns the table, which is why severity now differs between
   bypassing a guarded API and bypassing an unguarded one.
4. **Native-equivalent recognition.** Twelve idioms whose behaviour the target platform
   supplies declaratively are detected by shape (format validation, confirmation prompt,
   item state switching, display-only derivation, lookup-and-reject, sequence key,
   navigation toolbar, and others).
5. **Priority ordering where safety outranks convenience.** When a trigger both bypasses an
   API and contains a natively-replaceable validation, the bypass is reported first and the
   shortcut survives as a secondary statement. Nothing is discarded; the order is what
   changes.
6. **Verdict escalation on evidence.** A clean body that also commits, leaves the module, or
   writes session globals cannot be `AUTO`. Escalation only ever tightens: a `MANUAL`
   verdict is never relaxed by a later pass.

A new test suite (`tests/test_modernization.py`, 37 tests) exercises every rule above
against a **library-lending corpus that shares no table, package, column or module name with
this laboratory**. One of its tests runs the identical structure through two unrelated
vocabularies (library and clinic) and asserts both reach the same class, risk and verdict.
That test is the standing proof that these rules generalise.

---

## 5. Regressions, Named

### 5.1 Four cases v2 answered correctly and v3 does not

| Case | Truth | v2 | v3 | Why |
|:---|:---|:---|:---|:---|
| `LOM-MOD-003` | `PRESERVE` | `PRESERVE` | `REFACTOR` | Two packages call each other at body level. The engine sees a cycle; the architect saw a deliberate, contained one. Nothing in the source distinguishes them. |
| `LOM-MOD-019` | `PRESERVE` (LOW) | `PRESERVE` | `MOVE_TO_PLSQL_API` (HIGH) | The trigger calls the API *and* re-reads one of its inputs. Structural matching sees the re-read as duplicated logic; the architect read it as a gate that happens to query. |
| `LOM-MOD-032` | `PRESERVE` (LOW) | `PRESERVE` | `MANUAL_REVIEW` (CRITICAL) | A mandatory-comment rule enforced only in PL/SQL. v3 reports an unenforced business rule at CRITICAL; the architect judged the single enforcement point sufficient. **This is the largest single over-escalation in the run.** |
| `LOM-MOD-038` | `DROP` | `DROP` | `MANUAL_REVIEW` | A column with no observed reader or writer. v2 answered `DROP` from a rule that named this fixture's table. The generic rule cannot prove absence — a column may be fed by a system outside the analysed sources — so it asks rather than deletes. **This regression was accepted deliberately**: an engine that proposes dropping columns from evidence of absence is not one to trust with a production schema. |

Three of the four are `PRESERVE` losses, and all four err toward more scrutiny. That is the
safe direction, but it is still an error, and at scale it is the error that makes an operator
stop reading the report.

### 5.2 One risk level lost

`LOM-MOD-030` (duplicate PENDING approval requests) is classified correctly as
`MANUAL_REVIEW`, but v3 emits no risk level where v2 emitted `MEDIUM`. A finding that names
a concurrency hazard without grading it is incomplete. This is a defect, not a judgment call.

### 5.3 Two false automations, unchanged from v2

- `LOM-MOD-004` — a default credit limit that is a one-time suggestion, never a ceiling.
  v3 calls it `REPLACE_WITH_APEX_NATIVE`/`AUTO`; the truth is `MANUAL_REVIEW`. The
  distinction is a business intent ("suggestion" vs "limit") that the source does not carry.
- `LOM-MOD-018` — no constraint enforces a single default warehouse. v3 calls it
  `CONVERT`/`ASSISTED`; the truth is `MANUAL_REVIEW`.

Both were already wrong in v2 and neither is a *critical* safety miss, but both are cases
where a human would have been asked and was not.

### 5.4 Six cases wrong in both v2 and v3

`LOM-MOD-004`, `008`, `018`, `023`, `034`, `037`. Of these, `LOM-MOD-034` is a
`CASE_MAPPING_GAP`: the ground truth splits one Forms construct into two cases
(`034` and `021`) while the engine emits a single finding, so at most one of the pair can
ever be scored correct. Four such pairs exist in the registry, which is why the exact
classification ceiling for a single-finding-per-construct engine is approximately
**35/38 (92.1%)**, not 38/38.

---

## 6. De-Coupling Audit

Run against the whole product tree before the v3 prediction run:

```
grep -rnE "LOM-MOD-|LOM_|CUSTOMERS\.xml|ORDERS\.xml|APPROVALS\.xml|INVENTORY\.xml|modernization-lab|baselines/v" formslang/
-> no matches
```

The same audit against the v2 engine returned 30 matches. Laboratory identifiers now exist
only in the laboratory's own fixtures and in benchmark tooling, never in reasoning code.

Ground-truth and historical baseline integrity, verified by SHA256 before and after the v3
run: **16/16 files byte-identical, none added, none removed, none modified.**

---

## 7. Determinism

Unchanged across all three baselines: no AI, no LLM, no network, no randomness, no wall
clock in any decision path. `tests/test_modernization.py::test_reasoning_is_deterministic`
asserts that two runs over the same input produce identical signal objects field for field.

---

## 8. Method Statement

The v3 prediction run was executed **once** and frozen in the same command
(`run_benchmark.py --freeze --baseline-name v3`). No engine code, heuristic, threshold or
rule was modified after that run. Every number above was read from the frozen artifacts.
The mismatches catalogued in §5 are inputs to a future v4, not to this one.
