-- =============================================================================
-- Legacy Order Management (LOM) modernization lab -- lookup tables
-- FACT: LOM_ORDER_STATUS.SEQUENCE_NO documents the intended forward flow but
-- is NOT used to enforce transitions -- LOM_ORDER_API.transition_status
-- (database/packages/lom_order_api.pkb) enforces the real state machine with
-- a hardcoded matrix. See docs/business-rules.md and LOM-MOD-002.
-- =============================================================================

create table lom_customer_types (
    customer_type_code     varchar2(10)    not null,
    description             varchar2(100)   not null,
    default_credit_limit    number(12,2)    not null,
    constraint pk_lom_customer_types primary key (customer_type_code),
    constraint ck_lom_cust_types_limit check (default_credit_limit >= 0)
);

comment on table lom_customer_types is 'Lookup: customer segments and their default credit limit.';

create table lom_warehouses (
    warehouse_code  varchar2(10)    not null,
    warehouse_name  varchar2(100)   not null,
    is_default      char(1)         default 'N' not null,
    active_flag     char(1)         default 'Y' not null,
    constraint pk_lom_warehouses primary key (warehouse_code),
    constraint ck_lom_wh_is_default check (is_default in ('Y','N')),
    constraint ck_lom_wh_active check (active_flag in ('Y','N'))
);

comment on table lom_warehouses is 'Lookup: shipping warehouses. Exactly one row should carry IS_DEFAULT=Y (enforced by LOM_INVENTORY_API.default_warehouse picking the first match, not by a constraint -- see LOM-MOD-018).';

create table lom_order_status (
    status_code     varchar2(20)    not null,
    description     varchar2(100)   not null,
    sequence_no     number(4)       not null,
    constraint pk_lom_order_status primary key (status_code)
);

comment on table lom_order_status is 'Lookup/documentation only: the labels and display order of order statuses. DESIGN DECISION: the actual allowed transitions are enforced in PL/SQL (LOM_ORDER_API.transition_status), not derived from this table -- see LOM-MOD-002.';
