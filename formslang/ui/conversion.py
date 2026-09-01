"""The AI conversion run (propose/poll/progress) and the APEX export flow -- split out of formslang/ui.py."""

from __future__ import annotations

JOB_PROGRESS_JS = r"""function elapsed() {
  const s = Math.max(0, Math.round((Date.now() - jobStart) / 1000));
  return s < 60 ? s + "s" : Math.floor(s / 60) + "m " + String(s % 60).padStart(2, "0") + "s";
}
function providerLabel() { return $("provider").textContent || "the model"; }
function running() { return !!(job && job.running); }

function paintWorking() {
  const on = running();
  $("working").hidden = !on;
  $("bar").classList.toggle("busy", on);
  if (on) {
    const at = Math.min((job.done || 0) + 1, job.total || 1);
    $("working-what").innerHTML = job.current
      ? `Converting <b>${esc(job.current)}</b> — unit ${at} of ${job.total}`
      : `Starting the conversion — unit ${at} of ${job.total}`;
    const left = Math.max(0, (job.total || 0) - (job.done || 0));
    $("working-meta").textContent =
      [job.provider || providerLabel(), elapsed(), left + " left"].join(" · ");
    const btn = $("btn-propose-all");
    btn.disabled = true;
    btn.textContent = `Converting ${job.done || 0}/${job.total}…`;
  }
  paintBusyRows();
  paintBusyPane();
}

function paintBusyRows() {
  const queue = new Set(running() ? (job.queue || []) : []);
  document.querySelectorAll("#list .row").forEach((r) => {
    const id = r.dataset.id;
    const working = running() && id === job.current_id;
    r.classList.toggle("working", working);
    r.classList.toggle("queued", queue.has(id) && !working);
    const cell = r.querySelector(".state");
    if (!cell) return;
    if (working) { if (!cell.firstElementChild) cell.innerHTML = `<span class="spin"></span>`; }
    else if (cell.firstElementChild) cell.textContent = cell.dataset.mark || "●";
  });
}

function paintBusyPane() {
  const box = $("out-busy");
  if (!box) return;
  const queue = new Set(running() ? (job.queue || []) : []);
  // Only the unit being written is covered: its answer is about to replace
  // whatever is in the box. A unit merely waiting in line stays editable --
  // a queue of fifty must not lock fifty panes.
  const mine = !!(running() && selected && selected === job.current_id);
  const ahead = !!(selected && !mine && queue.has(selected));
  box.hidden = !mine;
  $("out-queued").hidden = !ahead;
  if (ahead) {
    $("out-queued").textContent =
      "in queue · " + Math.max(1, (job.total || 0) - (job.done || 0) - 1) + " ahead";
  }
  if (!mine) return;
  const who = job.provider || providerLabel();
  $("busy-title").textContent = "Reading this unit and writing the APEX version";
  $("busy-sub").textContent = who +
    " has the whole trigger body, its built-ins and its globals. One unit usually takes 15 to 60 seconds; the proposal lands here the moment it answers.";
  $("busy-tick").textContent = elapsed() + " elapsed";
}

function startTicker() {
  stopTicker();
  ticker = setInterval(() => { if (running()) paintWorking(); }, 1000);
}
function stopTicker() { if (ticker) clearInterval(ticker); ticker = null; }
function resetProposeButton() {
  const btn = $("btn-propose");
  btn.disabled = false;
  if (PROPOSE_LABEL) btn.innerHTML = PROPOSE_LABEL;
}

"""

PROPOSE_AND_POLL_JS = r"""async function propose(all) {
  const body = all ? { all: true } : { task_id: selected };
  if (!all && !selected) return;
  const btn = all ? $("btn-propose-all") : $("btn-propose");
  const before = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = all ? "Sending…" : `<span class="spin"></span> Converting…`;
  // Paint the working state before the server answers. Starting a CLI run can
  // take a couple of seconds on its own, and a screen that does not move in
  // that gap reads as a broken button.
  const here = state.tasks.find((x) => x.id === selected);
  jobStart = Date.now();
  job = {
    running: true, done: 0, failed: 0, total: all ? Math.max(1, state.stats.unproposed || 1) : 1,
    current: all ? "" : (here || {}).title || "", current_id: all ? "" : selected,
    queue: all ? [] : [selected], provider: providerLabel(),
  };
  paintWorking();
  startTicker();
  try {
    await api("/api/propose", body);
  } catch (e) {
    job = null; stopTicker(); paintWorking();
    btn.disabled = false; btn.innerHTML = before;
    toast(e.message, true);
    return;
  }
  poll();
}

function poll() {
  clearInterval(polling);
  if (!jobStart) jobStart = Date.now();
  startTicker();
  let seen = (job && ((job.done || 0) + (job.failed || 0))) || 0;
  let refreshing = false;
  polling = setInterval(async () => {
    let snap;
    try { snap = await api("/api/job"); }
    catch (e) { return; }  // one missed poll is not the end of the run
    job = snap;
    if (snap.running) {
      paintWorking();
      // A long run must not leave finished units looking unconverted: pull the
      // real proposals in as soon as the server reports one landing, not only
      // once the whole queue is done.
      const done = (snap.done || 0) + (snap.failed || 0);
      if (done !== seen && !refreshing) {
        seen = done;
        refreshing = true;
        const keep = selected;
        refresh()
          .then(() => { if (keep) { selected = keep; renderList(); renderDetail(); } })
          .finally(() => { refreshing = false; });
      }
      return;
    }
    clearInterval(polling);
    stopTicker();
    job = null;
    jobStart = 0;
    paintWorking();
    resetProposeButton();
    if (snap.error) toast(snap.error, true);
    else if (snap.failed) toast(`${snap.failed} of ${snap.total} conversion(s) failed — ${snap.last_error}`, true);
    else if (snap.total) toast(`Converted ${snap.done} unit(s). Now read them.`);
    const keep = selected;
    await refresh();  // restores the button's own label from the new counts
    if (keep) { selected = keep; renderList(); renderDetail(); }
  }, 700);
}

/* ── overlay: which module, which model ────────────────── */
"""

