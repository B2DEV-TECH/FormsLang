"""The lexical extractor must not be fooled by comments or literals."""

from __future__ import annotations

from formslang.plsql import analyze, strip_noise


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
