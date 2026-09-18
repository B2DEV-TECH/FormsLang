create or replace package body lom_order_api as

    function calc_line_total(
        p_quantity   in number,
        p_unit_price in number,
        p_discount   in number default 0
    ) return number is
    begin
        return round((p_quantity * p_unit_price) - nvl(p_discount, 0), 2);
    end calc_line_total;

    function requires_approval(
        p_total_amount in number
    ) return varchar2 is
    begin
        return case when p_total_amount > gc_approval_threshold then 'Y' else 'N' end;
    end requires_approval;

    procedure recalc_order_totals(
        p_order_id in lom_orders.order_id%type
    ) is
        v_subtotal lom_orders.subtotal%type;
        v_tax      lom_orders.tax_amount%type;
        v_total    lom_orders.total_amount%type;
    begin
        select nvl(sum(line_total), 0) into v_subtotal
          from lom_order_lines
         where order_id = p_order_id;

        v_tax   := round(v_subtotal * gc_tax_rate, 2);
        v_total := v_subtotal + v_tax;

        update lom_orders
           set subtotal = v_subtotal,
               tax_amount = v_tax,
               total_amount = v_total,
               approval_required = requires_approval(v_total),
               updated_date = sysdate
         where order_id = p_order_id;

        if sql%rowcount = 0 then
            raise_application_error(
                gc_err_order_not_found,
                'LOM_ORDER_API.recalc_order_totals: order '
                    || p_order_id || ' not found'
            );
        end if;
    end recalc_order_totals;

    -- DESIGN DECISION: the allowed-transition matrix is a hardcoded set of
    -- (from, to) pairs rather than a data-driven table. See LOM-MOD-002.
    function is_valid_transition(
        p_from in lom_orders.status%type,
        p_to   in lom_orders.status%type
    ) return boolean is
    begin
        return (p_from = 'DRAFT'             and p_to = 'SUBMITTED')
            or (p_from = 'SUBMITTED'         and p_to = 'PENDING_APPROVAL')
            or (p_from = 'SUBMITTED'         and p_to = 'APPROVED')
            or (p_from = 'PENDING_APPROVAL'  and p_to = 'APPROVED')
            or (p_from = 'PENDING_APPROVAL'  and p_to = 'REJECTED')
            or (p_from = 'APPROVED'          and p_to = 'RELEASED')
            or (p_from = 'RELEASED'          and p_to = 'SHIPPED')
            or (p_from = 'DRAFT'             and p_to = 'CANCELLED')
            or (p_from = 'SUBMITTED'         and p_to = 'CANCELLED')
            or (p_from = 'PENDING_APPROVAL'  and p_to = 'CANCELLED');
    end is_valid_transition;

    procedure transition_status(
        p_order_id   in lom_orders.order_id%type,
        p_new_status in lom_orders.status%type,
        p_changed_by in varchar2 default user
    ) is
        v_current_status lom_orders.status%type;
    begin
        select status into v_current_status
          from lom_orders
         where order_id = p_order_id
           for update;

        if not is_valid_transition(v_current_status, p_new_status) then
            raise_application_error(
                gc_err_invalid_transition,
                'LOM_ORDER_API.transition_status: cannot move order '
                    || p_order_id || ' from ' || v_current_status
                    || ' to ' || p_new_status
            );
        end if;

        update lom_orders
           set status = p_new_status,
               updated_date = sysdate
         where order_id = p_order_id;

        lom_audit_api.log_event(
            p_entity_name => 'ORDER',
            p_entity_id   => to_char(p_order_id),
            p_action      => 'STATUS_CHANGE',
            p_old_value   => v_current_status,
            p_new_value   => p_new_status,
            p_changed_by  => p_changed_by
        );
    exception
        when no_data_found then
            raise_application_error(
                gc_err_order_not_found,
                'LOM_ORDER_API.transition_status: order '
                    || p_order_id || ' not found'
            );
    end transition_status;

    procedure submit_order(
        p_order_id in lom_orders.order_id%type
    ) is
        v_current_status lom_orders.status%type;
        v_needs_approval lom_orders.approval_required%type;
    begin
        select status into v_current_status
          from lom_orders
         where order_id = p_order_id;

        if v_current_status <> 'DRAFT' then
            raise_application_error(
                gc_err_invalid_transition,
                'LOM_ORDER_API.submit_order: order '
                    || p_order_id || ' is not in DRAFT status'
            );
        end if;

        recalc_order_totals(p_order_id);

        select approval_required into v_needs_approval
          from lom_orders
         where order_id = p_order_id;

        transition_status(p_order_id, 'SUBMITTED');

        if v_needs_approval = 'Y' then
            transition_status(p_order_id, 'PENDING_APPROVAL');
            lom_approval_api.create_approval_request(p_order_id);
        else
            transition_status(p_order_id, 'APPROVED');
        end if;
    exception
        when no_data_found then
            raise_application_error(
                gc_err_order_not_found,
                'LOM_ORDER_API.submit_order: order '
                    || p_order_id || ' not found'
            );
    end submit_order;

    procedure release_order(
        p_order_id in lom_orders.order_id%type
    ) is
        v_current_status lom_orders.status%type;
        v_warehouse_code lom_orders.warehouse_code%type;
    begin
        select status, warehouse_code into v_current_status, v_warehouse_code
          from lom_orders
         where order_id = p_order_id;

        if v_current_status <> 'APPROVED' then
            raise_application_error(
                gc_err_invalid_transition,
                'LOM_ORDER_API.release_order: order '
                    || p_order_id || ' is not APPROVED'
            );
        end if;

        for r in (
            select product_id, quantity
              from lom_order_lines
             where order_id = p_order_id
        ) loop
            lom_inventory_api.reserve_quantity(
                p_product_id     => r.product_id,
                p_warehouse_code => v_warehouse_code,
                p_quantity       => r.quantity
            );
        end loop;

        transition_status(p_order_id, 'RELEASED');

        insert into lom_shipments (
            shipment_id, order_id, warehouse_code, status, created_date
        ) values (
            lom_shipment_id_seq.nextval, p_order_id, v_warehouse_code, 'PENDING', sysdate
        );
    exception
        when no_data_found then
            raise_application_error(
                gc_err_order_not_found,
                'LOM_ORDER_API.release_order: order '
                    || p_order_id || ' not found'
            );
    end release_order;

    procedure ship_order(
        p_order_id in lom_orders.order_id%type
    ) is
    begin
        update lom_shipments
           set status = 'SHIPPED',
               shipped_date = sysdate
         where order_id = p_order_id;

        if sql%rowcount = 0 then
            raise_application_error(
                gc_err_order_not_found,
                'LOM_ORDER_API.ship_order: no shipment found for order '
                    || p_order_id
            );
        end if;

        transition_status(p_order_id, 'SHIPPED');
    end ship_order;

end lom_order_api;
/
