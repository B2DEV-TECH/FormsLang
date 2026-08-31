"""Cross-organization isolation at the HTTP boundary (design SS3, SS7.2a):
one org's session must never see, list, or act on another org's data."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from formslang.ai import EchoProvider
from formslang.authstore import AuthStore, DEVELOPER
from formslang.convert import build_tasks
from formslang.parser import parse_xml
from formslang.store import Store
from formslang.workbench import Handler, Workbench

PASSWORD = "correct horse battery staple"
ORIGIN = "http://127.0.0.1"


@pytest.fixture()
def server(tmp_path, sample_xml):
    auth_store = AuthStore(tmp_path / "auth.db")
    store = Store(tmp_path / "s.db")
    store.init_session("DEMO_ORDER", str(sample_xml))
    store.add_tasks(build_tasks(parse_xml(sample_xml)))
    wb = Workbench(
        store, EchoProvider(), tmp_path / "export",
        auth_store=auth_store, auth_data_dir=tmp_path / "data",
    )
    handler = type("BoundHandler", (Handler,), {"workbench": wb})
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_port}"
    try:
        yield base, wb, auth_store
    finally:
        httpd.shutdown()
        httpd.server_close()
        store.close()
        auth_store.close()


def _get(base, path, *, cookie=None):
    headers = {"Cookie": f"formslang_session={cookie}"} if cookie else {}
    req = urllib.request.Request(base + path, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def _post(base, path, payload, *, cookie=None, csrf=None, origin=ORIGIN):
    headers = {"Content-Type": "application/json"}
    if origin is not None:
        headers["Origin"] = origin
    if cookie:
        headers["Cookie"] = f"formslang_session={cookie}"
    if csrf is not None:
        headers["X-CSRF-Token"] = csrf
    req = urllib.request.Request(
        base + path, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def _post_capturing_cookie(base, path, payload, *, cookie=None, csrf=None, origin=ORIGIN):
    """Like _post, but also returns the raw token from a Set-Cookie
    response header, when present -- for routes that rotate the session."""
    headers = {"Content-Type": "application/json"}
    if origin is not None:
        headers["Origin"] = origin
    if cookie:
        headers["Cookie"] = f"formslang_session={cookie}"
    if csrf is not None:
        headers["X-CSRF-Token"] = csrf
    req = urllib.request.Request(
        base + path, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            status, body = r.status, json.loads(r.read())
            set_cookie = r.headers.get("Set-Cookie", "")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read()), None
    new_token = set_cookie.split(";")[0].partition("=")[2] if set_cookie else None
    return status, body, new_token


def _login(base, email, password, *, org_id=None):
    payload = {"email": email, "password": password}
    if org_id:
        payload["org_id"] = org_id
    req = urllib.request.Request(
        base + "/api/auth/login",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Origin": ORIGIN},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            status, body = r.status, json.loads(r.read())
            set_cookie = r.headers.get("Set-Cookie", "")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read()), None
    token = set_cookie.split(";")[0].partition("=")[2] if set_cookie else None
    return status, body, token


def _two_orgs(auth_store):
    """Org A (alice, owner) and Org B (bob, owner) -- fully independent."""
    alice = auth_store.bootstrap_owner("alice@a.example", PASSWORD, org_slug="org-a", org_name="A")
    org_b = auth_store.create_organization("org-b", "B")
    bob_id = auth_store.create_user("bob@b.example", PASSWORD)
    auth_store.create_membership(org_b, bob_id, "OWNER")
    return alice, {"organization_id": org_b, "user_id": bob_id, "email": "bob@b.example"}


def _login_normal(base, auth_store, user, *, org_id=None):
    """HTTP login followed by the MFA step, done at store level so these
    tests stay about tenancy, not about the MFA route (which has its own
    suite). An Owner needs this now: a fresh Owner login is MFA_PENDING or
    BOOTSTRAP_MFA, and the scope gate keeps both away from data routes."""
    from conftest import next_mfa_code, setup_confirmed_mfa

    mfa = setup_confirmed_mfa(auth_store, user["user_id"])
    _status, _body, pending = _login(base, user["email"], PASSWORD, org_id=org_id)
    code = next_mfa_code(auth_store, user["user_id"], mfa["secret"])
    return auth_store.complete_mfa_login(pending, code).session_token


def test_a_session_only_lists_projects_from_its_own_org(server, tmp_path):
    base, wb, auth_store = server
    alice, bob = _two_orgs(auth_store)

    auth_store.register_external_project(
        alice["organization_id"], "Alice's project", _fresh_session_file(tmp_path, "a.session.db"),
        created_by=alice["user_id"],
    )
    auth_store.register_external_project(
        bob["organization_id"], "Bob's project", _fresh_session_file(tmp_path, "b.session.db"),
        created_by=bob["user_id"],
    )

    alice_token = _login_normal(base, auth_store, alice)
    status, listing = _get(base, "/api/projects", cookie=alice_token)
    assert status == 200
    names = [p["name"] for p in listing["projects"]]
    assert names == ["Alice's project"]


def test_a_project_id_from_another_org_is_a_404_not_a_403(server, tmp_path):
    """The IDOR chokepoint (SS3): existence of another org's project is never
    revealed to a non-member, even one who is a fully valid, logged-in Owner
    of a different organization."""
    base, wb, auth_store = server
    alice, bob = _two_orgs(auth_store)

    bobs_project = auth_store.register_external_project(
        bob["organization_id"], "Bob's project", _fresh_session_file(tmp_path, "b.session.db"),
        created_by=bob["user_id"],
    )

    alice_token = _login_normal(base, auth_store, alice)
    _status, who = _get(base, "/api/auth/whoami", cookie=alice_token)

    status, body = _post(
        base, "/api/projects/adopt", {"project_id": bobs_project["id"]},
        cookie=alice_token, csrf=who["csrf_token"],
    )
    assert status == 404
    assert "not found" in body["error"].lower()


def test_switching_to_an_org_you_do_not_belong_to_is_refused(server):
    base, wb, auth_store = server
    alice, bob = _two_orgs(auth_store)

    alice_token = _login_normal(base, auth_store, alice)
    _status, who = _get(base, "/api/auth/whoami", cookie=alice_token)

    status, body = _post(
        base, "/api/auth/switch-org", {"org_id": bob["organization_id"]},
        cookie=alice_token, csrf=who["csrf_token"],
    )
    assert status == 400
    assert "not a member" in body["error"].lower()

    # The session must be unaffected by the refused attempt.
    status, who_after = _get(base, "/api/auth/whoami", cookie=alice_token)
    assert who_after["active_org_id"] == alice["organization_id"]


def test_switching_to_an_org_you_do_belong_to_rotates_the_session(server, tmp_path):
    base, wb, auth_store = server
    alice, bob = _two_orgs(auth_store)
    # Add Alice as a Developer of Bob's org too.
    auth_store.create_membership(bob["organization_id"], alice["user_id"], DEVELOPER)

    token = _login_normal(base, auth_store, alice, org_id=alice["organization_id"])
    _status, who = _get(base, "/api/auth/whoami", cookie=token)

    status, body, new_token = _post_capturing_cookie(
        base, "/api/auth/switch-org", {"org_id": bob["organization_id"]},
        cookie=token, csrf=who["csrf_token"],
    )
    assert status == 200
    assert body["active_org_id"] == bob["organization_id"]
    assert new_token and new_token != token

    status, who_after = _get(base, "/api/auth/whoami", cookie=new_token)
    assert who_after["active_org_id"] == bob["organization_id"]
    assert who_after["role"] == "DEVELOPER"

    # The old token was revoked by the switch -- it must no longer work.
    status, _who_old = _get(base, "/api/auth/whoami", cookie=token)
    assert _who_old == {"authenticated": False}


def _fresh_session_file(tmp_path, name):
    from formslang.store import Store as _Store

    path = tmp_path / name
    s = _Store(path)
    s.init_session("DEMO_ORDER")
    s.close()
    return path
