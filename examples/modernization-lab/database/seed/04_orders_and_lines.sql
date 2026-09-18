-- =============================================================================
-- LOM seed data -- orders and order lines
-- FACT: order_id values are fixed (not sequence-generated). Header totals
-- (subtotal/tax_amount/total_amount/approval_required) below are computed
-- with the exact same formulas as LOM_ORDER_API (calc_line_total,
-- recalc_order_totals, requires_approval / gc_tax_rate=0.08,
-- gc_approval_threshold=5000) so the seed is internally consistent, even
-- though these rows are inserted directly rather than through the API --
-- representing a bulk historical load, which is how this kind of seed data
-- normally enters a real system.
--
-- Status coverage: DRAFT, SUBMITTED, PENDING_APPROVAL, APPROVED, RELEASED,
-- SHIPPED, REJECTED, CANCELLED -- all eight states appear at least once.
--
-- FIXTURE: order 5004 is deliberately APPROVED for 20 units of product 2004
-- at warehouse EAST, where EAST only has 2 units on hand (see
-- 03_products_inventory.sql). This is intentional: it is a realistic
-- "approved but not releasable yet" situation, and calling
-- LOM_ORDER_API.release_order(5004) is expected to raise
-- LOM_INVENTORY_API.gc_err_insufficient_stock. See tests/.
-- =============================================================================

-- 5001: DRAFT, no approval needed
insert into lom_orders (order_id, customer_id, order_date, warehouse_code, status, subtotal, tax_amount, total_amount, approval_required, created_date)
values (5001, 1001, date '2026-08-03', 'MAIN', 'DRAFT', 250.00, 20.00, 270.00, 'N', date '2026-08-03');

insert into lom_order_lines (order_id, line_number, product_id, quantity, unit_price, discount_amount, line_total)
values (5001, 1, 2001, 10, 25.00, 0, 250.00);

-- 5002: SUBMITTED, no approval needed
insert into lom_orders (order_id, customer_id, order_date, warehouse_code, status, subtotal, tax_amount, total_amount, approval_required, created_date)
values (5002, 1002, date '2026-08-05', 'MAIN', 'SUBMITTED', 2402.50, 192.20, 2594.70, 'N', date '2026-08-05');

insert into lom_order_lines (order_id, line_number, product_id, quantity, unit_price, discount_amount, line_total)
values (5002, 1, 2002, 20, 89.50, 0, 1790.00);
insert into lom_order_lines (order_id, line_number, product_id, quantity, unit_price, discount_amount, line_total)
values (5002, 2, 2006, 50, 12.75, 25.00, 612.50);

-- 5003: PENDING_APPROVAL (over threshold)
insert into lom_orders (order_id, customer_id, order_date, warehouse_code, status, subtotal, tax_amount, total_amount, approval_required, created_date)
values (5003, 1003, date '2026-08-10', 'MAIN', 'PENDING_APPROVAL', 6470.00, 517.60, 6987.60, 'Y', date '2026-08-10');

insert into lom_order_lines (order_id, line_number, product_id, quantity, unit_price, discount_amount, line_total)
values (5003, 1, 2007, 20, 199.00, 0, 3980.00);
insert into lom_order_lines (order_id, line_number, product_id, quantity, unit_price, discount_amount, line_total)
values (5003, 2, 2008, 10, 259.00, 100.00, 2490.00);

-- 5004: APPROVED (over threshold, already approved) -- see FIXTURE note above
insert into lom_orders (order_id, customer_id, order_date, warehouse_code, status, subtotal, tax_amount, total_amount, approval_required, created_date)
values (5004, 1005, date '2026-08-12', 'EAST', 'APPROVED', 5580.00, 446.40, 6026.40, 'Y', date '2026-08-12');

insert into lom_order_lines (order_id, line_number, product_id, quantity, unit_price, discount_amount, line_total)
values (5004, 1, 2004, 20, 289.00, 200.00, 5580.00);

-- 5005: RELEASED, no approval needed
insert into lom_orders (order_id, customer_id, order_date, warehouse_code, status, subtotal, tax_amount, total_amount, approval_required, created_date)
values (5005, 1002, date '2026-08-14', 'MAIN', 'RELEASED', 2349.90, 187.99, 2537.89, 'N', date '2026-08-14');

insert into lom_order_lines (order_id, line_number, product_id, quantity, unit_price, discount_amount, line_total)
values (5005, 1, 2003, 10, 149.99, 0, 1499.90);
insert into lom_order_lines (order_id, line_number, product_id, quantity, unit_price, discount_amount, line_total)
values (5005, 2, 2005, 200, 4.25, 0, 850.00);

-- 5006: SHIPPED, full lifecycle example
insert into lom_orders (order_id, customer_id, order_date, warehouse_code, status, subtotal, tax_amount, total_amount, approval_required, created_date)
values (5006, 1006, date '2026-08-16', 'MAIN', 'SHIPPED', 202.00, 16.16, 218.16, 'N', date '2026-08-16');

insert into lom_order_lines (order_id, line_number, product_id, quantity, unit_price, discount_amount, line_total)
values (5006, 1, 2001, 4, 25.00, 0, 100.00);
insert into lom_order_lines (order_id, line_number, product_id, quantity, unit_price, discount_amount, line_total)
values (5006, 2, 2006, 8, 12.75, 0, 102.00);

-- 5007: CANCELLED (customer went INACTIVE after this order was placed)
insert into lom_orders (order_id, customer_id, order_date, warehouse_code, status, subtotal, tax_amount, total_amount, approval_required, created_date)
values (5007, 1004, date '2026-07-20', 'MAIN', 'CANCELLED', 125.00, 10.00, 135.00, 'N', date '2026-07-20');

insert into lom_order_lines (order_id, line_number, product_id, quantity, unit_price, discount_amount, line_total)
values (5007, 1, 2001, 5, 25.00, 0, 125.00);

-- 5008: REJECTED (over threshold, rejected on review)
insert into lom_orders (order_id, customer_id, order_date, warehouse_code, status, subtotal, tax_amount, total_amount, approval_required, created_date)
values (5008, 1003, date '2026-08-18', 'MAIN', 'REJECTED', 5970.00, 477.60, 6447.60, 'Y', date '2026-08-18');

insert into lom_order_lines (order_id, line_number, product_id, quantity, unit_price, discount_amount, line_total)
values (5008, 1, 2007, 30, 199.00, 0, 5970.00);

commit;
