"""The app chrome: top bar, live-run status banners, the first-run welcome screen, the state refresh loop and the top-level event wiring -- split out of formslang/ui.py."""

from __future__ import annotations

BODY_OPEN_HTML = r"""<body>
<a class="skip-workspace" href="#workspace-title">Skip to workspace</a>
<button class="nav-scrim" id="nav-scrim" aria-label="Close navigation" tabindex="-1" hidden></button>
<nav id="app-nav" class="app-nav" aria-label="Workbench navigation">
  <div class="brand app-brand">
    <svg viewBox="0 0 512 512" aria-hidden="true"><path fill="#F5A640" fill-rule="evenodd" d="M112 72H322V104H112C90 104 72 122 72 144V368C72 390 90 408 112 408H322V440H112C72 440 40 408 40 368V144C40 104 72 72 112 72ZM290 72H322V440H290Z"/><rect x="322" y="112" width="92" height="24" rx="2" fill="#F5A640"/><rect x="322" y="160" width="132" height="24" rx="2" fill="#F5A640"/><rect x="322" y="208" width="104" height="24" rx="2" fill="#F5A640"/><rect x="322" y="256" width="148" height="24" rx="2" fill="#F5A640"/><rect x="322" y="304" width="116" height="24" rx="2" fill="#F5A640"/><rect x="322" y="352" width="140" height="24" rx="2" fill="#F5A640"/></svg>
    <div class="brand-copy"><span class="mark">FormsLang</span><small>Workbench</small></div>
    <button class="btn nav-collapse" id="nav-collapse" type="button" aria-label="Collapse navigation" title="Collapse navigation" aria-controls="app-nav" aria-expanded="true"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m14 7-5 5 5 5"/></svg></button>
    <button class="btn nav-close" id="nav-close" aria-label="Close navigation">&times;</button>
  </div>
  <div class="module-switcher"><span class="nav-kicker">Current module</span><button class="btn" id="btn-module" aria-label="Open or switch Forms module" title="Open or switch Forms module">Open a module…</button></div>
  <div class="nav-sections">
    <div class="nav-group"><span class="nav-kicker">Workspace</span>
      <button class="nav-item" id="btn-review" aria-current="page" title="Conversion review"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M10 4v16M14 9h3M14 13h3"/></svg><span>Review</span></button>
      <button class="nav-item" id="btn-dash" title="Project overview"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 20V10m8 10V4m8 16v-7"/></svg><span>Project</span></button>
      <button class="nav-item" id="btn-blueprint" title="Modernization blueprint"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="8" y="3" width="8" height="5" rx="1"/><rect x="2" y="16" width="7" height="5" rx="1"/><rect x="15" y="16" width="7" height="5" rx="1"/><path d="M12 8v4M5.5 16v-4h13v4"/></svg><span>Blueprint</span></button>
    </div>
    <div class="nav-group"><span class="nav-kicker">Inspect</span>
      <button class="nav-item" id="btn-doc" title="Technical documentation"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14 3H5v18h14V8l-5-5Z M14 3v5h5M8 12h8M8 16h6"/></svg><span>Documentation</span></button>
      <button class="nav-item" id="btn-preview" title="Visual preview of Forms and APEX"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="4" width="18" height="13" rx="2"/><path d="M8 21h8M12 17v4M3 8h18"/></svg><span>Visual preview</span></button>
      <button class="nav-item" id="btn-diff" title="Compare module versions"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 3v18M17 3v18M4 6l3-3 3 3M14 18l3 3 3-3M4 12h6M14 12h6"/></svg><span>Structural diff</span></button>
    </div>
    <div class="nav-group"><span class="nav-kicker">Deliver</span>
      <button class="nav-item" id="btn-exports" title="Export history and packages"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v12M8 11l4 4 4-4M4 15v6h16v-6"/></svg><span>Exports</span></button>
      <button class="nav-item" id="btn-settings" title="Settings — model, API key, CLI"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="3"/><circle cx="15" cy="17" r="3"/></svg><span>Settings</span></button>
    </div>
  </div>
  <div class="nav-footer">
    <div class="provider-block"><span class="provider-dot" id="provider-dot" aria-hidden="true"></span><div><span class="nav-kicker">Conversion provider</span><button class="provider" id="provider" title="Choose conversion provider">Loading…</button></div></div>
    <div class="nav-local"><span>Local workspace</span><button class="btn theme-toggle" id="theme-toggle" aria-label="Switch color theme" title="Switch color theme"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5 19 19M5 19l1.5-1.5M17.5 6.5 19 5"/></svg><span class="theme-label">Theme</span></button></div>
    <span class="nav-credit">by B2DEV TECH</span>
  </div>
</nav>
"""

