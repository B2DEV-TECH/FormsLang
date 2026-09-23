-- Synthetic source only: FormsLang never executes this DDL during assessment.
create table work_items (
    item_id number primary key,
    status varchar2(20) not null,
    gross number,
    closed_by varchar2(30)
);
create table audit_notes (
    note_id number primary key,
    item_id number references work_items(item_id),
    note varchar2(400)
);
create table staging_rows (
    row_id number primary key
);
