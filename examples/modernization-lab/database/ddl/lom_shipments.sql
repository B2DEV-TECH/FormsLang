-- =============================================================================
-- LOM_SHIPMENTS
-- FACT: one shipment row is created by LOM_ORDER_API.release_order when an
-- order transitions RELEASED -> SHIPPED is out of this lab's scope (no
-- carrier/tracking integration is modeled); the shipment row exists mainly to
-- give the order lifecycle a visible terminal state and an audit trail.
-- =============================================================================

create table lom_shipments (
    shipment_id         number(10)      not null,
    order_id            number(10)      not null,
    warehouse_code      varchar2(10)    not null,
    shipped_date        date,
    status              varchar2(20)    default 'PENDING' not null,
    tracking_reference  varchar2(60),
    created_date        date            default sysdate not null,
    constraint pk_lom_shipments primary key (shipment_id),
    constraint uk_lom_shipments_order unique (order_id),
    constraint fk_lom_ship_order foreign key (order_id)
        references lom_orders (order_id),
    constraint fk_lom_ship_warehouse foreign key (warehouse_code)
        references lom_warehouses (warehouse_code),
    constraint ck_lom_ship_status check (status in ('PENDING','SHIPPED','CANCELLED'))
);

comment on table lom_shipments is 'One shipment record per released order. Created by LOM_ORDER_API.release_order; there is intentionally no separate Forms screen for shipments in this lab (see docs/forms-inventory.md, "what was deliberately left out").';

create index ix_lom_shipments_status on lom_shipments (status);
