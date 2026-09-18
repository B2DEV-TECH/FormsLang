-- =============================================================================
-- LOM seed data -- approvals and shipments
-- FACT: approval_id / shipment_id values are fixed (not sequence-generated),
-- consistent with the rest of the seed. These rows are inserted directly to
-- represent pre-existing history, matching the orders seeded in
-- 04_orders_and_lines.sql.
-- =============================================================================

-- 5003: still PENDING_APPROVAL -> open approval request, no decision yet
insert into lom_approvals (approval_id, order_id, requested_by, requested_date, status)
values (1, 5003, 'SALES_APP', date '2026-08-10', 'PENDING');

-- 5004: already APPROVED
insert into lom_approvals (approval_id, order_id, requested_by, requested_date, status, approver, approval_date, comments)
values (2, 5004, 'SALES_APP', date '2026-08-12', 'APPROVED', 'CREDIT_MGR', date '2026-08-13', 'Within customer credit line, approved as submitted.');

-- 5008: REJECTED, with a mandatory rejection reason (see LOM_APPROVAL_API.reject)
insert into lom_approvals (approval_id, order_id, requested_by, requested_date, status, approver, approval_date, comments)
values (3, 5008, 'SALES_APP', date '2026-08-18', 'REJECTED', 'CREDIT_MGR', date '2026-08-19', 'Unusual order volume for this customer; requesting confirmed PO before resubmission.');

-- 5005: RELEASED, shipment not yet dispatched
insert into lom_shipments (shipment_id, order_id, warehouse_code, status, created_date)
values (1, 5005, 'MAIN', 'PENDING', date '2026-08-14');

-- 5006: SHIPPED, full lifecycle example
insert into lom_shipments (shipment_id, order_id, warehouse_code, shipped_date, status, created_date)
values (2, 5006, 'MAIN', date '2026-08-17', 'SHIPPED', date '2026-08-16');

commit;
