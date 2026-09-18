-- =============================================================================
-- LOM_PRODUCTS / LOM_INVENTORY
-- FACT: QUANTITY_AVAILABLE is a virtual column (on_hand - reserved) so every
-- reader (Forms, APEX, PL/SQL, ad-hoc SQL) computes availability identically.
-- Forms nonetheless re-derives it with an inline SELECT in ORDERS.fmb instead
-- of calling LOM_INVENTORY_API.get_available_qty -- see LOM-MOD-025.
-- =============================================================================

create table lom_products (
    product_id      number(10)      not null,
    product_code    varchar2(20)    not null,
    product_name    varchar2(200)   not null,
    description     varchar2(1000),
    unit_price      number(12,2)    not null,
    active_flag     char(1)         default 'Y' not null,
    created_date    date            default sysdate not null,
    constraint pk_lom_products primary key (product_id),
    constraint uk_lom_products_code unique (product_code),
    constraint ck_lom_prod_price check (unit_price >= 0),
    constraint ck_lom_prod_active check (active_flag in ('Y','N'))
);

comment on table lom_products is 'Product catalog. UNIT_PRICE is the current default sales price copied into LOM_ORDER_LINES.UNIT_PRICE at line-entry time (a snapshot, not a live reference -- see data-model.md).';

create table lom_inventory (
    product_id          number(10)  not null,
    warehouse_code      varchar2(10) not null,
    quantity_on_hand    number(12)  default 0 not null,
    quantity_reserved   number(12)  default 0 not null,
    quantity_available  number(12) generated always as (quantity_on_hand - quantity_reserved) virtual,
    reorder_level       number(12)  default 0 not null,
    last_updated        date        default sysdate not null,
    constraint pk_lom_inventory primary key (product_id, warehouse_code),
    constraint fk_lom_inv_product foreign key (product_id)
        references lom_products (product_id),
    constraint fk_lom_inv_warehouse foreign key (warehouse_code)
        references lom_warehouses (warehouse_code),
    constraint ck_lom_inv_on_hand check (quantity_on_hand >= 0),
    constraint ck_lom_inv_reserved check (quantity_reserved >= 0),
    constraint ck_lom_inv_reorder check (reorder_level >= 0)
);

comment on table lom_inventory is 'Stock position per product/warehouse. QUANTITY_AVAILABLE is a virtual column: the single authoritative definition of "available to sell" (on_hand - reserved). See LOM-MOD-025, LOM-MOD-026.';

create index ix_lom_inventory_wh on lom_inventory (warehouse_code);
