"""``formslang export``: the workbench's Export button, headless and reproducible."""

from __future__ import annotations

import json
import zipfile

import pytest

from formslang import cli
from formslang.apexlang import last_export_config
from formslang.convert import Proposal, build_tasks
from formslang.parser import parse_xml
from formslang.store import APPROVED, Store


@pytest.fixture()
def session_db(tmp_path, sample_xml):
    """A reviewed session on disk, the way a repository would carry one."""
    module = parse_xml(sample_xml)
    db = tmp_path / "DEMO_ORDER.session.db"
    store = Store(db)
    store.init_session(module.name, str(sample_xml))
    store.add_tasks(build_tasks(module))
    first = store.task_ids()[0]
    code = "begin\n  :P0_ORDER_ID := 1;\nend;"
    store.save_proposal(first, Proposal(code=code, apex_target="Page process"))
    store.set_decision(first, APPROVED, code=code, reviewer="ana")
    store.close()
    return db


def test_export_builds_the_zip_beside_the_session(session_db, capsys):
    exit_code = cli.main(["export", str(session_db), "--alias", "demo", "--app-id", "200"])
    assert exit_code == 0

    zip_path = session_db.parent / "export" / "demo.apex.zip"
    assert zip_path.is_file()
    out = capsys.readouterr().out
    assert str(zip_path) in out
    assert "Approved : 1 component(s)" in out
    assert "formslang apex validate" in out

    with zipfile.ZipFile(zip_path) as archive:
        names = set(archive.namelist())
    assert {"application.apx", ".apex/apexlang.json", "deployments/default.json"} <= names
    deployment = json.loads(
        (session_db.parent / "export" / "demo" / "deployments" / "default.json").read_text("utf-8")
    )
    assert deployment["app"]["id"] == 200


def test_a_second_run_with_no_flags_reproduces_the_same_bytes(session_db):
    """The CI promise: the session carries the choices, and the same session
    yields the same ZIP -- so a rebuilt artifact can be diffed, cached and
    trusted to be what was reviewed."""
    assert cli.main(["export", str(session_db), "--alias", "demo", "--app-id", "200"]) == 0
    zip_path = session_db.parent / "export" / "demo.apex.zip"
    first = zip_path.read_bytes()

    assert cli.main(["export", str(session_db)]) == 0
    assert zip_path.read_bytes() == first

    store = Store(session_db)
    try:
        remembered = last_export_config(store)
    finally:
        store.close()
    assert remembered["alias"] == "demo"
    assert remembered["app_id"] == 200


def test_flags_override_only_what_they_name(session_db):
    assert cli.main(["export", str(session_db), "--alias", "demo", "--app-id", "200"]) == 0
    assert cli.main(["export", str(session_db), "--app-id", "201"]) == 0

    store = Store(session_db)
    try:
        remembered = last_export_config(store)
    finally:
        store.close()
    assert remembered["alias"] == "demo"  # kept from the previous export
    assert remembered["app_id"] == 201  # replaced by the flag


def test_json_output_describes_the_export(session_db, capsys):
    assert cli.main(["export", str(session_db), "--alias", "demo", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["format"] == "APEXlang 26.1"
    assert data["zip"].endswith("demo.apex.zip")
    assert data["approved"] == 1


def test_export_works_straight_from_a_module(sample_xml, tmp_path, capsys):
    """No session yet: one is created beside the module, exactly like the
    other commands do, and the export holds no approved work."""
    out = tmp_path / "work"
    exit_code = cli.main(["export", str(sample_xml), "--out", str(out), "--alias", "fresh"])
    assert exit_code == 0
    assert (out / "DEMO_ORDER.session.db").is_file()
    assert (out / "export" / "fresh.apex.zip").is_file()
    assert "Approved : 0 component(s)" in capsys.readouterr().out


def test_a_session_without_a_module_is_refused_with_a_hint(tmp_path, capsys):
    db = tmp_path / "empty.session.db"
    exit_code = cli.main(["export", str(db)])
    assert exit_code == 2
    err = capsys.readouterr().err
    assert "ERROR" in err
    assert "no Forms module" in err


def test_an_unsafe_alias_is_refused(session_db, capsys):
    assert cli.main(["export", str(session_db), "--alias", "../escape"]) == 2
    assert "alias" in capsys.readouterr().err
