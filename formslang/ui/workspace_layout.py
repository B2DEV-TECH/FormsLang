"""Resizable review panels and local, data-free workspace preferences."""

from __future__ import annotations

WORKSPACE_LAYOUT_STYLE = r"""
  /* One flexible code area owns the space left by optional supporting panels. */
  main { --units-width: 260px; grid-template-columns: var(--units-width) 7px minmax(0, 1fr); }
  #unit-list { grid-column: 1; border-right: 0; }
  #units-splitter { grid-column: 2; }
  #review-workspace { grid-column: 3; display: flex; flex-direction: column; min-height: 0; overflow-x: hidden; overflow-y: auto; }
  #review-workspace > .head, #review-workspace > .review-toolbar, #review-workspace > .actions { grid-area: auto; flex-shrink: 0; }
  #workspace-body { --source-fr: 50fr; --proposal-fr: 50fr; --evidence-height: 180px; --evidence-width: 300px; flex: 1 1 0%; min-height: 160px; min-width: 0; display: grid; grid-template-columns: minmax(0, 1fr); grid-template-rows: minmax(160px, 1fr) 7px var(--evidence-height); overflow: hidden; }
  #review-workspace #workspace-body #review-code { display: grid; grid-area: 1 / 1; min-height: 0; min-width: 0; grid-template-columns: minmax(0, var(--source-fr)) 7px minmax(0, var(--proposal-fr)); grid-template-rows: minmax(0, 1fr); }
  #review-code > .source-pane { grid-area: 1 / 1; }
  #code-splitter { grid-area: 1 / 2; }
  #review-code > .proposal-pane { grid-area: 1 / 3; border-left: 0; }
  #evidence-splitter { grid-area: 2 / 1; }
  #evidence-panel { grid-area: 3 / 1; min-height: 0; min-width: 0; display: flex; flex-direction: column; background: var(--panel); overflow: hidden; }
  #review-workspace #notes { display: block; grid-area: auto; min-height: 0; max-height: none; flex: 1; border: 0; padding: 12px 16px; overflow-y: auto; }
  .evidence-panel-head { display: flex; flex-shrink: 0; align-items: center; justify-content: space-between; gap: 8px; padding: 11px 16px; border-bottom: 1px solid var(--line); }
  .evidence-panel-head h2 { margin: 0; font: 600 12px var(--sans); color: var(--ink); }
  .evidence-panel-head span { display: block; margin-top: 3px; font: 10px var(--sans); color: var(--ink-dim); }
  #evidence-close, #unit-close { display: grid; place-items: center; width: 25px; height: 25px; padding: 4px; border-color: transparent; color: var(--ink-dim); }
  #evidence-close:hover, #unit-close:hover { border-color: var(--line-hi); color: var(--ink); }
  #evidence-close svg { width: 14px; height: 14px; fill: none; stroke: currentColor; stroke-width: 1.5; }
  .units-heading kbd { margin-left: auto; margin-right: 7px; }
  .workspace-splitter { position: relative; z-index: 5; display: grid; place-items: center; width: 7px; min-width: 7px; height: 100%; min-height: 0; background: var(--panel); border-left: 1px solid var(--line); border-right: 1px solid var(--line); cursor: col-resize; touch-action: none; outline-offset: -2px; transition: background .12s; }
  .workspace-splitter > span { width: 2px; height: 26px; background: var(--ink-faint); border-radius: 2px; pointer-events: none; transition: background .12s; }
  .workspace-splitter[aria-orientation="horizontal"] { width: 100%; height: 7px; min-height: 7px; border: 0; border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); cursor: row-resize; }
  .workspace-splitter[aria-orientation="horizontal"] > span { width: 26px; height: 2px; }
  .workspace-splitter:hover, .workspace-splitter:focus-visible, .workspace-splitter.dragging { background: var(--gold-soft); }
  .workspace-splitter:hover > span, .workspace-splitter:focus-visible > span, .workspace-splitter.dragging > span { background: var(--gold); }
  .workspace-splitter:focus-visible { outline: 2px solid var(--gold); }
  body.workspace-resizing, body.workspace-resizing * { user-select: none !important; }
  body.workspace-resizing[data-resize-axis="vertical"], body.workspace-resizing[data-resize-axis="vertical"] * { cursor: col-resize !important; }
  body.workspace-resizing[data-resize-axis="horizontal"], body.workspace-resizing[data-resize-axis="horizontal"] * { cursor: row-resize !important; }
  main[data-units="hidden"] { grid-template-columns: 0 0 minmax(0, 1fr); }
  main[data-units="hidden"] #unit-list, main[data-units="hidden"] #units-splitter { display: none; }
  #unit-toggle { display: inline-flex; align-items: center; gap: 5px; }
  #unit-toggle[aria-expanded="true"] { background: var(--raised); border-color: var(--line-hi); }
  #review-workspace[data-details="hidden"] .head .review-eyebrow,
  #review-workspace[data-details="hidden"] .head .where,
  #review-workspace[data-details="hidden"] .head .meta { display: none; }
  #review-workspace[data-details="hidden"] > .head { padding: 12px 18px; }
  #review-workspace[data-details="hidden"] > .head h1 { font-size: 15px; line-height: 1.45; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  #review-workspace[data-fields="hidden"] #reviewer-fields { display: none; }
  #review-workspace[data-evidence="hidden"] #workspace-body { grid-template-rows: minmax(0, 1fr); }
  #review-workspace[data-evidence="shown"][data-evidence-position="bottom"]:not([data-view="evidence"]) #workspace-body { min-height: 327px; }
  #review-workspace[data-evidence="hidden"] #evidence-panel,
  #review-workspace[data-evidence="hidden"] #evidence-splitter { display: none; }
  #review-workspace[data-evidence-position="side"] #workspace-body { grid-template-columns: minmax(0, 1fr) 7px var(--evidence-width); grid-template-rows: minmax(0, 1fr); }
  #review-workspace[data-evidence-position="side"] #evidence-splitter { grid-area: 1 / 2; }
  #review-workspace[data-evidence-position="side"] #evidence-panel { grid-area: 1 / 3; }
  #review-workspace[data-evidence-position="side"][data-evidence="hidden"] #workspace-body { grid-template-columns: minmax(0, 1fr); }
  #review-workspace[data-view="source"] #workspace-body #review-code,
  #review-workspace[data-view="proposal"] #workspace-body #review-code { grid-template-columns: minmax(0, 1fr); grid-template-rows: minmax(0, 1fr); }
  #review-workspace[data-view="source"] #code-splitter,
  #review-workspace[data-view="proposal"] #code-splitter { display: none; }
  #review-workspace[data-view="proposal"] #review-code > .proposal-pane { grid-area: 1 / 1; }
  #review-workspace[data-view="evidence"] #workspace-body { grid-template-columns: minmax(0, 1fr); grid-template-rows: minmax(0, 1fr); }
  #review-workspace[data-view="evidence"] #workspace-body #review-code,
  #review-workspace[data-view="evidence"] #workspace-body #evidence-splitter { display: none; }
  #review-workspace[data-view="evidence"] #workspace-body #evidence-panel { display: flex; grid-area: 1 / 1; }
  #review-workspace[data-view="evidence"] #notes { padding: 16px 22px; }
  #review-workspace .review-toolbar { position: sticky; top: 0; z-index: 10; flex-wrap: wrap; gap: 8px; padding: 7px 12px; min-height: 47px; }
  .workspace-tools { display: flex; align-items: center; gap: 5px; margin-left: auto; }
  .workspace-tool { display: inline-flex; align-items: center; justify-content: center; gap: 6px; padding: 6px 8px; min-height: 30px; font: 500 11px var(--sans); white-space: nowrap; }
  .workspace-tool svg, .fields-toggle svg { height: 14px; width: 14px; fill: none; stroke: currentColor; stroke-width: 1.5; stroke-linecap: round; stroke-linejoin: round; flex-shrink: 0; }
  #focus-code[aria-pressed="true"] { color: var(--gold); border-color: var(--gold-line); background: var(--gold-soft); }
  .layout-picker { position: relative; }
  .layout-options { position: absolute; top: calc(100% + 9px); right: 0; z-index: 18; width: 244px; padding: 13px; background: var(--panel); border: 1px solid var(--line-hi); border-radius: 8px; box-shadow: 0 12px 38px color-mix(in srgb, var(--ground) 40%, transparent); }
  .layout-options[hidden] { display: none; }
  .layout-menu-title { margin-bottom: 9px; font: 600 12px var(--sans); }
  .layout-options label { display: flex; align-items: center; gap: 9px; padding: 7px 2px; color: var(--ink); font: 11px var(--sans); cursor: pointer; }
  .layout-options label:has(input:disabled) { color: var(--ink-dim); cursor: default; }
  .layout-options input { margin: 0; width: 14px; height: 14px; accent-color: var(--gold); cursor: inherit; }
  .layout-options p { margin: 10px 0; color: var(--ink-dim); font: 10px/1.55 var(--sans); }
  #reset-layout { width: 100%; margin-top: 2px; padding: 7px 10px; font-size: 11px; }
  #focus-unit-title { display: none; max-width: 260px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--ink-dim); font: 11px var(--mono); }
  #review-workspace .review-navigation { margin-left: 0; }
  #review-workspace .review-views { flex-wrap: nowrap; }
  #review-workspace .review-views button { padding: 7px 8px; }
  #review-workspace .actions { position: sticky; bottom: 0; z-index: 8; padding: 10px 14px; gap: 8px; }
  .review-buttons .fields-toggle { display: inline-flex; align-items: center; justify-content: center; gap: 5px; padding: 7px 8px; color: var(--ink-dim); border-color: transparent; }
  .review-buttons .fields-toggle:hover, .review-buttons .fields-toggle[aria-expanded="true"] { color: var(--ink); border-color: var(--line); background: var(--raised); }
  #review-status { flex: 1 0 75%; }
  body.workspace-focus { padding-left: 0 !important; }
  body.workspace-focus #app-nav, body.workspace-focus > .app-header, body.workspace-focus #setup-banner, body.workspace-focus #bar { display: none; }
  body.workspace-focus #review-workspace > .head { display: none; }
  body.workspace-focus #focus-unit-title { display: block; }
  body.workspace-focus #review-workspace .review-toolbar { min-height: 48px; padding: 8px 16px; }
  body.workspace-focus .skip-workspace { left: 16px; }
  body.is-first-run main { grid-template-columns: minmax(0, 1fr); }
  body.is-first-run #units-splitter { display: none; }
  body.is-first-run #review-workspace { grid-column: 1; }
  @media (max-width: 1250px) {
    #review-workspace .review-toolbar { gap: 5px; padding-left: 10px; padding-right: 10px; }
    #review-workspace .review-views button { padding: 7px 6px; font-size: 10px; }
    .workspace-tool { font-size: 10px; padding: 6px; }
    .review-buttons .fields-toggle > span { display: none; }
    #review-workspace .review-navigation #unit-position { display: none; }
  }
  @media (max-width: 900px) {
    main, main[data-units="hidden"] { grid-template-columns: minmax(0, 1fr); }
    #units-splitter { display: none; }
    #review-workspace { grid-column: 1; }
    main #unit-list { display: none; width: min(var(--units-width), 86vw); grid-column: auto; position: absolute; inset: 0 auto 0 0; }
    main.units-open #unit-list { display: flex; }
    #review-workspace #workspace-body { min-height: 160px; }
    #review-workspace .review-views { flex: 0 1 auto; }
    #review-workspace .workspace-tools { margin-left: auto; }
    body.workspace-focus #focus-unit-title { display: none; }
  }
  @media (max-width: 600px) {
    #review-workspace .review-toolbar { gap: 7px; }
    #review-workspace .review-views { order: 4; flex: 1 0 100%; }
    #review-workspace .review-views button { padding: 7px 4px; }
    .workspace-tools { order: 1; }
    #review-workspace .review-navigation { order: 2; }
    #review-workspace[data-view="compare"] #workspace-body #review-code { grid-template-columns: minmax(0, 1fr); grid-template-rows: minmax(0, var(--source-fr)) 7px minmax(0, var(--proposal-fr)); }
    #review-workspace[data-view="compare"] #review-code > .source-pane { grid-area: 1 / 1; }
    #review-workspace[data-view="compare"] #code-splitter { grid-area: 2 / 1; }
    #review-workspace[data-view="compare"] #review-code > .proposal-pane { grid-area: 3 / 1; border-top: 0; }
    #review-workspace .actions { padding: 9px 10px; }
    #review-workspace .review-buttons { gap: 4px; }
    .review-buttons .fields-toggle { padding: 6px; }
    .review-buttons .fields-toggle > span { display: none; }
    #review-workspace[data-details="hidden"] > .head { padding: 10px 12px; }
    #review-workspace[data-details="hidden"] > .head h1 { font-size: 12px; }
    .layout-options { right: -50px; }
    #review-workspace #notes { padding: 10px 12px; }
    #review-workspace .review-fields { grid-template-columns: minmax(0, 1fr) 100px; }
    #review-status { font-size: 9px; }
  }
  @media (max-height: 560px) {
    #review-workspace { overflow-y: auto; }
    #workspace-body { flex-basis: 230px; flex-shrink: 0; }
    #review-workspace .head { max-height: 110px; overflow-y: auto; }
  }
  @media (prefers-reduced-motion: reduce) {
    .workspace-splitter, .workspace-splitter > span { transition: none; }
  }
"""

