"""A confirmed key turns a region into a form the page can actually save.

Every claim here was checked against a running APEX 26.1 before it was
written down: the page was imported into a throwaway application, opened
through a signed link, and made to fetch a row, save an edit and create a
row. Two of these tests exist because ``apex validate`` and ``apex import``
both accepted a page that silently did nothing at run time -- the branch
spelling and the buttons' database action. Those are the lines to be most
careful about changing.
"""

from __future__ import annotations

import pytest

from formslang.apexlang import export_apexlang
from formslang.convert import build_tasks
from formslang.parser import parse_xml
from formslang.store import Store


@pytest.fixture()
def order_session(tmp_path, sample_xml):
    module = parse_xml(sample_xml)
    store = Store(tmp_path / "DEMO_ORDER.session.db")
    store.init_session(module.name, str(sample_xml))
    store.add_tasks(build_tasks(module))
    try:
        yield store, module
    finally:
        store.close()


def _page(store, module, tmp_path, name="export") -> str:
    result = export_apexlang(
        store, module, tmp_path / name, {"app_id": 321, "alias": "demo-orders"}
    )
    return next((result.project / "pages").glob("p00001-*.apx")).read_text(encoding="utf-8")


def _component(text: str, header: str) -> str:
    """One component of the page, from its header line to its closing paren."""
    start = text.index(header)
    return text[start : text.index("\n    )\n", start)]


def _block(component: str, name: str) -> str:
    """One ``name { ... }`` group inside a component."""
    start = component.index(name + " {")
    return component[start : component.index("\n        }", start)]


def test_a_confirmed_key_binds_the_region_to_its_table(order_session, tmp_path):
    """The whole point of the confirmation: the region stops being a picture
    of a block and becomes a form APEX can query, with the key item marked so
    APEX knows which column identifies the row."""
    store, module = order_session
    store.confirm_block_key("ORDERS", "ORDERS", "ORDER_ID", "ana")
    text = _page(store, module, tmp_path)

    region = _component(text, "\n    region cv-main")
    assert "type: form" in region
    assert "staticContent" not in region
    assert "tableName: ORDERS" in _block(region, "source")

    source = _block(_component(text, "\n    pageItem P1_ORDER_ID"), "source")
    assert "formRegion: @cv-main" in source
    assert "column: ORDER_ID" in source
    assert "dataType: number" in source
    assert "primaryKey: true" in source
    # ``type:`` inside ``source`` is what an *unbound* item carries; a bound
    # one takes its value from the region's row instead.
    assert "type:" not in source


def test_a_bound_region_fetches_before_the_header_and_writes_behind_every_rule(
    order_session, tmp_path
):
    store, module = order_session
    store.confirm_block_key("ORDERS", "ORDERS", "ORDER_ID", "ana")
    text = _page(store, module, tmp_path)

    fetch = _component(text, "\n    process cv-main-form-init")
    assert "type: formInitialization" in fetch
    assert "point: beforeHeader" in fetch

    dml = _component(text, "\n    process cv-main-form-dml")
    assert "type: formAutoRowProcessing" in dml
    assert "targetType: regionSource" in dml
    # Approved conversions number from 10; the write has to come last so a
    # trigger a reviewer enables has already filled its column.
    assert "sequence: 1000" in dml
    assert "point: processing" in dml


def test_the_save_branch_redirects_and_is_never_a_show_only_branch(order_session, tmp_path):
    """APEX refuses a Show Only branch on a page whose Reload on Submit is
    Only for Success -- which is every page FormsLang writes. It refuses it
    at run time, in the debug log, with the DML skipped and nothing on
    screen: ``apex validate`` accepts both spellings, so only this test
    stands between the two."""
    store, module = order_session
    store.confirm_block_key("ORDERS", "ORDERS", "ORDER_ID", "ana")
    text = _page(store, module, tmp_path)

    branch = _component(text, "\n    branch cv-main-form-branch")
    assert "type: pageOrUrl" in branch
    assert "target: {" in branch and "page: 1" in branch
    assert "type: page\n" not in branch
    assert "pageNumber:" not in branch
    # Any submit has to have a branch: a conditioned one leaves a button
    # FormsLang did not write with nowhere to go, which is ERR-1777.
    assert "serverSideCondition" not in branch


def test_a_bound_region_gets_a_create_button_and_a_save_button(order_session, tmp_path):
    """APEX takes insert-or-update from the button's Database Action, not
    from whether the form found a row. One button alone always updates, and
    the page can then never create a record -- which is how the first
    version of this shipped through ``apex validate`` unnoticed."""
    store, module = order_session
    store.confirm_block_key("ORDERS", "ORDERS", "ORDER_ID", "ana")
    text = _page(store, module, tmp_path)

    create = _component(text, "\n    button cv-main-create")
    assert "buttonName: CREATE" in create
    assert "databaseAction: insert" in create
    assert "type: itemIsNull" in create and "item: P1_ORDER_ID" in create

    save = _component(text, "\n    button cv-main-save")
    assert "buttonName: SAVE" in save
    assert "databaseAction: update" in save
    assert "type: itemIsNotNull" in save and "item: P1_ORDER_ID" in save

    # Both buttons have to reach the one process that writes the row.
    dml = _component(text, "\n    process cv-main-form-dml")
    assert "type: requestIsContainedInValue" in dml
    assert "value: CREATE,SAVE" in dml


def test_a_block_without_a_confirmed_key_is_left_exactly_as_it_was(order_session, tmp_path):
    """The confirmation is the whole gate. With nobody on the hook for the
    key, the page keeps the shape it had before any of this existed."""
    store, module = order_session
    text = _page(store, module, tmp_path)

    region = _component(text, "\n    region cv-main")
    assert "type: staticContent" in region
    assert "type: form" not in region
    for absent in (
        "formInitialization",
        "formAutoRowProcessing",
        "cv-main-form-branch",
        "button cv-main-save",
        "button cv-main-create",
    ):
        assert absent not in text

    item = _component(text, "\n    pageItem P1_ORDER_ID")
    assert "formRegion:" not in item
    assert "primaryKey:" not in item


def test_withdrawing_the_confirmation_takes_the_form_back_out(order_session, tmp_path):
    store, module = order_session
    store.confirm_block_key("ORDERS", "ORDERS", "ORDER_ID", "ana")
    assert "type: form" in _page(store, module, tmp_path, "bound")

    store.forget_block_key("ORDERS")
    text = _page(store, module, tmp_path, "unbound")
    assert "type: staticContent" in _component(text, "\n    region cv-main")
    assert "formAutoRowProcessing" not in text


def test_the_same_confirmation_exports_the_same_bytes(order_session, tmp_path):
    """Determinism is the contract the whole export makes; binding must not
    be the thing that breaks it."""
    store, module = order_session
    store.confirm_block_key("ORDERS", "ORDERS", "ORDER_ID", "ana")
    assert _page(store, module, tmp_path, "first") == _page(store, module, tmp_path, "second")
