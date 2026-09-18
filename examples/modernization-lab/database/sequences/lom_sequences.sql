-- =============================================================================
-- Legacy Order Management (LOM) modernization lab -- sequences
-- FACT: every sequence below is created and used by the DDL/packages in this
-- lab; none of them are decorative.
-- =============================================================================

create sequence lom_customer_id_seq
    start with 1000 increment by 1 nocache;

create sequence lom_product_id_seq
    start with 1000 increment by 1 nocache;

create sequence lom_order_id_seq
    start with 5000 increment by 1 nocache;

create sequence lom_approval_id_seq
    start with 1 increment by 1 nocache;

create sequence lom_shipment_id_seq
    start with 1 increment by 1 nocache;

create sequence lom_audit_id_seq
    start with 1 increment by 1 nocache;
