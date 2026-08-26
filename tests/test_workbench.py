"""The local server: routes, refusals, and where files land.

The workbench holds customer source, so the tests that matter most here are
the ones about what it refuses.
"""

from __future__ import annotations

import argparse
import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from formslang.ai import EchoProvider
from formslang.cli import _work_dir
from formslang.convert import build_tasks
from formslang.parser import parse_xml
from formslang.store import APPROVED, Store
from formslang.workbench import Handler, Workbench


@pytest.fixture()
def server(tmp_path, sample_xml):
    store = Store(tmp_path / "s.db")
    store.init_session("DEMO_ORDER", str(sample_xml))
    store.add_tasks(build_tasks(parse_xml(sample_xml)))
    wb = Workbench(store, EchoProvider(), tmp_path / "export")

    handler = type("BoundHandler", (Handler,), {"workbench": wb})
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_port}"
    try:
        yield base, wb
    finally:
        httpd.shutdown()
        httpd.server_close()
        store.close()


def _get(base, path, host=None):
    req = urllib.request.Request(base + path)
    if host:
        req.add_header("Host", host)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def _post(base, path, payload):
    req = urllib.request.Request(
        base + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def _wait_for_job(wb, timeout=10.0):
    deadline = threading.Event()
    threading.Timer(timeout, deadline.set).start()
    while not deadline.is_set():
        if not wb.job_state()["running"]:
            return wb.job_state()
        deadline.wait(0.05)
    raise AssertionError("conversion job never finished")


def test_index_is_served(server):
    base, _ = server
    code, body = _get(base, "/")
    assert code == 200
    assert b"FormsLang" in body


def test_a_foreign_host_header_is_refused(server):
    """DNS rebinding is the one real attack on a loopback server."""
    base, _ = server
    assert _get(base, "/", host="attacker.example.com")[0] == 403
    assert _get(base, "/api/state", host="attacker.example.com")[0] == 403


def test_state_reports_the_session(server):
    base, _ = server
    _, body = _get(base, "/api/state")
    state = json.loads(body)
    assert state["session"]["title"] == "DEMO_ORDER"
    assert state["stats"]["tasks"] == len(state["tasks"])
    assert "echo" in state["provider"].lower() or "offline" in state["provider"].lower()


def test_unknown_path_is_a_404_not_a_crash(server):
    base, _ = server
    assert _get(base, "/etc/passwd")[0] == 404
    assert _post(base, "/api/nope", {})[0] == 404


def test_malformed_json_is_a_400(server):
    base, _ = server
    req = urllib.request.Request(
        base + "/api/decision", data=b"{not json", method="POST",
        headers={"Content-Type": "application/json"},
    )
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(req, timeout=10)
    assert e.value.code == 400


def test_conversion_runs_and_lands_in_the_store(server):
    base, wb = server
    task_id = wb.store.task_ids()[0]
    code, body = _post(base, "/api/propose", {"task_id": task_id})
    assert code == 200 and body["started"] == 1

    job = _wait_for_job(wb)
    assert job["done"] == 1 and job["error"] == ""
    assert wb.store.latest_proposal(task_id) is not None


def test_convert_all_only_touches_unconverted_tasks(server):
    base, wb = server
    total = wb.store.stats()["tasks"]
    _post(base, "/api/propose", {"all": True})
    _wait_for_job(wb)
    assert wb.store.stats()["unproposed"] == 0

    # Everything is converted now, so there is nothing left to ask for.
    code, body = _post(base, "/api/propose", {"all": True})
    assert code == 400 and "nothing" in body["error"].lower()
    assert wb.store.stats()["proposed"] == total


def test_decision_is_validated_before_it_is_stored(server):
    base, wb = server
    task_id = wb.store.task_ids()[0]
    assert _post(base, "/api/decision", {"task_id": task_id, "state": "maybe"})[0] == 400
    assert _post(base, "/api/decision", {"task_id": "ghost", "state": APPROVED})[0] == 404
    assert wb.store.view(task_id).state == "pending"


def test_approval_stores_the_reviewer_edit(server):
    base, wb = server
    task_id = wb.store.task_ids()[0]
    code, body = _post(base, "/api/decision", {
        "task_id": task_id, "state": APPROVED,
        "code": "-- hand written\nnull;", "reviewer": "ana",
    })
    assert code == 200 and body["stats"]["approved"] == 1
    view = wb.store.view(task_id)
    assert view.code == "-- hand written\nnull;"
    assert view.reviewer == "ana"


def test_export_writes_where_the_workbench_was_told_to(server, tmp_path):
    base, wb = server
    task_id = wb.store.task_ids()[0]
    _post(base, "/api/decision", {"task_id": task_id, "state": APPROVED, "code": "null;"})
    code, body = _post(base, "/api/export", {})
    assert code == 200
    assert Path(body["sql"]).parent == tmp_path / "export"
    assert Path(body["sql"]).exists() and Path(body["json"]).exists()


def test_a_second_job_is_refused_while_one_runs(tmp_path, sample_xml):
    store = Store(tmp_path / "s.db")
    store.init_session("DEMO_ORDER", str(sample_xml))
    store.add_tasks(build_tasks(parse_xml(sample_xml)))
    wb = Workbench(store, EchoProvider(), tmp_path / "export")
    try:
        wb.job["running"] = True  # pretend one is in flight
        assert wb.start_job(store.task_ids()) is False
    finally:
        store.close()


def test_the_ui_script_only_reaches_for_elements_that_exist():
    """A typo'd id is a silent blank panel, not an error anyone would see."""
    import re

    from formslang.ui import INDEX_HTML

    markup = re.sub(r"<script>.*?</script>", "", INDEX_HTML, flags=re.S)
    declared = set(re.findall(r'id="([^"]+)"', markup))
    used = set(re.findall(r"getElementById\(['\"]([^'\"]+)['\"]\)", INDEX_HTML))
    used |= set(re.findall(r"\$\(['\"]([^'\"]+)['\"]\)", INDEX_HTML))
    assert used, "the review screen has no script left in it"
    assert not (used - declared), f"script reaches for missing ids: {sorted(used - declared)}"


def test_the_ui_carries_no_external_reference():
    """The screen shows customer source; it must not phone anywhere."""
    from formslang.ui import INDEX_HTML

    lowered = INDEX_HTML.lower()
    for marker in ("http://", "https://", "//cdn", "fonts.googleapis", "integrity="):
        assert marker not in lowered, f"external reference in the review UI: {marker}"


def test_resumed_session_exports_next_to_its_own_file(tmp_path):
    """A reviewer resuming a session must not scatter SQL into their cwd."""
    db = tmp_path / "deep" / "DEMO.session.db"
    db.parent.mkdir()
    db.touch()
    args = argparse.Namespace(path=str(db), out=None)
    assert _work_dir(args) == db.parent.resolve()


def test_explicit_out_still_wins(tmp_path):
    args = argparse.Namespace(path=str(tmp_path / "x.session.db"), out="chosen")
    assert _work_dir(args) == Path("chosen")
