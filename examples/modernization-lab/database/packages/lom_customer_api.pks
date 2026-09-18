-- =============================================================================
-- LOM_CUSTOMER_API
-- can_place_order is the canonical gate for "inactive customers cannot place
-- new orders" (BR-001); has_open_orders backs the CUSTOMERS.fmb rule that
-- blocks inactivating a customer with open orders (LOM-MOD-011, HIGH risk).
-- =============================================================================
create or replace package lom_customer_api as

    gc_err_customer_not_found constant number := -20001;
    gc_err_invalid_status     constant number := -20002;
    gc_err_negative_credit    constant number := -20003;
    gc_err_open_orders        constant number := -20004;

    function get_status(
        p_customer_id in lom_customers.customer_id%type
    ) return lom_customers.status%type;

    -- Returns Y/N (not BOOLEAN): called directly from Forms triggers,
    -- which historically bind function results to VARCHAR2 form items.
    function can_place_order(
        p_customer_id in lom_customers.customer_id%type
    ) return varchar2;

    function has_open_orders(
        p_customer_id in lom_customers.customer_id%type
    ) return varchar2;

    procedure change_status(
        p_customer_id in lom_customers.customer_id%type,
        p_new_status  in lom_customers.status%type,
        p_changed_by  in varchar2 default user,
        p_reason      in varchar2 default null
    );

    procedure set_credit_limit(
        p_customer_id in lom_customers.customer_id%type,
        p_new_limit   in lom_customers.credit_limit%type,
        p_changed_by  in varchar2 default user
    );

end lom_customer_api;
/
