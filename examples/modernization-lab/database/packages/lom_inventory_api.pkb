create or replace package body lom_inventory_api as

    function get_available_qty(
        p_product_id     in lom_inventory.product_id%type,
        p_warehouse_code in lom_inventory.warehouse_code%type
    ) return number is
        v_available number;
    begin
        select quantity_available into v_available
          from lom_inventory
         where product_id = p_product_id
           and warehouse_code = p_warehouse_code;
        return v_available;
    exception
        when no_data_found then
            return 0;
    end get_available_qty;

    function validate_quantity(
        p_product_id     in lom_inventory.product_id%type,
        p_warehouse_code in lom_inventory.warehouse_code%type,
        p_quantity       in number
    ) return varchar2 is
        v_available number;
    begin
        v_available := get_available_qty(p_product_id, p_warehouse_code);
        if p_quantity > v_available then
            return 'Only ' || v_available
                || ' unit(s) available in warehouse ' || p_warehouse_code;
        end if;
        return null;
    end validate_quantity;

    procedure reserve_quantity(
        p_product_id     in lom_inventory.product_id%type,
        p_warehouse_code in lom_inventory.warehouse_code%type,
        p_quantity       in number
    ) is
    begin
        update lom_inventory
           set quantity_reserved = quantity_reserved + p_quantity,
               last_updated = sysdate
         where product_id = p_product_id
           and warehouse_code = p_warehouse_code
           and quantity_on_hand - quantity_reserved >= p_quantity;

        if sql%rowcount = 0 then
            raise_application_error(
                gc_err_insufficient_stock,
                'LOM_INVENTORY_API.reserve_quantity: insufficient stock for product '
                    || p_product_id || ' in warehouse ' || p_warehouse_code
            );
        end if;
    end reserve_quantity;

    procedure release_quantity(
        p_product_id     in lom_inventory.product_id%type,
        p_warehouse_code in lom_inventory.warehouse_code%type,
        p_quantity       in number
    ) is
    begin
        update lom_inventory
           set quantity_reserved = greatest(quantity_reserved - p_quantity, 0),
               last_updated = sysdate
         where product_id = p_product_id
           and warehouse_code = p_warehouse_code;
    end release_quantity;

    procedure adjust_quantity(
        p_product_id     in lom_inventory.product_id%type,
        p_warehouse_code in lom_inventory.warehouse_code%type,
        p_delta          in number,
        p_changed_by     in varchar2 default user
    ) is
        v_old_on_hand lom_inventory.quantity_on_hand%type;
        v_new_on_hand lom_inventory.quantity_on_hand%type;
    begin
        select quantity_on_hand into v_old_on_hand
          from lom_inventory
         where product_id = p_product_id
           and warehouse_code = p_warehouse_code
           for update;

        v_new_on_hand := v_old_on_hand + p_delta;

        if v_new_on_hand < 0 then
            raise_application_error(
                gc_err_insufficient_stock,
                'LOM_INVENTORY_API.adjust_quantity: resulting on-hand quantity would be negative'
            );
        end if;

        update lom_inventory
           set quantity_on_hand = v_new_on_hand,
               last_updated = sysdate
         where product_id = p_product_id
           and warehouse_code = p_warehouse_code;

        lom_audit_api.log_event(
            p_entity_name => 'INVENTORY',
            p_entity_id   => p_product_id || '/' || p_warehouse_code,
            p_action      => 'QUANTITY_ADJUSTMENT',
            p_old_value   => to_char(v_old_on_hand),
            p_new_value   => to_char(v_new_on_hand),
            p_changed_by  => p_changed_by
        );
    end adjust_quantity;

    function default_warehouse return lom_warehouses.warehouse_code%type is
        v_warehouse_code lom_warehouses.warehouse_code%type;
    begin
        select warehouse_code into v_warehouse_code
          from lom_warehouses
         where is_default = 'Y'
           and rownum = 1;
        return v_warehouse_code;
    exception
        when no_data_found then
            raise_application_error(
                gc_err_no_default_warehouse,
                'LOM_INVENTORY_API.default_warehouse: no warehouse is flagged as default'
            );
    end default_warehouse;

end lom_inventory_api;
/
