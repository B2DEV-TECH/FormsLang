-- =============================================================================
-- LOM seed data -- lookups
-- FACT: this is realistic, hand-authored seed data, not randomly generated.
-- FIXTURE: values are illustrative for the lab and do not represent any real
-- organization, customer, or product.
-- =============================================================================

insert into lom_customer_types (customer_type_code, description, default_credit_limit)
values ('RETAIL', 'Retail / walk-in account', 10000);

insert into lom_customer_types (customer_type_code, description, default_credit_limit)
values ('WHOLESALE', 'Wholesale / distributor account', 75000);

insert into lom_customer_types (customer_type_code, description, default_credit_limit)
values ('VIP', 'Key account with negotiated terms', 250000);

insert into lom_warehouses (warehouse_code, warehouse_name, is_default, active_flag)
values ('MAIN', 'Main Distribution Center', 'Y', 'Y');

insert into lom_warehouses (warehouse_code, warehouse_name, is_default, active_flag)
values ('EAST', 'East Regional Warehouse', 'N', 'Y');

insert into lom_order_status (status_code, description, sequence_no) values ('DRAFT', 'Draft', 10);
insert into lom_order_status (status_code, description, sequence_no) values ('SUBMITTED', 'Submitted', 20);
insert into lom_order_status (status_code, description, sequence_no) values ('PENDING_APPROVAL', 'Pending Approval', 30);
insert into lom_order_status (status_code, description, sequence_no) values ('APPROVED', 'Approved', 40);
insert into lom_order_status (status_code, description, sequence_no) values ('REJECTED', 'Rejected', 35);
insert into lom_order_status (status_code, description, sequence_no) values ('RELEASED', 'Released', 50);
insert into lom_order_status (status_code, description, sequence_no) values ('SHIPPED', 'Shipped', 60);
insert into lom_order_status (status_code, description, sequence_no) values ('CANCELLED', 'Cancelled', 90);

commit;
