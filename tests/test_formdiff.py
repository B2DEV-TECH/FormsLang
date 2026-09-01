"""formdiff: structural diff between two versions of the same module."""

from __future__ import annotations

from formslang.formdiff import compare_modules, diff_code, render_html, write_report
from formslang.model import Block, FormModule, Item, Lov, ProgramUnit, Relation, Trigger


def trigger(name, text, owner="", scope="form"):
    return Trigger(name=name, text=text, scope=scope, owner=owner)


def block(name, **kw):
    return Block(name=name, **kw)


def item(name, **kw):
    return Item(name=name, **kw)


# -- code diff -------------------------------------------------------------


def test_diff_code_reports_no_change_for_identical_text():
    changed, hunks = diff_code("BEGIN\n  NULL;\nEND;", "BEGIN\n  NULL;\nEND;")
    assert not changed
    assert hunks == []


def test_diff_code_produces_one_hunk_per_contiguous_change():
    a = "BEGIN\n  X := 1;\n  Y := 2;\nEND;"
    b = "BEGIN\n  X := 9;\n  Y := 2;\nEND;"
    changed, hunks = diff_code(a, b)
    assert changed
    assert len(hunks) == 1
    assert hunks[0].a_lines == ["  X := 1;"]
    assert hunks[0].b_lines == ["  X := 9;"]


def test_diff_code_does_not_drop_frequent_short_lines():
    """autojunk=False: PL/SQL full of repeated 'END IF;' lines must still diff correctly."""
    common = "\n".join(["IF a THEN", "  NULL;", "END IF;"] * 20)
    a = common + "\nX := 1;"
    b = common + "\nX := 2;"
    changed, hunks = diff_code(a, b)
    assert changed
    assert len(hunks) == 1
    assert hunks[0].a_lines == ["X := 1;"]
    assert hunks[0].b_lines == ["X := 2;"]


# -- flat collections: form-level triggers, LOVs, relations -----------------


def test_no_changes_between_identical_modules():
    a = FormModule(name="A", triggers=[trigger("WHEN-NEW-FORM-INSTANCE", "NULL;")])
    b = FormModule(name="A", triggers=[trigger("WHEN-NEW-FORM-INSTANCE", "NULL;")])
    diff = compare_modules(a, b)
    assert not diff.has_changes
    assert diff.triggers.unchanged == 1


def test_added_and_removed_are_detected_by_name():
    a = FormModule(name="A", lovs=[Lov(name="LOV_OLD")])
    b = FormModule(name="A", lovs=[Lov(name="LOV_NEW")])
    diff = compare_modules(a, b)
    assert [x.name for x in diff.lovs.added] == ["LOV_NEW"]
    assert [x.name for x in diff.lovs.removed] == ["LOV_OLD"]
    assert diff.lovs.modified == []


def test_renamed_entity_is_reported_as_remove_plus_add_not_a_match():
    """v1 does not detect renames -- documented scope limitation."""
    a = FormModule(name="A", relations=[Relation(name="ORD_LINES", detail_block="LINES")])
    b = FormModule(name="A", relations=[Relation(name="ORDER_LINES", detail_block="LINES")])
    diff = compare_modules(a, b)
    assert len(diff.relations.added) == 1
    assert len(diff.relations.removed) == 1
    assert diff.relations.modified == []


def test_property_change_is_reported_with_before_after():
    a = FormModule(name="A", relations=[Relation(name="R", join_condition="A.ID = B.ID")])
    b = FormModule(name="A", relations=[Relation(name="R", join_condition="A.ID = B.FK_ID")])
    diff = compare_modules(a, b)
    assert len(diff.relations.modified) == 1
    ec = diff.relations.modified[0]
    changed_fields = {name for name, _, _ in ec.props}
    assert "join_condition" in changed_fields


def test_trigger_code_change_is_reported_via_hunks_not_props():
    a = FormModule(name="A", triggers=[trigger("T1", "NULL;")])
    b = FormModule(name="A", triggers=[trigger("T1", "COMMIT;")])
    diff = compare_modules(a, b)
    assert len(diff.triggers.modified) == 1
    ec = diff.triggers.modified[0]
    assert ec.code_changed
    assert ec.hunks
    assert ec.props == []  # 'text' is excluded from plain property diffing