EXPORT_JS = r"""function exportApex() {
  if (!state.session.title) { toast("Open a Forms module first.", true); return; }
  const suggested = state.session.title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "formslang-app";
  openModal("Export Oracle APEX 26.1");
  $("modal-path").textContent = "APEXlang project + import ZIP";
  $("modal-hint").textContent =
    "Only approved conversions enter the app. Generated processes start disabled until their execution point and condition are confirmed in Page Designer.";
  $("modal-body").innerHTML = `
    <div class="export-form">
      <label class="wide">Application name<input name="name" value="${esc(state.session.title)}"></label>
      <label>Application alias<input name="alias" value="${esc(suggested)}"></label>
      <label>Application ID<input name="app_id" type="number" min="1" value="100"></label>
      <label>Workspace (optional)<input name="workspace" placeholder="resolved during import"></label>
      <label>Parsing schema (optional)<input name="schema" placeholder="resolved during import"></label>
      <label>Page number<input name="page" type="number" min="1" value="1"></label>
    </div>`;
  $("modal-foot").style.display = "flex";
  $("modal-input").style.display = "none";
  $("modal-go").textContent = "Build import ZIP";
  $("modal-go").onclick = async () => {
    const form = $("modal-body").querySelector(".export-form");
    const value = (name) => form.querySelector(`[name="${name}"]`).value.trim();
    const go = $("modal-go");
    go.disabled = true;
    go.innerHTML = `<span class="spin"></span> Building ZIP…`;
    try {
      const r = await api("/api/export", {
        name: value("name"), alias: value("alias"), app_id: value("app_id"),
        workspace: value("workspace"), schema: value("schema"), page: value("page"),
      });
      closeModal();
      toast(`APEXlang ZIP ready: ${r.zip}`);
      showExports(r.zip.split(/[\/]/).pop());
    } catch (e) { toast(e.message, true); }
    finally { $("modal-go").disabled = false; $("modal-go").textContent = "Build import ZIP"; }
  };
}

async function showExports(freshName) {
  let data;
  try { data = await api("/api/exports"); } catch (e) { toast(e.message, true); return; }
  openModal("Exported APEX applications");
  $("modal-path").textContent = data.dir || "";
  $("modal-hint").textContent =
    "Each ZIP imports straight into APEX 26.1 — App Builder or SQLcl. Show in folder selects the file on disk.";
  $("modal-foot").style.display = "none";
  const size = (b) => (b >= 1048576 ? (b / 1048576).toFixed(1) + " MB" : Math.max(1, Math.round(b / 1024)) + " KB");
  const rows = (data.exports || []).map((e) => `
    <div class="exp-row${e.name === freshName ? " fresh" : ""}">
      <span class="exp-name">${esc(e.name)}</span>
      <span class="exp-meta">${size(e.size)} &middot; ${esc(new Date(e.mtime * 1000).toLocaleString())}</span>
      <button class="btn" data-reveal="${esc(e.name)}">Show in folder</button>
    </div>`).join("");
  $("modal-body").innerHTML =
    `<div class="exports-list">${rows || '<div class="empty">No exports yet — press Export APEX 26.1 first.</div>'}</div>`;
  $("modal-body").querySelectorAll("[data-reveal]").forEach((b) => {
    b.onclick = async () => {
      try { await api("/api/exports/open", { name: b.dataset.reveal }); }
      catch (e) { toast(e.message, true); }
    };
  });
}

/* ── the project view ──────────────────────────────────── */
/* Every figure here is a count over rows already on disk. The readiness
   score is the only one that could be read as a verdict, so it is printed
   next to the formula that produced it, weight by weight. */
"""
