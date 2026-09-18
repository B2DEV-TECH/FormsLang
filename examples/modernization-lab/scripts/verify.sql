-- =============================================================================
-- LOM modernization lab -- post-install/seed verification
-- Run after install.sql and seed.sql. Fails loudly (RAISE_APPLICATION_ERROR)
-- on the first check that doesn't hold, rather than printing a silent
-- mismatch -- and exits SQL*Plus with a failure code (whenever sqlerror
-- exit failure), so it is safe to run in an automated pipeline: a failed
-- check is a non-zero exit, not a line of output somebody has to read.
--
-- Usage (from this directory or from the lab root):
--   sqlplus lom_lab/<your_password>@//localhost:1521/freepdb1 @verify.sql
--   sqlplus lom_lab/<your_password>@//localhost:1521/freepdb1 @scripts/verify.sql
-- =============================================================================

set define off
set serveroutput on
whenever sqlerror exit failure rollback

prompt === Row counts ===
select 'lom_customer_types' tbl, count(*) rows_ from lom_customer_types
union all select 'lom_order_status',    count(*) from lom_order_status
union all select 'lom_warehouses',      count(*) from lom_warehouses
union all select 'lom_customers',       count(*) from lom_customers
union all select 'lom_products',        count(*) from lom_products
union all select 'lom_inventory',       count(*) from lom_inventory
union all select 'lom_orders',          count(*) from lom_orders
union all select 'lom_order_lines',     count(*) from lom_order_lines
union all select 'lom_approvals',       count(*) from lom_approvals
union all select 'lom_shipments',       count(*) from lom_shipments
union all select 'lom_audit_log',       count(*) from lom_audit_log
order by 1;

prompt === Object validity ===
select object_type, object_name, status
from user_objects
where status != 'VALID'
order by object_type, object_name;

prompt === Known-fixture business assertions ===
declare
    v_count       number;
    v_available   number;

    procedure check_true(p_label in varchar2, p_condition in boolean) is
    begin
        if not p_condition then
            raise_application_error(-20000, 'VERIFY FAILED: ' || p_label);
        end if;
        dbms_output.put_line('OK   ' || p_label);
    end check_true;
begin
    -- Every table this lab creates has at least one seeded row.
    select count(*) into v_count from lom_customers;
    check_true('lom_customers is seeded', v_count > 0);

    select count(*) into v_count from lom_orders;
    check_true('lom_orders is seeded', v_count > 0);

    -- FIXTURE: order 5004 is deliberately APPROVED but under-stocked at
    -- EAST for product 2004 (20 units needed, 2 on hand) -- see
    -- database/seed/04_orders_and_lines.sql. This is the case
    -- LOM_ORDER_API.release_order(5004) is meant to fail against with
    -- gc_err_insufficient_stock. Verify the fixture's own numbers still
    -- hold (this script does not call release_order itself, since that
    -- would consume the fixture -- run it explicitly if you want to
    -- observe the exception).
    select quantity_available into v_available
    from lom_inventory
    where product_id = 2004 and warehouse_code = 'EAST';
    check_true(
        'order 5004 fixture is still under-stocked at EAST (available=' || v_available || ', order needs 20)',
        v_available < 20
    );

    -- LOM_INVENTORY.QUANTITY_AVAILABLE is a virtual column
    -- (quantity_on_hand - quantity_reserved, LOM-MOD-025's single
    -- authoritative definition) -- spot-check it computed correctly for
    -- every seeded row rather than trusting the DDL comment alone.
    select count(*) into v_count
    from lom_inventory
    where quantity_available != quantity_on_hand - quantity_reserved;
    check_true('quantity_available matches quantity_on_hand - quantity_reserved for every row', v_count = 0);

    -- Order 5006 is the seeded full-lifecycle example (DRAFT ->
    -- SUBMITTED -> APPROVED -> RELEASED -> SHIPPED, see
    -- database/seed/06_audit_log.sql) and must have ended SHIPPED.
    select count(*) into v_count from lom_orders where order_id = 5006 and status = 'SHIPPED';
    check_true('order 5006 reached SHIPPED', v_count = 1);

    -- Order 5008 is the seeded REJECTED example and must carry a mandatory
    -- rejection comment (LOM_APPROVAL_API.reject enforces this on new
    -- rejections; this seeded row must not itself violate the rule it
    -- illustrates).
    select count(*) into v_count
    from lom_approvals
    where order_id = 5008 and status = 'REJECTED' and comments is not null;
    check_true('order 5008''s rejection carries a non-null comment', v_count = 1);

    dbms_output.put_line('All checks passed.');
end;
/
