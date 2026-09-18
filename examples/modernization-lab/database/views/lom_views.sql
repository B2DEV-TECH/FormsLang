-- =============================================================================
-- Views used as Forms query data sources (Forms base-table blocks bind to a
-- single row source; these joins let INVENTORY.fmb and APPROVALS.fmb show
-- denormalized worklist data without embedding the join in every trigger).
-- =============================================================================

create or replace view lom_inventory_v as
select
    i.product_id,
    p.product_code,
    p.product_name,
    i.warehouse_code,
    w.warehouse_name,
    i.quantity_on_hand,
    i.quantity_reserved,
    i.quantity_available,
    i.reorder_level,
    i.last_updated
from lom_inventory i
join lom_products  p on p.product_id = i.product_id
join lom_warehouses w on w.warehouse_code = i.warehouse_code;

comment on table lom_inventory_v is 'Query data source for INVENTORY.fmb / BK_INVENTORY. DESIGN DECISION: the view deliberately does NOT compute a low-stock flag -- that derivation stays in the Forms POST-QUERY trigger on purpose, to give this lab a REPLACE_WITH_APEX_NATIVE example (LOM-MOD-035: an Interactive Report highlight/format rule replaces the PL/SQL-free presentation logic).';

create or replace view lom_approval_worklist_v as
select
    a.approval_id,
    a.order_id,
    o.customer_id,
    c.customer_name,
    o.total_amount    as order_total,
    o.currency_code,
    a.requested_by,
    a.requested_date,
    a.status,
    a.approver,
    a.approval_date,
    a.comments
from lom_approvals a
join lom_orders    o on o.order_id = a.order_id
join lom_customers c on c.customer_id = o.customer_id;

comment on table lom_approval_worklist_v is 'Query data source for APPROVALS.fmb / BK_APPROVAL. Read-only by convention: the Approve/Reject buttons write to LOM_APPROVALS and LOM_ORDERS directly, not through this view -- see LOM-MOD-041/LOM-MOD-042.';
