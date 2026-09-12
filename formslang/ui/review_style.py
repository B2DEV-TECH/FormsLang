"""Corporate review workspace styles, composed with the shared design tokens."""

from __future__ import annotations

REVIEW_STYLE = r"""
  main { position: relative; display: grid; grid-template-columns: 280px minmax(0, 1fr); min-height: 0; min-width: 0; flex: 1; }
  #unit-list { min-width: 0; background: var(--panel); border-right: 1px solid var(--line); }
  .units-heading { display: flex; align-items: center; justify-content: space-between; padding: 19px 18px 8px; }
  .units-heading h2 { margin: 0; color: var(--ink); font: 600 13px var(--sans); letter-spacing: -.01em; }
  .units-heading kbd { color: var(--ink-dim); }
  #unit-close { display: none; padding: 4px; }
  #unit-close svg { display: block; width: 15px; height: 15px; fill: none; stroke: currentColor; stroke-width: 1.6; }
  #unit-list .search { position: relative; padding: 6px 16px 14px; border: 0; }
  #unit-list .search svg { position: absolute; left: 27px; top: 18px; width: 15px; height: 15px; fill: none; stroke: var(--ink-dim); stroke-width: 1.6; pointer-events: none; }
  #unit-list .search input { background: var(--raised); padding: 10px 10px 10px 33px; border-radius: 7px; font: 12px var(--sans); }
  .unit-filters { flex: 0 0 auto; margin: 0; border-bottom: 1px solid var(--line); }
  .unit-filters > summary { display: flex; align-items: center; gap: 8px; padding: 0 18px 12px; list-style: none; cursor: pointer; color: var(--ink-dim); font: 500 11px var(--sans); }
  .unit-filters > summary::-webkit-details-marker { display: none; }
  .unit-filters > summary::before { content: "›"; font-size: 15px; line-height: 1; transition: transform .16s; }
  .unit-filters[open] > summary::before { transform: rotate(90deg); }
  #active-filters { margin-left: auto; font-size: 10px; color: var(--gold); }
  #unit-list .filters { gap: 12px; padding: 0 16px 15px; border: 0; }
  #unit-list .frow { display: block; }
  #unit-list .flabel { display: block; margin-bottom: 5px; color: var(--ink-dim); font: 500 10px var(--sans); letter-spacing: .025em; text-transform: none; }
  #unit-list .frow > span:last-child { display: flex; flex-wrap: wrap; gap: 3px; }
  #unit-list .frow button { padding: 4px 7px; border-radius: 5px; border-color: var(--line); font: 11px var(--sans); letter-spacing: 0; text-transform: capitalize; }
  #unit-list .frow button.on { color: var(--gold); border-color: var(--gold-line); background: var(--gold-soft); }
  .units-meta { display: flex; align-items: center; justify-content: space-between; gap: 8px; min-height: 37px; padding: 8px 18px; border-bottom: 1px solid var(--line); }
  .units-summary { margin: 0; padding: 0; border: 0; color: var(--ink-dim); font: 10px var(--mono); letter-spacing: 0; text-transform: none; }
  #reset-filters { background: none; border: 0; padding: 1px 0; color: var(--gold); font: 11px var(--sans); }
  #reset-filters:hover { text-decoration: underline; }
  #reset-filters[hidden] { display: none; }
  #list { padding: 4px 0 12px; overscroll-behavior: contain; }
  .unit-group { padding: 13px 18px 6px; color: var(--ink-dim); font: 500 9px var(--mono); text-transform: uppercase; letter-spacing: .11em; overflow-wrap: anywhere; }
  #list .row { grid-template-columns: 13px minmax(0, 1fr) auto; gap: 7px; padding: 11px 10px; margin: 2px 7px; border: 1px solid transparent; border-left: 2px solid transparent; border-radius: 5px; transition: background .14s, border-color .14s; }
  #list .row:hover { background: var(--hover); }
  #list .row.sel { background: var(--raised); border-color: var(--line); border-left-color: var(--gold); }
  #list .row.sel .title { color: var(--ink); }
  #list .row .title { color: var(--ink-dim); font: 500 11px/1.5 var(--mono); }
  #list .row .sub { margin-top: 4px; font: 10px/1.5 var(--sans); color: var(--ink-dim); }
  #list .row .rside { gap: 4px; }
  #list .row .verdict { max-width: 58px; padding: 2px 4px; font-size: 8px; letter-spacing: 0; }
  #list .row .state { align-self: start; padding-top: 1px; }
  #list .row.queued { background: color-mix(in srgb, var(--gold-soft) 40%, var(--panel)); }
  #list .row.working { background: var(--gold-soft); border-left-color: var(--gold); }
  #list .empty { padding: 28px 22px; }
  #list .empty strong, #list .empty span { display: block; }
  #list .empty strong { color: var(--ink); font-size: 12px; font-weight: 500; }
  #list .empty span { margin-top: 7px; color: var(--ink-dim); font-size: 11px; }
  .units-footer { display: flex; justify-content: space-between; gap: 10px; padding: 11px 16px; border-top: 1px solid var(--line); color: var(--ink-dim); font-size: 10px; }
  .units-footer kbd { font: 9px var(--mono); background: var(--raised); border: 1px solid var(--line); border-radius: 3px; padding: 1px 4px; }

  #review-workspace { display: flex; flex-direction: column; min-height: 0; min-width: 0; background: var(--ground); overflow: hidden; }
  #review-workspace .head { padding: 18px 22px 16px; background: var(--panel); }
  .review-eyebrow { margin-bottom: 5px; color: var(--ink-dim); font: 500 9px var(--mono); letter-spacing: .14em; text-transform: uppercase; }
  #review-workspace .head h1 { font: 600 18px/1.35 var(--mono); letter-spacing: -.025em; overflow-wrap: anywhere; }
  #review-workspace .head .where { margin-top: 5px; color: var(--ink-dim); font-size: 11px; }
  #review-workspace .head .where b { color: var(--ink); }
  #review-workspace .head .meta { margin-top: 11px; gap: 6px 8px; color: var(--ink-dim); font-size: 10px; }
  #review-workspace .meta .verdict { font-size: 9px; padding: 3px 6px; }
  #review-workspace .meta .apex-target { border: 1px solid var(--line-hi); padding: 3px 7px; border-radius: 4px; color: var(--ink-dim); }
  .review-toolbar { display: flex; align-items: center; gap: 12px; min-height: 48px; padding: 6px 18px; border-bottom: 1px solid var(--line); background: var(--panel); flex-shrink: 0; }
  .review-views { display: flex; align-items: center; gap: 2px; min-width: 0; }
  .review-views button { padding: 7px 10px; border: 1px solid transparent; border-radius: 5px; color: var(--ink-dim); background: transparent; white-space: nowrap; font: 500 11px var(--sans); transition: color .14s, background .14s, border-color .14s; }
  .review-views button:hover { color: var(--ink); background: var(--hover); }
  .review-views button[aria-pressed="true"] { color: var(--gold); border-color: var(--gold-line); background: var(--gold-soft); }
  .review-navigation { display: flex; align-items: center; gap: 4px; margin-left: auto; }
  #unit-position { margin-right: 6px; color: var(--ink-dim); font: 10px var(--mono); white-space: nowrap; }
  .review-navigation .btn { display: grid; place-items: center; padding: 5px; width: 29px; height: 29px; background: transparent; border-color: var(--line); }
  .review-navigation svg { height: 15px; width: 15px; fill: none; stroke: currentColor; stroke-width: 1.6; stroke-linecap: round; stroke-linejoin: round; }
  #unit-toggle { display: none; white-space: nowrap; font-size: 11px; padding: 7px 10px; }
  #review-workspace #review-code { flex: 1 1 0%; min-height: 120px; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); grid-template-rows: minmax(0, 1fr); }
  #review-code .pane { min-height: 0; background: var(--ground); }
  #review-code .pane h2 { min-height: 54px; padding: 10px 16px; gap: 8px; align-items: center; font: 500 11px/1.4 var(--sans); letter-spacing: 0; text-transform: none; background: var(--raised); }
  #review-code .pane h2 small { display: block; padding-left: 13px; margin-top: 2px; color: var(--ink-dim); font: 10px var(--sans); }
  .pane-label { min-width: 0; color: var(--ink); white-space: nowrap; }
  .pane-dot { display: inline-block; width: 6px; height: 6px; margin-right: 7px; border-radius: 50%; vertical-align: 1px; }
  .forms-dot { background: var(--ink-dim); }
  .apex-dot { background: var(--gold); }
  #t-lines { color: var(--ink-dim); font: 10px var(--mono); white-space: nowrap; }
  #t-conf { display: flex; flex-direction: column; align-items: flex-end; gap: 5px; color: var(--ink-dim); font: 9px var(--mono); }
  #t-conf .cbar { width: 70px; height: 3px; }
  #review-workspace .qtag { font-size: 9px; letter-spacing: 0; white-space: nowrap; }
  #src { padding: 16px 14px 16px 0; color: var(--ink); background: var(--ground); font: 12px/1.75 var(--mono); }
  #src .ln { width: 44px; padding-right: 14px; color: var(--ink-faint); }
  #review-workspace .code-wrap { background: var(--ground); }
  /* These layers share every text metric, including italic handling. */
  #review-workspace .code-wrap pre.code,
  #review-workspace .code-wrap textarea.code { position: absolute; inset: 0; margin: 0; height: 100%; width: 100%; padding: 16px; border: 0; font: 12px/1.75 var(--mono); tab-size: 4; white-space: pre-wrap; overflow-wrap: break-word; word-break: break-word; letter-spacing: 0; overflow: auto; scrollbar-gutter: stable; }
  #review-workspace .code-wrap pre.hl-overlay { background: transparent; color: var(--ink); pointer-events: none; }
  #review-workspace .code-wrap textarea.code { background: transparent; color: transparent; caret-color: var(--ink); resize: none; }
  #review-workspace .code-wrap textarea.plain-code { color: var(--ink); }
  #review-workspace .code-wrap pre.hl-overlay[hidden] { display: none; }
  #review-workspace .code i { font-style: normal; }
  #review-workspace .code .k { color: var(--gold); }
  #review-workspace .code .s { color: var(--green); }
  #review-workspace .code .c { color: var(--ink-dim); }
  #review-workspace .code .n { color: var(--violet); }
  #review-workspace .code .b { color: var(--blue); }
  #review-workspace .pane-busy { background: color-mix(in srgb, var(--panel) 96%, transparent); }

  #notes { display: block; flex: 0 1 auto; min-height: 90px; max-height: 29%; overflow-y: auto; padding: 16px 20px; border-top: 1px solid var(--line); background: var(--panel); scrollbar-gutter: stable; overscroll-behavior: contain; }
  .evidence-heading { margin-bottom: 14px; }
  .evidence-heading h2 { margin: 0; color: var(--ink); font: 600 12px var(--sans); letter-spacing: 0; }
  .evidence-heading p { margin: 4px 0 0; color: var(--ink-dim); font: 11px/1.5 var(--sans); }
  #notes details { margin: 0 0 8px; padding: 0; border: 1px solid var(--line); border-radius: 6px; background: var(--raised); }
  #notes details > summary { padding: 11px 12px; font: 500 11px/1.5 var(--sans); letter-spacing: 0; text-transform: none; color: var(--ink); }
  #notes details > summary::before { color: var(--ink-dim); flex-shrink: 0; }
  #notes details[open] > summary { border-bottom: 1px solid var(--line); margin-bottom: 10px; }
  #notes details > ul, #notes details > .tc, #notes details > .why { margin-left: 12px; margin-right: 12px; }
  #notes details > ul { padding-left: 15px; }
  #notes h3 { margin: 0 0 8px; color: var(--ink); font: 600 11px var(--sans); text-transform: none; letter-spacing: 0; }
  #notes li { margin: 5px 0; font-size: 11px; color: var(--ink-dim); line-height: 1.65; overflow-wrap: anywhere; }
  #notes li.q { color: var(--gold); }
  #notes li code { font-size: 10px; }
  #notes .ev { margin: 4px 0; font-size: 10px; line-height: 1.6; color: var(--ink-dim); }
  #notes .why { color: var(--ink-dim); font-size: 10px; line-height: 1.65; overflow-wrap: anywhere; }
  #notes .pts { color: var(--ink-dim); }
  #notes .empty { margin: 0 0 12px; padding: 13px; border: 1px dashed var(--line-hi); border-radius: 6px; text-align: left; color: var(--ink-dim); font-size: 11px; }
  #notes .err { padding: 12px; border: 1px solid color-mix(in srgb, var(--red) 30%, transparent); border-radius: 6px; margin-bottom: 12px; background: color-mix(in srgb, var(--red) 5%, var(--panel)); overflow-wrap: anywhere; }
  .evidence-card { padding: 13px; border: 1px solid var(--line); border-radius: 6px; margin-bottom: 10px; background: var(--raised); }
  .evidence-card ul { margin-bottom: 0; }
  .evidence-card.questions { border-color: var(--gold-line); background: var(--gold-soft); }
  .evidence-card.questions h3 { color: var(--gold); display: flex; justify-content: space-between; }
  #notes .proposal-origin { display: grid; gap: 4px; margin-top: 15px; padding-top: 12px; border-top: 1px solid var(--line); color: var(--ink-dim); font: 10px/1.6 var(--mono); overflow-wrap: anywhere; }
  #notes .proposal-origin strong { color: var(--ink); font-weight: 500; }
  #notes .tc { margin-bottom: 15px; padding-left: 10px; }
  #notes .tc-t { font-size: 11px; }
  #notes .tc-a { flex-wrap: wrap; gap: 4px; }
  #notes .tc-a button { padding: 4px 6px; color: var(--ink-dim); font: 10px var(--sans); }
  #notes .tc-a .said { width: 100%; font-size: 9px; }
  #notes .gwt li { font-size: 10px; }
  #notes .org, #notes .tc-k, #notes .dep-k { font-size: 9px; }

  #review-workspace .actions { display: flex; flex-direction: column; align-items: stretch; gap: 10px; padding: 13px 20px 15px; border-top: 1px solid var(--line); background: var(--panel); flex-shrink: 0; }
  .review-fields { display: grid; grid-template-columns: minmax(0, 1fr) 145px; gap: 12px; }
  .review-fields label { display: flex; flex-direction: column; align-items: stretch; gap: 5px; min-width: 0; white-space: normal; text-align: left; color: var(--ink-dim); font: 11px var(--sans); }
  #review-workspace .actions input { width: 100%; min-width: 0; padding: 8px 10px; border-color: var(--line); background: var(--raised); color: var(--ink); font: 11px var(--sans); }
  .review-buttons { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; }
  .review-buttons > .btn { min-height: 32px; padding: 7px 11px; font: 500 11px var(--sans); }
  .review-buttons .btn.approve { background: color-mix(in srgb, var(--green) 11%, var(--panel)); border-color: color-mix(in srgb, var(--green) 40%, var(--line)); color: var(--green); }
  .review-buttons .btn.approve:hover { background: color-mix(in srgb, var(--green) 20%, var(--panel)); border-color: var(--green); }
  #btn-needs { color: var(--gold); }
  .review-buttons .btn.reject { color: var(--red); }
  .review-buttons .btn.reject:hover { background: color-mix(in srgb, var(--red) 10%, var(--panel)); border-color: var(--red); }
  #btn-propose { margin-left: auto; }
  #review-status { flex: 1 0 80%; color: var(--ink-dim); font: 10px/1.5 var(--sans); }
  #review-status.err { color: var(--red); }
  #discard-draft { min-height: auto; padding: 0; border: 0; color: var(--gold); font-size: 10px; }
  #discard-draft[hidden] { display: none; }
  #review-workspace[data-view="source"] #review-code,
  #review-workspace[data-view="proposal"] #review-code { grid-template-columns: minmax(0, 1fr); }
  #review-workspace[data-view="source"] .proposal-pane,
  #review-workspace[data-view="proposal"] .source-pane { display: none; }
  #review-workspace[data-view="proposal"] .proposal-pane { border-left: 0; }
  #review-workspace[data-view="evidence"] #review-code { display: none; }
  #review-workspace[data-view="evidence"] #notes { flex: 1; min-height: 0; max-height: none; border-top: 0; }

  @media (min-width: 1680px) {
    main { grid-template-columns: 288px minmax(0, 1fr); }
    #review-workspace { display: grid; grid-template-columns: minmax(0, 1fr) 300px; grid-template-rows: auto auto minmax(0, 1fr) auto; }
    #review-workspace .head { grid-column: 1 / -1; }
    #review-workspace .review-toolbar { grid-column: 1 / -1; }
    #review-code { grid-column: 1; grid-row: 3; }
    #notes { grid-column: 2; grid-row: 3 / 5; max-height: none; min-height: 0; border-top: 0; border-left: 1px solid var(--line); padding: 19px 16px; }
    #review-workspace .actions { grid-column: 1; grid-row: 4; }
    #review-workspace[data-view="evidence"] #notes { grid-column: 1 / -1; grid-row: 3; border-left: 0; padding: 22px 28px; }
    #review-workspace[data-view="evidence"] .actions { grid-column: 1 / -1; }
    #review-workspace[data-view="evidence"] .evidence-heading { margin-bottom: 20px; }
  }
  @media (max-width: 1180px) {
    main { grid-template-columns: 250px minmax(0, 1fr); }
    #review-workspace .head { padding: 15px 17px 13px; }
    #review-workspace .head h1 { font-size: 16px; }
    .review-toolbar { gap: 6px; padding: 6px 11px; }
    .review-views button { padding: 7px 8px; font-size: 10px; }
    #unit-position { display: none; }
    #review-code .pane h2 { padding: 10px 12px; }
    #review-workspace .actions { padding: 12px 16px; }
    .review-buttons > .btn { padding: 7px 8px; }
    .review-buttons kbd.hint { display: none; }
    #t-conf { font: 9px var(--sans); }
    #t-conf .cbar { display: none; }
  }
  @media (max-width: 900px) {
    main { grid-template-columns: minmax(0, 1fr); }
    #unit-list { display: none; position: absolute; z-index: 12; inset: 0 auto 0 0; width: min(320px, 86vw); box-shadow: 16px 0 40px color-mix(in srgb, var(--ground) 35%, transparent); }
    main.units-open #unit-list { display: flex; }
    #unit-toggle { display: inline-flex; }
    #unit-close { display: block; }
    .units-heading kbd { display: none; }
    .review-toolbar { flex-wrap: wrap; }
    .review-views { flex: 1; }
    #notes { max-height: 26%; }
    #review-workspace .head .meta { margin-top: 8px; }
    #review-workspace .review-navigation { margin-left: auto; }
  }
  @media (max-width: 600px) {
    #review-workspace .head { padding: 12px 14px; }
    #review-workspace .head h1 { font-size: 14px; }
    #review-workspace .head .where { font-size: 10px; }
    .review-eyebrow { font-size: 8px; }
    #review-workspace .head .meta { gap: 5px; }
    #review-workspace .meta .verdict { font-size: 8px; padding: 2px 4px; }
    .review-toolbar { padding: 6px 10px; gap: 4px; }
    .review-views { order: 3; flex-basis: 100%; justify-content: space-between; }
    .review-views button { flex: 1; padding: 7px 5px; font-size: 10px; }
    .review-navigation { order: 2; }
    #unit-position { display: inline; }
    #review-code .pane h2 { min-height: 44px; font-size: 10px; padding: 7px 10px; }
    #review-code .pane h2 small { font-size: 9px; }
    #review-workspace[data-view="compare"] #review-code { grid-template-columns: minmax(0, 1fr); grid-template-rows: minmax(100px, 1fr) minmax(100px, 1fr); min-height: 230px; }
    #review-workspace[data-view="compare"] .proposal-pane { border-left: 0; border-top: 1px solid var(--line); }
    #notes { display: none; }
    #review-workspace[data-view="evidence"] #notes { display: block; }
    #review-workspace .actions { padding: 10px 12px; gap: 8px; }
    .review-fields { grid-template-columns: minmax(0, 1fr) 100px; gap: 8px; }
    .review-fields label { font-size: 10px; }
    .review-buttons { gap: 5px; }
    .review-buttons > .btn { padding: 7px; font-size: 10px; }
    #review-status { font-size: 9px; }
  }
  @media (max-height: 700px) and (min-width: 601px) {
    #review-workspace .head { padding-top: 11px; padding-bottom: 10px; }
    .review-eyebrow { display: none; }
    #notes { max-height: 22%; min-height: 55px; }
    #review-workspace[data-view="evidence"] #notes { max-height: none; min-height: 0; }
    #review-workspace .actions { padding-top: 10px; padding-bottom: 10px; }
  }
  @media (prefers-reduced-motion: reduce) {
    #unit-list *, #review-workspace * { animation: none !important; transition: none !important; }
  }
"""
