"""Unit tests for Oracle database source parsing and cross-layer reasoning in FormsLang."""

from __future__ import annotations

from pathlib import Path

from formslang import blueprint, database
from formslang.model import Block, FormModule, Item, Trigger


def _find_trigger_finding(bp: dict, trigger_name: str, owner: str = ""):
    entities = {e["id"]: e for e in bp["entities"]}
    for f in bp["findings"]:
        ent = entities.get(f["entity"])
        if (
            ent
            and ent["type"] == "TRIGGER"
            and ent["name"] == trigger_name
            and (not owner or ent.get("attributes", {}).get("owner") == owner)
        ):
            return f, ent
    return None, None


def test_parse_package_spec(tmp_path: Path):
    sql = """
    create or replace package order_mgmt_api as
        gc_vat_rate constant number := 0.20;
        gc_max_discount constant number := 0.50;

        function calc_total(
            p_qty in number,
            p_price in number,
            p_discount in number default 0
        ) return number;

        procedure process_order(
            p_order_id in number,
            p_user in varchar2 default user
        );
    end order_mgmt_api;
    /
    """
    spec_file = tmp_path / "order_mgmt_api.pks"
    spec_file.write_text(sql, encoding="utf-8")

    proj = database.parse_database_file(spec_file)
    assert "ORDER_MGMT_API" in proj.package_specs
    spec = proj.package_specs["ORDER_MGMT_API"]
    assert spec.name == "ORDER_MGMT_API"
    assert len(spec.constants) == 2
    assert spec.constants[0].name == "GC_VAT_RATE"
    assert spec.constants[0].value == "0.20"

    assert len(spec.subprograms) == 2
    fn = next(s for s in spec.subprograms if s.name == "CALC_TOTAL")
    assert fn.subprogram_type == "FUNCTION"
    assert fn.return_type == "NUMBER"
    assert len(fn.parameters) == 3
    assert fn.parameters[2].name == "P_DISCOUNT"
    assert fn.parameters[2].default_value == "0"

    proc = next(s for s in spec.subprograms if s.name == "PROCESS_ORDER")
    assert proc.subprogram_type == "PROCEDURE"
    assert proc.return_type is None
    assert proc.parameters[1].default_value.upper() == "USER"


def test_parse_package_body(tmp_path: Path):
    sql = """
    create or replace package body order_mgmt_api as
        function calc_total(
            p_qty in number,
            p_price in number,
            p_discount in number default 0
        ) return number is
        begin
            return (p_qty * p_price) - nvl(p_discount, 0);
        end calc_total;

        procedure process_order(
            p_order_id in number,
            p_user in varchar2 default user
        ) is
        begin
            update orders set status = 'PROCESSED' where order_id = p_order_id;
        end process_order;
    end order_mgmt_api;
    /
    """
    body_file = tmp_path / "order_mgmt_api.pkb"
    body_file.write_text(sql, encoding="utf-8")

    proj = database.parse_database_file(body_file)
    assert "ORDER_MGMT_API" in proj.package_bodies
    body = proj.package_bodies["ORDER_MGMT_API"]
    assert len(body.subprograms) == 2
    fn = next(s for s in body.subprograms if s.name == "CALC_TOTAL")
    assert "return (p_qty * p_price)" in fn.body_text


def test_parse_create_table(tmp_path: Path):
    sql = """
    create table customers (
        customer_id number(10) not null,
        customer_name varchar2(100) not null,
        credit_limit number(12,2) default 0 not null,
        status varchar2(20) default 'ACTIVE' not null,
        constraint pk_customers primary key (customer_id),
        constraint ck_cust_credit check (credit_limit >= 0),
        constraint ck_cust_status check (status in ('ACTIVE', 'INACTIVE'))
    );
    comment on table customers is 'Customer master table';
    """
    ddl_file = tmp_path / "customers.sql"
    ddl_file.write_text(sql, encoding="utf-8")

    proj = database.parse_database_file(ddl_file)
    assert "CUSTOMERS" in proj.tables
    tbl = proj.tables["CUSTOMERS"]
    assert tbl.name == "CUSTOMERS"
    assert tbl.comment == "Customer master table"
    assert len(tbl.columns) == 4
    assert len(tbl.constraints) == 3

    pk = next(c for c in tbl.constraints if c.constraint_type == "PRIMARY KEY")
    assert pk.columns == ["CUSTOMER_ID"]

    ck_credit = next(c for c in tbl.constraints if c.name == "CK_CUST_CREDIT")
    assert ck_credit.constraint_type == "CHECK"
    assert "credit_limit >= 0" in ck_credit.check_condition


