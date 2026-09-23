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
function visualReasonText(reasons = []) { return reasons.map(r => visualReasonLabels[r] || projectFactorText([r])).join(' · '); }

function visualInvestigationBoard(visual) {
  const board = visual.board || { groups: [] };
  const columns = (board.groups || []).map(group => {
    const modules = (group.modules || []).map(m => `<li><button type="button" class="project-metric-link" data-visual-module="${esc(m.module)}"><b>${esc(m.module)}</b></button><span>${Number(m.findings || 0)} findings · ${Number(m.unresolved || 0)} awaiting decision${m.hotspot_candidates ? ` · ${Number(m.hotspot_candidates)} hotspot candidates` : ''}${m.stale_decisions ? ` · ${Number(m.stale_decisions)} stale decisions` : ''}</span>${(m.reasons || []).length ? `<span>Why: ${esc(visualReasonText(m.reasons))}</span>` : ''}</li>`).join('');
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
  else if (section === 'hotspots') { if (typeof visualHotspotsOpen === 'function') visualHotspotsOpen(); else projectOpenInventory({ category: 'hotspots' }); }
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
'''
