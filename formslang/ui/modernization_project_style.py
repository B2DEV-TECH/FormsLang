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
  @media(max-width:720px){#project-workspace{padding:16px;}.project-steps{gap:12px;}.project-stats>div{min-width:100px;flex:1;}}
'''
