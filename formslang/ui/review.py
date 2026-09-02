"""The task list and its detail pane: filtering, rendering, PL/SQL syntax highlighting, unit navigation and the approve/reject/needs-work decision -- split out of formslang/ui.py."""

from __future__ import annotations

MAIN_OPEN_HTML = r"""<main>
"""

LIST_PANE_HTML = r"""  <aside>
    <div class="filters">
      <div class="frow"><span class="flabel">Conversion</span><span id="f-conv"></span></div>
      <div class="frow"><span class="flabel">Your call</span><span id="f-call"></span></div>
      <div class="frow"><span class="flabel">Risk</span><span id="f-risk"></span></div>
    </div>
    <div class="search"><input id="q" placeholder="filter by name, block or built-in…" spellcheck="false"></div>
    <div id="list"></div>
  </aside>

"""

DETAIL_SECTION_HTML = r"""  <section>
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
          <span class="qtag" id="out-queued" hidden>in queue</span>
          <span class="conf" id="t-conf"></span>
        </h2>
        <div class="code-wrap">
          <pre class="code hl-overlay" id="out-hl" aria-hidden="true"></pre>
          <textarea class="code" id="out" spellcheck="false" placeholder="No proposal yet — write the APEX replacement here yourself, or press P to ask the model."></textarea>
        </div>
        <div class="pane-busy" id="out-busy" hidden>
          <div class="spin big"></div>
          <strong id="busy-title"></strong>
          <span class="sub" id="busy-sub"></span>
          <span class="tick" id="busy-tick"></span>
        </div>
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

"""

SYNTAX_HIGHLIGHT_JS = r"""const PLSQL_KW = new Set(("begin end if then else elsif loop while for declare is as procedure function return exception " +
  "when others null and or not in out nocopy varchar2 number date boolean pls_integer binary_integer char long raw clob blob " +
  "constant cursor type record table of index by exit goto raise commit rollback savepoint select into from where insert " +
  "update delete values set order group having union all distinct like between exists case default rownum rowtype sysdate " +
  "user true false package body subtype rowid nextval currval trigger before after each row").split(" "));
function hlLine(line, st) {
  let out = "", i = 0;
  const n = line.length;
  while (i < n) {
    if (st.c) {                                   /* inside a block comment */
      const end = line.indexOf("*/", i);
      if (end < 0) { out += '<i class="c">' + esc(line.slice(i)) + "</i>"; i = n; break; }
      out += '<i class="c">' + esc(line.slice(i, end + 2)) + "</i>"; i = end + 2; st.c = false;
      continue;
    }
    const ch = line[i], two = line.substr(i, 2);
    if (two === "--") { out += '<i class="c">' + esc(line.slice(i)) + "</i>"; break; }
    if (two === "/*") { st.c = true; continue; }
    if (ch === "'") {                             /* string, '' escapes */
      let j = i + 1;
      while (j < n) { if (line[j] === "'" && line[j + 1] === "'") j += 2; else if (line[j] === "'") { j++; break; } else j++; }
      out += '<i class="s">' + esc(line.slice(i, j)) + "</i>"; i = j;
      continue;
    }
    if (ch === ":" && /[a-z_]/i.test(line[i + 1] || "")) {   /* :block.item bind */
      let j = i + 1;
      while (j < n && /[\w$#.]/.test(line[j])) j++;
      out += '<i class="b">' + esc(line.slice(i, j)) + "</i>"; i = j;
      continue;
    }
    if (/[0-9]/.test(ch)) {
      let j = i;
      while (j < n && /[\d.]/.test(line[j])) j++;
      out += '<i class="n">' + esc(line.slice(i, j)) + "</i>"; i = j;
      continue;
    }
    if (/[a-z_]/i.test(ch)) {
      let j = i;
      while (j < n && /[\w$#]/.test(line[j])) j++;
      const word = line.slice(i, j);
      out += PLSQL_KW.has(word.toLowerCase()) ? '<i class="k">' + esc(word) + "</i>" : esc(word);
      i = j;
      continue;
    }
    out += esc(ch); i++;
  }
  return out;
}
function withLineNumbers(code) {
  const st = { c: false };
  return (code || "").split("\n").map((l, i) =>
    `<span class="ln">${i + 1}</span>${hlLine(l, st)}`).join("\n");
}
/* Same lexer, no gutter -- the APEX pane is a textarea overlay, not a
   line-numbered read-only listing. */
function highlightPlain(code) {
  const st = { c: false };
  return (code || "").split("\n").map((l) => hlLine(l, st)).join("\n");
}
/* The overlay behind the (transparently-coloured) textarea repaints on
   every keystroke and follows its scroll -- the two must stay pixel-locked
   or the colour drifts away from the letters it is supposed to colour. */
function syncOutHighlight() {
  $("out-hl").innerHTML = highlightPlain($("out").value);
}
function syncOutScroll() {
  $("out-hl").scrollTop = $("out").scrollTop;
  $("out-hl").scrollLeft = $("out").scrollLeft;
}

/* ── rendering ─────────────────────────────────────────── */
"""

