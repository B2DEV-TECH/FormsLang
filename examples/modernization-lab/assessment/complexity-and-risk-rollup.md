# LOM modernization -- complexity and risk rollup

Numbers on this page are computed directly from
`expected/modernization-ground-truth.json` (41 cases) and
`metrics/compute_metrics.py`'s structural counts. Regenerate by loading
the ground-truth JSON and counting `classification`/`risk`/`category`
fields -- these are not hand-maintained totals. `tests/test_fixtures.py`
recomputes every table on this page from the registry and fails if a
number here has gone stale.

## By classification (41 cases)

| Classification              | Count | Meaning in this lab |
|------------------------------|------:|----------------------|
| `MANUAL_REVIEW`              |    10 | No mechanical rule decides the outcome; a human must choose |
| `PRESERVE`                   |     8 | Carries forward unchanged (only the call site changes) |
| `MOVE_TO_PLSQL_API`          |     6 | Logic must move out of the UI layer into (existing or new) PL/SQL |
| `REFACTOR`                   |     6 | Same intent, different implementation |
| `REPLACE_WITH_APEX_NATIVE`   |     5 | An APEX platform feature replaces hand-rolled Forms logic |
| `CONVERT`                    |     4 | Direct mechanical translation |
| `DROP`                       |     2 | Not carried forward at all |

**Reading this table**: 16 of 41 cases (`MANUAL_REVIEW` + `MOVE_TO_PLSQL_API`)
cannot be handled by a mechanical Forms-to-APEX converter no matter how
sophisticated its trigger-translation rules are -- either because the
correct target requires human judgment, or because the correct target is
PL/SQL that does not exist yet. That is 39% of the registry. The
`PRESERVE`/`CONVERT` rows (12 cases) are the positive controls: a
classifier that cannot leave LOM-MOD-016/019/021/028 alone, or that
escalates LOM-MOD-010 to `MOVE_TO_PLSQL_API`, is over-classifying.

## By risk

| Risk       | Count |
|------------|------:|
| `LOW`      |    24 |
| `MEDIUM`   |     9 |
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

All four `CRITICAL` cases sit on one surface: the two `APPROVALS.fmb`
buttons (LOM-MOD-041/042) and the two package-level rules those buttons
bypass -- the status matrix (LOM-MOD-002) and the `USER`-defaulted
attribution (LOM-MOD-031). This is the single highest-risk surface in the
whole lab, not an evenly spread risk profile.

## By category (taxonomy A-F)

| Category | Count | Meaning |
|----------|------:|---------|
| F        |    17 | Architectural/cross-cutting -- no single trigger fixes it |
| A        |     7 | Mechanical/structural mapping |
| C        |     6 | Presentation/UI logic replaced by an APEX native feature |
| E        |     6 | Belongs in the PL/SQL API layer |
| D        |     4 | Navigation/multi-form flow redesign requiring human judgment |
| B        |     1 | Validation logic conversion (same logic, different call site) |

**Observation**: category B has exactly one case, LOM-MOD-010 (a `CHECK`
constraint mirrored in a `WHEN-VALIDATE-ITEM`; the trigger becomes an APEX
item validation and nothing changes ownership). Every other case that
looked like "same validation, different call site" on inspection turned
out to either already call the API (category A, `PRESERVE`) or to need
the logic's *ownership* moved (category E, `MOVE_TO_PLSQL_API`). This is
not a gap to fill artificially; it reflects that in this codebase,
wherever validation logic is duplicated, it is almost always duplicated
from a package rather than from a constraint.

## By module (first file cited in each case's `source` field)

Attribution rule, the one `metrics/compute_metrics.py` implements as
`by_module`: a case belongs to the first file its `source` cites --
`forms/xml/<MODULE>.xml` -> that form, `database/packages/<pkg>.*` -> that
package, `forms/libraries/OM_SHARED.*` -> the library, anything else under
`database/` -> "database DDL/views".

| Module               | Cases | Dominant classification |
|-----------------------|------:|--------------------------|
| `ORDERS.fmb`          |    13 | `MOVE_TO_PLSQL_API` (3), `PRESERVE` (3), `REFACTOR` (3) |
| `CUSTOMERS.fmb`       |     7 | `REPLACE_WITH_APEX_NATIVE` (2), `CONVERT` (2) |
| database DDL/views    |     7 | `MANUAL_REVIEW` (5) |
| `lom_order_api`       |     4 | 1 each of `MANUAL_REVIEW`/`MOVE_TO_PLSQL_API`/`PRESERVE`/`REFACTOR` |
| `APPROVALS.fmb`       |     3 | `MANUAL_REVIEW` (2) |
| `OM_SHARED.pll`       |     3 | 1 each of `REPLACE_WITH_APEX_NATIVE`/`DROP`/`MOVE_TO_PLSQL_API` |
| `INVENTORY.fmb`       |     2 | 1 each of `PRESERVE`/`REPLACE_WITH_APEX_NATIVE` |
| `lom_approval_api`    |     2 | 1 each of `MANUAL_REVIEW`/`PRESERVE` |

`ORDERS.fmb` is both the largest form (26 items, per
`metrics/compute_metrics.py`) and the largest source of migration work by
case count -- consistent with it owning three of the six
`MOVE_TO_PLSQL_API` cases in the entire registry (LOM-MOD-025/026/027)
and being the form the order-line API gap (LOM-MOD-037, attributed to
`lom_order_api` above because its `source` cites the package spec) exists
to serve.

## What this rollup does not tell you

This is a *count* of cases, not a *sizing estimate* in hours or story
points -- the lab deliberately does not assign effort estimates, since
that number depends entirely on a target team's own PL/SQL/APEX velocity,
which is outside this lab's scope. Use this table to prioritize *review
order* (start with the 4 CRITICAL cases, then the `APPROVALS.fmb` cluster
as a whole), not as a project-planning substitute.
