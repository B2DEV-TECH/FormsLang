# Why LOM is harder to modernize than it looks

This lab is built around one core claim: a Forms-to-APEX migration that
treats each trigger as "translate this PL/SQL into a page process" will
compile, will look correct in a demo, and will quietly change what the
application does. This document walks through the recurring patterns
behind the 41 cases in `expected/modernization-ground-truth.json`, grouped
by theme rather than by module. Every `LOM-MOD-###` id below is grounded
in a specific line of `database/` or `forms/xml/` — see the registry for
the exact source citation.

## Theme 1 — Business logic duplicated between Forms and PL/SQL

The single most common defect pattern in this lab: a Forms trigger
re-implements a check that a `LOM_*_API` package already provides, instead
of calling it. Two independent implementations of the same rule will drift
the moment one changes and the other doesn't.

- LOM-MOD-011 — Forms re-queries open-order status directly instead of
  calling `LOM_CUSTOMER_API.has_open_orders`, even though
  `LOM_CUSTOMER_API.change_status` already calls it correctly.
- LOM-MOD-025/026 — an inline `SELECT` and a hand-rolled threshold
  comparison instead of `LOM_INVENTORY_API.get_available_qty`/
  `validate_quantity`.
- LOM-MOD-027 — the highest-risk instance: a financial formula
  (`ROUND(quantity * unit_price - discount_amount, 2)`) duplicated
  verbatim on two different triggers instead of calling
  `LOM_ORDER_API.calc_line_total` once.
- LOM-MOD-010 — the contrast case: a `CHECK` constraint re-verified in a
  trigger, harmlessly. It is *not* classified `MOVE_TO_PLSQL_API`, because
  nothing needs to be centralized — the constraint already owns the rule,
  and the trigger maps one-to-one onto an APEX item validation
  (`CONVERT`, `LOW`). It is in the registry precisely so that a classifier
  which flags every duplicated check as "move it into the API" is caught
  over-classifying.
- LOM-MOD-039 — even `OM_SHARED.pll`, the *shared* library, has its own
  bypass: `log_action` writes to `LOM_AUDIT_LOG` directly instead of
  calling `LOM_AUDIT_API.log_event`, the function every business package
  already uses correctly.

