create or replace package body lom_audit_api as

    procedure log_event(
        p_entity_name in lom_audit_log.entity_name%type,
        p_entity_id   in lom_audit_log.entity_id%type,
        p_action      in lom_audit_log.action%type,
        p_old_value   in lom_audit_log.old_value%type default null,
        p_new_value   in lom_audit_log.new_value%type default null,
        p_notes       in lom_audit_log.notes%type default null,
        p_changed_by  in varchar2 default user
    ) is
    begin
        insert into lom_audit_log (
            audit_id, entity_name, entity_id, action,
            old_value, new_value, changed_by, changed_date, notes
        ) values (
            lom_audit_id_seq.nextval, p_entity_name, p_entity_id, p_action,
            p_old_value, p_new_value, p_changed_by, sysdate, p_notes
        );
    end log_event;

end lom_audit_api;
/
