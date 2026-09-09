"""The lexical extractor must not be fooled by comments or literals."""

from __future__ import annotations

from formslang.plsql import (
    APEX_MESSAGES,
    FORMS_MESSAGES,
    analyze,
    spoken_messages,
    strip_noise,
)


def test_commented_out_call_is_not_a_dependency():
    code = "BEGIN\n  -- HOST('rm -rf');\n  NULL;\nEND;"
    assert "HOST" not in analyze(code).builtins


def test_call_inside_a_string_literal_is_not_a_dependency():
    code = "BEGIN\n  v_msg := 'call HOST(x) here';\nEND;"
    assert "HOST" not in analyze(code).builtins


def test_block_comment_is_blanked_but_lines_are_kept():
    clean = strip_noise("a\n/* two\nlines */\nb")
    assert clean.count("\n") == 3
    assert "two" not in clean


def test_real_call_is_detected():
    assert analyze("BEGIN HOST('x'); END;").builtins["HOST"] == 1


def test_builtin_without_parentheses_is_detected():
    assert analyze("BEGIN COMMIT_FORM; END;").builtins["COMMIT_FORM"] == 1


def test_standard_sql_functions_are_not_forms_builtins():
    res = analyze("BEGIN x := NVL(TO_CHAR(SYSDATE), SUBSTR(y, 1, 2)); END;")
    assert not res.builtins
    assert not res.unknown_calls


def test_external_package_call_lands_in_unknown_calls():
    res = analyze("BEGIN PKG_ORDERS.CALCULATE(:B.ID); END;")
    assert res.unknown_calls["PKG_ORDERS.CALCULATE"] == 1
    assert not res.builtins


def test_bind_references_are_split_by_kind():
    res = analyze("BEGIN :GLOBAL.USER_ID := :ORDERS.ID; x := :SYSTEM.RECORD_STATUS; END;")
    assert res.globals_used["GLOBAL.USER_ID"] == 1
    assert res.item_refs["ORDERS.ID"] == 1
    assert res.system_vars["SYSTEM.RECORD_STATUS"] == 1


def test_sql_verbs_and_exception_block_are_counted():
    res = analyze(
        "BEGIN\n  SELECT 1 INTO x FROM DUAL;\n  UPDATE t SET c = 1;\n"
        "EXCEPTION WHEN OTHERS THEN NULL;\nEND;"
    )
    assert res.sql_verbs["select"] == 1
    assert res.sql_verbs["update"] == 1
    assert res.has_exception_block


def test_webutil_prefix_counts_as_a_forms_builtin():
    res = analyze("BEGIN WEBUTIL_FILE.FILE_SELECTION_DIALOG(x); END;")
    assert res.builtins["WEBUTIL_FILE.FILE_SELECTION_DIALOG"] == 1
    assert res.blockers()[0][0] == "WEBUTIL_FILE.FILE_SELECTION_DIALOG"


def test_merge_accumulates_two_analyses():
    a = analyze("BEGIN HOST('x'); END;")
    a.merge(analyze("BEGIN HOST('y'); COMMIT_FORM; END;"))
    assert a.builtins["HOST"] == 2
    assert a.builtins["COMMIT_FORM"] == 1


def test_a_message_is_read_out_of_the_forms_trigger():
    spoken = spoken_messages("BEGIN MESSAGE('Informe o cliente.'); END;", FORMS_MESSAGES)
    assert [(m.builtin, m.text) for m in spoken] == [("MESSAGE", "Informe o cliente.")]


def test_a_raise_carries_its_message_in_the_second_argument():
    spoken = spoken_messages(
        "BEGIN raise_application_error(-20001, 'Preco invalido.'); END;", APEX_MESSAGES
    )
    assert [m.text for m in spoken] == ["Preco invalido."]


def test_named_notation_finds_the_message_wherever_it_sits():
    spoken = spoken_messages(
        "BEGIN apex_error.add_error(p_display_location => 'INLINE', "
        "p_message => 'Sem estoque.'); END;",
        APEX_MESSAGES,
    )
    assert [m.text for m in spoken] == ["Sem estoque."]


def test_a_doubled_quote_is_an_apostrophe_the_user_should_see():
    """``_literal_value`` reads object names, where a surviving quote means two
    literals were concatenated. In prose it means an apostrophe, so the message
    reader has to be stricter and keep it."""
    spoken = spoken_messages("BEGIN MESSAGE('Nao pode''ser'); END;", FORMS_MESSAGES)
    assert [m.text for m in spoken] == ["Nao pode'ser"]


def test_a_message_built_at_run_time_comes_back_unread():
    """Half a sentence is not a sentence: the caller is handed the expression
    it could not read rather than a guess at what it will say."""
    spoken = spoken_messages("BEGIN MESSAGE('bad: ' || :B.A); END;", FORMS_MESSAGES)
    assert spoken[0].text == "" and spoken[0].expression == "'bad: ' || :B.A"


def test_a_message_call_inside_a_comment_or_a_string_is_not_a_message():
    code = (
        "BEGIN\n  -- MESSAGE('commented out');\n"
        "  v := 'text with MESSAGE(''quoted'') inside';\n"
        "  MESSAGE('the real one');\nEND;"
    )
    assert [m.text for m in spoken_messages(code, FORMS_MESSAGES)] == ["the real one"]


def test_a_package_of_your_own_named_message_is_not_the_builtin():
    assert spoken_messages("BEGIN PKG.MESSAGE('x'); END;", FORMS_MESSAGES) == []


def test_each_side_of_a_conversion_reads_only_its_own_calls():
    code = "BEGIN MESSAGE('forms'); raise_application_error(-20001, 'apex'); END;"
    assert [m.text for m in spoken_messages(code, FORMS_MESSAGES)] == ["forms"]
    assert [m.text for m in spoken_messages(code, APEX_MESSAGES)] == ["apex"]
