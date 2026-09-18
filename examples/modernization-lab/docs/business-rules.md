# LOM business rules — the domain, independent of migration concerns

This is a reference for what the Legacy Order Management system actually
does, before getting into how any of it should move to APEX. Every rule
below cites the exact table, constraint, or package procedure that
enforces it today — read this first if you need to understand the domain;
read `modernization-challenges.md` next for how migrating it is harder
than it looks.

## Customers

- A customer has a `STATUS` of `ACTIVE` or `INACTIVE`
  (`lom_customers.ck_lom_cust_status`). Inactivating a customer is blocked
  while they have any order not in a terminal state (`SHIPPED`,
  `REJECTED`, `CANCELLED`) — enforced by
  `LOM_CUSTOMER_API.has_open_orders`, called from `change_status`.
- `CREDIT_LIMIT` must be `>= 0` (`ck_lom_cust_credit`). A customer type
  (`LOM_CUSTOMER_TYPES.DEFAULT_CREDIT_LIMIT`) supplies a one-time default
  when a new customer's credit limit is left blank; it is never enforced
  as an ongoing ceiling.
- `LOM_CUSTOMER_API.can_place_order` is the single gate deciding whether a
  customer is eligible to have a new order entered against them at all.
  Today it checks exactly one thing — `get_status(p_customer_id) =
  'ACTIVE'` — and returns `'Y'`/`'N'`; there is no credit or standing
  check behind it (`database/packages/lom_customer_api.pkb`).

## Orders and order lines

- An order's `STATUS` moves through a fixed lifecycle: `DRAFT` ->
  `SUBMITTED` -> (`PENDING_APPROVAL` when over the approval threshold) ->
  `APPROVED` -> `RELEASED` -> `SHIPPED`, with `PENDING_APPROVAL` ->
  `REJECTED`, and `CANCELLED` reachable only from `DRAFT`, `SUBMITTED` or
  `PENDING_APPROVAL` (an `APPROVED`, `RELEASED`, `SHIPPED` or `REJECTED`
  order cannot be cancelled). That is exactly ten legal `(from, to)`
  pairs, and the only thing that may ever change `STATUS` is
  `LOM_ORDER_API.transition_status` — a hardcoded PL/SQL matrix
  (`is_valid_transition`), not the `SEQUENCE_NO` column on
  `LOM_ORDER_STATUS`, which is descriptive only. All ten legal pairs
  happen to increase `SEQUENCE_NO`, so a "sequence must go up" shortcut
  would accept every legal transition and also several illegal ones
  (`DRAFT` -> `SHIPPED`, `REJECTED` -> `APPROVED`); `tests/test_fixtures.py`
  pins both facts from the seed data and the package body.
- Submitting an order (`LOM_ORDER_API.submit_order`) recalculates totals,
  transitions status, and — when the order total exceeds
  `LOM_ORDER_API.gc_approval_threshold` (5000, a package constant) —
  creates an approval request via `LOM_APPROVAL_API.create_approval_request`.
- Each order line's total is `ROUND(quantity * unit_price - discount_amount, 2)`
  (`LOM_ORDER_API.calc_line_total`); the order header's `subtotal`/
  `tax_amount`/`total_amount` are derived from summing lines and applying
  `LOM_ORDER_API.gc_tax_rate` (0.08), via `recalc_order_totals`.
- A line's quantity may not be entered past what
  `LOM_INVENTORY_API.validate_quantity` allows against that product's
  available stock at the order's warehouse.
- Releasing an order (`LOM_ORDER_API.release_order`) reserves the ordered
  quantity against inventory (`LOM_INVENTORY_API.reserve_quantity`) before
  transitioning to `RELEASED`; if there isn't enough stock, the release
  fails with `gc_err_insufficient_stock` and the order stays where it was.
- Shipping an order (`LOM_ORDER_API.ship_order`) marks its shipment row
  `SHIPPED` with today's date and transitions the order to `SHIPPED`.
  Carrier/tracking integration is out of scope for this system —
  `LOM_SHIPMENTS.TRACKING_REFERENCE` exists but nothing populates it.

## Inventory

- `LOM_INVENTORY.QUANTITY_AVAILABLE` is always
  `quantity_on_hand - quantity_reserved` (a virtual column) — this is the
  single authoritative definition of "available to sell."
- Reserving quantity (`LOM_INVENTORY_API.reserve_quantity`) is an atomic,
  race-safe conditional `UPDATE` that only succeeds if enough unreserved
  stock exists; it raises `gc_err_insufficient_stock` otherwise.
- Manually adjusting on-hand quantity (`LOM_INVENTORY_API.adjust_quantity`)
  locks the row (`SELECT ... FOR UPDATE`) and refuses to let the resulting
  on-hand quantity go negative.
- `LOM_INVENTORY_API.default_warehouse` returns the first warehouse where
  `LOM_WAREHOUSES.IS_DEFAULT = 'Y'`; nothing in the schema guarantees
  exactly one warehouse carries that flag.
- Only products with `LOM_PRODUCTS.ACTIVE_FLAG = 'Y'` may be ordered or
  looked up on an order line — but this eligibility check exists **only**
  in the Forms UI layer today (product lookup validation and both the
  Product/Warehouse LOVs), not in any PL/SQL API — see
  `modernization-challenges.md` for why that matters.

## Approvals

- An approval request (`LOM_APPROVALS`) has `STATUS` of `PENDING`,
  `APPROVED`, or `REJECTED` (`ck_lom_appr_status`); nothing prevents more
  than one `PENDING` request existing for the same order at the schema
  level (only `LOM_ORDER_API.submit_order`'s own DRAFT-only guard keeps
  this from happening in practice today).
- Approving (`LOM_APPROVAL_API.approve`) or rejecting
  (`LOM_APPROVAL_API.reject`) an approval transitions the underlying order
  via `LOM_ORDER_API.transition_status` — the same status matrix every
  other order-lifecycle change goes through. Neither procedure checks that
  the request is still `PENDING` before updating it (the `SELECT ... FOR
  UPDATE` has no status predicate, and the audit row hardcodes
  `p_old_value => 'PENDING'`); a second approve/reject on the same request
  is stopped only because the follow-on order transition is illegal
  (`APPROVED` -> `APPROVED`, `REJECTED` -> `REJECTED` and `APPROVED` ->
  `REJECTED` are not in the matrix). Since neither package commits or uses
  an autonomous transaction, the raised error takes the approval update
  and its audit row back with it — provided the caller lets the exception
  propagate instead of catching it and committing.
- Rejecting an approval requires a non-blank `p_comments` argument
  (`gc_err_comments_required`) — a rule enforced in PL/SQL, not by any
  `NOT NULL`/`CHECK` constraint on `LOM_APPROVALS.COMMENTS`.
- Both `create_approval_request` and `approve`/`reject` default their
  identity parameter (`p_requested_by`/`p_approver`) to the PL/SQL `USER`
  pseudo-column — the connected database session's own identity. So does
  `LOM_ORDER_API.transition_status` (`p_changed_by default user`), while
  `submit_order`, `release_order` and `ship_order` expose no identity
  parameter at all and always write `USER` into the audit trail. Under
  APEX that session belongs to the APEX engine's pool account, not to the
  end user — see ADR-004.

## Audit trail

- `LOM_AUDIT_LOG` is a single polymorphic table (`ENTITY_NAME` + `ENTITY_ID`,
  no FK to the tables it describes) written to by `LOM_AUDIT_API.log_event`
  from every business package, recording an action, an old/new value pair,
  who made the change, and when.