def test_parse_create_view(tmp_path: Path):
    sql = """
    create or replace view active_customers_v as
    select c.customer_id, c.customer_name
      from customers c
     where c.status = 'ACTIVE';
    comment on table active_customers_v is 'Worklist view of active customers';
    """
    vw_file = tmp_path / "views.sql"
    vw_file.write_text(sql, encoding="utf-8")

    proj = database.parse_database_file(vw_file)
    assert "ACTIVE_CUSTOMERS_V" in proj.views
    vw = proj.views["ACTIVE_CUSTOMERS_V"]
    assert "from customers c" in vw.query_text
    assert vw.comment == "Worklist view of active customers"


def test_cross_layer_clean_api_delegation(tmp_path: Path):
    spec_sql = """
    create or replace package order_api as
        procedure submit_order(p_order_id in number);
    end order_api;
    """
    (tmp_path / "order_api.pks").write_text(spec_sql, encoding="utf-8")

    mod = FormModule(
        name="ORDERS",
        blocks=[
            Block(
                name="BK_ORDER",
                items=[
                    Item(
                        name="BT_SUBMIT",
                        triggers=[
                            Trigger(
                                name="WHEN-BUTTON-PRESSED",
                                text="BEGIN order_api.submit_order(:bk_order.order_id); END;",
                                scope="item",
                                owner="BK_ORDER.BT_SUBMIT",
                            )
                        ],
                    )
                ],
            )
        ],
    )

    bp = blueprint.build([mod], title="Orders", database_sources=tmp_path)
    tf, entity = _find_trigger_finding(bp, "WHEN-BUTTON-PRESSED", "BK_ORDER.BT_SUBMIT")
    assert tf is not None
    assert tf["recommendation"] == "PRESERVE"
    assert tf["execution_verdict"] == "AUTO"
    assert entity["attributes"]["risk"]["level"] == "LOW"


def test_cross_layer_check_constraint_mirroring(tmp_path: Path):
    table_sql = """
    create table customers (
        customer_id number not null,
        credit_limit number(12,2) not null,
        constraint pk_cust primary key (customer_id),
        constraint ck_cust_credit check (credit_limit >= 0)
    );
    """
    (tmp_path / "customers.sql").write_text(table_sql, encoding="utf-8")

    mod = FormModule(
        name="CUSTOMERS",
        blocks=[
            Block(
                name="BK_CUSTOMER",
                items=[
                    Item(
                        name="CREDIT_LIMIT",
                        triggers=[
                            Trigger(
                                name="WHEN-VALIDATE-ITEM",
                                text="BEGIN IF :BK_CUSTOMER.CREDIT_LIMIT < 0 THEN RAISE FORM_TRIGGER_FAILURE; END IF; END;",
                                scope="item",
                                owner="BK_CUSTOMER.CREDIT_LIMIT",
                            )
                        ],
                    )
                ],
            )
        ],
    )

    bp = blueprint.build([mod], title="Customers", database_sources=tmp_path)
    tf, entity = _find_trigger_finding(bp, "WHEN-VALIDATE-ITEM", "BK_CUSTOMER.CREDIT_LIMIT")
    assert tf is not None
    assert tf["recommendation"] == "CONVERT"
    assert tf["execution_verdict"] == "AUTO"
    assert entity["attributes"]["risk"]["level"] == "LOW"


def test_cross_layer_status_predicate_duplication(tmp_path: Path):
    body_sql = """
    create or replace package body customer_api as
        function has_open_orders(p_id in number) return varchar2 is
            v_cnt number;
        begin
            select count(*) into v_cnt from orders
             where customer_id = p_id and status not in ('SHIPPED', 'CANCELLED');
            return case when v_cnt > 0 then 'Y' else 'N' end;
        end has_open_orders;
    end customer_api;
    """
    (tmp_path / "customer_api.pkb").write_text(body_sql, encoding="utf-8")

    mod = FormModule(
        name="CUSTOMERS",
        blocks=[
            Block(
                name="BK_CUSTOMER",
                items=[
                    Item(
                        name="STATUS",
                        triggers=[
                            Trigger(
                                name="WHEN-VALIDATE-ITEM",
                                text="""BEGIN
                                    select count(*) into v_cnt from orders
                                     where customer_id = :bk_customer.customer_id
                                       and status not in ('SHIPPED', 'CANCELLED');
                                    IF v_cnt > 0 THEN RAISE FORM_TRIGGER_FAILURE; END IF;
                                END;""",
                                scope="item",
                                owner="BK_CUSTOMER.STATUS",
                            )
                        ],
                    )
                ],
            )
        ],
    )

    bp = blueprint.build([mod], title="Customers", database_sources=tmp_path)
    tf, entity = _find_trigger_finding(bp, "WHEN-VALIDATE-ITEM", "BK_CUSTOMER.STATUS")
    assert tf is not None
    assert tf["recommendation"] == "MOVE_TO_PLSQL_API"
    assert tf["execution_verdict"] == "MANUAL"
    assert entity["attributes"]["risk"]["level"] == "HIGH"


