# FormsLang 2.3 — Ecosystem Explorer, phase 1

Status: **phase 1 reviewed** (PR #17). This folder holds the contract, the
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
| `ecosystem/1` contract written | Done |
| Case A reproducible up to the limit of the 2.2 facts | Done: `test_case_a_*`, with gaps G-CALL-LOCAL, G-CALL-EXPR and G-RISK-TEXT pinned |
| Case B reproducible up to the limit of the 2.2 facts | Done: `test_case_b_*`, with defect G-DML pinned |
| Case C (homonyms across schemas) measured | Done: two engine defects pinned (G-SCHEMA-BODY, G-SCHEMA-COLLIDE); legacy-resolution rule covered |
| Gaps documented with a phase-2 capture inventory | Done |
| Visible/CanvasType origin recorded as not verifiable | Done: contract §6, `CV_VISIBLE_DECLARED` vs `CV_DEFAULTS` |
| Scale generator reaches ≥5k findings and ≥5k relations | Done: 18,638 findings and 39,571 relations at 500 Forms |
| Performance parameters documented | Done: single machine, synthetic; warm reads above the 2 s target (decision 4) |
| Three-step journey designed | Done, text only |
| No UI code, no engine change | Held |
| **Five-professional evaluation** | **PENDING.** Kit prepared; no session has run. Never reported as met before the sessions. |

## Decisions recorded at review (PR #17, 2026-09-24)

1. **Legacy resolution.** In 2.1/2.2 snapshots, every database resolution is
   presented as `LEGACY_RESOLVED`, which is not verifiable against schema
   collisions and is never a confirmed path. This lasts until a re-analysis
   with the corrected engine
   ([contract §5.1](contract-ecosystem-1.md#51-legacy-database-resolution-2122-snapshots)).
   Case C covers it.
2. **G-DML** (engine defect, ships in 2.2.0). It is fixed in a separate 2.2.x
   pull request, with regression tests for `UPDATE` after `THEN` and for
   `MERGE`.
3. **G-SCHEMA-BODY and G-SCHEMA-COLLIDE** are fixed in phase 2. The fix keeps
   the schema and records ambiguities. Old assessments are not rewritten.
4. **Read latency.** Phase 3 adds a per-revision read of the Blueprint, then
   re-measures p50/p95 at 500 Forms. The `project_store` timeouts are not
   raised. Today every warm read takes 1.6–2.7 s, mostly in copying the saved
   assessment.
5. **Map.** Entry is always a Form in focus, and every view shows relations
   displayed versus available.
6. **Journey.** Choose a screen, click a relation, understand its evidence. No
   graph configuration is required. UI work has not started.
7. **Evaluation sessions.** The project owner will arrange them with five
   Oracle professionals who have not worked on the explorer, on a phase-4
   build. Until the sessions run, the criterion stays pending.
