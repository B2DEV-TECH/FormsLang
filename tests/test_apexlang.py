"""APEXlang export: exact package shape, safe names, and review boundary."""

from __future__ import annotations

import json
import zipfile

import pytest

from formslang.apexlang import (
    ApexExportConfig,
    _item_type,
    _page_items,
    checksum_salt,
    export_apexlang,
    last_export_config,
)
from formslang.convert import Proposal, build_tasks
from formslang.model import Block, FormModule, Item
from formslang.parser import parse_xml
from formslang.store import APPROVED, REJECTED, Store


@pytest.mark.parametrize(
    "forms_type, apex_type",
    [
        ("Check Box", "checkbox"),
        ("Display Item", "displayOnly"),
        ("Text Item", "textField"),
        ("Bean Area", "textarea"),
        ("List Item", "selectList"),
        ("Radio Group", "radioGroup"),
        ("Image", "textField"),  # no verified APEXlang keyword -> safe fallback
    ],
)
def test_item_type_mapping(forms_type, apex_type):
    assert _item_type(Item(name="X", item_type=forms_type)) == apex_type


def test_a_multiline_text_item_becomes_a_textarea():
    """``MultiLine="true"`` is the Forms spelling of "a box that wraps and
    scrolls"; the same verified ``textarea`` keyword a Bean Area already
    maps to. A plain Text Item stays a one-line field."""
    assert _item_type(Item(name="X", item_type="Text Item", multi_line=True)) == "textarea"
    assert _item_type(Item(name="X", item_type="Text Item", multi_line=False)) == "textField"


def test_value_required_is_emitted_only_for_editable_item_types():
    """APEX's compiler rejects ``valueRequired`` on a ``displayOnly`` item
    (INVALID_PROPERTY, observed against APEX 26.1) and one such line fails the
    whole import; editable types accept it. The Forms fact survives in the
    comment either way."""
    module = FormModule(
        name="REQ",
        blocks=[
            Block(
                name="B",
                items=[
                    Item(name="SHOWN", item_type="Display Item", required=True),
                    Item(name="TYPED", item_type="Text Item", required=True),
                    Item(name="TICKED", item_type="Check Box", required=True),
                    Item(name="FREE", item_type="Text Item", required=False),
                ],
            )
        ],
    )
    chunks, _ = _page_items(module, 1)
    by_item = {name: chunk for chunk in chunks for name in ("SHOWN", "TYPED", "TICKED", "FREE") if f"P1_{name}" in chunk}

    assert "valueRequired" not in by_item["SHOWN"]
    assert "required in Forms" in by_item["SHOWN"]
    assert "valueRequired: true" in by_item["TYPED"]
    assert "valueRequired: true" in by_item["TICKED"]
    assert "valueRequired" not in by_item["FREE"]
    assert "required in Forms" not in by_item["FREE"]


@pytest.fixture()
def approved_session(tmp_path, sample_xml):
    module = parse_xml(sample_xml)
    store = Store(tmp_path / "DEMO_ORDER.session.db")
    store.init_session(module.name, str(sample_xml))
    store.add_tasks(build_tasks(module))
    ids = store.task_ids()
    store.save_proposal(
        ids[0],
        Proposal(code="begin\n  :P0_ORDER_ID := 1;\nend;", apex_target="Page process"),
    )
    store.set_decision(
        ids[0], APPROVED, code="begin\n  :P0_ORDER_ID := 1;\nend;", reviewer="ana"
    )
    store.save_proposal(ids[1], Proposal(code="do_not_ship;"))
    store.set_decision(ids[1], REJECTED, code="do_not_ship;")
    try:
        yield store, module
    finally:
        store.close()


def test_export_is_an_apexlang_261_project_and_import_zip(approved_session, tmp_path):
    store, module = approved_session
    result = export_apexlang(
        store,
        module,
        tmp_path / "export",
        {
            "app_id": 321,
            "name": "Demo Orders",
            "alias": "demo-orders",
            "workspace": "MY_WORKSPACE",
            "schema": "my_schema",
        },
    )

    assert result.project.name == "demo-orders"
    assert result.zip_path.name == "demo-orders.apex.zip"
    assert result.approved == 1
    assert (result.project / "application.apx").exists()
    assert (result.project / ".apex" / "apexlang.json").exists()
    assert (result.project / "deployments" / "default.json").exists()

    app = (result.project / "application.apx").read_text(encoding="utf-8")
    deployment = json.loads(
        (result.project / "deployments" / "default.json").read_text(encoding="utf-8")
    )
    assert "app DEMO-ORDERS" in app
    assert 'compatibilityMode: "26.1"' in app
    assert deployment["app"]["id"] == 321
    assert deployment["app"]["databaseSession"]["parsingSchema"] == "MY_SCHEMA"
    assert deployment["workspace"]["name"] == "MY_WORKSPACE"

    page = next((result.project / "pages").glob("p00001-demo-order.apx"))
    text = page.read_text(encoding="utf-8")
    assert "region cv-main" in text  # the canvas, not the block, is the region
    assert "pageItem P1_ORDER_ID" in text
    assert ":P1_ORDER_ID := 1" in text
    assert "serverSideCondition" in text and "type: never" in text
    assert "do_not_ship" not in text

    with zipfile.ZipFile(result.zip_path) as archive:
        names = set(archive.namelist())
    assert "application.apx" in names
    assert ".apex/apexlang.json" in names
    assert "deployments/default.json" in names
    assert "session.json" not in names
    assert not any(name.startswith("demo-orders/") for name in names)


