"""The task list and its detail pane: filtering, rendering, PL/SQL syntax highlighting, unit navigation and the approve/reject/needs-work decision -- split out of formslang/ui.py."""

from __future__ import annotations

MAIN_OPEN_HTML = r"""<main>
"""

LIST_PANE_HTML = r"""  <aside id="unit-list" aria-label="Conversion units">
    <div class="units-heading"><h2>Conversion units</h2><kbd class="hint" title="Search units">/</kbd><button id="unit-close" class="btn" aria-label="Close conversion units"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18"/></svg></button></div>
    <div class="search"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4.5 4.5"/></svg><input id="q" aria-label="Filter units by name, block or built-in" placeholder="Find a unit or built-in…" spellcheck="false" autocomplete="off"></div>
    <details class="unit-filters" open>
      <summary>Filters <span id="active-filters"></span></summary>
      <div class="filters">
        <div class="frow"><span class="flabel" id="label-conv">Conversion</span><span id="f-conv" role="group" aria-labelledby="label-conv"></span></div>
        <div class="frow"><span class="flabel" id="label-call">Review decision</span><span id="f-call" role="group" aria-labelledby="label-call"></span></div>
        <div class="frow"><span class="flabel" id="label-risk">Risk level</span><span id="f-risk" role="group" aria-labelledby="label-risk"></span></div>
      </div>
    </details>
    <div class="units-meta"><span id="units-summary" class="units-summary" aria-live="polite"></span><button id="reset-filters" hidden>Clear filters</button></div>
    <div id="list" aria-label="Units matching the current filters"></div>
    <div class="units-footer"><span><kbd>J</kbd> <kbd>K</kbd> navigate</span><span>Human review</span></div>
  </aside>

"""

DETAIL_SECTION_HTML = r"""  <section id="review-workspace" data-view="compare" aria-label="Conversion review">
    <div class="head">
      <div class="review-eyebrow">Unit review</div>
      <h1 id="t-title">—</h1>
      <div class="where" id="t-where"></div>
      <div class="meta" id="t-meta"></div>
    </div>
    <div class="review-toolbar">
      <button class="btn" id="unit-toggle" aria-controls="unit-list" aria-expanded="false">Units</button>
      <div class="review-views" role="group" aria-label="Review view">
        <button id="view-compare" aria-pressed="true" aria-controls="review-code">Compare</button>
        <button id="view-source" aria-pressed="false" aria-controls="review-code">Forms source</button>
        <button id="view-proposal" aria-pressed="false" aria-controls="review-code">APEX proposal</button>
        <button id="view-evidence" aria-pressed="false" aria-controls="notes">Evidence &amp; tests</button>
      </div>
      <div class="review-navigation">
        <span id="unit-position"></span>
        <button class="btn" id="unit-prev" aria-label="Previous unit" title="Previous unit (K)"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m14 6-6 6 6 6"/></svg></button>
        <button class="btn" id="unit-next" aria-label="Next unit" title="Next unit (J)"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m10 6 6 6-6 6"/></svg></button>
      </div>
    </div>
    <div class="panes" id="review-code">
      <div class="pane source-pane">
        <h2><span class="pane-label"><span class="pane-dot forms-dot"></span>Oracle Forms <small>Original source</small></span><span id="t-lines"></span></h2>
        <pre class="code" id="src" tabindex="0" aria-label="Original Oracle Forms source"></pre>
      </div>
      <div class="pane proposal-pane">
        <h2>
          <span class="pane-label"><span class="pane-dot apex-dot"></span>Oracle APEX <small>Editable proposal</small></span>
          <span class="qtag" id="out-queued" hidden>in queue</span>
          <span class="conf" id="t-conf"></span>
        </h2>
        <div class="code-wrap">
          <pre class="code hl-overlay" id="out-hl" aria-hidden="true"></pre>
          <textarea class="code" id="out" aria-label="Editable Oracle APEX proposal" spellcheck="false" autocomplete="off" placeholder="No proposal yet. Generate one with Convert, or write the APEX replacement here."></textarea>
        </div>
        <div class="pane-busy" id="out-busy" role="status" hidden>
          <div class="spin big"></div>
          <strong id="busy-title"></strong>
          <span class="sub" id="busy-sub"></span>
          <span class="tick" id="busy-tick"></span>
        </div>
      </div>
    </div>
    <div class="notes" id="notes" tabindex="0" aria-label="Evidence, questions and test cases"></div>
    <div class="actions">
      <div class="review-fields">
        <label>Reviewer note <input id="comment" placeholder="Reason, checks or remaining work" maxlength="8000" autocomplete="off"></label>
        <label>Your name <input id="reviewer" placeholder="Reviewer" maxlength="200" autocomplete="off"></label>
      </div>
      <div class="review-buttons">
        <button class="btn approve" id="btn-approve">Approve <kbd class="hint">A</kbd></button>
        <button class="btn" id="btn-needs">Needs work <kbd class="hint">W</kbd></button>
        <button class="btn reject" id="btn-reject">Reject <kbd class="hint">R</kbd></button>
        <button class="btn" id="btn-propose">Convert with AI <kbd class="hint">P</kbd></button>
        <span id="review-status" role="status" aria-live="polite"></span>
        <button class="btn" id="discard-draft" hidden>Discard edits</button>
      </div>
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
  const code = $("out").value;
  // Very large generated units stay editable without a full syntax pass.
  const plain = code.length > 150000;
  $("out").classList.toggle("plain-code", plain);
  $("out-hl").hidden = plain;
  if (!plain) $("out-hl").innerHTML = highlightPlain(code) + "\n";
  syncOutScroll();
}
function syncOutScroll() {
  $("out-hl").scrollTop = $("out").scrollTop;
  $("out-hl").scrollLeft = $("out").scrollLeft;
}

/* ── rendering ─────────────────────────────────────────── */
"""

