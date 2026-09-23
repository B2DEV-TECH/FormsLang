"""FormsLang 2.2 visual layer: design tokens, presentation mode and the Overview command center.

Loaded after PROJECT_JS and PROJECT_STYLE. The 2.1 project screens call into
this bundle only through ``typeof`` guards, so they still run without it.

Every figure comes from the server (``overview`` and ``overview/visual``);
this file only lays it out. Executive and Technical modes change labels and
density, never the assessment, and the choice lives in sessionStorage for the
browser session only.
"""

VISUAL_PROJECT_STYLE = r'''
  :root {
    --fl-space-1:4px;--fl-space-2:8px;--fl-space-3:12px;--fl-space-4:16px;--fl-space-5:24px;--fl-space-6:32px;
    --fl-radius:8px;--fl-radius-sm:5px;
    --fl-card:var(--panel);--fl-card-raised:var(--raised);--fl-card-border:var(--line);--fl-card-border-hi:var(--line-hi);
    --fl-text:var(--ink);--fl-text-dim:var(--ink-dim);--fl-accent:var(--gold);--fl-focus:var(--gold);
    --fl-status-observed:var(--ink);--fl-status-candidate:var(--risk-medium);--fl-status-proposed:var(--blue);
    --fl-status-decided:var(--green);--fl-status-unresolved:var(--violet);
    --fl-bar-track:var(--surface-2);--fl-bar-fill:var(--gold-deep);--fl-bar-failed:var(--risk-high);
  }
  .visual-command-center { display:grid;gap:var(--fl-space-3);margin:var(--fl-space-3) 0; }
  .visual-command-bar { display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:var(--fl-space-3);padding:var(--fl-space-3) var(--fl-space-4);border:1px solid var(--fl-card-border);border-radius:var(--fl-radius);background:var(--fl-card); }
  .visual-command-bar p { margin:0; }
  .visual-record { color:var(--fl-text-dim);font-size:12px;font-variant-numeric:tabular-nums; }
  .visual-mode-toggle { display:inline-flex;border:1px solid var(--fl-card-border-hi);border-radius:var(--fl-radius-sm);overflow:hidden; }
  .visual-mode-toggle button { background:none;border:0;color:var(--fl-text-dim);padding:6px 12px;cursor:pointer;font:inherit; }
  .visual-mode-toggle button[aria-pressed="true"] { background:var(--fl-card-raised);color:var(--fl-accent);font-weight:600; }
  .visual-mode-toggle button:focus-visible,.visual-card-link:focus-visible,.visual-stage button:focus-visible { outline:2px solid var(--fl-focus);outline-offset:2px; }
  .visual-panel { min-width:0;border:1px solid var(--fl-card-border);border-radius:var(--fl-radius);background:var(--fl-card);padding:var(--fl-space-4); }
  .visual-panel > h3 { margin:0 0 var(--fl-space-2);font-size:15px; }
  .visual-panel > p { margin:0 0 var(--fl-space-3); }
  .visual-kicker { display:block;color:var(--fl-text-dim);font-size:12px;letter-spacing:.02em; }
  .visual-figure { display:block;font-size:26px;font-variant-numeric:tabular-nums;line-height:1.2; }
  .visual-glance { display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:var(--fl-space-3); }
  .visual-lane-card { min-width:0;border:1px solid var(--fl-card-border);border-top:3px solid var(--fl-accent);border-radius:var(--fl-radius-sm);padding:var(--fl-space-3);background:var(--fl-card-raised); }
  .visual-lane-card[data-lane="SHARED_LOGIC"] { border-top-color:var(--blue); }
  .visual-lane-card[data-lane="DATA"] { border-top-color:var(--green); }
  .visual-lane-card[data-lane="INTEGRATION"] { border-top-color:var(--violet); }
  .visual-card-link { display:block;width:100%;text-align:left;background:none;border:0;padding:0;color:inherit;cursor:pointer;font:inherit; }
  .visual-card-link:hover .visual-figure { color:var(--fl-accent); }
  .visual-type-list { list-style:none;margin:var(--fl-space-2) 0 0;padding:0;display:grid;gap:3px;font-size:12px; }
  .visual-type-list li { display:flex;justify-content:space-between;gap:var(--fl-space-2); }
  .visual-type-list span { font-variant-numeric:tabular-nums;color:var(--fl-text-dim); }
  .visual-two { display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:var(--fl-space-3); }
  .visual-coverage { display:grid;gap:var(--fl-space-3);margin:0; }
  .visual-coverage dt { font-size:12px;color:var(--fl-text-dim); }
  .visual-coverage dd { margin:3px 0 0; }
  .visual-bar { position:relative;height:8px;border-radius:4px;background:var(--fl-bar-track);overflow:hidden;margin-top:4px; }
  .visual-bar i { position:absolute;top:0;bottom:0;left:0;background:var(--fl-bar-fill); }
  .visual-bar i.visual-bar-failed { background:var(--fl-bar-failed); }
  .visual-attention { list-style:none;margin:0;padding:0;display:grid;gap:var(--fl-space-2); }
  .visual-attention li { display:flex;align-items:center;justify-content:space-between;gap:var(--fl-space-3);border-bottom:1px solid var(--fl-card-border);padding:4px 0; }
  .visual-attention b { font-variant-numeric:tabular-nums; }
  .visual-status { display:inline-block;font-size:10.5px;letter-spacing:.03em;padding:1px 6px;border-radius:3px;border:1px solid currentColor;white-space:nowrap; }
  .visual-status[data-status="OBSERVED"] { color:var(--fl-status-observed);border-style:solid; }
  .visual-status[data-status="CANDIDATE"] { color:var(--fl-status-candidate);border-style:dashed; }
  .visual-status[data-status="PROPOSED"] { color:var(--fl-status-proposed);border-style:dotted; }
  .visual-status[data-status="DECIDED"] { color:var(--fl-status-decided);border-style:double;border-width:3px; }
  .visual-status[data-status="UNRESOLVED"] { color:var(--fl-status-unresolved);border-style:dashed;font-style:italic; }
  .visual-journey { list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:var(--fl-space-3); }
  .visual-stage { border:1px solid var(--fl-card-border);border-radius:var(--fl-radius-sm);padding:var(--fl-space-3);background:var(--fl-card-raised);display:flex;flex-direction:column;gap:var(--fl-space-2); }
  .visual-stage h4 { margin:0;font-size:14px; }
  .visual-stage p { margin:0;font-size:12px;color:var(--fl-text-dim); }
  .visual-stage dl { margin:0;display:grid;gap:2px;font-size:12px; }
  .visual-stage dl div { display:flex;justify-content:space-between;gap:var(--fl-space-2); }
  .visual-stage dd { margin:0;font-variant-numeric:tabular-nums; }
  .visual-stage button { margin-top:auto;align-self:flex-start; }
  .visual-boundary { border-left:3px solid var(--fl-accent);padding:6px 10px;background:var(--fl-card-raised);font-size:12.5px; }
  .visual-board { display:grid;grid-auto-flow:column;grid-auto-columns:minmax(210px,1fr);gap:var(--fl-space-3);overflow-x:auto;padding-bottom:4px; }
  .visual-board-column { min-width:0;border:1px solid var(--fl-card-border);border-radius:var(--fl-radius-sm);padding:var(--fl-space-3);background:var(--fl-card-raised); }
  .visual-board-column h4 { margin:0 0 4px;font-size:13px;display:flex;justify-content:space-between;gap:var(--fl-space-2); }
  .visual-board-column ul { list-style:none;margin:var(--fl-space-2) 0 0;padding:0;display:grid;gap:var(--fl-space-2); }
  .visual-board-column li { border:1px solid var(--fl-card-border);border-radius:var(--fl-radius-sm);padding:6px 8px;background:var(--fl-card);font-size:12px;overflow-wrap:anywhere; }
  .visual-board-column li span { display:block;color:var(--fl-text-dim); }
  .project-start-here { display:grid;gap:var(--fl-space-2);margin:var(--fl-space-2) 0; }
  .project-priority-item { display:flex;justify-content:space-between;gap:var(--fl-space-3);border:1px solid var(--fl-card-border);border-left:3px solid var(--fl-accent);border-radius:var(--fl-radius-sm);padding:8px 10px;background:var(--fl-card-raised); }
  .visual-map-toolbar { display:flex;flex-wrap:wrap;align-items:flex-end;gap:var(--fl-space-2) var(--fl-space-3);margin-bottom:var(--fl-space-2); }
  .visual-map-toolbar label { display:flex;flex-direction:column;gap:3px;font-size:12px;color:var(--fl-text-dim); }
  .visual-map-toolbar input[type="search"] { min-width:180px; }
  .visual-map-toolbar-actions { display:flex;flex-wrap:wrap;align-items:center;gap:var(--fl-space-2);margin-left:auto; }
  .visual-map-hint { margin:0 0 var(--fl-space-2);font-size:12px;color:var(--fl-text-dim); }
  .visual-map-hint:empty { display:none; }
  .visual-map-note { margin:0 0 var(--fl-space-2);padding:6px 10px;border-left:3px solid var(--fl-accent);background:var(--fl-card-raised);font-size:12.5px; }
  .visual-map-note .btn { margin-left:var(--fl-space-2);padding:2px 8px; }
  .visual-map-stage { position:relative;min-width:0; }
  .project-system-map-canvas.visual-map-canvas { height:clamp(420px,62vh,720px);min-height:0;overflow:auto;cursor:grab;touch-action:pan-x pan-y; }
  .visual-map-canvas.is-panning { cursor:grabbing;user-select:none; }
  .project-system-map-svg.visual-map-svg { min-width:0;min-height:0;max-width:none;display:block; }
  .visual-map-controls { position:absolute;top:8px;right:8px;display:flex;gap:4px;z-index:2; }
  .visual-map-controls .btn { min-width:30px;padding:3px 7px;line-height:1.2; }
  .visual-map-minimap { position:absolute;right:8px;bottom:34px;z-index:2;background:var(--surface-1);border:1px solid var(--border-subtle);border-radius:6px;cursor:pointer; }
  .visual-map-minimap rect { fill:var(--ink-dim);opacity:.55; }
  .visual-map-minimap rect[data-lane="APPLICATION"] { fill:var(--fl-accent); }
  .visual-map-minimap rect[data-lane="SHARED_LOGIC"] { fill:var(--blue); }
  .visual-map-minimap rect[data-lane="DATA"] { fill:var(--green); }
  .visual-map-minimap rect[data-lane="INTEGRATION"] { fill:var(--violet); }
  .visual-map-minimap .visual-map-minimap-view { fill:none;opacity:1;stroke:var(--fl-focus);stroke-width:1.5; }
  .visual-map-lane { fill:var(--surface-1);stroke:var(--border-subtle);opacity:.6; }
  .visual-map-lane[data-lane="APPLICATION"] { stroke:var(--fl-accent); }
  .visual-map-lane[data-lane="SHARED_LOGIC"] { stroke:var(--blue); }
  .visual-map-lane[data-lane="DATA"] { stroke:var(--green); }
  .visual-map-lane[data-lane="INTEGRATION"] { stroke:var(--violet); }
  .visual-map-column { font-size:12.5px;font-weight:650;fill:var(--ink-dim); }
  .visual-map-card { fill:var(--surface-1);stroke:var(--border-strong);stroke-width:1.2; }
  .visual-map-card[data-risk="CRITICAL"] { stroke:var(--risk-critical);stroke-width:2.2; }
  .visual-map-card[data-risk="HIGH"] { stroke:var(--risk-high);stroke-width:1.8; }
  .visual-map-card[data-risk="MEDIUM"] { stroke:var(--risk-medium); }
  .visual-map-node.is-unresolved .visual-map-card { fill:none;stroke:var(--fl-status-unresolved);stroke-dasharray:5 4; }
  .visual-map-node.is-candidate .visual-map-card { stroke:var(--fl-status-candidate);stroke-dasharray:2 3; }
  .visual-legend-node.is-candidate { stroke:var(--fl-status-candidate);stroke-dasharray:2 3; }
  .visual-map-node.is-focus .visual-map-card { fill:var(--surface-2);stroke:var(--gold);stroke-width:3; }
  .visual-map-node.is-selected .visual-map-card { stroke:var(--gold);stroke-width:3.2; }
  .visual-map-node:focus { outline:none; }
  .visual-map-node:focus-visible .visual-map-card { stroke:var(--fl-focus);stroke-width:4; }
  .visual-map-name { font-size:12px;font-weight:650;fill:var(--ink); }
  .visual-map-meta { font-size:10.5px;fill:var(--ink-dim); }
  .visual-map-badge rect { fill:var(--surface-0);stroke:var(--fl-status-candidate);stroke-dasharray:3 2; }
  .visual-map-badge text { font-size:10px;fill:var(--fl-status-candidate); }
  .visual-map-line { fill:none;stroke:var(--border-strong); }
  .visual-map-arrowhead { fill:var(--ink-dim); }
  .visual-map-edge.is-candidate .visual-map-line { stroke-dasharray:6 4; }
  .visual-map-edge.is-hotspot .visual-map-line { stroke:var(--risk-high); }
  .visual-map-edge.is-selected .visual-map-line { stroke:var(--gold);stroke-width:3.5; }
  .visual-map-edge:hover .visual-map-line { stroke-width:3; }
  .visual-map-hit { fill:none;stroke:transparent;stroke-width:12;pointer-events:stroke; }
  .visual-map-svg .is-dim { opacity:.16; }
  .visual-map-legend { border:1px solid var(--fl-card-border);border-radius:var(--fl-radius);background:var(--fl-card);padding:var(--fl-space-3) var(--fl-space-4);margin-bottom:var(--fl-space-2);font-size:12.5px; }
  .visual-map-legend h4 { margin:0 0 var(--fl-space-2);font-size:13px; }
  .visual-map-legend ul { list-style:none;margin:0 0 var(--fl-space-2);padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:4px var(--fl-space-4); }
  .visual-map-legend li { display:flex;align-items:center;gap:var(--fl-space-2); }
  .visual-legend-line { stroke:var(--border-strong);stroke-width:2; }
  .visual-legend-line.is-candidate { stroke-dasharray:6 4; }
  .visual-legend-line.is-hotspot { stroke:var(--risk-high); }
  .visual-legend-node { fill:none;stroke:var(--fl-status-unresolved);stroke-dasharray:5 4; }
  .visual-legend-badge { font-size:11px;color:var(--fl-status-candidate);border:1px dashed var(--fl-status-candidate);border-radius:3px;padding:0 4px; }
  .visual-drawer-section { border-top:1px solid var(--fl-card-border);padding-top:var(--fl-space-2);margin-top:var(--fl-space-2); }
  .visual-drawer-section p { margin:4px 0; }
  .visual-drawer-facts { margin:0;display:grid;gap:3px;font-size:12.5px; }
  .visual-drawer-facts div { display:flex;justify-content:space-between;gap:var(--fl-space-2); }
  .visual-drawer-facts dt { color:var(--fl-text-dim); }
  .visual-drawer-facts dd { margin:0;text-align:right;overflow-wrap:anywhere; }
  .visual-drawer-rel ul,.visual-drawer-list { list-style:none;margin:4px 0;padding:0;display:grid;gap:3px;font-size:12px; }
  .visual-drawer-list li span { display:block;color:var(--fl-text-dim); }
  .visual-drawer-list li span.visual-status { display:inline-block; }
  .visual-drawer-actions { display:flex;flex-direction:column;gap:6px;margin-top:4px; }
  .visual-map-table { margin-top:var(--fl-space-3); }
  .visual-map-table summary { cursor:pointer;font-size:13px;padding:6px 0; }
  @media(prefers-reduced-motion:no-preference){.visual-map-node,.visual-map-edge{transition:opacity .15s ease;}}
  @media(max-width:1100px){.project-system-map-split{grid-template-columns:1fr;}.visual-map-minimap{display:none;}.visual-map-toolbar-actions{margin-left:0;}}
  @media(max-width:720px){.project-system-map-canvas.visual-map-canvas{height:60vh;}.visual-map-controls{position:static;margin-top:4px;flex-wrap:wrap;}}
  .visual-page-head { display:flex;flex-wrap:wrap;align-items:flex-start;justify-content:space-between;gap:var(--fl-space-3); }
  .visual-page-head h2 { margin:var(--fl-space-2) 0 var(--fl-space-1); }
  .visual-back { margin-bottom:var(--fl-space-1); }
  .visual-module-grid { display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:var(--fl-space-3);margin:var(--fl-space-3) 0; }
  #visual-module-body > .visual-panel { margin:var(--fl-space-3) 0; }
  .visual-panel h4 { margin:var(--fl-space-3) 0 var(--fl-space-1);font-size:13px; }
  .visual-cell-note { display:block;color:var(--fl-text-dim);font-size:11.5px; }
  .visual-neighbours td,.visual-matrix td,.visual-matrix th { vertical-align:top; }
  .visual-hotspot { border:1px solid var(--fl-card-border);border-left:3px solid var(--fl-status-candidate);border-radius:var(--fl-radius);background:var(--fl-card);padding:var(--fl-space-4);margin:var(--fl-space-3) 0; }
  .visual-hotspot-head h3 { margin:0 0 var(--fl-space-1);font-size:15px;overflow-wrap:anywhere; }
  .visual-hotspot-head p { margin:0 0 var(--fl-space-3); }
  .visual-why,.visual-not-prove { min-width:0;border:1px solid var(--fl-card-border);border-radius:var(--fl-radius-sm);padding:var(--fl-space-3);background:var(--fl-card-raised); }
  .visual-not-prove { border-style:dashed; }
  .visual-why h4,.visual-not-prove h4 { margin:0 0 var(--fl-space-2); }
  .visual-not-prove ul { margin:0 0 var(--fl-space-2);padding-left:18px; }
  .visual-severity { font-size:11px;font-weight:700;letter-spacing:.03em;border:1px solid var(--fl-card-border-hi);border-radius:3px;padding:0 5px; }
  .visual-severity[data-severity="HIGH"] { color:var(--risk-high);border-color:var(--risk-high); }
  .visual-hotspot-nodes { list-style:none;margin:0;padding:0;display:grid;gap:4px; }
  .visual-hotspot-nodes li { display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:var(--fl-space-2); }
  .visual-hotspot-nodes small { color:var(--fl-text-dim); }
  .visual-matrix td { text-align:center;font-variant-numeric:tabular-nums; }
  .visual-matrix th[scope="row"] { overflow-wrap:anywhere;max-width:340px;text-align:left; }
  .visual-matrix td[data-level="1"] { background:color-mix(in srgb,var(--fl-status-candidate) 12%,transparent); }
  .visual-matrix td[data-level="2"] { background:color-mix(in srgb,var(--fl-status-candidate) 24%,transparent); }
  .visual-matrix td[data-level="3"] { background:color-mix(in srgb,var(--fl-status-candidate) 38%,transparent); }
  .visual-matrix .visual-card-link { text-align:center; }
  .visual-review-context { border:1px solid var(--fl-card-border);border-radius:var(--fl-radius-sm);padding:var(--fl-space-2) var(--fl-space-3);margin:0 0 var(--fl-space-3);font-size:12.5px; }
  .visual-review-context:empty { display:none; }
  .visual-review-context p { margin:0 0 var(--fl-space-2); }
  .search-map-link { font:inherit;font-size:11px;background:none;border:1px solid var(--border-subtle);border-radius:4px;color:var(--ink-dim);padding:1px 6px;margin-right:6px;cursor:pointer; }
  @media(max-width:900px){.visual-module-grid{grid-template-columns:1fr;}}
  body[data-view-mode="executive"] .visual-technical-only { display:none; }
  @media(max-width:1100px){.visual-glance,.visual-journey{grid-template-columns:repeat(2,minmax(0,1fr));}}
  @media(max-width:720px){.visual-glance,.visual-journey,.visual-two{grid-template-columns:1fr;}.visual-command-bar{flex-direction:column;align-items:flex-start;}}
  @media(prefers-reduced-motion:reduce){.visual-command-center *{transition:none!important;animation:none!important;scroll-behavior:auto!important;}}
'''

