"""Dependency graph and test-case sections of the detail pane -- split out of formslang/ui.py."""

from __future__ import annotations

DEPENDENCIES_JS = r"""async function loadDeps(id) {
  if (deps[id]) return;
  deps[id] = "loading";
  try {
    deps[id] = await api("/api/deps?task=" + encodeURIComponent(id) + "&depth=2");
  } catch (e) {
    deps[id] = { available: false, reason: e.message };
  }
  if (selected === id) renderDetail();
}

function depLine(x) {
  const tags = [x.label];
  if (x.depth > 1) tags.push(x.depth + " hops away");
  if (x.risk) tags.push(x.risk + " RISK");
  if (x.missing) tags.push("not declared in this module");
  else if (x.external) tags.push("outside this form");
  if (x.evidence) tags.push(x.evidence);
  return `<li><span class="dep-k">${esc(x.via_label)}</span> <code>${esc(x.name)}</code>
    <span class="ev">${tags.map(esc).join(" · ")}</span></li>`;
}

function renderDeps(t) {
  const d = deps[t.id];
  if (d === undefined) loadDeps(t.id);
  if (d === "loading" || d === undefined) return `<details><summary>Dependencies — reading…</summary></details>`;
  if (!d.available) return "";
  const e = d.explore;
  if (!e || !e.node) return "";
  const impact = e.impact || [], needs = e.depends_on || [];
  const unresolved = e.node.unresolved_targets || [];
  const risky = impact.concat(needs).filter((x) => x.risk === "HIGH" || x.risk === "CRITICAL" || x.missing).length;
  return `<details><summary>Dependencies — ${impact.length} affected by this · ${needs.length} needed by it${risky ? ` · <b>${risky} to check</b>` : ""}</summary>
    ${impact.length ? `<div class="why"><b>Breaks if this changes</b> (inbound)</div><ul>${impact.map(depLine).join("")}</ul>` : ""}
    ${needs.length ? `<div class="why"><b>This unit needs</b> (outbound)</div><ul>${needs.map(depLine).join("")}</ul>` : ""}
    ${unresolved.length ? `<div class="why">Named at runtime, so no dependency could be resolved: <code>${unresolved.map(esc).join("</code>, <code>")}</code></div>` : ""}
    ${!impact.length && !needs.length ? `<div class="why">Nothing else in this module refers to it, and it refers to nothing outside itself.</div>` : ""}
  </details>`;
}

/* ── test cases ────────────────────────────────────────── */
/* Written from the original Forms body before any conversion exists, so the
   section is there even for a unit nobody has proposed yet. */
"""

TEST_CASES_JS = r"""async function loadTests(id) {
  if (tests[id]) return;
  tests[id] = "loading";
  try {
    tests[id] = await api("/api/tests?task=" + encodeURIComponent(id));
  } catch (e) {
    tests[id] = { cases: [], error: e.message };
  }
  if (selected === id) renderDetail();
}

const CASE_ACTION = { accepted: "Accept", rejected: "Reject", needs_work: "Needs work" };
const RUN_ACTION = { pass: "Pass", fail: "Fail", blocked: "Blocked" };
const RUN_LABEL = { pass: "Passed", fail: "Failed", blocked: "Blocked", not_run: "Not run" };

async function decideCase(caseId, state, taskId) {
  try {
    await api("/api/test-decision", {
      case_id: caseId, state,
      reviewer: $("reviewer").value, comment: $("comment").value,
    });
  } catch (e) {
    toast(e.message, true);
    return;
  }
  delete tests[taskId];          // re-read: the counts in the header moved too
  await loadTests(taskId);
  toast(CASE_ACTION[state] + "ed");
}

async function recordRun(caseId, runState, taskId) {
  try {
    await api("/api/test-run", {
      case_id: caseId, run_state: runState,
      run_by: $("reviewer").value, run_notes: $("comment").value,
    });
  } catch (e) {
    toast(e.message, true);
    return;
  }
  delete tests[taskId];          // re-read: the counts in the header moved too
  await loadTests(taskId);
  toast(RUN_LABEL[runState]);
}

function caseBlock(c, taskId) {
  const gwt = [["Given", c.given], ["When", c.when], ["Then", c.then]]
    .filter(([, rows]) => (rows || []).length)
    .map(([heading, rows]) => rows.map((r) =>
      `<li><b>${heading}</b> ${esc(r)}</li>`).join("")).join("");
  const buttons = ["accepted", "rejected", "needs_work"].map((s) =>
    `<button class="${c.state === s ? "on" : ""}" data-case="${c.id}" data-task="${taskId}" data-state="${s}">${CASE_ACTION[s]}</button>`
  ).join("");
  const said = c.state && c.state !== "pending"
    ? `<span class="said">${esc(label(c.state))}${c.reviewer ? " by " + esc(c.reviewer) : ""}${c.comment ? " — " + esc(c.comment) : ""}</span>`
    : "";
  const runButtons = ["pass", "fail", "blocked"].map((s) =>
    `<button class="${c.run_state === s ? "on r-" + s : ""}" data-case="${c.id}" data-task="${taskId}" data-run="${s}">${RUN_ACTION[s]}</button>`
  ).join("");
  const runSaid = c.run_state && c.run_state !== "not_run"
    ? `<span class="said">${esc(RUN_LABEL[c.run_state] || c.run_state)}${c.run_by ? " by " + esc(c.run_by) : ""}${c.run_notes ? " — " + esc(c.run_notes) : ""}</span>`
    : "";
  return `<div class="tc${c.state && c.state !== "pending" ? " answered" : ""}">
    <div class="tc-h">
      <span class="tc-t">${esc(c.title)}</span>
      <span class="tc-k">${esc(c.kind_label || c.kind)}</span>
      <span class="org o-${esc(c.origin)}" title="${esc(TEST_ORIGINS[c.origin] || "")}">${esc(c.origin)}</span>
      ${c.stale ? `<span class="tc-k" title="Written under an older rule set.">rules moved since</span>` : ""}
    </div>
    <ul class="gwt">${gwt}</ul>
    ${(c.evidence || []).length ? `<span class="ev">${c.evidence.map(esc).join(" · ")}</span>` : ""}
    <div class="tc-a">${buttons}${said}</div>
    <div class="tc-a run">${runButtons}${runSaid}</div>
  </div>`;
}


function renderTests(t) {
  const d = tests[t.id];
  if (d === undefined) loadTests(t.id);
  if (d === "loading" || d === undefined) return `<details><summary>Test cases — reading…</summary></details>`;
  if (d.origins) TEST_ORIGINS = d.origins;
  const cases = d.cases || [];
  if (!cases.length) return "";
  const open = cases.filter((c) => !c.state || c.state === "pending").length;
  const unsure = cases.filter((c) => c.origin === "NEEDS_CONFIRMATION").length;
  const notRun = cases.filter((c) => !c.run_state || c.run_state === "not_run").length;
  const failed = cases.filter((c) => c.run_state === "fail").length;
  return `<details><summary>Test cases — ${cases.length} · ${cases.length - open} reviewed · ${cases.length - notRun} run${failed ? ` · <b>${failed} failed</b>` : ""}${unsure ? ` · <b>${unsure} to confirm</b>` : ""}</summary>
    <div class="why">Written from the Forms body, not from the conversion, and not executed by FormsLang.${
      d.item_metadata === false ? " The module itself is not on disk, so nothing about required values or lengths could be checked." : ""}</div>
    ${cases.map((c) => caseBlock(c, t.id)).join("")}
  </details>`;
}

"""
