-- =============================================================================
-- LOM seed data -- illustrative audit trail
-- FACT: audit_id values are fixed. These rows illustrate the shape of what
-- LOM_AUDIT_API.log_event writes; they are backfilled here for the seeded
-- orders rather than produced by actually replaying the API (the seed
-- inserts orders directly, per the note in 04_orders_and_lines.sql).
-- =============================================================================

insert into lom_audit_log (audit_id, entity_name, entity_id, action, old_value, new_value, changed_by, changed_date)
values (1, 'ORDER', '5006', 'STATUS_CHANGE', 'DRAFT', 'SUBMITTED', 'SALES_APP', date '2026-08-16');

insert into lom_audit_log (audit_id, entity_name, entity_id, action, old_value, new_value, changed_by, changed_date)
values (2, 'ORDER', '5006', 'STATUS_CHANGE', 'SUBMITTED', 'APPROVED', 'SALES_APP', date '2026-08-16');

insert into lom_audit_log (audit_id, entity_name, entity_id, action, old_value, new_value, changed_by, changed_date)
values (3, 'ORDER', '5006', 'STATUS_CHANGE', 'APPROVED', 'RELEASED', 'SALES_APP', date '2026-08-16');

insert into lom_audit_log (audit_id, entity_name, entity_id, action, old_value, new_value, changed_by, changed_date)
values (4, 'ORDER', '5006', 'STATUS_CHANGE', 'RELEASED', 'SHIPPED', 'SALES_APP', date '2026-08-17');

insert into lom_audit_log (audit_id, entity_name, entity_id, action, old_value, new_value, changed_by, changed_date, notes)
values (5, 'APPROVAL', '5008', 'REJECTED', 'PENDING', 'REJECTED', 'CREDIT_MGR', date '2026-08-19', 'Unusual order volume for this customer; requesting confirmed PO before resubmission.');

insert into lom_audit_log (audit_id, entity_name, entity_id, action, old_value, new_value, changed_by, changed_date)
values (6, 'CUSTOMER', '1004', 'STATUS_CHANGE', 'ACTIVE', 'INACTIVE', 'CREDIT_MGR', date '2026-08-01');

commit;
