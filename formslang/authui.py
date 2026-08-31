"""The auth overlay: login, MFA verification and mandatory TOTP enrollment.

Injected into the workbench page only when the auth subsystem is on --
auth-off mode serves ``ui.INDEX_HTML`` byte-for-byte unchanged. The overlay
is self-contained (style + markup + script) and follows the same rules as
the page it rides in: no build step, no CDN, no external request of any
kind. The QR encoder is the vendored ``qrcode-generator`` 1.4.4 (MIT --
see ``formslang/vendor/README.md`` for provenance and pinned SHA-256).

Secret hygiene (design doc SS7.3): the TOTP secret and otpauth URI live
only in transient DOM and local variables while the enrollment screen is
open, and are wiped -- DOM emptied, references nulled -- the moment the
enrollment is confirmed or cancelled. Nothing auth-related ever touches
localStorage, sessionStorage or a URL.
"""

from __future__ import annotations

import functools
from pathlib import Path

_VENDOR_QR = Path(__file__).parent / "vendor" / "qrcode-generator-1.4.4.js"

#: Pinned at vendoring time (2026-08-31); tests re-hash the file against
#: this on every run, so a modified copy fails the suite.
QR_SHA256 = "18ae399f81182bc9de916e9c77b195df20cc58d6f2d55a62b085a299f1bf1780"

