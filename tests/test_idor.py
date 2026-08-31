"""IDOR-specific tests (design SS3): the exact distinction between "you can't
see this" (404, no existence leak) and "you can see it but can't touch it"
(403, existence already established by membership) is the whole point of
authorize_project_access, and is easy to get backwards by accident."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from formslang.ai import EchoProvider
from formslang.authstore import AuthStore, DEVELOPER, VIEWER
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


def _fresh_session_file(tmp_path, name):
    path = tmp_path / name
    s = Store(path)
    s.init_session("DEMO_ORDER")
    s.close()
    return path


def test_a_viewer_gets_403_not_404_adopting_a_project_in_their_own_org(server, tmp_path):
    """Membership already proves the project is visible to this user, so a
    role that merely lacks ADOPT_PROJECT must be a permission denial -- a 404
    here would be a lie: the caller already knows the project exists."""
    base, wb, auth_store = server
    owner = auth_store.bootstrap_owner("owner@example.com", PASSWORD)
    viewer_id = auth_store.create_user("viewer@example.com", PASSWORD)
    auth_store.create_membership(owner["organization_id"], viewer_id, VIEWER)

    project = auth_store.register_external_project(
        owner["organization_id"], "Shared project",
        _fresh_session_file(tmp_path, "shared.session.db"),
        created_by=owner["user_id"],
    )

    _status, _body, token = _login(base, "viewer@example.com", PASSWORD)
    _status, who = _get(base, "/api/auth/whoami", cookie=token)
    assert who["role"] == "VIEWER"

    status, body = _post(
        base, "/api/projects/adopt", {"project_id": project["id"]},
        cookie=token, csrf=who["csrf_token"],
    )
    assert status == 403
    assert "not found" not in body["error"].lower()


def test_a_developer_gets_403_not_404_adopting_a_project_in_their_own_org(server, tmp_path):
    base, wb, auth_store = server
    owner = auth_store.bootstrap_owner("owner2@example.com", PASSWORD)
    dev_id = auth_store.create_user("dev@example.com", PASSWORD)
    auth_store.create_membership(owner["organization_id"], dev_id, DEVELOPER)

    project = auth_store.register_external_project(
        owner["organization_id"], "Shared project 2",
        _fresh_session_file(tmp_path, "shared2.session.db"),
        created_by=owner["user_id"],
    )

    _status, _body, token = _login(base, "dev@example.com", PASSWORD)
    _status, who = _get(base, "/api/auth/whoami", cookie=token)
    assert who["role"] == "DEVELOPER"

    status, body = _post(
        base, "/api/projects/adopt", {"project_id": project["id"]},
        cookie=token, csrf=who["csrf_token"],
    )
    assert status == 403


def test_a_project_id_belonging_to_another_org_is_404_not_403(server, tmp_path):
    """The flip side: an Owner (full ADOPT_PROJECT rights in their own org)
    pointing at a project_id from an org they are not a member of gets a
    404 -- the role check never even runs, because membership itself is
    what's missing, and existence must not be revealed."""
    base, wb, auth_store = server
    owner_a = auth_store.bootstrap_owner("ownera@example.com", PASSWORD, org_slug="org-a", org_name="A")
    org_b = auth_store.create_organization("org-b", "B")
    owner_b_id = auth_store.create_user("ownerb@example.com", PASSWORD)
    auth_store.create_membership(org_b, owner_b_id, "OWNER")

    other_org_project = auth_store.register_external_project(
        org_b, "Org B project", _fresh_session_file(tmp_path, "orgb.session.db"),
        created_by=owner_b_id,
    )

    _status, _body, token = _login(base, "ownera@example.com", PASSWORD)
    _status, who = _get(base, "/api/auth/whoami", cookie=token)
    assert who["role"] == "OWNER"

    status, body = _post(
        base, "/api/projects/adopt", {"project_id": other_org_project["id"]},
        cookie=token, csrf=who["csrf_token"],
    )
    assert status == 404


def test_a_nonexistent_project_id_is_also_404(server):
    base, wb, auth_store = server
    owner = auth_store.bootstrap_owner("owner3@example.com", PASSWORD)
    _status, _body, token = _login(base, "owner3@example.com", PASSWORD)
    _status, who = _get(base, "/api/auth/whoami", cookie=token)

    status, body = _post(
        base, "/api/projects/adopt", {"project_id": "not-a-real-id"},
        cookie=token, csrf=who["csrf_token"],
    )
    assert status == 404


def test_an_unauthenticated_request_to_list_projects_is_401(server):
    base, wb, auth_store = server
    status, _body = _get(base, "/api/projects")
    assert status == 401


def test_an_unauthenticated_adopt_attempt_is_401_not_a_leak(server, tmp_path):
    base, wb, auth_store = server
    owner = auth_store.bootstrap_owner("owner4@example.com", PASSWORD)
    project = auth_store.register_external_project(
        owner["organization_id"], "Some project",
        _fresh_session_file(tmp_path, "some.session.db"),
        created_by=owner["user_id"],
    )
    status, body = _post(base, "/api/projects/adopt", {"project_id": project["id"]})
    assert status == 401
