-- Intentionally unsafe identity default: a modernization review example,
-- not a production API or deployment recommendation.
create or replace package body shipment_api as
    function current_state(p_shipment_id in number) return varchar2 is
        v_state varchar2(20);
    begin
        select state into v_state from shipments where shipment_id = p_shipment_id;
        return v_state;
    end current_state;

    procedure approve(p_id in number, p_approved_by in varchar2 default user) is
    begin
        update shipments set state = 'APPROVED', approved_by = p_approved_by
        where shipment_id = p_id;
    end approve;
end shipment_api;
/