WORKSPACE_LAYOUT_JS = r"""const WORKSPACE_LAYOUT_KEY = "formslang.workspace-layout.v1";
let workspaceLayout = null, workspaceFocus = false, workspaceLayoutFrame = 0;
let workspaceLastCodeView = "compare", workspaceFocusView = "compare";
const workspaceClamp = (n, min, max) => Math.min(Math.max(n, min), Math.max(min, max));
function workspaceDefaults() {
  const roomy = window.innerHeight > 760;
  return { version: 1, unitsWidth: 260, codeRatio: 50, evidenceHeight: 180, evidenceWidth: 300,
    units: true, evidence: roomy && window.innerWidth > 900, details: roomy, fields: roomy, filters: roomy };
}
function readWorkspaceLayout() {
  const defaults = workspaceDefaults();
  try {
    const saved = JSON.parse(localStorage.getItem(WORKSPACE_LAYOUT_KEY) || "null");
    if (!saved || Array.isArray(saved) || saved.version !== 1) return defaults;
    for (const key of ["units", "evidence", "details", "fields", "filters"])
      if (typeof saved[key] === "boolean") defaults[key] = saved[key];
    for (const [key, min, max] of [["unitsWidth", 220, 420], ["codeRatio", 20, 80], ["evidenceHeight", 100, 480], ["evidenceWidth", 240, 520]])
      if (typeof saved[key] === "number" && Number.isFinite(saved[key])) defaults[key] = workspaceClamp(saved[key], min, max);
  } catch (_) { /* An unavailable or malformed preference never blocks review. */ }
  return defaults;
}
function saveWorkspaceLayout() {
  try { localStorage.setItem(WORKSPACE_LAYOUT_KEY, JSON.stringify(workspaceLayout)); }
  catch (_) { /* The current layout still works when storage is unavailable. */ }
}
function workspaceIsMobile() { return window.matchMedia("(max-width: 900px)").matches; }
function workspaceStacked() { return window.matchMedia("(max-width: 600px)").matches; }
function workspaceBounds(kind) {
  const main = document.querySelector("main"), body = $("workspace-body"), code = $("review-code");
  if (kind === "units") return { min: 220, max: Math.max(220, Math.min(420, workspaceIsMobile() ? window.innerWidth * .86 : main.clientWidth - 480)), value: workspaceLayout.unitsWidth };
  if (kind === "code") {
    const available = Math.max(1, (workspaceStacked() ? code.clientHeight : code.clientWidth) - 7);
    const min = Math.min(40, Math.max(20, 100 * (workspaceStacked() ? 100 : 160) / available));
    return { min: Math.ceil(min), max: Math.floor(100 - min), value: workspaceLayout.codeRatio };
  }
  const side = $("review-workspace").dataset.evidencePosition === "side";
  return side ? { min: 240, max: Math.max(240, Math.min(520, body.clientWidth - 420)), value: workspaceLayout.evidenceWidth }
    : { min: 100, max: Math.max(100, Math.min(480, body.clientHeight - 227)), value: workspaceLayout.evidenceHeight };
}
function updateWorkspaceSeparator(id, bounds, orientation, suffix) {
  const separator = $(id), value = Math.round(workspaceClamp(bounds.value, bounds.min, bounds.max));
  separator.setAttribute("aria-orientation", orientation);
  separator.setAttribute("aria-valuemin", String(Math.round(bounds.min)));
  separator.setAttribute("aria-valuemax", String(Math.round(bounds.max)));
  separator.setAttribute("aria-valuenow", String(value));
  separator.setAttribute("aria-valuetext", value + suffix);
}
function applyWorkspaceLayout() {
  if (!workspaceLayout) return;
  const main = document.querySelector("main"), workspace = $("review-workspace"), body = $("workspace-body");
  const mobile = workspaceIsMobile();
  const units = !workspaceFocus && (mobile ? main.classList.contains("units-open") : workspaceLayout.units);
  main.dataset.units = units ? "shown" : "hidden";
  $("unit-toggle").setAttribute("aria-expanded", String(units));
  workspace.dataset.details = !workspaceFocus && workspaceLayout.details ? "shown" : "hidden";
  workspace.dataset.fields = !workspaceFocus && workspaceLayout.fields ? "shown" : "hidden";
  const evidence = !workspaceFocus && workspaceLayout.evidence;
  workspace.dataset.evidence = evidence ? "shown" : "hidden";
  const side = window.innerWidth >= 1680 && workspace.clientWidth >= 1000;
  workspace.dataset.evidencePosition = side ? "side" : "bottom";
  const unitsBounds = workspaceBounds("units");
  main.style.setProperty("--units-width", workspaceClamp(workspaceLayout.unitsWidth, unitsBounds.min, unitsBounds.max) + "px");
  const codeBounds = workspaceBounds("code");
  const ratio = workspaceClamp(workspaceLayout.codeRatio, codeBounds.min, codeBounds.max);
  body.style.setProperty("--source-fr", ratio + "fr");
  body.style.setProperty("--proposal-fr", (100 - ratio) + "fr");
  const evidenceBounds = workspaceBounds("evidence");
  body.style.setProperty(side ? "--evidence-width" : "--evidence-height", workspaceClamp(evidenceBounds.value, evidenceBounds.min, evidenceBounds.max) + "px");
  updateWorkspaceSeparator("units-splitter", unitsBounds, "vertical", " pixels wide");
  updateWorkspaceSeparator("code-splitter", codeBounds, workspaceStacked() ? "horizontal" : "vertical", "% Forms source");
  updateWorkspaceSeparator("evidence-splitter", evidenceBounds, side ? "vertical" : "horizontal", side ? " pixels wide" : " pixels high");
  for (const [key, actual] of [["units", units], ["evidence", evidence], ["details", !workspaceFocus && workspaceLayout.details], ["fields", !workspaceFocus && workspaceLayout.fields]]) {
    $("layout-" + key).checked = actual;
    $("layout-" + key).disabled = workspaceFocus;
  }
  $("fields-toggle").setAttribute("aria-expanded", String(!workspaceFocus && workspaceLayout.fields));
  $("focus-code").setAttribute("aria-pressed", String(workspaceFocus));
  $("focus-code").querySelector("span").textContent = workspaceFocus ? "Exit focus" : "Focus";
  $("focus-code").title = workspaceFocus ? "Restore workspace (Escape)" : "Expand code workspace";
  $("focus-unit-title").textContent = $("t-title").textContent;
  $("focus-unit-title").title = $("t-title").textContent;
  document.querySelector(".skip-workspace")?.setAttribute("href", workspaceFocus ? "#focus-code" : "#workspace-title");
  if (reviewView !== "evidence") workspaceLastCodeView = reviewView;
  syncOutScroll();
}
function scheduleWorkspaceLayout() {
  cancelAnimationFrame(workspaceLayoutFrame);
  workspaceLayoutFrame = requestAnimationFrame(applyWorkspaceLayout);
}
function setUnitsVisible(on, restoreFocus = false) {
  if (on && workspaceFocus) setWorkspaceFocus(false);
  const main = document.querySelector("main");
  if (workspaceIsMobile()) main.classList.toggle("units-open", on);
  else { workspaceLayout.units = on; main.classList.remove("units-open"); saveWorkspaceLayout(); }
  applyWorkspaceLayout();
  if (restoreFocus) $("unit-toggle").focus({ preventScroll: true });
}
function setWorkspaceFocus(on) {
  closeWorkspaceLayoutMenu();
  const wasFocus = workspaceFocus;
  if (on && !wasFocus) workspaceFocusView = reviewView;
  workspaceFocus = !!on;
  document.body.classList.toggle("workspace-focus", workspaceFocus);
  document.querySelector("main").classList.remove("units-open");
  if (workspaceFocus && reviewView === "evidence") setReviewView(workspaceLastCodeView);
  else if (!workspaceFocus && wasFocus) setReviewView(workspaceFocusView);
  applyWorkspaceLayout();
  $("focus-code").focus({ preventScroll: true });
  scheduleWorkspaceLayout();
}
function closeWorkspaceLayoutMenu(restoreFocus = false) {
  $("layout-options").hidden = true;
  $("layout-toggle").setAttribute("aria-expanded", "false");
  if (restoreFocus) $("layout-toggle").focus({ preventScroll: true });
}
function resetWorkspaceLayout() {
  workspaceLayout = workspaceDefaults();
  workspaceFocus = false;
  document.body.classList.remove("workspace-focus");
  document.querySelector("main").classList.remove("units-open");
  $("unit-filters").open = workspaceLayout.filters;
  if (typeof resetNavigationLayout === "function") resetNavigationLayout();
  setReviewView(workspaceIsMobile() ? "source" : "compare");
  saveWorkspaceLayout(); applyWorkspaceLayout();
  closeWorkspaceLayoutMenu(true);
  toast("Workspace layout reset.");
}
function setWorkspaceSize(kind, value) {
  const bounds = workspaceBounds(kind), clamped = workspaceClamp(value, bounds.min, bounds.max);
  if (kind === "units") workspaceLayout.unitsWidth = clamped;
  else if (kind === "code") workspaceLayout.codeRatio = clamped;
  else if ($("review-workspace").dataset.evidencePosition === "side") workspaceLayout.evidenceWidth = clamped;
  else workspaceLayout.evidenceHeight = clamped;
  applyWorkspaceLayout();
}
function wireWorkspaceSeparator(id, kind) {
  const separator = $(id);
  let pointerId = null, startValue = 0;
  function stopDrag(event, cancelled = false) {
    if (pointerId === null || (event && event.pointerId !== undefined && event.pointerId !== pointerId)) return;
    const pointer = pointerId; pointerId = null;
    if (cancelled) setWorkspaceSize(kind, startValue);
    if (separator.hasPointerCapture?.(pointer)) separator.releasePointerCapture(pointer);
    separator.classList.remove("dragging"); document.body.classList.remove("workspace-resizing");
    delete document.body.dataset.resizeAxis;
    saveWorkspaceLayout();
  }
  separator.addEventListener("pointerdown", (event) => {
    if (event.button !== 0 || pointerId !== null) return;
    event.preventDefault(); pointerId = event.pointerId; startValue = workspaceBounds(kind).value;
    separator.setPointerCapture(pointerId); separator.focus({ preventScroll: true });
    separator.classList.add("dragging"); document.body.classList.add("workspace-resizing");
    document.body.dataset.resizeAxis = separator.getAttribute("aria-orientation");
  });
  separator.addEventListener("pointermove", (event) => {
    if (event.pointerId !== pointerId) return;
    let value;
    if (kind === "units") value = event.clientX - document.querySelector("main").getBoundingClientRect().left;
    else if (kind === "code") {
      const rect = $("review-code").getBoundingClientRect();
      value = 100 * (workspaceStacked() ? event.clientY - rect.top : event.clientX - rect.left) / Math.max(1, (workspaceStacked() ? rect.height : rect.width) - 7);
    } else {
      const rect = $("workspace-body").getBoundingClientRect();
      value = $("review-workspace").dataset.evidencePosition === "side" ? rect.right - event.clientX : rect.bottom - event.clientY;
    }
    setWorkspaceSize(kind, value);
  });
  separator.addEventListener("pointerup", (event) => stopDrag(event));
  separator.addEventListener("pointercancel", (event) => stopDrag(event, true));
  separator.addEventListener("lostpointercapture", (event) => stopDrag(event));
  separator.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && pointerId !== null) { event.preventDefault(); event.stopPropagation(); stopDrag(null, true); return; }
    const vertical = separator.getAttribute("aria-orientation") === "vertical";
    const low = vertical ? "ArrowLeft" : "ArrowUp", high = vertical ? "ArrowRight" : "ArrowDown";
    if (![low, high, "Home", "End"].includes(event.key)) return;
    event.preventDefault(); event.stopPropagation();
    const bounds = workspaceBounds(kind), step = kind === "code" ? (event.shiftKey ? 10 : 2) : (event.shiftKey ? 40 : 10);
    let value = workspaceClamp(bounds.value, bounds.min, bounds.max);
    if (event.key === "Home") value = bounds.min;
    else if (event.key === "End") value = bounds.max;
    else value += (event.key === high ? 1 : -1) * step * (kind === "evidence" ? -1 : 1);
    setWorkspaceSize(kind, value); saveWorkspaceLayout();
  });
  separator.addEventListener("dblclick", () => {
    const defaults = workspaceDefaults();
    const value = kind === "units" ? defaults.unitsWidth : kind === "code" ? defaults.codeRatio
      : $("review-workspace").dataset.evidencePosition === "side" ? defaults.evidenceWidth : defaults.evidenceHeight;
    setWorkspaceSize(kind, value); saveWorkspaceLayout();
  });
}
function initWorkspaceLayout() {
  workspaceLayout = readWorkspaceLayout();
  $("unit-filters").open = workspaceLayout.filters;
  $("unit-filters").addEventListener("toggle", () => { workspaceLayout.filters = $("unit-filters").open; saveWorkspaceLayout(); });
  $("focus-code").onclick = () => setWorkspaceFocus(!workspaceFocus);
  $("layout-toggle").onclick = () => {
    const open = $("layout-options").hidden;
    $("layout-options").hidden = !open; $("layout-toggle").setAttribute("aria-expanded", String(open));
    if (open) $("layout-options").querySelector("input:not(:disabled), button").focus();
  };
  for (const key of ["units", "evidence", "details", "fields"]) $("layout-" + key).onchange = (event) => {
    if (key === "units") setUnitsVisible(event.target.checked);
    else { workspaceLayout[key] = event.target.checked; saveWorkspaceLayout(); applyWorkspaceLayout(); }
  };
  $("fields-toggle").onclick = () => {
    if (workspaceFocus) { setWorkspaceFocus(false); workspaceLayout.fields = true; }
    else workspaceLayout.fields = !workspaceLayout.fields;
    saveWorkspaceLayout(); applyWorkspaceLayout();
    if (workspaceLayout.fields) $("comment").focus();
  };
  $("evidence-close").onclick = () => {
    workspaceLayout.evidence = false;
    if (reviewView === "evidence") setReviewView(workspaceLastCodeView);
    saveWorkspaceLayout(); applyWorkspaceLayout(); $("view-evidence").focus({ preventScroll: true });
  };
  $("reset-layout").onclick = resetWorkspaceLayout;
  for (const kind of ["units", "code", "evidence"]) wireWorkspaceSeparator(kind + "-splitter", kind);
  document.addEventListener("pointerdown", (event) => {
    if (!event.target.closest(".layout-picker")) closeWorkspaceLayoutMenu();
  });
  document.addEventListener("focusin", (event) => {
    if (!event.target.closest(".layout-picker")) closeWorkspaceLayoutMenu();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape" || $("layout-options").hidden) return;
    event.preventDefault(); event.stopImmediatePropagation(); closeWorkspaceLayoutMenu(true);
  }, true);
  window.addEventListener("resize", scheduleWorkspaceLayout);
  window.addEventListener("formslang:layoutchange", scheduleWorkspaceLayout);
  window.matchMedia("(max-width: 900px)").addEventListener("change", () => {
    document.querySelector("main").classList.remove("units-open"); scheduleWorkspaceLayout();
  });
  if (typeof ResizeObserver !== "undefined") {
    const observer = new ResizeObserver(scheduleWorkspaceLayout);
    observer.observe(document.querySelector("main")); observer.observe($("workspace-body"));
  }
  applyWorkspaceLayout();
}
"""