def test_cross_layer_formula_duplication(tmp_path: Path):
    body_sql = """
    create or replace package body order_api as
        function calc_line_total(p_qty in number, p_price in number, p_disc in number) return number is
        begin
            return (p_qty * p_price) - nvl(p_disc, 0);
        end calc_line_total;
    end order_api;
    """
    (tmp_path / "order_api.pkb").write_text(body_sql, encoding="utf-8")

    mod = FormModule(
        name="ORDERS",
        blocks=[
            Block(
                name="BK_ORDER_LINE",
                items=[
                    Item(
                        name="QUANTITY",
                        triggers=[
                            Trigger(
                                name="WHEN-VALIDATE-ITEM",
                                text="""BEGIN
                                    :bk_order_line.line_total := (:bk_order_line.quantity * :bk_order_line.unit_price) - nvl(:bk_order_line.discount, 0);
                                END;""",
                                scope="item",
                                owner="BK_ORDER_LINE.QUANTITY",
                            )
                        ],
                    )
                ],
            )
        ],
    )

    bp = blueprint.build([mod], title="Orders", database_sources=tmp_path)
    tf, entity = _find_trigger_finding(bp, "WHEN-VALIDATE-ITEM", "BK_ORDER_LINE.QUANTITY")
    assert tf is not None
    assert tf["recommendation"] == "MOVE_TO_PLSQL_API"
    assert tf["execution_verdict"] == "MANUAL"
    assert entity["attributes"]["risk"]["level"] == "HIGH"


def test_cross_layer_direct_dml_bypass_safety(tmp_path: Path):
    body_sql = """
    create or replace package body approval_api as
        procedure approve(p_id in number) is
        begin
            update lom_orders set status = 'APPROVED' where order_id = p_id;
        end approve;
    end approval_api;
    """
    (tmp_path / "approval_api.pkb").write_text(body_sql, encoding="utf-8")

    mod = FormModule(
        name="APPROVALS",
        blocks=[
            Block(
                name="BK_APPROVAL",
                items=[
                    Item(
                        name="BT_APPROVE",
                        triggers=[
                            Trigger(
                                name="WHEN-BUTTON-PRESSED",
                                text="""BEGIN
                                    UPDATE lom_orders SET status = 'APPROVED' WHERE order_id = :bk_approval.order_id;
                                    COMMIT;
                                END;""",
                                scope="item",
                                owner="BK_APPROVAL.BT_APPROVE",
                            )
                        ],
                    )
                ],
            )
        ],
    )

    bp = blueprint.build([mod], title="Approvals", database_sources=tmp_path)
    tf, entity = _find_trigger_finding(bp, "WHEN-BUTTON-PRESSED", "BK_APPROVAL.BT_APPROVE")
    assert tf is not None
    assert tf["recommendation"] == "MANUAL_REVIEW"
    assert tf["execution_verdict"] == "MANUAL"
    # Severity is measured, not assumed from the name of the column being written.
    # This API guards nothing, so what the trigger bypasses is ownership plus the
    # transaction boundary: serious, but short of the guarded case below.
    assert entity["attributes"]["risk"]["level"] == "HIGH"


def test_cross_layer_direct_dml_bypass_escalates_when_guards_are_lost(tmp_path: Path):
    """The same bypass against a guarded API is worse, and is reported as worse."""
    body_sql = """
    create or replace package body approval_api as
        procedure approve(p_id in number) is
            v_status varchar2(30);
        begin
            select status into v_status from lom_orders
             where order_id = p_id for update;
            update lom_orders set status = 'APPROVED' where order_id = p_id;
            if sql%rowcount = 0 then
                raise_application_error(-20001, 'Order not found');
            end if;
        end approve;
    end approval_api;
    """
    (tmp_path / "approval_api.pkb").write_text(body_sql, encoding="utf-8")

    mod = FormModule(
        name="APPROVALS",
        blocks=[
            Block(
                name="BK_APPROVAL",
                items=[
                    Item(
                        name="BT_APPROVE",
                        triggers=[
                            Trigger(
                                name="WHEN-BUTTON-PRESSED",
                                # No COMMIT here: the escalation must come from the
                                # guards this statement skips, not from durability.
                                text="""BEGIN
                                    UPDATE lom_orders SET status = 'APPROVED' WHERE order_id = :bk_approval.order_id;
                                END;""",
                                scope="item",
                                owner="BK_APPROVAL.BT_APPROVE",
                            )
                        ],
                    )
                ],
            )
        ],
    )

    bp = blueprint.build([mod], title="Approvals", database_sources=tmp_path)
    tf, entity = _find_trigger_finding(bp, "WHEN-BUTTON-PRESSED", "BK_APPROVAL.BT_APPROVE")
    assert tf is not None
    assert tf["recommendation"] == "MANUAL_REVIEW"
    assert tf["execution_verdict"] == "MANUAL"
    assert entity["attributes"]["risk"]["level"] == "CRITICAL"
    assert tf["suggested_target"] == "APPROVAL_API.APPROVE"