LIST_AND_DETAIL_JS = r"""/* Drafts exist only in this tab's memory, never localStorage. A refresh,
dependency response or another unit must not overwrite a reviewer's work. */
const reviewDrafts = new Map();
let editorTask = null, decisionBusy = false, reviewError = "", highlightFrame = 0;
let reviewView = window.matchMedia("(max-width: 900px)").matches ? "source" : "compare";
function reviewContext(data = state) { return data.context_id || data.session_path || ""; }
function draftKey(t) { return JSON.stringify([reviewContext(), t.id, t.source || ""]); }
function captureReviewDraft() {
  if (!editorTask) return;
  const code = $("out").value, comment = $("comment").value;
  if (code === editorTask.code && comment === editorTask.comment) reviewDrafts.delete(editorTask.key);
  else reviewDrafts.set(editorTask.key, { code, comment, baseCode: editorTask.code, baseComment: editorTask.comment });
  reviewError = "";
  paintReviewStatus();
}
function paintReviewStatus() {
  const t = state.tasks.find((x) => x.id === selected);
  const draft = t && reviewDrafts.get(draftKey(t));
  const queued = !!(running() && t && ((job.queue || []).includes(t.id) || job.current_id === t.id));
  const conflict = draft && (draft.baseCode !== (t.final_code || "") || draft.baseComment !== (t.comment || ""));
  $("review-status").textContent = reviewError || (decisionBusy ? "Saving decision…" : queued
    ? "Conversion in progress · editing resumes when the proposal arrives" : conflict
    ? "Saved proposal changed. Your edits are kept; inspect before deciding."
    : draft ? "Unsaved edits · choose a review decision to save" : t ? "Only approved code enters the export" : "");
  $("review-status").classList.toggle("err", !!reviewError || !!conflict);
  $("discard-draft").hidden = !draft;
  $("discard-draft").disabled = decisionBusy;
  for (const id of ["btn-approve", "btn-needs", "btn-reject"]) $(id).disabled = !t || decisionBusy || queued;
  $("btn-propose").disabled = !t || decisionBusy || running();
  $("out").readOnly = !t || queued;
}
function discardReviewDraft() {
  if (!editorTask || !reviewDrafts.has(editorTask.key)) return;
  if (!window.confirm("Discard the unsaved code and note for this unit?")) return;
  reviewDrafts.delete(editorTask.key);
  reviewError = "";
  renderDetail();
}
function setReviewView(view) {
  if (!["compare", "source", "proposal", "evidence"].includes(view)) return;
  reviewView = view;
  $("review-workspace").dataset.view = view;
  for (const name of ["compare", "source", "proposal", "evidence"])
    $("view-" + name).setAttribute("aria-pressed", String(name === view));
  syncOutScroll();
}
function initReviewWorkspace() {
  $("reset-filters").onclick = () => {
    conv = "all"; call = "all"; risk = "all"; query = ""; $("q").value = "";
    renderFilters(); renderList(); renderDetail(); $("q").focus();
  };
  $("unit-close").onclick = () => {
    document.querySelector("main").classList.remove("units-open");
    $("unit-toggle").setAttribute("aria-expanded", "false");
    $("unit-toggle").focus();
  };
}
function matches(t) {
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
    `<button data-v="${value}" aria-pressed="${value === current}" class="${value === current ? "on" : ""}">${text}</button>`).join("");
  $(id).querySelectorAll("button").forEach((b) =>
    b.onclick = () => {
      const value = b.dataset.v;
      set(value); renderFilters(); renderList(); renderDetail();
      $(id).querySelector(`[data-v="${value}"]`)?.focus({ preventScroll: true });
    }
  );
}

function renderFilters() {
  renderRow("f-conv", CONV, conv, (v) => (conv = v));
  renderRow("f-call", CALL, call, (v) => (call = v));
  renderRow("f-risk", RISK, risk, (v) => (risk = v));
  const count = [conv, call, risk].filter((v) => v !== "all").length;
  $("active-filters").textContent = count ? `${count} active` : "";
}

function renderList() {
  const rows = filtered();
  $("units-summary").textContent = `${rows.length} of ${state.tasks.length} units`;
  $("reset-filters").hidden = !filtering();
  let previousGroup = "";
  const groupHeading = (t) => {
    const group = t.kind === "program_unit" ? "Program units" : t.owner || "Form level";
    if (group === previousGroup) return "";
    previousGroup = group;
    return `<div class="unit-group">${esc(group)}</div>`;
  };
  $("list").innerHTML = rows.map((t) => `
    ${groupHeading(t)}
    <div class="row ${t.id === selected ? "sel" : ""}" role="button" tabindex="0" aria-pressed="${t.id === selected}" aria-label="${esc(t.title)}, ${esc(label(t.state))}" data-id="${esc(t.id)}">
      <div class="state st-${t.state}" title="${esc(label(t.state))}" aria-hidden="true" data-mark="${MARK[t.state] || "●"}">${MARK[t.state] || "●"}</div>
      <div>
        <div class="title" title="${esc(t.title)}">${esc(t.name || t.title)}</div>
        <div class="sub">${t.lines} lines · ${esc(label(t.state))}${t.proposal ? "" : " · not converted"}</div>
      </div>
      <div class="rside">
        ${sensOf(t) ? `<i class="sflag r-${sensOf(t)}" title="Sensitive data found in the source — ${esc(sensOf(t))}">&#9888;</i>` : ""}
        ${riskOf(t) ? `<i class="rdot r-${riskOf(t)}" title="${esc(RISK_HELP[riskOf(t)] || "")}"></i>` : ""}
        <div class="verdict v-${t.verdict || "DROP"}" title="${esc(help(t.verdict))}">${t.verdict || "PU"}</div>
      </div>
    </div>`).join("") || `<div class="empty"><strong>${state.tasks.length ? "No matching units" : "Your units will appear here"}</strong><span>${state.tasks.length ? "Try another name or clear the filters above." : "Open a Forms module to start reviewing."}</span></div>`;
  $("list").querySelectorAll(".row").forEach((r) => {
    r.onclick = () => select(r.dataset.id);
    r.onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); select(r.dataset.id); } };
  });
  paintBusyRows();  // a re-render must not wipe the spinners of a live run
}

function renderCounts() {
  const s = state.stats;
  $("counts").innerHTML = `
    <span class="oc"><i></i>converted <b>${s.proposed || 0}</b>/${s.tasks || 0}</span>
    <span><i></i>undecided <b>${s.pending || 0}</b></span>
    <span class="ok" title="Approved for export"><i></i><b>${s.approved || 0}</b> approved</span>
    <span class="no" title="Rejected"><i></i><b>${s.rejected || 0}</b> rejected</span>`;
  // Progress is decisions made, not conversions run: the model finishing is
  // not the job finishing.
  const decided = (s.tasks || 0) - (s.pending || 0);
  $("bar").style.width = s.tasks ? (100 * decided / s.tasks) + "%" : "0";

  const left = s.unproposed || 0;
  const btn = $("btn-propose-all");
  btn.disabled = left === 0 || running() || decisionBusy;
  btn.textContent = !s.tasks ? "Open a module first" : left ? `Convert ${left} unconverted` : "All converted";
}

function renderDetail() {
  setReviewView(reviewView);
  paintBusyPane();
  const t = state.tasks.find((x) => x.id === selected);
  if (!t) {
    editorTask = null;
    $("t-title").textContent = "—";
    $("t-where").textContent = "";
    $("src").innerHTML = ""; $("out").value = ""; $("out-hl").innerHTML = ""; $("t-meta").innerHTML = "";
    $("t-lines").textContent = ""; $("t-conf").textContent = "";
    $("unit-position").textContent = "";
    $("unit-prev").disabled = true; $("unit-next").disabled = true;
    $("notes").innerHTML = state.tasks.length
      ? `<div class="empty">Nothing selected.</div>`
      : `<div class="empty">No module open. Pick the .fmb you want to convert from the button at the top left.</div>`;
    paintReviewStatus();
    return;
  }

  $("t-title").textContent = t.title;
  const rows = filtered();
  const pos = rows.findIndex((x) => x.id === t.id);
  $("unit-position").textContent = pos >= 0 ? `${pos + 1} / ${rows.length}` : "Outside filter";
  // The one line that says what this screen is, on every unit.
  $("t-where").innerHTML =
    (pos >= 0 ? `Unit <b>${pos + 1}</b> of <b>${rows.length}</b>${filtering() ? " in this view" : ""} · ` : "") +
    `${esc(t.kind === "program_unit" ? "Program unit" : "Trigger")} · ${esc(t.module)}`;
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
    p && p.apex_target ? `<span class="apex-target" title="Proposed APEX destination">${esc(p.apex_target)}</span>` : "",
    a && a.stale ? `<span class="st-needs_work" title="Computed under an older rule set — reopen the module to recompute.">rules moved since</span>` : "",
  ].filter(Boolean).join("");
  $("t-lines").textContent = t.lines + " lines";
  const key = draftKey(t), draft = reviewDrafts.get(key);
  const changedUnit = !editorTask || editorTask.key !== key;
  if (changedUnit) {
    if ((t.source || "").length > 150000) $("src").textContent = t.source;
    else $("src").innerHTML = withLineNumbers(t.source);
    $("src").scrollTop = 0;
    $("notes").scrollTop = 0;
    reviewError = "";
    const workspace = $("review-code");
    if (workspace.animate && !window.matchMedia("(prefers-reduced-motion: reduce)").matches)
      workspace.animate([{ opacity: .6, transform: "translateY(3px)" }, { opacity: 1, transform: "translateY(0)" }], { duration: 180, easing: "ease-out" });
  }
  editorTask = { key, code: t.final_code || "", comment: t.comment || "" };
  const code = draft ? draft.code : editorTask.code;
  if ($("out").value !== code || changedUnit) {
    $("out").value = code;
    syncOutHighlight();
    if (changedUnit) { $("out").scrollTop = 0; $("out").scrollLeft = 0; syncOutScroll(); }
  }

  if (p) {
    const c = Math.max(0, Math.min(1, Number(p.confidence) || 0));
    const color = c >= 0.8 ? "var(--green)" : c >= 0.5 ? "var(--gold)" : "var(--red)";
    $("t-conf").innerHTML = `<span title="Provider's estimate, not a correctness or safety score">AI confidence ${Math.round(c * 100)}%</span><span class="cbar"><i style="width:${Math.round(c * 100)}%;background:${color}"></i></span>`;
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
    bits.push(`<div class="evidence-card"><h3>What changed</h3><ul>${p.notes.map((n) => `<li>${esc(n)}</li>`).join("")}</ul></div>`);
  if (p && p.open_questions && p.open_questions.length)
    bits.push(`<div class="evidence-card questions"><h3>Open questions <span>${p.open_questions.length}</span></h3><ul>${p.open_questions.map((n) => `<li class="q">${esc(n)}</li>`).join("")}</ul></div>`);
  bits.push(renderTests(t));
  // Sessions created before the analysis engine still show their built-ins.
  if (!a && (t.builtins || []).length)
    bits.push(`<h3>Built-ins in this body</h3><ul>${t.builtins.map((b) =>
      `<li><span class="verdict v-${b.verdict}">${b.verdict}</span> <code>${esc(b.name)}</code> — ${esc(b.apex)}</li>`).join("")}</ul>`);
  if (t.globals && t.globals.length)
    bits.push(`<h3>Globals</h3><ul><li>${t.globals.map(esc).join(", ")}</li></ul>`);
  if (!p) bits.unshift(`<div class="empty">Not converted yet — press <kbd>P</kbd> to ask the model, or write the APEX code on the right and approve it.</div>`);
  if (p && p.model) bits.push(`<div class="conf proposal-origin"><span>Proposal generated by</span><strong>${esc(p.provider)} · ${esc(p.model)}</strong><span>${esc(p.created_at || "")}</span></div>`);
  const openDetails = new Set(Array.from($("notes").querySelectorAll("details[open]")).map((d) => d.querySelector("summary")?.textContent));
  $("notes").innerHTML = `<div class="evidence-heading"><h2>Evidence &amp; context</h2><p>Findings, dependencies and validation for this unit.</p></div>` + bits.join("");
  if (!changedUnit) $("notes").querySelectorAll("details").forEach((d) => { d.open = openDetails.has(d.querySelector("summary")?.textContent); });
  $("notes").querySelectorAll(".tc-a:not(.run) button").forEach((b) =>
    (b.onclick = () => decideCase(b.dataset.case, b.dataset.state, b.dataset.task)));
  $("notes").querySelectorAll(".tc-a.run button").forEach((b) =>
    (b.onclick = () => recordRun(b.dataset.case, b.dataset.run, b.dataset.task)));
  const comment = draft ? draft.comment : editorTask.comment;
  if ($("comment").value !== comment) $("comment").value = comment;
  $("unit-prev").disabled = pos <= 0;
  $("unit-next").disabled = pos < 0 || pos >= rows.length - 1;
  const evidenceCount = ((a || {}).findings || []).length + ((p || {}).open_questions || []).length;
  $("view-evidence").textContent = "Evidence & tests" + (evidenceCount ? ` (${evidenceCount})` : "");
  paintReviewStatus();
}

/* ── dependencies ──────────────────────────────────────── */
/* Fetched on demand rather than shipped with every task: the graph is one
   payload per module, and the reviewer looks at one unit at a time. */
"""

