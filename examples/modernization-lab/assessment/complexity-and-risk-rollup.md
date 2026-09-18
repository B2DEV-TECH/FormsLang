# LOM modernization -- complexity and risk rollup

Numbers on this page are computed directly from
`expected/modernization-ground-truth.json` (41 cases) and
`metrics/compute_metrics.py`'s structural counts. Regenerate by loading
the ground-truth JSON and counting `classification`/`risk`/`category`
fields -- these are not hand-maintained totals, so if a case is added or
reclassified, this table goes stale until recomputed.

## By classification (41 cases)

| Classification              | Count | Meaning in this lab |
|------------------------------|------:|----------------------|
| `MANUAL_REVIEW`              |    10 | No mechanical rule decides the outcome; a human must choose |
| `MOVE_TO_PLSQL_API`          |     8 | Logic must move out of the UI layer into (existing or new) PL/SQL |
| `PRESERVE`                   |     7 | Carries forward unchanged |
| `REFACTOR`                   |     6 | Same intent, different implementation |
| `REPLACE_WITH_APEX_NATIVE`   |     5 | An APEX platform feature replaces hand-rolled Forms logic |
| `CONVERT`                    |     3 | Direct mechanical translation |
| `DROP`                       |     2 | Not carried forward at all |

**Reading this table**: 18 of 41 cases (`MANUAL_REVIEW` + `MOVE_TO_PLSQL_API`)
cannot be handled by a mechanical Forms-to-APEX converter no matter how
sophisticated its trigger-translation rules are -- either because the
correct target requires human judgment, or because the correct target is
PL/SQL that does not exist yet. That is 44% of the registry, concentrated
disproportionately in `ORDERS.fmb` (see below).

## By risk

| Risk       | Count |
|------------|------:|
| `LOW`      |    23 |
| `MEDIUM`   |    10 |
| `HIGH`     |     4 |
| `CRITICAL` |     4 |

### The 8 HIGH/CRITICAL cases, by name

- **CRITICAL** LOM-MOD-002 -- order status transitions enforced only by a
  hardcoded PL/SQL matrix, not by any schema constraint (see
  [ADR-002](../docs/adr/002-status-transitions-owned-by-plsql-matrix.md)).
- **CRITICAL** LOM-MOD-031 -- approval attribution defaults to the
  database session `USER`, silently wrong under APEX (see
  [ADR-004](../docs/adr/004-approval-attribution-must-pass-app-user-explicitly.md)).
- **CRITICAL** LOM-MOD-041 -- `APPROVALS.fmb`'s Approve button bypasses
  `LOM_APPROVAL_API` entirely.
- **CRITICAL** LOM-MOD-042 -- `APPROVALS.fmb`'s Reject button bypasses
  the API *and* its mandatory-comment rule.
- **HIGH** LOM-MOD-011 -- Forms duplicates `LOM_CUSTOMER_API.has_open_orders`.
- **HIGH** LOM-MOD-026 -- quantity threshold check re-implemented instead
  of called.
- **HIGH** LOM-MOD-027 -- line total formula duplicated on two items.
- **HIGH** LOM-MOD-037 -- no PL/SQL API exists for order-line operations
  at all.

Three of the four `CRITICAL` cases live in a single form
(`APPROVALS.fmb`'s two cases plus the status-matrix case they both
ultimately call into) -- this is the single highest-risk surface in the
whole lab, not an evenly spread risk profile.

## By category (taxonomy A-F)

| Category | Count | Meaning |
|----------|------:|---------|
| F        |    17 | Architectural/cross-cutting -- no single trigger fixes it |
| E        |     8 | Belongs in the PL/SQL API layer |
| C        |     6 | Presentation/UI logic replaced by an APEX native feature |
| A        |     6 | Mechanical/structural mapping |
| D        |     4 | Navigation/multi-form flow redesign requiring human judgment |
| B        |     0 | Validation logic conversion (same logic, different call site) |

**Observation**: category B (defined in the taxonomy for completeness) has
zero cases in the current registry -- every case that looked like "same
validation, different call site" on inspection turned out to also involve
moving the logic's *ownership* (category E, `MOVE_TO_PLSQL_API`) rather
than just relocating an unchanged check. This isn't a gap to fill
artificially; it reflects that in this codebase, wherever validation logic
needs to move, it also needs to be centralized.

## By module (rough attribution from each case's `source` field)

| Module               | Cases | Dominant classification |
|-----------------------|------:|--------------------------|
| `ORDERS.fmb`          |    14 | `MOVE_TO_PLSQL_API` (5), `REFACTOR` (3) |
| `CUSTOMERS.fmb`       |     8 | `MOVE_TO_PLSQL_API` (2), `REPLACE_WITH_APEX_NATIVE` (2) |
| `APPROVALS.fmb`       |     5 | `MANUAL_REVIEW` (3) |
| `INVENTORY.fmb`       |     4 | `MANUAL_REVIEW` (2) |
| `lom_order_api`       |     4 | mixed (1 each) |
| `OM_SHARED.pll`       |     3 | 1 each of `REPLACE_WITH_APEX_NATIVE`/`DROP`/`MOVE_TO_PLSQL_API` |
| `lom_approval_api`    |     1 | `MANUAL_REVIEW` |
| other/cross-cutting   |     2 | 1 each `MANUAL_REVIEW`/`PRESERVE` |

`ORDERS.fmb` is both the largest form (26 items, per
`metrics/compute_metrics.py`) and the largest source of migration work by
case count -- consistent with it owning the order-line API gap
(LOM-MOD-037) and five of the eight `MOVE_TO_PLSQL_API` cases in the
entire registry.

## What this rollup does not tell you

This is a *count* of cases, not a *sizing estimate* in hours or story
points -- the lab deliberately does not assign effort estimates, since
that number depends entirely on a target team's own PL/SQL/APEX velocity,
which is outside this lab's scope. Use this table to prioritize *review
order* (start with the 4 CRITICAL cases, then the `APPROVALS.fmb` cluster
as a whole), not as a project-planning substitute.