LIST_AND_DETAIL_JS = r"""function matches(t) {
  if (conv === "unconverted" && t.proposal) return false;
  if (conv === "converted" && !t.proposal) return false;
  if (call !== "all" && t.state !== call) return false;
  if (risk !== "all" && riskOf(t) !== risk) return false;
  if (!query) return true;
  const hay = [t.title, t.module, t.kind, t.verdict, riskOf(t), behOf(t),
               ...(t.builtins || []).map((b) => b.name)].join(" ").toLowerCase();
  return hay.includes(query);
}
const filtered = () => state.tasks.filter(matches);
const filtering = () => conv !== "all" || call !== "all" || risk !== "all" || !!query;

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
  renderRow("f-risk", RISK, risk, (v) => (risk = v));
}

function renderList() {
  const rows = filtered();
  $("list").innerHTML = rows.map((t) => `
    <div class="row ${t.id === selected ? "sel" : ""}" data-id="${t.id}">
      <div class="state st-${t.state}" data-mark="${MARK[t.state] || "●"}">${MARK[t.state] || "●"}</div>
      <div>
        <div class="title">${esc(t.title)}</div>
        <div class="sub">${esc(t.module)} · ${t.lines} lines${t.proposal ? "" : " · not converted"}</div>
      </div>
      <div class="rside">
        ${sensOf(t) ? `<i class="sflag r-${sensOf(t)}" title="Sensitive data found in the source — ${esc(sensOf(t))}">&#9888;</i>` : ""}
        ${riskOf(t) ? `<i class="rdot r-${riskOf(t)}" title="${esc(RISK_HELP[riskOf(t)] || "")}"></i>` : ""}
        <div class="verdict v-${t.verdict || "DROP"}" title="${esc(help(t.verdict))}">${t.verdict || "PU"}</div>
      </div>
    </div>`).join("") || `<div class="empty">Nothing matches this filter.</div>`;
  $("list").querySelectorAll(".row").forEach((r) => (r.onclick = () => select(r.dataset.id)));
  paintBusyRows();  // a re-render must not wipe the spinners of a live run
}

function renderCounts() {
  const s = state.stats;
  $("counts").innerHTML = `
    <span class="oc"><i></i>converted <b>${s.proposed || 0}</b>/${s.tasks || 0}</span>
    <span><i></i>undecided <b>${s.pending || 0}</b></span>
    <span class="ok"><i></i><b>${s.approved || 0}</b></span>
    <span class="no"><i></i><b>${s.rejected || 0}</b></span>`;
  // Progress is decisions made, not conversions run: the model finishing is
  // not the job finishing.
  const decided = (s.tasks || 0) - (s.pending || 0);
  $("bar").style.width = s.tasks ? (100 * decided / s.tasks) + "%" : "0";

  const left = s.unproposed || 0;
  const btn = $("btn-propose-all");
  btn.disabled = left === 0;
  btn.textContent = !s.tasks ? "Open a module first" : left ? `Convert ${left} unconverted` : "All converted";
}

function renderDetail() {
  paintBusyPane();
  const t = state.tasks.find((x) => x.id === selected);
  if (!t) {
    $("t-title").textContent = "—";
    $("t-where").textContent = "";
    $("src").innerHTML = ""; $("out").value = ""; $("out-hl").innerHTML = ""; $("t-meta").innerHTML = "";
    $("notes").innerHTML = state.tasks.length
      ? `<div class="empty">Nothing selected.</div>`
      : `<div class="empty">No module open. Pick the .fmb you want to convert from the button at the top left.</div>`;
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
  const a = t.analysis || null;
  const lvl = riskOf(t), beh = behOf(t);
  // Status, then how it converts, then how dangerous, then what changes.
  // Confidence sits on the right pane on purpose: it is the model talking,
  // and it belongs next to the model's answer, not next to the facts.
  $("t-meta").innerHTML = [
    t.state !== "pending" ? `<span class="st-${t.state}">${label(t.state)}${t.reviewer ? " by " + esc(t.reviewer) : ""}</span>` : "",
    `<span class="verdict v-${t.verdict || "DROP"}" title="${esc(help(t.verdict))}">${t.verdict || "PROGRAM UNIT"}</span>`,
    lvl ? `<span class="verdict r-${lvl}" title="${esc(RISK_HELP[lvl] || "")}">${lvl} RISK · ${(a.risk.score || 0).toFixed(0)}</span>` : "",
    beh ? `<span class="verdict bh-${beh}" title="${esc(BEH_HELP[beh] || "")}">${BEH_SHORT[beh] || beh}</span>` : "",
    sensOf(t) ? `<span class="verdict r-${sensOf(t)}" title="Redacted findings only -- see below.">SENSITIVE DATA · ${esc(sensOf(t))}</span>` : "",
    `<span>${esc(t.module)}</span>`,
    t.apex_hint ? `<span>→ ${esc(t.apex_hint)}</span>` : "",
    p && p.apex_target ? `<span class="chip">${esc(p.apex_target)}</span>` : "",
    a && a.stale ? `<span class="st-needs_work" title="Computed under an older rule set — reopen the module to recompute.">rules moved since</span>` : "",
  ].filter(Boolean).join("");
  $("t-lines").textContent = t.lines + " lines";
  $("src").innerHTML = withLineNumbers(t.source);
  $("out").value = t.final_code || "";
  syncOutHighlight();

  if (p) {
    const c = p.confidence || 0;
    const color = c >= 0.8 ? "var(--green)" : c >= 0.5 ? "var(--gold)" : "var(--red)";
    $("t-conf").innerHTML = `confidence <span class="cbar"><i style="width:${Math.round(c * 100)}%;background:${color}"></i></span> ${c.toFixed(2)}`;
  } else {
    $("t-conf").textContent = "";
  }

  const bits = [];
  if (p && p.error) bits.push(`<div class="err">Provider error: ${esc(p.error)}</div>`);
  // The deterministic findings come first and stay collapsed: they are the
  // evidence behind the badges above, available without ever being in the way.
  if (a && a.risk && (a.risk.factors || []).length) {
    const f = a.risk.factors;
    bits.push(`<details><summary>Why this risk? — ${esc(lvl)} · score ${(a.risk.score || 0).toFixed(0)} of 100 · ${f.length} factor${f.length > 1 ? "s" : ""}</summary>
      <ul>${f.map((x) => `<li><code>${esc(x.title)}</code> <span class="pts">+${x.points} raw</span> — ${esc(x.detail)}
        ${(x.evidence || []).length ? `<span class="ev">${x.evidence.map(esc).join(" · ")}</span>` : ""}</li>`).join("")}</ul>
      ${(a.review_areas || []).length ? `<div class="why"><b>Check by hand:</b> ${a.review_areas.map(esc).join(" · ")}</div>` : ""}
      <div class="why">Score is <code>100 × (1 − 0.5 ^ (raw ÷ 12))</code> over the raw points above — no model opinion is an input.</div>
    </details>`);
  }
  if (a && a.sensitive && (a.sensitive.findings || []).length) {
    const sf = a.sensitive.findings;
    bits.push(`<details><summary>Sensitive data found — ${esc(sensOf(t))} · ${sf.length} finding${sf.length > 1 ? "s" : ""}</summary>
      <ul>${sf.map((f) => `<li><span class="verdict r-${f.severity}">${esc(f.severity)}</span>
        <code>${esc(SENS_CATEGORY_LABEL[f.category] || f.category)}</code> — ${esc(f.title)}
        <span class="pts">line ${f.line}${f.in_comment ? " · in a comment" : ""}</span>
        <span class="ev">${esc(f.confidence)} · ${esc(f.excerpt)}${f.detail ? " · " + esc(f.detail) : ""}</span></li>`).join("")}</ul>
      <div class="why">Every excerpt above is redacted — the raw value that was matched never leaves the scan.</div>
    </details>`);
  }
  if (a && a.behavior && (( a.behavior.reasons || []).length || (a.behavior.uncertainties || []).length)) {
    const b = a.behavior;
    bits.push(`<details><summary>Behaviour after migration — ${esc(b.value)}${b.source === "rules+ai" ? " · rules + model" : ""}</summary>
      ${(b.reasons || []).length ? `<ul>${b.reasons.map((n) => `<li>${esc(n)}</li>`).join("")}</ul>` : ""}
      ${(b.uncertainties || []).length ? `<div class="why">Not established by the rules:</div><ul>${b.uncertainties.map((n) => `<li class="q">${esc(n)}</li>`).join("")}</ul>` : ""}
    </details>`);
  }
  if (a && (a.findings || []).length) {
    bits.push(`<details><summary>Forms compatibility — ${a.findings.length} construct${a.findings.length > 1 ? "s" : ""}</summary>
      <ul>${a.findings.map((f) => `<li><span class="verdict v-${f.verdict}">${esc(f.verdict)}</span>
        <code>${esc(f.name)}</code>${f.count > 1 ? ` <span class="pts">×${f.count}</span>` : ""}
        — ${esc(f.apex)}
        <span class="ev">${esc(CLASS_LABEL[f.migration_class] || f.migration_class)} · ${esc(f.category_label)}${f.targets && f.targets.length ? " · targets: " + f.targets.map(esc).join(", ") : ""}</span></li>`).join("")}</ul>
    </details>`);
  }
  bits.push(renderDeps(t));
  if (p && p.notes && p.notes.length)
    bits.push(`<h3>What changed</h3><ul>${p.notes.map((n) => `<li>${esc(n)}</li>`).join("")}</ul>`);
  if (p && p.open_questions && p.open_questions.length)
    bits.push(`<h3>Open questions</h3><ul>${p.open_questions.map((n) => `<li class="q">${esc(n)}</li>`).join("")}</ul>`);
  bits.push(renderTests(t));
  // Sessions created before the analysis engine still show their built-ins.
  if (!a && (t.builtins || []).length)
    bits.push(`<h3>Built-ins in this body</h3><ul>${t.builtins.map((b) =>
      `<li><span class="verdict v-${b.verdict}">${b.verdict}</span> <code>${esc(b.name)}</code> — ${esc(b.apex)}</li>`).join("")}</ul>`);
  if (t.globals && t.globals.length)
    bits.push(`<h3>Globals</h3><ul><li>${t.globals.map(esc).join(", ")}</li></ul>`);
  if (!p) bits.unshift(`<div class="empty">Not converted yet — press <kbd>P</kbd> to ask the model, or write the APEX code on the right and approve it.</div>`);
  if (p && p.model) bits.push(`<div class="conf">${esc(p.provider)} · ${esc(p.model)} · ${esc(p.created_at || "")}</div>`);
  $("notes").innerHTML = bits.join("");
  $("notes").querySelectorAll(".tc-a:not(.run) button").forEach((b) =>
    (b.onclick = () => decideCase(b.dataset.case, b.dataset.state, b.dataset.task)));
  $("notes").querySelectorAll(".tc-a.run button").forEach((b) =>
    (b.onclick = () => recordRun(b.dataset.case, b.dataset.run, b.dataset.task)));
  $("comment").value = t.comment || "";
}

/* ── dependencies ──────────────────────────────────────── */
/* Fetched on demand rather than shipped with every task: the graph is one
   payload per module, and the reviewer looks at one unit at a time. */
"""

NAVIGATION_JS = r"""function select(id) {
  selected = id;
  loadDeps(id);
  loadTests(id);
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
"""

DECIDE_JS = r"""async function decide(st) {
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

/* ── the run, made visible ─────────────────────────────────
   A conversion through a CLI provider takes 15-60 seconds per unit. Silence
   for a minute reads as a hang, so every second of it is accounted for: a
   moving bar, the name of the unit being read, spinners on the queue and an
   overlay on the pane whose answer is still being written. */
"""
