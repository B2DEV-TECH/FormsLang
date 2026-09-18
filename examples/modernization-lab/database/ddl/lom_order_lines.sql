-- =============================================================================
-- LOM_ORDER_LINES (detail)
-- FACT: LINE_TOTAL = (QUANTITY * UNIT_PRICE) - DISCOUNT_AMOUNT. The formula
-- already exists once, centrally, as LOM_ORDER_API.calc_line_total -- but
-- ORDERS.fmb re-implements it inline in a WHEN-VALIDATE-ITEM trigger instead
-- of calling that function (LOM-MOD-027, HIGH risk: a financial calculation
-- that can silently diverge between the UI and the database).
-- =============================================================================

create table lom_order_lines (
    order_id            number(10)      not null,
    line_number         number(5)       not null,
    product_id          number(10)      not null,
    quantity            number(10)      not null,
    unit_price          number(12,2)    not null,
    discount_amount     number(12,2)    default 0 not null,
    line_total          number(14,2)    not null,
    constraint pk_lom_order_lines primary key (order_id, line_number),
    constraint fk_lom_ol_order foreign key (order_id)
        references lom_orders (order_id) on delete cascade,
    constraint fk_lom_ol_product foreign key (product_id)
        references lom_products (product_id),
    constraint ck_lom_ol_qty check (quantity > 0),
    constraint ck_lom_ol_price check (unit_price >= 0),
    constraint ck_lom_ol_discount check (discount_amount >= 0),
    constraint ck_lom_ol_total check (line_total >= 0)
);

comment on table lom_order_lines is 'Order line detail. QUANTITY validation against available inventory is a presentation-layer rule today (ORDERS.fmb, WHEN-VALIDATE-ITEM on QUANTITY) even though LOM_INVENTORY_API.validate_quantity already exists -- the canonical MOVE_TO_PLSQL_API example for this lab, LOM-MOD-026.';

create index ix_lom_order_lines_product on lom_order_lines (product_id);
