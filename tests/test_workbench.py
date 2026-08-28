"""The local server: routes, refusals, and where files land.

The workbench holds customer source, so the tests that matter most here are
the ones about what it refuses.
"""

from __future__ import annotations

import argparse
import json
import os
import threading
import urllib.error
import urllib.parse
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


def _upload(base, name, payload):
    req = urllib.request.Request(
        base + "/api/upload?name=" + urllib.parse.quote(name),
        data=payload,
        headers={"Content-Type": "application/octet-stream"},
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
    """DNS rebinding is one of the two real attacks on a loopback server."""
    base, _ = server
    assert _get(base, "/", host="attacker.example.com")[0] == 403
    assert _get(base, "/api/state", host="attacker.example.com")[0] == 403


def test_a_keyless_http_provider_refuses_to_start_a_run(server):
    """An HTTP provider with no API key would 401 on every task. The run
    must be refused up front, with the fix in the message."""
    from formslang.ai import build_provider

    base, wb = server
    wb.provider = build_provider("anthropic")  # isolated config: no key anywhere
    status, data = _post(base, "/api/propose", {"all": True})
    assert status == 400
    assert "needs an API key" in data["error"]
    assert not wb.job_state()["running"]


def test_failed_proposals_are_counted_in_the_job(server):
    """A run where the provider errors must say so -- never report the
    failures as converted units."""
    from formslang.ai import EchoProvider, ProviderError

    class FailingProvider(EchoProvider):
        def complete(self, messages, max_tokens=4096):
            raise ProviderError("HTTP 401: x-api-key header is required")

    base, wb = server
    wb.provider = FailingProvider()
    status, _data = _post(base, "/api/propose", {"all": True})
    assert status == 200
    job = _wait_for_job(wb)
    assert job["failed"] == job["total"] > 0
    assert "401" in job["last_error"]


def test_a_cross_site_content_type_is_refused(server):
    """The other real attack: a plain HTML form can smuggle JSON as
    text/plain with no CORS preflight. Demanding the real content type
    turns that CSRF into a 415 before any route runs."""
    base, wb = server
    smuggled = b'{"provider": "anthropic", "base_url": "http://evil.example"}'
    for path in ("/api/settings", "/api/propose", "/api/terminal"):
        req = urllib.request.Request(
            base + path, data=smuggled,
            headers={"Content-Type": "text/plain"}, method="POST",
        )
        with pytest.raises(urllib.error.HTTPError) as err:
            urllib.request.urlopen(req, timeout=10)
        assert err.value.code == 415, path
    # The upload route takes bytes, not JSON -- but only as octet-stream.
    req = urllib.request.Request(
        base + "/api/upload?name=x.fmb", data=b"AB",
        headers={"Content-Type": "text/plain"}, method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as err:
        urllib.request.urlopen(req, timeout=10)
    assert err.value.code == 415
    assert wb.provider.type_id == "echo", "the smuggled settings must not land"


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
    assert Path(body["sql"]).parent.parent == tmp_path / "export"
    assert Path(body["sql"]).exists() and Path(body["json"]).exists()
    assert Path(body["zip"]).parent == tmp_path / "export"
    assert Path(body["zip"]).exists() and Path(body["project"]).is_dir()


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

    markup = re.sub(r"<script>.*?</script>", "", INDEX_HTML, flags=re.DOTALL)
    declared = set(re.findall(r'id="([^"]+)"', markup))
    used = set(re.findall(r"getElementById\(['\"]([^'\"]+)['\"]\)", INDEX_HTML))
    used |= set(re.findall(r"\$\(['\"]([^'\"]+)['\"]\)", INDEX_HTML))
    assert used, "the review screen has no script left in it"
    assert not (used - declared), f"script reaches for missing ids: {sorted(used - declared)}"


def test_the_ui_carries_no_external_reference():
    """The screen shows customer source; it must not phone anywhere."""
    import re

    from formslang.ui import INDEX_HTML

    lowered = INDEX_HTML.lower()
    for marker in ("https://", "//cdn", "fonts.googleapis", "integrity="):
        assert marker not in lowered, f"external reference in the review UI: {marker}"
    # The SVG namespace in the favicon is an identifier, never fetched;
    # any other http URL in the page would be a real reference.
    urls = re.findall(r"http://[^\s'\"\)%>]+", lowered)
    assert urls and all(u.startswith("http://www.w3.org/") for u in urls), urls


def test_the_picker_has_a_primary_native_file_action_and_drop_target():
    from formslang.ui import INDEX_HTML

    assert "Select FMB / XML" in INDEX_HTML
    assert 'accept=".fmb,.mmb,.xml"' in INDEX_HTML
    assert 'class="dropzone"' in INDEX_HTML
    assert "uploadModule" in INDEX_HTML


# -- picking the module to convert ---------------------------------------


@pytest.fixture()
def picker(tmp_path, sample_xml):
    """A workbench with nothing open yet, rooted at a folder of modules."""
    forms = tmp_path / "forms"
    (forms / "sub").mkdir(parents=True)
    (forms / "ORDERS.xml").write_text(sample_xml.read_text(encoding="utf-8"), encoding="utf-8")
    (forms / "LEGACY.fmb").write_bytes(b"\x00binary\x00")
    (forms / "notes.txt").write_text("not a module", encoding="utf-8")

    store = Store(tmp_path / "empty.session.db")
    wb = Workbench(
        store, EchoProvider(), tmp_path / "out" / "export",
        out_dir=tmp_path / "out", browse_root=forms,
    )
    try:
        yield wb, forms
    finally:
        wb.store.close()


def test_browse_lists_modules_and_folders_and_nothing_else(picker):
    wb, forms = picker
    listing = wb.browse()

    assert [d["name"] for d in listing["dirs"]] == ["sub"]
    assert sorted(m["name"] for m in listing["modules"]) == ["LEGACY.fmb", "ORDERS.xml"]
    assert "notes.txt" not in json.dumps(listing)
    # Names travel; code does not. Reading a module takes an explicit open.
    assert "TriggerText" not in json.dumps(listing)
    assert listing["parent"] == str(forms.parent)


def test_browse_refuses_something_that_is_not_a_folder(picker):
    wb, forms = picker
    with pytest.raises(ValueError, match="not a folder"):
        wb.browse(str(forms / "ORDERS.xml"))


def test_opening_a_module_replaces_what_is_on_screen(picker):
    wb, forms = picker
    assert wb.store.stats()["tasks"] == 0

    result = wb.open_module(str(forms / "ORDERS.xml"))

    assert result["title"] == "DEMO_ORDER"
    assert result["added"] > 0
    assert wb.store.stats()["tasks"] == result["added"]
    assert wb.state()["session"]["title"] == "DEMO_ORDER"


def test_the_session_lands_in_our_folder_never_beside_the_customer_source(picker):
    """Conversion output must not appear inside the customer's tree."""
    wb, forms = picker
    wb.open_module(str(forms / "ORDERS.xml"))

    assert (wb.out_dir / "DEMO_ORDER.session.db").exists()
    assert not list(forms.glob("*.db"))
    assert wb.export_dir.parent == wb.out_dir


def test_reopening_the_same_module_resumes_instead_of_duplicating(picker):
    wb, forms = picker
    first = wb.open_module(str(forms / "ORDERS.xml"))
    again = wb.open_module(str(forms / "ORDERS.xml"))

    assert again["added"] == 0
    assert again["stats"]["tasks"] == first["stats"]["tasks"]


def test_opening_something_that_is_not_a_forms_module_is_refused(picker):
    wb, forms = picker
    with pytest.raises(ValueError, match="not a Forms module"):
        wb.open_module(str(forms / "notes.txt"))
    with pytest.raises(ValueError, match="not a file"):
        wb.open_module(str(forms / "nope.fmb"))


def test_no_module_swap_while_a_conversion_is_running(picker):
    """Swapping the store mid-job would have the job writing into the old one."""
    wb, forms = picker
    wb.job = {"running": True, "done": 0, "total": 3, "error": ""}
    with pytest.raises(ValueError, match="wait for it to finish"):
        wb.open_module(str(forms / "ORDERS.xml"))
    with pytest.raises(ValueError, match="wait for it to finish"):
        wb.set_provider("echo")


def test_the_browser_and_the_open_are_reachable_over_http(server, tmp_path, sample_xml):
    base, _wb = server
    other = tmp_path / "elsewhere"
    other.mkdir()
    (other / "SECOND.xml").write_text(sample_xml.read_text(encoding="utf-8"), encoding="utf-8")

    status, raw = _get(base, "/api/browse?dir=" + str(other).replace("\\", "%5C"))
    assert status == 200
    assert [m["name"] for m in json.loads(raw)["modules"]] == ["SECOND.xml"]

    status, body = _post(base, "/api/open", {"path": str(other / "SECOND.xml")})
    assert status == 200
    assert body["title"] == "DEMO_ORDER"

    status, body = _post(base, "/api/open", {"path": str(other / "ghost.fmb")})
    assert status == 400
    assert "not a file" in body["error"]


def test_a_browser_selected_xml_is_staged_and_opened(server, sample_xml):
    base, wb = server
    status, body = _upload(base, "SELECTED.xml", sample_xml.read_bytes())

    assert status == 200
    assert body["title"] == "DEMO_ORDER"
    assert (wb.out_dir / "uploads" / "SELECTED.xml").exists()
    assert wb.state()["session"]["source_path"].endswith("SELECTED.xml")


def test_an_unsafe_or_unsupported_upload_name_is_refused(server):
    base, _ = server
    status, body = _upload(base, "notes.txt", b"not a form")
    assert status == 400
    assert ".fmb" in body["error"]


# -- picking the model ---------------------------------------------------


def test_the_model_can_be_swapped_mid_session(server):
    base, wb = server
    status, body = _post(base, "/api/provider", {"provider": "ollama", "model": "llama3.3"})

    assert status == 200
    assert "llama3.3" in body["provider"]
    assert wb.provider.type_id == "ollama"
    assert json.loads(_get(base, "/api/state")[1])["model"] == "llama3.3"


def test_an_unknown_model_choice_is_refused_and_the_old_one_survives(server):
    base, wb = server
    status, body = _post(base, "/api/provider", {"provider": "not_a_provider"})

    assert status == 400
    assert "unknown AI provider" in body["error"]
    assert wb.provider.type_id == "echo"  # still the one that was working


def test_the_api_key_never_reaches_the_browser(server, monkeypatch):
    """The key lives in the server's environment and stays there."""
    base, wb = server
    monkeypatch.setenv("FORMSLANG_AI_KEY", "sk-do-not-leak-me")

    _post(base, "/api/provider", {"provider": "anthropic", "model": "claude-sonnet-4-6"})
    seen = _get(base, "/api/state")[1].decode() + _get(base, "/api/providers")[1].decode()

    assert "sk-do-not-leak-me" not in seen
    assert wb.provider.api_key == "sk-do-not-leak-me"  # the server does hold it


def test_the_picker_is_offered_every_provider(server):
    base, _ = server
    ids = [p["id"] for p in json.loads(_get(base, "/api/providers")[1])["providers"]]
    assert {"anthropic", "claude_cli", "codex_cli", "echo", "ollama"} <= set(ids)


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


# -- exported ZIPs: the list and the reveal --------------------------------


def test_exports_are_listed_newest_first(server):
    base, wb = server
    status, body = _get(base, "/api/exports")
    assert status == 200
    assert json.loads(body) == {"exports": [], "dir": str(wb.export_dir)}

    wb.export_dir.mkdir(parents=True, exist_ok=True)
    old = wb.export_dir / "old-app.apex.zip"
    new = wb.export_dir / "new-app.apex.zip"
    old.write_bytes(b"PK-old")
    new.write_bytes(b"PK-new-longer")
    stamp = old.stat().st_mtime
    os.utime(old, (stamp - 100, stamp - 100))
    (wb.export_dir / "notes.txt").write_text("not a zip", encoding="utf-8")

    status, body = _get(base, "/api/exports")
    data = json.loads(body)
    assert status == 200
    assert [e["name"] for e in data["exports"]] == ["new-app.apex.zip", "old-app.apex.zip"]
    assert data["exports"][0]["size"] == len(b"PK-new-longer")


def test_reveal_refuses_traversal_and_misses(server):
    base, wb = server
    wb.export_dir.mkdir(parents=True, exist_ok=True)
    # A secret OUTSIDE the export dir, named like an export.
    secret = wb.export_dir.parent / "secret.apex.zip"
    secret.write_bytes(b"PK")
    for name in ("../secret.apex.zip", "..\secret.apex.zip", "ghost.apex.zip", "notes.txt", ""):
        status, data = _post(base, "/api/exports/open", {"name": name})
        assert status == 400, name
        assert "no such export" in data["error"], name
