-- =============================================================================
-- LOM seed data -- customers
-- FACT: customer_id values are fixed (not sequence-generated) so the rest of
-- the seed data, expected/modernization-ground-truth.json examples, and any
-- documentation can reference them stably. See docs/data-model.md.
-- FIXTURE: 1004 is seeded INACTIVE on purpose, to exercise the
-- LOM_CUSTOMER_API.can_place_order gate (LOM-MOD-019).
-- =============================================================================

insert into lom_customers (customer_id, customer_name, customer_type_code, status, credit_limit, email, phone)
values (1001, 'Acme Retail Corp', 'RETAIL', 'ACTIVE', 15000, 'orders@acmeretail.example', '555-0101');

insert into lom_customers (customer_id, customer_name, customer_type_code, status, credit_limit, email, phone)
values (1002, 'Blue Ridge Wholesale', 'WHOLESALE', 'ACTIVE', 75000, 'purchasing@blueridge.example', '555-0102');

insert into lom_customers (customer_id, customer_name, customer_type_code, status, credit_limit, email, phone)
values (1003, 'Cedar Point Holdings', 'VIP', 'ACTIVE', 250000, 'ap@cedarpoint.example', '555-0103');

insert into lom_customers (customer_id, customer_name, customer_type_code, status, credit_limit, email, phone)
values (1004, 'Dormant Industries LLC', 'RETAIL', 'INACTIVE', 5000, 'accounts@dormantind.example', '555-0104');

insert into lom_customers (customer_id, customer_name, customer_type_code, status, credit_limit, email, phone)
values (1005, 'Evergreen Supply Co', 'WHOLESALE', 'ACTIVE', 50000, 'orders@evergreensupply.example', '555-0105');

insert into lom_customers (customer_id, customer_name, customer_type_code, status, credit_limit, email, phone)
values (1006, 'Frontier Trading Ltd', 'RETAIL', 'ACTIVE', 8000, 'info@frontiertrading.example', '555-0106');

commit;
