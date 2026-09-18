-- =============================================================================
-- LOM_AUDIT_LOG
-- FACT: this is the single sink all four API packages (via LOM_AUDIT_API)
-- and one Forms trigger (CUSTOMERS.fmb POST-UPDATE) write to. OM_SHARED.pll's
-- log_action instead writes to this table directly, bypassing LOM_AUDIT_API
-- -- see LOM-MOD-039, another instance of "an API already exists but is
-- bypassed".
-- =============================================================================

create table lom_audit_log (
    audit_id        number(10)      not null,
    entity_name     varchar2(30)    not null,
    entity_id       varchar2(60)    not null,
    action          varchar2(30)    not null,
    old_value       varchar2(200),
    new_value       varchar2(200),
    changed_by      varchar2(30)    default user not null,
    changed_date    date            default sysdate not null,
    notes           varchar2(2000),
    constraint pk_lom_audit_log primary key (audit_id)
);

comment on table lom_audit_log is 'Generic, denormalized audit trail. ENTITY_NAME/ENTITY_ID identify the record informally (no FK -- this table intentionally outlives the rows it describes). See LOM_AUDIT_API.log_event.';

create index ix_lom_audit_entity on lom_audit_log (entity_name, entity_id);
create index ix_lom_audit_date on lom_audit_log (changed_date);
