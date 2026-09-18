-- =============================================================================
-- LOM_APPROVALS
-- FACT: rows in this table are only ever expected to be written through
-- LOM_APPROVAL_API (create_approval_request / approve / reject). The
-- as-built APPROVALS.fmb worklist screen does NOT do this -- its Approve and
-- Reject buttons issue raw UPDATE statements directly against this table and
-- against LOM_ORDERS in the same trigger (LOM-MOD-041/LOM-MOD-042, this
-- lab's flagship "why direct Forms-to-APEX translation is dangerous" case).
-- =============================================================================

create table lom_approvals (
    approval_id     number(10)      not null,
    order_id        number(10)      not null,
    requested_by    varchar2(30)    not null,
    requested_date  date            default sysdate not null,
    status          varchar2(20)    default 'PENDING' not null,
    approver        varchar2(30),
    approval_date   date,
    comments        varchar2(2000),
    constraint pk_lom_approvals primary key (approval_id),
    constraint fk_lom_appr_order foreign key (order_id)
        references lom_orders (order_id),
    constraint ck_lom_appr_status check (status in ('PENDING','APPROVED','REJECTED'))
);

comment on table lom_approvals is 'Approval worklist entries for orders whose total exceeds the configured approval threshold (LOM_ORDER_API.gc_approval_threshold). See LOM-MOD-029..LOM-MOD-032.';

create index ix_lom_approvals_order on lom_approvals (order_id);
create index ix_lom_approvals_status on lom_approvals (status);