_OVERLAY = r"""
<style>
  #flAuth {
    position: fixed; inset: 0; z-index: 9999; display: flex;
    align-items: center; justify-content: center;
    background: var(--ground, #07090D); color: var(--ink, #EEF1F6);
    font: 14px/1.5 var(--sans, system-ui, sans-serif);
  }
  #flAuth[hidden] { display: none; }
  #flAuth .card {
    width: min(420px, 92vw); background: var(--panel, #0C1016);
    border: 1px solid var(--line, #222937); border-radius: 10px;
    padding: 28px; box-shadow: 0 12px 40px rgba(0,0,0,.5);
  }
  #flAuth h1 { margin: 0 0 4px; font-size: 18px; color: var(--gold, #F5A640); }
  #flAuth p.sub { margin: 0 0 18px; color: var(--ink-dim, #9AA3B2); font-size: 13px; }
  #flAuth label { display: block; margin: 12px 0 4px; font-size: 12px; color: var(--ink-dim, #9AA3B2); }
  #flAuth input, #flAuth select {
    width: 100%; padding: 9px 10px; border-radius: 6px;
    border: 1px solid var(--line-hi, #2E3746); background: var(--raised, #11161E);
    color: inherit; font: inherit;
  }
  #flAuth input.code { font-family: var(--mono, monospace); letter-spacing: .35em; text-align: center; }
  #flAuth button {
    margin-top: 18px; width: 100%; padding: 10px; border-radius: 6px; border: 0;
    background: var(--gold, #F5A640); color: #14100a; font-weight: 600;
  }
  #flAuth button.ghost { background: transparent; color: var(--ink-dim, #9AA3B2);
    border: 1px solid var(--line, #222937); margin-top: 8px; }
  #flAuth .err { margin: 12px 0 0; color: var(--red, #F87171); font-size: 13px; min-height: 1.2em; }
  #flAuth .qr { display: flex; justify-content: center; margin: 16px 0;
    background: #fff; border-radius: 8px; padding: 12px; }
  #flAuth .qr svg { display: block; }
  #flAuth .key { font-family: var(--mono, monospace); font-size: 13px; word-break: break-all;
    background: var(--raised, #11161E); border: 1px solid var(--line, #222937);
    border-radius: 6px; padding: 8px 10px; user-select: all; }
  #flAuth ul.rc { list-style: none; margin: 14px 0; padding: 0; columns: 2;
    font-family: var(--mono, monospace); font-size: 13px; }
  #flAuth ul.rc li { padding: 3px 0; user-select: all; }
  #flAuth .warn { color: var(--gold, #F5A640); font-size: 13px; }
  #flAuth .row2 { display: flex; gap: 10px; }
  #flAuth .row2 > div { flex: 1; }
</style>
<div id="flAuth" hidden><div class="card" id="flAuthCard"></div></div>
<script>
__QR_LIB__
</script>
<script>
(() => {
  "use strict";
  const overlay = document.getElementById("flAuth");
  const card = document.getElementById("flAuthCard");
  let csrf = "";

  // The main app predates auth mode and sends no CSRF header of its own:
  // once a NORMAL session exists, inject the token into every same-origin
  // mutating fetch so the whole workbench works unmodified.
  const realFetch = window.fetch.bind(window);
  window.fetch = (input, init) => {
    const method = ((init && init.method) || "GET").toUpperCase();
    if (csrf && method !== "GET" && method !== "HEAD") {
      init = init || {};
      init.headers = Object.assign({}, init.headers, { "X-CSRF-Token": csrf });
    }
    return realFetch(input, init);
  };

  const esc = (s) => String(s).replace(/[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  async function post(path, payload) {
    const r = await realFetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
      body: JSON.stringify(payload || {}),
    });
    let data = {};
    try { data = await r.json(); } catch (_e) { /* non-JSON error body */ }
    return { ok: r.ok, status: r.status, data };
  }

  async function api(path, payload) {
    const r = await post(path, payload);
    if (!r.ok) throw new Error(r.data.error || r.data.reason || ("HTTP " + r.status));
    return r.data;
  }

  async function whoami() {
    const r = await realFetch("/api/auth/whoami");
    return r.json();
  }

  function show(html) { card.innerHTML = html; overlay.hidden = false; }
  function err(msg) {
    const el = card.querySelector(".err");
    if (el) el.textContent = msg;
  }

  function done() {
    // A fresh boot with the NORMAL cookie: simplest way to hand the page
    // back to the main app with clean state.
    location.reload();
  }

  // -- screens -----------------------------------------------------------

  function loginScreen(orgs, email, password) {
    show(`
      <h1>FormsLang</h1>
      <p class="sub">Sign in to the workbench</p>
      <label>Email</label><input id="flEmail" type="email" autocomplete="username">
      <label>Password</label><input id="flPass" type="password" autocomplete="current-password">
      ${orgs && orgs.length ? `<label>Organization</label><select id="flOrg">` +
        orgs.map((o) => `<option value="${esc(o.org_id)}">${esc(o.org_id)}</option>`).join("") +
        `</select>` : ""}
      <button id="flGo">Sign in</button>
      <p class="err"></p>`);
    if (email) card.querySelector("#flEmail").value = email;
    if (password) card.querySelector("#flPass").value = password;
    const go = async () => {
      const payload = {
        email: card.querySelector("#flEmail").value,
        password: card.querySelector("#flPass").value,
      };
      const org = card.querySelector("#flOrg");
      if (org) payload.org_id = org.value;
      const r = await post("/api/auth/login", payload);
      if (r.ok) { route(); return; }
      if (r.data.organizations && r.data.organizations.length) {
        // Multi-org account: same screen again, org picker added.
        loginScreen(r.data.organizations, payload.email, payload.password);
        return;
      }
      err(r.data.reason || r.data.error || "sign-in failed");
    };
    card.querySelector("#flGo").addEventListener("click", go);
    card.addEventListener("keydown", (e) => { if (e.key === "Enter") go(); });
    card.querySelector("#flEmail").focus();
  }

  function mfaScreen() {
    show(`
      <h1>Two-factor check</h1>
      <p class="sub">Enter the 6-digit code from your authenticator app,
        or one of your recovery codes.</p>
      <input id="flCode" class="code" autocomplete="one-time-code">
      <button id="flGo">Verify</button>
      <button id="flBack" class="ghost">Back to sign in</button>
      <p class="err"></p>`);
    const go = async () => {
      try {
        await api("/api/auth/mfa", { code: card.querySelector("#flCode").value });
        done();
      } catch (e) { err(e.message); }
    };
    card.querySelector("#flGo").addEventListener("click", go);
    card.querySelector("#flCode").addEventListener("keydown", (e) => { if (e.key === "Enter") go(); });
    card.querySelector("#flBack").addEventListener("click", async () => {
      try { await api("/api/auth/logout", {}); } catch (_e) {}
      route();
    });
    card.querySelector("#flCode").focus();
  }

  function enrollIntro() {
    show(`
      <h1>Set up two-factor auth</h1>
      <p class="sub">Your role requires an authenticator app (TOTP) before
        the workbench opens. You will need a phone with Google
        Authenticator, Microsoft Authenticator, 1Password or similar.</p>
      <button id="flGo">Start setup</button>
      <button id="flBack" class="ghost">Sign out</button>
      <p class="err"></p>`);
    card.querySelector("#flGo").addEventListener("click", enrollStart);
    card.querySelector("#flBack").addEventListener("click", async () => {
      try { await api("/api/auth/logout", {}); } catch (_e) {}
      route();
    });
  }

  async function enrollStart() {
    let enrollment;
    try { enrollment = await api("/api/auth/mfa/enroll", {}); }
    catch (e) { err(e.message); return; }
    enrollScreen(enrollment);
    enrollment = null;
  }

  function enrollScreen(enrollment) {
    show(`
      <h1>Scan this code</h1>
      <p class="sub">Scan with your authenticator app, then type two
        codes in a row (wait for the code to change once).</p>
      <div class="qr" id="flQr"></div>
      <label>Or enter the key manually</label>
      <div class="key" id="flKey"></div>
      <div class="row2">
        <div><label>First code</label>
          <input id="flC1" class="code"></div>
        <div><label>Next code</label>
          <input id="flC2" class="code"></div>
      </div>
      <button id="flGo">Confirm</button>
      <button id="flCancel" class="ghost">Cancel</button>
      <p class="err"></p>`);

    // Rendered locally by the vendored encoder -- the URI never leaves
    // this page. Both land in transient DOM only, wiped by flWipe below.
    const qr = qrcode(0, "M");
    qr.addData(enrollment.otpauth_uri);
    qr.make();
    card.querySelector("#flQr").innerHTML = qr.createSvgTag(4, 8);
    card.querySelector("#flKey").textContent = enrollment.secret;
    enrollment = null;

    const flWipe = () => {
      const qrEl = card.querySelector("#flQr");
      const keyEl = card.querySelector("#flKey");
      if (qrEl) qrEl.innerHTML = "";
      if (keyEl) keyEl.textContent = "";
    };
    card.querySelector("#flGo").addEventListener("click", async () => {
      try {
        const out = await api("/api/auth/mfa/confirm", {
          code1: card.querySelector("#flC1").value,
          code2: card.querySelector("#flC2").value,
        });
        flWipe();
        recoveryScreen(out.recovery_codes);
      } catch (e) { err(e.message); }
    });
    card.querySelector("#flCancel").addEventListener("click", async () => {
      flWipe();
      try { await api("/api/auth/logout", {}); } catch (_e) {}
      route();
    });
    card.querySelector("#flC1").focus();
  }

  function recoveryScreen(codes) {
    show(`
      <h1>Recovery codes</h1>
      <p class="sub">Each code signs you in once if you lose the phone.
        <span class="warn">This is the only time they are shown.</span>
        Store them somewhere safe (a password manager, a printed copy).</p>
      <ul class="rc">${codes.map((c) => `<li>${esc(c)}</li>`).join("")}</ul>
      <button id="flCopy" class="ghost">Copy all</button>
      <button id="flGo">I saved them &mdash; open the workbench</button>`);
    const joined = codes.join("\n");
    codes = null;
    card.querySelector("#flCopy").addEventListener("click", () => {
      if (navigator.clipboard) navigator.clipboard.writeText(joined).catch(() => {});
    });
    card.querySelector("#flGo").addEventListener("click", () => {
      card.innerHTML = "";   // the codes leave the DOM before the app boots
      done();
    });
  }

  // -- router ------------------------------------------------------------

  async function route() {
    let me;
    try { me = await whoami(); }
    catch (_e) { overlay.hidden = true; return; }   // auth off / server gone
    if (!me.authenticated) { csrf = ""; loginScreen(); return; }
    csrf = me.csrf_token || "";
    if (me.scope === "MFA_PENDING") { mfaScreen(); return; }
    if (me.scope === "BOOTSTRAP_MFA") { enrollIntro(); return; }
    overlay.hidden = true;   // NORMAL: hand over to the app (fetch glue armed)
  }

  route();
})();
</script>
"""


@functools.lru_cache(maxsize=1)
def _overlay() -> str:
    qr_lib = _VENDOR_QR.read_text(encoding="utf-8")
    return _OVERLAY.replace("__QR_LIB__", qr_lib)


def with_auth_overlay(index_html: str) -> str:
    """The workbench page with the auth overlay riding just before
    ``</body>`` -- called only when the auth subsystem is on."""
    return index_html.replace("</body>", _overlay() + "\n</body>", 1)
