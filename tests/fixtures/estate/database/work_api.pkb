create or replace package body work_api as
    procedure close_item(p_item_id in number) is
        v_status varchar2(20);
    begin
        select status into v_status from work_items where item_id = p_item_id for update;
        if v_status = 'CLOSED' then
            raise_application_error(-20001, 'Item already closed');
        end if;
        update work_items set status = 'CLOSED' where item_id = p_item_id;
        if sql%rowcount = 0 then
            raise_application_error(-20002, 'Item not found');
        end if;
    end close_item;

    function net_amount(p_gross in number) return number is
    begin
        return p_gross * 0.9 - 5;
    end net_amount;

    procedure log_note(p_item_id in number, p_note in varchar2) is
    begin
        insert into audit_notes (note_id, item_id, note) values (p_item_id, p_item_id, p_note);
    end log_note;
end work_api;
/