**Why this matters for migration**: a literal port carries each
duplicate forward as two separate pieces of APEX logic (a page validation
plus, wherever the PL/SQL API is *also* called, the API's own check) that
now have to be kept in sync by hand in a codebase with no compiler warning
for "these two validations used to be the same." The correct fix is not a
translation — it's deleting the duplicate and pointing the single
remaining call site at the API.

## Theme 2 — Business logic with no PL/SQL home at all

A sharper version of Theme 1: some logic was never centralized anywhere,
because the API for it doesn't exist yet.

- LOM-MOD-037 — there is no `LOM_ORDER_API.add_line`/`update_line`
  procedure. Every order-line rule (product eligibility, quantity
  validation, discount, line total) lives *only* in Forms
  `WHEN-VALIDATE-ITEM` triggers, validating a raw table insert. This is
  the root cause behind LOM-MOD-025, 026, and 027 all looking like
  "call the API instead" fixes: there is no line-level API to call.
  Modernizing this correctly means designing new PL/SQL, not moving a
  call site.

## Theme 3 — A mechanical port would faithfully carry forward a bypass

The lab's two flagship cases: not a duplication, but an outright
bypass of the API layer, with a real consequence if copied as-is.

- LOM-MOD-041 — `APPROVALS.fmb`'s Approve button issues raw `UPDATE`
  statements against `LOM_APPROVALS` and `LOM_ORDERS` directly, skipping
  `LOM_APPROVAL_API.approve` — which itself calls
  `LOM_ORDER_API.transition_status` (the real status-transition control,
  LOM-MOD-002) and `LOM_AUDIT_API.log_event`. Translate this trigger's SQL
  mechanically into an APEX page process, and the APEX app ships without
  either.
- LOM-MOD-042 — the Reject button's version of the same bypass, with a
  sharper edge: `LOM_APPROVAL_API.reject` enforces that a rejection reason
  is mandatory; the raw `UPDATE` this trigger performs does not. A
  mechanical port would let an APEX user reject an order silently, with no
  explanation, even though the Forms UI's own tooltip claims a reason is
  required.

Contrast both with LOM-MOD-016 (`INVENTORY.fmb`'s Adjust button, which
correctly calls `LOM_INVENTORY_API.adjust_quantity`) and LOM-MOD-021
(`ORDERS.fmb`'s Submit button, equally clean) — proof that this codebase
knows how to call its own API correctly elsewhere, which makes the
bypass in `APPROVALS.fmb` a defect to fix, not a stylistic inconsistency
to preserve.

## Theme 4 — Rules enforced only where they're least visible

- The status-gate idea behind LOM-MOD-011/019, generalized to
  `ACTIVE_FLAG`: only Forms
  (the order-line product lookup trigger, and both the Product/Warehouse
  LOVs) filters out inactive products and warehouses. No PL/SQL API
  independently enforces this. Any future caller that bypasses Forms —
  including, ironically, the very same `add_line` API that LOM-MOD-037
  says should exist — needs to be told explicitly to carry this filter
  forward; it will not happen automatically.
- LOM-MOD-031 — `default user` as an identity-parameter default resolves
  to the *database session's* identity. In Forms, that is genuinely the
  connected end user. In APEX, the database session belongs to the APEX
  engine's pool account (`APEX_PUBLIC_USER` when fronted by ORDS) — not
  the parsing schema and not the end user — so an unmodified call site
  would silently attribute every approval to that pool account. This is
  invisible in code review unless you already know to look for it.
- LOM-MOD-032 — the mandatory-rejection-comment rule (see Theme 3) is
  visible only as a UI `Hint` string and a PL/SQL exception; there is no
  schema-level `NOT NULL` a reviewer could grep for.

## Theme 5 — Navigation with no APEX equivalent

Forms' `CALL_FORM`/`OPEN_FORM` model (modal vs. non-modal, MDI window
positioning, shared session state across open forms) has no direct APEX
analogue. Each of `ORDERS.fmb`'s three cross-module buttons needs its own
human decision about what replaces it:

- LOM-MOD-020 — `CALL_FORM` into `APPROVALS` (modal, blocks `ORDERS`) —
  candidate for a modal dialog page, an inline region, or a plain link,
  each with different UX trade-offs.
- LOM-MOD-022 — `OPEN_FORM` into `INVENTORY` (non-modal, both stay open) —
  candidate for a new-tab link or a modal region; no in-memory `PARAMLIST`
  state survives either way, so parameters must travel as URL/page items.
- LOM-MOD-023 — `CALL_FORM` into `CUSTOMERS`, query-only — the simplest of
  the three; a plain link suffices.

`OM_SHARED.open_form_with_context` (LOM-MOD-007), the helper wrapping all
three calls, is dropped wholesale rather than translated — it wraps
window-positioning coordinates that mean nothing in a browser.

## Theme 6 — Silent scope gaps worth a deliberate decision

Not defects so much as unexamined assumptions baked in by omission:

- LOM-MOD-018 — `LOM_WAREHOUSES` has no constraint guaranteeing exactly
  one default warehouse.
- LOM-MOD-030 — no constraint prevents duplicate `PENDING` approval rows
  for one order.
- LOM-MOD-036 — neither `LOM_APPROVAL_WORKLIST_V` nor `LOM_INVENTORY_V`
  filters by owner/region; every row is visible to every caller.
- LOM-MOD-038 — `LOM_SHIPMENTS.TRACKING_REFERENCE` is dead weight (never
  written, never read); carrier integration was never built.

None of these block a migration, but each is exactly the kind of gap that
becomes a production incident three months after go-live if nobody
decided on purpose to leave it as-is.
