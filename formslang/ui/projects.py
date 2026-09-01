"""Opening a Forms module (file picker / upload) and the project-wide dashboard -- split out of formslang/ui.py."""

from __future__ import annotations

PICKER_JS = r"""async function browse(dir) {
  let d;
  try { d = await api("/api/browse" + (dir ? "?dir=" + encodeURIComponent(dir) : "")); }
  catch (e) { toast(e.message, true); return; }

  openModal("Import a Forms module");
  $("modal-path").textContent = d.dir;
  $("modal-hint").textContent =
    "Choose the exact FMB you want to convert. FormsLang works from a private copy and leaves the original untouched.";
  const dirs = d.dirs.map((x) =>
    `<div class="entry dir" data-dir="${esc(x.path)}"><span class="icon">DIR</span><span class="name">${esc(x.name)}</span><span class="tag">Open folder</span></div>`).join("");
  const mods = d.modules.map((m) => {
    const ext = m.name.split(".").pop().toUpperCase();
    return `<div class="entry mod ${ext === "XML" ? "xml" : ""}" data-mod="${esc(m.path)}"><span class="icon">${ext}</span>` +
      `<span class="name">${esc(m.name)}</span>` +
      `<span class="tag">${m.kb} KB${m.has_session ? " / Resume" : " / New"}</span></div>`;
  }).join("");
  $("modal-body").innerHTML = `
    <div class="picker-shell">
      <div class="picker-hero">
        <div class="dropzone" tabindex="0">
          <div class="dropmark">FMB</div>
          <div class="dropcopy">
            <strong>Select the Oracle Forms file</strong>
            <p>Drag it here or use the Windows file selector.</p>
            <button class="btn primary" type="button" data-pick>Select FMB / XML</button>
            <input type="file" accept=".fmb,.mmb,.xml" hidden>
          </div>
        </div>
        <div class="picker-info">
          <strong>What happens next?</strong>
          <p>Oracle reads the FMB, then FormsLang opens a resumable review session for that module.</p>
          <div class="safety"><i>&#10003;</i><span>The original file and its folder are never changed.</span></div>
        </div>
      </div>
      <div class="picker-nav">
        <button class="btn" type="button" data-home>&#8962; Start folder</button>
        ${d.parent ? `<button class="btn" type="button" data-up>&uarr; Up</button>` : ""}
        <span class="current" title="${esc(d.dir)}">${esc(d.dir)}</span>
      </div>
      <div class="group">Folders and Forms modules</div>
      <div class="picker-files">${dirs + mods || `<div class="picker-empty">No Forms modules in this folder.<br>Drop a file above or choose another folder.</div>`}</div>
    </div>`;
  foot({ placeholder: "Paste a full path to .fmb, .mmb, .xml or .session.db", button: "Open path", run: openModule });

  const body = $("modal-body");
  body.querySelectorAll(".entry.dir").forEach((e) => (e.onclick = () => browse(e.dataset.dir)));
  body.querySelectorAll(".entry.mod").forEach((e) => (e.onclick = () => openModule(e.dataset.mod)));
  const input = body.querySelector('input[type="file"]');
  const drop = body.querySelector(".dropzone");
  body.querySelector("[data-pick]").onclick = () => input.click();
  body.querySelector("[data-home]").onclick = () => browse("");
  const up = body.querySelector("[data-up]");
  if (up) up.onclick = () => browse(d.parent);
  input.onchange = () => input.files[0] && uploadModule(input.files[0]);
  drop.onkeydown = (e) => {
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); input.click(); }
  };
  for (const event of ["dragenter", "dragover"])
    drop.addEventListener(event, (e) => { e.preventDefault(); drop.classList.add("drag"); });
  for (const event of ["dragleave", "drop"])
    drop.addEventListener(event, (e) => { e.preventDefault(); drop.classList.remove("drag"); });
  drop.addEventListener("drop", (e) => e.dataTransfer.files[0] && uploadModule(e.dataTransfer.files[0]));
}

async function uploadModule(file) {
  if (!file) return;
  if (!/\.(fmb|mmb|xml)$/i.test(file.name)) {
    toast("Choose an .fmb, .mmb or .xml file.", true); return;
  }
  $("modal-body").innerHTML = `<div class="uploading"><div class="spinner"></div><strong>Importing ${esc(file.name)}</strong><span>Copying safely, then running the Oracle Forms converter...</span></div>`;
  foot(null);
  try {
    const response = await fetch("/api/upload?name=" + encodeURIComponent(file.name), {
      method: "POST", headers: { "Content-Type": "application/octet-stream" }, body: file,
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
    deps = {}; tests = {};  // another module, another graph and another specification
    closeModal();
    await refresh(false);
    toast(`${data.title}: ${data.stats.tasks} unit(s) ready for review.`);
  } catch (e) {
    toast(e.message, true);
    browse("");
  }
}

async function openModule(path) {
  if (!path) return;
  $("modal-body").innerHTML = `<div class="uploading"><div class="spinner"></div><strong>Opening ${esc(path.split(/[\\/]/).pop())}</strong>` +
    `<span>An .fmb goes through Oracle's converter first, then every trigger and program unit is indexed.</span></div>`;
  foot(null);
  try {
    const r = await api("/api/open", { path });
    deps = {}; tests = {};  // another module, another graph and another specification
    closeModal();
    await refresh(false);
    toast(`${r.title}: ${r.stats.tasks} unit(s)${r.added ? "" : " — resumed, nothing new"}`);
  } catch (e) {
    toast(e.message, true);
    browse("");
  }
}

/* Settings: which model converts, with what credentials. CLI providers ride
   your existing subscription; API providers take a key that is stored on this
   machine, write-only — the browser never sees it again. */
"""

