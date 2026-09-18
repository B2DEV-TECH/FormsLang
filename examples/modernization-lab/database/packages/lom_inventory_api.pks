-- =============================================================================
-- LOM_INVENTORY_API
-- validate_quantity and get_available_qty already exist here but ORDERS.fmb
-- bypasses both with inline SELECTs (LOM-MOD-025, LOM-MOD-026) -- this
-- lab's other flagship case: the API exists, Forms just never calls it,
-- alongside default_warehouse (LOM-MOD-018).
-- =============================================================================
create or replace package lom_inventory_api as

    gc_err_insufficient_stock   constant number := -20011;
    gc_err_no_default_warehouse constant number := -20012;

    function get_available_qty(
        p_product_id     in lom_inventory.product_id%type,
        p_warehouse_code in lom_inventory.warehouse_code%type
    ) return number;

    -- Returns NULL when the quantity is acceptable, or a human-readable
    -- error message otherwise. Deliberately not a BOOLEAN or exception so
    -- the same function can drive both a PL/SQL check and an APEX
    -- validation error message without a second code path.
    function validate_quantity(
        p_product_id     in lom_inventory.product_id%type,
        p_warehouse_code in lom_inventory.warehouse_code%type,
        p_quantity       in number
    ) return varchar2;

    procedure reserve_quantity(
        p_product_id     in lom_inventory.product_id%type,
        p_warehouse_code in lom_inventory.warehouse_code%type,
        p_quantity       in number
    );

    procedure release_quantity(
        p_product_id     in lom_inventory.product_id%type,
        p_warehouse_code in lom_inventory.warehouse_code%type,
        p_quantity       in number
    );

    procedure adjust_quantity(
        p_product_id     in lom_inventory.product_id%type,
        p_warehouse_code in lom_inventory.warehouse_code%type,
        p_delta          in number,
        p_changed_by     in varchar2 default user
    );

    function default_warehouse return lom_warehouses.warehouse_code%type;

end lom_inventory_api;
/
