-- =============================================================================
-- LOM_APPROVAL_API
-- The as-built APPROVALS.fmb worklist does not call this package: its
-- Approve/Reject buttons update LOM_APPROVALS and LOM_ORDERS directly in one
-- WHEN-BUTTON-PRESSED trigger each (LOM-MOD-041, LOM-MOD-042). This package
-- is what a modernized implementation should call instead.
-- =============================================================================
create or replace package lom_approval_api as

    gc_err_approval_not_found constant number := -20031;
    gc_err_comments_required  constant number := -20032;

    procedure create_approval_request(
        p_order_id     in lom_orders.order_id%type,
        p_requested_by in varchar2 default user
    );

    procedure approve(
        p_approval_id in lom_approvals.approval_id%type,
        p_approver    in varchar2 default user,
        p_comments    in varchar2 default null
    );

    -- Rejection always requires a reason (p_comments mandatory) -- a real
    -- business rule, not a UI nicety.
    procedure reject(
        p_approval_id in lom_approvals.approval_id%type,
        p_approver    in varchar2 default user,
        p_comments    in varchar2
    );

end lom_approval_api;
/
