-- =============================================================================
-- LOM seed data -- align sequences with seeded fixed IDs
-- FACT: every table above is seeded with fixed, hand-picked primary keys
-- (for stable cross-references in docs and tests) rather than
-- <seq>.nextval, so the sequences still start at their original START WITH
-- value after seeding. Any package call that inserts a new row via nextval
-- (e.g. LOM_AUDIT_API.log_event, LOM_APPROVAL_API.create_approval_request)
-- would then collide with an existing seeded primary key.
-- DESIGN DECISION: realign every sequence to (max seeded id + 1) here, once,
-- right after seeding, using the standard "burn nextval up to the target"
-- technique -- Oracle sequences have no direct SET. Idempotent: running this
-- twice in a row is a no-op (v_gap <= 0).
-- =============================================================================

declare
    procedure align(p_sequence in varchar2, p_table in varchar2, p_pk_column in varchar2) is
        v_max_id  number;
        v_current number;
        v_gap     number;
    begin
        execute immediate
            'select nvl(max(' || p_pk_column || '), 0) from ' || p_table
            into v_max_id;

        execute immediate 'select ' || p_sequence || '.nextval from dual' into v_current;

        v_gap := v_max_id - v_current;
        if v_gap > 0 then
            execute immediate 'alter sequence ' || p_sequence || ' increment by ' || v_gap;
            execute immediate 'select ' || p_sequence || '.nextval from dual' into v_current;
            execute immediate 'alter sequence ' || p_sequence || ' increment by 1';
        end if;

        dbms_output.put_line(p_sequence || ': next value will be ' || (v_current + 1) ||
            ' (max seeded ' || p_pk_column || ' in ' || p_table || ' = ' || v_max_id || ')');
    end align;
begin
    align('lom_customer_id_seq', 'lom_customers', 'customer_id');
    align('lom_product_id_seq', 'lom_products', 'product_id');
    align('lom_order_id_seq', 'lom_orders', 'order_id');
    align('lom_approval_id_seq', 'lom_approvals', 'approval_id');
    align('lom_shipment_id_seq', 'lom_shipments', 'shipment_id');
    align('lom_audit_id_seq', 'lom_audit_log', 'audit_id');
end;
/
