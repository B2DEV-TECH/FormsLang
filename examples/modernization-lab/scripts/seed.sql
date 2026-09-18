-- =============================================================================
-- LOM modernization lab -- seed data
-- Run after install.sql, against the same schema.
--
-- Usage:
--   sqlplus lom_lab/<your_password>@//localhost:1521/freepdb1 @seed.sql
--
-- Order matters: 01-06 insert fixed, hand-picked primary keys (not
-- sequence-generated -- see database/seed/07_align_sequences.sql for why),
-- and 04_orders_and_lines.sql inserts order/order-line rows directly
-- rather than through LOM_ORDER_API, so every package procedure's own
-- validation (submit_order, transition_status, etc.) is intentionally
-- bypassed for seeding -- these rows represent orders already in-flight
-- at various lifecycle stages, not orders freshly created through the API.
-- 07 must run last, once, to realign sequences with the fixed IDs just
-- inserted so the very next LOM_ORDER_API.submit_order (or any other
-- nextval-based insert) does not collide with a seeded row.
-- =============================================================================

set define off
set echo on
whenever sqlerror continue

@../database/seed/01_lookup_data.sql
@../database/seed/02_customers.sql
@../database/seed/03_products_inventory.sql
@../database/seed/04_orders_and_lines.sql
@../database/seed/05_approvals_and_shipments.sql
@../database/seed/06_audit_log.sql
@../database/seed/07_align_sequences.sql

prompt Seed complete. Run verify.sql to sanity-check row counts and the
prompt known fixtures (e.g. order 5004's deliberate under-stock condition).
