-- =============================================================================
-- LOM modernization lab -- full install
-- Run as the target schema (create the schema/user yourself first; this
-- script does not create users, grants, or tablespaces).
--
-- Usage (SQL*Plus or SQLcl) -- run it WITH THIS DIRECTORY AS THE CURRENT
-- DIRECTORY, because the nested paths below are resolved against the
-- current directory, not against this file:
--   cd scripts
--   sqlplus lom_lab/<your_password>@//localhost:1521/freepdb1 @install.sql
--
-- Measured on SQL*Plus 23.26.3.0.0 (Windows): @@ behaves like @ there, so
-- invoking this as @scripts/install.sql from the lab root -- or by absolute
-- path from anywhere else -- makes all 40 nested scripts fail to open with
-- SP2-0310. Step 6 below now fails loudly when that happens; it used to
-- report success.
--
-- Stops at the first SQL error and rolls back (whenever sqlerror exit
-- failure rollback). Two kinds of failure are NOT SQL errors and slip past
-- that: a package body that compiles WITH ERRORS, and a nested script that
-- cannot be opened (SP2-0310). So each body is followed by SHOW ERRORS, and
-- step 6 asserts both that the expected objects exist and that none of them
-- is INVALID -- a pipeline run cannot pass with a broken package, nor with
-- an install that silently created nothing.
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
whenever sqlerror exit failure rollback

-- 1. Sequences (no dependencies)
@@../database/sequences/lom_sequences.sql

-- 2. Tables, in FK dependency order
@@../database/ddl/lom_lookup_tables.sql
@@../database/ddl/lom_customers.sql
@@../database/ddl/lom_products_inventory.sql
@@../database/ddl/lom_orders.sql
@@../database/ddl/lom_order_lines.sql
@@../database/ddl/lom_approvals.sql
@@../database/ddl/lom_shipments.sql
@@../database/ddl/lom_audit_log.sql

-- 3. Views (Forms/APEX query data sources)
@@../database/views/lom_views.sql

-- 4. Package specs (all of them, before any body)
@@../database/packages/lom_audit_api.pks
@@../database/packages/lom_customer_api.pks
@@../database/packages/lom_inventory_api.pks
@@../database/packages/lom_approval_api.pks
@@../database/packages/lom_order_api.pks

-- 5. Package bodies (order no longer matters; all specs already exist)
@@../database/packages/lom_audit_api.pkb
show errors
@@../database/packages/lom_customer_api.pkb
show errors
@@../database/packages/lom_inventory_api.pkb
show errors
@@../database/packages/lom_approval_api.pkb
show errors
@@../database/packages/lom_order_api.pkb
show errors

-- 6. Confirm the install actually happened, then that nothing is INVALID.
-- Both halves are needed: "nothing is INVALID" is vacuously true of an
-- empty schema, so a run in which every @@ above failed with SP2-0310 used
-- to print "Install complete" and exit 0.
select object_type, object_name, status
from user_objects
where status != 'VALID'
order by object_type, object_name;

declare
    type t_counts is table of number index by varchar2(30);
    v_expected t_counts;
    v_type     varchar2(30);
    v_actual   number;
    v_report   varchar2(500);
    v_invalid  number;
begin
    -- Derived from the @@ list in steps 1-5 above. Adding an object to this
    -- script means updating the matching number here; that coupling is the
    -- point of the check. Indexes are deliberately not counted: most of them
    -- are created implicitly by constraints, not by a line in this script.
    v_expected('SEQUENCE')     := 6;
    v_expected('TABLE')        := 11;
    v_expected('VIEW')         := 2;
    v_expected('PACKAGE')      := 5;
    v_expected('PACKAGE BODY') := 5;

    v_type := v_expected.first;
    while v_type is not null loop
        select count(*) into v_actual
          from user_objects
         where object_type = v_type;
        if v_actual != v_expected(v_type) then
            v_report := v_report || v_type || ': expected '
                     || v_expected(v_type) || ', found ' || v_actual || '. ';
        end if;
        v_type := v_expected.next(v_type);
    end loop;

    if v_report is not null then
        raise_application_error(-20002,
            'INSTALL FAILED: ' || v_report || 'If the counts are all zero, '
            || 'the nested scripts could not be opened (look for SP2-0310 '
            || 'above) -- run this from the scripts/ directory. If the schema '
            || 'was not empty, reset.sql first.');
    end if;

    select count(*) into v_invalid from user_objects where status != 'VALID';
    if v_invalid > 0 then
        raise_application_error(-20001,
            'INSTALL FAILED: ' || v_invalid || ' object(s) INVALID -- see the '
            || 'listing and SHOW ERRORS output above');
    end if;
end;
/

prompt Install complete: every object in the schema is VALID.
prompt Run seed.sql next, then verify.sql.
