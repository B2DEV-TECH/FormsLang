"""The app chrome: top bar, live-run status banners, the first-run welcome screen, the state refresh loop and the top-level event wiring -- split out of formslang/ui.py."""

from __future__ import annotations

BODY_OPEN_HTML = r"""<body>

"""

HEADER_HTML = r"""<header>
  <div class="brand">
    <svg viewBox="0 0 512 512" aria-hidden="true"><path fill="#F5A640" fill-rule="evenodd" d="M112 72H322V104H112C90 104 72 122 72 144V368C72 390 90 408 112 408H322V440H112C72 440 40 408 40 368V144C40 104 72 72 112 72ZM290 72H322V440H290Z"/><rect x="322" y="112" width="92" height="24" rx="2" fill="#F5A640"/><rect x="322" y="160" width="132" height="24" rx="2" fill="#F5A640"/><rect x="322" y="208" width="104" height="24" rx="2" fill="#F5A640"/><rect x="322" y="256" width="148" height="24" rx="2" fill="#F5A640"/><rect x="322" y="304" width="116" height="24" rx="2" fill="#F5A640"/><rect x="322" y="352" width="140" height="24" rx="2" fill="#F5A640"/></svg>
    <span class="mark">FormsLang</span> <small>Workbench &middot; by B2DEV TECH</small>
  </div>
  <button class="btn" id="btn-module" title="Pick another Forms module">—</button>
  <div class="spacer"></div>
  <div class="counts" id="counts"></div>
  <span class="chip provider" id="provider" title="Pick the model that converts">—</span>
  <button class="btn" id="btn-settings" title="Settings — model, API key, CLI">&#9881;</button>
  <button class="btn" id="btn-propose-all">Convert unconverted</button>
  <button class="btn" id="btn-dash" title="Project view — what this session says, counted">Project</button>
  <button class="btn" id="btn-doc" title="HTML technical documentation for this module">Doc</button>
  <button class="btn" id="btn-preview" title="Read-only preview: Forms UI vs. the APEX default mapping">Preview</button>
  <button class="btn" id="btn-diff" title="Compare this module against another version">Diff</button>
  <button class="btn" id="btn-exports" title="Exported ZIPs — open in folder">Exports</button>
  <button class="btn primary" id="btn-export">Export APEX 26.1</button>
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
        <h1>Your Forms code, read <em>one unit at a time</em></h1>
        <p>Open an Oracle Forms module and FormsLang turns every trigger and
           program unit into a reviewable APEX proposal — you approve each one.</p>
        <div class="steps">
          <div class="step"><span class="no">01 · IMPORT</span><b>Open the .fmb</b><span>Oracle's own converter reads it. Your source tree is never written to.</span></div>
          <div class="step"><span class="no">02 · CONVERT</span><b>Ask your model</b><span>Every proposal is a draft with a confidence score and open questions.</span></div>
          <div class="step"><span class="no">03 · REVIEW</span><b>Decide and export</b><span>Approve, reject or edit — only approved code enters the APEX package.</span></div>
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

DATA_REFRESH_JS = r"""async function refresh(keep = true) {
  const data = await api("/api/state");
  state = data;
  $("btn-module").textContent = data.session.title || "Open a module…";
  $("provider").textContent = data.provider;
  $("btn-export").disabled = !data.can_export_apex;
  $("btn-doc").disabled = !data.can_export_apex;
  $("btn-preview").disabled = !data.can_export_apex;
  $("btn-diff").disabled = !data.can_export_apex;
  /* First run, nothing open: the welcome takes the whole stage. */
  $("welcome").classList.toggle("show", !state.tasks.length && !data.session.title);
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

WIRING_JS = r"""$("btn-module").onclick = () => browse("");
$("welcome-open").onclick = () => browse("");
$("provider").onclick = openSettings;
$("btn-settings").onclick = openSettings;
$("setup-open").onclick = openSettings;
$("setup-later").onclick = () => { setupLater = true; $("setup-banner").hidden = true; };
$("modal-close").onclick = closeModal;
$("modal").onclick = (e) => { if (e.target === $("modal")) closeModal(); };
$("btn-approve").onclick = () => decide("approved");
$("btn-reject").onclick = () => decide("rejected");
$("btn-needs").onclick = () => decide("needs_work");
$("btn-propose").onclick = () => propose(false);
$("btn-propose-all").onclick = () => propose(true);
$("btn-export").onclick = exportApex;
$("btn-exports").onclick = () => showExports();
$("btn-dash").onclick = showDashboard;
$("btn-doc").onclick = openDoc;
$("btn-preview").onclick = openPreview;
$("btn-diff").onclick = pickDiffTarget;
$("q").oninput = (e) => { query = e.target.value.toLowerCase(); renderList(); };
$("out").oninput = syncOutHighlight;
$("out").onscroll = syncOutScroll;

document.addEventListener("keydown", (e) => {
  const typing = ["INPUT", "TEXTAREA"].includes(document.activeElement.tagName);
  if (e.key === "Escape") { closeModal(); document.activeElement.blur(); return; }
  // With the overlay up, every other shortcut belongs to the overlay.
  if ($("modal").classList.contains("show")) return;
  if (e.key === "/" && !typing) { e.preventDefault(); $("q").focus(); return; }
  if (typing) return;
  if (e.key === "j") move(1);
  else if (e.key === "k") move(-1);
  else if (e.key === "a") decide("approved");
  else if (e.key === "r") decide("rejected");
  else if (e.key === "w") decide("needs_work");
  else if (e.key === "p") propose(false);
  else if (e.key === "o") browse("");
  else if (e.key === "d") showDashboard();
});

$("reviewer").value = localStorage.getItem("formslang.reviewer") || "";
PROPOSE_LABEL = $("btn-propose").innerHTML;
refresh(false)
  /* A run started before this window opened still owns the screen. */
  .then(() => api("/api/job"))
  .then((j) => { if (j.running) { job = j; jobStart = Date.now(); paintWorking(); poll(); } })
  .catch((e) => toast(e.message, true));
</script>
</body>
</html>
"""
