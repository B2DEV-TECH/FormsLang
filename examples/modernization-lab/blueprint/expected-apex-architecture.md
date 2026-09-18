# Target APEX architecture for LOM

This is the intended shape of the APEX application this lab's Forms
modules would become, mapped module-by-module. It is a design target, not
a build: no APEX export exists in this lab (see "What this lab does not
include" at the end). Every page/process below is justified by specific
`LOM-MOD-###` cases in `expected/modernization-ground-truth.json`; consult
the registry for the full rationale behind any individual decision.

## Page map

| Page | Replaces | Type | Notes |
|------|----------|------|-------|
| 1. Customers | `CUSTOMERS.fmb` | Interactive Grid | see below |
| 2. Orders | `ORDERS.fmb` (BK_ORDER) | Interactive Grid + form region | master of a master-detail pair |
| 2a. Order lines | `ORDERS.fmb` (BK_ORDER_LINE) | Inline detail Interactive Grid on Page 2 | driven by the relation in the registry (ORDERS has the lab's only `Relation`) |
| 3. Inventory | `INVENTORY.fmb` | Interactive Report over `lom_inventory_v` | read-mostly, one adjustment modal |
| 3a. Adjust quantity | `INVENTORY.fmb` (BT_ADJUST) | Modal dialog page | calls `LOM_INVENTORY_API.adjust_quantity` (LOM-MOD-016, `PRESERVE` -- already calls the API correctly) |
| 4. Approvals worklist | `APPROVALS.fmb` | Interactive Report over `lom_approval_worklist_v` | see LOM-MOD-036 caveat below |
| 4a. Approve / Reject | `APPROVALS.fmb` (BT_APPROVE/BT_REJECT) | Page processes on Page 4, not raw DML | must call `LOM_APPROVAL_API.approve`/`.reject` -- see LOM-MOD-041/042, ADR-003 and ADR-004 |

No page replaces `OM_SHARED.pll` or the `LOM_MAIN` menu module directly:
their responsibilities are absorbed into APEX platform features (page
template, navigation menu, and the App Builder's own alert/confirmation
dynamic actions) rather than ported as a page or process.

## Customers (Page 1)

- Interactive Grid over `LOM_CUSTOMERS`, `STATUS` shown as a badge.
- `LOM_CUSTOMER_API.can_place_order` and `.has_open_orders` are called
  from a validation process before any status change or order-creation
  action succeeds (LOM-MOD-011, LOM-MOD-019) -- never re-implemented as a
  page-level query.
- Email format validation (LOM-MOD-015) uses APEX's native email item
  validation (`REPLACE_WITH_APEX_NATIVE`), not a ported regex check.
- `LOM_CUSTOMER_TYPES.DEFAULT_CREDIT_LIMIT` is surfaced only as a
  suggested value when creating a customer (a page item default sourced
  from the customer type), never re-applied as an ongoing ceiling
  (LOM-MOD-004 is `MANUAL_REVIEW` precisely because "should this become an
  enforced ceiling in APEX" is a business decision this lab does not make
  on the customer's behalf).

## Orders (Page 2 + 2a)

- Master-detail Interactive Grid: header region bound to `LOM_ORDERS`,
  inline detail region bound to `LOM_ORDER_LINES`, mirroring the one
  `Relation` (`BK_ORDER` -> `BK_ORDER_LINE`) that exists across all four
  forms.
- Every status change (Submit, Release, Ship, Cancel) is a page process
  calling the matching `LOM_ORDER_API` procedure
  (`submit_order`/`release_order`/`ship_order`/`transition_status`)
  directly -- never a page-level `UPDATE lom_orders SET status = ...`
  (ADR-002). Sequence numbers on `LOM_ORDER_STATUS` drive only the
  display order of a read-only status badge/select list (LOM-MOD-005),
  never the transition logic itself.
- Order-line validation (product eligibility, quantity, discount, line
  total) calls `LOM_ORDER_API`/`LOM_INVENTORY_API` procedures from a
  Dynamic Action or page validation. Because no `add_line`/`update_line`
  procedure exists yet (LOM-MOD-037), this is new PL/SQL that must be
  designed before this region can be built as described -- it is not a
  page that can be assembled purely from what `LOM_ORDER_API` exposes
  today.
- Line numbering (LOM-MOD-017, currently inline `MAX()+1`) moves into
  whatever new line-level API procedure LOM-MOD-037 produces, rather than
  being reimplemented as its own page-level query.
- The Submit confirmation alert (LOM-MOD-034) is an APEX confirmation
  Dynamic Action, not a ported `SHOW_ALERT` call.
- `CLEAR_FORM(NO_VALIDATE)` + `CREATE_RECORD` (LOM-MOD-024, entering a new
  order) has a direct mechanical equivalent: the Interactive Grid's native
  "add row" affordance.

### Cross-module navigation from Orders

Each of the three navigation cases gets the pattern ADR-005 assigns it,
not a single uniform treatment:
- LOM-MOD-020 (into Approvals, modal in Forms) -> a modal dialog page
  passing the order ID as a page item.
- LOM-MOD-022 (into Inventory, non-modal in Forms) -> a plain link to
  Page 3, opened in a new browser tab; no shared in-memory state is
  carried across, since APEX pages don't share a `PARAMLIST`.
- LOM-MOD-023 (into Customers, query-only) -> a plain link to Page 1
  pre-filtered to the relevant customer.
- `OM_SHARED.open_form_with_context` (LOM-MOD-007) is not ported: its
  window-positioning logic has no meaning in a browser.

## Inventory (Page 3 / 3a)

- `LOM_INVENTORY_V` backs a read-focused Interactive Report.
- The low-stock flag (LOM-MOD-035, currently computed in a Forms
  `POST-QUERY` trigger) becomes a computed column in the view or an APEX
  native "icon/badge based on column value" formatting rule --
  `REPLACE_WITH_APEX_NATIVE`, not a page-load PL/SQL loop re-implementing
  the same comparison.
- The Adjust-quantity modal is the one write path on this page, and it is
  the lab's cleanest case: it already calls `LOM_INVENTORY_API.adjust_quantity`
  correctly in Forms (LOM-MOD-016, `PRESERVE`), so the APEX page process is
  a direct call to the same procedure, unchanged.

## Approvals (Page 4 / 4a)

This is the highest-risk page in the whole application, and the one
requiring the most care to build correctly rather than mechanically:

- The worklist query (`LOM_APPROVAL_WORKLIST_V`) has a hardcoded filter
  today (LOM-MOD-029) and no row-level ownership/region filtering
  (LOM-MOD-036) -- before this becomes a multi-user APEX page, someone
  must decide whether "every approver sees every pending approval,
  everywhere" is the intended production behavior or an artifact of a
  single-user Forms deployment. This lab does not decide that question;
  it flags it (`MANUAL_REVIEW`).
- The Approve and Reject actions must be page processes that call
  `LOM_APPROVAL_API.approve`/`.reject` directly. The current Forms
  fixture (`forms/xml/APPROVALS.xml`, BT_APPROVE/BT_REJECT) deliberately
  demonstrates the wrong way to build this -- raw `UPDATE` statements
  bypassing the API and its mandatory-rejection-comment rule
  (LOM-MOD-041/042). A page built by literally translating those
  triggers' SQL would reproduce both defects in APEX. Do not do that.
- Both calls must explicitly pass `v('APP_USER')` as the approver
  identity (ADR-004) -- omitting it lets the identity parameter default to
  the APEX engine's database session user, silently misattributing every
  approval.
- The confirmation alerts before Approve/Reject (`AL_CONFIRM_APPROVE`/
  `AL_CONFIRM_REJECT` in the Forms fixture) become APEX confirmation
  Dynamic Actions on the respective buttons, same as LOM-MOD-034 on the
  Orders page.

## Cross-cutting, applies to every page

- Audit logging: every write path above must result in a call to
  `LOM_AUDIT_API.log_event` -- through the business package it's already
  wired into (`LOM_ORDER_API`, `LOM_APPROVAL_API`, etc.), never a
  duplicate direct insert into `LOM_AUDIT_LOG` from the APEX layer itself
  (the same defect `OM_SHARED.log_action` already commits in Forms,
  LOM-MOD-039).
- Global state: `:GLOBAL.G_USER` (Forms) becomes `v('APP_USER')`/`:APP_USER`
  (APEX) everywhere it's read (LOM-MOD-008), not a custom session-state
  workaround.
- Hardcoded constants (LOM-MOD-001: approval threshold 5000, tax rate
  0.08) stay exactly where they are, inside `LOM_ORDER_API`'s package
  spec -- `REFACTOR` in the registry (e.g. promoting them to an
  application-level settings table is a legitimate future improvement,
  but out of scope for this migration itself).

## What this lab does not include

No `.sql` APEX application export, no page-by-page APEX Builder
screenshots, and no working APEX application are part of this lab. This
document is the design target a migration would build toward, grounded in
the 41-case registry -- not a delivered application. Building the actual
APEX pages against a live workspace is explicitly out of scope (see the
top-level `README.md`'s "What this lab is not" section).
