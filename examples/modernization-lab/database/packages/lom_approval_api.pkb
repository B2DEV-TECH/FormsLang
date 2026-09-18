create or replace package body lom_approval_api as

    procedure create_approval_request(
        p_order_id     in lom_orders.order_id%type,
        p_requested_by in varchar2 default user
    ) is
    begin
        insert into lom_approvals (
            approval_id, order_id, status, requested_by, requested_date
        ) values (
            lom_approval_id_seq.nextval, p_order_id, 'PENDING', p_requested_by, sysdate
        );

        lom_audit_api.log_event(
            p_entity_name => 'APPROVAL',
            p_entity_id   => to_char(p_order_id),
            p_action      => 'REQUESTED',
            p_new_value   => 'PENDING',
            p_changed_by  => p_requested_by
        );
    end create_approval_request;

    procedure approve(
        p_approval_id in lom_approvals.approval_id%type,
        p_approver    in varchar2 default user,
        p_comments    in varchar2 default null
    ) is
        v_order_id lom_approvals.order_id%type;
    begin
        select order_id into v_order_id
          from lom_approvals
         where approval_id = p_approval_id
           for update;

        update lom_approvals
           set status = 'APPROVED',
               approver = p_approver,
               comments = p_comments,
               approval_date = sysdate
         where approval_id = p_approval_id;

        lom_audit_api.log_event(
            p_entity_name => 'APPROVAL',
            p_entity_id   => to_char(p_approval_id),
            p_action      => 'APPROVED',
            p_old_value   => 'PENDING',
            p_new_value   => 'APPROVED',
            p_notes       => p_comments,
            p_changed_by  => p_approver
        );

        lom_order_api.transition_status(v_order_id, 'APPROVED', p_approver);
    exception
        when no_data_found then
            raise_application_error(
                gc_err_approval_not_found,
                'LOM_APPROVAL_API.approve: approval '
                    || p_approval_id || ' not found'
            );
    end approve;

    procedure reject(
        p_approval_id in lom_approvals.approval_id%type,
        p_approver    in varchar2 default user,
        p_comments    in varchar2
    ) is
        v_order_id lom_approvals.order_id%type;
    begin
        if p_comments is null then
            raise_application_error(
                gc_err_comments_required,
                'LOM_APPROVAL_API.reject: a rejection reason is required'
            );
        end if;

        select order_id into v_order_id
          from lom_approvals
         where approval_id = p_approval_id
           for update;

        update lom_approvals
           set status = 'REJECTED',
               approver = p_approver,
               comments = p_comments,
               approval_date = sysdate
         where approval_id = p_approval_id;

        lom_audit_api.log_event(
            p_entity_name => 'APPROVAL',
            p_entity_id   => to_char(p_approval_id),
            p_action      => 'REJECTED',
            p_old_value   => 'PENDING',
            p_new_value   => 'REJECTED',
            p_notes       => p_comments,
            p_changed_by  => p_approver
        );

        lom_order_api.transition_status(v_order_id, 'REJECTED', p_approver);
    exception
        when no_data_found then
            raise_application_error(
                gc_err_approval_not_found,
                'LOM_APPROVAL_API.reject: approval '
                    || p_approval_id || ' not found'
            );
    end reject;

end lom_approval_api;
/
