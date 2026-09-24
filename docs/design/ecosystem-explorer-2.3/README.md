# FormsLang 2.3 — Ecosystem Explorer, phase 1

Status: **phase 1 delivered for review.** This folder holds the contract, the
measurements and the journey design. Phase 1 writes no UI, and it changes
nothing in `formslang/`. The Blueprint enrichment (phase 2) and the UI do not
start until this phase has been reviewed.

## Contents

| Document | What it fixes |
|---|---|
| [`contract-ecosystem-1.md`](contract-ecosystem-1.md) | The `ecosystem/1` contract: identities, the relation record, the seven families mapped from the 2.2 edge types, certainty, the visual-attribute origin rule, frontiers, bounds and revision compatibility. |
| [`inventory-2.2.json`](inventory-2.2.json) | What the 2.2 engine records, measured on four corpora (showcase, modernization lab, Case C and the visual-hierarchy fixture) and Cases A–C. Regenerate or check it with `py examples/verify/ecosystem_inventory.py --output/--check`. |
| [`gaps-and-capture.md`](gaps-and-capture.md) | Three pre-existing engine defects, the contract gaps, and what phase 2 must capture. |
| [`performance-2.2-baseline.md`](performance-2.2-baseline.md) | The 500-Form baseline and ecosystem runs, warm-read p50/p95, memory and response sizes. |
| [`journey-three-steps.md`](journey-three-steps.md) | The three-step journey as text wireframes built from measured facts. |
| [`evaluation/`](evaluation/protocol.md) | Protocol, task script, session sheet and criteria sheet for the five-professional evaluation. |

Tests: `tests/test_ecosystem_phase1.py`. Fixtures: `tests/fixtures/ecosystem/`.
Scale: `examples/verify/project_corporate_scale.py --profile ecosystem` and
`examples/verify/project_read_samples.py`.

## Phase 1 gate (spec §12)

| Item | Status |
|---|---|
| `ecosystem/1` contract written | Done, for review |
| Case A reproducible up to the limit of the 2.2 facts | Done: `test_case_a_*`, with gaps G-CALL-LOCAL, G-CALL-EXPR and G-RISK-TEXT pinned |
| Case B reproducible up to the limit of the 2.2 facts | Done: `test_case_b_*`, with defect G-DML pinned |
| Case C (homonyms across schemas) measured | Done: two engine defects pinned (G-SCHEMA-BODY, G-SCHEMA-COLLIDE) |
| Gaps documented with a phase-2 capture inventory | Done |
| Visible/CanvasType origin recorded as not verifiable | Done: contract §6, `CV_VISIBLE_DECLARED` vs `CV_DEFAULTS` |
| Scale generator reaches ≥5k findings and ≥5k relations | Done: 18,638 findings and 39,571 relations at 500 Forms |
| Performance parameters documented | Done: single machine, synthetic; warm reads above the 2 s target (see below) |
| Three-step journey designed | Done, text only |
| No UI code, no engine change | Held |
| **Five-professional evaluation** | **PENDING.** Kit prepared; no session has run. Never reported as met before the sessions. |

## What needs a decision before phase 2

1. **G-DML** (engine defect, ships in 2.2.0). An `UPDATE` right after `THEN` is
   not recorded as a write, so writes are under-reported. The recommendation is
   a separate 2.2.x decision, because the defect affects the existing hotspots
   and not only the explorer.
2. **G-SCHEMA-BODY and G-SCHEMA-COLLIDE.** Schema-qualified bodies lose their
   subprograms, and same-named packages in different schemas collapse into
   one. The recommendation is to fix both in phase 2, where schema-aware
   resolution becomes part of the contract.
3. **Read latency.** Every warm read at 500 Forms takes 1.6–2.7 s, and most of
   that time is spent copying the whole saved assessment on each call. The
   spec's neighbourhood target (p95 ≤ 2 s) is not met by the 2.2 read path. The
   explorer's endpoints need a cached, revision-bound read of the Blueprint.
   That work belongs in phase 3 and does not change `project_store` timeouts.
4. **ESTATE map.** At 500 Forms, the 2.2 ESTATE view showed no relationships.
   The explorer is focus-first, and every bounded view reports shown versus
   available.
5. **Evaluation sessions.** Five Oracle professionals who have not worked on
   the explorer, to be recruited by the project owner. The build under test
   must exist first (phase 4). Until the sessions run, the criterion stays
   pending.
