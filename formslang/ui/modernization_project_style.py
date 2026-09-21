"""Project screens reuse the existing corporate theme and responsive shell."""

PROJECT_STYLE = r'''
  #project-workspace[hidden] { display:none; }
  body.project-mode main { display:block; overflow:auto; }
  body.project-mode main > :not(#project-workspace), body.project-mode .header-actions,
  body.project-mode #counts, body.project-mode #setup-banner, body.project-mode .provider-block { display:none !important; }
  body.project-mode .module-switcher, body.project-mode .nav-item:not(#btn-modernization):not(#btn-settings) { display:none; }
  body.project-mode .nav-group > .nav-kicker { display:none; }
  #project-workspace { max-width:1100px; margin:auto; padding:24px; gap:12px; }
  #project-workspace h2 { font-size:22px; margin:12px 0; }
  #project-workspace p { line-height:1.6; }
  #project-error:empty,#project-status:empty { display:none; }
  .project-toolbar,.project-actions { display:flex;flex-wrap:wrap;gap:10px;margin:12px 0; }
  .project-steps { display:flex;gap:24px;list-style:none;padding:16px 0;border-bottom:1px solid var(--line);flex-wrap:wrap;color:var(--ink-dim); }
  .project-steps [aria-current] { color:var(--gold);font-weight:600; }
  .project-fields { display:grid;gap:8px;max-width:650px; }
  .project-fields input,.project-fields textarea,.project-picker input { width:100%;background:var(--panel);color:var(--ink);border:1px solid var(--line-hi);border-radius:6px;padding:10px; }
  .project-fields textarea { min-height:80px; }
  #project-error:not(:empty),#project-picker-error:not(:empty) { border-left:3px solid var(--red);padding:10px;color:var(--ink);background:var(--raised); }
  .project-stats { display:flex;gap:12px;flex-wrap:wrap;margin:18px 0; }
  .project-stats > div { min-width:130px;padding:12px;border:1px solid var(--line);background:var(--panel);border-radius:7px; }
  .project-stats dt { color:var(--ink-dim);font-size:12px; }.project-stats dd { margin:8px 0 0;font-size:22px; }
  .project-recent { border-top:1px solid var(--line);padding:14px 0; }
  .project-muted { color:var(--ink-dim);font-size:12px; }
  .project-table { width:100%;border-collapse:collapse; }.project-table td,.project-table th { text-align:left;padding:8px;border-bottom:1px solid var(--line);overflow-wrap:anywhere; }
  .project-diagnostics li { padding:8px 0;overflow-wrap:anywhere; }.project-diagnostics span { display:block;color:var(--ink-dim); }
  .project-picker { padding:16px; }.project-picker ul { list-style:none;padding:0; }.project-picker li { margin:5px 0; }
  #project-progress { border-left:3px solid var(--gold);padding:16px;background:var(--panel); }
  .project-section-nav { display:flex;gap:6px;overflow-x:auto;padding:0 0 10px;border-bottom:1px solid var(--line); }
  .project-section-nav [aria-current="page"] { border-color:var(--gold);color:var(--gold); }
  .project-overview-header { display:flex;align-items:flex-start;justify-content:space-between;gap:24px; }
  .project-overview-header p { margin:4px 0; }
  .project-assessment-state { display:grid;gap:4px;min-width:145px;text-align:right; }
  .project-assessment-state span { color:var(--ink-dim);font-size:12px; }
  .project-assessment-state b { font-size:16px; }
  .project-assessment-state [data-status="STALE"],.project-assessment-state [data-status="INCOMPLETE"],.project-assessment-state [data-status="MISSING_SOURCE"] { color:var(--amber); }
  .project-state-warning { border-left:3px solid var(--amber);background:var(--raised);padding:10px 14px;margin:12px 0; }
  .project-overview-grid { display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px; }
  .project-panel { min-width:0;border:1px solid var(--line);background:var(--panel);border-radius:7px;padding:14px; }
  .project-panel h3 { margin:0 0 10px;font-size:15px; }
  .project-panel-wide { grid-column:1/-1; }
  .project-overview-inventory { display:grid;grid-template-columns:repeat(5,minmax(110px,1fr));gap:0;margin:0; }
  .project-overview-inventory div { padding:8px 10px;border-left:1px solid var(--line); }
  .project-overview-inventory div:first-child { border-left:0; }
  .project-overview-inventory dt,.project-distribution dt,.project-coverage dt { color:var(--ink-dim);font-size:12px; }
  .project-overview-inventory dd { margin:5px 0 0;font-size:20px; }
  .project-distribution { display:grid;gap:6px;margin:0; }
  .project-distribution div { display:flex;align-items:center;justify-content:space-between;gap:12px;border-bottom:1px solid var(--line);padding:5px 0; }
  .project-distribution dd { margin:0;font-variant-numeric:tabular-nums; }
  .project-metric-link { color:inherit;background:none;border:0;padding:0;text-align:left;text-decoration:underline;text-decoration-color:transparent;cursor:pointer; }
  .project-metric-link:hover,.project-metric-link:focus { color:var(--gold);text-decoration-color:currentColor; }
  .project-coverage { display:grid;gap:10px;margin:0; }.project-coverage dd { margin:3px 0 0; }
  .project-warnings { margin:0;padding-left:20px; }.project-warnings li { padding:5px 0; }.project-warnings span { display:block;color:var(--ink-dim); }
  .project-empty { color:var(--ink-dim); }
  .project-inventory-tabs { display:flex;gap:6px;overflow-x:auto;padding:10px 0; }
  .project-inventory-tabs [aria-selected="true"] { border-color:var(--gold);color:var(--gold); }
  .project-filter-bar { display:grid;grid-template-columns:max-content minmax(150px,1fr) max-content minmax(110px,.5fr) max-content minmax(180px,.8fr) max-content max-content;align-items:center;gap:8px;padding:10px;background:var(--panel);border:1px solid var(--line);border-radius:7px; }
  .project-filter-bar input,.project-filter-bar select { min-width:0;background:var(--raised);color:var(--ink);border:1px solid var(--line-hi);border-radius:5px;padding:8px; }
  .project-table-wrap { overflow:auto;max-width:100%;border:1px solid var(--line);border-radius:7px; }
  .project-inventory-table { min-width:720px;margin:0; }
  .project-inventory-table caption { text-align:left;padding:10px;color:var(--ink-dim); }
  .project-inventory-item { color:var(--ink);background:none;border:0;padding:0;text-align:left;text-decoration:underline;text-decoration-color:var(--line-hi);cursor:pointer; }
  .project-inventory-item:hover,.project-inventory-item:focus { color:var(--gold); }
  .project-pagination { display:flex;align-items:center;justify-content:flex-end;gap:8px;margin:8px 0; }
  .project-pagination p { margin-right:auto; }
  .project-inventory-detail dl { display:grid;grid-template-columns:max-content 1fr;gap:6px 14px; }
  .project-inventory-detail dd { margin:0;overflow-wrap:anywhere; }.project-inventory-detail li span { display:block;color:var(--ink-dim); }
  @media(max-width:900px){.project-overview-inventory{grid-template-columns:repeat(3,minmax(100px,1fr));}.project-overview-inventory div{border-left:0;border-top:1px solid var(--line);}}
  @media(max-width:900px){.project-filter-bar{grid-template-columns:max-content 1fr max-content 1fr;}.project-filter-bar .btn{justify-self:start;}}
  @media(max-width:720px){#project-workspace{padding:16px;}.project-steps{gap:12px;}.project-stats>div{min-width:100px;flex:1;}.project-overview-grid{grid-template-columns:1fr;}.project-panel-wide{grid-column:auto;}.project-overview-header{display:block;}.project-assessment-state{text-align:left;}.project-overview-inventory{grid-template-columns:repeat(2,minmax(100px,1fr));}.project-filter-bar{display:flex;flex-direction:column;align-items:stretch;}.project-inventory-detail dl{grid-template-columns:1fr;}.project-inventory-detail dd{margin-bottom:6px;}}
  @media(prefers-reduced-motion:reduce){.project-section-nav{scroll-behavior:auto;}}
'''
