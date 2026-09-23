create or replace package work_api as
    procedure close_item(p_item_id in number);
    function net_amount(p_gross in number) return number;
    procedure log_note(p_item_id in number, p_note in varchar2);
end work_api;
/
