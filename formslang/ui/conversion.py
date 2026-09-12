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
  paintReviewStatus();
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
  // Queued units stay readable; editing resumes after their result arrives.
  const mine = !!(running() && selected && selected === job.current_id);
  const ahead = !!(selected && !mine && queue.has(selected));
  box.hidden = !mine;
  $("out-queued").hidden = !ahead;
  if (ahead) {
    $("out-queued").textContent =
      "in queue · " + Math.max(0, (job.queue || []).indexOf(selected)) + " ahead";
  }
  if (!mine) return;
  const who = job.provider || providerLabel();
  $("busy-title").textContent = "Reading this unit and writing the APEX version";
  $("busy-sub").textContent = who +
    " is preparing a proposal from this unit. You can read the source, inspect evidence or review another unit while it runs.";
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
  if (running() || decisionBusy) return;
  const body = all ? { all: true, context_id: state.context_id } : { task_id: selected, context_id: state.context_id };
  if (!all && !selected) return;
  const targets = all ? state.tasks.filter((t) => !t.proposal) : state.tasks.filter((t) => t.id === selected);
  if (targets.some((t) => reviewDrafts.has(draftKey(t)))) {
    toast("Save a review decision or discard your edits before replacing this code with an AI proposal.", true);
    return;
  }
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
    queue: targets.map((t) => t.id), provider: providerLabel(),
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

let conversionPollGeneration = 0;
function poll() {
  const generation = ++conversionPollGeneration;
  clearTimeout(polling);
  if (!jobStart) jobStart = Date.now();
  startTicker();
  let seen = (job && ((job.done || 0) + (job.failed || 0))) || 0;
  let missed = 0;
  const check = async () => {
    let snap;
    try { snap = await api("/api/job"); }
    catch (e) {
      if (generation !== conversionPollGeneration) return;
      missed++;
      if (missed === 3) toast("Connection interrupted. Checking the conversion again; your edits are kept.", true);
      polling = setTimeout(check, Math.min(10000, 1000 * missed));
      return;
    }
    if (generation !== conversionPollGeneration) return;
    missed = 0;
    job = snap;
    if (snap.running) {
      paintWorking();
      // A long run must not leave finished units looking unconverted: pull the
      // real proposals in as soon as the server reports one landing, not only
      // once the whole queue is done.
      const done = (snap.done || 0) + (snap.failed || 0);
      if (done !== seen) {
        try { await refresh(); seen = done; }
        catch (e) { toast("Conversion continues, but the latest result could not be loaded: " + e.message, true); }
      }
      if (generation === conversionPollGeneration) polling = setTimeout(check, 1000);
      return;
    }
    clearTimeout(polling);
    stopTicker();
    job = null;
    jobStart = 0;
    paintWorking();
    resetProposeButton();
    if (snap.error) toast(snap.error, true);
    else if (snap.failed) toast(`${snap.failed} of ${snap.total} conversion(s) failed — ${snap.last_error}`, true);
    else if (snap.total) toast(`Converted ${snap.done} unit(s). Review the proposals before approving.`);
    try { await refresh(); }
    catch (e) { toast("Conversion finished. Reload to retrieve the latest proposals: " + e.message, true); }
  };
  polling = setTimeout(check, 500);
}

