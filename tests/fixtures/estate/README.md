# Synthetic estate fixture (FormsLang 2.1 Estate Intelligence)

Hand-authored, invented sources used by the Estate Intelligence journey tests.
They are **not** part of the frozen modernization benchmarks and no reasoning
rule may reference their names.

Positive cases:

- `INTAKE` writes `WORK_ITEMS` directly while `WORK_API.CLOSE_ITEM` also writes it
  and carries guards the trigger does not (possible API bypass).
- `REVIEWS` and `TOTALS` recompute the arithmetic of `WORK_API.NET_AMOUNT`
  (duplicated business-rule candidate across two modules).
- `INTAKE` assigns `:GLOBAL.CURRENT_ITEM` and `REVIEWS` reads it
  (cross-module global state).

Negative controls:

- a trigger that calls `WORK_API.LOG_NOTE` (delegation, not bypass);
- a trigger writing `STAGING_ROWS`, which no package writes;
- `:GLOBAL.GHOST_FLAG` appears only in a comment and a string literal;
- a form-local program unit named `CLOSE_ITEM` (same name, different scope).
