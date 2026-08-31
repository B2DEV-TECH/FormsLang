"""HTTP-layer auth surface: login/logout/whoami, CSRF, Origin, and the
brute-force/rate-limit and DNS-rebinding defenses layered on top once auth
is on (design doc SS2, SS7.2, D3)."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from formslang.ai import EchoProvider
from formslang.authstore import AuthStore
from formslang.convert import build_tasks
from formslang.parser import parse_xml
from formslang.store import Store
from formslang.workbench import Handler, Workbench

EMAIL = "owner@example.com"
PASSWORD = "correct horse battery staple"
ORIGIN = "http://127.0.0.1"


@pytest.fixture()
def server(tmp_path, sample_xml):
    auth_store = AuthStore(tmp_path / "auth.db")
    owner = auth_store.bootstrap_owner(EMAIL, PASSWORD)
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
        yield base, wb, owner
    finally:
        httpd.shutdown()
        httpd.server_close()
        store.close()
        auth_store.close()


def _get(base, path, *, cookie=None, host=None):
    headers = {}
    if cookie:
        headers["Cookie"] = f"formslang_session={cookie}"
    if host:
        headers["Host"] = host
    req = urllib.request.Request(base + path, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def _post(base, path, payload, *, cookie=None, csrf=None, origin=ORIGIN, host=None):
    headers = {"Content-Type": "application/json"}
    if origin is not None:
        headers["Origin"] = origin
    if cookie:
        headers["Cookie"] = f"formslang_session={cookie}"
    if csrf is not None:
        headers["X-CSRF-Token"] = csrf
    if host:
        headers["Host"] = host
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


def test_whoami_reports_not_authenticated_with_no_cookie(server):
    base, _wb, _owner = server
    status, body = _get(base, "/api/auth/whoami")
    assert status == 200
    assert body == {"authenticated": False}


def test_a_protected_route_refuses_an_anonymous_request(server):
    base, _wb, _owner = server
    assert _get(base, "/api/state")[0] == 401
    assert _post(base, "/api/decision", {})[0] == 401


def test_login_sets_a_session_cookie_and_whoami_reflects_it(server):
    base, _wb, owner = server
    status, body, token = _login(base, EMAIL, PASSWORD)
    assert status == 200
    assert body["ok"] is True
    assert body["active_org_id"] == owner["organization_id"]
    assert token

    status, who = _get(base, "/api/auth/whoami", cookie=token)
    assert status == 200
    assert who["authenticated"] is True
    assert who["email"] == EMAIL
    assert who["role"] == "OWNER"
    assert who["csrf_token"]


def test_a_wrong_password_is_refused_without_a_session(server):
    base, _wb, _owner = server
    status, body, token = _login(base, EMAIL, "not the password")
    assert status == 401
    assert body["ok"] is False
    assert token is None


def test_repeated_bad_logins_are_rate_limited(server):
    """D3: five failures lock the account; the sixth attempt never even
    reaches the password check."""
    base, _wb, _owner = server
    for _ in range(5):
        status, body, _token = _login(base, EMAIL, "not the password")
        assert status == 401
        assert body["reason"] == "invalid_credentials"

    status, body, _token = _login(base, EMAIL, "not the password")
    assert status == 429
    assert body["retry_after_seconds"] > 0

    # Even the *correct* password is refused while locked out.
    status, body, token = _login(base, EMAIL, PASSWORD)
    assert status == 429
    assert token is None


def test_a_mutating_request_without_a_csrf_token_is_refused(server):
    base, _wb, _owner = server
    _status, _body, token = _login(base, EMAIL, PASSWORD)

    status, body = _post(base, "/api/decision", {}, cookie=token, csrf=None)
    assert status == 403
    assert "csrf" in body["error"].lower()


def test_a_mutating_request_with_the_wrong_csrf_token_is_refused(server):
    base, _wb, _owner = server
    _status, _body, token = _login(base, EMAIL, PASSWORD)

    status, body = _post(base, "/api/decision", {}, cookie=token, csrf="not-the-real-token")
    assert status == 403
    assert "csrf" in body["error"].lower()


def test_a_mutating_request_with_the_correct_csrf_token_is_accepted(server):
    base, wb, _owner = server
    _status, _body, token = _login(base, EMAIL, PASSWORD)
    _status, who = _get(base, "/api/auth/whoami", cookie=token)
    csrf = who["csrf_token"]

    task_id = wb.store.pending_tasks()[0].id
    status, body = _post(
        base, "/api/decision",
        {"task_id": task_id, "state": "approved", "code": "NULL;"},
        cookie=token, csrf=csrf,
    )
    assert status == 200
    assert body["ok"] is True


def test_a_mutating_request_without_an_origin_header_is_refused(server):
    base, _wb, _owner = server
    _status, _body, token = _login(base, EMAIL, PASSWORD)
    _status, who = _get(base, "/api/auth/whoami", cookie=token)

    status, body = _post(
        base, "/api/decision", {}, cookie=token, csrf=who["csrf_token"], origin=None,
    )
    assert status == 403
    assert "origin" in body["error"].lower()


def test_a_mutating_request_with_a_foreign_origin_is_refused(server):
    base, _wb, _owner = server
    _status, _body, token = _login(base, EMAIL, PASSWORD)
    _status, who = _get(base, "/api/auth/whoami", cookie=token)

    status, body = _post(
        base, "/api/decision", {}, cookie=token, csrf=who["csrf_token"],
        origin="http://attacker.example.com",
    )
    assert status == 403
    assert "origin" in body["error"].lower()


def test_login_itself_still_requires_a_local_origin(server):
    """The login route is CSRF-exempt (no session exists yet) but not
    Origin-exempt -- a page on another origin cannot even start a login."""
    base, _wb, _owner = server
    status, body = _post(
        base, "/api/auth/login", {"email": EMAIL, "password": PASSWORD},
        origin="http://attacker.example.com",
    )
    assert status == 403
    assert "origin" in body["error"].lower()


def test_a_foreign_host_header_is_refused_even_with_a_valid_session(server):
    """DNS rebinding: a page that got a browser to send a request to this
    server under an attacker-controlled hostname must be refused before
    the session cookie is even looked at."""
    base, _wb, _owner = server
    _status, _body, token = _login(base, EMAIL, PASSWORD)

    status, _body = _get(base, "/api/state", cookie=token, host="attacker.example.com")
    assert status == 403


def test_an_unknown_session_cookie_is_treated_as_unauthenticated(server):
    base, _wb, _owner = server
    status, body = _get(base, "/api/auth/whoami", cookie="not-a-real-token")
    assert status == 200
    assert body == {"authenticated": False}

    assert _get(base, "/api/state", cookie="not-a-real-token")[0] == 401


def test_logout_clears_the_cookie_and_revokes_the_session(server):
    base, _wb, _owner = server
    _status, _body, token = _login(base, EMAIL, PASSWORD)
    _status, who = _get(base, "/api/auth/whoami", cookie=token)

    status, body = _post(base, "/api/auth/logout", {}, cookie=token, csrf=who["csrf_token"])
    assert status == 200
    assert body["ok"] is True

    status, who_after = _get(base, "/api/auth/whoami", cookie=token)
    assert status == 200
    assert who_after == {"authenticated": False}
    assert _get(base, "/api/state", cookie=token)[0] == 401


def test_the_auth_surface_does_not_exist_when_auth_is_off(tmp_path, sample_xml):
    """Zero-effect-when-off, proven at the HTTP boundary, not just by
    absence of a crash: the new routes 404 exactly like any other unknown
    path, and every pre-existing route behaves as it always has."""
    store = Store(tmp_path / "s.db")
    store.init_session("DEMO_ORDER", str(sample_xml))
    store.add_tasks(build_tasks(parse_xml(sample_xml)))
    wb = Workbench(store, EchoProvider(), tmp_path / "export")  # auth_store=None
    handler = type("BoundHandler", (Handler,), {"workbench": wb})
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_port}"
    try:
        assert _get(base, "/api/auth/whoami")[0] == 404
        assert _get(base, "/api/projects")[0] == 404
        assert _post(base, "/api/auth/login", {"email": EMAIL, "password": PASSWORD})[0] == 404
        # Pre-existing, unauthenticated access still works exactly as before.
        assert _get(base, "/api/state")[0] == 200
    finally:
        httpd.shutdown()
        httpd.server_close()
        store.close()
