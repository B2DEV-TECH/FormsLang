"""The workbench's shared corporate theme and restrained motion system."""

CORPORATE_STYLE = r"""
  :root {
    color-scheme: dark;
    --code-bg: #0D1117;
    --code-ink: #CDD6E3;
    --code-comment: #8997AC;
    --code-string: #A6CBAF;
    --code-number: #C8AEED;
    --code-gutter: #768296;
    --overlay: rgba(4, 7, 12, .72);
    --shadow: 0 20px 72px rgba(0, 0, 0, .36);
    --ease: cubic-bezier(.2, .75, .25, 1);
    --fast: 150ms;
    --normal: 220ms;
  }
  :root[data-theme="light"] {
    color-scheme: light;
    --ground: #EFF1F4;
    --panel: #FFFFFF;
    --raised: #F7F8FA;
    --hover: #E9EDF2;
    --line: #DCE1E8;
    --line-hi: #BEC7D3;
    --ink: #202B3B;
    --ink-dim: #536175;
    --ink-faint: #617086;
    --gold: #9C5B06;
    --gold-deep: #A5640C;
    --gold-soft: rgba(166, 100, 12, .07);
    --gold-line: rgba(156, 91, 6, .30);
    --green: #247750;
    --red: #BD3C47;
    --violet: #7851B4;
    --blue: #3269AE;
    --code-bg: #FAFBFD;
    --code-ink: #25364C;
    --code-comment: #617087;
    --code-string: #347244;
    --code-number: #7950A0;
    --code-gutter: #6C7B90;
    --overlay: rgba(30, 41, 58, .28);
    --shadow: 0 20px 72px rgba(28, 43, 66, .16);
  }
  body { font-size: 13px; }
  button, input, textarea, select { font-family: var(--sans); }
  input, textarea, select { accent-color: var(--gold-deep); }
  button, a, input, select, summary {
    -webkit-tap-highlight-color: transparent;
  }
  :focus-visible { outline: 2px solid var(--gold); outline-offset: 3px; }
  .btn {
    min-height: 34px; border-radius: 7px; font-size: 12px; font-weight: 550;
    transition: background var(--fast) var(--ease), border-color var(--fast) var(--ease),
      color var(--fast) var(--ease), transform var(--fast) var(--ease), box-shadow var(--fast) var(--ease);
  }
  .btn.primary {
    background: #F5A640; color: #20180C; border-color: #F5A640;
    box-shadow: 0 1px 2px rgba(0, 0, 0, .12); font-weight: 650;
  }
  .btn.primary:hover:not(:disabled) { background: #FFB554; border-color: #FFB554; filter: none; }
  .btn:disabled { opacity: .45; }
  .btn:disabled:hover { color: var(--ink-dim); background: transparent; border-color: var(--line-hi); }
  .btn.primary:disabled:hover { color: #20180C; background: #F5A640; border-color: #F5A640; }
  .chip { letter-spacing: .015em; border-radius: 6px; }
  .sheet { background: var(--panel); border-radius: 12px; box-shadow: var(--shadow); }
  .sheet::before { background: var(--gold); height: 1px; opacity: .45; }
  .modal { background: var(--overlay); backdrop-filter: blur(5px); z-index: 50; }
  .sheet-head { padding: 21px 24px; background: var(--panel); }
  .sheet-head h2 { font-size: 20px; letter-spacing: -.025em; }
  .sheet-foot { background: var(--raised); }
  .sheet-body { scrollbar-gutter: stable; }
  .sheet .hint { line-height: 1.65; }
  .sheet-body:has(.dash) { background: var(--ground); }
  .dash { padding-top: 14px; gap: 20px; }
  .dash h3 { font: 600 11px var(--sans); letter-spacing: .07em; }
  .dash .card { background: var(--panel); padding: 20px; border-radius: 9px; }
  .kpis { gap: 12px; }
  .kpi { padding: 17px; border-radius: 9px; background: var(--panel); }
  .kpi b { font-size: 27px; font-weight: 600; margin-bottom: 7px; }
  .kpi span { font-family: var(--sans); letter-spacing: .035em; }
  .ready .num { font-size: 50px; font-weight: 600; }
  .ready .gauge i, .brow .track i { animation: corporate-meter 400ms var(--ease) both; transform-origin: left; }
  .formula th, .dtable th { font-family: var(--sans); font-weight: 600; padding: 9px 10px; }
  .formula td, .dtable td { padding: 9px 10px; }
  .dtable .sub, .formula .d { line-height: 1.6; }
  .dtable td.n, .formula td.n { color: var(--ink); }
  .blk span, .notes li, .entry.dir .name { color: var(--ink-dim); }
  .picker-info, .entry .icon { background: var(--raised); }
  .entry.mod .icon { background: #F5A640; color: #20180C; }
  .entry.mod.xml .icon { background: color-mix(in srgb, var(--violet) 14%, var(--panel)); color: var(--violet); }
  .dropmark { background: #F5A640; box-shadow: none; }
  .dropzone { border-color: var(--line-hi); }
  .safety { color: var(--green); }
  .settings-form { gap: 18px; padding-bottom: 14px; }
  .settings-form label, .export-form label, .bind-row label {
    font-family: var(--sans); letter-spacing: .045em; font-weight: 600;
  }
  .settings-form input, .export-form input, .sheet-foot input, .bind-row select {
    min-height: 38px; background: var(--raised); border-radius: 7px;
  }
  .settings-form .duo { gap: 16px; }
  .export-form { gap: 16px; padding: 16px 24px 20px; }
  .exports-list .exp-row { flex-wrap: wrap; gap: 10px; padding: 15px; }
  .exports-list .exp-meta { white-space: normal; }
  .pane-busy { background: color-mix(in srgb, var(--panel) 96%, transparent); }
  .code-wrap, textarea.code { background: var(--code-bg); }
  pre.code, .code-wrap pre.hl-overlay { color: var(--code-ink); }
  pre.code .ln { color: var(--code-gutter); }
  .code-wrap textarea.code { background: transparent; color: transparent; caret-color: var(--code-ink); }
  .s { color: var(--code-string); }
  .c { color: var(--code-comment); }
  .n { color: var(--code-number); }
  .r-HIGH { color: var(--gold); }
  .notes { color: var(--ink-dim); }
  #toast { box-shadow: var(--shadow); border-radius: 8px; z-index: 60; }
  .sheet { animation: corporate-dialog var(--normal) var(--ease) both; }
  .entry { transition: background var(--fast) var(--ease), border-color var(--fast) var(--ease); }
  .bp-card, .bp-row, .bp-category { transition: background var(--fast) var(--ease), border-color var(--fast) var(--ease); }
  @keyframes corporate-dialog { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }
  @keyframes corporate-meter { from { transform: scaleX(0); } to { transform: scaleX(1); } }
  @media (max-width: 760px) {
    .sheet-head { padding: 16px; gap: 10px; }
    .sheet-head h2 { font-size: 17px; }
    .sheet-head .path { grid-column: 1 / -1; grid-row: 2; }
    .sheet-head .path:empty { display: none; }
    .sheet-foot { padding: 12px 16px; }
    .sheet-foot input { min-width: 0; }
    .dash { padding: 12px 14px; }
    .dash .card { padding: 15px; overflow-x: auto; }
    .kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .dists { grid-template-columns: minmax(0, 1fr); }
    .settings-form { padding: 14px 16px; }
    .settings-form .duo { grid-template-columns: minmax(0, 1fr); }
    .picker-shell { padding: 4px 16px 12px; }
    .dropzone { padding: 16px; gap: 12px; }
    .dropmark { flex-basis: 42px; height: 54px; font-size: 12px; }
    .export-form { padding: 14px 16px; }
  }
  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { animation: none !important; transition: none !important; scroll-behavior: auto !important; }
  }
"""

THEME_JS = r"""
function setWorkbenchTheme(theme) {
  document.documentElement.dataset.theme = theme;
  try { localStorage.setItem("formslang.theme", theme); } catch (_) { /* Storage can be disabled. */ }
  const control = $("theme-toggle");
  const light = theme === "light";
  control.setAttribute("aria-pressed", String(light));
  control.setAttribute("aria-label", light ? "Switch to dark theme" : "Switch to light theme");
  control.title = light ? "Switch to dark theme" : "Switch to light theme";
  const label = control.querySelector(".theme-label");
  if (label) label.textContent = light ? "Light theme" : "Dark theme";
}
function initWorkbenchTheme() {
  setWorkbenchTheme(document.documentElement.dataset.theme === "light" ? "light" : "dark");
  $("theme-toggle").onclick = () => setWorkbenchTheme(
    document.documentElement.dataset.theme === "light" ? "dark" : "light"
  );
}
initWorkbenchTheme();
"""
