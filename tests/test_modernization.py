"""Generic modernization reasoning, exercised on a corpus unrelated to any benchmark.

Every fixture below describes a library lending system. Nothing in it shares a
table, package, column or module name with the corpus the engine is measured
against, which is the whole point: a rule that fires here fires on shape alone.
The vocabulary-independence test states that claim directly, by running one
structure through two different vocabularies and demanding the same verdict.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from formslang import database
from formslang import modernization as m


def unit(**overrides) -> m.UnitContext:
    """A trigger context with empty surroundings, overridden field by field."""
    base = {
        "name": "WHEN-BUTTON-PRESSED", "scope": "item", "block": "BK_LOAN",
        "item": "BT_GO", "source": "BEGIN NULL; END;",
        "calls": frozenset(), "writes": frozenset(), "reads": frozenset(),
    }
    base.update(overrides)
    for key in ("calls", "writes", "reads", "display_only_items"):
        if key in base and base[key] is not None:
            base[key] = frozenset(base[key])
    return m.UnitContext(**base)


def index_from(tmp_path: Path, **sources) -> m.ApiIndex:
    """Build the structural index from SQL given as <extension>__<name> keywords."""
    for keyword, text in sources.items():
        suffix, _, stem = keyword.partition("__")
        (tmp_path / f"{stem}.{suffix}").write_text(text, encoding="utf-8")
    return m.build_index(database.parse_database_sources(tmp_path))


def codes(signals) -> list:
    return [s.code for s in signals]


# --------------------------------------------------------------------------
# Structural primitives: the vocabulary in which every rule is written.
# --------------------------------------------------------------------------


def test_leaf_drops_qualifiers_and_conventional_prefixes():
    # A bind, a parameter and a local may all denote one concept.
    assert m.leaf(":bk_loan.due_date") == "DUE_DATE"
    assert m.leaf("p_due_date") == "DUE_DATE"
    assert m.leaf("v_due_date") == "DUE_DATE"
    assert m.leaf("lending_api.g_due_date") == "DUE_DATE"


def test_skeleton_erases_vocabulary_and_keeps_structure():
    form = "(:bk_fine.days * :bk_fine.day_rate) - nvl(:bk_fine.waiver, 0)"
    api = "(p_days * p_rate) - nvl(p_waiver, 0)"
    assert m.skeleton(form) == m.skeleton(api)
    # Structure still separates a different calculation.
    assert m.skeleton(form) != m.skeleton("(p_days + p_rate) - nvl(p_waiver, 0)")


def test_select_shape_records_table_projection_and_filter_columns():
    shape = m.select_shapes(
        "select state into v_state from loan_items "
        "where loan_id = p_loan_id and rownum = 1;")[0]
    assert shape.table == "LOAN_ITEMS"
    assert shape.filters == frozenset({"LOAN_ID"})
    assert shape.has_rownum_limit is True
    assert shape.locks is False


def test_literal_sets_collect_the_values_a_column_is_tested_against():
    triples = m.literal_sets("if p_state not in ('ON_LOAN', 'OVERDUE') then null; end if;")
    assert triples == [("STATE", "NOT IN", frozenset({"ON_LOAN", "OVERDUE"}))]


def test_guard_strength_counts_observable_protections():
    assert m.guard_strength("update loan_items set state = 'X' where id = p_id;") == 0
    guarded = """
        select state into v_state from loan_items where id = p_id for update;
        update loan_items set state = 'X' where id = p_id;
        if sql%rowcount = 0 then raise_application_error(-20001, 'gone'); end if;
    """
    assert m.guard_strength(guarded) == 3


def test_written_tables_reads_dml_targets_without_a_dictionary():
    body = """
        insert into loan_events(id) values (1);
        update loan_items set state = 'RETURNED' where id = p_id;
        delete from holds where loan_id = p_id;
    """
    assert m.written_tables(body) == [
        ("INSERT", "LOAN_EVENTS"), ("UPDATE", "LOAN_ITEMS"), ("DELETE", "HOLDS")]


def test_returned_expressions_ignore_the_declared_return_type():
    body = """
        function fine_amount(p_days in number, p_rate in number) return number is
        begin
            return p_days * p_rate;
        end fine_amount;
    """
    assert m.returned_expressions(body) == ["p_days * p_rate"]


def test_compared_values_ignore_the_direction_of_the_comparison():
    # A trigger mirrors a CHECK by testing its negation, so only the value counts.
    assert m.compared_values("fine_balance >= 0", "FINE_BALANCE") == frozenset({"0"})
    assert m.compared_values("if :bk.fine_balance < 0 then", "FINE_BALANCE") == frozenset({"0"})


# --------------------------------------------------------------------------
# The claim that matters: conclusions follow structure, not names.
# --------------------------------------------------------------------------


LIBRARY = {"pkg": "lending_api", "proc": "close_loan", "table": "loan_items",
           "column": "state", "key": "loan_id"}
CLINIC = {"pkg": "scheduling_api", "proc": "release_slot", "table": "appointments",
          "column": "visit_state", "key": "appointment_id"}


def _guarded_api(v: dict) -> str:
    return f"""
    create or replace package body {v['pkg']} as
        procedure {v['proc']}(p_id in number) is
            v_current varchar2(30);
        begin
            select {v['column']} into v_current from {v['table']}
             where {v['key']} = p_id for update;
            update {v['table']} set {v['column']} = 'CLOSED' where {v['key']} = p_id;
            if sql%rowcount = 0 then
                raise_application_error(-20001, 'not found');
            end if;
        end {v['proc']};
    end {v['pkg']};
    """


@pytest.mark.parametrize("vocabulary", [LIBRARY, CLINIC], ids=["library", "clinic"])
def test_same_structure_in_two_vocabularies_reaches_the_same_conclusion(
    tmp_path: Path, vocabulary: dict
):
    api = index_from(tmp_path, **{f"pkb__{vocabulary['pkg']}": _guarded_api(vocabulary)})
    ctx = unit(
        source=f"BEGIN UPDATE {vocabulary['table']} SET {vocabulary['column']} = 'CLOSED' "
               f"WHERE {vocabulary['key']} = :bk_main.id; END;",
        writes={vocabulary["table"].upper()})
    top = m.trigger_signals(ctx, api)[0]
    assert top.code == "DIRECT_DML_BYPASSES_API"
    assert top.recommendation == "MANUAL_REVIEW"
    assert top.verdict == m.MANUAL
    assert top.risk_level == m.CRITICAL
    assert top.target == f"{vocabulary['pkg']}.{vocabulary['proc']}".upper()


def test_reasoning_is_deterministic(tmp_path: Path):
    api = index_from(tmp_path, pkb__lending_api=_guarded_api(LIBRARY))
    ctx = unit(source="BEGIN UPDATE loan_items SET state = 'CLOSED' WHERE loan_id = 1; END;",
               writes={"LOAN_ITEMS"})
    assert [s.__dict__ for s in m.trigger_signals(ctx, api)] == \
           [s.__dict__ for s in m.trigger_signals(ctx, api)]


# --------------------------------------------------------------------------
# Ownership: logic the database layer already owns, restated in the form.
# --------------------------------------------------------------------------


def test_duplicated_query_is_routed_back_to_the_api(tmp_path: Path):
    api = index_from(tmp_path, pkb__lending_api="""
    create or replace package body lending_api as
        function current_state(p_loan_id in number) return varchar2 is
            v_state varchar2(30);
        begin
            select state into v_state from loan_items where loan_id = p_loan_id;
            return v_state;
        end current_state;
    end lending_api;
    """)
    ctx = unit(name="WHEN-VALIDATE-ITEM", item="STATE", source=(
        "BEGIN SELECT state INTO :bk_loan.state FROM loan_items "
        "WHERE loan_id = :bk_loan.loan_id; END;"))
    top = m.trigger_signals(ctx, api)[0]
    assert top.code == "LOGIC_DUPLICATED_QUERY"
    assert top.recommendation == m.MOVE_TO_PLSQL_API
    assert top.duplicates == "LENDING_API.CURRENT_STATE"


def test_duplicated_formula_is_routed_back_to_the_api(tmp_path: Path):
    api = index_from(tmp_path, pkb__fine_api="""
    create or replace package body fine_api as
        function fine_due(p_days in number, p_rate in number, p_waiver in number)
            return number is
        begin
            return (p_days * p_rate) - nvl(p_waiver, 0);
        end fine_due;
    end fine_api;
    """)
    ctx = unit(name="WHEN-VALIDATE-ITEM", item="AMOUNT", source=(
        "BEGIN :bk_fine.amount := (:bk_fine.days * :bk_fine.day_rate) "
        "- nvl(:bk_fine.waiver, 0); END;"))
    top = m.trigger_signals(ctx, api)[0]
    assert top.code == "LOGIC_DUPLICATED_FORMULA"
    assert top.duplicates == "FINE_API.FINE_DUE"


def test_duplicated_predicate_is_routed_back_to_the_api(tmp_path: Path):
    api = index_from(tmp_path, pkb__lending_api="""
    create or replace package body lending_api as
        function is_out(p_state in varchar2) return boolean is
        begin
            if p_state in ('ON_LOAN', 'OVERDUE') then
                return true;
            end if;
            return false;
        end is_out;
    end lending_api;
    """)
    ctx = unit(name="WHEN-VALIDATE-ITEM", item="STATE", source=(
        "BEGIN IF :bk_loan.state IN ('ON_LOAN', 'OVERDUE') THEN "
        "RAISE FORM_TRIGGER_FAILURE; END IF; END;"))
    top = m.trigger_signals(ctx, api)[0]
    assert top.code == "LOGIC_DUPLICATED_PREDICATE"
    assert top.duplicates == "LENDING_API.IS_OUT"


def test_calling_the_owning_api_is_not_reported_as_duplication(tmp_path: Path):
    api = index_from(tmp_path, pkb__lending_api=_guarded_api(LIBRARY))
    ctx = unit(source="BEGIN lending_api.close_loan(:bk_loan.loan_id); END;",
               calls={"LENDING_API.CLOSE_LOAN"})
    assert "DIRECT_DML_BYPASSES_API" not in codes(m.trigger_signals(ctx, api))


def test_write_with_no_owning_api_asks_for_one(tmp_path: Path):
    """A database layer was supplied, and nothing in it owns this table."""
    # The package owns LOAN_ITEMS, so the absence of an owner for LOAN_EVENTS is
    # a fact about the supplied layer rather than an absence of evidence.
    api = index_from(tmp_path, pkb__lending_api="""
    create or replace package body lending_api as
        procedure close_loan(p_id in number) is
        begin
            update loan_items set state = 'CLOSED' where loan_id = p_id;
        end close_loan;
    end lending_api;
    """)
    ctx = unit(source="BEGIN INSERT INTO loan_events(id) VALUES (1); END;",
               writes={"LOAN_EVENTS"})
    top = m.trigger_signals(ctx, api)[0]
    assert top.code == "DML_WITHOUT_OWNING_API"
    assert top.recommendation == m.MOVE_TO_PLSQL_API
    assert "LOAN_EVENTS" in top.target


def test_delegation_to_the_api_is_preserved(tmp_path: Path):
    api = index_from(tmp_path, pks__lending_api="""
    create or replace package lending_api as
        procedure close_loan(p_id in number);
    end lending_api;
    """)
    ctx = unit(source="BEGIN lending_api.close_loan(:bk_loan.loan_id); END;",
               calls={"LENDING_API.CLOSE_LOAN"})
    top = m.trigger_signals(ctx, api)[0]
    assert top.code == "DELEGATES_TO_API"
    assert (top.recommendation, top.verdict, top.level) == ("PRESERVE", m.AUTO, m.FACT)


# --------------------------------------------------------------------------
# Concurrency, navigation, filters and session state.
# --------------------------------------------------------------------------


def test_max_plus_one_key_allocation_is_flagged_at_insert_time():
    ctx = unit(name="PRE-INSERT", scope="block", item="", source=(
        "BEGIN SELECT NVL(MAX(line_no), 0) + 1 INTO :bk_loan_line.line_no "
        "FROM loan_lines WHERE loan_id = :bk_loan.loan_id; END;"))
    top = m.trigger_signals(ctx)[0]
    assert top.code == "UNSERIALIZED_KEY_DERIVATION"
    assert (top.recommendation, top.verdict) == ("REFACTOR", m.MANUAL)


def test_modal_and_non_modal_navigation_are_told_apart():
    modal = m.trigger_signals(unit(
        source="BEGIN CALL_FORM('MEMBERS', HIDE, DO_REPLACE, QUERY_ONLY, pl); END;",
        calls={"CALL_FORM"}))[0]
    assert (modal.code, modal.recommendation, modal.verdict) == (
        "MODAL_MODULE_CALL", "MANUAL_REVIEW", m.MANUAL)

    opened = m.trigger_signals(unit(
        source="BEGIN OPEN_FORM('MEMBERS', ACTIVATE, NO_SESSION, pl); END;",
        calls={"OPEN_FORM"}))[0]
    assert (opened.code, opened.recommendation, opened.verdict) == (
        "NON_MODAL_MODULE_OPEN", "REFACTOR", m.ASSISTED)


def test_literal_filter_policy_compiled_into_the_trigger_is_flagged():
    ctx = unit(name="WHEN-NEW-FORM-INSTANCE", scope="form", item="", source=(
        "BEGIN SET_BLOCK_PROPERTY('BK_LOAN', DEFAULT_WHERE, "
        "'state = ''OVERDUE'''); END;"), calls={"SET_BLOCK_PROPERTY"})
    top = m.trigger_signals(ctx)[0]
    assert top.code == "FILTER_POLICY_IN_CODE"
    assert (top.recommendation, top.verdict) == ("REFACTOR", m.ASSISTED)


def test_session_global_used_as_a_per_record_baseline_is_flagged():
    ctx = unit(name="POST-QUERY", scope="block", item="",
               source="BEGIN :GLOBAL.PREVIOUS_STATE := :BK_LOAN.STATE; END;")
    top = m.trigger_signals(ctx)[0]
    assert top.code == "CROSS_RECORD_SESSION_STATE"
    assert (top.recommendation, top.verdict) == ("REFACTOR", m.ASSISTED)


# --------------------------------------------------------------------------
# Behaviour the target platform already provides, and plain mechanical work.
# --------------------------------------------------------------------------


def test_hand_written_address_check_has_a_declarative_equivalent():
    ctx = unit(name="WHEN-VALIDATE-ITEM", item="EMAIL", source=(
        "BEGIN IF NOT REGEXP_LIKE(:bk_member.email, "
        "'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+$') THEN "
        "RAISE FORM_TRIGGER_FAILURE; END IF; END;"))
    top = m.trigger_signals(ctx)[0]
    assert top.code == "NATIVE_FORMAT_VALIDATION"
    assert (top.recommendation, top.verdict, top.risk_level) == (
        m.REPLACE_WITH_APEX_NATIVE, m.AUTO, m.LOW)


def test_confirmation_only_body_becomes_a_confirm_action():
    ctx = unit(source="BEGIN IF SHOW_ALERT('AL_CONFIRM') = ALERT_BUTTON1 THEN "
                      "NULL; END IF; END;", calls={"SHOW_ALERT"})
    assert m.trigger_signals(ctx)[0].code == "NATIVE_CONFIRMATION"


def test_runtime_item_property_switching_becomes_an_item_attribute():
    ctx = unit(source="BEGIN SET_ITEM_PROPERTY('BK_LOAN.DUE_DATE', ENABLED, "
                      "PROPERTY_FALSE); END;", calls={"SET_ITEM_PROPERTY"})
    assert m.trigger_signals(ctx)[0].code == "NATIVE_ITEM_STATE"


def test_display_only_derivation_is_presentation_not_logic():
    ctx = unit(name="POST-QUERY", scope="block", item="",
               source="BEGIN :bk_loan.days_late := :bk_loan.due_date - SYSDATE; END;",
               display_only_items={"DAYS_LATE"})
    assert m.trigger_signals(ctx)[0].code == "NATIVE_DISPLAY_DERIVATION"


def test_sequence_key_and_navigation_are_mechanical_conversions():
    key = m.trigger_signals(unit(name="PRE-INSERT", scope="block", item="",
                                 source="BEGIN :bk_loan.loan_id := loan_seq.NEXTVAL; END;"))[0]
    assert (key.code, key.recommendation, key.verdict, key.level) == (
        "SEQUENCE_KEY_ASSIGNMENT", "CONVERT", m.AUTO, m.FACT)

    toolbar = m.trigger_signals(unit(source="BEGIN GO_BLOCK('BK_LOAN'); EXECUTE_QUERY; END;",
                                     calls={"GO_BLOCK", "EXECUTE_QUERY"}))[0]
    assert (toolbar.code, toolbar.recommendation, toolbar.verdict) == (
        "NAVIGATION_TOOLBAR", "CONVERT", m.AUTO)


def test_lookup_and_reject_becomes_a_list_of_values():
    ctx = unit(name="WHEN-VALIDATE-ITEM", item="MEMBER_ID", source=(
        "BEGIN SELECT full_name INTO :bk_loan.member_name FROM members "
        "WHERE member_id = :bk_loan.member_id; "
        "EXCEPTION WHEN NO_DATA_FOUND THEN RAISE FORM_TRIGGER_FAILURE; END;"))
    top = m.trigger_signals(ctx)[0]
    assert top.code == "LOOKUP_VALIDATION"
    assert (top.recommendation, top.verdict) == ("CONVERT", m.ASSISTED)


def test_a_trigger_mirroring_a_check_constraint_is_already_guaranteed(tmp_path: Path):
    api = index_from(tmp_path, sql__members="""
    create table members (
        member_id number not null,
        fine_balance number(10,2) not null,
        constraint pk_members primary key (member_id),
        constraint ck_members_balance check (fine_balance >= 0)
    );
    """)
    ctx = unit(name="WHEN-VALIDATE-ITEM", item="FINE_BALANCE", item_column="FINE_BALANCE",
               base_table="MEMBERS", source=(
                   "BEGIN IF :bk_member.fine_balance < 0 THEN "
                   "RAISE FORM_TRIGGER_FAILURE; END IF; END;"))
    top = m.trigger_signals(ctx, api)[0]
    assert top.code == "MIRRORS_SCHEMA_CONSTRAINT"
    assert (top.verdict, top.risk_level, top.level) == (m.AUTO, m.LOW, m.FACT)


# --------------------------------------------------------------------------
# Verdict safety: what a body does decides how far it may be automated.
# --------------------------------------------------------------------------


def test_transaction_control_costs_a_clean_body_its_automatic_verdict(tmp_path: Path):
    api = index_from(tmp_path, pks__lending_api="""
    create or replace package lending_api as
        procedure close_loan(p_id in number);
    end lending_api;
    """)
    call = "BEGIN lending_api.close_loan(:bk_loan.loan_id); "
    plain = unit(source=call + "END;", calls={"LENDING_API.CLOSE_LOAN"})
    committing = unit(source=call + "COMMIT; END;", calls={"LENDING_API.CLOSE_LOAN"})
    assert m.trigger_signals(plain, api)[0].verdict == m.AUTO
    assert m.trigger_signals(committing, api)[0].verdict == m.ASSISTED


def test_leaving_the_module_costs_a_clean_body_its_automatic_verdict():
    assert m.escalate(m.AUTO, unit(calls={"CALL_FORM"})) == m.ASSISTED
    assert m.escalate(m.AUTO, unit(
        source="BEGIN :GLOBAL.LAST_ID := :BK_LOAN.LOAN_ID; END;")) == m.ASSISTED
    # An already-manual verdict is never relaxed by the same pass.
    assert m.escalate(m.MANUAL, unit()) == m.MANUAL


def test_a_safety_finding_outranks_a_native_shortcut(tmp_path: Path):
    api = index_from(tmp_path, pkb__lending_api=_guarded_api(LIBRARY))
    ctx = unit(name="WHEN-VALIDATE-ITEM", item="EMAIL", writes={"LOAN_ITEMS"}, source=(
        "BEGIN IF NOT REGEXP_LIKE(:bk_member.email, "
        "'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+$') THEN RAISE FORM_TRIGGER_FAILURE; END IF; "
        "UPDATE loan_items SET state = 'CLOSED' WHERE loan_id = :bk_loan.loan_id; END;"))
    found = codes(m.trigger_signals(ctx, api))
    assert found[0] == "DIRECT_DML_BYPASSES_API"
    # The weaker observation survives as a statement rather than being discarded.
    assert "NATIVE_FORMAT_VALIDATION" in found


# --------------------------------------------------------------------------
# Database-layer reasoning.
# --------------------------------------------------------------------------


def _subprogram(tmp_path: Path, sql: str):
    (tmp_path / "lending_api.pkb").write_text(sql, encoding="utf-8")
    db = database.parse_database_sources(tmp_path)
    return db.package_bodies["LENDING_API"].subprograms[0], m.build_index(db)


def test_identity_defaulting_to_the_session_user_is_critical(tmp_path: Path):
    sub, api = _subprogram(tmp_path, """
    create or replace package body lending_api as
        procedure close_loan(p_id in number, p_closed_by in varchar2 default user) is
        begin
            update loan_items set closed_by = p_closed_by where loan_id = p_id;
        end close_loan;
    end lending_api;
    """)
    top = m.subprogram_signals("LENDING_API.CLOSE_LOAN", sub, api)[0]
    assert top.code == "IDENTITY_DEFAULTS_TO_DB_SESSION"
    assert (top.recommendation, top.verdict, top.risk_level) == (
        "MANUAL_REVIEW", m.MANUAL, m.CRITICAL)


def test_an_enumerated_rule_matrix_stays_a_human_decision(tmp_path: Path):
    sub, api = _subprogram(tmp_path, """
    create or replace package body lending_api as
        function may_renew(p_state in varchar2) return boolean is
        begin
            if p_state = 'RESERVED' or p_state = 'ON_LOAN'
               or p_state = 'OVERDUE' or p_state = 'RETURNED' then
                return true;
            end if;
            return false;
        end may_renew;
    end lending_api;
    """)
    top = m.subprogram_signals("LENDING_API.MAY_RENEW", sub, api)[0]
    assert top.code == "RULE_TABLE_ENCODED_IN_CODE"
    assert (top.verdict, top.risk_level) == (m.MANUAL, m.HIGH)


def test_row_limited_read_is_flagged_only_without_a_uniqueness_guarantee(tmp_path: Path):
    (tmp_path / "holdings.sql").write_text("""
    create table holdings (
        holding_id number not null,
        isbn varchar2(20) not null,
        shelf varchar2(20),
        constraint pk_holdings primary key (holding_id)
    );
    """, encoding="utf-8")
    (tmp_path / "lending_api.pkb").write_text("""
    create or replace package body lending_api as
        procedure by_isbn(p_isbn in varchar2) is
            v_shelf varchar2(20);
        begin
            select shelf into v_shelf from holdings
             where isbn = p_isbn and rownum = 1;
        end by_isbn;
        procedure by_id(p_id in number) is
            v_shelf varchar2(20);
        begin
            select shelf into v_shelf from holdings
             where holding_id = p_id and rownum = 1;
        end by_id;
    end lending_api;
    """, encoding="utf-8")
    db = database.parse_database_sources(tmp_path)
    api = m.build_index(db)
    by_name = {s.name: s for s in db.package_bodies["LENDING_API"].subprograms}
    assert "NONDETERMINISTIC_SINGLE_ROW" in codes(
        m.subprogram_signals("LENDING_API.BY_ISBN", by_name["BY_ISBN"], api))
    # Filtering on the primary key makes the single row a guarantee, not a hope.
    assert "NONDETERMINISTIC_SINGLE_ROW" not in codes(
        m.subprogram_signals("LENDING_API.BY_ID", by_name["BY_ID"], api))


def test_a_column_nobody_reads_or_writes_is_reported(tmp_path: Path):
    (tmp_path / "holds.sql").write_text("""
    create table holds (
        hold_id number not null,
        member_id number not null,
        cancelled_reason varchar2(200)
    );
    """, encoding="utf-8")
    db = database.parse_database_sources(tmp_path)
    api = m.build_index(db)
    top = m.table_signals(db.tables["HOLDS"], api, frozenset({"HOLD_ID", "MEMBER_ID"}))[0]
    assert top.code == "UNREFERENCED_COLUMN"
    assert "CANCELLED_REASON" in top.reason
    assert top.verdict == m.MANUAL


def test_an_insert_only_table_with_no_references_is_left_alone(tmp_path: Path):
    (tmp_path / "loan_events.sql").write_text("""
    create table loan_events (
        event_id number not null,
        event_text varchar2(400)
    );
    """, encoding="utf-8")
    (tmp_path / "lending_api.pkb").write_text("""
    create or replace package body lending_api as
        procedure record_event(p_text in varchar2) is
        begin
            insert into loan_events(event_id, event_text)
            values (event_seq.nextval, p_text);
        end record_event;
    end lending_api;
    """, encoding="utf-8")
    db = database.parse_database_sources(tmp_path)
    api = m.build_index(db)
    top = m.table_signals(db.tables["LOAN_EVENTS"], api, frozenset())[0]
    assert top.code == "APPEND_ONLY_UNCONSTRAINED_TABLE"
    assert (top.recommendation, top.verdict) == ("PRESERVE", m.AUTO)


def test_a_view_without_a_restriction_needs_an_access_boundary(tmp_path: Path):
    (tmp_path / "views.sql").write_text("""
    create or replace view open_loans_v as
    select loan_id, member_id, state from loan_items;
    create or replace view my_loans_v as
    select loan_id, member_id from loan_items where member_id = sys_context('X', 'Y');
    """, encoding="utf-8")
    db = database.parse_database_sources(tmp_path)
    top = m.view_signals(db.views["OPEN_LOANS_V"])[0]
    assert top.code == "UNFILTERED_QUERY_SOURCE"
    assert (top.verdict, top.risk_level) == (m.MANUAL, m.MEDIUM)
    assert m.view_signals(db.views["MY_LOANS_V"]) == []