/* ── overlay: which module, which model ────────────────── */
"""

EXPORT_JS = r"""function exportApex() {
  if (!state.session.title) { toast("Open a Forms module first.", true); return; }
  const suggested = state.session.title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "formslang-app";
  openModal("Export Oracle APEX 26.1");
  $("modal-path").textContent = "APEXlang project + import ZIP";
  $("modal-hint").textContent =
    "Only approved conversions enter the app. An approved WHEN-VALIDATE rule ships as an enabled page validation; everything else starts as a disabled page process until its execution point and condition are confirmed in Page Designer.";
  $("modal-body").innerHTML = `
    <div class="export-form">
      <label class="wide">Application name<input name="name" value="${esc(state.session.title)}"></label>
      <label>Application alias<input name="alias" value="${esc(suggested)}"></label>
      <label>Application ID<input name="app_id" type="number" min="1" value="100"></label>
      <label>Workspace (optional)<input name="workspace" placeholder="resolved during import"></label>
      <label>Parsing schema (optional)<input name="schema" placeholder="resolved during import"></label>
      <label>Page number<input name="page" type="number" min="1" value="1"></label>
      <label class="wide checkbox"><input type="checkbox" name="ai_layout"> Ask the AI provider to lay out the regions the rules could not place cleanly (uses the model in Settings; the plan is cached on this session)</label>
      <label class="wide checkbox"><input type="checkbox" name="import_now"> Import into APEX right after building (runs SQLcl for you, locally)</label>
    </div>
    <div class="bind-section" hidden>
      <div class="bind-head">Data binding</div>
      <div class="bind-lead">A block only becomes a form APEX fetches and saves once you name the column that identifies one row. The answer is saved with your name and today's date. A wrong key raises no error &mdash; it fetches and saves the wrong row.</div>
      <div class="bind-rows"></div>
    </div>
    <div class="import-note cli"><span>Same build from a terminal or CI:</span> <code data-cli></code></div>
    <div class="import-note warn" hidden></div>
    <div class="export-form import-fields" hidden>${importFieldsHtml({})}</div>
    <div class="import-result" hidden></div>`;
  $("modal-foot").style.display = "flex";
  $("modal-input").style.display = "none";
  const body = $("modal-body");
  const form = body.querySelector(".export-form");
  const importFields = body.querySelector(".import-fields");
  const importNote = body.querySelector(".import-note.warn");
  const resultBox = body.querySelector(".import-result");
  const importNow = form.querySelector('[name="import_now"]');
  const go = $("modal-go");
  const labelGo = () => { go.textContent = importNow.checked ? "Build ZIP & import into APEX" : "Build import ZIP"; };
  importNow.onchange = () => {
    importFields.hidden = !importNow.checked;
    importNote.hidden = !(importNow.checked && importNote.textContent);
    labelGo();
  };
  labelGo();
  // The exact command line that reproduces this dialog -- the same export,
  // the same bytes -- kept in step with the fields as they are edited.
  const value = (name) => form.querySelector(`[name="${name}"]`).value.trim();
  const aiLayout = form.querySelector('[name="ai_layout"]');
  const cliLine = body.querySelector("[data-cli]");
  const bindSection = body.querySelector(".bind-section");
  const bindRows = bindSection.querySelector(".bind-rows");
  // What was confirmed before this dialog opened, so the CLI line knows the
  // difference between "never bound" and "just withdrawn" -- only the second
  // one is a --forget-key.
  let bindConfirmed = {};
  const bindKeys = () => {
    const keys = {};
    bindRows.querySelectorAll("select[data-block]").forEach((s) => { keys[s.dataset.block] = s.value; });
    return keys;
  };
  const showCli = () => {
    cliLine.textContent = exportCommand(state.session_path, {
      app_id: value("app_id"), alias: value("alias"), page: value("page"),
      workspace: value("workspace"), schema: value("schema"),
      ai_layout: aiLayout.checked, keys: bindKeys(), confirmed: bindConfirmed,
    });
  };
  form.oninput = showCli;
  aiLayout.onchange = showCli;
  showCli();
  // The saved connection, whether SQLcl is reachable and the previous
  // export's choices arrive after the dialog is already up, so a slow lookup
  // never delays opening it. A field the user already changed is left alone.
  // Which blocks a confirmed key could turn into a form. Fetched beside the
  // lookup below rather than before the dialog opens, for the same reason:
  // parsing the module must never be what the reviewer waits on.
  api("/api/bindings").then((data) => {
    const list = data.candidates || [];
    bindConfirmed = {};
    list.forEach((c) => { if (c.confirmed_key) bindConfirmed[c.block] = c.confirmed_key; });
    bindRows.innerHTML = bindSectionHtml(list);
    bindRows.querySelectorAll("select[data-block]").forEach((s) => { s.onchange = showCli; });
    bindSection.hidden = false;
    showCli();
  }).catch(() => {});

  api("/api/exports").then((data) => {
    const d = data.import || {};
    importFields.innerHTML = importFieldsHtml(d);
    if (!d.sqlcl_found) {
      importNote.textContent = "SQLcl was not found on PATH. Set its path in Settings (or the FORMSLANG_SQLCL_PATH environment variable) before importing.";
      importNote.hidden = !importNow.checked;
    }
    const last = data.last_export || {};
    for (const name of ["name", "alias", "app_id", "workspace", "schema", "page"]) {
      const el = form.querySelector(`[name="${name}"]`);
      const v = last[name];
      if (el && el.value === el.defaultValue && v !== undefined && v !== null && v !== "") el.value = v;
    }
    showCli();
  }).catch(() => {});

  go.onclick = async () => {
    go.disabled = true;
    go.innerHTML = `<span class="spin"></span> Building ZIP…`;
    let zipName, dataBinding;
    try {
      const r = await api("/api/export", {
        name: value("name"), alias: value("alias"), app_id: value("app_id"),
        workspace: value("workspace"), schema: value("schema"), page: value("page"),
        ai_layout: aiLayout.checked ? "1" : "",
        keys: bindKeys(),
      });
      zipName = r.zip.split(/[\\/]/).pop();
      dataBinding = r.data_binding;
      toast(`APEXlang ZIP ready: ${r.zip}`);
    } catch (e) { toast(e.message, true); go.disabled = false; labelGo(); return; }
    if (!importNow.checked) {
      go.disabled = false; labelGo();
      // A page that binds is the whole point of confirming a key, so say
      // what happened to each block instead of closing over it.
      const summary = bindResultHtml(dataBinding);
      if (summary) {
        resultBox.hidden = false;
        resultBox.innerHTML = summary;
        go.textContent = "Show exports";
        go.onclick = () => { closeModal(); showExports(zipName); };
        return;
      }
      closeModal();
      showExports(zipName);
      return;
    }
    $("modal-path").textContent = zipName;
    go.textContent = "Importing…";
    const ok = await runImport(zipName, importFields, false, go, resultBox);
    if (ok) {
      go.textContent = "Show exports";
      go.onclick = () => { closeModal(); showExports(zipName); };
    } else {
      // The ZIP is built; only the import failed. Fix the connection and try again without rebuilding.
      go.textContent = "Retry import";
      go.onclick = async () => {
        const again = await runImport(zipName, importFields, false, go, resultBox);
        if (again) { go.textContent = "Show exports"; go.onclick = () => { closeModal(); showExports(zipName); }; }
      };
    }
  };
}

