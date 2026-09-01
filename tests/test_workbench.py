"""The local server: routes, refusals, and where files land.

The workbench holds the source under review, so the tests that matter most here are
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

from formslang import testspec
from formslang.ai import EchoProvider
from formslang.cli import _work_dir
from formslang.convert import build_tasks
from formslang.parser import parse_xml
from formslang.store import APPROVED, JOB_CANCELLED, Store
from formslang.workbench import Handler, Workbench

NEWLINE = chr(10)


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
    """The screen shows the source under review; it must not phone anywhere."""
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


def test_the_session_lands_in_our_folder_never_beside_the_source(picker):
    """Conversion output must not appear inside the source tree."""
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


def test_a_sensitive_finding_never_echoes_its_own_secret_over_http(server):
    """The finding is redacted wherever it surfaces -- the editor pane is not the finding.

    The task's ``source`` field legitimately carries the user's own Forms
    code back to their own editor -- that is the product. What must never
    happen is the *scanner's own output* repeating the raw value it
    matched: see formslang/sensitive.py's ``redact()`` and the module
    docstring in formslang/policy.py.
    """
    base, wb = server
    from formslang.analysis import analyze_task
    from formslang.convert import ConversionTask

    task = ConversionTask(
        id="U_SECRET", module="DEMO_ORDER", kind="trigger", name="U_SECRET",
        owner="", verdict="DIRECT_EQUIVALENT", apex_hint="",
        source=NEWLINE.join([
            "BEGIN",
            "  GRANT CONNECT TO scott IDENTIFIED BY tiger123;",
            "END;",
            "",
        ]),
        lines=3,
    )
    wb.store.add_tasks([task])
    wb.store.save_analysis(analyze_task(task))

    body = json.loads(_get(base, "/api/state")[1])
    view = next(t for t in body["tasks"] if t["id"] == "U_SECRET")

    # The source pane is allowed to show the user their own code, secret included.
    assert "tiger123" in view["source"]

    # The scanner's own findings must not repeat it.
    findings = view["analysis"]["sensitive"]["findings"]
    assert findings, "expected the credential scan to fire on this fixture"
    dumped = json.dumps(findings)
    assert "tiger123" not in dumped
    assert "CREDENTIAL" in dumped


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
    for name in ("../secret.apex.zip", r"..\secret.apex.zip", "ghost.apex.zip", "notes.txt", ""):
        status, data = _post(base, "/api/exports/open", {"name": name})
        assert status == 400, name
        assert "no such export" in data["error"], name


def test_the_job_names_the_unit_being_converted(server):
    """A run that reports only "0 of 6" is indistinguishable from a hang.
    The job has to name the unit in flight and the ones still queued, so
    the screen can show a spinner where the work actually is."""
    _base, wb = server
    gate = threading.Event()

    class SlowProvider(EchoProvider):
        def complete(self, messages, max_tokens=4096):
            gate.wait(10)
            return super().complete(messages, max_tokens)

    wb.provider = SlowProvider()
    ids = wb.store.task_ids()[:2]
    assert wb.start_job(ids) is True
    try:
        stop = threading.Event()
        threading.Timer(10, stop.set).start()
        while not stop.is_set() and not wb.job_state()["current_id"]:
            stop.wait(0.02)
        job = wb.job_state()
        assert job["current_id"] == ids[0]
        assert job["current"], "the unit in flight must carry a name to show"
        assert job["queue"] == ids, "nothing has finished yet"
        assert job["provider"] == wb.provider.label
    finally:
        gate.set()
    done = _wait_for_job(wb)
    assert done["done"] == 2
    assert done["queue"] == [] and done["current"] == "" and done["current_id"] == ""


def test_an_idle_job_has_the_same_shape_as_a_running_one(server):
    """A reader polling before the first run must not have to tell a
    missing field from an empty one."""
    base, wb = server
    idle = wb.job_state()
    assert idle["running"] is False
    assert set(idle) == {
        "running", "done", "failed", "total", "error", "last_error", "run_id",
        "current", "current_id", "queue", "provider", "last_run",
    }
    status, _ = _post(base, "/api/propose", {"all": True})
    assert status == 200
    assert set(_wait_for_job(wb)) == set(idle)


def test_the_job_queue_is_handed_out_as_a_copy(server):
    """The queue crosses a thread boundary on every poll; handing out the
    live list would let a reader corrupt the run it is watching."""
    _base, wb = server
    ids = wb.store.task_ids()[:2]
    wb.job = {
        "running": True, "done": 0, "failed": 0, "total": 2, "error": "",
        "last_error": "", "current": "", "current_id": "", "queue": list(ids),
    }
    snapshot = wb.job_state()
    snapshot["queue"].append("intruder")
    assert wb.job_state()["queue"] == list(ids)

    wb._job_advance(ids[0], error="boom")
    after = wb.job_state()
    assert after["done"] == 1 and after["failed"] == 1
    assert after["last_error"] == "boom"
    assert after["queue"] == [ids[1]]


def test_cancel_lets_the_unit_in_flight_finish_and_skips_the_rest(server):
    """Cancellation is only ever checked between tasks -- the unit already
    being converted when cancel is requested must still get its proposal
    saved, so a cancel can never leave a half written proposal behind."""
    base, wb = server
    gate = threading.Event()

    class SlowProvider(EchoProvider):
        def complete(self, messages, max_tokens=4096):
            gate.wait(10)
            return super().complete(messages, max_tokens)

    wb.provider = SlowProvider()
    ids = wb.store.task_ids()[:3]
    assert wb.start_job(ids) is True
    try:
        stop = threading.Event()
        threading.Timer(10, stop.set).start()
        while not stop.is_set() and not wb.job_state()["current_id"]:
            stop.wait(0.02)
        assert wb.job_state()["current_id"] == ids[0]

        status, body = _post(base, "/api/job/cancel", {})
        assert status == 200 and body["ok"] is True
    finally:
        gate.set()  # let the in-flight unit finish now that cancel is requested

    done = _wait_for_job(wb)
    assert done["done"] == 1
    assert wb.store.latest_proposal(ids[0]) is not None
    assert wb.store.latest_proposal(ids[1]) is None
    assert wb.store.latest_proposal(ids[2]) is None

    run = wb.store.last_job_run()
    assert run["status"] == JOB_CANCELLED
    assert run["done"] == 1


def test_cancelling_with_no_job_running_is_a_400_not_a_crash(server):
    base, _wb = server
    status, body = _post(base, "/api/job/cancel", {})
    assert status == 400
    assert "no conversion is running" in body["error"]


def test_job_state_carries_the_last_run_after_a_normal_completion(server):
    base, wb = server
    task_id = wb.store.task_ids()[0]
    status, _ = _post(base, "/api/propose", {"task_id": task_id})
    assert status == 200
    done = _wait_for_job(wb)
    assert done["last_run"]["status"] == "completed"
    assert done["last_run"]["done"] == 1


def test_a_refusal_stays_readable_with_a_body_attached(server):
    """A refusal that answers without emptying the socket gets the
    connection reset on the way back, and the client sees a dropped
    connection instead of the 415 it was just sent."""
    base, _wb = server
    for _ in range(5):
        req = urllib.request.Request(
            base + "/api/propose", data=b"x" * 200_000,
            headers={"Content-Type": "text/plain"}, method="POST",
        )
        with pytest.raises(urllib.error.HTTPError) as err:
            urllib.request.urlopen(req, timeout=10)
        assert err.value.code == 415


def test_deps_answers_for_the_unit_on_screen(server):
    """The graph is fetched per selection, never shipped with every task."""
    base, wb = server
    task_id = wb.store.task_ids()[0]
    status, body = _get(base, "/api/deps?task=" + task_id + "&depth=2")
    out = json.loads(body)
    assert status == 200
    assert out["available"] is True
    assert out["summary"]["nodes"] > 0
    assert out["explore"]["node"]["task_id"] == task_id


def test_deps_without_a_task_is_the_module_rollup_alone(server):
    base, _wb = server
    out = json.loads(_get(base, "/api/deps")[1])
    assert out["available"] is True and "explore" not in out
    assert out["summary"]["module"] == "DEMO_ORDER"


def test_deps_for_a_task_nobody_has_heard_of_is_empty_not_a_crash(server):
    base, _wb = server
    out = json.loads(_get(base, "/api/deps?task=deadbeef")[1])
    assert out["available"] is True and out["explore"] == {}


def test_deps_admits_when_there_is_no_graph_at_all(tmp_path):
    """Saying so beats an empty explorer, which reads as no dependencies."""
    store = Store(tmp_path / "empty.db")
    store.init_session("NO_SOURCE", "")
    try:
        wb = Workbench(store, EchoProvider(), tmp_path / "export")
        out = wb.deps_state()
        assert out["available"] is False and out["reason"]
    finally:
        store.close()


def test_the_graph_outlives_the_xml_it_was_built_from(tmp_path, sample_xml):
    """A session reopened from its .db alone still explains its dependencies."""
    db = tmp_path / "s.db"
    store = Store(db)
    store.init_session("DEMO_ORDER", str(sample_xml))
    store.add_tasks(build_tasks(parse_xml(sample_xml)))
    before = Workbench(store, EchoProvider(), tmp_path / "export").deps_state()["summary"]
    store.close()

    sample_xml.unlink()
    store = Store(db)
    try:
        wb = Workbench(store, EchoProvider(), tmp_path / "export")
        assert wb.module is None, "the source is gone; only the session remains"
        assert wb.deps_state()["summary"] == before
    finally:
        store.close()


def test_tests_are_written_for_the_whole_session_the_moment_it_opens(server):
    """Deterministic and offline: no provider, no proposal, no waiting."""
    _base, wb = server
    coverage = wb.store.test_coverage()
    assert coverage["tasks"] > 0
    assert coverage["specified"] == coverage["tasks"]
    assert coverage["missing"] == 0
    assert coverage["total"] > coverage["tasks"], "more than one case per unit"


def test_the_specification_of_the_unit_on_screen_is_fetched_on_demand(server):
    base, wb = server
    task_id = wb.store.task_ids()[0]
    status, body = _get(base, "/api/tests?task=" + task_id)
    out = json.loads(body)
    assert status == 200
    assert out["cases"] and all(c["task_id"] == task_id for c in out["cases"])
    assert out["coverage"]["specified"] == out["coverage"]["tasks"]
    assert out["item_metadata"] is True
    assert set(out["states"]) == set(testspec.CASE_STATES)


def test_asking_for_no_unit_returns_the_rollup_without_the_cases(server):
    base, _wb = server
    out = json.loads(_get(base, "/api/tests")[1])
    assert "cases" not in out
    assert out["coverage"]["total"] > 0


def test_a_reviewer_decision_on_a_case_is_recorded_and_counted(server):
    base, wb = server
    task_id = wb.store.task_ids()[0]
    case_id = wb.store.test_cases(task_id)[0]["id"]
    status, out = _post(base, "/api/test-decision", {
        "case_id": case_id, "state": "accepted",
        "reviewer": "geraldo", "comment": "matches production",
    })
    assert status == 200 and out["ok"] is True
    assert out["coverage"]["states"]["accepted"] == 1
    stored = {c["id"]: c for c in wb.store.test_cases(task_id)}[case_id]
    assert stored["state"] == "accepted"
    assert stored["reviewer"] == "geraldo" and stored["decided_at"]


def test_an_invented_reviewer_state_is_refused(server):
    base, wb = server
    case_id = wb.store.test_cases(wb.store.task_ids()[0])[0]["id"]
    status, out = _post(base, "/api/test-decision", {"case_id": case_id, "state": "lgtm"})
    assert status == 400 and out["error"] == "unknown state"


def test_deciding_a_case_that_does_not_exist_is_a_404(server):
    base, _wb = server
    status, out = _post(base, "/api/test-decision",
                        {"case_id": "nope", "state": "accepted"})
    assert status == 404 and out["error"] == "unknown test case"


def test_without_the_module_the_specification_says_it_could_not_check_the_items(tmp_path,
                                                                               sample_xml):
    """"Needs confirmation" must read as a limit of the input, not of the code."""
    db = tmp_path / "s.db"
    store = Store(db)
    store.init_session("DEMO_ORDER", str(sample_xml))
    store.add_tasks(build_tasks(parse_xml(sample_xml)))
    Workbench(store, EchoProvider(), tmp_path / "export")
    store.close()

    sample_xml.unlink()
    store = Store(db)
    try:
        wb = Workbench(store, EchoProvider(), tmp_path / "export")
        assert wb.module is None
        assert wb.tests_state()["item_metadata"] is False
    finally:
        store.close()


def test_the_review_screen_offers_the_three_answers_on_every_case():
    from formslang.ui import INDEX_HTML

    assert "Test cases —" in INDEX_HTML
    assert "/api/test-decision" in INDEX_HTML
    for state in testspec.CASE_STATES[1:]:
        assert f'"{state}"' in INDEX_HTML, f"no way to mark a case {state}"
    # The screen must not let a reader mistake a specification for a test run.
    assert "not executed by FormsLang" in INDEX_HTML


def test_the_project_view_is_reachable_and_counts_this_session(server):
    base, wb = server
    status, body = _get(base, "/api/dashboard")
    assert status == 200
    out = json.loads(body)
    assert out["totals"]["units"] == len(wb.store.task_ids())
    assert out["session"]["title"] == "DEMO_ORDER"
    assert 0 <= out["readiness"]["score"] <= 100


def test_the_score_never_appears_on_screen_without_its_own_arithmetic():
    """An unexplained percentage is exactly what this product must not ship."""
    from formslang import dashboard
    from formslang.ui import INDEX_HTML

    assert "/api/dashboard" in INDEX_HTML
    assert "How this number is calculated" in INDEX_HTML
    # Every weight of the published formula is printed beside the number.
    assert "readiness_model" in INDEX_HTML
    assert "m.formula" in INDEX_HTML and "m.caveat" in INDEX_HTML
    for key in (c["key"] for c in dashboard.COMPONENTS):
        assert key  # the table is data-driven; the keys travel in the payload
    # And the page says what is missing instead of hiding it in the score.
    assert "still unanalysed and counted nowhere in this chart" in INDEX_HTML
    assert "a blocker is work to do, not a percentage" in INDEX_HTML
