-- Synthetic source only: FormsLang never executes this DDL during assessment.
create table customers (
    customer_id number primary key,
    name varchar2(120) not null
);
create table shipments (
    shipment_id number primary key,
    customer_id number references customers(customer_id),
    state varchar2(20) not null,
    approved_by varchar2(120)
);