def test_review_artifacts_stay_outside_the_import_project(approved_session, tmp_path):
    store, module = approved_session
    result = export_apexlang(store, module, tmp_path / "export")

    assert result.sql_path.parent.name == "demo-order-review"
    assert result.json_path.parent == result.sql_path.parent
    assert result.manifest_path.parent == result.sql_path.parent
    assert not (result.project / "session.json").exists()
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["format"] == "APEXlang 26.1"
    assert manifest["approved_components"][0]["enabled"] is False
    assert manifest["import"]["database_required"] is True


@pytest.mark.parametrize(
    "config, message",
    [
        ({"alias": "../escape"}, "alias"),
        ({"alias": "99bad"}, "alias"),
        ({"app_id": "not-a-number"}, "integers"),
        ({"page": 9999}, "page"),
    ],
)
def test_unsafe_or_invalid_export_configuration_is_refused(
    approved_session, config, message
):
    _, module = approved_session
    with pytest.raises(ValueError, match=message):
        ApexExportConfig.from_dict(config, module)


def test_workspace_and_schema_can_be_resolved_only_at_import(approved_session, tmp_path):
    store, module = approved_session
    result = export_apexlang(store, module, tmp_path / "export", {"alias": "portable"})
    deployment = json.loads(
        (result.project / "deployments" / "default.json").read_text(encoding="utf-8")
    )
    assert "workspace" not in deployment
    assert "databaseSession" not in deployment["app"]


# -- determinism: the same session yields the same bytes ---------------------


def test_the_same_session_exports_the_same_bytes(approved_session, tmp_path):
    """What makes an export a build artifact rather than a snapshot: two
    exports of the same reviewed session are identical -- ZIP included --
    so CI can rebuild what was reviewed and a diff between two commits is a
    diff between two reviews, never between two clocks."""
    store, module = approved_session
    config = {"app_id": 321, "alias": "demo-orders", "workspace": "WS", "schema": "S"}
    first = export_apexlang(store, module, tmp_path / "one", config)
    second = export_apexlang(store, module, tmp_path / "two", config)

    assert first.zip_path.read_bytes() == second.zip_path.read_bytes()
    assert (first.project / "application.apx").read_bytes() == (
        second.project / "application.apx"
    ).read_bytes()


def test_zip_entries_never_carry_the_build_clock(approved_session, tmp_path):
    store, module = approved_session
    result = export_apexlang(store, module, tmp_path / "export")
    with zipfile.ZipFile(result.zip_path) as archive:
        infos = archive.infolist()
    assert infos, "an empty ZIP would import nothing"
    assert {info.date_time for info in infos} == {(1980, 1, 1, 0, 0, 0)}
    assert [info.filename for info in infos] == sorted(info.filename for info in infos)


def test_the_checksum_salt_is_drawn_once_per_session(approved_session, tmp_path, sample_xml):
    store, _ = approved_session
    salt = checksum_salt(store)
    assert len(salt) == 64 and salt == salt.upper()
    assert checksum_salt(store) == salt

    other = Store(tmp_path / "other.session.db")
    try:
        other.init_session("OTHER", str(sample_xml))
        assert checksum_salt(other) != salt  # unpredictable, per application
    finally:
        other.close()


def test_the_export_remembers_its_choices_on_the_session(approved_session, tmp_path):
    store, module = approved_session
    assert last_export_config(store) == {}

    export_apexlang(store, module, tmp_path / "export", {"app_id": 321, "alias": "demo-orders"})
    remembered = last_export_config(store)
    assert remembered["app_id"] == 321
    assert remembered["alias"] == "demo-orders"
    assert remembered["page"] == 1

    # Whatever is remembered must be a valid starting point for the next one.
    ApexExportConfig.from_dict(remembered, module)


def test_the_manifest_tells_the_cli_way_back(approved_session, tmp_path):
    store, module = approved_session
    result = export_apexlang(store, module, tmp_path / "export", {"alias": "demo-orders"})
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["reproducible"] is True
    cli = manifest["cli"]
    assert cli["export"].startswith(f"formslang export {store.path.name} ")
    assert "--alias demo-orders" in cli["export"]
    assert cli["validate"] == "formslang apex validate demo-orders.apex.zip"
    assert cli["import"] == "formslang apex import demo-orders.apex.zip"
