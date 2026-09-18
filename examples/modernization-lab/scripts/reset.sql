-- =============================================================================
-- LOM modernization lab -- full reset (DESTRUCTIVE)
-- Drops every object install.sql creates, in reverse dependency order, so
-- install.sql can be re-run cleanly from empty. Safe to run against an
-- empty schema too: each DROP is allowed to error ("does not exist") and
-- execution continues (whenever sqlerror continue) -- errors printed here
-- are expected and not a sign of a broken reset.
--
-- Usage:
--   sqlplus lom_lab/<your_password>@//localhost:1521/freepdb1 @reset.sql
--
-- This drops tables with CASCADE CONSTRAINTS so FK order technically
-- would not matter, but they are still listed in reverse-FK order for
-- readability and so the "does not exist" noise stays minimal on a
-- partially-installed schema.
-- =============================================================================

set define off
set echo on
whenever sqlerror continue

-- Packages
drop package lom_order_api;
drop package lom_approval_api;
drop package lom_inventory_api;
drop package lom_customer_api;
drop package lom_audit_api;

-- Views
drop view lom_approval_worklist_v;
drop view lom_inventory_v;

-- Tables (reverse of install.sql's creation order)
drop table lom_audit_log purge;
drop table lom_shipments purge;
drop table lom_approvals purge;
drop table lom_order_lines purge;
drop table lom_orders purge;
drop table lom_inventory purge;
drop table lom_products purge;
drop table lom_customers purge;
drop table lom_warehouses purge;
drop table lom_order_status purge;
drop table lom_customer_types purge;

-- Sequences
drop sequence lom_customer_id_seq;
drop sequence lom_product_id_seq;
drop sequence lom_order_id_seq;
drop sequence lom_approval_id_seq;
drop sequence lom_shipment_id_seq;
drop sequence lom_audit_id_seq;

prompt Reset complete (see above for any unexpected errors -- "does not
prompt exist" errors are normal on a partially-installed or already-empty
prompt schema). Run install.sql, then seed.sql, to rebuild from scratch.