/* The `formslang export` line that rebuilds what the dialog is about to
   build. Only values the CLI would not derive on its own are spelled out. */
function exportCommand(sessionPath, c) {
  const file = (sessionPath || "<session.db>").split(/[\\/]/).pop();
  const parts = ["formslang export", file];
  if (c.app_id) parts.push("--app-id", c.app_id);
  if (c.alias) parts.push("--alias", c.alias);
  if (c.page && c.page !== "1") parts.push("--page", c.page);
  if (c.workspace) parts.push("--workspace", c.workspace);
  if (c.schema) parts.push("--schema", c.schema);
  if (c.ai_layout) parts.push("--ai-layout");
  for (const block of Object.keys(c.keys || {}).sort()) {
    const column = c.keys[block];
    if (column) parts.push("--key", `${block}=${column}`);
    else if ((c.confirmed || {})[block]) parts.push("--forget-key", block);
  }
  return parts.join(" ");
}

/* One row per block a confirmed key could bind.

   The column is picked from a list and never typed. A column the block does
   not place on the page is refused by the exporter without ever saying so on
   screen -- the region just stays unbound, with the reason buried in the
   manifest -- so a text box here would turn a typo into a silently unbound
   page. The .fmb's own PrimaryKey flag is shown and deliberately never
   pre-selected: Forms keeps that flag for its own locking and it can
   disagree with the table's real key, and a wrong key raises nothing at run
   time. It fetches and saves the wrong row. */