HEADER_HTML = r"""<header class="app-header">
  <button class="btn nav-toggle" id="nav-toggle" aria-label="Open navigation" aria-controls="app-nav" aria-expanded="false"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h16"/></svg></button>
  <div class="workspace-heading"><span class="workspace-eyebrow">Workspace <span aria-hidden="true">/</span> <span id="workspace-caption">Getting started</span></span><h1 id="workspace-title" tabindex="-1">Welcome to FormsLang</h1></div>
  <div class="counts" id="counts" aria-label="Session progress"></div>
  <div class="header-actions"><button class="btn" id="btn-propose-all">Convert unconverted</button><button class="btn primary" id="btn-export">Export APEX 26.1 <span aria-hidden="true">↗</span></button></div>
</header>
"""

PROGRESS_BAR_HTML = r"""<div id="bar"></div>
"""

WORKING_BANNER_HTML = r"""<div id="working" hidden>
  <span class="spin"></span>
  <span class="what" id="working-what"></span>
  <span class="spacer"></span>
  <span class="mono" id="working-meta"></span>
</div>
"""

SETUP_BANNER_HTML = r"""<div id="setup-banner" hidden>
  <span><b>Offline mode</b> — conversions are placeholders until you pick a model. Hand-written APEX works either way.</span>
  <div class="spacer"></div>
  <button class="btn primary" id="setup-open">Choose a model</button>
  <button class="btn" id="setup-later">Later</button>
</div>

"""

WELCOME_HTML = r"""    <div id="welcome">
      <div class="hello">
        <svg viewBox="0 0 512 512" aria-hidden="true"><path fill="#F5A640" fill-rule="evenodd" d="M112 72H322V104H112C90 104 72 122 72 144V368C72 390 90 408 112 408H322V440H112C72 440 40 408 40 368V144C40 104 72 72 112 72ZM290 72H322V440H290Z"/><rect x="322" y="112" width="92" height="24" rx="2" fill="#F5A640"/><rect x="322" y="160" width="132" height="24" rx="2" fill="#F5A640"/><rect x="322" y="208" width="104" height="24" rx="2" fill="#F5A640"/><rect x="322" y="256" width="148" height="24" rx="2" fill="#F5A640"/><rect x="322" y="304" width="116" height="24" rx="2" fill="#F5A640"/><rect x="322" y="352" width="140" height="24" rx="2" fill="#F5A640"/></svg>
        <span class="welcome-eyebrow">ORACLE FORMS → ORACLE APEX</span>
        <h1>A clear path from legacy<br>to <em>what comes next.</em></h1>
        <p>Open an Oracle Forms module and FormsLang turns every trigger and
           program unit into a reviewable APEX proposal. Your source, your decisions.</p>
        <div class="steps">
          <div class="step"><span class="no">01 / UNDERSTAND</span><b>Bring your Forms module</b><span>Open an FMB or XML and inspect the structure, dependencies and migration risks.</span></div>
          <div class="step"><span class="no">02 / MODERNIZE</span><b>Review every proposal</b><span>Compare original PL/SQL with the APEX proposal. Edit and decide, one unit at a time.</span></div>
          <div class="step"><span class="no">03 / DELIVER</span><b>Build with confidence</b><span>Export an APEX package that includes the code you have approved.</span></div>
        </div>
        <div class="cta">
          <button class="btn primary" id="welcome-open">Open a Forms module</button>
          <span class="or">or press <kbd class="key">O</kbd></span>
        </div>
        <div class="local"><i>&#10003;</i> Runs entirely on this machine — code goes only to the model you configure.</div>
        <div class="local legal">FormsLang &middot; created by Geraldo Viana Jr &middot; Apache-2.0 open source &middot; b2dev.tech</div>
      </div>
    </div>
  </section>
</main>

"""

