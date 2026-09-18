-- =============================================================================
-- LOM_ORDERS (header)
-- FACT: SUBTOTAL/TAX_AMOUNT/TOTAL_AMOUNT are maintained exclusively by
-- LOM_ORDER_API.recalc_order_totals, called from ORDERS.fmb's line-level
-- POST-INSERT/POST-UPDATE/POST-DELETE triggers (LOM-MOD-028, a case of logic
-- already correctly centralized -- only the call site moves in APEX).
-- =============================================================================

create table lom_orders (
    order_id            number(10)      not null,
    customer_id         number(10)      not null,
    order_date          date            default sysdate not null,
    warehouse_code      varchar2(10)    not null,
    status              varchar2(20)    default 'DRAFT' not null,
    currency_code       varchar2(3)     default 'USD' not null,
    subtotal            number(14,2)    default 0 not null,
    tax_amount          number(14,2)    default 0 not null,
    total_amount        number(14,2)    default 0 not null,
    approval_required   char(1)         default 'N' not null,
    created_by          varchar2(30)    default user not null,
    created_date        date            default sysdate not null,
    updated_date         date,
    constraint pk_lom_orders primary key (order_id),
    constraint fk_lom_ord_customer foreign key (customer_id)
        references lom_customers (customer_id),
    constraint fk_lom_ord_warehouse foreign key (warehouse_code)
        references lom_warehouses (warehouse_code),
    constraint fk_lom_ord_status foreign key (status)
        references lom_order_status (status_code),
    constraint ck_lom_ord_approval_req check (approval_required in ('Y','N')),
    constraint ck_lom_ord_amounts check (subtotal >= 0 and tax_amount >= 0 and total_amount >= 0)
);

comment on table lom_orders is 'Sales order header. STATUS is only ever changed through LOM_ORDER_API.transition_status, which enforces the DRAFT -> SUBMITTED -> PENDING_APPROVAL -> APPROVED -> RELEASED -> SHIPPED flow (with PENDING_APPROVAL -> REJECTED and any status -> CANCELLED). See LOM-MOD-002 (CRITICAL) and docs/business-rules.md.';

create index ix_lom_orders_customer on lom_orders (customer_id);
create index ix_lom_orders_status on lom_orders (status);
create index ix_lom_orders_warehouse on lom_orders (warehouse_code);