function bindSectionHtml(list) {
  if (!list.length) {
    return `<div class="bind-empty">No block qualifies yet &mdash; binding needs a single-record block on a table whose fields all sit in one region of their own.</div>`;
  }
  return list.map((c) => {
    const options = [`<option value="">&mdash; leave unbound &mdash;</option>`].concat(
      (c.columns || []).map((col) =>
        `<option value="${esc(col)}"${col === c.confirmed_key ? " selected" : ""}>${esc(col)}</option>`)
    ).join("");
    const hint = c.forms_hint
      ? `the .fmb hints at ${esc(c.forms_hint)}`
      : "the .fmb hints at nothing";
    const who = c.confirmed_key && c.confirmed_by
      ? ` &middot; confirmed by ${esc(c.confirmed_by)}${c.confirmed_at ? " &middot; " + esc(String(c.confirmed_at).slice(0, 10)) : ""}`
      : "";
    return `<div class="bind-row">
      <div><b>${esc(c.block)}</b> &rarr; ${esc(c.table)}<div class="bind-note">${hint}${who}</div></div>
      <label>key column<select data-block="${esc(c.block)}">${options}</select></label>
    </div>`;
  }).join("");
}

/* What the export just did with each block, in the exporter's own words. */
function bindResultHtml(entries) {
  if (!entries || !entries.length) return "";
  return entries.map((e) => e.bound
    ? `<div>Bound: ${esc(e.block)} &rarr; ${esc(e.table)} on ${esc(e.confirmed_key)}</div>`
    : `<div class="bind-note">Unbound: ${esc(e.block)} &mdash; ${esc(e.reason)}</div>`).join("");
}

/* Connection fields shared by the export dialog and the per-ZIP import
   dialog. The password box is never pre-filled: a saved password stays in
   the OS credential store and is only ever hinted at. */
function importFieldsHtml(d) {
  return `
      <label class="wide">Connection string<input name="connect_string" placeholder="host:port/service_name" value="${esc(d.connect_string || "")}"></label>
      <label>Username (schema)<input name="username" value="${esc(d.username || "")}"></label>
      <label>Password<input name="password" type="password" placeholder="${d.has_saved_password ? "using the saved password" : "required"}"></label>
      <label class="wide checkbox"><input type="checkbox" name="remember"> Remember this connection (password goes to the OS credential store)</label>`;
}

/* One import run against one ZIP. Returns true on success; the result box
   keeps SQLcl's own output either way so a failure is readable in place. */
async function runImport(name, form, validateOnly, button, resultBox) {
  const value = (n) => form.querySelector(`[name="${n}"]`).value.trim();
  const original = button.textContent;
  button.disabled = true;
  button.textContent = validateOnly ? "Validating…" : "Importing…";
  try {
    const r = await api("/api/exports/import", {
      name,
      connect_string: value("connect_string"),
      username: value("username"),
      password: form.querySelector('[name="password"]').value,
      remember: form.querySelector('[name="remember"]').checked,
      validate_only: validateOnly,
    });
    resultBox.hidden = false;
    resultBox.className = "import-result " + (r.ok ? "ok" : "bad");
    // SQLcl exits 0 even when it prints "APEXlang Compile Errors" and imports
    // nothing, so a failure with exit 0 is labelled by what actually happened.
    const verdict = r.ok ? "OK"
      : r.exit_code === 0 ? "Failed (SQLcl reported errors; nothing was imported)"
      : `Failed (exit ${r.exit_code})`;
    // Never let a bare "OK" imply a workspace checked it: an offline run
    // proves the package compiles, not that this database would take it.
    const header = verdict + (r.offline ? " — offline (SQLcl's APEXlang compiler; no database)" : "");
    resultBox.textContent = header + "\n" + (r.stdout || "") + (r.stderr || "");
    if (r.ok) toast(validateOnly ? (r.offline ? "Validation passed (offline)." : "Validation passed.") : "Imported into APEX.");
    return !!r.ok;
  } catch (e) { toast(e.message, true); return false; }
  finally { button.disabled = false; button.textContent = original; }
}

