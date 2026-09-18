-- =============================================================================
-- LOM_AUDIT_API -- shared audit-trail writer.
-- DESIGN DECISION: this is the one place LOM_AUDIT_LOG should be written
-- from. Every other package calls it; OM_SHARED.pll's log_action does not
-- (it inserts directly) -- see LOM-MOD-039. This package itself is a
-- PRESERVE case: already correctly centralized, nothing to move.
-- =============================================================================
create or replace package lom_audit_api as

    procedure log_event(
        p_entity_name in lom_audit_log.entity_name%type,
        p_entity_id   in lom_audit_log.entity_id%type,
        p_action      in lom_audit_log.action%type,
        p_old_value   in lom_audit_log.old_value%type default null,
        p_new_value   in lom_audit_log.new_value%type default null,
        p_notes       in lom_audit_log.notes%type default null,
        p_changed_by  in varchar2 default user
    );

end lom_audit_api;
/