# -- nested cascading: items inside blocks, triggers inside items -----------


def test_item_level_trigger_change_elevates_the_item_as_forced():
    a_item = item("ORDER_ID", triggers=[trigger("WHEN-VALIDATE-ITEM", "NULL;", owner="ORDER_ID", scope="item")])
    b_item = item("ORDER_ID", triggers=[trigger("WHEN-VALIDATE-ITEM", "RAISE FORM_TRIGGER_FAILURE;", owner="ORDER_ID", scope="item")])
    a = FormModule(name="A", blocks=[block("ORDERS", items=[a_item])])
    b = FormModule(name="A", blocks=[block("ORDERS", items=[b_item])])

    diff = compare_modules(a, b)
    assert len(diff.blocks.modified) == 1
    block_change = diff.blocks.modified[0]
    assert block_change.forced  # block's own properties are unchanged
    assert block_change.props == []
    item_diff = block_change.children["items"]
    assert len(item_diff.modified) == 1
    item_change = item_diff.modified[0]
    assert item_change.forced
    assert item_change.children["triggers"].modified[0].code_changed


def test_block_own_property_change_is_not_marked_forced():
    a = FormModule(name="A", blocks=[block("ORDERS", where_clause="")])
    b = FormModule(name="A", blocks=[block("ORDERS", where_clause="STATUS = 'OPEN'")])
    diff = compare_modules(a, b)
    assert len(diff.blocks.modified) == 1
    assert not diff.blocks.modified[0].forced
    assert diff.blocks.modified[0].props


def test_unrelated_block_is_left_out_of_modified():
    a = FormModule(name="A", blocks=[block("ORDERS"), block("CUSTOMERS")])
    b = FormModule(name="A", blocks=[block("ORDERS", where_clause="X=1"), block("CUSTOMERS")])
    diff = compare_modules(a, b)
    assert [ec.name for ec in diff.blocks.modified] == ["ORDERS"]
    assert diff.blocks.unchanged == 1


# -- program units / record groups ------------------------------------------


def test_program_unit_body_change_is_hunked():
    a = FormModule(name="A", program_units=[ProgramUnit(name="PKG", kind="Package Body", text="BEGIN\n  NULL;\nEND;")])
    b = FormModule(name="A", program_units=[ProgramUnit(name="PKG", kind="Package Body", text="BEGIN\n  COMMIT;\nEND;")])
    diff = compare_modules(a, b)
    assert len(diff.program_units.modified) == 1
    assert diff.program_units.modified[0].hunks


# -- rendering ---------------------------------------------------------------


def test_render_html_reports_identical_modules_plainly():
    a = FormModule(name="A")
    b = FormModule(name="A")
    diff = compare_modules(a, b)
    html = render_html(diff, generated_at="2026-01-01 00:00 UTC")
    assert "structurally identical" in html


def test_render_html_shows_added_removed_modified_and_hunks():
    a = FormModule(
        name="OLD",
        triggers=[trigger("T1", "NULL;")],
        lovs=[Lov(name="LOV_A")],
    )
    b = FormModule(
        name="NEW",
        triggers=[trigger("T1", "COMMIT;")],
        lovs=[Lov(name="LOV_B")],
    )
    diff = compare_modules(a, b)
    html = render_html(diff, generated_at="2026-01-01 00:00 UTC")

    assert "OLD" in html and "NEW" in html
    assert "LOV_A" in html and "LOV_B" in html
    assert "- NULL;" in html
    assert "+ COMMIT;" in html


def test_write_report_names_file_after_both_modules(tmp_path):
    a = FormModule(name="ORDER_V1")
    b = FormModule(name="ORDER_V2", lovs=[Lov(name="NEW_LOV")])
    diff = compare_modules(a, b)
    path = write_report(diff, tmp_path / "diff")

    assert path.name == "ORDER_V1_vs_ORDER_V2.diff.html"
    assert "NEW_LOV" in path.read_text(encoding="utf-8")
