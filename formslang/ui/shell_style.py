"""Layout and navigation styles for the corporate workbench shell."""

SHELL_STYLE = r"""
  :root { --nav-width: 232px; }
  body { padding-left: var(--nav-width); }
  .skip-workspace { position: fixed; top: -80px; left: calc(var(--nav-width) + 16px); z-index: 100; padding: 10px 16px; background: var(--gold); color: var(--on-accent, #1a1206); border-radius: 6px; }
  .skip-workspace:focus { top: 12px; }
  .app-nav { position: fixed; inset: 0 auto 0 0; width: var(--nav-width); z-index: 22; display: flex; flex-direction: column; background: var(--panel); border-right: 1px solid var(--line); min-height: 0; }
  .app-nav .app-brand { padding: 24px 22px 20px; gap: 11px; flex: 0 0 auto; }
  .app-nav .app-brand svg { width: 29px; height: 29px; flex: 0 0 auto; filter: none; }
  .app-brand .brand-copy { display: flex; flex-direction: column; gap: 3px; }
  .app-brand .mark { font-size: 16px; font-weight: 650; letter-spacing: -.025em; }
  .app-nav .app-brand small { display: block; font: 500 9px var(--mono); color: var(--ink-faint); letter-spacing: .18em; text-transform: uppercase; }
  .app-nav .nav-kicker { display: block; color: var(--ink-faint); font: 500 9px/1.5 var(--mono); letter-spacing: .14em; text-transform: uppercase; }
  .module-switcher { margin: 0 14px 20px; padding: 11px 12px 10px; border: 1px solid var(--line); border-radius: 8px; background: var(--raised); }
  .module-switcher #btn-module { display: block; width: 100%; padding: 4px 14px 0 0; border: 0; border-radius: 0; background: transparent; text-align: left; color: var(--ink); font: 500 11px/1.6 var(--mono); text-overflow: ellipsis; overflow: hidden; white-space: nowrap; position: relative; }
  .module-switcher #btn-module::after { content: '⌄'; position: absolute; right: 0; top: 3px; color: var(--ink-faint); }
  .module-switcher:hover { border-color: var(--line-hi); }
  .nav-sections { flex: 1; min-height: 0; overflow-y: auto; padding: 0 10px 16px; }
  .nav-group + .nav-group { margin-top: 22px; }
  .nav-group > .nav-kicker { padding: 0 12px 8px; }
  .nav-item { position: relative; display: flex; align-items: center; gap: 12px; width: 100%; padding: 10px 12px; margin: 2px 0; border: 0; border-radius: 7px; background: transparent; color: var(--ink-dim); font: 450 12.5px/1.5 var(--sans); text-align: left; transition: background .16s, color .16s, box-shadow .16s; }
  .nav-item svg, .theme-toggle svg, .nav-toggle svg { display: block; width: 17px; height: 17px; fill: none; stroke: currentColor; stroke-width: 1.5; stroke-linecap: round; stroke-linejoin: round; flex-shrink: 0; }
  .nav-item:hover:not(:disabled) { background: var(--hover); color: var(--ink); }
  .nav-item[aria-current='page'] { background: var(--gold-soft); color: var(--gold); box-shadow: inset 2px 0 0 var(--gold); }
  .nav-item:disabled { opacity: .35; cursor: not-allowed; }
  .nav-footer { padding: 16px 20px 14px; border-top: 1px solid var(--line); flex: 0 0 auto; }
  .provider-block { display: flex; gap: 9px; align-items: center; min-width: 0; }
  .provider-block > div { min-width: 0; flex: 1; }
  .provider-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--green); flex-shrink: 0; }
  .provider-dot.offline { background: var(--ink-faint); }
  .app-nav #provider { display: block; width: 100%; margin-top: 3px; padding: 0; border: 0; background: transparent; text-overflow: ellipsis; overflow: hidden; white-space: nowrap; color: var(--ink-dim); font: 500 11px/1.6 var(--mono); text-align: left; cursor: pointer; }
  .app-nav #provider:hover { color: var(--gold); }
  .nav-local { display: flex; align-items: center; justify-content: space-between; gap: 6px; padding-top: 15px; color: var(--ink-faint); font-size: 10px; }
  .nav-local .theme-toggle { display: inline-flex; align-items: center; justify-content: center; gap: 6px; padding: 5px 7px; color: var(--ink-dim); font-size: 10px; border-color: var(--line); }
  .theme-toggle svg { width: 13px; height: 13px; }
  .nav-credit { display: block; margin-top: 13px; color: var(--ink-faint); font: 500 8px var(--mono); letter-spacing: .09em; }
  .app-header { min-height: 89px; padding: 16px 26px; gap: 16px; background: var(--panel); border-bottom: 1px solid var(--line); flex-wrap: wrap; }
  .workspace-heading { min-width: 140px; max-width: 38%; flex: 1; }
  .workspace-eyebrow { display: flex; align-items: center; gap: 8px; color: var(--ink-faint); font: 500 9px/1.5 var(--mono); text-transform: uppercase; letter-spacing: .1em; white-space: nowrap; }
  .workspace-eyebrow > span:first-child { opacity: .5; }
  .workspace-eyebrow #workspace-caption { color: var(--ink-dim); }
  .workspace-heading h1 { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font: 600 17px/1.5 var(--sans); letter-spacing: -.025em; margin: 3px 0 0; }
  .header-actions { display: flex; align-items: center; gap: 8px; margin-left: auto; }
  .header-actions .btn { white-space: nowrap; font-size: 11.5px; padding: 9px 12px; border-radius: 7px; }
  .header-actions .primary { display: inline-flex; align-items: center; gap: 10px; }
  .app-header #counts { margin-left: auto; flex-wrap: wrap; justify-content: flex-end; gap: 7px; font-size: 10px; }
  .app-header #counts > span { padding: 0; border: 0; border-radius: 0; background: transparent; gap: 5px; }
  .app-header #counts > span + span { border-left: 1px solid var(--line); padding-left: 8px; }
  .nav-toggle, .nav-close, .nav-scrim { display: none; }
  #working, #setup-banner { padding: 12px 26px; }
  #setup-banner { font-size: 12px; gap: 12px; }
  #setup-banner .btn { font-size: 11px; padding: 7px 10px; white-space: nowrap; }
  body.is-first-run main { grid-template-columns: minmax(0, 1fr); }
  body.is-first-run main > aside { display: none; }
  body.is-first-run .app-header #counts { display: none; }
  body.is-first-run .header-actions { display: none; }
  body.is-first-run .workspace-heading { max-width: none; }
  #welcome { overflow-y: auto; padding: 32px; background: radial-gradient(ellipse at 70% 18%, var(--gold-soft), transparent 55%), var(--ground); }
  #welcome .hello { width: 100%; max-width: 850px; padding: 36px 30px; text-align: left; margin: auto; animation: shell-arrive .4s cubic-bezier(.2,.7,.2,1) both; }
  #welcome .hello > svg { width: 42px; height: 42px; margin-bottom: 25px; filter: none; }
  #welcome .welcome-eyebrow { display: block; margin-bottom: 17px; color: var(--ink-faint); font: 500 10px var(--mono); letter-spacing: .15em; }
  #welcome .hello h1 { margin-bottom: 20px; font-size: clamp(30px, 3.4vw, 48px); font-weight: 550; line-height: 1.12; letter-spacing: -.045em; text-wrap: balance; }
  #welcome .hello > p { margin: 0 0 30px; max-width: 55ch; font-size: 14px; line-height: 1.8; }
  #welcome .steps { gap: 0; margin: 32px 0; border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); }
  #welcome .step { padding: 21px 20px; border: 0; border-radius: 0; background: transparent; animation: shell-arrive .45s ease both; }
  #welcome .step:first-child { padding-left: 0; }
  #welcome .step + .step { border-left: 1px solid var(--line); }
  #welcome .step:nth-child(2) { animation-delay: .05s; }
  #welcome .step:nth-child(3) { animation-delay: .1s; }
  #welcome .step .no { color: var(--gold); font-size: 9px; margin-bottom: 12px; font-weight: 500; }
  #welcome .step b { font-size: 12px; font-weight: 600; margin-bottom: 7px; }
  #welcome .step > span:last-child { color: var(--ink-dim); line-height: 1.7; font-size: 11.5px; }
  #welcome .hello .cta { justify-content: flex-start; }
  #welcome .hello .cta .primary { padding: 12px 20px; font-size: 13px; }
  #welcome .hello .local { justify-content: flex-start; text-align: left; font-size: 11px; color: var(--ink-faint); margin-top: 22px; }
  #welcome .hello .legal { font-size: 10px; margin-top: 12px; }
  @keyframes shell-arrive { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
  @media (max-width: 1380px) {
    .app-header { gap: 12px; padding: 15px 20px; }
    .app-header #counts { order: 3; flex-basis: 100%; justify-content: flex-start; margin: 0; }
  }
  @media (max-width: 1180px) and (min-width: 721px) {
    :root { --nav-width: 76px; }
    .app-nav .app-brand { justify-content: center; padding: 24px 0; }
    .app-brand .brand-copy, .module-switcher .nav-kicker, .nav-group > .nav-kicker, .nav-item > span, .provider-block, .nav-local > span, .nav-credit { display: none; }
    .module-switcher { margin: 0 12px 18px; padding: 0; border: 0; background: transparent; }
    .module-switcher #btn-module { height: 40px; overflow: hidden; color: transparent; font-size: 0; border: 1px solid var(--line); border-radius: 7px; }
    .module-switcher #btn-module::after { content: '+'; top: 3px; right: 0; width: 100%; text-align: center; color: var(--ink-dim); font: 400 22px var(--sans); }
    .nav-sections { padding: 0 12px 12px; }
    .nav-group + .nav-group { margin-top: 15px; padding-top: 15px; border-top: 1px solid var(--line); }
    .nav-item { justify-content: center; padding: 12px; }
    .nav-item svg { width: 19px; height: 19px; }
    .nav-footer { padding: 15px 12px; }
    .nav-local { padding: 0; justify-content: center; }
    .nav-local .theme-toggle { padding: 9px; }
    .nav-local .theme-toggle span { display: none; }
    .nav-local .theme-toggle svg { width: 17px; height: 17px; }
  }
  @media (max-width: 720px) {
    :root { --nav-width: 0px; }
    .app-nav { width: min(282px, calc(100vw - 48px)); transform: translateX(-100%); visibility: hidden; transition: transform .22s cubic-bezier(.2,.7,.2,1), visibility .22s; box-shadow: 12px 0 48px rgba(0,0,0,.2); }
    body.nav-open .app-nav { transform: translateX(0); visibility: visible; transition-property: transform; }
    .app-nav .app-brand { padding: 20px; }
    .nav-close { display: block; margin-left: auto; padding: 2px 9px; font-size: 21px; border-color: var(--line); }
    .nav-scrim:not([hidden]) { display: block; position: fixed; inset: 0; z-index: 21; background: rgba(0,0,0,.5); border: 0; border-radius: 0; }
    .app-header { padding: 12px 14px; gap: 12px; min-height: 74px; }
    .nav-toggle { display: flex; padding: 9px; flex-shrink: 0; border-color: var(--line); }
    .workspace-heading { max-width: calc(100% - 50px); min-width: 0; }
    .workspace-heading h1 { font-size: 15px; }
    .workspace-eyebrow { font-size: 8px; gap: 6px; }
    .header-actions { flex-basis: 100%; justify-content: flex-end; }
    .header-actions .btn { flex: 1; justify-content: center; padding: 8px 9px; font-size: 11px; }
    .app-header #counts { font-size: 9px; gap: 6px; }
    .app-header #counts > span + span { padding-left: 6px; }
    #working, #setup-banner { padding: 10px 14px; flex-wrap: wrap; }
    #setup-banner > span:first-child { flex-basis: 100%; }
    #welcome { padding: 15px; }
    #welcome .hello { padding: 24px 12px; }
    #welcome .hello h1 { font-size: 32px; }
    #welcome .hello > p { font-size: 13px; }
    #welcome .steps { grid-template-columns: 1fr; margin: 26px 0; }
    #welcome .step, #welcome .step:first-child { padding: 17px 0; }
    #welcome .step + .step { border-left: 0; border-top: 1px solid var(--line); }
    #welcome .hello .cta { flex-wrap: wrap; }
    #welcome .hello .local { line-height: 1.7; }
  }
  @media (max-height: 730px) and (min-width: 721px) {
    .app-nav .app-brand { padding-top: 17px; padding-bottom: 16px; }
    .module-switcher { margin-bottom: 13px; }
    .nav-group + .nav-group { margin-top: 13px; }
    .nav-item { padding-top: 8px; padding-bottom: 8px; }
    .nav-footer { padding-top: 12px; padding-bottom: 10px; }
    .nav-credit { display: none; }
    #welcome .hello { padding-top: 16px; padding-bottom: 16px; }
    #welcome .hello > svg { width: 30px; height: 30px; margin-bottom: 15px; }
  }
  @media (prefers-reduced-motion: reduce) {
    .app-nav, .nav-item, #welcome .hello, #welcome .step { transition: none; animation: none; }
  }
"""
