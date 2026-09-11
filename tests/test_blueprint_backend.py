"""Request lifetime, source isolation and bounded Blueprint projections."""

import json
import sqlite3
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from formslang import blueprint, blueprint_ai, blueprint_view
from formslang.ai import EchoProvider
from formslang.convert import build_tasks
from formslang.model import Block, FormModule, Item, Trigger
from formslang.store import APPROVED, Store
from formslang.workbench import Handler, Workbench


class ControlledProvider(EchoProvider):
    type_id = "test"

    def __init__(self):
        super().__init__()
        self.entered = threading.Event()
        self.release = threading.Event()
        self.calls = 0

    def complete(self, messages, **kwargs):
        self.calls += 1
        self.entered.set()
        assert self.release.wait(10), "test did not release provider"
        return json.dumps({"sections": [{"title": "Investigate", "text": "Inspect the observed dependencies.", "components": []}]})


@pytest.fixture()
def wb(tmp_path):
    store = Store(tmp_path / "session.db")
    store.save_blueprint(blueprint.build([FormModule(name="DEMO", triggers=[Trigger("KEY-COMMIT", "COMMIT_FORM;", "form", "")])]))
    instance = Workbench(store, ControlledProvider(), tmp_path / "export")
    try:
        yield instance
    finally:
        instance.provider.release.set()
        store.close()


def request_body(wb, **extra):
    return {"scope": "application", "background": True,
            "source_revision": wb.blueprint_payload()["source_revision"], **extra}


def settle(wb, job_id):
    wb.provider.release.set()
    # Wait on the Workbench mutex, never an arbitrary sleep or network timeout.
    deadline = threading.Event()
    timer = threading.Timer(5, deadline.set)
    timer.start()
    try:
        while not deadline.is_set():
            state = wb.blueprint_ai_state(job_id=job_id)
            if state["status"] != "running" and wb._blueprint_ai_active is None:
                return state
            deadline.wait(0.01)
    finally:
        timer.cancel()
    pytest.fail("AI job did not settle")


def test_background_explanation_deduplicates_and_reattaches(wb):
    body = request_body(wb)
    job = wb.start_blueprint_ai(body)
    assert job["status"] == "running"
    assert wb.provider.entered.wait(2)
    assert wb.start_blueprint_ai(body)["job_id"] == job["job_id"]
    assert wb.blueprint_ai_state()["job_id"] == job["job_id"]
    with pytest.raises(ValueError, match="explanation is still running"):
        wb.start_job([])
    done = settle(wb, job["job_id"])
    assert done["status"] == "completed" and done["result"]["status"] == "PROPOSAL"
    assert wb.start_blueprint_ai(body)["job_id"] == job["job_id"]
    assert wb.provider.calls == 1
    assert wb.blueprint_payload()["summary"]["review"].get("APPROVE", 0) == 0


def test_cancel_discards_result_without_releasing_provider_guard(wb):
    body = request_body(wb)
    job = wb.start_blueprint_ai(body)
    assert wb.provider.entered.wait(2)
    assert wb.cancel_blueprint_ai(job["job_id"])["status"] == "cancelled"
    with pytest.raises(ValueError, match="still running"):
        wb.start_blueprint_ai(body)
    done = settle(wb, job["job_id"])
    assert done["status"] == "cancelled" and "result" not in done


def test_explanations_are_bound_to_actor_source_session_and_provider(wb, tmp_path):
    original = wb.store
    body = request_body(wb)
    actor = ("token", {"active_org_id": "org", "user_id": "owner"}, {})
    stranger = ("other", {"active_org_id": "org", "user_id": "stranger"}, {})
    job = wb.start_blueprint_ai(body, actor)
    assert wb.provider.entered.wait(2)
    assert wb.blueprint_ai_state(job_id=job["job_id"], auth=stranger) == {"status": "stale"}
    with pytest.raises(ValueError, match="no longer available"):
        wb.cancel_blueprint_ai(job["job_id"], stranger)
    second = Store(tmp_path / "other.db")
    second.save_blueprint(wb.blueprint_payload())  # identical source is still a different session
    try:
        wb.store = second
        assert wb.blueprint_ai_state(job_id=job["job_id"], auth=actor) == {"status": "stale"}
        wb.store = original
        wb.provider.model = "different-model"
        assert wb.blueprint_ai_state(auth=actor) == {"status": "idle"}
        wb.provider.model = EchoProvider.default_model
        changed = blueprint.build([FormModule(name="CHANGED")])
        wb.store.save_blueprint(changed)
        assert wb.blueprint_ai_state(job_id=job["job_id"], auth=actor) == {"status": "stale"}
        with pytest.raises(ValueError, match="changed"):
            wb.start_blueprint_ai(body, actor)
    finally:
        wb.store = original
        second.close()
        settle(wb, job["job_id"])