VISUAL_PROJECT_JS = r'''
// ---- 2.2 presentation mode ------------------------------------------------
// Presentation only: the same saved assessment, labelled for a technical or an
// executive reader. Remembered for this browser session; never sent or saved.
const VISUAL_MODE_KEY = 'formslang.presentationMode';
const visualUI = { mode: null, overview: { key: null, data: null, error: null, request: 0 } };

function visualMode() {
  if (visualUI.mode) return visualUI.mode;
  let stored = null;
  try { stored = window.sessionStorage ? window.sessionStorage.getItem(VISUAL_MODE_KEY) : null; } catch (e) { stored = null; }
  visualUI.mode = stored === 'executive' ? 'executive' : 'technical';
  if (document.body && document.body.dataset) document.body.dataset.viewMode = visualUI.mode;
  return visualUI.mode;
}

function visualSetMode(mode) {
  visualUI.mode = mode === 'executive' ? 'executive' : 'technical';
  try { if (window.sessionStorage) window.sessionStorage.setItem(VISUAL_MODE_KEY, visualUI.mode); } catch (e) { /* private window: the mode lasts for this page */ }
  if (document.body && document.body.dataset) document.body.dataset.viewMode = visualUI.mode;
  if (projectUI.view === 'overview' && projectUI.overview) renderProjectOverview(projectUI.overview);
  else if (projectUI.view === 'system-map' && typeof renderProjectSystemMap === 'function') renderProjectSystemMap();
  else if (projectUI.view === 'module-360' && typeof visualRenderModule === 'function') visualRenderModule();
  else if (projectUI.view === 'hotspots' && typeof visualRenderHotspots === 'function') visualRenderHotspots();
  const pressed = $('visual-mode-' + visualUI.mode);
  if (pressed && pressed.focus) pressed.focus();
}

// A server label pair {technical, executive}; the technical text is the fallback.
function visualLabel(pair) {
  if (!pair) return '';
  return pair[visualMode()] || pair.technical || '';
}

function visualModeToggle() {
  const mode = visualMode();
  const button = (id, label) => `<button type="button" id="visual-mode-${id}" data-visual-mode="${id}" aria-pressed="${mode === id}">${label}</button>`;
  return `<div class="visual-mode-toggle" role="group" aria-label="Presentation mode">${button('executive', 'Executive')}${button('technical', 'Technical')}</div>`;
}

function visualBindModeToggle(root) {
  root.querySelectorAll('[data-visual-mode]').forEach(el => { el.onclick = () => visualSetMode(el.dataset.visualMode); });
}

// Epistemic status chip. The five statuses keep their own words and shapes.
const visualStatusText = { OBSERVED: 'Observed', CANDIDATE: 'Candidate', PROPOSED: 'Proposed', DECIDED: 'Decided', UNRESOLVED: 'Unresolved' };
function visualStatus(status, title) {
  const key = visualStatusText[status] ? status : 'OBSERVED';
  return `<span class="visual-status" data-status="${key}"${title ? ` title="${esc(title)}"` : ''}>${visualStatusText[key]}</span>`;
}

// A count the server did not provide is "Not observed", never zero.
function visualCount(value) { return Number.isInteger(value) ? String(value) : 'Not observed'; }

// ---- Overview command center ----------------------------------------------
function visualOverviewKey(data) {
  const a = data.assessment || {};
  return [projectUI.activeId, a.analysis_revision || data.analysis_revision || '', a.review_revision ?? data.review_revision ?? '', a.freshness || ''].join('|');
}

function visualCoverage(coverage = {}) {
  const forms = coverage.forms || {}, database = coverage.database || {}, libraries = coverage.libraries || {};
  const bar = (done, total, failed) => {
    if (!Number.isInteger(done) || !Number.isInteger(total) || total <= 0) return '';
    const width = n => Math.max(0, Math.min(100, Math.round(100 * n / total)));
    const failedPart = Number.isInteger(failed) && failed > 0 ? `<i class="visual-bar-failed" style="left:${width(done)}%;width:${width(failed)}%"></i>` : '';
    return `<div class="visual-bar" aria-hidden="true"><i style="width:${width(done)}%"></i>${failedPart}</div>`;
  };
  const failed = Number.isInteger(forms.failed) ? ` · ${forms.failed} failed` : '';
  const librariesText = Number.isInteger(libraries.discovered)
    ? `${libraries.discovered} discovered · ${visualCount(libraries.without_semantic_representation)} without semantic representation`
    : 'Not observed';
  return `<section class="visual-panel" aria-labelledby="visual-coverage-title"><h3 id="visual-coverage-title">Source Coverage</h3><dl class="visual-coverage">
    <div><dt>Forms representations</dt><dd>${esc(visualCount(forms.analyzed))} of ${esc(visualCount(forms.discovered))} analyzed${esc(failed)}</dd>${bar(forms.analyzed, forms.discovered, forms.failed)}</div>
    <div><dt>Database sources</dt><dd>${esc(visualCount(database.analyzed))} analyzed${Number.isInteger(database.discovered) ? ` of ${database.discovered} discovered` : ''}</dd>${bar(database.analyzed, database.discovered, database.failed)}</div>
    <div><dt>PL/SQL libraries</dt><dd>${esc(librariesText)}</dd></div>
  </dl><p class="project-muted">Coverage describes what was read, not how much of the migration is done.</p></section>`;
}

function visualAttentionSummary(data) {
  const priority = data.priority || {}, hotspots = data.hotspots || {}, severity = hotspots.by_severity || {};
  const hasHotspots = Number.isInteger(hotspots.total);
  const rows = [
    ['critical', 'Unresolved CRITICAL findings', priority.critical, 'PROPOSED', 'Engine proposals waiting for a human decision'],
    ['high', 'Unresolved HIGH findings', priority.high, 'PROPOSED', 'Engine proposals waiting for a human decision'],
    ['manual', 'Findings that need an architecture decision', priority.manual, 'PROPOSED', 'The engine could not propose a mechanical path'],
    ['stale', 'Decisions that no longer match the source', priority.stale, 'DECIDED', 'A human decision was recorded against an earlier source'],
    ['hotspots', 'Hotspot candidates', hotspots.total, 'CANDIDATE', 'Structural evidence that needs architecture review, not a verdict'],
  ];
  const items = rows.map(([id, label, value, status, title]) => `<li><button type="button" class="project-metric-link" data-visual-attention="${id}">${esc(label)}</button><span>${visualStatus(status, title)} <b>${esc(visualCount(value))}</b></span></li>`).join('');
  const detail = hasHotspots ? `<p class="project-muted">${Number(severity.HIGH || 0)} HIGH · ${Number(severity.MEDIUM || 0)} MEDIUM hotspot candidates.</p>` : '';
  return `<section class="visual-panel" aria-labelledby="visual-attention-title"><h3 id="visual-attention-title">Architecture Attention</h3><ul class="visual-attention">${items}</ul>${detail}</section>`;
}

function visualInventoryCategory(type, lane) {
  const map = { FORM: 'forms', FORM_REFERENCE: 'forms', PACKAGE: 'packages', SUBPROGRAM_BODY: 'routines', PACKAGE_SUBPROGRAM: 'routines', TABLE: 'tables', VIEW: 'views', LIBRARY: 'libraries', LIBRARY_REFERENCE: 'libraries' };
  return map[type] || (lane === 'APPLICATION' ? 'forms' : 'dependencies');
}

function visualEstateGlance(visual) {
  const lanes = visual.estate || [];
  if (!lanes.length) return '<p class="project-empty">No module-level architecture was recorded in this assessment.</p>';
  return `<div class="visual-glance">${lanes.map(lane => {
    // Executive labels fold several recorded types into one reader-facing term.
    const merged = [];
    (lane.types || []).forEach(t => {
      const label = visualLabel(t), found = merged.find(m => m.label === label);
      if (found) found.count += Number(t.count || 0); else merged.push({ label, type: t.type, count: Number(t.count || 0) });
    });
    const list = merged.length
      ? `<ul class="visual-type-list">${merged.map(m => `<li><button type="button" class="project-metric-link" data-visual-type="${esc(m.type)}" data-visual-lane-of="${esc(lane.lane)}">${esc(m.label)}</button><span>${m.count}</span></li>`).join('')}</ul>`
      : '<p class="project-muted">None recorded.</p>';
    return `<article class="visual-lane-card" data-lane="${esc(lane.lane)}"><button type="button" class="visual-card-link" data-visual-lane="${esc(lane.lane)}" aria-label="${esc(visualLabel(lane))}: ${Number(lane.count || 0)} modules. Open in System Map"><span class="visual-kicker">${esc(visualLabel(lane))}</span><b class="visual-figure">${Number(lane.count || 0)}</b></button>${list}</article>`;
  }).join('')}</div>`;
}

const visualJourneyFacts = { forms_modules: 'Forms modules', database_packages: 'Database packages', dependencies: 'Dependencies', modernization_findings: 'Findings', hotspot_candidates: 'Hotspot candidates', decided: 'Decisions recorded', findings: 'Findings to decide' };
const visualJourneyActions = { UNDERSTAND: 'Explore System Map', ASSESS: 'Explore Hotspots', DECIDE: 'Open Review', DELIVER: 'Open Reports' };

function visualJourney(visual) {
  const stages = visual.journey || [];
  const facts = stage => {
    const entries = Object.entries(stage.facts || {});
    if (!entries.length) return '<p>Reports and packages are generated on request from the saved assessment.</p>';
    return `<dl>${entries.map(([key, value]) => `<div><dt>${esc(visualJourneyFacts[key] || key)}</dt><dd>${esc(visualCount(value))}</dd></div>`).join('')}</dl>`;
  };
  return `<ol class="visual-journey">${stages.map(stage => `<li class="visual-stage" data-stage="${esc(stage.id)}"><h4>${esc(stage.label)}</h4><p>${esc(stage.question)}</p>${facts(stage)}<button type="button" class="btn" data-visual-journey="${esc(stage.section)}">${esc(visualJourneyActions[stage.id] || 'Open')}</button></li>`).join('')}</ol>`;
}

const visualReasonLabels = { UNRESOLVED_UNKNOWN: 'Risk could not be measured', HOTSPOT_HIGH: 'HIGH hotspot candidate', HOTSPOT_MEDIUM: 'MEDIUM hotspot candidate', HOTSPOT_CANDIDATE: 'Hotspot candidate' };
// A module id is "<source root>/<file>"; the file name is what a reader recognises,
// the full id stays available as a tooltip.
function visualModuleLabel(module) { const id = String(module || ''); return `<span title="${esc(id)}">${esc(id.split('/').pop())}</span>`; }
function visualReasonText(reasons = []) { return reasons.map(r => visualReasonLabels[r] || projectFactorText([r])).join(' · '); }

function visualInvestigationBoard(visual) {
  const board = visual.board || { groups: [] };
  const columns = (board.groups || []).map(group => {
    const modules = (group.modules || []).map(m => `<li><button type="button" class="project-metric-link" data-visual-module="${esc(m.module)}"><b>${visualModuleLabel(m.module)}</b></button><span>${Number(m.findings || 0)} findings · ${Number(m.unresolved || 0)} awaiting decision${m.hotspot_candidates ? ` · ${Number(m.hotspot_candidates)} hotspot candidates` : ''}${m.stale_decisions ? ` · ${Number(m.stale_decisions)} stale decisions` : ''}</span>${(m.reasons || []).length ? `<span>Why: ${esc(visualReasonText(m.reasons))}</span>` : ''}</li>`).join('');
    const more = group.truncated ? `<p class="project-muted">Showing ${(group.modules || []).length} of ${Number(group.total || 0)}. Filter Inventory by module for the rest.</p>` : '';
    return `<section class="visual-board-column" aria-label="${esc(group.name)}" data-group="${esc(group.id)}"><h4><span>${esc(group.name)}</span><span>${Number(group.total || 0)}</span></h4><p class="project-muted">${esc(group.rule)}</p>${modules ? `<ul>${modules}</ul>` : '<p class="project-muted">No modules in this group.</p>'}${more}</section>`;
  }).join('');
  return `<p class="visual-boundary" role="note">${esc(board.boundary || '')}</p><div class="visual-board">${columns}</div>`;
}

// Static part: rendered with the overview. Live part: filled from overview/visual.
function visualCommandCenter(data) {
  const assessment = data.assessment || {};
  const priority = data.priority || {};
  const primary = Number(priority.total || 0) > 0 ? projectButton('visual-primary-review', 'Start Priority Review', true) : projectButton('visual-primary-map', 'Explore System Map', true);
  const revision = String(assessment.analysis_revision || data.analysis_revision || '').slice(0, 12);
  const assessed = assessment.assessment_timestamp || data.assessment_timestamp;
  return `<section class="visual-command-center" aria-label="Modernization command center">
    <div class="visual-command-bar"><p class="visual-record">${assessed ? `Assessed ${esc(assessed)}` : 'Not analyzed'}${revision ? ` · Revision ${esc(revision)}` : ''}</p>${visualModeToggle()}${primary}</div>
    <section class="visual-panel" aria-labelledby="visual-estate-title"><h3 id="visual-estate-title">Estate at a Glance</h3><div id="visual-estate" aria-live="polite"><p class="project-muted">Loading estate architecture…</p></div></section>
    <div class="visual-two">${visualCoverage(data.source_coverage)}${visualAttentionSummary(data)}</div>
    <section class="visual-panel" aria-labelledby="visual-journey-title"><h3 id="visual-journey-title">Modernization Journey</h3><p class="project-muted">The kind of work each stage asks for, with what the assessment observed. It is not a progress tracker: stages overlap and none is ever marked complete.</p><div id="visual-journey"></div></section>
    <section class="visual-panel" aria-labelledby="visual-board-title"><h3 id="visual-board-title">Investigation Board</h3><div id="visual-board"></div></section>
  </section>`;
}

function visualFillOverview(data) {
  const state = visualUI.overview, visual = state.data;
  const estate = $('visual-estate'), journeyEl = $('visual-journey'), board = $('visual-board');
  if (!estate || !journeyEl || !board) return;
  if (state.error) {
    estate.innerHTML = `<p class="project-state-warning" role="status">Estate visuals are unavailable: ${esc(state.error)} The saved assessment above is unaffected.</p>`;
    journeyEl.innerHTML = ''; board.innerHTML = ''; return;
  }
  if (!visual) {
    if (state.key === visualOverviewKey(data)) { estate.innerHTML = '<p class="project-empty">Estate visuals become available after an assessment is saved.</p>'; journeyEl.innerHTML = ''; board.innerHTML = ''; }
    return;
  }
  estate.innerHTML = visualEstateGlance(visual);
  journeyEl.innerHTML = visualJourney(visual);
  board.innerHTML = visualInvestigationBoard(visual);
  const root = $('project-content');
  root.querySelectorAll('[data-visual-lane]').forEach(el => { el.onclick = () => projectSystemMapOpen({ view: 'ESTATE', lane: el.dataset.visualLane, focus: null }); });
  root.querySelectorAll('[data-visual-type]').forEach(el => { el.onclick = () => projectOpenInventory({ category: visualInventoryCategory(el.dataset.visualType, el.dataset.visualLaneOf) }); });
  root.querySelectorAll('[data-visual-journey]').forEach(el => { el.onclick = () => visualOpenSection(el.dataset.visualJourney); });
  root.querySelectorAll('[data-visual-module]').forEach(el => { el.onclick = () => visualOpenModule(el.dataset.visualModule); });
}

function visualOpenSection(section) {
  if (section === 'system-map') projectSystemMapOpen({ view: 'ESTATE' });
  else if (section === 'hotspots') { if (typeof visualHotspotsOpen === 'function') visualHotspotsOpen({}); else projectOpenInventory({ category: 'hotspots' }); }
  else if (section === 'review') projectReviewOpen();
  else if (section === 'reports') projectReportsOpen();
}

function visualOpenModule(module) {
  if (typeof visualModuleOpen === 'function') visualModuleOpen(module);
  else projectOpenInventory({ category: 'findings', filters: { module } });
}

async function visualLoadOverview(data) {
  const c = projectContext(), key = visualOverviewKey(data), request = ++visualUI.overview.request;
  try {
    const payload = await api(`/api/v2/projects/${encodeURIComponent(c.id)}/overview/visual`);
    if (!projectCurrent(c) || request !== visualUI.overview.request) return;
    visualUI.overview = { key, data: payload?.visual || null, error: null, request };
  } catch (e) {
    if (!projectCurrent(c) || request !== visualUI.overview.request) return;
    visualUI.overview = { key: null, data: null, error: e.message, request };
  }
  if (projectUI.view === 'overview' && projectUI.overview === data) visualFillOverview(data);
}

function visualBindOverview(data) {
  const root = $('project-content');
  visualBindModeToggle(root);
  const review = $('visual-primary-review'), map = $('visual-primary-map');
  if (review) review.onclick = projectOpenPriorityReview;
  if (map) map.onclick = () => projectSystemMapOpen({ view: 'ESTATE' });
  root.querySelectorAll('[data-visual-attention]').forEach(el => {
    el.onclick = () => {
      const kind = el.dataset.visualAttention;
      if (kind === 'hotspots') visualOpenSection('hotspots');
      else if (kind === 'stale') projectOpenInventory({ category: 'findings', filters: { review: 'STALE' } });
      else if (kind === 'manual') projectOpenInventory({ category: 'findings', filters: { intervention: 'MANUAL', priority: 'unresolved' } });
      else projectOpenInventory({ category: 'findings', filters: { risk: kind.toUpperCase(), priority: 'unresolved' } });
    };
  });
  // A review decision changes the review revision, so the overlay is refetched
  // without re-analysis; an unchanged key reuses what is already on screen.
  if (visualUI.overview.key === visualOverviewKey(data) && !visualUI.overview.error) visualFillOverview(data);
  else visualLoadOverview(data);
}

// ---- 2.2 System Map ------------------------------------------------------
// Module-level architecture drawn from the server layout. The browser never
// invents a position, a relationship or a label: coordinates, lanes and
// presentation labels arrive with the response. Lens, lane and search only
// change emphasis; they never hide what the server returned.
const systemMapState = { view: 'ESTATE', focus: null, lane: null, depth: 2, layer: '', edge_type: '', lens: 'ARCHITECTURE', query: '', legend: false, zoom: 1, data: null, layoutKey: null, selectedNode: null, selectedEdge: null, detail: { id: null, data: null, error: null, request: 0 }, request: 0 };
const systemMapLayerLabels = { FORM: 'Forms', DATABASE: 'Database', GLOBAL: 'Global state', LIBRARY: 'Libraries / menus', INTEGRATION: 'Integration points', UNRESOLVED: 'Unresolved references', OTHER: 'Other' };
const systemMapLenses = {
  ARCHITECTURE: ['Architecture', 'Every observed relationship at equal weight.'],
  DATA_ACCESS: ['Data access', 'Emphasises reads and writes of data objects.'],
  SHARED_LOGIC: ['Shared logic', 'Emphasises service calls, shared global state and similar logic.'],
  HOTSPOTS: ['Hotspots', 'Emphasises what is linked to a hotspot candidate. Candidates need architecture review; they are not verdicts.'],
  REVIEW: ['Review', 'Shows open and stale review decisions on each node. Review status is not migration readiness.'],
};
const systemMapZoomSteps = [0.25, 0.35, 0.5, 0.65, 0.8, 1, 1.25, 1.5, 2];
const systemMapLaneFallback = { FORM: 'APPLICATION', LIBRARY: 'APPLICATION', GLOBAL: 'SHARED_LOGIC' };

async function projectSystemMapOpen(options = {}) {
  projectSaveDraft();projectEnter('system-map');
  if (systemMapState.projectId !== projectUI.activeId) Object.assign(systemMapState, { view: 'ESTATE', focus: null, lane: null, query: '', lens: 'ARCHITECTURE', zoom: 1, data: null, layoutKey: null, selectedNode: null, selectedEdge: null, projectId: projectUI.activeId });
  // A focus request (search, a drawer, a hotspot) opens the focus view unless told otherwise.
  const next = { ...options };
  if (next.focus && !next.view) next.view = 'FOCUS';
  if (next.view === 'ESTATE' && !('focus' in next)) next.focus = null;
  Object.assign(systemMapState, next);
  renderProjectSystemMap();
  await loadProjectSystemMap();
}

async function loadProjectSystemMap() {
  const c = projectContext(), request = ++systemMapState.request;
  const params = new URLSearchParams({ view: systemMapState.view, depth: String(systemMapState.depth) });
  if (systemMapState.view === 'FOCUS' && systemMapState.focus) params.set('focus', systemMapState.focus);
  if (systemMapState.layer) params.set('layer', systemMapState.layer);
  if (systemMapState.edge_type) params.set('edge_type', systemMapState.edge_type);
  try {
    const data = await api(`/api/v2/projects/${encodeURIComponent(c.id)}/system-map?${params}`);
    if (!projectCurrent(c) || projectUI.view !== 'system-map' || request !== systemMapState.request) return;
    systemMapState.data = data;
    if (systemMapState.view === 'FOCUS' && data.focus) systemMapState.focus = data.focus;
    if (systemMapState.selectedNode) systemMapState.selectedNode = data.nodes.find(n => n.id === systemMapState.selectedNode.id) || null;
    if (systemMapState.selectedEdge) systemMapState.selectedEdge = data.edges.find(e => e.id === systemMapState.selectedEdge.id) || null;
    // A new layout starts at 100%; a refresh of the same view keeps the reader's zoom.
    const key = [data.view, data.focus, data.layer_filter, data.edge_filter, data.analysis_revision].join('|');
    const fresh = key !== systemMapState.layoutKey;
    if (fresh) { systemMapState.layoutKey = key; systemMapState.zoom = 1; }
    renderProjectSystemMap();
    // A new focus layout opens on the focus column, not on its far-left callers.
    if (fresh && data.view === 'FOCUS' && data.focus) systemMapCenterOn(data.focus);
  } catch (e) {
    if (projectCurrent(c) && request === systemMapState.request) projectError(e.message);
  }
}

function systemMapNumber(value) { return Number(value || 0).toLocaleString('en-US'); }

function systemMapTruncation(d) {
  return (d.truncation || []).map(t => {
    if (t.reason === 'SELECTOR_LIMIT') return `<p class="project-state-warning">The Form selector lists ${systemMapNumber(t.limit)} of ${systemMapNumber(t.available)} Forms. Use Search (Ctrl+K) to focus any other Form.</p>`;
    const what = t.reason === 'EDGE_LIMIT' ? 'relationships' : t.reason === 'NODE_LIMIT' ? 'nodes' : esc(t.reason);
    return `<p class="project-state-warning">Showing ${systemMapNumber(t.limit)} of ${systemMapNumber(t.available)} ${what} in this view. Refocus, search or filter to explore the rest.</p>`;
  }).join('');
}

function systemMapLabels() { return systemMapState.data?.labels || {}; }
function systemMapLaneLabel(id) {
  const lane = (systemMapLabels().lanes || []).find(l => l.id === id);
  return lane ? visualLabel(lane) : String(id || '');
}
function systemMapTypeLabel(node) {
  return visualLabel(node.presentation_type) || node.type;
}
function systemMapRelationshipLabel(classification) {
  const pair = (systemMapLabels().relationships || {})[classification];
  return pair ? visualLabel(pair) : String(classification || '').replaceAll('_', ' ');
}
function systemMapLaneOf(node) {
  if (node.lane) return node.lane;
  if (node.layer === 'DATABASE') return ['TABLE', 'VIEW', 'SEQUENCE_REFERENCE'].includes(node.type) ? 'DATA' : 'SHARED_LOGIC';
  return systemMapLaneFallback[node.layer] || 'INTEGRATION';
}

// Positions come from the server. A response without a layout (a 2.1 server)
// is placed in lane columns in the order it arrived; nothing is invented.
function systemMapGeometry(d) {
  const layout = d.layout;
  if (layout && layout.positions) {
    // Coerced once here: every SVG attribute below is built from these numbers.
    const positions = {};
    Object.entries(layout.positions).forEach(([id, p]) => { positions[id] = { x: Number(p.x) || 0, y: Number(p.y) || 0 }; });
    return { positions, columns: layout.columns || [], w: Number(layout.node_width) || 184, h: Number(layout.node_height) || 54, width: Number(layout.width) || 900, height: Number(layout.height) || 480, cycles: new Set(layout.cycle_nodes || []) };
  }
  const lanes = ['APPLICATION', 'SHARED_LOGIC', 'DATA', 'INTEGRATION'], positions = {}, rows = [0, 0, 0, 0];
  d.nodes.forEach(n => { const c = Math.max(0, lanes.indexOf(systemMapLaneOf(n))); positions[n.id] = { x: 28 + c * 248, y: 68 + rows[c]++ * 68 }; });
  const columns = lanes.map((id, c) => ({ id, label: id, x: 28 + c * 248, width: 184, count: rows[c] }));
  return { positions, columns, w: 184, h: 54, width: 28 * 2 + 4 * 248 - 64, height: Math.max(480, 96 + Math.max(...rows) * 68), cycles: new Set() };
}

// Emphasis from the lens, the highlighted lane and the in-map search. Null means "no dimming".
function systemMapEmphasis(d) {
  const sets = [];
  const lens = systemMapState.lens;
  const touching = test => {
    const nodes = new Set(), edges = new Set();
    d.edges.forEach(e => { if (test(e)) { edges.add(e.id); nodes.add(e.source); nodes.add(e.target); } });
    return { nodes, edges };
  };
  if (lens === 'DATA_ACCESS' || lens === 'SHARED_LOGIC') {
    const kinds = lens === 'DATA_ACCESS' ? ['READS', 'WRITES'] : ['CALLS', 'SHARES_STATE', 'DUPLICATES_LOGIC'];
    const lane = lens === 'DATA_ACCESS' ? 'DATA' : 'SHARED_LOGIC';
    const found = touching(e => kinds.includes(e.classification));
    d.nodes.forEach(n => { if (systemMapLaneOf(n) === lane) found.nodes.add(n.id); });
    sets.push(found);
  } else if (lens === 'HOTSPOTS') {
    const found = touching(e => e.is_hotspot);
    d.nodes.forEach(n => { if (Number(n.hotspot_count) > 0) found.nodes.add(n.id); });
    sets.push(found);
  } else if (lens === 'REVIEW') {
    const nodes = new Set(d.nodes.filter(n => Number(n.review_summary?.open) > 0 || Number(n.review_summary?.stale) > 0).map(n => n.id));
    sets.push({ nodes, edges: new Set(d.edges.filter(e => nodes.has(e.source) || nodes.has(e.target)).map(e => e.id)) });
  }
  if (systemMapState.lane) {
    const nodes = new Set(d.nodes.filter(n => systemMapLaneOf(n) === systemMapState.lane).map(n => n.id));
    sets.push({ nodes, edges: new Set(d.edges.filter(e => nodes.has(e.source) && nodes.has(e.target)).map(e => e.id)) });
  }
  const query = systemMapState.query.trim().toLocaleLowerCase();
  if (query) {
    const nodes = new Set(d.nodes.filter(n => String(n.name).toLocaleLowerCase().includes(query)).map(n => n.id));
    sets.push({ nodes, edges: new Set(d.edges.filter(e => nodes.has(e.source) || nodes.has(e.target)).map(e => e.id)) });
  }
  if (!sets.length) return null;
  return sets.reduce((a, b) => ({ nodes: new Set([...a.nodes].filter(x => b.nodes.has(x))), edges: new Set([...a.edges].filter(x => b.edges.has(x))) }));
}

function systemMapSearchMatches(d) {
  const query = systemMapState.query.trim().toLocaleLowerCase();
  return query ? d.nodes.filter(n => String(n.name).toLocaleLowerCase().includes(query)) : [];
}

function systemMapEdgePath(s, t, w, h) {
  const sy = s.y + h / 2, ty = t.y + h / 2;
  if (t.x >= s.x + w) { const x1 = s.x + w, x2 = t.x, dx = Math.max(32, (x2 - x1) * 0.45); return `M ${x1} ${sy} C ${x1 + dx} ${sy}, ${x2 - dx} ${ty}, ${x2} ${ty}`; }
  if (t.x + w <= s.x) { const x1 = s.x, x2 = t.x + w, dx = Math.max(32, (x1 - x2) * 0.45); return `M ${x1} ${sy} C ${x1 - dx} ${sy}, ${x2 + dx} ${ty}, ${x2} ${ty}`; }
  // Same column: loop out to the right so the curve never crosses the cards.
  const x = s.x + w, bend = x + 36 + Math.min(60, Math.abs(ty - sy) * 0.15);
  return `M ${x} ${sy} C ${bend} ${sy}, ${bend} ${ty}, ${x} ${ty}`;
}

function systemMapSvg(d) {
  const g = systemMapGeometry(d), emphasis = systemMapEmphasis(d), zoom = systemMapState.zoom;
  const focus = systemMapState.view === 'FOCUS' ? (systemMapState.focus || d.focus) : null;
  const names = new Map(d.nodes.map(n => [n.id, n.name]));
  const trim = (text, max) => { const s = String(text ?? ''); return s.length > max ? s.slice(0, max - 1) + '…' : s; };
  const columns = g.columns.map(c => {
    const label = d.layout?.mode === 'FOCUS' ? c.label : systemMapLaneLabel(c.id);
    return `<g class="visual-map-column-group"><rect class="visual-map-lane" data-lane="${esc(c.id)}" x="${Number(c.x) - 10}" y="18" width="${Number(c.width) + 20}" height="${g.height - 28}" rx="10" /><text class="visual-map-column" x="${Number(c.x)}" y="44">${esc(trim(label, 34))} · ${Number(c.count)}</text></g>`;
  }).join('');
  const edges = d.edges.map(e => {
    const s = g.positions[e.source], t = g.positions[e.target];
    if (!s || !t) return '';
    const path = systemMapEdgePath(s, t, g.w, g.h);
    const width = Math.min(4, 1.2 + Math.log2(Math.max(1, Number(e.count) || 1)) * 0.6).toFixed(2);
    const classes = ['map-edge', 'visual-map-edge', `edge-${esc(String(e.classification).toLowerCase())}`,
      e.is_hotspot ? 'is-hotspot' : '', e.level && e.level !== 'FACT' ? 'is-candidate' : '',
      systemMapState.selectedEdge?.id === e.id ? 'is-selected' : '', emphasis && !emphasis.edges.has(e.id) ? 'is-dim' : ''].filter(Boolean).join(' ');
    // Pointer shortcut only; the relationship table below is the keyboard and screen-reader path.
    return `<g class="${classes}" data-edge-id="${esc(e.id)}" aria-hidden="true"><title>${esc(names.get(e.source) || e.source_name)} ${esc(systemMapRelationshipLabel(e.classification))} ${esc(names.get(e.target) || e.target_name)} (${Number(e.count)})</title><path class="visual-map-hit" d="${path}" /><path class="visual-map-line" d="${path}" stroke-width="${width}" marker-end="url(#visual-map-arrow)" /></g>`;
  }).join('');
  const nodes = d.nodes.map(n => {
    const p = g.positions[n.id];
    if (!p) return '';
    const hotspots = Number(n.hotspot_count) || 0, findings = Number(n.findings_count) || 0, cycle = g.cycles.has(n.id);
    const classes = ['map-node', 'visual-map-node', n.id === focus ? 'is-focus' : '', systemMapState.selectedNode?.id === n.id ? 'is-selected' : '',
      n.unresolved || n.layer === 'UNRESOLVED' ? 'is-unresolved' : '', n.status === 'CANDIDATE' ? 'is-candidate' : '', emphasis && !emphasis.nodes.has(n.id) ? 'is-dim' : ''].filter(Boolean).join(' ');
    const review = n.review_summary || {};
    const meta = systemMapState.lens === 'REVIEW' && Number(review.total) > 0
      ? `${Number(review.open)} open · ${Number(review.stale)} stale · ${Number(review.decided)} decided`
      : `${systemMapTypeLabel(n)} · ${findings} ${findings === 1 ? 'finding' : 'findings'}`;
    const label = [n.name, systemMapTypeLabel(n), systemMapLaneLabel(systemMapLaneOf(n)), `${findings} findings`, n.highest_risk && n.highest_risk !== 'NONE' ? `highest risk ${n.highest_risk}` : '', hotspots ? `${hotspots} hotspot candidates` : '',
      n.unresolved || n.layer === 'UNRESOLVED' ? 'unresolved reference' : '', n.status === 'CANDIDATE' ? 'candidate, not observed structure' : '', cycle ? 'in a cycle with the focus' : '', n.id === focus ? 'focus' : ''].filter(Boolean).join(', ');
    const badge = hotspots ? `<g class="visual-map-badge" transform="translate(${g.w - 38},6)"><rect width="32" height="16" rx="3" /><text x="16" y="12" text-anchor="middle">◆ ${hotspots}</text></g>` : '';
    return `<g class="${classes}" data-node-id="${esc(n.id)}" tabindex="0" role="button" aria-label="${esc(label)}" transform="translate(${Number(p.x)},${Number(p.y)})"><title>${esc(n.name)}</title><rect class="visual-map-card" data-risk="${esc(n.highest_risk || n.risk || 'NONE')}" width="${g.w}" height="${g.h}" rx="8" /><text class="visual-map-name" x="10" y="21">${cycle ? '↻ ' : ''}${esc(trim(n.name, hotspots ? 20 : 24))}</text><text class="visual-map-meta" x="10" y="40">${esc(trim(meta, 30))}</text>${badge}</g>`;
  }).join('');
  const described = `System Map, ${d.view === 'ESTATE' ? 'whole estate by lane' : 'focus view'}: ${d.nodes.length} nodes and ${d.edges.length} relationships. Tab moves between nodes, arrow keys move within the map, Enter inspects. The relationship table lists the same content.`;
  return `<svg id="system-map-svg" class="project-system-map-svg visual-map-svg" viewBox="0 0 ${g.width} ${g.height}" style="width:${Math.round(g.width * zoom)}px;height:${Math.round(g.height * zoom)}px" role="group" aria-label="${esc(described)}"><defs><marker id="visual-map-arrow" viewBox="0 0 8 8" refX="8" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path class="visual-map-arrowhead" d="M0,0 L8,4 L0,8 z" /></marker></defs>${columns}${edges}${nodes}</svg>`;
}

// A small overview of the whole layout; the rectangle is the visible part.
function systemMapMinimap(d) {
  const g = systemMapGeometry(d), scale = 160 / Math.max(1, g.width), height = Math.max(40, Math.round(g.height * scale));
  const dots = d.nodes.map(n => { const p = g.positions[n.id]; return p ? `<rect data-lane="${esc(systemMapLaneOf(n))}" x="${(Number(p.x) * scale).toFixed(1)}" y="${(Number(p.y) * scale).toFixed(1)}" width="${(g.w * scale).toFixed(1)}" height="${Math.max(2, g.h * scale).toFixed(1)}" />` : ''; }).join('');
  return `<svg id="system-map-minimap" class="visual-map-minimap" viewBox="0 0 160 ${height}" width="160" height="${height}" aria-hidden="true" focusable="false">${dots}<rect id="system-map-minimap-view" class="visual-map-minimap-view" x="0" y="0" width="160" height="${height}" /></svg>`;
}

function systemMapLegend() {
  const statuses = systemMapLabels().statuses || {};
  return `<div id="system-map-legend" class="visual-map-legend" ${systemMapState.legend ? '' : 'hidden'}><h4>Legend</h4><ul>
    <li><svg width="36" height="10" aria-hidden="true"><line x1="0" y1="5" x2="36" y2="5" class="visual-legend-line" /></svg> Observed relationship</li>
    <li><svg width="36" height="10" aria-hidden="true"><line x1="0" y1="5" x2="36" y2="5" class="visual-legend-line is-candidate" /></svg> Inferred relationship (candidate)</li>
    <li><svg width="36" height="10" aria-hidden="true"><line x1="0" y1="5" x2="36" y2="5" class="visual-legend-line is-hotspot" /></svg> Linked to a hotspot candidate</li>
    <li><svg width="36" height="16" aria-hidden="true"><rect x="1" y="1" width="34" height="14" rx="3" class="visual-legend-node is-unresolved" /></svg> Referenced but not found in the supplied sources</li>
    <li><svg width="36" height="16" aria-hidden="true"><rect x="1" y="1" width="34" height="14" rx="3" class="visual-legend-node is-candidate" /></svg> Engine-derived candidate (for example a business rule candidate), not observed structure</li>
    <li><span class="visual-legend-badge">◆ n</span> Hotspot candidates on the node</li>
    <li><span class="visual-legend-badge">↻</span> Reaches the focus and is reached from it (a cycle)</li>
    <li>Node border: highest risk of the node's findings</li>
  </ul><p>${Object.keys(visualStatusText).map(s => `${visualStatus(s, statuses[s])} ${esc(statuses[s] || '')}`).join('<br>')}</p></div>`;
}

function systemMapToolbar(d) {
  const forms = d?.available_forms || [];
  const focus = systemMapState.focus || '';
  const focusNode = d?.nodes?.find(n => n.id === focus);
  const extra = focus && focusNode && !forms.some(f => f.id === focus) ? `<option value="${esc(focus)}" selected>${esc(focusNode.name)}</option>` : '';
  const layers = d?.layers || Object.keys(systemMapLayerLabels);
  const relationships = d?.relationships || ['CALLS', 'READS', 'WRITES', 'OPENS_FORM', 'SHARES_STATE', 'DUPLICATES_LOGIC', 'REFERENCES'];
  const estate = systemMapState.view === 'ESTATE';
  return `<div class="visual-map-toolbar" role="toolbar" aria-label="System Map controls">
      <label for="system-map-search">Find in this view<input id="system-map-search" type="search" value="${esc(systemMapState.query)}" placeholder="Node name" autocomplete="off"></label>
      <label for="system-map-view">View<select id="system-map-view"><option value="ESTATE" ${estate ? 'selected' : ''}>Whole estate by lane</option><option value="FOCUS" ${estate ? '' : 'selected'}>Focus on one node</option></select></label>
      <label for="system-map-focus">Focus Form<select id="system-map-focus">${estate || !focus ? '<option value="">Choose a Form…</option>' : ''}${extra}${forms.map(f => `<option value="${esc(f.id)}" ${!estate && f.id === focus ? 'selected' : ''}>${esc(f.name)}</option>`).join('')}</select></label>
      <label for="system-map-depth">Depth<select id="system-map-depth" ${estate ? 'disabled' : ''}>${[1, 2, 3, 4, 5].map(n => `<option value="${n}" ${systemMapState.depth === n ? 'selected' : ''}>${n} ${n === 1 ? 'hop' : 'hops'}</option>`).join('')}</select></label>
      <label for="system-map-lens">Lens<select id="system-map-lens">${Object.entries(systemMapLenses).map(([id, [label]]) => `<option value="${id}" ${systemMapState.lens === id ? 'selected' : ''}>${label}</option>`).join('')}</select></label>
      <label for="system-map-edge">Relationship<select id="system-map-edge"><option value="">All relationships</option>${relationships.map(r => `<option value="${esc(r)}" ${systemMapState.edge_type === r ? 'selected' : ''}>${esc(systemMapRelationshipLabel(r))}</option>`).join('')}</select></label>
      <label for="system-map-layer">Layer<select id="system-map-layer"><option value="">All layers</option>${layers.map(l => `<option value="${esc(l)}" ${systemMapState.layer === l ? 'selected' : ''}>${esc(systemMapLayerLabels[l] || l)}</option>`).join('')}</select></label>
      <div class="visual-map-toolbar-actions">${projectButton('system-map-fit', 'Fit')}${projectButton('system-map-reset', 'Reset')}<button type="button" class="btn" id="system-map-legend-toggle" aria-expanded="${systemMapState.legend}" aria-controls="system-map-legend">Legend</button>${projectButton('system-map-refresh', 'Refresh Map')}${visualModeToggle()}</div>
    </div>`;
}

function systemMapInspectorIntro(d) {
  return `<h4>Architecture inspector</h4><p>${esc(d.description || '')}</p><p>Select a node or relationship, or use the table below.</p><p><b>Nodes shown:</b> ${systemMapNumber(d.total_nodes)} of ${systemMapNumber(d.reachable_nodes ?? d.total_nodes)} ${d.view === 'ESTATE' ? 'in this view' : 'reachable'} (${systemMapNumber(d.total_estate_nodes)} in the estate)</p><p><b>Relationships shown:</b> ${systemMapNumber(d.total_edges)} of ${systemMapNumber(d.available_edges ?? d.total_edges)}</p>`;
}

function systemMapSection(title, body) { return `<section class="visual-drawer-section"><h5>${title}</h5>${body}</section>`; }

function systemMapNodeDrawer(d, n) {
  const detail = systemMapState.detail.id === n.id ? systemMapState.detail : null;
  const info = detail?.data, review = n.review_summary || {}, findings = Number(n.findings_count) || 0, hotspots = Number(n.hotspot_count) || 0;
  const g = systemMapGeometry(d), unresolved = n.unresolved || n.layer === 'UNRESOLVED';
  const isFocus = systemMapState.view === 'FOCUS' && n.id === (systemMapState.focus || d.focus);
  const relList = rel => Object.entries(rel || {}).map(([k, v]) => `<li>${esc(systemMapRelationshipLabel(k))} <b>${Number(v)}</b></li>`).join('') || '<li>None observed</li>';
  const architecture = `<p>${Number(n.fan_in)} incoming · ${Number(n.fan_out)} outgoing relationships</p>${info ? `<div class="visual-two visual-drawer-rel"><div><b>Incoming</b><ul>${relList(info.relationships?.inbound)}</ul></div><div><b>Outgoing</b><ul>${relList(info.relationships?.outbound)}</ul></div></div>` : ''}${g.cycles.has(n.id) ? '<p>Reaches the focus and is reached from it: a cycle.</p>' : ''}`;
  const hotspotList = info?.hotspots?.length ? `<ul class="visual-drawer-list">${info.hotspots.map(h => `<li>${visualStatus('CANDIDATE')} ${esc(h.title)} <span>${esc(h.severity)}</span></li>`).join('')}</ul>${info.hotspots_total > info.hotspots.length ? `<p class="project-muted">Showing ${info.hotspots.length} of ${Number(info.hotspots_total)}.</p>` : ''}` : '';
  const attention = `<p><b>Findings:</b> ${findings}${findings ? ` · highest risk ${esc(n.highest_risk)}` : ''}</p><p><b>Hotspot candidates:</b> ${hotspots}</p>${hotspotList}${hotspots ? '<p class="project-muted">Candidates need architecture review; they are not verdicts.</p>' : ''}`;
  const reviewBody = Number(review.total) > 0
    ? `<p>${visualStatus('DECIDED')} ${Number(review.decided)} of ${Number(review.total)} findings decided</p><p>${visualStatus('PROPOSED')} ${Number(review.open)} still proposals${Number(review.stale) ? ` · ${Number(review.stale)} need revalidation` : ''}${Number(review.deferred) ? ` · ${Number(review.deferred)} deferred` : ''}</p><p class="project-muted">Review status, not migration readiness.</p>`
    : '<p>No findings on this node, so nothing to decide here.</p>';
  let evidence = '<p class="project-muted">The map never shows source text. Evidence stays in Review and Inventory.</p>';
  if (detail?.error) evidence = `<p class="project-state-warning">Details are unavailable: ${esc(detail.error)}</p>` + evidence;
  else if (!info) evidence = '<p>Loading findings…</p>' + evidence;
  else if (info.findings?.length) evidence = `<ul class="visual-drawer-list">${info.findings.map(f => `<li><button type="button" class="visual-card-link" data-map-finding="${esc(f.id)}">${esc(f.name)}</button><span>${esc(f.risk)} · ${esc((typeof projectReviewStates === 'object' && projectReviewStates[f.review_state]) || f.review_state)}</span></li>`).join('')}</ul>${info.findings_total > info.findings.length ? `<p class="project-muted">Showing ${info.findings.length} of ${Number(info.findings_total)} findings.</p>` : ''}` + evidence;
  const actions = `<div class="project-actions visual-drawer-actions">${isFocus ? '' : `<button class="btn primary" id="system-map-set-focus" data-focus-id="${esc(n.id)}">Focus System Map Here</button>`}${typeof visualModuleOpen === 'function' && n.type === 'FORM' ? `<button class="btn" id="system-map-module-360" data-node="${esc(n.id)}">Open Module 360</button>` : ''}${findings && n.module ? `<button class="btn" id="system-map-view-findings" data-module="${esc(n.module)}">View Findings</button>` : ''}<button class="btn" id="system-map-view-inventory" data-node-name="${esc(n.name)}" data-node-layer="${esc(n.layer)}" data-node-type="${esc(n.type)}">View in Inventory</button></div>`;
  const identity = `<dl class="visual-drawer-facts"><div><dt>Type</dt><dd>${esc(systemMapTypeLabel(n))}</dd></div><div><dt>Lane</dt><dd>${esc(systemMapLaneLabel(systemMapLaneOf(n)))}</dd></div>${n.module ? `<div class="visual-technical-only"><dt>Module</dt><dd>${esc(n.module)}</dd></div>` : ''}<div><dt>Components folded in</dt><dd>${Number(n.members) || 0}</dd></div></dl>${unresolved ? '<p>Not found in the supplied sources. Supply its definition to resolve it.</p>' : ''}`;
  return `<h4>${esc(n.name)}</h4><p>${visualStatus(unresolved ? 'UNRESOLVED' : 'OBSERVED')} ${esc(systemMapTypeLabel(n))}</p>${systemMapSection('Identity', identity)}${systemMapSection('Architecture', architecture)}${systemMapSection('Modernization attention', attention)}${systemMapSection('Review', reviewBody)}${systemMapSection('Evidence', evidence)}${systemMapSection('Actions', actions)}`;
}

function systemMapEdgeDrawer(d, e) {
  const names = new Map(d.nodes.map(n => [n.id, n.name]));
  const source = names.get(e.source) || e.source_name, target = names.get(e.target) || e.target_name;
  const identity = `<p><b>${esc(source)}</b> ${esc(systemMapRelationshipLabel(e.classification))} <b>${esc(target)}</b></p><div class="project-actions visual-drawer-actions"><button type="button" class="btn" data-map-select="${esc(e.source)}">Select ${esc(source)}</button><button type="button" class="btn" data-map-select="${esc(e.target)}">Select ${esc(target)}</button></div>`;
  const architecture = `<p>${Number(e.count)} observed relationship(s) · evidence level ${esc(e.level)}</p><p class="visual-technical-only"><b>Blueprint relationship types:</b> ${(e.relationships || []).map(esc).join(', ')}</p>`;
  const attention = e.is_hotspot ? `<p class="project-state-warning">Linked to ${Number((e.hotspot_ids || []).length)} hotspot candidate(s). Candidates need architecture review; they are not verdicts.</p>` : '<p>Not linked to a hotspot candidate.</p>';
  const evidence = `${e.components?.length ? `<p><b>From components:</b> ${e.components.map(esc).join(', ')}</p>` : ''}<p class="project-muted">${Number((e.evidence || e.evidence_refs || []).length)} evidence record(s) sampled. Open the Form in Review for source-level evidence.</p>`;
  const actions = `<div class="project-actions visual-drawer-actions"><button class="btn" data-map-focus="${esc(e.source)}">Focus on ${esc(source)}</button><button class="btn" data-map-focus="${esc(e.target)}">Focus on ${esc(target)}</button></div>`;
  return `<h4>Relationship evidence</h4><p>${visualStatus(e.status || (e.level === 'FACT' ? 'OBSERVED' : 'CANDIDATE'))} ${esc(systemMapRelationshipLabel(e.classification))}</p>${systemMapSection('Identity', identity)}${systemMapSection('Architecture', architecture)}${systemMapSection('Modernization attention', attention)}${systemMapSection('Review', '<p>Relationships are not decided directly; decisions are recorded on the findings of either module.</p>')}${systemMapSection('Evidence', evidence)}${systemMapSection('Actions', actions)}`;
}

function systemMapDrawerHtml(d) {
  if (!d) return '<p>Loading details…</p>';
  if (!d.nodes || !d.nodes.length) return '<p>Select a different focus or loosen the filters.</p>';
  if (systemMapState.selectedEdge) return systemMapEdgeDrawer(d, systemMapState.selectedEdge);
  if (systemMapState.selectedNode) return systemMapNodeDrawer(d, systemMapState.selectedNode);
  return systemMapInspectorIntro(d);
}

function systemMapTable(d) {
  const names = new Map(d.nodes.map(n => [n.id, n.name]));
  return `<details class="visual-map-table" id="system-map-table"><summary>Relationship table (${d.edges.length}): the same content as the map, for keyboard and screen-reader review</summary><div class="project-table-wrap"><table class="project-table"><caption>Relationships shown in the map</caption><thead><tr><th scope="col">Source</th><th scope="col">Relationship</th><th scope="col">Target</th><th scope="col">Observations</th><th scope="col">Inspect</th></tr></thead><tbody>${d.edges.map(e => `<tr><td>${esc(names.get(e.source) || e.source_name)}</td><td>${esc(systemMapRelationshipLabel(e.classification))}${e.is_hotspot ? ' · hotspot candidate' : ''}${e.level && e.level !== 'FACT' ? ' · inferred' : ''}</td><td>${esc(names.get(e.target) || e.target_name)}</td><td>${Number(e.count)}</td><td><button type="button" class="btn" data-edge-inspect="${esc(e.id)}">Inspect</button></td></tr>`).join('')}</tbody></table></div></details>`;
}

function systemMapNotes(d) {
  const lane = systemMapState.lane ? `<p class="visual-map-note">Highlighting the ${esc(systemMapLaneLabel(systemMapState.lane))} lane. <button type="button" class="btn" id="system-map-clear-lane">Show every lane equally</button></p>` : '';
  const lens = systemMapState.lens !== 'ARCHITECTURE' ? `<p class="visual-map-note"><b>${esc(systemMapLenses[systemMapState.lens]?.[0] || '')} lens.</b> ${esc(systemMapLenses[systemMapState.lens]?.[1] || '')}</p>` : '';
  const focusNode = systemMapState.view === 'FOCUS' ? d?.nodes?.find(n => n.id === (systemMapState.focus || d.focus)) : null;
  const focus = focusNode ? `<p class="visual-map-note">Focus: <b>${esc(focusNode.name)}</b>. What reaches it is on the left; what it reaches is on the right.</p>` : '';
  return `${d ? systemMapTruncation(d) : ''}${focus}${lane}${lens}`;
}

function renderProjectSystemMap() {
  const d = systemMapState.data;
  const canvas = $('system-map-canvas');
  const scroll = canvas ? { left: canvas.scrollLeft || 0, top: canvas.scrollTop || 0 } : null;
  let stage;
  if (!d) stage = '<p style="padding:24px;">Loading system architecture map…</p>';
  else if (!d.nodes || !d.nodes.length) stage = '<p style="padding:24px;">No architecture nodes match the current view and filters.</p>';
  else stage = `<div id="system-map-svg-host">${systemMapSvg(d)}</div>`;
  const controls = d && d.nodes?.length ? `<div class="visual-map-controls" role="group" aria-label="Zoom and pan">${projectButton('system-map-zoom-out', '−', false, 'Zoom out')}${projectButton('system-map-zoom-in', '+', false, 'Zoom in')}${projectButton('system-map-pan-left', '←', false, 'Pan left')}${projectButton('system-map-pan-up', '↑', false, 'Pan up')}${projectButton('system-map-pan-down', '↓', false, 'Pan down')}${projectButton('system-map-pan-right', '→', false, 'Pan right')}</div>${systemMapMinimap(d)}` : '';
  const hint = '<p class="visual-map-hint">Drag or use the arrow buttons to pan; Ctrl + mouse wheel zooms. The wheel alone scrolls the page.</p>';
  $('project-content').innerHTML = `${projectSectionNav('system-map')}<header>${visualBackButton()}<h2 id="project-step-title" tabindex="-1">System Map</h2><p>Module-level architecture: each Form includes its blocks, items, triggers and program units; each package includes its subprograms. Containment is not drawn as a dependency.</p></header>${systemMapToolbar(d)}<p id="system-map-search-status" class="visual-map-hint" aria-live="polite"></p>${systemMapLegend()}${systemMapNotes(d)}<div class="project-system-map-split"><div class="visual-map-stage"><div class="project-system-map-canvas visual-map-canvas" id="system-map-canvas">${stage}</div>${controls}${hint}</div><aside class="system-map-drawer" id="system-map-drawer" aria-label="System map inspector" aria-live="polite">${systemMapDrawerHtml(d)}</aside></div>${d && d.edges?.length ? systemMapTable(d) : ''}`;
  projectBindSectionNav();
  visualBindBack();
  systemMapBind();
  const fresh = $('system-map-canvas');
  if (scroll && fresh) { fresh.scrollLeft = scroll.left; fresh.scrollTop = scroll.top; }
  systemMapUpdateMinimap();
}

// Redraw only the drawing (search, lens, zoom): the toolbar keeps its focus.
function systemMapRedraw() {
  const d = systemMapState.data, host = $('system-map-svg-host');
  if (!d || !d.nodes?.length || !host) return;
  host.innerHTML = systemMapSvg(d);
  systemMapBindCanvas();
  systemMapUpdateMinimap();
}

function systemMapRenderDrawer() {
  const drawer = $('system-map-drawer');
  if (!drawer) return;
  drawer.innerHTML = systemMapDrawerHtml(systemMapState.data);
  systemMapBindDrawer();
}

function systemMapNodeElement(id) {
  const canvas = $('system-map-canvas');
  return canvas ? [...canvas.querySelectorAll('[data-node-id]')].find(el => el.dataset.nodeId === id) || null : null;
}

function systemMapSelectNode(id, keepFocus = true) {
  const d = systemMapState.data, n = d?.nodes?.find(x => x.id === id);
  if (!n) return;
  systemMapState.selectedNode = n; systemMapState.selectedEdge = null;
  systemMapRedraw(); systemMapRenderDrawer();
  if (keepFocus) systemMapNodeElement(id)?.focus?.();
  systemMapLoadDetail(id);
}

function systemMapSelectEdge(id) {
  const e = systemMapState.data?.edges?.find(x => x.id === id);
  if (!e) return;
  systemMapState.selectedEdge = e; systemMapState.selectedNode = null;
  systemMapRedraw(); systemMapRenderDrawer();
}

// Drawer detail is bound to the project, the analysis revision and the node that asked for it.
async function systemMapLoadDetail(id) {
  const c = projectContext(), detail = systemMapState.detail, revision = systemMapState.data?.analysis_revision;
  if (detail.id === id && detail.revision === revision && (detail.data || detail.error)) return;
  const request = ++detail.request;
  Object.assign(detail, { id, revision, data: null, error: null });
  try {
    const data = await api(`/api/v2/projects/${encodeURIComponent(c.id)}/system-map/node?id=${encodeURIComponent(id)}`);
    if (!projectCurrent(c) || request !== detail.request) return;
    detail.data = data;
  } catch (e) {
    if (!projectCurrent(c) || request !== detail.request) return;
    detail.error = e.message;
  }
  if (projectUI.view === 'system-map' && systemMapState.selectedNode?.id === id) systemMapRenderDrawer();
}

function systemMapFocusOn(id) {
  Object.assign(systemMapState, { view: 'FOCUS', focus: id, selectedNode: null, selectedEdge: null });
  renderProjectSystemMap();
  return loadProjectSystemMap();
}

function systemMapSetZoom(zoom) {
  const canvas = $('system-map-canvas'), before = systemMapState.zoom;
  systemMapState.zoom = Math.max(systemMapZoomSteps[0], Math.min(systemMapZoomSteps[systemMapZoomSteps.length - 1], zoom));
  if (canvas && canvas.clientWidth) {
    // Keep the centre of the visible area where it was.
    const ratio = systemMapState.zoom / before;
    const cx = (canvas.scrollLeft + canvas.clientWidth / 2) * ratio, cy = (canvas.scrollTop + canvas.clientHeight / 2) * ratio;
    systemMapRedraw();
    canvas.scrollLeft = cx - canvas.clientWidth / 2; canvas.scrollTop = cy - canvas.clientHeight / 2;
  } else systemMapRedraw();
  systemMapUpdateMinimap();
}

function systemMapZoomStep(direction) {
  const z = systemMapState.zoom;
  const next = direction > 0 ? systemMapZoomSteps.find(s => s > z + 1e-6) : [...systemMapZoomSteps].reverse().find(s => s < z - 1e-6);
  if (next) systemMapSetZoom(next);
}

function systemMapFit() {
  const d = systemMapState.data, canvas = $('system-map-canvas');
  if (!d || !d.nodes?.length) return;
  const g = systemMapGeometry(d);
  const width = canvas?.clientWidth || 900, height = canvas?.clientHeight || 560;
  systemMapState.zoom = Math.max(0.1, Math.min(1, (width - 16) / g.width, (height - 16) / g.height));
  systemMapRedraw();
  if (canvas) { canvas.scrollLeft = 0; canvas.scrollTop = 0; }
  systemMapUpdateMinimap();
}

function systemMapCenterOn(id) {
  const d = systemMapState.data, canvas = $('system-map-canvas');
  if (!d || !canvas) return;
  const g = systemMapGeometry(d), p = g.positions[id], zoom = systemMapState.zoom;
  if (!p) return;
  canvas.scrollLeft = Math.max(0, (p.x + g.w / 2) * zoom - (canvas.clientWidth || 0) / 2);
  canvas.scrollTop = Math.max(0, p.y * zoom - 48);
  systemMapUpdateMinimap();
}

function systemMapPan(dx, dy) {
  const canvas = $('system-map-canvas');
  if (!canvas) return;
  const reduce = !!window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches;
  const left = (canvas.scrollLeft || 0) + dx * (canvas.clientWidth || 600) * 0.4, top = (canvas.scrollTop || 0) + dy * (canvas.clientHeight || 400) * 0.4;
  if (canvas.scrollTo) canvas.scrollTo({ left, top, behavior: reduce ? 'auto' : 'smooth' });
  else { canvas.scrollLeft = left; canvas.scrollTop = top; }
}

function systemMapUpdateMinimap() {
  const d = systemMapState.data, canvas = $('system-map-canvas'), view = $('system-map-minimap-view');
  if (!d || !d.nodes?.length || !canvas || !view || !canvas.clientWidth) return;
  const g = systemMapGeometry(d), scale = 160 / Math.max(1, g.width) / systemMapState.zoom;
  view.setAttribute('x', (canvas.scrollLeft * scale).toFixed(1));
  view.setAttribute('y', (canvas.scrollTop * scale).toFixed(1));
  view.setAttribute('width', Math.min(160, canvas.clientWidth * scale).toFixed(1));
  view.setAttribute('height', (canvas.clientHeight * scale).toFixed(1));
}

// Arrow keys move between nodes: up and down within a column, left and right to the nearest node in the next column.
function systemMapNeighbour(id, key) {
  const d = systemMapState.data, g = systemMapGeometry(d), here = g.positions[id];
  if (!here) return null;
  const all = d.nodes.filter(n => g.positions[n.id]).map(n => ({ id: n.id, ...g.positions[n.id] }));
  let pool;
  if (key === 'ArrowUp' || key === 'ArrowDown') {
    pool = all.filter(p => p.x === here.x && (key === 'ArrowUp' ? p.y < here.y : p.y > here.y));
    pool.sort((a, b) => Math.abs(a.y - here.y) - Math.abs(b.y - here.y));
  } else {
    const xs = [...new Set(all.map(p => p.x))].sort((a, b) => a - b), index = xs.indexOf(here.x);
    const x = xs[index + (key === 'ArrowRight' ? 1 : -1)];
    pool = x === undefined ? [] : all.filter(p => p.x === x).sort((a, b) => Math.abs(a.y - here.y) - Math.abs(b.y - here.y));
  }
  return pool[0]?.id || null;
}

function systemMapBindCanvas() {
  const canvas = $('system-map-canvas');
  if (!canvas) return;
  canvas.querySelectorAll('[data-node-id]').forEach(el => {
    el.onclick = () => systemMapSelectNode(el.dataset.nodeId);
    el.onkeydown = event => {
      if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); systemMapSelectNode(el.dataset.nodeId); }
      else if (event.key.startsWith('Arrow')) { const next = systemMapNeighbour(el.dataset.nodeId, event.key); if (next) { event.preventDefault(); systemMapNodeElement(next)?.focus?.(); } }
    };
  });
  canvas.querySelectorAll('[data-edge-id]').forEach(el => { el.onclick = () => systemMapSelectEdge(el.dataset.edgeId); });
}

function systemMapBindDrawer() {
  const root = $('system-map-drawer');
  if (!root) return;
  const focusBtn = $('system-map-set-focus');
  if (focusBtn) focusBtn.onclick = () => systemMapFocusOn(focusBtn.dataset.focusId);
  const invBtn = $('system-map-view-inventory');
  if (invBtn) invBtn.onclick = () => {
    const layer = invBtn.dataset.nodeLayer, type = invBtn.dataset.nodeType;
    const cat = layer === 'FORM' ? 'forms' : type === 'PACKAGE' ? 'packages' : type === 'TABLE' ? 'tables' : type === 'VIEW' ? 'views' : 'dependencies';
    projectOpenInventory({ category: cat, query: invBtn.dataset.nodeName });
  };
  const findingsBtn = $('system-map-view-findings');
  if (findingsBtn) findingsBtn.onclick = () => projectOpenInventory({ category: 'findings', filters: { module: findingsBtn.dataset.module } });
  const moduleBtn = $('system-map-module-360');
  if (moduleBtn && typeof visualModuleOpen === 'function') moduleBtn.onclick = () => visualModuleOpen({ node: moduleBtn.dataset.node });
  root.querySelectorAll('[data-map-finding]').forEach(el => { el.onclick = () => projectReviewFinding(el.dataset.mapFinding); });
  root.querySelectorAll('[data-map-select]').forEach(el => { el.onclick = () => systemMapSelectNode(el.dataset.mapSelect); });
  root.querySelectorAll('[data-map-focus]').forEach(el => { el.onclick = () => systemMapFocusOn(el.dataset.mapFocus); });
}

function systemMapBind() {
  const d = systemMapState.data;
  const reload = () => { systemMapState.selectedNode = null; systemMapState.selectedEdge = null; renderProjectSystemMap(); loadProjectSystemMap(); };
  $('system-map-view').onchange = () => {
    systemMapState.view = $('system-map-view').value === 'FOCUS' ? 'FOCUS' : 'ESTATE';
    if (systemMapState.view === 'FOCUS' && !systemMapState.focus) systemMapState.focus = d?.available_forms?.[0]?.id || null;
    reload();
  };
  $('system-map-focus').onchange = () => { const value = $('system-map-focus').value; if (!value) return; systemMapState.focus = value; systemMapState.view = 'FOCUS'; reload(); };
  $('system-map-depth').onchange = () => { systemMapState.depth = Number($('system-map-depth').value); reload(); };
  $('system-map-layer').onchange = () => { systemMapState.layer = $('system-map-layer').value; reload(); };
  $('system-map-edge').onchange = () => { systemMapState.edge_type = $('system-map-edge').value; reload(); };
  $('system-map-lens').onchange = () => { systemMapState.lens = systemMapLenses[$('system-map-lens').value] ? $('system-map-lens').value : 'ARCHITECTURE'; renderProjectSystemMap(); $('system-map-lens')?.focus?.(); };
  $('system-map-refresh').onclick = () => loadProjectSystemMap();
  $('system-map-fit').onclick = () => systemMapFit();
  $('system-map-reset').onclick = () => {
    Object.assign(systemMapState, { view: 'ESTATE', focus: null, lane: null, layer: '', edge_type: '', lens: 'ARCHITECTURE', query: '', zoom: 1, layoutKey: null });
    reload();
  };
  $('system-map-legend-toggle').onclick = () => {
    systemMapState.legend = !systemMapState.legend;
    const legend = $('system-map-legend'); if (legend) legend.hidden = !systemMapState.legend;
    $('system-map-legend-toggle').setAttribute('aria-expanded', String(systemMapState.legend));
  };
  const search = $('system-map-search');
  search.oninput = () => {
    systemMapState.query = search.value;
    systemMapRedraw();
    const matches = d ? systemMapSearchMatches(d) : [];
    $('system-map-search-status').textContent = !systemMapState.query.trim() ? '' : matches.length
      ? `${matches.length} ${matches.length === 1 ? 'node matches' : 'nodes match'} in this view. Press Enter to select the first.`
      : 'No node in this view matches. Ctrl+K searches the whole project.';
  };
  search.onkeydown = event => {
    if (event.key !== 'Enter' || !d) return;
    event.preventDefault();
    const first = systemMapSearchMatches(d)[0];
    if (first) systemMapSelectNode(first.id);
  };
  const clearLane = $('system-map-clear-lane');
  if (clearLane) clearLane.onclick = () => { systemMapState.lane = null; renderProjectSystemMap(); };
  visualBindModeToggle($('project-content'));
  if (!d || !d.nodes?.length) return;
  $('system-map-zoom-in').onclick = () => systemMapZoomStep(1);
  $('system-map-zoom-out').onclick = () => systemMapZoomStep(-1);
  $('system-map-pan-left').onclick = () => systemMapPan(-1, 0);
  $('system-map-pan-right').onclick = () => systemMapPan(1, 0);
  $('system-map-pan-up').onclick = () => systemMapPan(0, -1);
  $('system-map-pan-down').onclick = () => systemMapPan(0, 1);
  const canvas = $('system-map-canvas');
  // The wheel scrolls the page as usual; only Ctrl/Cmd + wheel zooms the map.
  canvas.onwheel = event => { if (!(event.ctrlKey || event.metaKey)) return; event.preventDefault(); systemMapZoomStep(event.deltaY < 0 ? 1 : -1); };
  canvas.onscroll = () => systemMapUpdateMinimap();
  let drag = null;
  canvas.onpointerdown = event => {
    if (event.button !== 0 || event.target?.closest?.('[data-node-id],[data-edge-id]')) return;
    drag = { x: event.clientX, y: event.clientY, left: canvas.scrollLeft, top: canvas.scrollTop };
    canvas.classList.add('is-panning'); canvas.setPointerCapture?.(event.pointerId);
  };
  canvas.onpointermove = event => { if (!drag) return; canvas.scrollLeft = drag.left - (event.clientX - drag.x); canvas.scrollTop = drag.top - (event.clientY - drag.y); };
  canvas.onpointerup = canvas.onpointercancel = () => { drag = null; canvas.classList.remove('is-panning'); };
  const minimap = $('system-map-minimap');
  if (minimap) minimap.onclick = event => {
    const box = minimap.getBoundingClientRect?.(); if (!box) return;
    const g = systemMapGeometry(d), scale = g.width * systemMapState.zoom / 160;
    canvas.scrollLeft = (event.clientX - box.left) * scale - canvas.clientWidth / 2;
    canvas.scrollTop = (event.clientY - box.top) * scale - canvas.clientHeight / 2;
  };
  systemMapBindCanvas();
  systemMapBindDrawer();
  $('project-content').querySelectorAll('[data-edge-inspect]').forEach(el => { el.onclick = () => systemMapSelectEdge(el.dataset.edgeInspect); });
}

// ---- 2.2 Return context ----------------------------------------------------
// Cross-navigation remembers where the reader came from, so "Back to …" returns
// to the same map focus, review item or hotspot filter. It is a bounded chain
// held in memory only; the section navigation starts a fresh chain.
visualUI.back = null;
const VISUAL_BACK_DEPTH = 8;

function visualReturnContext() {
  const view = projectUI.view;
  if (view === 'system-map') {
    const focus = systemMapState.view === 'FOCUS' ? systemMapState.data?.nodes?.find(n => n.id === systemMapState.focus) : null;
    return { view, label: focus ? `System Map · ${focus.name}` : 'System Map' };
  }
  if (view === 'review') return { view, label: 'Review' };
  if (view === 'overview') return { view, label: 'Overview' };
  if (view === 'hotspots') return { view, label: 'Hotspots' };
  if (view === 'module-360' && visualUI.module.selector) return { view, label: `Module 360${visualUI.module.data ? ` · ${visualUI.module.data.node.name}` : ''}`, selector: visualUI.module.selector };
  return null;
}

function visualCross(target) {
  const here = visualReturnContext();
  if (!here) { visualUI.back = null; return; }
  let prior = visualUI.back?.target === projectUI.view ? visualUI.back : null, depth = 1;
  for (let p = prior; p; p = p.prior) if (++depth > VISUAL_BACK_DEPTH) { prior = null; break; }
  visualUI.back = { ...here, target, prior };
}

function visualBackButton() {
  const back = visualUI.back;
  return back && back.target === projectUI.view ? `<button type="button" class="btn visual-back" id="visual-back">← Back to ${esc(back.label)}</button>` : '';
}

function visualBindBack() {
  const button = $('visual-back');
  if (button) button.onclick = visualGoBack;
}

function visualGoBack() {
  const back = visualUI.back;
  if (!back) return;
  visualUI.back = back.prior || null;
  if (back.view === 'system-map') projectSystemMapOpen();
  else if (back.view === 'review') projectReviewOpen();
  else if (back.view === 'hotspots') visualHotspotsOpen(null, { remember: false });
  else if (back.view === 'module-360') visualModuleOpen(back.selector, { remember: false });
  else visualOpenOverview();
}

function visualOpenOverview() {
  if (projectUI.overview) { renderProjectOverview(projectUI.overview); return; }
  projectUI.view = 'overview';
  const c = projectContext();
  projectLoadOverview(c, false).then(data => { if (data && projectCurrent(c) && projectUI.view === 'overview') renderProjectOverview(data); });
}

function visualShowOnMap(id) { visualCross('system-map'); projectSystemMapOpen({ focus: id, selectedNode: null, selectedEdge: null }); }

function visualPageHead(title, intro) {
  return `<header class="visual-page-head"><div>${visualBackButton()}<h2 id="project-step-title" tabindex="-1">${title}</h2><p>${intro}</p></div>${visualModeToggle()}</header>`;
}

function visualBindPage() {
  const root = $('project-content');
  projectBindSectionNav();
  visualBindBack();
  visualBindModeToggle(root);
}

// ---- 2.2 Module 360 --------------------------------------------------------
// One module on one page. Every count comes from the saved analysis; the page
// holds names, statuses and counts, never source text.
visualUI.module = { selector: null, data: null, error: null, request: 0 };

function visualModuleSelector(selector) {
  if (typeof selector === 'string') return { module: selector };
  const key = ['module', 'node', 'finding'].find(k => selector && typeof selector[k] === 'string' && selector[k]);
  return key ? { [key]: selector[key] } : null;
}

async function visualModuleOpen(selector, options = {}) {
  const chosen = visualModuleSelector(selector);
  if (!chosen) return;
  if (options.remember !== false) visualCross('module-360');
  projectSaveDraft(); projectEnter('module-360');
  const state = visualUI.module, c = projectContext(), request = ++state.request;
  Object.assign(state, { selector: chosen, data: null, error: null });
  visualRenderModule();
  try {
    const data = await api(`/api/v2/projects/${encodeURIComponent(c.id)}/module-360?${new URLSearchParams(chosen)}`);
    if (!projectCurrent(c) || request !== state.request) return;
    state.data = data;
  } catch (e) {
    if (!projectCurrent(c) || request !== state.request) return;
    state.error = e.message;
  }
  if (projectUI.view === 'module-360') visualRenderModule();
}

function visualNeighbourList(group, direction) {
  const items = group?.items || [];
  if (!items.length) return `<p class="project-muted">${direction === 'inbound' ? 'Nothing in the supplied sources reaches this module.' : 'This module reaches nothing else in the supplied sources.'}</p>`;
  const rows = items.map(n => `<tr><td><b>${esc(n.name)}</b><span class="visual-cell-note">${esc(visualLabel(n.presentation_type) || n.type)}</span></td><td>${esc(visualLabel(n.presentation_label) || n.classification)}${n.is_hotspot ? ' · hotspot candidate' : ''}</td><td>${visualStatus(n.unresolved ? 'UNRESOLVED' : n.status)}</td><td>${Number(n.count)}</td><td><button type="button" class="btn" data-module-map="${esc(n.id)}" aria-label="Show ${esc(n.name)} on the System Map">Map</button>${n.type === 'FORM' ? ` <button type="button" class="btn" data-module-node="${esc(n.id)}" aria-label="Open Module 360 for ${esc(n.name)}">360</button>` : ''}</td></tr>`).join('');
  const more = group.total > items.length ? `<p class="project-muted">Showing ${items.length} of ${Number(group.total)}. Hotspot-linked relationships first; open the System Map focus for the rest.</p>` : '';
  const caption = direction === 'inbound' ? 'What reaches this module' : 'What this module reaches';
  return `<div class="project-table-wrap"><table class="project-table visual-neighbours"><caption>${caption}</caption><thead><tr><th scope="col">Name</th><th scope="col">Relationship</th><th scope="col">Status</th><th scope="col">Observations</th><th scope="col">Open</th></tr></thead><tbody>${rows}</tbody></table></div>${more}`;
}

function visualDistribution(dist, labels = {}) {
  const entries = Object.entries(dist || {});
  return entries.length ? `<dl class="visual-drawer-facts">${entries.map(([k, v]) => `<div><dt>${esc(labels[k] || k)}</dt><dd>${Number(v)}</dd></div>`).join('')}</dl>` : '<p class="project-muted">No findings on this module.</p>';
}

function visualModuleBody(d) {
  const n = d.node || {}, review = n.review_summary || {}, unresolved = n.unresolved || n.layer === 'UNRESOLVED';
  const composition = (d.composition || []).map(c => `<li>${esc(c.type)} <b>${Number(c.count)}</b></li>`).join('');
  const identity = `<p>${visualStatus(unresolved ? 'UNRESOLVED' : 'OBSERVED')} ${esc(visualLabel(n.presentation_type) || n.type)}</p><dl class="visual-drawer-facts"><div><dt>Lane</dt><dd>${esc(systemMapLaneLabel(n.lane))}</dd></div><div class="visual-technical-only"><dt>Module</dt><dd>${esc(d.module || '')}</dd></div><div><dt>Components folded in</dt><dd>${Number(n.members) || 0}</dd></div></dl>${composition ? `<h4>Composition</h4><ul class="visual-drawer-list visual-composition">${composition}</ul>` : ''}`;
  const architecture = `<p>${Number(n.fan_in)} incoming · ${Number(n.fan_out)} outgoing relationships</p><div class="visual-two"><div>${visualNeighbourList(d.neighbours?.inbound, 'inbound')}</div><div>${visualNeighbourList(d.neighbours?.outbound, 'outbound')}</div></div>`;
  const hotspots = (d.hotspots || []).map(h => `<li>${visualStatus('CANDIDATE')} <b>${esc(h.title)}</b> <span>${esc(h.severity)} · ${esc(h.statement)}</span></li>`).join('');
  const attention = `<p><b>Findings:</b> ${Number(d.findings_total)}${d.findings_total ? ` · highest risk ${esc(n.highest_risk)}` : ''}</p>${visualDistribution(d.risk_distribution, typeof projectRiskLabels === 'object' ? projectRiskLabels : {})}<p><b>Hotspot candidates:</b> ${Number(d.hotspots_total)}</p>${hotspots ? `<ul class="visual-drawer-list">${hotspots}</ul><p class="project-muted">Candidates need architecture review; they are not verdicts.</p>` : ''}`;
  const reviewBody = Number(review.total) > 0
    ? `<p>${visualStatus('DECIDED')} ${Number(review.decided)} of ${Number(review.total)} findings decided</p><p>${visualStatus('PROPOSED')} ${Number(review.open)} still proposals${Number(review.stale) ? ` · ${Number(review.stale)} need revalidation` : ''}${Number(review.deferred) ? ` · ${Number(review.deferred)} deferred` : ''}</p><h4>Recommendations proposed</h4>${visualDistribution(d.recommendation_distribution, typeof projectRecommendationLabels === 'object' ? projectRecommendationLabels : {})}<p><b>Business-rule candidates:</b> ${Number(d.business_rule_candidates)}</p><p class="project-muted">Review status, not migration readiness.</p>`
    : '<p>No findings on this module, so nothing to decide here.</p>';
  const findings = (d.findings || []).map(f => `<li><button type="button" class="visual-card-link" data-module-finding="${esc(f.id)}">${esc(f.name)}</button><span>${esc(f.risk)} · ${esc((typeof projectReviewStates === 'object' && projectReviewStates[f.review_state]) || f.review_state)}</span></li>`).join('');
  const evidence = `${findings ? `<ul class="visual-drawer-list">${findings}</ul>` : ''}${d.findings_total > (d.findings || []).length ? `<p class="project-muted">Showing ${(d.findings || []).length} of ${Number(d.findings_total)} findings.</p>` : ''}<p class="project-muted">Module 360 never shows source text. Source-level evidence stays in Review.</p>`;
  const actions = `<div class="project-actions"><button class="btn primary" id="visual-module-map" data-id="${esc(n.id)}">Show on System Map</button>${d.hotspots_total ? '<button class="btn" id="visual-module-hotspots">Explore these hotspots</button>' : ''}${d.findings_total ? '<button class="btn" id="visual-module-findings">View findings in Inventory</button>' : ''}</div>`;
  const section = (id, title, body) => `<section class="visual-panel" aria-labelledby="visual-module-${id}"><h3 id="visual-module-${id}">${title}</h3>${body}</section>`;
  return `<p class="visual-boundary" role="note">${esc(d.boundary || '')}</p><div class="visual-module-grid">${section('identity', 'Identity', identity)}${section('attention', 'Modernization attention', attention)}</div>${section('architecture', 'Architecture', architecture)}<div class="visual-module-grid">${section('review', 'Review', reviewBody)}${section('evidence', 'Evidence', evidence)}</div>${section('actions', 'Actions', actions)}`;
}

function visualRenderModule() {
  const state = visualUI.module, d = state.data;
  let body;
  if (state.error) body = `<p class="project-state-warning" role="status">Module 360 is unavailable: ${esc(state.error)}</p>${state.selector?.module ? '<div class="project-actions"><button class="btn" id="visual-module-inventory">View this module\'s findings in Inventory</button></div>' : ''}`;
  else if (!d) body = '<p aria-live="polite">Loading Module 360…</p>';
  else body = visualModuleBody(d);
  const title = d ? `Module 360 · ${esc(d.node?.name || '')}` : 'Module 360';
  $('project-content').innerHTML = `${projectSectionNav('module-360')}${visualPageHead(title, 'Everything the saved assessment shows about one module: what it contains, what it touches, what needs attention and what has been decided.')}<div id="visual-module-body" aria-live="polite">${body}</div>`;
  visualBindPage();
  const root = $('project-content');
  root.querySelectorAll('[data-module-map]').forEach(el => { el.onclick = () => visualShowOnMap(el.dataset.moduleMap); });
  root.querySelectorAll('[data-module-node]').forEach(el => { el.onclick = () => visualModuleOpen({ node: el.dataset.moduleNode }); });
  root.querySelectorAll('[data-module-finding]').forEach(el => { el.onclick = () => { visualCross('review'); projectReviewFinding(el.dataset.moduleFinding); }; });
  const map = $('visual-module-map');
  if (map && d) map.onclick = () => visualShowOnMap(d.node.id);
  const hot = $('visual-module-hotspots');
  if (hot && d) hot.onclick = () => visualHotspotsOpen({ module: d.module });
  const findings = $('visual-module-findings');
  if (findings && d) findings.onclick = () => projectOpenInventory({ category: 'findings', filters: { module: d.module } });
  const inventory = $('visual-module-inventory');
  if (inventory) inventory.onclick = () => projectOpenInventory({ category: 'findings', filters: { module: state.selector.module } });
}

// ---- 2.2 Hotspot Explorer --------------------------------------------------
// Why each candidate was noticed, and what that evidence cannot prove, side by
// side. Candidates are never verdicts, defects or migration priorities.
visualUI.hotspots = { filters: {}, offset: 0, data: null, error: null, request: 0 };
const VISUAL_HOTSPOT_PAGE = 20;
const VISUAL_NO_MODULE = 'UNKNOWN';

async function visualHotspotsOpen(filters, options = {}) {
  const state = visualUI.hotspots;
  if (options.remember !== false) visualCross('hotspots');
  if (filters) Object.assign(state, { filters: { ...filters }, offset: 0 });
  projectSaveDraft(); projectEnter('hotspots');
  return visualLoadHotspots();
}

async function visualLoadHotspots() {
  const state = visualUI.hotspots, c = projectContext(), request = ++state.request;
  const params = new URLSearchParams({ offset: String(state.offset), limit: String(VISUAL_HOTSPOT_PAGE) });
  for (const key of ['type', 'severity', 'module']) if (state.filters[key]) params.set(key, state.filters[key]);
  Object.assign(state, { error: null });
  visualRenderHotspots();
  try {
    const data = await api(`/api/v2/projects/${encodeURIComponent(c.id)}/hotspots?${params}`);
    if (!projectCurrent(c) || request !== state.request) return;
    state.data = data;
  } catch (e) {
    if (!projectCurrent(c) || request !== state.request) return;
    state.error = e.message; state.data = null;
  }
  if (projectUI.view === 'hotspots') visualRenderHotspots();
}

function visualEvidenceValue(value) {
  if (value && typeof value === 'object' && Array.isArray(value.values)) {
    const more = value.total > value.values.length ? ` (+${Number(value.total) - value.values.length} more)` : '';
    return `${value.values.map(esc).join(', ')}${more}`;
  }
  if (value === null || value === undefined) return 'Not observed';
  return esc(String(value));
}

function visualHotspotCard(h) {
  const evidence = Object.entries(h.evidence || {}).map(([k, v]) => `<div><dt>${esc(k.replaceAll('_', ' '))}</dt><dd>${visualEvidenceValue(v)}</dd></div>`).join('');
  const nodes = (h.nodes || []).map(n => `<li><span>${esc(n.name)} <small>${esc(visualLabel(n.presentation_type) || n.type)}</small></span><span><button type="button" class="btn" data-hotspot-map="${esc(n.id)}" aria-label="Show ${esc(n.name)} on the System Map">Show on map</button>${n.type === 'FORM' ? ` <button type="button" class="btn" data-hotspot-module="${esc(n.id)}" aria-label="Open Module 360 for ${esc(n.name)}">Module 360</button>` : ''}</span></li>`).join('');
  const moreNodes = h.nodes_total > (h.nodes || []).length ? `<p class="project-muted">Showing ${(h.nodes || []).length} of ${Number(h.nodes_total)} places.</p>` : '';
  const review = (h.finding_ids || []).length ? `<button type="button" class="btn" data-hotspot-review="${esc(h.finding_ids[0])}">Review the linked finding${h.finding_ids.length > 1 ? ` (1 of ${h.finding_ids.length})` : ''}</button>` : '';
  return `<article class="visual-hotspot" aria-labelledby="visual-hotspot-${esc(h.id)}">
    <div class="visual-hotspot-head"><h3 id="visual-hotspot-${esc(h.id)}">${esc(h.title)}</h3><p>${visualStatus('CANDIDATE', 'A candidate for architecture review, not a verdict')} <span class="visual-severity" data-severity="${h.severity === 'HIGH' ? 'HIGH' : 'MEDIUM'}">${esc(h.severity)}</span> ${esc(h.label)}${h.module ? ` · ${visualModuleLabel(h.module)}` : ' · across modules'}</p></div>
    <div class="visual-two">
      <section class="visual-why" aria-label="Why FormsLang noticed this"><h4>Why FormsLang noticed this</h4><p>${esc(h.statement)}</p>${evidence ? `<dl class="visual-drawer-facts">${evidence}</dl>` : ''}<p class="project-muted">${Number(h.evidence_count)} evidence record(s) linked.</p></section>
      <section class="visual-not-prove" aria-label="What this does NOT prove"><h4>What this does NOT prove</h4><ul>${(h.uncertainty || []).map(u => `<li>${esc(u)}</li>`).join('')}</ul><p><b>Next step:</b> ${esc(h.recommended_action)}</p></section>
    </div>
    ${nodes ? `<h4>Where it was observed</h4><ul class="visual-hotspot-nodes">${nodes}</ul>${moreNodes}` : ''}
    ${review ? `<div class="project-actions">${review}</div>` : ''}
  </article>`;
}

function visualMatrixLevel(count, max) {
  if (!count) return 0;
  return Math.max(1, Math.min(3, Math.ceil(count * 3 / max)));
}

function visualHotspotMatrix(matrix) {
  if (!matrix || !(matrix.rows || []).length) return '';
  const max = Math.max(1, ...matrix.rows.flatMap(r => r.cells.map(Number)));
  const head = matrix.types.map(t => `<th scope="col">${esc(t.label)}</th>`).join('');
  const rows = matrix.rows.map(r => {
    const single = r.module !== VISUAL_NO_MODULE;
    const label = single ? visualModuleLabel(r.module) : 'Across modules';
    const cells = r.cells.map((count, i) => {
      const n = Number(count), type = matrix.types[i];
      const text = n ? String(n) : '<span aria-label="none">·</span>';
      return `<td data-level="${visualMatrixLevel(n, max)}">${n && single ? `<button type="button" class="visual-card-link" data-matrix-module="${esc(r.module)}" data-matrix-type="${esc(type.id)}" aria-label="${n} ${esc(type.label)} in ${esc(r.module)}">${text}</button>` : text}</td>`;
    }).join('');
    return `<tr><th scope="row">${label}</th>${cells}<td>${Number(r.total)}</td></tr>`;
  }).join('');
  const more = matrix.truncated ? `<p class="project-muted">Showing ${matrix.rows.length} of ${Number(matrix.total_modules)} modules, those with the most candidates first.</p>` : '';
  return `<section class="visual-panel" aria-labelledby="visual-matrix-title"><h3 id="visual-matrix-title">Attention matrix</h3><p>Hotspot candidates per module and type. Counts of candidates, not a ranking of modules.</p><div class="project-table-wrap"><table class="project-table visual-matrix"><caption>Hotspot candidates by module and type</caption><thead><tr><th scope="col">Module</th>${head}<th scope="col">Total</th></tr></thead><tbody>${rows}</tbody></table></div>${more}</section>`;
}

function visualHotspotFilters(d) {
  const f = visualUI.hotspots.filters;
  const types = (d?.types || []).map(t => `<option value="${esc(t.id)}" ${f.type === t.id ? 'selected' : ''}>${esc(t.label)}</option>`).join('');
  const severities = (d?.severities || ['HIGH', 'MEDIUM']).map(s => `<option value="${esc(s)}" ${f.severity === s ? 'selected' : ''}>${esc(s)}</option>`).join('');
  const module = f.module ? `<p class="visual-map-note">Module: <b>${visualModuleLabel(f.module)}</b> <button type="button" class="btn" id="visual-hotspot-clear-module">Show every module</button></p>` : '';
  return `<form id="visual-hotspot-filters" class="visual-map-toolbar" aria-label="Filter hotspot candidates"><label>Type <select id="visual-hotspot-type"><option value="">All types</option>${types}</select></label><label>Severity <select id="visual-hotspot-severity"><option value="">All severities</option>${severities}</select></label></form>${module}`;
}

function visualRenderHotspots() {
  const state = visualUI.hotspots, d = state.data;
  let body;
  if (state.error) body = `<p class="project-state-warning" role="status">Hotspots are unavailable: ${esc(state.error)}</p>`;
  else if (!d) body = '<p>Loading hotspot candidates…</p>';
  else if (!d.estate_total) body = '<p class="project-empty">The saved assessment has no hotspot candidates. That is an observation about the supplied sources, not a clean bill of health.</p>';
  else {
    const cards = (d.items || []).map(visualHotspotCard).join('') || '<p class="project-empty">No hotspot candidates match these filters.</p>';
    const page = d.total > d.limit ? `<div class="project-actions"><button class="btn" id="visual-hotspot-prev" ${d.offset === 0 ? 'disabled' : ''}>Previous</button><span>${Number(d.offset) + 1}–${Math.min(Number(d.total), Number(d.offset) + Number(d.limit))} of ${Number(d.total)}</span><button class="btn" id="visual-hotspot-next" ${d.offset + d.limit >= d.total ? 'disabled' : ''}>Next</button></div>` : '';
    body = `<p class="visual-boundary" role="note">${esc(d.boundary)}</p><p aria-live="polite">Showing ${(d.items || []).length} of ${Number(d.total)} matching candidates (${Number(d.estate_total)} in the estate).</p>${cards}${page}${visualHotspotMatrix(d.matrix)}`;
  }
  $('project-content').innerHTML = `${projectSectionNav('hotspots')}${visualPageHead('Hotspot Explorer', 'Structural patterns in the saved assessment that deserve an architect\'s attention, with the evidence behind each one and its limits.')}${visualHotspotFilters(d)}<div id="visual-hotspot-body">${body}</div>`;
  visualBindPage();
  const root = $('project-content'), reload = () => { state.offset = 0; visualLoadHotspots(); };
  const type = $('visual-hotspot-type'), severity = $('visual-hotspot-severity');
  if (type) type.onchange = () => { state.filters.type = type.value || undefined; reload(); };
  if (severity) severity.onchange = () => { state.filters.severity = severity.value || undefined; reload(); };
  const form = $('visual-hotspot-filters');
  if (form) form.onsubmit = e => e.preventDefault();
  const clear = $('visual-hotspot-clear-module');
  if (clear) clear.onclick = () => { delete state.filters.module; reload(); };
  const prev = $('visual-hotspot-prev'), next = $('visual-hotspot-next');
  if (prev) prev.onclick = () => { state.offset = Math.max(0, state.offset - VISUAL_HOTSPOT_PAGE); visualLoadHotspots(); };
  if (next) next.onclick = () => { state.offset += VISUAL_HOTSPOT_PAGE; visualLoadHotspots(); };
  root.querySelectorAll('[data-hotspot-map]').forEach(el => { el.onclick = () => visualShowOnMap(el.dataset.hotspotMap); });
  root.querySelectorAll('[data-hotspot-module]').forEach(el => { el.onclick = () => visualModuleOpen({ node: el.dataset.hotspotModule }); });
  root.querySelectorAll('[data-hotspot-review]').forEach(el => { el.onclick = () => { visualCross('review'); projectReviewFinding(el.dataset.hotspotReview); }; });
  root.querySelectorAll('[data-matrix-module]').forEach(el => { el.onclick = () => { state.filters = { module: el.dataset.matrixModule, type: el.dataset.matrixType }; reload(); }; });
}

// ---- 2.2 Review architecture context ---------------------------------------
// The review detail gains one line of architecture around the finding. It is
// refetched for every detail render, so a decision refreshes the counts
// without re-analysis; a late answer for another finding is discarded.
visualUI.reviewContext = { request: 0 };

async function visualReviewContext(row) {
  const host = $('visual-review-context');
  if (!host || !row?.id) return;
  const c = projectContext(), state = visualUI.reviewContext, request = ++state.request;
  host.innerHTML = '<p class="project-muted">Loading architecture context…</p>';
  let d = null, error = null;
  try { d = await api(`/api/v2/projects/${encodeURIComponent(c.id)}/module-360?finding=${encodeURIComponent(row.id)}`); }
  catch (e) { error = e.message; }
  if (!projectCurrent(c) || request !== state.request || projectUI.view !== 'review' || projectUI.reviewState?.detail?.item?.id !== row.id) return;
  const target = $('visual-review-context');
  if (!target) return;
  if (error) { target.innerHTML = `<p class="project-muted">Architecture context is unavailable for this finding: ${esc(error)}</p>`; return; }
  const n = d.node || {}, review = n.review_summary || {};
  target.innerHTML = `<p><b>Architecture context:</b> ${esc(n.name)} · ${esc(visualLabel(n.presentation_type) || n.type)} · ${Number(n.fan_in)} incoming · ${Number(n.fan_out)} outgoing relationships${d.hotspots_total ? ` · ${visualStatus('CANDIDATE')} ${Number(d.hotspots_total)} hotspot candidate(s)` : ''} · ${Number(review.decided)} of ${Number(review.total)} findings decided${Number(review.deferred) ? ` · ${Number(review.deferred)} deferred` : ''}</p><div class="project-actions"><button type="button" class="btn" id="visual-review-module" data-id="${esc(n.id)}">Open Module 360</button><button type="button" class="btn" id="visual-review-map" data-id="${esc(n.id)}">Show on System Map</button></div>`;
  const module = $('visual-review-module'), map = $('visual-review-map');
  if (module) module.onclick = () => visualModuleOpen({ node: n.id });
  if (map) map.onclick = () => visualShowOnMap(n.id);
}
'''