DATA_REFRESH_JS = r"""let stateRequest = 0;
async function refresh(keep = true) {
  const request = ++stateRequest;
  const data = await api("/api/state");
  if (request !== stateRequest) return;
  const switchedSession = reviewContext() && reviewContext() !== reviewContext(data);
  if (switchedSession) { deps = {}; tests = {}; editorTask = null; }
  state = data;
  $("btn-module").textContent = data.session.title || "Open a module…";
  $("btn-module").title = data.session.title || "Open or switch Forms module";
  $("workspace-title").textContent = data.session.title || "Welcome to FormsLang";
  $("workspace-caption").textContent = data.session.title ? "Conversion review" : "Getting started";
  $("provider").textContent = data.provider;
  $("provider").title = data.provider + " — choose conversion provider";
  $("provider-dot").classList.toggle("offline", data.provider_id === "echo");
  $("btn-export").disabled = !data.can_export_apex;
  $("btn-doc").disabled = !data.can_export_apex;
  $("btn-preview").disabled = !data.can_export_apex;
  $("btn-diff").disabled = !data.can_export_apex;
  /* First run, nothing open: the welcome takes the whole stage. */
  $("welcome").classList.toggle("show", !state.tasks.length && !data.session.title);
  document.body.classList.toggle("is-first-run", !state.tasks.length && !data.session.title);
  /* A module is open but the provider is still the offline stub: say so once.
     Never silently default to a cloud provider — choosing is an explicit act. */
  $("setup-banner").hidden = !(data.provider_id === "echo" && state.tasks.length && !setupLater);
  renderCounts();
  renderFilters();
  if (!keep || !state.tasks.some((t) => t.id === selected))
    selected = (state.tasks[0] || {}).id || null;
  renderList();
  renderDetail();
}

"""

