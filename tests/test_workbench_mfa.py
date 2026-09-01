"""The Phase 3 HTTP surface (design doc SS7, D5): the MFA and password-reset
routes, the scope gate that keeps restricted sessions off data routes, the
security headers every response carries, and the vendored QR encoder's
integrity -- its pinned SHA-256 and its zero-network guarantee.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest
from conftest import next_mfa_code, setup_confirmed_mfa

from formslang import authstore, authui, totp
from formslang.ai import EchoProvider
from formslang.authstore import AuthStore
from formslang.convert import build_tasks
from formslang.parser import parse_xml
from formslang.store import Store
from formslang.ui import INDEX_HTML
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


def _get(base, path, *, cookie=None):
    headers = {}
    if cookie:
        headers["Cookie"] = f"formslang_session={cookie}"
    req = urllib.request.Request(base + path, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def _get_raw(base, path, *, cookie=None):
    """(status, headers, body bytes) -- for header and page-identity checks."""
    headers = {}
    if cookie:
        headers["Cookie"] = f"formslang_session={cookie}"
    req = urllib.request.Request(base + path, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.status, dict(r.headers), r.read()


def _post(base, path, payload, *, cookie=None, csrf=None):
    """(status, body, new session token from Set-Cookie or None)."""
    headers = {"Content-Type": "application/json", "Origin": ORIGIN}
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
    token = set_cookie.split(";")[0].partition("=")[2] if set_cookie else None
    return status, body, token


def _login(base, email, password):
    return _post(base, "/api/auth/login", {"email": email, "password": password})


def _csrf(base, cookie):
    _status, who = _get(base, "/api/auth/whoami", cookie=cookie)
    return who["csrf_token"]


def _scope(base, cookie):
    """The session's scope, the way the overlay itself learns it: whoami.
    The login response deliberately carries only ok/active_org_id."""
    _status, who = _get(base, "/api/auth/whoami", cookie=cookie)
    return who["scope"]


def _normal_session(base, wb, user_id, email):
    """A NORMAL session for a user, MFA step done at store level."""
    mfa = setup_confirmed_mfa(wb.auth_store, user_id)
    _status, _body, pending = _login(base, email, PASSWORD)
    code = next_mfa_code(wb.auth_store, user_id, mfa["secret"])
    return wb.auth_store.complete_mfa_login(pending, code).session_token, mfa


# -- the vendored QR encoder (D5) --------------------------------------------


def test_the_vendored_qr_encoder_matches_its_pinned_hash():
    """A modified vendor file -- tampered, upgraded without review, or
    corrupted -- fails the suite before it ever reaches a browser."""
    digest = hashlib.sha256(authui._VENDOR_QR.read_bytes()).hexdigest()
    assert digest == authui.QR_SHA256


def test_the_vendored_qr_encoder_contains_no_network_or_eval_construct():
    """The zero-network guarantee (SS7.3/D5), checked against the source:
    nothing in the encoder can phone home or defeat the CSP's missing
    unsafe-eval."""
    src = authui._VENDOR_QR.read_text(encoding="utf-8")
    for forbidden in (
        "XMLHttpRequest", "fetch(", "WebSocket", "sendBeacon",
        "eval(", "new Function", "importScripts", "document.write",
    ):
        assert forbidden not in src, forbidden


def test_the_auth_page_embeds_everything_and_references_no_external_script(server):
    base, _wb, _owner = server
    _status, _headers, body = _get_raw(base, "/")
    page = body.decode("utf-8")
    assert 'id="flAuth"' in page          # the overlay rode in
    assert "qrcode" in page               # with the embedded encoder
    assert "<script src" not in page      # and nothing loaded from anywhere


def test_with_auth_off_the_page_is_served_byte_for_byte_unmodified(tmp_path, sample_xml):
    store = Store(tmp_path / "s.db")
    store.init_session("DEMO_ORDER", str(sample_xml))
    wb = Workbench(store, EchoProvider(), tmp_path / "export")  # auth_store=None
    handler = type("BoundHandler", (Handler,), {"workbench": wb})
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        base = f"http://127.0.0.1:{httpd.server_port}"
        _status, _headers, body = _get_raw(base, "/")
        assert body.decode("utf-8") == INDEX_HTML
    finally:
        httpd.shutdown()
        httpd.server_close()
        store.close()


# -- security headers (SS7.3) ------------------------------------------------


def test_every_response_carries_the_hardening_headers(server):
    base, _wb, _owner = server
    for path in ("/", "/api/auth/whoami"):
        _status, headers, _body = _get_raw(base, path)
        assert headers["Cache-Control"] == "no-store"
        assert headers["Referrer-Policy"] == "no-referrer"
        assert headers["X-Content-Type-Options"] == "nosniff"
        csp = headers["Content-Security-Policy"]
        assert "default-src 'none'" in csp
        assert "frame-ancestors 'none'" in csp
        assert "unsafe-eval" not in csp


# -- the scope gate (SS7.1/SS7.2) --------------------------------------------


def test_a_bootstrap_mfa_session_is_kept_off_data_routes_and_audited(server):
    base, wb, _owner = server
    _status, _body, token = _login(base, EMAIL, PASSWORD)
    assert _scope(base, token) == authstore.BOOTSTRAP_MFA

    status, _body = _get(base, "/api/state", cookie=token)
    assert status == 403
    status, _body, _t = _post(
        base, "/api/decision", {"task_id": "x", "state": "approved"},
        cookie=token, csrf=_csrf(base, token),
    )
    assert status == 403

    denied = [
        e for e in wb.auth_store.list_audit_events(limit=50)
        if e["event_type"] == "ACCESS_DENIED"
    ]
    assert {e["target_id"] for e in denied} >= {"/api/state", "/api/decision"}


def test_an_mfa_pending_session_may_only_verify_or_log_out(server):
    base, wb, owner = server
    setup_confirmed_mfa(wb.auth_store, owner["user_id"])
    _status, _body, token = _login(base, EMAIL, PASSWORD)
    assert _scope(base, token) == authstore.MFA_PENDING

    assert _get(base, "/api/state", cookie=token)[0] == 403
    csrf = _csrf(base, token)
    # Not even MFA enrollment -- this account is enrolled; only the
    # verification step and the exit are open.
    assert _post(base, "/api/auth/mfa/enroll", {}, cookie=token, csrf=csrf)[0] == 403


def test_whoami_still_answers_a_restricted_session_with_its_scope(server):
    """The overlay routes on whoami; a restricted session must be able to
    ask 'who am I' or the user can never complete MFA."""
    base, _wb, _owner = server
    _status, _body, token = _login(base, EMAIL, PASSWORD)
    status, who = _get(base, "/api/auth/whoami", cookie=token)
    assert status == 200
    assert who["scope"] == authstore.BOOTSTRAP_MFA
    assert who["mfa_confirmed"] is False
    assert who["csrf_token"]


# -- the enrollment flow over HTTP (SS7.1, SS7.3) ----------------------------


def test_the_full_http_enrollment_flow_graduates_to_a_normal_session(server):
    base, _wb, _owner = server
    _status, _body, token = _login(base, EMAIL, PASSWORD)
    csrf = _csrf(base, token)

    status, enrollment, _t = _post(base, "/api/auth/mfa/enroll", {}, cookie=token, csrf=csrf)
    assert status == 200
    secret = enrollment["secret"]
    assert enrollment["otpauth_uri"].startswith("otpauth://totp/")

    now = time.time()
    status, body, new_token = _post(
        base, "/api/auth/mfa/confirm",
        {
            "code1": totp.generate_code(secret, at=now),
            "code2": totp.generate_code(secret, at=now + totp.PERIOD_SECONDS),
        },
        cookie=token, csrf=csrf,
    )
    assert status == 200
    assert len(body["recovery_codes"]) == authstore.MFA_RECOVERY_CODE_COUNT
    assert new_token and new_token != token

    # The graduated cookie reaches data routes; the bootstrap one is dead.
    assert _get(base, "/api/state", cookie=new_token)[0] == 200
    assert _get(base, "/api/state", cookie=token)[0] == 401


def test_the_http_mfa_step_completes_a_pending_login(server):
    base, wb, owner = server
    dev_id = wb.auth_store.create_user("dev@example.com", PASSWORD)
    wb.auth_store.create_membership(owner["organization_id"], dev_id, authstore.DEVELOPER)
    mfa = setup_confirmed_mfa(wb.auth_store, dev_id)

    _status, _body, pending = _login(base, "dev@example.com", PASSWORD)
    assert _scope(base, pending) == authstore.MFA_PENDING

    status, _body, normal = _post(
        base, "/api/auth/mfa",
        {"code": next_mfa_code(wb.auth_store, dev_id, mfa["secret"])},
        cookie=pending, csrf=_csrf(base, pending),
    )
    assert status == 200
    assert normal and normal != pending
    assert _get(base, "/api/state", cookie=normal)[0] == 200


def test_a_wrong_code_on_the_http_mfa_step_is_a_400_not_a_500(server):
    base, wb, owner = server
    setup_confirmed_mfa(wb.auth_store, owner["user_id"])
    _status, _body, pending = _login(base, EMAIL, PASSWORD)
    status, body, _t = _post(
        base, "/api/auth/mfa", {"code": "000000"},
        cookie=pending, csrf=_csrf(base, pending),
    )
    assert status == 400
    assert "code" in body["error"].lower() or "invalid" in body["error"].lower()


def test_disabling_mfa_over_http_revokes_the_session_itself(server):
    base, wb, owner = server
    token, mfa = _normal_session(base, wb, owner["user_id"], EMAIL)
    status, _body, _t = _post(
        base, "/api/auth/mfa/disable",
        {"password": PASSWORD, "code": next_mfa_code(wb.auth_store, owner["user_id"], mfa["secret"])},
        cookie=token, csrf=_csrf(base, token),
    )
    assert status == 200
    assert _get(base, "/api/state", cookie=token)[0] == 401


def test_regenerating_recovery_codes_over_http(server):
    base, wb, owner = server
    token, mfa = _normal_session(base, wb, owner["user_id"], EMAIL)
    status, body, _t = _post(
        base, "/api/auth/mfa/recovery-codes",
        {"code": next_mfa_code(wb.auth_store, owner["user_id"], mfa["secret"])},
        cookie=token, csrf=_csrf(base, token),
    )
    assert status == 200
    assert len(body["recovery_codes"]) == authstore.MFA_RECOVERY_CODE_COUNT
    assert not set(body["recovery_codes"]) & set(mfa["recovery_codes"])


# -- password reset over HTTP (SS7.5) ----------------------------------------


def test_the_full_http_reset_flow(server):
    base, wb, owner = server
    dev_id = wb.auth_store.create_user("dev@example.com", PASSWORD)
    wb.auth_store.create_membership(owner["organization_id"], dev_id, authstore.DEVELOPER)
    token, _mfa = _normal_session(base, wb, owner["user_id"], EMAIL)

    status, body, _t = _post(
        base, "/api/auth/reset/issue", {"user_id": dev_id},
        cookie=token, csrf=_csrf(base, token),
    )
    assert status == 200
    reset_token = body["reset_token"]

    # Redeemed with no cookie at all -- the caller lost their password.
    status, body, _t = _post(
        base, "/api/auth/reset/redeem",
        {"token": reset_token, "new_password": "a whole new passphrase"},
    )
    assert status == 200
    assert wb.auth_store.login("dev@example.com", "a whole new passphrase").ok


def test_a_bogus_reset_token_gets_the_same_generic_refusal(server):
    base, _wb, _owner = server
    status, body, _t = _post(
        base, "/api/auth/reset/redeem",
        {"token": "never-existed", "new_password": "whatever passphrase"},
    )
    assert status == 400
    assert body["error"] == "invalid or expired reset token"


def test_issuing_a_reset_for_an_owner_over_http_is_refused(server):
    base, wb, owner = server
    token, _mfa = _normal_session(base, wb, owner["user_id"], EMAIL)
    status, body, _t = _post(
        base, "/api/auth/reset/issue", {"user_id": owner["user_id"]},
        cookie=token, csrf=_csrf(base, token),
    )
    assert status in (400, 403)
    assert "reset-owner" in body["error"]
