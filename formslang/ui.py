"""The workbench UI: one self-contained HTML document.

No build step, no framework, no CDN. The page ships inside the Python
package and is served from localhost, because the data on screen is the
customer's source code and it has no business travelling to a CDN to fetch a
font.

Everything the page shows comes from ``/api/state``; the page itself holds
no data and no secrets.
"""

from __future__ import annotations

INDEX_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>FormsLang Workbench</title>
<style>
  :root {
    --gold: #F5A640;
    --gold-dim: #b8791f;
    --black: #07090C;
    --graphite: #1A1D23;
    --graphite-2: #23272F;
    --bone: #F2F4F7;
    --grey: #8A9099;
    --green: #4ADE80;
    --red: #F87171;
    --violet: #A78BFA;
    --line: #2A2F38;
    --mono: ui-monospace, "Cascadia Mono", "JetBrains Mono", Consolas, monospace;
    --sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, system-ui, sans-serif;
  }
  * { box-sizing: border-box; }
  html, body { height: 100%; }
  body {
    margin: 0; background: var(--black); color: var(--bone);
    font: 14px/1.5 var(--sans); overflow: hidden;
  }
  button { font: inherit; cursor: pointer; }
  ::-webkit-scrollbar { width: 10px; height: 10px; }
  ::-webkit-scrollbar-thumb { background: #333a45; border-radius: 6px; }
  ::-webkit-scrollbar-track { background: transparent; }

  /* ── top bar ─────────────────────────────────────────── */
  header {
    display: flex; align-items: center; gap: 18px;
    height: 52px; padding: 0 18px; border-bottom: 1px solid var(--line);
    background: var(--graphite);
  }
  .brand { display: flex; align-items: baseline; gap: 8px; font-weight: 600; letter-spacing: -0.01em; }
  .brand .mark { color: var(--gold); }
  .brand small { color: var(--grey); font-weight: 400; font-size: 11px; letter-spacing: .12em; text-transform: uppercase; }
  .session { color: var(--grey); font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .spacer { flex: 1; }
  .chip {
    font: 11px/1 var(--mono); letter-spacing: .06em; text-transform: uppercase;
    padding: 5px 8px; border-radius: 4px; border: 1px solid var(--line); color: var(--grey);
    white-space: nowrap;
  }
  .chip.provider { border-color: var(--gold-dim); color: var(--gold); }
  .counts { display: flex; gap: 14px; font: 12px var(--mono); color: var(--grey); }
  .counts b { color: var(--bone); font-weight: 600; }
  .counts .ok b { color: var(--green); }
  .counts .no b { color: var(--red); }
  .btn {
    background: transparent; color: var(--bone); border: 1px solid var(--line);
    padding: 7px 12px; border-radius: 5px; transition: .12s;
  }
  .btn:hover { border-color: var(--gold-dim); color: var(--gold); }
  .btn.primary { background: var(--gold); border-color: var(--gold); color: #1a1206; font-weight: 600; }
  .btn.primary:hover { filter: brightness(1.08); color: #1a1206; }
  .btn:disabled { opacity: .4; cursor: not-allowed; }

  /* ── layout ──────────────────────────────────────────── */
  main { display: grid; grid-template-columns: 330px 1fr; height: calc(100% - 52px); }
  aside { border-right: 1px solid var(--line); display: flex; flex-direction: column; min-height: 0; background: #0B0E13; }
  /* Two filter rows, never one: "converted" and "decided" are different
     questions, and putting them in the same row of buttons taught people
     they were the same question. */
  .filters { display: flex; flex-direction: column; gap: 7px; padding: 10px; border-bottom: 1px solid var(--line); }
  .frow { display: flex; align-items: center; gap: 4px; flex-wrap: wrap; }
  .flabel {
    font: 10px var(--mono); letter-spacing: .1em; text-transform: uppercase;
    color: #4a5260; flex: 0 0 66px;
  }
  .frow button {
    background: transparent; border: 1px solid var(--line); color: var(--grey);
    font: 11px var(--mono); text-transform: uppercase; letter-spacing: .06em;
    padding: 4px 8px; border-radius: 4px;
  }
  .frow button.on { border-color: var(--gold); color: var(--gold); }
  .search { padding: 8px 10px; border-bottom: 1px solid var(--line); }
  .search input {
    width: 100%; background: var(--black); border: 1px solid var(--line); color: var(--bone);
    padding: 7px 9px; border-radius: 5px; font: 12px var(--mono);
  }
  .search input:focus { outline: none; border-color: var(--gold-dim); }
  #list { overflow-y: auto; flex: 1; }
  .row {
    display: grid; grid-template-columns: 14px 1fr auto; gap: 8px; align-items: center;
    padding: 9px 12px; border-bottom: 1px solid #14181F; cursor: pointer;
  }
  .row:hover { background: #10141B; }
  .row.sel { background: #161B24; box-shadow: inset 2px 0 0 var(--gold); }
  .row .state { font-size: 11px; text-align: center; }
  .row .title { font: 12px var(--mono); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .row .sub { font-size: 11px; color: var(--grey); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .verdict {
    font: 10px var(--mono); padding: 2px 5px; border-radius: 3px; letter-spacing: .05em;
    border: 1px solid currentColor;
  }
  .v-AUTO { color: var(--green); } .v-ASSISTED { color: var(--gold); }
  .v-MANUAL { color: var(--red); } .v-DROP { color: var(--grey); }
  .v-UNKNOWN { color: var(--violet); }
  .st-approved { color: var(--green); } .st-rejected { color: var(--red); }
  .st-needs_work { color: var(--gold); } .st-pending { color: #4a5260; }

  /* ── detail ──────────────────────────────────────────── */
  section { display: flex; flex-direction: column; min-width: 0; min-height: 0; }
  .head { padding: 14px 18px; border-bottom: 1px solid var(--line); }
  .head h1 { margin: 0; font: 600 17px var(--mono); letter-spacing: -0.01em; }
  .head .where { margin-top: 3px; font-size: 12px; color: #5c6472; }
  .head .where b { color: var(--grey); font-weight: 500; }
  .head .meta { margin-top: 8px; display: flex; gap: 10px; align-items: center; flex-wrap: wrap; color: var(--grey); font-size: 12px; }
  .panes { flex: 1; display: grid; grid-template-columns: 1fr 1fr; min-height: 0; }
  .pane { display: flex; flex-direction: column; min-width: 0; min-height: 0; }
  .pane + .pane { border-left: 1px solid var(--line); }
  .pane h2 {
    margin: 0; padding: 8px 14px; font: 11px var(--mono); letter-spacing: .1em;
    text-transform: uppercase; color: var(--grey); border-bottom: 1px solid var(--line);
    display: flex; justify-content: space-between; align-items: center; background: #0B0E13;
  }
  .code { flex: 1; overflow: auto; margin: 0; }
  pre.code { padding: 12px 14px 12px 0; font: 12.5px/1.6 var(--mono); color: #cfd6e0; }
  pre.code .ln { display: inline-block; width: 46px; padding-right: 12px; text-align: right; color: #3d4553; user-select: none; }
  textarea.code {
    background: #0A0D12; color: #cfd6e0; border: 0; padding: 12px 14px;
    font: 12.5px/1.6 var(--mono); resize: none; width: 100%;
  }
  textarea.code:focus { outline: none; }
  .empty { padding: 40px 20px; text-align: center; color: var(--grey); }
  .empty kbd { border: 1px solid var(--line); border-radius: 4px; padding: 2px 6px; font: 11px var(--mono); color: var(--gold); }

  .notes { border-top: 1px solid var(--line); max-height: 30%; overflow-y: auto; padding: 12px 18px; background: #0B0E13; }
  .notes h3 { margin: 0 0 6px; font: 11px var(--mono); letter-spacing: .1em; text-transform: uppercase; color: var(--grey); }
  .notes ul { margin: 0 0 12px; padding-left: 18px; }
  .notes li { margin: 3px 0; color: #b9c1cc; font-size: 13px; }
  .notes li.q { color: var(--gold); }
  .conf { display: flex; align-items: center; gap: 8px; font: 11px var(--mono); color: var(--grey); }
  .conf .bar { width: 90px; height: 5px; background: #23272F; border-radius: 3px; overflow: hidden; }
  .conf .bar i { display: block; height: 100%; }
  .err { color: var(--red); font: 12px var(--mono); }

  .actions { display: flex; gap: 8px; align-items: center; padding: 10px 18px; border-top: 1px solid var(--line); background: var(--graphite); }
  .actions input {
    flex: 1; background: var(--black); border: 1px solid var(--line); color: var(--bone);
    padding: 8px 10px; border-radius: 5px; font-size: 13px;
  }
  .actions input:focus { outline: none; border-color: var(--gold-dim); }
  .btn.approve:hover { border-color: var(--green); color: var(--green); }
  .btn.reject:hover { border-color: var(--red); color: var(--red); }
  kbd.hint { color: #4a5260; font: 10px var(--mono); }

  #toast {
    position: fixed; bottom: 18px; right: 18px; max-width: 420px;
    background: var(--graphite-2); border: 1px solid var(--line); border-left: 3px solid var(--gold);
    padding: 10px 14px; border-radius: 6px; font-size: 13px; opacity: 0;
    transform: translateY(8px); transition: .2s; pointer-events: none;
  }
  #toast.show { opacity: 1; transform: none; }
  #toast.bad { border-left-color: var(--red); }
  #bar { height: 2px; background: var(--gold); width: 0; transition: width .3s; }
</style>
</head>
<body>

<header>
  <div class="brand"><span class="mark">FormsLang</span> <small>Workbench</small></div>
  <div class="session" id="session"></div>
  <div class="spacer"></div>
  <div class="counts" id="counts"></div>
  <span class="chip provider" id="provider">—</span>
  <button class="btn" id="btn-propose-all">Convert unconverted</button>
  <button class="btn primary" id="btn-export">Export approved</button>
</header>
<div id="bar"></div>

<main>
  <aside>
    <div class="filters">
      <div class="frow"><span class="flabel">Conversion</span><span id="f-conv"></span></div>
      <div class="frow"><span class="flabel">Your call</span><span id="f-call"></span></div>
    </div>
    <div class="search"><input id="q" placeholder="filter by name, block or built-in…" spellcheck="false"></div>
    <div id="list"></div>
  </aside>

  <section>
    <div class="head">
      <h1 id="t-title">—</h1>
      <div class="where" id="t-where"></div>
      <div class="meta" id="t-meta"></div>
    </div>
    <div class="panes">
      <div class="pane">
        <h2><span>Oracle Forms — what runs today</span><span id="t-lines"></span></h2>
        <pre class="code" id="src"></pre>
      </div>
      <div class="pane">
        <h2>
          <span>Oracle APEX — what would replace it · editable</span>
          <span class="conf" id="t-conf"></span>
        </h2>
        <textarea class="code" id="out" spellcheck="false" placeholder="No proposal yet."></textarea>
      </div>
    </div>
    <div class="notes" id="notes"></div>
    <div class="actions">
      <button class="btn approve" id="btn-approve">Approve <kbd class="hint">A</kbd></button>
      <button class="btn" id="btn-needs">Needs work <kbd class="hint">W</kbd></button>
      <button class="btn reject" id="btn-reject">Reject <kbd class="hint">R</kbd></button>
      <button class="btn" id="btn-propose">Convert <kbd class="hint">P</kbd></button>
      <input id="comment" placeholder="reviewer note (optional)">
      <input id="reviewer" placeholder="your name" style="flex:0 0 140px">
    </div>
  </section>
</main>

<div id="toast"></div>

<script>
const $ = (id) => document.getElementById(id);

/* Two independent axes. A unit can be converted and still undecided, so the
   two questions get two rows of buttons and never share a word. */
const CONV = [["all", "all"], ["unconverted", "not converted"], ["converted", "converted"]];
const CALL = [["all", "all"], ["pending", "undecided"], ["approved", "approved"],
              ["needs_work", "needs work"], ["rejected", "rejected"]];
const MARK = { approved: "✓", rejected: "✕", needs_work: "⚠", pending: "●" };
/* What the catalog verdict means, on hover -- the colours alone taught nobody. */
const VERDICT_HELP = {
  AUTO: "AUTO — direct APEX equivalent. Machine converts, you review.",
  ASSISTED: "ASSISTED — the intent translates, the form does not. Read this one carefully.",
  MANUAL: "MANUAL — no APEX equivalent. Needs a redesign decision, not a translation.",
  DROP: "DROP — solves a problem APEX does not have. It disappears, and that is a gain.",
  UNKNOWN: "UNKNOWN — not in the catalog yet. Priced expensive on purpose.",
};
const help = (v) => VERDICT_HELP[v] || "Program unit — no trigger verdict applies.";
const CALL_LABEL = { pending: "undecided", needs_work: "needs work" };
const label = (s) => CALL_LABEL[s] || s;
let state = { tasks: [], stats: {}, session: {}, provider: "" };
let conv = "all", call = "all", query = "", selected = null, polling = null;

function esc(s) {
  return (s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}
function toast(msg, bad) {
  const t = $("toast");
  t.textContent = msg;
  t.className = "show" + (bad ? " bad" : "");
  clearTimeout(t._h);
  t._h = setTimeout(() => (t.className = ""), 4200);
}
async function api(path, body) {
  const opt = body ? { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) } : {};
  const r = await fetch(path, opt);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || r.statusText);
  return data;
}

/* ── rendering ─────────────────────────────────────────── */
function matches(t) {
  if (conv === "unconverted" && t.proposal) return false;
  if (conv === "converted" && !t.proposal) return false;
  if (call !== "all" && t.state !== call) return false;
  if (!query) return true;
  const hay = [t.title, t.module, t.kind, t.verdict, ...(t.builtins || []).map((b) => b.name)].join(" ").toLowerCase();
  return hay.includes(query);
}
const filtered = () => state.tasks.filter(matches);
const filtering = () => conv !== "all" || call !== "all" || !!query;

function renderRow(id, defs, current, set) {
  $(id).innerHTML = defs.map(([value, text]) =>
    `<button data-v="${value}" class="${value === current ? "on" : ""}">${text}</button>`).join("");
  $(id).querySelectorAll("button").forEach((b) =>
    b.onclick = () => { set(b.dataset.v); renderFilters(); renderList(); renderDetail(); }
  );
}

function renderFilters() {
  renderRow("f-conv", CONV, conv, (v) => (conv = v));
  renderRow("f-call", CALL, call, (v) => (call = v));
}

function renderList() {
  const rows = filtered();
  $("list").innerHTML = rows.map((t) => `
    <div class="row ${t.id === selected ? "sel" : ""}" data-id="${t.id}">
      <div class="state st-${t.state}">${MARK[t.state] || "●"}</div>
      <div>
        <div class="title">${esc(t.title)}</div>
        <div class="sub">${esc(t.module)} · ${t.lines} lines${t.proposal ? "" : " · not converted"}</div>
      </div>
      <div class="verdict v-${t.verdict || "DROP"}" title="${esc(help(t.verdict))}">${t.verdict || "PU"}</div>
    </div>`).join("") || `<div class="empty">Nothing matches this filter.</div>`;
  $("list").querySelectorAll(".row").forEach((r) => (r.onclick = () => select(r.dataset.id)));
}

function renderCounts() {
  const s = state.stats;
  $("counts").innerHTML = `
    <span>converted <b>${s.proposed || 0}</b>/${s.tasks || 0}</span>
    <span>undecided <b>${s.pending || 0}</b></span>
    <span class="ok">approved <b>${s.approved || 0}</b></span>
    <span class="no">rejected <b>${s.rejected || 0}</b></span>`;
  // Progress is decisions made, not conversions run: the model finishing is
  // not the job finishing.
  const decided = (s.tasks || 0) - (s.pending || 0);
  $("bar").style.width = s.tasks ? (100 * decided / s.tasks) + "%" : "0";

  const left = s.unproposed || 0;
  const btn = $("btn-propose-all");
  btn.disabled = left === 0;
  btn.textContent = left ? `Convert ${left} unconverted` : "All converted";
}

function withLineNumbers(code) {
  return (code || "").split("\n").map((l, i) =>
    `<span class="ln">${i + 1}</span>${esc(l)}`).join("\n");
}

function renderDetail() {
  const t = state.tasks.find((x) => x.id === selected);
  if (!t) {
    $("t-title").textContent = "—";
    $("t-where").textContent = "";
    $("src").innerHTML = ""; $("out").value = ""; $("t-meta").innerHTML = "";
    $("notes").innerHTML = `<div class="empty">Nothing selected.</div>`;
    return;
  }

  $("t-title").textContent = t.title;
  const rows = filtered();
  const pos = rows.findIndex((x) => x.id === t.id);
  // The one line that says what this screen is, on every unit.
  $("t-where").innerHTML =
    (pos >= 0 ? `Unit <b>${pos + 1}</b> of <b>${rows.length}</b>${filtering() ? " in this view" : ""} · ` : "") +
    `one ${esc(t.kind)} · left is <b>what runs today</b>, right is <b>what would replace it</b>`;
  const p = t.proposal;
  $("t-meta").innerHTML = [
    `<span class="verdict v-${t.verdict || "DROP"}" title="${esc(help(t.verdict))}">${t.verdict || "PROGRAM UNIT"}</span>`,
    `<span>${esc(t.module)}</span>`,
    t.apex_hint ? `<span>→ ${esc(t.apex_hint)}</span>` : "",
    p && p.apex_target ? `<span class="chip">${esc(p.apex_target)}</span>` : "",
    t.state !== "pending" ? `<span class="st-${t.state}">${label(t.state)}${t.reviewer ? " by " + esc(t.reviewer) : ""}</span>` : "",
  ].filter(Boolean).join("");
  $("t-lines").textContent = t.lines + " lines";
  $("src").innerHTML = withLineNumbers(t.source);
  $("out").value = t.final_code || "";

  if (p) {
    const c = p.confidence || 0;
    const color = c >= 0.8 ? "var(--green)" : c >= 0.5 ? "var(--gold)" : "var(--red)";
    $("t-conf").innerHTML = `confidence <span class="bar"><i style="width:${Math.round(c * 100)}%;background:${color}"></i></span> ${c.toFixed(2)}`;
  } else {
    $("t-conf").textContent = "";
  }

  const bits = [];
  if (p && p.error) bits.push(`<div class="err">Provider error: ${esc(p.error)}</div>`);
  if (p && p.notes && p.notes.length)
    bits.push(`<h3>What changed</h3><ul>${p.notes.map((n) => `<li>${esc(n)}</li>`).join("")}</ul>`);
  if (p && p.open_questions && p.open_questions.length)
    bits.push(`<h3>Open questions</h3><ul>${p.open_questions.map((n) => `<li class="q">${esc(n)}</li>`).join("")}</ul>`);
  if ((t.builtins || []).length)
    bits.push(`<h3>Built-ins in this body</h3><ul>${t.builtins.map((b) =>
      `<li><span class="verdict v-${b.verdict}">${b.verdict}</span> <code>${esc(b.name)}</code> — ${esc(b.apex)}</li>`).join("")}</ul>`);
  if (t.globals && t.globals.length)
    bits.push(`<h3>Globals</h3><ul><li>${t.globals.map(esc).join(", ")}</li></ul>`);
  if (!p) bits.unshift(`<div class="empty">Not converted yet — press <kbd>P</kbd> to ask the model.</div>`);
  if (p && p.model) bits.push(`<div class="conf">${esc(p.provider)} · ${esc(p.model)} · ${esc(p.created_at || "")}</div>`);
  $("notes").innerHTML = bits.join("");
  $("comment").value = t.comment || "";
}

function select(id) {
  selected = id;
  renderList();
  renderDetail();
  const row = document.querySelector(".row.sel");
  if (row) row.scrollIntoView({ block: "nearest" });
}

function move(delta) {
  const rows = filtered();
  if (!rows.length) return;
  const i = rows.findIndex((t) => t.id === selected);
  select(rows[Math.min(rows.length - 1, Math.max(0, i + delta))].id);
}

/* ── data ──────────────────────────────────────────────── */
async function refresh(keep = true) {
  const data = await api("/api/state");
  state = data;
  $("session").textContent = data.session.title || "";
  $("provider").textContent = data.provider;
  renderCounts();
  renderFilters();
  if (!keep || !state.tasks.some((t) => t.id === selected))
    selected = (state.tasks[0] || {}).id || null;
  renderList();
  renderDetail();
}

async function decide(st) {
  if (!selected) return;
  await api("/api/decision", {
    task_id: selected, state: st, code: $("out").value,
    comment: $("comment").value, reviewer: $("reviewer").value,
  });
  localStorage.setItem("formslang.reviewer", $("reviewer").value);
  const wasSelected = selected;
  await refresh();
  selected = wasSelected;
  renderList(); renderDetail();
  move(1);
}

async function propose(all) {
  const body = all ? { all: true } : { task_id: selected };
  if (!all && !selected) return;
  try {
    await api("/api/propose", body);
  } catch (e) { toast(e.message, true); return; }
  $("btn-propose-all").disabled = true;
  poll();
}

function poll() {
  clearInterval(polling);
  polling = setInterval(async () => {
    const job = await api("/api/job");
    if (job.running) {
      $("btn-propose-all").textContent = `Converting ${job.done}/${job.total}…`;
      return;
    }
    clearInterval(polling);
    if (job.error) toast(job.error, true);
    else if (job.total) toast(`Converted ${job.done} unit(s). Now read them.`);
    const keep = selected;
    await refresh();  // restores the button's own label from the new counts
    if (keep) { selected = keep; renderList(); renderDetail(); }
  }, 700);
}

/* ── wiring ────────────────────────────────────────────── */
$("btn-approve").onclick = () => decide("approved");
$("btn-reject").onclick = () => decide("rejected");
$("btn-needs").onclick = () => decide("needs_work");
$("btn-propose").onclick = () => propose(false);
$("btn-propose-all").onclick = () => propose(true);
$("btn-export").onclick = async () => {
  try {
    const r = await api("/api/export", {});
    toast(`Exported ${r.approved} approved unit(s) to ${r.sql}`);
  } catch (e) { toast(e.message, true); }
};
$("q").oninput = (e) => { query = e.target.value.toLowerCase(); renderList(); };

document.addEventListener("keydown", (e) => {
  const typing = ["INPUT", "TEXTAREA"].includes(document.activeElement.tagName);
  if (e.key === "/" && !typing) { e.preventDefault(); $("q").focus(); return; }
  if (e.key === "Escape") { document.activeElement.blur(); return; }
  if (typing) return;
  if (e.key === "j") move(1);
  else if (e.key === "k") move(-1);
  else if (e.key === "a") decide("approved");
  else if (e.key === "r") decide("rejected");
  else if (e.key === "w") decide("needs_work");
  else if (e.key === "p") propose(false);
});

$("reviewer").value = localStorage.getItem("formslang.reviewer") || "";
refresh(false).catch((e) => toast(e.message, true));
</script>
</body>
</html>
"""
