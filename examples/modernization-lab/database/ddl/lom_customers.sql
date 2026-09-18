-- =============================================================================
-- LOM_CUSTOMERS
-- FACT: STATUS gates new-order creation (LOM_CUSTOMER_API.can_place_order,
-- called from ORDERS.fmb / CUSTOMER_ID.WHEN-VALIDATE-ITEM -- LOM-MOD-019).
-- CREDIT_LIMIT >= 0 is enforced here AND re-checked in CUSTOMERS.fmb's
-- WHEN-VALIDATE-ITEM on CREDIT_LIMIT -- an intentional duplicate, see
-- LOM-MOD-010 / docs/modernization-challenges.md.
-- =============================================================================

create table lom_customers (
    customer_id         number(10)      not null,
    customer_name       varchar2(200)   not null,
    customer_type_code  varchar2(10)    not null,
    status              varchar2(10)    default 'ACTIVE' not null,
    credit_limit        number(12,2)    not null,
    email               varchar2(200),
    phone               varchar2(40),
    created_by          varchar2(30)    default user not null,
    created_date        date            default sysdate not null,
    updated_by          varchar2(30),
    updated_date        date,
    constraint pk_lom_customers primary key (customer_id),
    constraint fk_lom_cust_type foreign key (customer_type_code)
        references lom_customer_types (customer_type_code),
    constraint ck_lom_cust_status check (status in ('ACTIVE','INACTIVE')),
    constraint ck_lom_cust_credit check (credit_limit >= 0)
);

comment on table lom_customers is 'Customer master. FACT: inactive customers cannot receive new orders (rule lives in LOM_CUSTOMER_API.can_place_order and is duplicated as a UI gate in CUSTOMERS.fmb -- see business-rules.md BR-001).';

create index ix_lom_customers_status on lom_customers (status);
create index ix_lom_customers_type on lom_customers (customer_type_code);