NAVIGATION_JS = r"""function select(id) {
  const fromList = document.activeElement?.closest?.("#list .row");
  selected = id;
  document.querySelector("main").classList.remove("units-open");
  $("unit-toggle").setAttribute("aria-expanded", "false");
  loadDeps(id);
  loadTests(id);
  renderList();
  renderDetail();
  const row = document.querySelector(".row.sel");
  if (row) {
    row.scrollIntoView({ block: "nearest" });
    if (fromList && window.matchMedia("(min-width: 901px)").matches) row.focus({ preventScroll: true });
    else if (fromList) $("unit-toggle").focus({ preventScroll: true });
  }
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
  const t = state.tasks.find((x) => x.id === selected);
  if (!t || decisionBusy || (running() && ((job.queue || []).includes(t.id) || job.current_id === t.id))) return;
  const key = draftKey(t), session = reviewContext(), id = t.id;
  const body = { task_id: id, context_id: state.context_id, state: st, code: $("out").value,
    comment: $("comment").value, reviewer: $("reviewer").value };
  let saved = false;
  decisionBusy = true; reviewError = ""; paintReviewStatus();
  try {
    await api("/api/decision", body);
    saved = true;
    const draft = reviewDrafts.get(key);
    // Edits made while the request was in flight belong to the next decision.
    if (!draft || (draft.code === body.code && draft.comment === body.comment)) reviewDrafts.delete(key);
    else { draft.baseCode = body.code; draft.baseComment = body.comment; }
    try { localStorage.setItem("formslang.reviewer", body.reviewer); } catch (_) { /* storage may be disabled */ }
    await refresh();
    if (selected === id && reviewContext() === session && !reviewDrafts.has(key)) move(1);
    toast("Review decision saved: " + label(st) + ".");
  } catch (e) {
    const message = saved ? "Decision saved, but the refreshed view could not be loaded. " + e.message
      : "Could not save. Your edits are kept. " + e.message;
    if (selected === id && reviewContext() === session) reviewError = message;
    toast(message, true);
  } finally { decisionBusy = false; paintReviewStatus(); }
}

/* ── the run, made visible ─────────────────────────────────
   A conversion through a CLI provider takes 15-60 seconds per unit. Silence
   for a minute reads as a hang, so every second of it is accounted for: a
   moving bar, the name of the unit being read, spinners on the queue and an
   overlay on the pane whose answer is still being written. */
"""
