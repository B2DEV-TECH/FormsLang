# ADR-003: Business logic belongs in the PL/SQL API layer, never in a UI trigger

## Status
Accepted

## Context
Across the four Forms modules, the same defect pattern recurs at multiple
risk levels: a validation, calculation, or state change is implemented
directly in a Forms trigger (`WHEN-VALIDATE-ITEM`, `WHEN-BUTTON-PRESSED`)
against raw tables, even where an equivalent `LOM_*_API` package procedure
already exists and is called correctly from other trigger sites in the
same codebase. See `docs/modernization-challenges.md` Theme 1 and Theme 3
for the full case inventory (LOM-MOD-010/011/025/026/027/039/041/042).

## Decision
Every one of these cases is classified `MOVE_TO_PLSQL_API` (where an API
procedure already exists to call instead) or, where no such procedure
exists yet (LOM-MOD-037), flagged as requiring new PL/SQL to be designed
before the APEX page can be built at all. In no case is the correct
modernization outcome "translate the trigger's SQL into an APEX page
process as-is." The UI layer (Forms today, APEX tomorrow) may only ever
call into the PL/SQL API layer; it may never independently implement a
rule the API layer is also responsible for.

## Consequences
- This is the single biggest source of net-new work in a rigorous
  migration compared to a mechanical one: LOM-MOD-037 alone requires
  designing and testing new PL/SQL (`add_line`/`update_line`) that never
  existed in the legacy system, not just moving code around.
- It also removes risk: once `LOM_ORDER_API.calc_line_total` is the only
  place a line total is computed, a future tax-rule or discount-rule
  change is a one-package change instead of a "find every duplicate"
  audit.
- Reviewers assessing a Forms trigger for migration should treat "does an
  API procedure already do this?" as the first question, before "how do I
  translate this PL/SQL," per the classification taxonomy's
  `MOVE_TO_PLSQL_API` definition in `expected/modernization-ground-truth.json`.