def test_payload_cache_observes_local_reviews_and_external_commits(wb, monkeypatch):
    loads = 0
    original = wb.store.blueprint

    def counted():
        nonlocal loads
        loads += 1
        return original()

    monkeypatch.setattr(wb.store, "blueprint", counted)
    payload = wb.blueprint_payload()
    wb.blueprint_state()
    wb.blueprint_payload()
    assert loads == 1
    finding = payload["findings"][0]
    wb.store.review_blueprint(entity=finding["entity"], revision=finding["revision"], action="DEFER",
                              reviewer="human", comment="Investigate")
    assert wb.blueprint_payload()["summary"]["review"]["DEFER"] == 1
    assert loads == 3  # review itself also deliberately reads the current snapshot
    with sqlite3.connect(wb.store.path) as external:
        external.execute("DELETE FROM blueprint_review")
    assert "DEFER" not in wb.blueprint_payload()["summary"]["review"]
    assert loads == 4


def test_explorer_omits_unselected_source_and_preserves_selected_body():
    source = "BEGIN " + "MESSAGE('long source'); " * 1000 + "END;"
    payload = blueprint.build([FormModule(name="DEMO", triggers=[Trigger("WHEN-NEW-FORM-INSTANCE", source, "form", "")])])
    node = next(n for n in payload["entities"] if n["type"] == "TRIGGER")
    page = blueprint.explore(payload)
    assert "source_text" not in json.dumps(page)
    detail = blueprint.explore(payload, node=node["id"])["selected"]
    assert detail["source_context"]["text"] == source
    assert "source_text" not in json.dumps(detail["neighbors"])
    assert node["attributes"]["source_text"] == source


def test_connection_sample_is_diverse_deterministic_and_bounded():
    triggers = [Trigger(f"KEY-COMMIT-{i:02}", "COMMIT_FORM;", "form", "") for i in range(80)]
    triggers.append(Trigger("WHEN-VALIDATE-ITEM", "BEGIN SELECT id INTO :b.id FROM orders; domain_pkg.validate; END;", "form", ""))
    payload = blueprint.build([FormModule(name="DEMO", triggers=triggers)])
    guide = blueprint_view.overview(payload)
    assert len(guide["paths"]) == 24 and guide["path_total"] > 24
    assert {p["relationship"] for p in guide["paths"][:4]} >= {"COMMITS", "READS", "CALLS"}
    payload["edges"].reverse()
    assert blueprint_view.overview(payload)["paths"] == guide["paths"]


def test_provider_validation_errors_do_not_expose_provider_details():
    class Failing(EchoProvider):
        def complete(self, *args, **kwargs):
            raise ValueError("private endpoint secret-key source-name")

    payload = blueprint.build([FormModule(name="DEMO", triggers=[Trigger("KEY-COMMIT", "COMMIT_FORM;", "form", "")])])
    with pytest.raises(ValueError, match="AI provider failed") as exc:
        blueprint_ai.review(payload, payload["findings"][0]["entity"], Failing())
    assert "secret-key" not in str(exc.value)


@pytest.fixture()
def http_request(wb):
    handler = type("BoundHandler", (Handler,), {"workbench": wb})
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{httpd.server_port}"

    def request(path, body=None):
        req = urllib.request.Request(base + path, data=None if body is None else json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=2) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as exc:
            return exc.code, json.load(exc)

    try:
        yield request
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_http_background_status_and_context_guards(wb, http_request):
    request = http_request
    status, state = request("/api/blueprint")
    assert status == 200 and state["context_id"]
    assert request("/api/blueprint/ai", request_body(wb, context_id="another-session"))[0] == 400
    for path in ("/api/blueprint/explore", "/api/blueprint/ai"):
        assert request(path + "?context_id=another-session")[0] == 400
        assert request(path + "?context_id=" + state["context_id"])[0] == 200
    status, job = request("/api/blueprint/ai", request_body(wb, context_id=state["context_id"]))
    assert status == 202 and job["status"] == "running"
    assert request("/api/blueprint/ai?job_id=" + job["job_id"])[1]["status"] == "running"
    assert request("/api/blueprint/review", ["not", "an", "object"])[0] == 400
    assert request("/api/blueprint/export", {"context_id": "another-session"})[0] == 400
    assert request("/api/blueprint/ai/cancel", {"job_id": job["job_id"]})[1]["status"] == "cancelled"
    settle(wb, job["job_id"])


