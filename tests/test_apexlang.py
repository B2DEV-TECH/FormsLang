"""APEXlang export: exact package shape, safe names, and review boundary."""

from __future__ import annotations

import json
import zipfile

import pytest

from formslang.apexlang import ApexExportConfig, export_apexlang
from formslang.convert import Proposal, build_tasks
from formslang.parser import parse_xml
from formslang.store import APPROVED, REJECTED, Store


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
    assert "region orders" in text
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