WIRING_JS = r"""function setShellSection(id = "btn-review") {
  document.querySelectorAll(".nav-item").forEach((button) => {
    if (button.id === id) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });
}
function setNavigationOpen(open, restoreFocus = true) {
  const isOpen = open && window.matchMedia("(max-width: 720px)").matches;
  document.body.classList.toggle("nav-open", isOpen);
  $("nav-toggle").setAttribute("aria-expanded", String(isOpen));
  $("nav-scrim").hidden = !isOpen;
  const stageInert = isOpen || $("modal").classList.contains("show");
  document.querySelectorAll("body > header, body > main, #working, #setup-banner").forEach((element) => { element.inert = stageInert; });
  if (isOpen) $("nav-close").focus();
  else if (restoreFocus && window.matchMedia("(max-width: 720px)").matches) $("nav-toggle").focus();
}
let shellNavigationRequest = 0;
async function openShellSection(id, action) {
  if (document.body.classList.contains("nav-open")) setNavigationOpen(false);
  setShellSection(id);
  const request = ++shellNavigationRequest;
  try { return await action(); }
  finally {
    if (request === shellNavigationRequest && !$("modal").classList.contains("show")) setShellSection();
  }
}
$("nav-toggle").onclick = () => setNavigationOpen(!document.body.classList.contains("nav-open"));
$("nav-close").onclick = () => setNavigationOpen(false);
$("nav-scrim").onclick = () => setNavigationOpen(false);
$("app-nav").querySelectorAll(".nav-item").forEach((button) => button.setAttribute("aria-label", button.textContent.trim()));
window.matchMedia("(max-width: 720px)").addEventListener("change", () => setNavigationOpen(false, false));
window.addEventListener("formslang:modalchange", () => {
  const open = $("modal").classList.contains("show");
  $("app-nav").inert = open;
  const stageInert = open || document.body.classList.contains("nav-open");
  document.querySelectorAll("body > header, body > main, #working, #setup-banner").forEach((element) => { element.inert = stageInert; });
  if (!open) setShellSection();
});
$("btn-review").onclick = () => { setNavigationOpen(false); closeModal(); setShellSection(); $("workspace-title").focus(); };
$("btn-module").onclick = () => openShellSection("btn-review", () => browse(""));
$("btn-blueprint").onclick = () => openShellSection("btn-blueprint", showBlueprint);
$("welcome-open").onclick = () => browse("");
$("provider").onclick = () => openShellSection("btn-settings", openSettings);
$("btn-settings").onclick = () => openShellSection("btn-settings", openSettings);
$("setup-open").onclick = () => openShellSection("btn-settings", openSettings);
$("setup-later").onclick = () => { setupLater = true; $("setup-banner").hidden = true; };
$("modal-close").onclick = closeModal;
$("modal").onclick = (e) => { if (e.target === $("modal")) closeModal(); };
$("btn-approve").onclick = () => decide("approved");
$("btn-reject").onclick = () => decide("rejected");
$("btn-needs").onclick = () => decide("needs_work");
$("btn-propose").onclick = () => propose(false);
$("btn-propose-all").onclick = () => propose(true);
$("btn-export").onclick = () => openShellSection("btn-exports", exportApex);
$("btn-exports").onclick = () => openShellSection("btn-exports", showExports);
$("btn-dash").onclick = () => openShellSection("btn-dash", showDashboard);
$("btn-doc").onclick = () => openShellSection("btn-review", openDoc);
$("btn-preview").onclick = () => openShellSection("btn-review", openPreview);
$("btn-diff").onclick = () => openShellSection("btn-diff", pickDiffTarget);
let filterTimer;
$("q").oninput = (e) => { query = e.target.value.toLowerCase(); clearTimeout(filterTimer); filterTimer = setTimeout(() => { renderList(); renderDetail(); }, 90); };
$("out").oninput = () => {
  captureReviewDraft();
  cancelAnimationFrame(highlightFrame);
  highlightFrame = requestAnimationFrame(syncOutHighlight);
};
$("comment").oninput = captureReviewDraft;
$("out").onscroll = syncOutScroll;
$("discard-draft").onclick = discardReviewDraft;
for (const view of ["compare", "source", "proposal", "evidence"]) $("view-" + view).onclick = () => setReviewView(view);
$("unit-prev").onclick = () => move(-1);
$("unit-next").onclick = () => move(1);
$("unit-toggle").onclick = () => {
  const open = $("unit-toggle").getAttribute("aria-expanded") !== "true";
  setUnitsVisible(open);
  if (open) $("q").focus();
};
window.addEventListener("beforeunload", (e) => {
  if (reviewDrafts.size) { e.preventDefault(); e.returnValue = ""; }
});

document.addEventListener("keydown", (e) => {
  const typing = ["INPUT", "TEXTAREA", "SELECT", "BUTTON", "A", "SUMMARY"].includes(document.activeElement.tagName) || document.activeElement.isContentEditable || document.activeElement.getAttribute("role") === "separator";
  if (document.body.classList.contains("nav-open")) {
    if (e.key === "Escape") { e.preventDefault(); setNavigationOpen(false); }
    if (e.key === "Tab") {
      const buttons = [...$("app-nav").querySelectorAll("button:not(:disabled)")].filter((button) => button.getClientRects().length);
      const first = buttons[0], last = buttons[buttons.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
    return;
  }
  if (e.key === "Escape") {
    if ($("modal").classList.contains("show")) closeModal();
    else if (workspaceFocus) setWorkspaceFocus(false);
    else {
      const unitsWereOpen = document.querySelector("main").classList.contains("units-open");
      if (unitsWereOpen) setUnitsVisible(false, true);
    }
    return;
  }
  // With the overlay up, every other shortcut belongs to the overlay.
  if ($("modal").classList.contains("show")) return;
  if (e.key === "/" && !typing) {
    e.preventDefault();
    setUnitsVisible(true);
    $("q").focus(); return;
  }
  if (typing || e.ctrlKey || e.metaKey || e.altKey || e.repeat) return;
  if (e.key === "j") move(1);
  else if (e.key === "k") move(-1);
  else if (e.key === "a") decide("approved");
  else if (e.key === "r") decide("rejected");
  else if (e.key === "w") decide("needs_work");
  else if (e.key === "p") propose(false);
  else if (e.key === "o") browse("");
  else if (e.key === "d") openShellSection("btn-dash", showDashboard);
});

try { $("reviewer").value = localStorage.getItem("formslang.reviewer") || ""; } catch (_) { /* storage may be disabled */ }
PROPOSE_LABEL = $("btn-propose").innerHTML;
initReviewWorkspace();
initWorkspaceLayout();
refresh(false)
  /* A run started before this window opened still owns the screen. */
  .then(() => api("/api/job"))
  .then((j) => { if (j.running) { job = j; jobStart = Date.now(); paintWorking(); poll(); } })
  .catch((e) => toast(e.message, true));
</script>
</body>
</html>
"""