def test_conversion_requests_cannot_cross_sessions_with_identical_tasks(wb, http_request, tmp_path, monkeypatch):
    module = FormModule(name="DEMO", triggers=[Trigger("KEY-COMMIT", "COMMIT_FORM;", "form", "")])
    tasks = build_tasks(module)
    original = wb.store
    original.add_tasks(tasks)
    first = http_request("/api/state")[1]
    starts = []
    monkeypatch.setattr(wb, "start_job", lambda ids: starts.append(ids) or True)
    second = Store(tmp_path / "second.db")
    second.add_tasks(tasks)
    try:
        with wb._lock:
            wb.store = second
        current = http_request("/api/state")[1]
        assert current["tasks"][0]["id"] == first["tasks"][0]["id"]
        assert current["context_id"] != first["context_id"]
        decision = {"task_id": tasks[0].id, "state": APPROVED, "code": "NULL;",
                    "reviewer": "human", "context_id": first["context_id"]}
        assert http_request("/api/decision", decision)[0] == 400
        assert http_request("/api/propose", {"all": True, "context_id": first["context_id"]})[0] == 400
        assert not starts
        assert second.view(tasks[0].id).state != APPROVED
        decision["context_id"] = current["context_id"]
        assert http_request("/api/decision", decision)[0] == 200
        assert second.view(tasks[0].id).state == APPROVED
        assert http_request("/api/propose", {"task_id": tasks[0].id, "context_id": current["context_id"]})[0] == 200
        assert starts == [[tasks[0].id]]
        assert original.view(tasks[0].id).state != APPROVED
    finally:
        with wb._lock:
            wb.store = original
        second.close()


def test_initial_blueprint_state_can_pin_its_first_build(wb, http_request):
    wb.store.db.execute("DELETE FROM blueprint_snapshot")
    wb.store.db.commit()
    state = http_request("/api/blueprint")[1]
    assert not state["available"] and state["context_id"] == http_request("/api/state")[1]["context_id"]
    assert http_request("/api/blueprint/build", {"context_id": "stale-context"})[0] == 400


def test_rule_projection_retains_owner_without_changing_source_graph():
    trigger = Trigger("WHEN-VALIDATE-ITEM", "IF :ORDERS.AMOUNT < 0 THEN RAISE FORM_TRIGGER_FAILURE; END IF;",
                      "item", "ORDERS.AMOUNT")
    module = FormModule(name="DEMO", blocks=[Block("ORDERS", items=[Item("AMOUNT", triggers=[trigger])])])
    payload = blueprint.build([module])
    before = blueprint.canonical(payload)
    rules = blueprint.explore(payload, entity_type="BUSINESS_RULE")["nodes"]
    assert len(rules) == 1 and rules[0]["attributes"]["owner"] == "ORDERS.AMOUNT"
    detail = blueprint.explore(payload, node=rules[0]["id"])["selected"]
    assert detail["entity"]["attributes"]["owner"] == detail["source_context"]["owner"] == "ORDERS.AMOUNT"
    assert any(e["type"] == "CONTAINS" for e in detail["inbound"])
    assert not detail["outbound"]
    assert blueprint.canonical(payload) == before


def test_individual_ai_explanation_bounds_its_dependency_sample():
    calls = "BEGIN " + " ".join(f"pkg_{i}.validate;" for i in range(150)) + " END;"
    payload = blueprint.build([FormModule(name="DEMO", triggers=[Trigger("WHEN-NEW-FORM-INSTANCE", calls, "form", "")])])
    unit = next(n for n in payload["entities"] if n["type"] == "TRIGGER")
    response = blueprint_ai.review(payload, unit["id"], EchoProvider())
    assert len(response["sent"]["dependencies"]) == 128
    assert response["sent"]["scope_limits"]["dependency_total"] >= 150
    assert response["sent"]["scope_limits"]["dependencies_shown"] == 128
    assert not response["sent"]["scope_limits"]["source_code_included"]


def test_conversion_context_is_also_bound_to_authenticated_actor(wb):
    owner = ("token", {"active_org_id": "org", "user_id": "owner"}, {})
    other = ("token2", {"active_org_id": "org", "user_id": "other"}, {})
    context = wb.state(owner)["context_id"]
    assert context == wb.blueprint_state(owner)["context_id"]
    assert context != wb.state(other)["context_id"] != wb.state()["context_id"]
    with wb._lock:
        wb.require_conversion_context({"context_id": context}, owner)
        with pytest.raises(ValueError, match="session changed"):
            wb.require_conversion_context({"context_id": context}, other)
        wb.require_conversion_context({}, other)  # legacy API callers remain compatible


@pytest.mark.parametrize(("route", "method", "post"), [
    ("/api/deps", "deps_state", False), ("/api/tests", "tests_state", False),
    ("/api/test-decision", "decide_test_case", True), ("/api/test-run", "record_test_run", True),
])
def test_evidence_endpoints_check_context_before_reading_or_writing(wb, http_request, monkeypatch, route, method, post):
    calls = []
    monkeypatch.setattr(wb, method, lambda *args, **kwargs: calls.append((args, kwargs)) or {"ok": True})
    context = wb.state()["context_id"]
    if post:
        rejected = http_request(route, {"context_id": "old-session", "case_id": "same-case"})
    else:
        rejected = http_request(route + "?context_id=old-session&task=same-task")
    assert rejected[0] == 400 and not calls
    if post:
        accepted = http_request(route, {"context_id": context, "case_id": "same-case"})
    else:
        accepted = http_request(route + "?context_id=" + context + "&task=same-task")
    assert accepted[0] == 200 and len(calls) == 1
