create or replace package body lom_customer_api as

    function get_status(
        p_customer_id in lom_customers.customer_id%type
    ) return lom_customers.status%type is
        v_status lom_customers.status%type;
    begin
        select status into v_status
          from lom_customers
         where customer_id = p_customer_id;
        return v_status;
    exception
        when no_data_found then
            raise_application_error(
                gc_err_customer_not_found,
                'LOM_CUSTOMER_API.get_status: customer '
                    || p_customer_id || ' not found'
            );
    end get_status;

    function can_place_order(
        p_customer_id in lom_customers.customer_id%type
    ) return varchar2 is
    begin
        if get_status(p_customer_id) = 'ACTIVE' then
            return 'Y';
        else
            return 'N';
        end if;
    end can_place_order;

    function has_open_orders(
        p_customer_id in lom_customers.customer_id%type
    ) return varchar2 is
        v_count pls_integer;
    begin
        select count(*) into v_count
          from lom_orders
         where customer_id = p_customer_id
           and status not in ('SHIPPED', 'REJECTED', 'CANCELLED');
        return case when v_count > 0 then 'Y' else 'N' end;
    end has_open_orders;

    procedure change_status(
        p_customer_id in lom_customers.customer_id%type,
        p_new_status  in lom_customers.status%type,
        p_changed_by  in varchar2 default user,
        p_reason      in varchar2 default null
    ) is
        v_old_status lom_customers.status%type;
    begin
        if p_new_status not in ('ACTIVE', 'INACTIVE') then
            raise_application_error(
                gc_err_invalid_status,
                'LOM_CUSTOMER_API.change_status: invalid status '
                    || p_new_status
            );
        end if;

        v_old_status := get_status(p_customer_id);

        if p_new_status = 'INACTIVE' and has_open_orders(p_customer_id) = 'Y' then
            raise_application_error(
                gc_err_open_orders,
                'LOM_CUSTOMER_API.change_status: customer '
                    || p_customer_id
                    || ' has open orders and cannot be inactivated'
            );
        end if;

        update lom_customers
           set status = p_new_status,
               updated_by = p_changed_by,
               updated_date = sysdate
         where customer_id = p_customer_id;

        lom_audit_api.log_event(
            p_entity_name => 'CUSTOMER',
            p_entity_id   => to_char(p_customer_id),
            p_action      => 'STATUS_CHANGE',
            p_old_value   => v_old_status,
            p_new_value   => p_new_status,
            p_notes       => p_reason,
            p_changed_by  => p_changed_by
        );
    end change_status;

    procedure set_credit_limit(
        p_customer_id in lom_customers.customer_id%type,
        p_new_limit   in lom_customers.credit_limit%type,
        p_changed_by  in varchar2 default user
    ) is
        v_old_limit lom_customers.credit_limit%type;
    begin
        if p_new_limit < 0 then
            raise_application_error(
                gc_err_negative_credit,
                'LOM_CUSTOMER_API.set_credit_limit: credit limit cannot be negative'
            );
        end if;

        select credit_limit into v_old_limit
          from lom_customers
         where customer_id = p_customer_id;

        update lom_customers
           set credit_limit = p_new_limit,
               updated_by = p_changed_by,
               updated_date = sysdate
         where customer_id = p_customer_id;

        lom_audit_api.log_event(
            p_entity_name => 'CUSTOMER',
            p_entity_id   => to_char(p_customer_id),
            p_action      => 'CREDIT_LIMIT_CHANGE',
            p_old_value   => to_char(v_old_limit),
            p_new_value   => to_char(p_new_limit),
            p_changed_by  => p_changed_by
        );
    exception
        when no_data_found then
            raise_application_error(
                gc_err_customer_not_found,
                'LOM_CUSTOMER_API.set_credit_limit: customer '
                    || p_customer_id || ' not found'
            );
    end set_credit_limit;

end lom_customer_api;
/