DASHBOARD_JS = r"""const pct = (n, of) => (of ? Math.round((100 * n) / of) : 0);

function bars(rows, total) {
  if (!rows.length) return `<div class="none">nothing counted yet</div>`;
  return rows.map(([label, n, cls]) => `
    <div class="brow ${cls || ""}">
      <span>${esc(label)}</span>
      <span class="track"><i style="width:${pct(n, total)}%"></i></span>
      <span class="cnt">${n}</span>
    </div>`).join("");
}

function readyCard(d) {
  const r = d.readiness || {}, m = d.readiness_model || {};
  const got = {};
  (r.components || []).forEach((c) => (got[c.key] = c));
  const rows = (m.components || []).map((c) => {
    const g = got[c.key] || {};
    return `<tr>
      <td>${esc(c.title)}<div class="d">${esc(c.detail)}</div></td>
      <td class="n">${c.weight}</td>
      <td class="n">${Math.round((g.ratio || 0) * 100)}%</td>
      <td class="n">${(g.points || 0).toFixed(1)}</td>
    </tr>`;
  }).join("");
  return `<div class="card ready">
    <div>
      <div class="num">${r.score}</div>
      <div class="of">OF ${r.of} &middot; MIGRATION READINESS</div>
      <div class="gauge"><i style="width:${pct(r.score, r.of)}%"></i></div>
      <div class="caveat">${esc(m.caveat || "")}</div>
      <div class="ver">${esc(m.version || "")} &middot; ${esc(m.engine_version || "")}</div>
    </div>
    <div>
      <h3>How this number is calculated</h3>
      <table class="formula">
        <tr><th>Component</th><th>Weight</th><th>Measured</th><th>Points</th></tr>
        ${rows}
        <tr class="sum"><td><b>readiness</b><div class="d">${esc(m.formula || "")}</div></td>
          <td class="n">${m.total_weight}</td><td class="n">&mdash;</td><td class="n"><b>${r.score}</b></td></tr>
      </table>
    </div>
  </div>`;
}

function riskTable(d) {
  const rows = d.highest_risk || [];
  if (!rows.length) return `<div class="none">No unit has been analysed yet.</div>`;
  return `<table class="dtable">
    <tr><th>Unit</th><th>Risk</th><th>Behaviour</th><th>Mode</th><th>State</th><th>Score</th></tr>
    ${rows.map((r) => `<tr class="pick" data-go="${esc(r.task_id)}">
      <td class="mono">${esc(r.title)}<div class="sub">${esc(r.kind)} &middot; ${r.factors} factor(s)</div></td>
      <td class="r-${esc(r.level)} mono">${esc(r.level)}</td>
      <td class="bh-${esc(r.behavior)} mono">${esc(r.behavior || "—")}</td>
      <td class="v-${esc(r.verdict)} mono">${esc(r.verdict)}</td>
      <td class="st-${esc(r.state)} mono">${esc(r.state)}</td>
      <td class="n">${r.score}</td>
    </tr>`).join("")}
  </table>`;
}

function unsupportedTable(d) {
  const rows = d.unsupported || [];
  if (!rows.length) return `<div class="none">No unsupported construct in what has been analysed.</div>`;
  return `<table class="dtable">
    <tr><th>Built-in</th><th>Calls</th><th>Where it is called</th><th>What APEX offers</th></tr>
    ${rows.map((r) => `<tr>
      <td class="mono">${esc(r.name)}<div class="sub">${esc(r.category || "")}</div></td>
      <td class="n">${r.count}</td>
      <td class="sub">${(r.units || []).map(esc).join("<br>")}</td>
      <td class="sub">${esc(r.apex || "no direct replacement")}</td>
    </tr>`).join("")}
  </table>`;
}

function depCard(d) {
  const g = d.dependencies || {};
  if (!g.available) return `<div class="none">${esc(g.reason || "no dependency graph")}</div>`;
  const hubs = (g.hubs || []).map((h) => `<tr>
    <td class="mono">${esc(h.name || h.id)}<div class="sub">${esc(h.label || h.kind || "")}</div></td>
    <td class="n">${h.in}</td><td class="n">${h.out}</td><td class="n">${h.degree}</td>
  </tr>`).join("");
  return `<div class="cap" style="margin-bottom:9px;color:var(--ink-dim);font-size:12px;line-height:1.5">
      ${g.nodes} object(s), ${g.edges} link(s) &mdash; ${g.external} external, ${g.missing} referenced but not
      declared here, ${g.unresolved} name(s) the parser could not resolve. One session holds one form, so this
      ranks the objects inside <b>${esc(g.module || "")}</b> that the most other things lean on.
    </div>
    ${hubs
      ? `<table class="dtable"><tr><th>Object</th><th>Depended on by</th><th>Depends on</th><th>Total</th></tr>${hubs}</table>`
      : `<div class="none">nothing in this form depends on anything else</div>`}`;
}

async function showDashboard() {
  let d;
  try { d = await api("/api/dashboard"); } catch (e) { toast(e.message, true); return; }
  openModal("Project — " + ((d.session || {}).title || "session"));
  $("modal-path").textContent = (d.session || {}).source_path || "";
  $("modal-hint").textContent =
    "Counted from this session, never estimated: the deterministic analysis, your decisions, the dependency graph and the test specifications.";
  $("modal-foot").style.display = "none";

  const t = d.totals, cov = d.coverage, tc = d.test_coverage;
  const measured = `Measured on ${cov.analysed} of ${t.units} unit(s)` +
    (cov.missing ? `; ${cov.missing} still unanalysed and counted nowhere in this chart.` : ".");

  $("modal-body").innerHTML = `<div class="dash">
    ${readyCard(d)}

    <div>
      <h3>The session</h3>
      <div class="kpis">
        <div class="kpi"><b>${t.units}</b><span>units</span></div>
        <div class="kpi"><b>${t.lines}</b><span>lines of PL/SQL</span></div>
        <div class="kpi"><b>${t.proposed}</b><span>converted</span></div>
        <div class="kpi"><b>${d.percent.reviewed}%</b><span>reviewed</span></div>
        <div class="kpi"><b>${d.percent.approved}%</b><span>approved</span></div>
        <div class="kpi"><b>${tc.total}</b><span>test cases</span></div>
      </div>
    </div>

    <div class="dists">
      <div class="card dist"><h3>Conversion mode</h3>
        ${bars(Object.entries(d.conversion_modes).map(([k, n]) => [k, n, "v-" + k]), t.units)}
        <div class="cap">What the rules say the conversion costs. A different question from risk.</div>
      </div>
      <div class="card dist"><h3>Your decisions</h3>
        ${bars(Object.entries(d.decisions).map(([k, n]) => [k, n, "st-" + k]), t.units)}
        <div class="cap">Approval is a human act. Nothing on this screen moves it.</div>
      </div>
      <div class="card dist"><h3>Migration risk</h3>
        ${bars(Object.entries(d.risk).map(([k, n]) => [k, n, "r-" + k]), cov.analysed)}
        <div class="cap">${esc(measured)} Average score ${d.avg_risk_score}.</div>
      </div>
      <div class="card dist"><h3>Behaviour after migration</h3>
        ${bars(Object.entries(d.behavior).map(([k, n]) => [k, n, "bh-" + k]), cov.analysed)}
        <div class="cap">${esc(measured)}</div>
      </div>
    </div>

    <div><h3>What is in the way</h3>
      ${(d.blockers || []).length
        ? d.blockers.map((b) => `<div class="blk"><b>${b.count}</b><span>${esc(b.detail)}</span></div>`).join("")
        : `<div class="none">Nothing outstanding: every unit is analysed, converted, decided and specified.</div>`}
      <div class="cap" style="margin-top:8px;color:var(--ink-faint);font-size:11px">
        Deliberately left out of the score above &mdash; a blocker is work to do, not a percentage.</div>
    </div>

    <div><h3>Highest risk first</h3>${riskTable(d)}</div>
    <div><h3>Forms features APEX has no equivalent for</h3>${unsupportedTable(d)}</div>
    <div><h3>Where the dependencies pile up</h3>${depCard(d)}</div>
  </div>`;

  $("modal-body").querySelectorAll("[data-go]").forEach((tr) => {
    tr.onclick = () => { closeModal(); select(tr.dataset.go); };
  });
}

/* ── wiring ────────────────────────────────────────────── */
"""