async function showExports(freshName) {
  let data;
  try { data = await api("/api/exports"); } catch (e) { toast(e.message, true); return; }
  openModal("Exported APEX applications");
  $("modal-path").textContent = data.dir || "";
  $("modal-hint").textContent =
    "Each ZIP imports straight into APEX 26.1 — App Builder, SQLcl, or `formslang apex import <zip>` from a terminal or CI. Show in folder selects the file on disk.";
  $("modal-foot").style.display = "none";
  const size = (b) => (b >= 1048576 ? (b / 1048576).toFixed(1) + " MB" : Math.max(1, Math.round(b / 1024)) + " KB");
  const rows = (data.exports || []).map((e) => `
    <div class="exp-row${e.name === freshName ? " fresh" : ""}">
      <span class="exp-name">${esc(e.name)}</span>
      <span class="exp-meta">${size(e.size)} &middot; ${esc(new Date(e.mtime * 1000).toLocaleString())}</span>
      <button class="btn" data-reveal="${esc(e.name)}">Show in folder</button>
      <button class="btn" data-import="${esc(e.name)}">Import to database…</button>
    </div>`).join("");
  $("modal-body").innerHTML =
    `<div class="exports-list">${rows || '<div class="empty">No exports yet — press Export APEX 26.1 first.</div>'}</div>`;
  $("modal-body").querySelectorAll("[data-reveal]").forEach((b) => {
    b.onclick = async () => {
      try { await api("/api/exports/open", { name: b.dataset.reveal }); }
      catch (e) { toast(e.message, true); }
    };
  });
  $("modal-body").querySelectorAll("[data-import]").forEach((b) => {
    b.onclick = () => showImportForm(b.dataset.import, data.import || {});
  });
}

function showImportForm(name, defaults) {
  openModal(`Import into APEX`);
  $("modal-path").textContent = name;
  $("modal-hint").textContent =
    "Runs SQLcl for you, locally. Your password is used once for this run and is never saved unless you " +
    "check Remember, which puts it in this computer's own credential manager — nothing is shared with anyone else.";
  const note = defaults.sqlcl_found
    ? ""
    : `<div class="import-note warn">SQLcl was not found on PATH. Set its path in Settings (or the FORMSLANG_SQLCL_PATH environment variable) first.</div>`;
  $("modal-body").innerHTML = `
    ${note}
    <div class="export-form">${importFieldsHtml(defaults)}</div>
    <button class="import-secondary">Validate only, don't change anything</button>
    <div class="import-note">Leave the three fields empty and Validate still works: SQLcl compiles the package
      against its own APEXlang grammar — no database, no workspace, no password. Narrower than validating against
      your workspace, and still Oracle's verdict rather than FormsLang's.</div>
    <div class="import-note cli"><span>Same from a terminal or CI (password via FORMSLANG_APEX_PASSWORD, never an argument):</span>
      <code>formslang apex validate ${esc(name)} --offline</code> · <code>formslang apex validate ${esc(name)}</code> · <code>formslang apex import ${esc(name)}</code></div>
    <div class="import-result" hidden></div>`;
  $("modal-foot").style.display = "flex";
  $("modal-input").style.display = "none";
  $("modal-go").textContent = "Import into APEX";

  const form = $("modal-body").querySelector(".export-form");
  const validateBtn = $("modal-body").querySelector(".import-secondary");
  const resultBox = $("modal-body").querySelector(".import-result");
  $("modal-go").onclick = () => runImport(name, form, false, $("modal-go"), resultBox);
  validateBtn.onclick = () => runImport(name, form, true, validateBtn, resultBox);
}

/* ── the project view ──────────────────────────────────── */
/* Every figure here is a count over rows already on disk. The readiness
   score is the only one that could be read as a verdict, so it is printed
   next to the formula that produced it, weight by weight. */
"""
