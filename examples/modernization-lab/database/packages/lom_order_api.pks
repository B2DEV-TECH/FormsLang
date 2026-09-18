-- =============================================================================
-- LOM_ORDER_API -- order totals, approval threshold and the status
-- transition matrix. transition_status is this lab's CRITICAL case
-- (LOM-MOD-002): the matrix is correct today, but an automated conversion
-- that simplifies or drops it could allow an order to be released or
-- shipped without ever being approved.
-- =============================================================================
create or replace package lom_order_api as

    -- DESIGN DECISION (intentional legacy smell): business constants
    -- hardcoded in package spec rather than a configuration table.
    -- See LOM-MOD-001 (REFACTOR candidate).
    gc_tax_rate            constant number := 0.08;
    gc_approval_threshold  constant number := 5000;

    gc_err_invalid_transition constant number := -20021;
    gc_err_order_not_found    constant number := -20022;

    function calc_line_total(
        p_quantity   in number,
        p_unit_price in number,
        p_discount   in number default 0
    ) return number;

    procedure recalc_order_totals(
        p_order_id in lom_orders.order_id%type
    );

    function requires_approval(
        p_total_amount in number
    ) return varchar2;

    procedure transition_status(
        p_order_id   in lom_orders.order_id%type,
        p_new_status in lom_orders.status%type,
        p_changed_by in varchar2 default user
    );

    procedure submit_order(
        p_order_id in lom_orders.order_id%type
    );

    procedure release_order(
        p_order_id in lom_orders.order_id%type
    );

    procedure ship_order(
        p_order_id in lom_orders.order_id%type
    );

end lom_order_api;
/
