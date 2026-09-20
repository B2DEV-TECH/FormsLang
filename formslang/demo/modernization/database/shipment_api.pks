create or replace package shipment_api as
    function current_state(p_shipment_id in number) return varchar2;
    procedure approve(p_id in number, p_approved_by in varchar2 default user);
end shipment_api;
/
