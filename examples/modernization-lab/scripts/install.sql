-- =============================================================================
-- LOM modernization lab -- full install
-- Run as the target schema (create the schema/user yourself first; this
-- script does not create users, grants, or tablespaces).
--
-- Usage (SQL*Plus or SQLcl):
--   sqlplus lom_lab/<your_password>@//localhost:1521/freepdb1 @install.sql
--
-- Never hardcode a real password into this file or any script that calls
-- it -- connect interactively or via a wallet/credential store you manage
-- outside this repo.
--
-- Order matters below because of foreign keys (see the "references" grep
-- across database/ddl/*.sql that this order is derived from) and because
-- every package BODY must compile after every package SPEC exists (Oracle
-- resolves cross-package body calls, including the mutual
-- lom_order_api <-> lom_approval_api calls documented in LOM-MOD-003,
-- against specs -- so spec order doesn't matter, only spec-before-body).
-- =============================================================================

set define off
set echo on
whenever sqlerror continue

-- 1. Sequences (no dependencies)
@../database/sequences/lom_sequences.sql

-- 2. Tables, in FK dependency order
@../database/ddl/lom_lookup_tables.sql
@../database/ddl/lom_customers.sql
@../database/ddl/lom_products_inventory.sql
@../database/ddl/lom_orders.sql
@../database/ddl/lom_order_lines.sql
@../database/ddl/lom_approvals.sql
@../database/ddl/lom_shipments.sql
@../database/ddl/lom_audit_log.sql

-- 3. Views (Forms/APEX query data sources)
@../database/views/lom_views.sql

-- 4. Package specs (all of them, before any body)
@../database/packages/lom_audit_api.pks
@../database/packages/lom_customer_api.pks
@../database/packages/lom_inventory_api.pks
@../database/packages/lom_approval_api.pks
@../database/packages/lom_order_api.pks

-- 5. Package bodies (order no longer matters; all specs already exist)
@../database/packages/lom_audit_api.pkb
@../database/packages/lom_customer_api.pkb
@../database/packages/lom_inventory_api.pkb
@../database/packages/lom_approval_api.pkb
@../database/packages/lom_order_api.pkb

-- 6. Confirm nothing is left INVALID
select object_type, object_name, status
from user_objects
where status != 'VALID'
order by object_type, object_name;

prompt Install complete. If the query above returned rows, recompile them
prompt (e.g. "alter package <name> compile body;") and re-check before seeding.
prompt Run seed.sql next, then verify.sql.
