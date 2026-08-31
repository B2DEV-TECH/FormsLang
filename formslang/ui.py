"""The workbench UI: one self-contained HTML document.

No build step, no framework, no CDN. The page ships inside the Python
package and is served from localhost, because the data on screen is the
source code under review and it has no business travelling to a CDN to fetch
a font.

Everything the page shows comes from ``/api/state``; the page itself holds
no data and no secrets.
"""

from __future__ import annotations

INDEX_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>FormsLang Workbench</title>
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 512 512'%3E%3Cpath fill='%23F5A640' fill-rule='evenodd' d='M112 72H322V104H112C90 104 72 122 72 144V368C72 390 90 408 112 408H322V440H112C72 440 40 408 40 368V144C40 104 72 72 112 72ZM290 72H322V440H290Z'/%3E%3Crect x='322' y='112' width='92' height='24' rx='2' fill='%23F5A640'/%3E%3Crect x='322' y='160' width='132' height='24' rx='2' fill='%23F5A640'/%3E%3Crect x='322' y='208' width='104' height='24' rx='2' fill='%23F5A640'/%3E%3Crect x='322' y='256' width='148' height='24' rx='2' fill='%23F5A640'/%3E%3Crect x='322' y='304' width='116' height='24' rx='2' fill='%23F5A640'/%3E%3Crect x='322' y='352' width='140' height='24' rx='2' fill='%23F5A640'/%3E%3C/svg%3E">
<style>
  /* FormsLang commits to one visual world: a dark review room where the
     code under review is the brightest thing on screen. Single theme, chosen. */
  :root {
    --gold: #F5A640;
    --gold-deep: #C07F22;
    --gold-soft: rgba(245, 166, 64, .10);
    --gold-line: rgba(245, 166, 64, .38);
    --ground: #07090D;
    --panel: #0C1016;
    --raised: #11161E;
    --hover: #171D27;
    --line: #222937;
    --line-hi: #2E3746;
    --ink: #EEF1F6;
    --ink-dim: #9AA3B2;
    --ink-faint: #5B6472;
    --green: #4ADE80;
    --red: #F87171;
    --violet: #A78BFA;
    --blue: #7DABF8;
    --mono: "Cascadia Code", "Cascadia Mono", ui-monospace, Consolas, "JetBrains Mono", monospace;
    --sans: "Segoe UI Variable Text", "Segoe UI", -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
  }
  * { box-sizing: border-box; }
  html, body { height: 100%; }
  body {
    margin: 0; background: var(--ground); color: var(--ink);
    font: 14px/1.5 var(--sans); overflow: hidden;
    display: flex; flex-direction: column;
    -webkit-font-smoothing: antialiased;
  }
  button { font: inherit; cursor: pointer; }
  :focus-visible { outline: 2px solid var(--gold-line); outline-offset: 1px; border-radius: 4px; }
  ::selection { background: rgba(245,166,64,.28); }
  ::-webkit-scrollbar { width: 9px; height: 9px; }
  ::-webkit-scrollbar-thumb { background: #2A3140; border-radius: 8px; border: 2px solid transparent; background-clip: padding-box; }
  ::-webkit-scrollbar-thumb:hover { background: #39424f; background-clip: padding-box; border: 2px solid transparent; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-corner { background: transparent; }
  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { animation: none !important; transition: none !important; }
  }

  /* ── top bar ─────────────────────────────────────────── */
  header {
    display: flex; align-items: center; gap: 14px;
    height: 54px; padding: 0 16px; border-bottom: 1px solid var(--line);
    background: linear-gradient(180deg, #10151D, #0C1016);
  }
  .brand { display: flex; align-items: center; gap: 9px; font-weight: 650; letter-spacing: -0.01em; user-select: none; }
  .brand svg { width: 24px; height: 24px; display: block; filter: drop-shadow(0 0 10px rgba(245,166,64,.25)); }
  .brand .mark { color: var(--ink); font-size: 15px; }
  .brand small { color: var(--ink-faint); font-weight: 500; font-size: 10.5px; letter-spacing: .16em; text-transform: uppercase; }
  .session { color: var(--ink-dim); font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .spacer { flex: 1; }
  .chip {
    font: 11px/1 var(--mono); letter-spacing: .05em; text-transform: uppercase;
    padding: 6px 9px; border-radius: 5px; border: 1px solid var(--line); color: var(--ink-dim);
    white-space: nowrap; background: transparent; transition: border-color .14s, color .14s, background .14s;
  }
  .chip.provider { border-color: var(--gold-line); color: var(--gold); cursor: pointer; }
  .chip.provider:hover { background: var(--gold-soft); }
  .counts { display: flex; gap: 6px; font: 11px var(--mono); color: var(--ink-dim); }
  .counts span {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 5px 9px; border: 1px solid var(--line); border-radius: 20px; background: var(--panel);
  }
  .counts b { color: var(--ink); font-weight: 600; }
  .counts i { font-style: normal; width: 6px; height: 6px; border-radius: 50%; background: var(--ink-faint); }
  .counts .ok i { background: var(--green); } .counts .ok b { color: var(--green); }
  .counts .no i { background: var(--red); } .counts .no b { color: var(--red); }
  .counts .oc i { background: var(--gold); }
  .btn {
    background: transparent; color: var(--ink); border: 1px solid var(--line-hi);
    padding: 7px 13px; border-radius: 6px; transition: border-color .14s, color .14s, background .14s, transform .1s;
  }
  .btn:hover { border-color: var(--gold-deep); color: var(--gold); background: var(--gold-soft); }
  .btn:active { transform: translateY(1px); }
  .btn.primary {
    background: linear-gradient(180deg, #FFB44E, #EE9A2F); border-color: transparent;
    color: #1A1206; font-weight: 650; box-shadow: 0 1px 8px rgba(245,166,64,.22);
  }
  .btn.primary:hover { filter: brightness(1.07); color: #1A1206; }
  .btn:disabled { opacity: .38; cursor: not-allowed; transform: none; }
  #btn-module { font: 12px var(--mono); max-width: 280px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  #bar { height: 2px; background: linear-gradient(90deg, var(--gold-deep), var(--gold)); width: 0; transition: width .35s ease; box-shadow: 0 0 8px rgba(245,166,64,.4); }
  /* While a run is live the same bar stops meaning "decisions made" and
     starts meaning "the model is busy" -- so it moves instead of filling. */
  #bar.busy {
    width: 100% !important; transition: none;
    background-image: linear-gradient(90deg, transparent, var(--gold), transparent);
    background-size: 40% 100%; background-repeat: no-repeat;
    animation: sweep 1.15s ease-in-out infinite;
  }
  @keyframes sweep { from { background-position: -40% 0; } to { background-position: 140% 0; } }

  /* ── working: what the model is doing, while it does it ── */
  .spin {
    display: inline-block; width: 12px; height: 12px; flex: none;
    border: 2px solid var(--line-hi); border-top-color: var(--gold);
    border-radius: 50%; animation: spin .7s linear infinite;
  }
  .spin.big { width: 30px; height: 30px; border-width: 3px; }
  #working {
    display: flex; align-items: center; gap: 10px; padding: 8px 16px;
    border-bottom: 1px solid var(--gold-line); background: var(--gold-soft);
    color: var(--gold); font-size: 12.5px;
  }
  #working[hidden] { display: none; }
  #working .what b { color: var(--ink); font: 600 12px var(--mono); }
  #working .mono { font: 11px var(--mono); color: var(--ink-dim); letter-spacing: .04em; white-space: nowrap; }
  .pane-busy {
    position: absolute; inset: 0; z-index: 3; padding: 24px; text-align: center;
    display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 11px;
    background: rgba(9,12,17,.93);
  }
  .pane-busy[hidden] { display: none; }
  .qtag {
    font: 10px var(--mono); letter-spacing: .1em; color: var(--gold);
    border: 1px solid var(--gold-line); border-radius: 4px; padding: 2px 6px;
    background: var(--gold-soft); animation: pulse 1.6s ease-in-out infinite;
  }
  .qtag[hidden] { display: none; }
  @keyframes pulse { 50% { opacity: .45; } }
  .pane-busy strong { font: 600 14px var(--sans); color: var(--ink); }
  .pane-busy span.sub { font-size: 12.5px; color: var(--ink-dim); max-width: 330px; line-height: 1.55; }
  .pane-busy .tick { font: 11px var(--mono); letter-spacing: .1em; text-transform: uppercase; color: var(--gold); }

  /* ── layout ──────────────────────────────────────────── */
  main { display: grid; grid-template-columns: 330px 1fr; flex: 1; min-height: 0; }
  aside { border-right: 1px solid var(--line); display: flex; flex-direction: column; min-height: 0; background: var(--panel); }
  /* Two filter rows, never one: "converted" and "decided" are different
     questions, and putting them in the same row of buttons taught people
     they were the same question. */
  .filters { display: flex; flex-direction: column; gap: 7px; padding: 11px 10px; border-bottom: 1px solid var(--line); }
  .frow { display: flex; align-items: center; gap: 4px; flex-wrap: wrap; }
  .flabel {
    font: 10px var(--mono); letter-spacing: .12em; text-transform: uppercase;
    color: var(--ink-faint); flex: 0 0 68px;
  }
  .frow button {
    background: transparent; border: 1px solid transparent; color: var(--ink-dim);
    font: 11px var(--mono); text-transform: uppercase; letter-spacing: .05em;
    padding: 4px 9px; border-radius: 20px; transition: color .12s, border-color .12s, background .12s;
  }
  .frow button:hover { color: var(--ink); background: var(--hover); }
  .frow button.on { border-color: var(--gold-line); color: var(--gold); background: var(--gold-soft); }
  .search { padding: 9px 10px; border-bottom: 1px solid var(--line); }
  .search input {
    width: 100%; background: var(--ground); border: 1px solid var(--line); color: var(--ink);
    padding: 8px 10px; border-radius: 6px; font: 12px var(--mono); transition: border-color .14s;
  }
  .search input::placeholder { color: var(--ink-faint); }
  .search input:focus { outline: none; border-color: var(--gold-deep); }
  #list { overflow-y: auto; flex: 1; padding: 3px 0; }
  .row {
    display: grid; grid-template-columns: 16px 1fr auto; gap: 8px; align-items: center;
    padding: 8px 12px 8px 10px; margin: 1px 6px; border-radius: 7px; cursor: pointer;
    border-left: 2px solid transparent; transition: background .1s;
  }
  .row:hover { background: var(--hover); }
  .row.sel { background: var(--raised); border-left-color: var(--gold); }
  .row.queued { background: rgba(245,166,64,.045); }
  .row.working { background: var(--gold-soft); border-left-color: var(--gold-deep); }
  .row.working .title { color: var(--gold); }
  .row .state .spin { width: 10px; height: 10px; border-width: 2px; vertical-align: -1px; }
  .row .state { font-size: 11px; text-align: center; }
  .row > div:nth-child(2) { min-width: 0; }
  .row .title { font: 12px var(--mono); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .row .sub { font-size: 11px; color: var(--ink-faint); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .verdict {
    font: 10px var(--mono); padding: 2px 6px; border-radius: 4px; letter-spacing: .05em;
    border: 1px solid currentColor; background: color-mix(in srgb, currentColor 8%, transparent);
  }
  .v-AUTO { color: var(--green); } .v-ASSISTED { color: var(--gold); }
  .v-MANUAL { color: var(--red); } .v-DROP { color: var(--ink-dim); }
  .v-UNKNOWN { color: var(--violet); }

  /* Risk and behaviour ride the same badge shape as the verdict: three
     short words in a row read as one sentence, and nothing new competes
     with the code for attention. */
  .r-LOW { color: var(--ink-dim); } .r-MEDIUM { color: var(--gold); }
  .r-HIGH { color: #FB923C; } .r-CRITICAL { color: var(--red); }
  .bh-PRESERVED { color: var(--green); } .bh-CHANGED { color: var(--red); }
  .bh-UNCERTAIN { color: var(--violet); }
  /* In the list a dot is enough: LOW nearly disappears, CRITICAL does not. */
  .rdot { width: 6px; height: 6px; border-radius: 50%; background: currentColor; flex: 0 0 6px; }
  .rdot.r-LOW { opacity: .28; }
  .row .rside { display: flex; align-items: center; gap: 7px; }
  .st-approved { color: var(--green); } .st-rejected { color: var(--red); }
  .st-needs_work { color: var(--gold); } .st-pending { color: var(--ink-faint); }

  /* ── detail ──────────────────────────────────────────── */
  section { position: relative; display: flex; flex-direction: column; min-width: 0; min-height: 0; }
  .head { padding: 13px 18px; border-bottom: 1px solid var(--line); background: var(--panel); }
  .head h1 { margin: 0; font: 600 17px var(--mono); letter-spacing: -0.01em; }
  .head .where { margin-top: 3px; font-size: 12px; color: var(--ink-faint); }
  .head .where b { color: var(--ink-dim); font-weight: 500; }
  .head .meta { margin-top: 8px; display: flex; gap: 10px; align-items: center; flex-wrap: wrap; color: var(--ink-dim); font-size: 12px; }
  .panes { flex: 1; display: grid; grid-template-columns: 1fr 1fr; min-height: 0; }
  .pane { display: flex; flex-direction: column; min-width: 0; min-height: 0; position: relative; }
  .pane + .pane { border-left: 1px solid var(--line); }
  .pane h2 {
    /* above the busy overlay: which pane is covered stays readable */
    position: relative; z-index: 4;
    margin: 0; padding: 8px 14px; font: 11px var(--mono); letter-spacing: .12em;
    text-transform: uppercase; color: var(--ink-dim); border-bottom: 1px solid var(--line);
    display: flex; justify-content: space-between; align-items: center; background: var(--panel);
  }
  .code { flex: 1; overflow: auto; margin: 0; }
  pre.code { padding: 12px 14px 12px 0; font: 12.5px/1.65 var(--mono); color: #CBD3DF; tab-size: 4; }
  pre.code .ln { display: inline-block; width: 48px; padding-right: 13px; text-align: right; color: #38404F; user-select: none; }
  /* PL/SQL, lit like a code editor: keywords gold, strings green-grey,
     comments sunk, bind variables violet — the code under review is the star. */
  .k { color: var(--gold); }
  .s { color: #A3C9A8; }
  .c { color: #4E586A; font-style: italic; }
  .n { color: #D6B4FA; }
  .b { color: var(--blue); }
  textarea.code {
    background: #090C11; color: #CBD3DF; border: 0; padding: 12px 14px;
    font: 12.5px/1.65 var(--mono); resize: none; width: 100%; tab-size: 4;
  }
  textarea.code::placeholder { color: var(--ink-faint); }
  textarea.code:focus { outline: none; box-shadow: inset 0 0 0 1px var(--gold-line); }
  .empty { padding: 40px 20px; text-align: center; color: var(--ink-dim); }
  .empty kbd, kbd.key {
    display: inline-block; border: 1px solid var(--line-hi); border-bottom-width: 2px; border-radius: 4px;
    padding: 1px 6px; font: 11px var(--mono); color: var(--gold); background: var(--raised);
  }

  .notes { border-top: 1px solid var(--line); max-height: 30%; overflow-y: auto; padding: 12px 18px; background: var(--panel); }
  .notes h3 { margin: 0 0 6px; font: 11px var(--mono); letter-spacing: .12em; text-transform: uppercase; color: var(--ink-dim); }
  .notes ul { margin: 0 0 12px; padding-left: 18px; }
  .notes li { margin: 3px 0; color: #B4BCC8; font-size: 13px; }
  .notes li.q { color: var(--gold); }
  .notes li code { font: 12px var(--mono); color: var(--ink); }
  /* Collapsed by default. The evidence is always there, and never in the way. */
  .notes details { margin: 0 0 8px; }
  .notes details > summary {
    cursor: pointer; list-style: none; display: flex; align-items: center; gap: 8px;
    font: 11px var(--mono); letter-spacing: .12em; text-transform: uppercase;
    color: var(--ink-dim); padding: 3px 0;
  }
  .notes details > summary::-webkit-details-marker { display: none; }
  .notes details > summary::before { content: "▸"; font-size: 9px; color: var(--ink-faint); }
  .notes details[open] > summary::before { content: "▾"; }
  .notes details > summary:hover { color: var(--ink); }
  .notes details ul { margin: 4px 0 10px; }
  .notes .pts { font: 10px var(--mono); color: var(--ink-faint); }
  .notes .ev { display: block; color: var(--ink-faint); font: 11px var(--mono); margin-left: 2px; }
  .notes .why { color: var(--ink-dim); font-size: 12px; margin: 0 0 8px; }
  /* The edge kind, ahead of the thing it points at: "calls", "queries". */
  .notes .dep-k { color: var(--ink-faint); font: 10px var(--mono); text-transform: uppercase; letter-spacing: .04em; }
  /* One test case: its origin badge, its Given/When/Then, its verdict row. */
  .notes .tc { border-left: 2px solid var(--line); padding: 0 0 0 10px; margin: 0 0 10px; }
  .notes .tc.answered { border-left-color: var(--line-hi); }
  .notes .tc-h { display: flex; align-items: baseline; gap: 6px; flex-wrap: wrap; margin-bottom: 3px; }
  .notes .tc-t { color: var(--ink); font-size: 13px; }
  .notes .tc-k { color: var(--ink-faint); font: 10px var(--mono); text-transform: uppercase; letter-spacing: .04em; }
  /* Where the expectation comes from -- the one thing a reviewer must not
     have to guess. Gold means the rules could not establish it. */
  .notes .org { font: 10px var(--mono); padding: 1px 5px; border-radius: 3px; border: 1px solid var(--line-hi); color: var(--ink-dim); }
  .notes .org.o-FORMS_BEHAVIOR { color: var(--green); border-color: rgba(74,222,128,.35); }
  .notes .org.o-MODERNIZATION { color: var(--ink-dim); }
  .notes .org.o-NEEDS_CONFIRMATION { color: var(--gold); border-color: var(--gold-deep); }
  .notes .gwt { margin: 2px 0 4px; padding-left: 14px; }
  .notes .gwt li { font-size: 12px; }
  .notes .gwt b { color: var(--ink-faint); font: 10px var(--mono); text-transform: uppercase; letter-spacing: .04em; }
  .notes .tc-a { display: flex; gap: 4px; align-items: center; margin-top: 4px; }
  .notes .tc-a button {
    background: none; border: 1px solid var(--line); color: var(--ink-faint);
    border-radius: 4px; padding: 1px 7px; font: 10px var(--mono);
  }
  .notes .tc-a button:hover { color: var(--ink); border-color: var(--line-hi); }
  .notes .tc-a button.on { color: var(--gold); border-color: var(--gold-deep); background: var(--gold-soft); }
  .notes .tc-a .said { color: var(--ink-faint); font: 10px var(--mono); }
  .conf { display: flex; align-items: center; gap: 8px; font: 11px var(--mono); color: var(--ink-dim); text-transform: none; letter-spacing: 0; }
  .conf .cbar { width: 90px; height: 5px; background: var(--line); border-radius: 3px; overflow: hidden; }
  .conf .cbar i { display: block; height: 100%; border-radius: 3px; transition: width .3s; }
  .err { color: var(--red); font: 12px var(--mono); }

  .actions { display: flex; gap: 8px; align-items: center; padding: 10px 18px; border-top: 1px solid var(--line); background: var(--raised); }
  .actions input {
    flex: 1; background: var(--ground); border: 1px solid var(--line); color: var(--ink);
    padding: 8px 10px; border-radius: 6px; font-size: 13px; transition: border-color .14s;
  }
  .actions input::placeholder { color: var(--ink-faint); }
  .actions input:focus { outline: none; border-color: var(--gold-deep); }
  .btn.approve:hover { border-color: var(--green); color: var(--green); background: rgba(74,222,128,.08); }
  .btn.reject:hover { border-color: var(--red); color: var(--red); background: rgba(248,113,113,.08); }
  kbd.hint {
    margin-left: 4px; border: 1px solid var(--line-hi); border-bottom-width: 2px; border-radius: 3px;
    padding: 0 4px; color: var(--ink-faint); font: 10px var(--mono); background: var(--panel);
  }

  #toast {
    position: fixed; bottom: 18px; right: 18px; max-width: 440px; z-index: 40;
    background: var(--raised); border: 1px solid var(--line-hi); border-left: 3px solid var(--gold);
    padding: 11px 15px; border-radius: 8px; font-size: 13px; opacity: 0;
    transform: translateY(10px); transition: opacity .18s, transform .18s; pointer-events: none;
    box-shadow: 0 12px 40px rgba(0,0,0,.5);
  }
  #toast.show { opacity: 1; transform: none; }
  #toast.bad { border-left-color: var(--red); }

  /* ── first-run banner + settings sheet ───────────────── */
  #setup-banner {
    display: flex; align-items: center; gap: 12px; padding: 8px 16px;
    background: var(--gold-soft); border-bottom: 1px solid var(--gold-line);
    color: var(--ink-dim); font-size: 13px;
  }
  #setup-banner[hidden] { display: none; }
  #setup-banner b { color: var(--gold); font-weight: 600; }
  .settings-form {
    display: grid; gap: 12px; padding: 16px 24px 4px;
    border-top: 1px solid var(--line); margin-top: 10px;
  }
  .settings-form label {
    display: grid; gap: 5px; color: var(--ink-dim);
    font: 10px var(--mono); letter-spacing: .08em; text-transform: uppercase;
  }
  .settings-form input {
    background: var(--ground); border: 1px solid var(--line); color: var(--ink);
    padding: 9px 10px; border-radius: 6px; font: 12px var(--mono);
    text-transform: none; letter-spacing: 0; transition: border-color .14s;
  }
  .settings-form input::placeholder { color: var(--ink-faint); }
  .settings-form input:focus { outline: none; border-color: var(--gold-deep); }
  .settings-form .duo { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  .keyline { display: flex; align-items: center; gap: 10px; font-size: 12px; color: var(--ink-faint); flex-wrap: wrap; }
  .keyline i { font-style: normal; color: var(--green); }
  .keyline.warn i, .keyline.warn span { color: var(--red); }
  .keyline .forget {
    background: none; border: none; color: var(--ink-dim);
    text-decoration: underline; font-size: 11px; padding: 0;
  }
  .keyline .forget:hover { color: var(--red); }
  .testrow { display: flex; align-items: center; gap: 10px; min-height: 30px; }
  .testrow .out { font: 12px var(--mono); }
  .testrow .out.ok { color: var(--green); }
  .testrow .out.bad { color: var(--red); }

  /* ── welcome: the first thing a new install shows ────── */
  #welcome {
    position: absolute; inset: 0; z-index: 10; display: none;
    align-items: center; justify-content: center; background:
      radial-gradient(900px 480px at 50% -10%, rgba(245,166,64,.07), transparent 60%),
      var(--ground);
  }
  #welcome.show { display: flex; }
  .hello { max-width: 620px; padding: 32px; text-align: center; animation: rise .4s ease both; }
  @keyframes rise { from { opacity: 0; transform: translateY(10px); } }
  .hello svg { width: 72px; height: 72px; margin-bottom: 18px; filter: drop-shadow(0 6px 30px rgba(245,166,64,.35)); }
  .hello h1 { margin: 0 0 8px; font-size: 26px; font-weight: 650; letter-spacing: -0.02em; text-wrap: balance; }
  .hello h1 em { font-style: normal; color: var(--gold); }
  .hello > p { margin: 0 auto 26px; max-width: 46ch; color: var(--ink-dim); font-size: 14.5px; }
  .steps { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 28px; }
  .step { border: 1px solid var(--line); border-radius: 10px; padding: 14px 12px; background: var(--panel); text-align: left; }
  .step b { display: block; font: 600 12.5px var(--sans); margin-bottom: 3px; }
  .step span { font-size: 11.5px; color: var(--ink-faint); line-height: 1.45; display: block; }
  .step .no { font: 700 10px var(--mono); color: var(--gold); letter-spacing: .1em; display: block; margin-bottom: 8px; }
  .hello .cta { display: flex; gap: 12px; align-items: center; justify-content: center; }
  .hello .cta .btn.primary { padding: 11px 22px; font-size: 14px; border-radius: 8px; }
  .hello .cta .or { color: var(--ink-faint); font-size: 12px; }
  .hello .local { margin-top: 26px; color: var(--ink-faint); font-size: 11.5px; display: flex; gap: 7px; align-items: center; justify-content: center; }
  .hello .local i { font-style: normal; color: var(--green); }
  .hello .local.legal { margin-top: 9px; }

  /* ── overlay: pick a module, pick a model ────────────── */
  .modal {
    position: fixed; inset: 0; background: rgba(2, 4, 8, .82); display: none;
    align-items: center; justify-content: center; padding: 24px; z-index: 20;
    backdrop-filter: blur(8px);
  }
  .modal.show { display: flex; }
  .sheet {
    position: relative; overflow: hidden; background: #10151D;
    border: 1px solid var(--line-hi); border-radius: 14px;
    width: min(980px, 100%); max-height: calc(100vh - 48px); display: flex; flex-direction: column;
    box-shadow: 0 32px 90px rgba(0,0,0,.72), 0 0 0 1px rgba(245,166,64,.04);
    animation: sheet .22s ease both;
  }
  @keyframes sheet { from { opacity: 0; transform: translateY(10px) scale(.99); } }
  .sheet::before {
    content: ""; position: absolute; inset: 0 0 auto; height: 2px;
    background: linear-gradient(90deg, var(--gold), #FFD285 48%, transparent 88%);
  }
  .sheet-head {
    display: grid; grid-template-columns: auto 1fr auto; align-items: center; gap: 16px; padding: 22px 24px 16px;
    border-bottom: 1px solid var(--line);
  }
  .sheet-head h2 { margin: 0; font-size: 20px; line-height: 1.15; font-weight: 650; letter-spacing: -.02em; }
  .sheet-head .path { font: 11px var(--mono); color: var(--ink-faint); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .sheet-head #modal-close { grid-column: 3; grid-row: 1; }
  .sheet > .hint { padding: 12px 24px 0; font-size: 13px; color: var(--ink-dim); }
  .sheet-body { overflow-y: auto; padding: 12px 0; min-height: 160px; }
  .sheet-foot { padding: 14px 24px 18px; border-top: 1px solid var(--line); display: flex; gap: 10px; align-items: center; background: #0C1016; }
  .sheet-foot input {
    flex: 1; background: var(--ground); border: 1px solid var(--line); color: var(--ink);
    padding: 11px 12px; border-radius: 7px; font: 12px var(--mono); transition: border-color .14s;
  }
  .sheet-foot input::placeholder { color: var(--ink-faint); }
  .sheet-foot input:focus { outline: none; border-color: var(--gold-deep); }
  .entry {
    display: flex; align-items: center; gap: 12px; padding: 11px 14px; cursor: pointer;
    border: 1px solid transparent; border-radius: 8px; transition: background .1s, border-color .1s;
  }
  .entry:hover { background: var(--hover); border-color: var(--line-hi); }
  .entry .icon { width: 32px; height: 32px; flex: 0 0 32px; display: grid; place-items: center; color: var(--ink-dim); border-radius: 7px; background: #1E2430; font: 10px var(--mono); }
  .entry .name { flex: 1; font: 13px var(--mono); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .entry .tag { font: 10px var(--mono); color: var(--ink-faint); text-transform: uppercase; letter-spacing: .06em; }
  .entry.dir .name { color: #B4BCC8; }
  .entry.mod .name { color: var(--ink); }
  .entry.mod .icon { color: #1D1305; background: var(--gold); font-weight: 800; }
  .entry.mod.xml .icon { color: #D8C9FF; background: #322A4C; }
  .entry.off { opacity: .45; cursor: not-allowed; }
  .entry.off:hover { background: none; border-color: transparent; }
  .entry.on { background: var(--raised); border-color: var(--gold-line); }
  .group { padding: 12px 2px 7px; font: 10px var(--mono); letter-spacing: .12em; text-transform: uppercase; color: var(--ink-faint); }
  .sheet .hint { padding: 4px 18px 10px; font-size: 12px; color: var(--ink-dim); }
  .picker-shell { padding: 4px 24px 12px; }
  .picker-hero { display: grid; grid-template-columns: 1.2fr .8fr; gap: 16px; margin-bottom: 18px; }
  .dropzone {
    min-height: 150px; border: 1px dashed #4A5261; border-radius: 12px;
    background: linear-gradient(135deg, rgba(245,166,64,.08), rgba(245,166,64,.015));
    display: flex; align-items: center; gap: 18px; padding: 24px; transition: border-color .16s, background .16s;
  }
  .dropzone:hover, .dropzone.drag { border-color: var(--gold); background: rgba(245,166,64,.11); }
  .dropmark { flex: 0 0 64px; height: 72px; display: grid; place-items: center; border-radius: 12px; background: linear-gradient(180deg, #FFB44E, #E1912B); color: #201404; font: 800 15px var(--mono); box-shadow: 0 10px 28px rgba(245,166,64,.2); }
  .dropcopy { flex: 1; min-width: 0; }
  .dropcopy strong { display: block; font-size: 16px; margin-bottom: 4px; }
  .dropcopy p { margin: 0 0 14px; color: var(--ink-faint); font-size: 12px; }
  .picker-info { border: 1px solid var(--line); border-radius: 12px; padding: 18px; background: #0C1016; }
  .picker-info strong { display: block; margin-bottom: 8px; }
  .picker-info p { margin: 0 0 10px; color: var(--ink-faint); font-size: 12px; }
  .safety { display: flex; gap: 8px; align-items: flex-start; color: #9ECBB0; font-size: 11px; }
  .safety i { color: var(--green); font-style: normal; }
  .picker-nav { display: flex; gap: 8px; align-items: center; padding: 10px 0; border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); }
  .picker-nav .current { flex: 1; min-width: 0; font: 11px var(--mono); color: var(--ink-faint); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .picker-files { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 6px; padding-top: 8px; }
  .picker-empty { grid-column: 1 / -1; padding: 26px; border: 1px dashed var(--line); border-radius: 10px; text-align: center; color: var(--ink-dim); }
  .uploading { padding: 54px 24px; text-align: center; }
  .uploading .spinner { width: 34px; height: 34px; margin: 0 auto 16px; border: 3px solid #2A313E; border-top-color: var(--gold); border-radius: 50%; animation: spin .8s linear infinite; }
  .uploading strong { display: block; font-size: 16px; }
  .uploading span { display: block; margin-top: 6px; color: var(--ink-dim); }
  @keyframes spin { to { transform: rotate(360deg); } }
  .export-form { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; padding: 12px 18px 18px; }
  .export-form label { display: grid; gap: 6px; color: var(--ink-dim); font: 10px var(--mono); letter-spacing: .06em; text-transform: uppercase; }
  .export-form label.wide { grid-column: 1 / -1; }
  .export-form input {
    background: var(--ground); border: 1px solid var(--line); color: var(--ink);
    padding: 9px 10px; border-radius: 6px; font: 12px var(--mono); text-transform: none; transition: border-color .14s;
  }
  .export-form input:focus { outline: none; border-color: var(--gold-deep); }
  .exports-list { display: grid; gap: 8px; padding: 12px 18px 18px; }
  .exports-list .exp-row { display: flex; align-items: center; gap: 12px; padding: 10px 14px; border: 1px solid var(--line); border-radius: 8px; background: var(--panel); }
  .exports-list .exp-row.fresh { border-color: var(--gold-line); background: var(--gold-soft); }
  .exports-list .exp-name { font: 12px var(--mono); overflow-wrap: anywhere; }
  .exports-list .exp-meta { margin-left: auto; white-space: nowrap; color: var(--ink-dim); font: 10px var(--mono); letter-spacing: .05em; }
  .exports-list .empty { color: var(--ink-dim); padding: 8px 2px; }
  /* the project view: counts first, and the one score with its own arithmetic
     printed beside it -- a number nobody can check is a number nobody should
     act on. */
  .dash { padding: 4px 24px 22px; display: grid; gap: 18px; }
  .dash h3 { margin: 0 0 8px; font: 10px var(--mono); letter-spacing: .12em; text-transform: uppercase; color: var(--ink-faint); font-weight: 500; }
  .dash .card { border: 1px solid var(--line); border-radius: 10px; background: #0C1016; padding: 14px 16px; }
  .dash .none { color: var(--ink-faint); font-size: 12.5px; padding: 2px; }
  .ready { display: grid; grid-template-columns: 210px 1fr; gap: 20px; align-items: start; }
  .ready .num { font: 650 46px var(--sans); letter-spacing: -.03em; color: var(--gold); line-height: 1; }
  .ready .of { color: var(--ink-faint); font: 11px var(--mono); letter-spacing: .06em; }
  .ready .gauge { height: 6px; background: var(--line); border-radius: 4px; margin-top: 11px; overflow: hidden; }
  .ready .gauge i { display: block; height: 100%; background: linear-gradient(90deg, var(--gold-deep), var(--gold)); }
  .ready .caveat { margin-top: 11px; color: var(--ink-dim); font-size: 12px; line-height: 1.5; }
  .ready .ver { margin-top: 8px; color: var(--ink-faint); font: 10px var(--mono); word-break: break-all; }
  .formula { width: 100%; border-collapse: collapse; font-size: 12.5px; }
  .formula th { text-align: left; padding: 4px 8px; border-bottom: 1px solid var(--line); color: var(--ink-faint); font: 10px var(--mono); letter-spacing: .1em; text-transform: uppercase; font-weight: 500; }
  .formula td { padding: 6px 8px; border-bottom: 1px solid var(--line); vertical-align: top; }
  .formula td.n { text-align: right; white-space: nowrap; font: 12px var(--mono); }
  .formula .d { margin-top: 2px; color: var(--ink-faint); font-size: 11px; line-height: 1.45; }
  .formula tr.sum td { border-bottom: none; color: var(--ink); }
  .kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(118px, 1fr)); gap: 10px; }
  .kpi { border: 1px solid var(--line); border-radius: 9px; padding: 11px 13px; background: var(--panel); }
  .kpi b { display: block; font: 600 21px var(--sans); letter-spacing: -.02em; }
  .kpi span { color: var(--ink-faint); font: 10px var(--mono); text-transform: uppercase; letter-spacing: .08em; }
  .dists { display: grid; grid-template-columns: repeat(auto-fit, minmax(238px, 1fr)); gap: 14px; }
  .brow { display: grid; grid-template-columns: 104px 1fr 30px; gap: 8px; align-items: center; margin: 5px 0; font: 11px var(--mono); }
  .brow .track { height: 7px; background: var(--line); border-radius: 4px; overflow: hidden; }
  .brow .track i { display: block; height: 100%; background: currentColor; border-radius: 4px; }
  .brow .cnt { text-align: right; }
  .dist .cap { margin-top: 8px; color: var(--ink-faint); font-size: 11px; line-height: 1.45; }
  .blk { display: flex; gap: 10px; align-items: baseline; padding: 7px 11px; margin-bottom: 6px; border-left: 2px solid var(--gold-deep); background: var(--gold-soft); border-radius: 0 6px 6px 0; }
  .blk b { flex: 0 0 auto; font: 600 12px var(--mono); color: var(--gold); }
  .blk span { color: #B4BCC8; font-size: 12.5px; }
  .dtable { width: 100%; border-collapse: collapse; font-size: 12.5px; }
  .dtable th { text-align: left; padding: 4px 8px; border-bottom: 1px solid var(--line); color: var(--ink-faint); font: 10px var(--mono); letter-spacing: .1em; text-transform: uppercase; font-weight: 500; }
  .dtable td { padding: 6px 8px; border-bottom: 1px solid var(--line); vertical-align: top; }
  .dtable tr:last-child td { border-bottom: none; }
  .dtable tr.pick { cursor: pointer; }
  .dtable tr.pick:hover td { background: var(--hover); }
  .dtable .mono { font: 12px var(--mono); }
  .dtable .sub { margin-top: 2px; color: var(--ink-faint); font-size: 11px; line-height: 1.4; }
  .dtable td.n { text-align: right; white-space: nowrap; font: 12px var(--mono); }
  @media (max-width: 760px) {
    .modal { padding: 10px; } .sheet { max-height: calc(100vh - 20px); }
    .picker-hero, .picker-files, .export-form { grid-template-columns: 1fr; }
    .picker-info { display: none; } .export-form label.wide { grid-column: auto; }
    .steps { grid-template-columns: 1fr; }
    .ready { grid-template-columns: 1fr; }
  }
</style>
</head>
<body>

<header>
  <div class="brand">
    <svg viewBox="0 0 512 512" aria-hidden="true"><path fill="#F5A640" fill-rule="evenodd" d="M112 72H322V104H112C90 104 72 122 72 144V368C72 390 90 408 112 408H322V440H112C72 440 40 408 40 368V144C40 104 72 72 112 72ZM290 72H322V440H290Z"/><rect x="322" y="112" width="92" height="24" rx="2" fill="#F5A640"/><rect x="322" y="160" width="132" height="24" rx="2" fill="#F5A640"/><rect x="322" y="208" width="104" height="24" rx="2" fill="#F5A640"/><rect x="322" y="256" width="148" height="24" rx="2" fill="#F5A640"/><rect x="322" y="304" width="116" height="24" rx="2" fill="#F5A640"/><rect x="322" y="352" width="140" height="24" rx="2" fill="#F5A640"/></svg>
    <span class="mark">FormsLang</span> <small>Workbench &middot; by B2DEV TECH</small>
  </div>
  <button class="btn" id="btn-module" title="Pick another Forms module">—</button>
  <div class="spacer"></div>
  <div class="counts" id="counts"></div>
  <span class="chip provider" id="provider" title="Pick the model that converts">—</span>
  <button class="btn" id="btn-settings" title="Settings — model, API key, CLI">&#9881;</button>
  <button class="btn" id="btn-propose-all">Convert unconverted</button>
  <button class="btn" id="btn-dash" title="Project view — what this session says, counted">Project</button>
  <button class="btn" id="btn-exports" title="Exported ZIPs — open in folder">Exports</button>
  <button class="btn primary" id="btn-export">Export APEX 26.1</button>
</header>
<div id="bar"></div>
<div id="working" hidden>
  <span class="spin"></span>
  <span class="what" id="working-what"></span>
  <span class="spacer"></span>
  <span class="mono" id="working-meta"></span>
</div>
<div id="setup-banner" hidden>
  <span><b>Offline mode</b> — conversions are placeholders until you pick a model. Hand-written APEX works either way.</span>
  <div class="spacer"></div>
  <button class="btn primary" id="setup-open">Choose a model</button>
  <button class="btn" id="setup-later">Later</button>
</div>

<main>
  <aside>
    <div class="filters">
      <div class="frow"><span class="flabel">Conversion</span><span id="f-conv"></span></div>
      <div class="frow"><span class="flabel">Your call</span><span id="f-call"></span></div>
      <div class="frow"><span class="flabel">Risk</span><span id="f-risk"></span></div>
    </div>
    <div class="search"><input id="q" placeholder="filter by name, block or built-in…" spellcheck="false"></div>
    <div id="list"></div>
  </aside>

  <section>
    <div class="head">
      <h1 id="t-title">—</h1>
      <div class="where" id="t-where"></div>
      <div class="meta" id="t-meta"></div>
    </div>
    <div class="panes">
      <div class="pane">
        <h2><span>Oracle Forms — what runs today</span><span id="t-lines"></span></h2>
        <pre class="code" id="src"></pre>
      </div>
      <div class="pane">
        <h2>
          <span>Oracle APEX — what would replace it · editable</span>
          <span class="qtag" id="out-queued" hidden>in queue</span>
          <span class="conf" id="t-conf"></span>
        </h2>
        <textarea class="code" id="out" spellcheck="false" placeholder="No proposal yet — write the APEX replacement here yourself, or press P to ask the model."></textarea>
        <div class="pane-busy" id="out-busy" hidden>
          <div class="spin big"></div>
          <strong id="busy-title"></strong>
          <span class="sub" id="busy-sub"></span>
          <span class="tick" id="busy-tick"></span>
        </div>
      </div>
    </div>
    <div class="notes" id="notes"></div>
    <div class="actions">
      <button class="btn approve" id="btn-approve">Approve <kbd class="hint">A</kbd></button>
      <button class="btn" id="btn-needs">Needs work <kbd class="hint">W</kbd></button>
      <button class="btn reject" id="btn-reject">Reject <kbd class="hint">R</kbd></button>
      <button class="btn" id="btn-propose">Convert <kbd class="hint">P</kbd></button>
      <input id="comment" placeholder="reviewer note (optional)">
      <input id="reviewer" placeholder="your name" style="flex:0 0 140px">
    </div>

    <div id="welcome">
      <div class="hello">
        <svg viewBox="0 0 512 512" aria-hidden="true"><path fill="#F5A640" fill-rule="evenodd" d="M112 72H322V104H112C90 104 72 122 72 144V368C72 390 90 408 112 408H322V440H112C72 440 40 408 40 368V144C40 104 72 72 112 72ZM290 72H322V440H290Z"/><rect x="322" y="112" width="92" height="24" rx="2" fill="#F5A640"/><rect x="322" y="160" width="132" height="24" rx="2" fill="#F5A640"/><rect x="322" y="208" width="104" height="24" rx="2" fill="#F5A640"/><rect x="322" y="256" width="148" height="24" rx="2" fill="#F5A640"/><rect x="322" y="304" width="116" height="24" rx="2" fill="#F5A640"/><rect x="322" y="352" width="140" height="24" rx="2" fill="#F5A640"/></svg>
        <h1>Your Forms code, read <em>one unit at a time</em></h1>
        <p>Open an Oracle Forms module and FormsLang turns every trigger and
           program unit into a reviewable APEX proposal — you approve each one.</p>
        <div class="steps">
          <div class="step"><span class="no">01 · IMPORT</span><b>Open the .fmb</b><span>Oracle's own converter reads it. Your source tree is never written to.</span></div>
          <div class="step"><span class="no">02 · CONVERT</span><b>Ask your model</b><span>Every proposal is a draft with a confidence score and open questions.</span></div>
          <div class="step"><span class="no">03 · REVIEW</span><b>Decide and export</b><span>Approve, reject or edit — only approved code enters the APEX package.</span></div>
        </div>
        <div class="cta">
          <button class="btn primary" id="welcome-open">Open a Forms module</button>
          <span class="or">or press <kbd class="key">O</kbd></span>
        </div>
        <div class="local"><i>&#10003;</i> Runs entirely on this machine — code goes only to the model you configure.</div>
        <div class="local legal">FormsLang &middot; created by Geraldo Viana Jr &middot; Apache-2.0 open source &middot; b2dev.tech</div>
      </div>
    </div>
  </section>
</main>

<div class="modal" id="modal">
  <div class="sheet">
    <div class="sheet-head">
      <h2 id="modal-title"></h2>
      <div class="path" id="modal-path"></div>
      <button class="btn" id="modal-close">Close</button>
    </div>
    <div class="hint" id="modal-hint"></div>
    <div class="sheet-body" id="modal-body"></div>
    <div class="sheet-foot" id="modal-foot">
      <input id="modal-input" list="modal-models" spellcheck="false">
      <datalist id="modal-models"></datalist>
      <button class="btn primary" id="modal-go">Open</button>
    </div>
  </div>
</div>

<div id="toast"></div>

<script>
const $ = (id) => document.getElementById(id);

/* Two independent axes. A unit can be converted and still undecided, so the
   two questions get two rows of buttons and never share a word. */
const CONV = [["all", "all"], ["unconverted", "not converted"], ["converted", "converted"]];
const CALL = [["all", "all"], ["pending", "undecided"], ["approved", "approved"],
              ["needs_work", "needs work"], ["rejected", "rejected"]];
const MARK = { approved: "✓", rejected: "✕", needs_work: "⚠", pending: "●" };
/* What the catalog verdict means, on hover -- the colours alone taught nobody. */
const VERDICT_HELP = {
  AUTO: "AUTO — direct APEX equivalent. Machine converts, you review.",
  ASSISTED: "ASSISTED — the intent translates, the form does not. Read this one carefully.",
  MANUAL: "MANUAL — no APEX equivalent. Needs a redesign decision, not a translation.",
  DROP: "DROP — solves a problem APEX does not have. It disappears, and that is a gain.",
  UNKNOWN: "UNKNOWN — not in the catalog yet. Priced expensive on purpose.",
};
const help = (v) => VERDICT_HELP[v] || "Program unit — no trigger verdict applies.";

/* Risk is not confidence. Confidence asks how sure the model is about its
   answer; risk asks how much damage a wrong answer does here. They are
   computed by different things and must never be read as one number. */
const RISK = [["all", "all"], ["CRITICAL", "critical"], ["HIGH", "high"],
              ["MEDIUM", "medium"], ["LOW", "low"]];
const RISK_HELP = {
  LOW: "LOW — nothing in this body is dangerous on its own.",
  MEDIUM: "MEDIUM — a few constructs need a deliberate decision.",
  HIGH: "HIGH — at least one construct is dangerous to translate blindly.",
  CRITICAL: "CRITICAL — several dangerous constructs at once. Read every line.",
};
const BEH_HELP = {
  PRESERVED: "PRESERVED — no rule found anything that changes observable behaviour.",
  CHANGED: "CHANGED — something observably differs after migration, and we can name it.",
  UNCERTAIN: "UNCERTAIN — the rules cannot tell. That is a finding, not a hedge.",
};
const BEH_SHORT = { PRESERVED: "BEHAVIOUR KEPT", CHANGED: "BEHAVIOUR CHANGED", UNCERTAIN: "BEHAVIOUR UNCERTAIN" };
const CLASS_LABEL = {
  DIRECT_EQUIVALENT: "direct equivalent",
  SERVER_SIDE_REPLACEMENT: "server-side replacement",
  CLIENT_SIDE_REPLACEMENT: "client-side replacement",
  ARCHITECTURAL_REDESIGN: "architectural redesign",
  MANUAL_REVIEW: "manual review",
  UNSUPPORTED: "unsupported in APEX",
  NOT_REQUIRED: "not required in APEX",
};
const riskOf = (t) => ((t.analysis || {}).risk || {}).level || "";
const behOf = (t) => ((t.analysis || {}).behavior || {}).value || "";

const CALL_LABEL = { pending: "undecided", needs_work: "needs work" };
const label = (s) => CALL_LABEL[s] || s;
let state = { tasks: [], stats: {}, session: {}, provider: "" };
let conv = "all", call = "all", risk = "all", query = "", selected = null, polling = null;
/* The live run, as the server last described it -- null when nothing runs.
   `ticker` only keeps the elapsed counter honest between polls. */
let job = null, jobStart = 0, ticker = null, PROPOSE_LABEL = "";
/* "Later" on the first-run banner means later: quiet until the next launch. */
let setupLater = false;
/* Dependency neighbourhoods, fetched per unit and kept until the module
   changes -- the graph does not move when a proposal or a decision does. */
let deps = {};
/* Test specifications, same deal: one fetch per unit, refreshed only when
   the reviewer answers a case. TEST_ORIGINS is the server's own legend for
   the three origins, shown as tooltips rather than restated here. */
let tests = {}, TEST_ORIGINS = {};

function esc(s) {
  return (s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}
function toast(msg, bad) {
  const t = $("toast");
  t.textContent = msg;
  t.className = "show" + (bad ? " bad" : "");
  clearTimeout(t._h);
  t._h = setTimeout(() => (t.className = ""), 4200);
}
async function api(path, body) {
  const opt = body ? { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) } : {};
  const r = await fetch(path, opt);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || r.statusText);
  return data;
}

/* ── PL/SQL highlighting ──────────────────────────────────
   A tiny stateful lexer, not a library: strings and comments are atomic,
   the block-comment flag survives across lines, everything is escaped. */
const PLSQL_KW = new Set(("begin end if then else elsif loop while for declare is as procedure function return exception " +
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

/* ── rendering ─────────────────────────────────────────── */
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
    `<button data-v="${value}" class="${value === current ? "on" : ""}">${text}</button>`).join("");
  $(id).querySelectorAll("button").forEach((b) =>
    b.onclick = () => { set(b.dataset.v); renderFilters(); renderList(); renderDetail(); }
  );
}

function renderFilters() {
  renderRow("f-conv", CONV, conv, (v) => (conv = v));
  renderRow("f-call", CALL, call, (v) => (call = v));
  renderRow("f-risk", RISK, risk, (v) => (risk = v));
}

function renderList() {
  const rows = filtered();
  $("list").innerHTML = rows.map((t) => `
    <div class="row ${t.id === selected ? "sel" : ""}" data-id="${t.id}">
      <div class="state st-${t.state}" data-mark="${MARK[t.state] || "●"}">${MARK[t.state] || "●"}</div>
      <div>
        <div class="title">${esc(t.title)}</div>
        <div class="sub">${esc(t.module)} · ${t.lines} lines${t.proposal ? "" : " · not converted"}</div>
      </div>
      <div class="rside">
        ${riskOf(t) ? `<i class="rdot r-${riskOf(t)}" title="${esc(RISK_HELP[riskOf(t)] || "")}"></i>` : ""}
        <div class="verdict v-${t.verdict || "DROP"}" title="${esc(help(t.verdict))}">${t.verdict || "PU"}</div>
      </div>
    </div>`).join("") || `<div class="empty">Nothing matches this filter.</div>`;
  $("list").querySelectorAll(".row").forEach((r) => (r.onclick = () => select(r.dataset.id)));
  paintBusyRows();  // a re-render must not wipe the spinners of a live run
}

function renderCounts() {
  const s = state.stats;
  $("counts").innerHTML = `
    <span class="oc"><i></i>converted <b>${s.proposed || 0}</b>/${s.tasks || 0}</span>
    <span><i></i>undecided <b>${s.pending || 0}</b></span>
    <span class="ok"><i></i><b>${s.approved || 0}</b></span>
    <span class="no"><i></i><b>${s.rejected || 0}</b></span>`;
  // Progress is decisions made, not conversions run: the model finishing is
  // not the job finishing.
  const decided = (s.tasks || 0) - (s.pending || 0);
  $("bar").style.width = s.tasks ? (100 * decided / s.tasks) + "%" : "0";

  const left = s.unproposed || 0;
  const btn = $("btn-propose-all");
  btn.disabled = left === 0;
  btn.textContent = !s.tasks ? "Open a module first" : left ? `Convert ${left} unconverted` : "All converted";
}

function renderDetail() {
  paintBusyPane();
  const t = state.tasks.find((x) => x.id === selected);
  if (!t) {
    $("t-title").textContent = "—";
    $("t-where").textContent = "";
    $("src").innerHTML = ""; $("out").value = ""; $("t-meta").innerHTML = "";
    $("notes").innerHTML = state.tasks.length
      ? `<div class="empty">Nothing selected.</div>`
      : `<div class="empty">No module open. Pick the .fmb you want to convert from the button at the top left.</div>`;
    return;
  }

  $("t-title").textContent = t.title;
  const rows = filtered();
  const pos = rows.findIndex((x) => x.id === t.id);
  // The one line that says what this screen is, on every unit.
  $("t-where").innerHTML =
    (pos >= 0 ? `Unit <b>${pos + 1}</b> of <b>${rows.length}</b>${filtering() ? " in this view" : ""} · ` : "") +
    `one ${esc(t.kind)} · left is <b>what runs today</b>, right is <b>what would replace it</b>`;
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
    `<span>${esc(t.module)}</span>`,
    t.apex_hint ? `<span>→ ${esc(t.apex_hint)}</span>` : "",
    p && p.apex_target ? `<span class="chip">${esc(p.apex_target)}</span>` : "",
    a && a.stale ? `<span class="st-needs_work" title="Computed under an older rule set — reopen the module to recompute.">rules moved since</span>` : "",
  ].filter(Boolean).join("");
  $("t-lines").textContent = t.lines + " lines";
  $("src").innerHTML = withLineNumbers(t.source);
  $("out").value = t.final_code || "";

  if (p) {
    const c = p.confidence || 0;
    const color = c >= 0.8 ? "var(--green)" : c >= 0.5 ? "var(--gold)" : "var(--red)";
    $("t-conf").innerHTML = `confidence <span class="cbar"><i style="width:${Math.round(c * 100)}%;background:${color}"></i></span> ${c.toFixed(2)}`;
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
    bits.push(`<h3>What changed</h3><ul>${p.notes.map((n) => `<li>${esc(n)}</li>`).join("")}</ul>`);
  if (p && p.open_questions && p.open_questions.length)
    bits.push(`<h3>Open questions</h3><ul>${p.open_questions.map((n) => `<li class="q">${esc(n)}</li>`).join("")}</ul>`);
  bits.push(renderTests(t));
  // Sessions created before the analysis engine still show their built-ins.
  if (!a && (t.builtins || []).length)
    bits.push(`<h3>Built-ins in this body</h3><ul>${t.builtins.map((b) =>
      `<li><span class="verdict v-${b.verdict}">${b.verdict}</span> <code>${esc(b.name)}</code> — ${esc(b.apex)}</li>`).join("")}</ul>`);
  if (t.globals && t.globals.length)
    bits.push(`<h3>Globals</h3><ul><li>${t.globals.map(esc).join(", ")}</li></ul>`);
  if (!p) bits.unshift(`<div class="empty">Not converted yet — press <kbd>P</kbd> to ask the model, or write the APEX code on the right and approve it.</div>`);
  if (p && p.model) bits.push(`<div class="conf">${esc(p.provider)} · ${esc(p.model)} · ${esc(p.created_at || "")}</div>`);
  $("notes").innerHTML = bits.join("");
  $("notes").querySelectorAll(".tc-a button").forEach((b) =>
    (b.onclick = () => decideCase(b.dataset.case, b.dataset.state, b.dataset.task)));
  $("comment").value = t.comment || "";
}

/* ── dependencies ──────────────────────────────────────── */
/* Fetched on demand rather than shipped with every task: the graph is one
   payload per module, and the reviewer looks at one unit at a time. */
async function loadDeps(id) {
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
async function loadTests(id) {
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
  return `<details><summary>Test cases — ${cases.length} · ${cases.length - open} reviewed${unsure ? ` · <b>${unsure} to confirm</b>` : ""}</summary>
    <div class="why">Written from the Forms body, not from the conversion, and not executed by FormsLang.${
      d.item_metadata === false ? " The module itself is not on disk, so nothing about required values or lengths could be checked." : ""}</div>
    ${cases.map((c) => caseBlock(c, t.id)).join("")}
  </details>`;
}

function select(id) {
  selected = id;
  loadDeps(id);
  loadTests(id);
  renderList();
  renderDetail();
  const row = document.querySelector(".row.sel");
  if (row) row.scrollIntoView({ block: "nearest" });
}

function move(delta) {
  const rows = filtered();
  if (!rows.length) return;
  const i = rows.findIndex((t) => t.id === selected);
  select(rows[Math.min(rows.length - 1, Math.max(0, i + delta))].id);
}

/* ── data ──────────────────────────────────────────────── */
async function refresh(keep = true) {
  const data = await api("/api/state");
  state = data;
  $("btn-module").textContent = data.session.title || "Open a module…";
  $("provider").textContent = data.provider;
  $("btn-export").disabled = !data.can_export_apex;
  /* First run, nothing open: the welcome takes the whole stage. */
  $("welcome").classList.toggle("show", !state.tasks.length && !data.session.title);
  /* A module is open but the provider is still the offline stub: say so once.
     Never silently default to a cloud provider — choosing is an explicit act. */
  $("setup-banner").hidden = !(data.provider_id === "echo" && state.tasks.length && !setupLater);
  renderCounts();
  renderFilters();
  if (!keep || !state.tasks.some((t) => t.id === selected))
    selected = (state.tasks[0] || {}).id || null;
  renderList();
  renderDetail();
}

async function decide(st) {
  if (!selected) return;
  await api("/api/decision", {
    task_id: selected, state: st, code: $("out").value,
    comment: $("comment").value, reviewer: $("reviewer").value,
  });
  localStorage.setItem("formslang.reviewer", $("reviewer").value);
  const wasSelected = selected;
  await refresh();
  selected = wasSelected;
  renderList(); renderDetail();
  move(1);
}

/* ── the run, made visible ─────────────────────────────────
   A conversion through a CLI provider takes 15-60 seconds per unit. Silence
   for a minute reads as a hang, so every second of it is accounted for: a
   moving bar, the name of the unit being read, spinners on the queue and an
   overlay on the pane whose answer is still being written. */
function elapsed() {
  const s = Math.max(0, Math.round((Date.now() - jobStart) / 1000));
  return s < 60 ? s + "s" : Math.floor(s / 60) + "m " + String(s % 60).padStart(2, "0") + "s";
}
function providerLabel() { return $("provider").textContent || "the model"; }
function running() { return !!(job && job.running); }

function paintWorking() {
  const on = running();
  $("working").hidden = !on;
  $("bar").classList.toggle("busy", on);
  if (on) {
    const at = Math.min((job.done || 0) + 1, job.total || 1);
    $("working-what").innerHTML = job.current
      ? `Converting <b>${esc(job.current)}</b> — unit ${at} of ${job.total}`
      : `Starting the conversion — unit ${at} of ${job.total}`;
    const left = Math.max(0, (job.total || 0) - (job.done || 0));
    $("working-meta").textContent =
      [job.provider || providerLabel(), elapsed(), left + " left"].join(" · ");
    const btn = $("btn-propose-all");
    btn.disabled = true;
    btn.textContent = `Converting ${job.done || 0}/${job.total}…`;
  }
  paintBusyRows();
  paintBusyPane();
}

function paintBusyRows() {
  const queue = new Set(running() ? (job.queue || []) : []);
  document.querySelectorAll("#list .row").forEach((r) => {
    const id = r.dataset.id;
    const working = running() && id === job.current_id;
    r.classList.toggle("working", working);
    r.classList.toggle("queued", queue.has(id) && !working);
    const cell = r.querySelector(".state");
    if (!cell) return;
    if (working) { if (!cell.firstElementChild) cell.innerHTML = `<span class="spin"></span>`; }
    else if (cell.firstElementChild) cell.textContent = cell.dataset.mark || "●";
  });
}

function paintBusyPane() {
  const box = $("out-busy");
  if (!box) return;
  const queue = new Set(running() ? (job.queue || []) : []);
  // Only the unit being written is covered: its answer is about to replace
  // whatever is in the box. A unit merely waiting in line stays editable --
  // a queue of fifty must not lock fifty panes.
  const mine = !!(running() && selected && selected === job.current_id);
  const ahead = !!(selected && !mine && queue.has(selected));
  box.hidden = !mine;
  $("out-queued").hidden = !ahead;
  if (ahead) {
    $("out-queued").textContent =
      "in queue · " + Math.max(1, (job.total || 0) - (job.done || 0) - 1) + " ahead";
  }
  if (!mine) return;
  const who = job.provider || providerLabel();
  $("busy-title").textContent = "Reading this unit and writing the APEX version";
  $("busy-sub").textContent = who +
    " has the whole trigger body, its built-ins and its globals. One unit usually takes 15 to 60 seconds; the proposal lands here the moment it answers.";
  $("busy-tick").textContent = elapsed() + " elapsed";
}

function startTicker() {
  stopTicker();
  ticker = setInterval(() => { if (running()) paintWorking(); }, 1000);
}
function stopTicker() { if (ticker) clearInterval(ticker); ticker = null; }
function resetProposeButton() {
  const btn = $("btn-propose");
  btn.disabled = false;
  if (PROPOSE_LABEL) btn.innerHTML = PROPOSE_LABEL;
}

async function propose(all) {
  const body = all ? { all: true } : { task_id: selected };
  if (!all && !selected) return;
  const btn = all ? $("btn-propose-all") : $("btn-propose");
  const before = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = all ? "Sending…" : `<span class="spin"></span> Converting…`;
  // Paint the working state before the server answers. Starting a CLI run can
  // take a couple of seconds on its own, and a screen that does not move in
  // that gap reads as a broken button.
  const here = state.tasks.find((x) => x.id === selected);
  jobStart = Date.now();
  job = {
    running: true, done: 0, failed: 0, total: all ? Math.max(1, state.stats.unproposed || 1) : 1,
    current: all ? "" : (here || {}).title || "", current_id: all ? "" : selected,
    queue: all ? [] : [selected], provider: providerLabel(),
  };
  paintWorking();
  startTicker();
  try {
    await api("/api/propose", body);
  } catch (e) {
    job = null; stopTicker(); paintWorking();
    btn.disabled = false; btn.innerHTML = before;
    toast(e.message, true);
    return;
  }
  poll();
}

function poll() {
  clearInterval(polling);
  if (!jobStart) jobStart = Date.now();
  startTicker();
  polling = setInterval(async () => {
    let snap;
    try { snap = await api("/api/job"); }
    catch (e) { return; }  // one missed poll is not the end of the run
    job = snap;
    if (snap.running) { paintWorking(); return; }
    clearInterval(polling);
    stopTicker();
    job = null;
    jobStart = 0;
    paintWorking();
    resetProposeButton();
    if (snap.error) toast(snap.error, true);
    else if (snap.failed) toast(`${snap.failed} of ${snap.total} conversion(s) failed — ${snap.last_error}`, true);
    else if (snap.total) toast(`Converted ${snap.done} unit(s). Now read them.`);
    const keep = selected;
    await refresh();  // restores the button's own label from the new counts
    if (keep) { selected = keep; renderList(); renderDetail(); }
  }, 700);
}

/* ── overlay: which module, which model ────────────────── */
function closeModal() { $("modal").className = "modal"; }
function openModal(title) {
  $("modal-title").textContent = title;
  $("modal").className = "modal show";
}
/* One footer, reused by both pickers: a text field, an optional list of
   suggestions, and the button that commits. */
function foot(opt) {
  $("modal-foot").style.display = opt ? "flex" : "none";
  if (!opt) return;
  $("modal-input").style.display = "block";
  $("modal-input").placeholder = opt.placeholder || "";
  $("modal-input").value = opt.value || "";
  $("modal-models").innerHTML = (opt.options || []).map((m) => `<option value="${esc(m)}">`).join("");
  $("modal-go").textContent = opt.button;
  const run = () => opt.run($("modal-input").value.trim());
  $("modal-go").onclick = run;
  $("modal-input").onkeydown = (e) => { if (e.key === "Enter") run(); };
}

/* The picker: native file selection and drag/drop first, folders as a
   secondary route. Names only travel over the wire here -- reading a
   module's code takes an explicit open. */
async function browse(dir) {
  let d;
  try { d = await api("/api/browse" + (dir ? "?dir=" + encodeURIComponent(dir) : "")); }
  catch (e) { toast(e.message, true); return; }

  openModal("Import a Forms module");
  $("modal-path").textContent = d.dir;
  $("modal-hint").textContent =
    "Choose the exact FMB you want to convert. FormsLang works from a private copy and leaves the original untouched.";
  const dirs = d.dirs.map((x) =>
    `<div class="entry dir" data-dir="${esc(x.path)}"><span class="icon">DIR</span><span class="name">${esc(x.name)}</span><span class="tag">Open folder</span></div>`).join("");
  const mods = d.modules.map((m) => {
    const ext = m.name.split(".").pop().toUpperCase();
    return `<div class="entry mod ${ext === "XML" ? "xml" : ""}" data-mod="${esc(m.path)}"><span class="icon">${ext}</span>` +
      `<span class="name">${esc(m.name)}</span>` +
      `<span class="tag">${m.kb} KB${m.has_session ? " / Resume" : " / New"}</span></div>`;
  }).join("");
  $("modal-body").innerHTML = `
    <div class="picker-shell">
      <div class="picker-hero">
        <div class="dropzone" tabindex="0">
          <div class="dropmark">FMB</div>
          <div class="dropcopy">
            <strong>Select the Oracle Forms file</strong>
            <p>Drag it here or use the Windows file selector.</p>
            <button class="btn primary" type="button" data-pick>Select FMB / XML</button>
            <input type="file" accept=".fmb,.mmb,.xml" hidden>
          </div>
        </div>
        <div class="picker-info">
          <strong>What happens next?</strong>
          <p>Oracle reads the FMB, then FormsLang opens a resumable review session for that module.</p>
          <div class="safety"><i>&#10003;</i><span>The original file and its folder are never changed.</span></div>
        </div>
      </div>
      <div class="picker-nav">
        <button class="btn" type="button" data-home>&#8962; Start folder</button>
        ${d.parent ? `<button class="btn" type="button" data-up>&uarr; Up</button>` : ""}
        <span class="current" title="${esc(d.dir)}">${esc(d.dir)}</span>
      </div>
      <div class="group">Folders and Forms modules</div>
      <div class="picker-files">${dirs + mods || `<div class="picker-empty">No Forms modules in this folder.<br>Drop a file above or choose another folder.</div>`}</div>
    </div>`;
  foot({ placeholder: "Paste a full path to .fmb, .mmb, .xml or .session.db", button: "Open path", run: openModule });

  const body = $("modal-body");
  body.querySelectorAll(".entry.dir").forEach((e) => (e.onclick = () => browse(e.dataset.dir)));
  body.querySelectorAll(".entry.mod").forEach((e) => (e.onclick = () => openModule(e.dataset.mod)));
  const input = body.querySelector('input[type="file"]');
  const drop = body.querySelector(".dropzone");
  body.querySelector("[data-pick]").onclick = () => input.click();
  body.querySelector("[data-home]").onclick = () => browse("");
  const up = body.querySelector("[data-up]");
  if (up) up.onclick = () => browse(d.parent);
  input.onchange = () => input.files[0] && uploadModule(input.files[0]);
  drop.onkeydown = (e) => {
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); input.click(); }
  };
  for (const event of ["dragenter", "dragover"])
    drop.addEventListener(event, (e) => { e.preventDefault(); drop.classList.add("drag"); });
  for (const event of ["dragleave", "drop"])
    drop.addEventListener(event, (e) => { e.preventDefault(); drop.classList.remove("drag"); });
  drop.addEventListener("drop", (e) => e.dataTransfer.files[0] && uploadModule(e.dataTransfer.files[0]));
}

async function uploadModule(file) {
  if (!file) return;
  if (!/\.(fmb|mmb|xml)$/i.test(file.name)) {
    toast("Choose an .fmb, .mmb or .xml file.", true); return;
  }
  $("modal-body").innerHTML = `<div class="uploading"><div class="spinner"></div><strong>Importing ${esc(file.name)}</strong><span>Copying safely, then running the Oracle Forms converter...</span></div>`;
  foot(null);
  try {
    const response = await fetch("/api/upload?name=" + encodeURIComponent(file.name), {
      method: "POST", headers: { "Content-Type": "application/octet-stream" }, body: file,
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
    deps = {}; tests = {};  // another module, another graph and another specification
    closeModal();
    await refresh(false);
    toast(`${data.title}: ${data.stats.tasks} unit(s) ready for review.`);
  } catch (e) {
    toast(e.message, true);
    browse("");
  }
}

async function openModule(path) {
  if (!path) return;
  $("modal-body").innerHTML = `<div class="uploading"><div class="spinner"></div><strong>Opening ${esc(path.split(/[\\/]/).pop())}</strong>` +
    `<span>An .fmb goes through Oracle's converter first, then every trigger and program unit is indexed.</span></div>`;
  foot(null);
  try {
    const r = await api("/api/open", { path });
    deps = {}; tests = {};  // another module, another graph and another specification
    closeModal();
    await refresh(false);
    toast(`${r.title}: ${r.stats.tasks} unit(s)${r.added ? "" : " — resumed, nothing new"}`);
  } catch (e) {
    toast(e.message, true);
    browse("");
  }
}

/* Settings: which model converts, with what credentials. CLI providers ride
   your existing subscription; API providers take a key that is stored on this
   machine, write-only — the browser never sees it again. */
async function openSettings() {
  let list, cfg;
  try {
    [list, cfg] = await Promise.all([api("/api/providers"), api("/api/settings")]);
    list = list.providers;
  } catch (e) { toast(e.message, true); return; }

  openModal("Settings — which model converts");
  $("modal-path").textContent = "saved to " + cfg.config_path + " — never inside your project";
  $("modal-hint").textContent =
    "CLI providers drive an agent you already pay for — no API key. " +
    "API providers take a key; it is stored on this machine only and never shown again.";

  let chosen = list.find((p) => p.id === cfg.provider) || list[0];

  const row = (p) => {
    const on = p.id === chosen.id;
    const tag = p.kind === "cli"
      ? (p.available ? "cli · your subscription" : "cli · not installed")
      : (p.needs_key ? (p.available ? "api key" : "api key · none yet") : "local");
    return `<div class="entry ${on ? "on" : ""}" data-p="${esc(p.id)}">` +
      `<span class="icon">${on ? "●" : "○"}</span>` +
      `<span class="name">${esc(p.label)}</span><span class="tag">${esc(tag)}</span></div>`;
  };

  /* The per-provider form: only the fields this provider actually needs. */
  const form = (p) => {
    const bits = [];
    if (p.needs_key) {
      const store = cfg.secure_storage || {};
      const vault = store.label || "the OS credential store";
      const sealed = store.available || cfg.key_source === "env";
      bits.push(`<label>API key
        <input type="password" data-f="api_key" spellcheck="false" autocomplete="off" ${sealed ? "" : "disabled"}
               placeholder="${cfg.has_key ? "saved — leave blank to keep it" : "paste your API key"}"></label>`);
      const src = cfg.key_source === "env" ? "from the environment — wins over anything saved here"
                : cfg.key_source === "keychain" ? `saved in ${vault}`
                : cfg.key_source === "file" ? "in the old config file — save it again to move it into " + vault
                : "not set yet";
      bits.push(`<div class="keyline"><i>${cfg.has_key ? "&#10003;" : "&#9702;"}</i><span>Key: ${esc(src)}</span>` +
        (cfg.key_source === "keychain" || cfg.key_source === "file"
          ? `<button type="button" class="forget" data-forget>forget saved key</button>` : "") +
        `</div>`);
      if (!sealed)
        bits.push(`<div class="keyline warn"><i>&#9888;</i><span>${esc(store.message || "")}</span></div>`);
    }
    if (p.kind === "http" && p.id !== "echo" && p.id !== "azure_openai") {
      bits.push(`<label>Endpoint override (optional)
        <input data-f="base_url" spellcheck="false" value="${esc(cfg.base_url || "")}" placeholder="blank = the provider's default endpoint"></label>`);
    }
    if (p.id === "azure_openai") {
      bits.push(`<label>Endpoint
        <input data-f="base_url" spellcheck="false" value="${esc(cfg.base_url || "")}" placeholder="your Azure OpenAI resource endpoint"></label>`);
      bits.push(`<div class="duo">
        <label>Deployment<input data-f="deployment" spellcheck="false" value="${esc(cfg.deployment || "")}"></label>
        <label>API version<input data-f="api_version" spellcheck="false" value="${esc(cfg.api_version || "")}"></label>
      </div>`);
    }
    if (p.kind === "cli") {
      bits.push(`<div class="keyline"><i>${p.available ? "&#10003;" : "&#10007;"}</i>` +
        `<span>${p.available ? "CLI installed — it signs in with your subscription." : esc(p.hint || "Not installed on this machine.")}</span>` +
        (p.available ? `<button type="button" class="btn" data-term>Open setup terminal</button>` : "") +
        `</div>`);
    }
    bits.push(`<div class="testrow"><button type="button" class="btn" data-test>Test</button><span class="out" data-testout></span></div>`);
    return `<div class="settings-form">${bits.join("")}</div>`;
  };

  const render = () => {
    const body = $("modal-body");
    body.innerHTML = list.map(row).join("") + form(chosen);
    body.querySelectorAll(".entry[data-p]").forEach((e) => (e.onclick = () => {
      chosen = list.find((p) => p.id === e.dataset.p);
      render();
    }));

    const field = (name) => {
      const el = body.querySelector(`[data-f="${name}"]`);
      return el ? el.value.trim() : "";
    };
    /* What travels on save/test: the provider, the model, and only the
       fields this provider's form actually shows. An untouched key field
       stays out of the payload, so a stored key is kept, not clobbered. */
    const payload = () => {
      const out = { provider: chosen.id, model: $("modal-input").value.trim() };
      for (const name of ["base_url", "deployment", "api_version"])
        if (body.querySelector(`[data-f="${name}"]`)) out[name] = field(name);
      if (field("api_key")) out.api_key = field("api_key");
      return out;
    };

    const testBtn = body.querySelector("[data-test]");
    const testOut = body.querySelector("[data-testout]");
    testBtn.onclick = async () => {
      testOut.className = "out";
      testOut.innerHTML = `<span class="spin"></span> asking the model for one word…`;
      testBtn.disabled = true;
      try {
        const r = await api("/api/settings/test", payload());
        testOut.className = "out " + (r.ok ? "ok" : "bad");
        testOut.textContent = (r.ok ? "✓ answered — " : "✗ ") + r.message;
      } catch (e) {
        testOut.className = "out bad";
        testOut.textContent = "✗ " + e.message;
      }
      testBtn.disabled = false;
    };

    const term = body.querySelector("[data-term]");
    if (term) term.onclick = async () => {
      try {
        await api("/api/terminal", { provider: chosen.id });
        toast("Terminal opened — sign in there, then press Test.");
      } catch (e) { toast(e.message, true); }
    };

    const forget = body.querySelector("[data-forget]");
    if (forget) forget.onclick = async () => {
      try {
        cfg = await api("/api/settings", { api_key: "" });
        toast("Key forgotten.");
        render();
      } catch (e) { toast(e.message, true); }
    };

    foot({
      placeholder: `model (blank = ${chosen.default_model || "provider default"})`,
      value: chosen.id === cfg.provider ? cfg.model : chosen.default_model,
      options: chosen.models.length ? chosen.models : (chosen.default_model ? [chosen.default_model] : []),
      button: `Save · use ${chosen.label}`,
      run: async () => {
        try {
          cfg = await api("/api/settings", payload());
          closeModal();
          await refresh();
          toast(`Converting with ${state.provider}.`);
        } catch (e) { toast(e.message, true); }
      },
    });
  };
  render();
}

function exportApex() {
  if (!state.session.title) { toast("Open a Forms module first.", true); return; }
  const suggested = state.session.title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "formslang-app";
  openModal("Export Oracle APEX 26.1");
  $("modal-path").textContent = "APEXlang project + import ZIP";
  $("modal-hint").textContent =
    "Only approved conversions enter the app. Generated processes start disabled until their execution point and condition are confirmed in Page Designer.";
  $("modal-body").innerHTML = `
    <div class="export-form">
      <label class="wide">Application name<input name="name" value="${esc(state.session.title)}"></label>
      <label>Application alias<input name="alias" value="${esc(suggested)}"></label>
      <label>Application ID<input name="app_id" type="number" min="1" value="100"></label>
      <label>Workspace (optional)<input name="workspace" placeholder="resolved during import"></label>
      <label>Parsing schema (optional)<input name="schema" placeholder="resolved during import"></label>
      <label>Page number<input name="page" type="number" min="1" value="1"></label>
    </div>`;
  $("modal-foot").style.display = "flex";
  $("modal-input").style.display = "none";
  $("modal-go").textContent = "Build import ZIP";
  $("modal-go").onclick = async () => {
    const form = $("modal-body").querySelector(".export-form");
    const value = (name) => form.querySelector(`[name="${name}"]`).value.trim();
    const go = $("modal-go");
    go.disabled = true;
    go.innerHTML = `<span class="spin"></span> Building ZIP…`;
    try {
      const r = await api("/api/export", {
        name: value("name"), alias: value("alias"), app_id: value("app_id"),
        workspace: value("workspace"), schema: value("schema"), page: value("page"),
      });
      closeModal();
      toast(`APEXlang ZIP ready: ${r.zip}`);
      showExports(r.zip.split(/[\/]/).pop());
    } catch (e) { toast(e.message, true); }
    finally { $("modal-go").disabled = false; $("modal-go").textContent = "Build import ZIP"; }
  };
}

async function showExports(freshName) {
  let data;
  try { data = await api("/api/exports"); } catch (e) { toast(e.message, true); return; }
  openModal("Exported APEX applications");
  $("modal-path").textContent = data.dir || "";
  $("modal-hint").textContent =
    "Each ZIP imports straight into APEX 26.1 — App Builder or SQLcl. Show in folder selects the file on disk.";
  $("modal-foot").style.display = "none";
  const size = (b) => (b >= 1048576 ? (b / 1048576).toFixed(1) + " MB" : Math.max(1, Math.round(b / 1024)) + " KB");
  const rows = (data.exports || []).map((e) => `
    <div class="exp-row${e.name === freshName ? " fresh" : ""}">
      <span class="exp-name">${esc(e.name)}</span>
      <span class="exp-meta">${size(e.size)} &middot; ${esc(new Date(e.mtime * 1000).toLocaleString())}</span>
      <button class="btn" data-reveal="${esc(e.name)}">Show in folder</button>
    </div>`).join("");
  $("modal-body").innerHTML =
    `<div class="exports-list">${rows || '<div class="empty">No exports yet — press Export APEX 26.1 first.</div>'}</div>`;
  $("modal-body").querySelectorAll("[data-reveal]").forEach((b) => {
    b.onclick = async () => {
      try { await api("/api/exports/open", { name: b.dataset.reveal }); }
      catch (e) { toast(e.message, true); }
    };
  });
}

/* ── the project view ──────────────────────────────────── */
/* Every figure here is a count over rows already on disk. The readiness
   score is the only one that could be read as a verdict, so it is printed
   next to the formula that produced it, weight by weight. */
const pct = (n, of) => (of ? Math.round((100 * n) / of) : 0);

function bars(rows, total) {
  if (!rows.length) return `<div class="none">nothing counted yet</div>`;
  return rows.map(([label, n, cls]) => `
    <div class="brow ${cls || ""}">
      <span>${esc(label)}</span>
      <span class="track"><i style="width:${pct(n, total)}%"></i></span>
      <span class="cnt">${n}</span>
    </div>`).join("");
}

function readyCard(d) {
  const r = d.readiness || {}, m = d.readiness_model || {};
  const got = {};
  (r.components || []).forEach((c) => (got[c.key] = c));
  const rows = (m.components || []).map((c) => {
    const g = got[c.key] || {};
    return `<tr>
      <td>${esc(c.title)}<div class="d">${esc(c.detail)}</div></td>
      <td class="n">${c.weight}</td>
      <td class="n">${Math.round((g.ratio || 0) * 100)}%</td>
      <td class="n">${(g.points || 0).toFixed(1)}</td>
    </tr>`;
  }).join("");
  return `<div class="card ready">
    <div>
      <div class="num">${r.score}</div>
      <div class="of">OF ${r.of} &middot; MIGRATION READINESS</div>
      <div class="gauge"><i style="width:${pct(r.score, r.of)}%"></i></div>
      <div class="caveat">${esc(m.caveat || "")}</div>
      <div class="ver">${esc(m.version || "")} &middot; ${esc(m.engine_version || "")}</div>
    </div>
    <div>
      <h3>How this number is calculated</h3>
      <table class="formula">
        <tr><th>Component</th><th>Weight</th><th>Measured</th><th>Points</th></tr>
        ${rows}
        <tr class="sum"><td><b>readiness</b><div class="d">${esc(m.formula || "")}</div></td>
          <td class="n">${m.total_weight}</td><td class="n">&mdash;</td><td class="n"><b>${r.score}</b></td></tr>
      </table>
    </div>
  </div>`;
}

function riskTable(d) {
  const rows = d.highest_risk || [];
  if (!rows.length) return `<div class="none">No unit has been analysed yet.</div>`;
  return `<table class="dtable">
    <tr><th>Unit</th><th>Risk</th><th>Behaviour</th><th>Mode</th><th>State</th><th>Score</th></tr>
    ${rows.map((r) => `<tr class="pick" data-go="${esc(r.task_id)}">
      <td class="mono">${esc(r.title)}<div class="sub">${esc(r.kind)} &middot; ${r.factors} factor(s)</div></td>
      <td class="r-${esc(r.level)} mono">${esc(r.level)}</td>
      <td class="bh-${esc(r.behavior)} mono">${esc(r.behavior || "—")}</td>
      <td class="v-${esc(r.verdict)} mono">${esc(r.verdict)}</td>
      <td class="st-${esc(r.state)} mono">${esc(r.state)}</td>
      <td class="n">${r.score}</td>
    </tr>`).join("")}
  </table>`;
}

function unsupportedTable(d) {
  const rows = d.unsupported || [];
  if (!rows.length) return `<div class="none">No unsupported construct in what has been analysed.</div>`;
  return `<table class="dtable">
    <tr><th>Built-in</th><th>Calls</th><th>Where it is called</th><th>What APEX offers</th></tr>
    ${rows.map((r) => `<tr>
      <td class="mono">${esc(r.name)}<div class="sub">${esc(r.category || "")}</div></td>
      <td class="n">${r.count}</td>
      <td class="sub">${(r.units || []).map(esc).join("<br>")}</td>
      <td class="sub">${esc(r.apex || "no direct replacement")}</td>
    </tr>`).join("")}
  </table>`;
}

function depCard(d) {
  const g = d.dependencies || {};
  if (!g.available) return `<div class="none">${esc(g.reason || "no dependency graph")}</div>`;
  const hubs = (g.hubs || []).map((h) => `<tr>
    <td class="mono">${esc(h.name || h.id)}<div class="sub">${esc(h.label || h.kind || "")}</div></td>
    <td class="n">${h.in}</td><td class="n">${h.out}</td><td class="n">${h.degree}</td>
  </tr>`).join("");
  return `<div class="cap" style="margin-bottom:9px;color:var(--ink-dim);font-size:12px;line-height:1.5">
      ${g.nodes} object(s), ${g.edges} link(s) &mdash; ${g.external} external, ${g.missing} referenced but not
      declared here, ${g.unresolved} name(s) the parser could not resolve. One session holds one form, so this
      ranks the objects inside <b>${esc(g.module || "")}</b> that the most other things lean on.
    </div>
    ${hubs
      ? `<table class="dtable"><tr><th>Object</th><th>Depended on by</th><th>Depends on</th><th>Total</th></tr>${hubs}</table>`
      : `<div class="none">nothing in this form depends on anything else</div>`}`;
}

async function showDashboard() {
  let d;
  try { d = await api("/api/dashboard"); } catch (e) { toast(e.message, true); return; }
  openModal("Project — " + ((d.session || {}).title || "session"));
  $("modal-path").textContent = (d.session || {}).source_path || "";
  $("modal-hint").textContent =
    "Counted from this session, never estimated: the deterministic analysis, your decisions, the dependency graph and the test specifications.";
  $("modal-foot").style.display = "none";

  const t = d.totals, cov = d.coverage, tc = d.test_coverage;
  const measured = `Measured on ${cov.analysed} of ${t.units} unit(s)` +
    (cov.missing ? `; ${cov.missing} still unanalysed and counted nowhere in this chart.` : ".");

  $("modal-body").innerHTML = `<div class="dash">
    ${readyCard(d)}

    <div>
      <h3>The session</h3>
      <div class="kpis">
        <div class="kpi"><b>${t.units}</b><span>units</span></div>
        <div class="kpi"><b>${t.lines}</b><span>lines of PL/SQL</span></div>
        <div class="kpi"><b>${t.proposed}</b><span>converted</span></div>
        <div class="kpi"><b>${d.percent.reviewed}%</b><span>reviewed</span></div>
        <div class="kpi"><b>${d.percent.approved}%</b><span>approved</span></div>
        <div class="kpi"><b>${tc.total}</b><span>test cases</span></div>
      </div>
    </div>

    <div class="dists">
      <div class="card dist"><h3>Conversion mode</h3>
        ${bars(Object.entries(d.conversion_modes).map(([k, n]) => [k, n, "v-" + k]), t.units)}
        <div class="cap">What the rules say the conversion costs. A different question from risk.</div>
      </div>
      <div class="card dist"><h3>Your decisions</h3>
        ${bars(Object.entries(d.decisions).map(([k, n]) => [k, n, "st-" + k]), t.units)}
        <div class="cap">Approval is a human act. Nothing on this screen moves it.</div>
      </div>
      <div class="card dist"><h3>Migration risk</h3>
        ${bars(Object.entries(d.risk).map(([k, n]) => [k, n, "r-" + k]), cov.analysed)}
        <div class="cap">${esc(measured)} Average score ${d.avg_risk_score}.</div>
      </div>
      <div class="card dist"><h3>Behaviour after migration</h3>
        ${bars(Object.entries(d.behavior).map(([k, n]) => [k, n, "bh-" + k]), cov.analysed)}
        <div class="cap">${esc(measured)}</div>
      </div>
    </div>

    <div><h3>What is in the way</h3>
      ${(d.blockers || []).length
        ? d.blockers.map((b) => `<div class="blk"><b>${b.count}</b><span>${esc(b.detail)}</span></div>`).join("")
        : `<div class="none">Nothing outstanding: every unit is analysed, converted, decided and specified.</div>`}
      <div class="cap" style="margin-top:8px;color:var(--ink-faint);font-size:11px">
        Deliberately left out of the score above &mdash; a blocker is work to do, not a percentage.</div>
    </div>

    <div><h3>Highest risk first</h3>${riskTable(d)}</div>
    <div><h3>Forms features APEX has no equivalent for</h3>${unsupportedTable(d)}</div>
    <div><h3>Where the dependencies pile up</h3>${depCard(d)}</div>
  </div>`;

  $("modal-body").querySelectorAll("[data-go]").forEach((tr) => {
    tr.onclick = () => { closeModal(); select(tr.dataset.go); };
  });
}

/* ── wiring ────────────────────────────────────────────── */
$("btn-module").onclick = () => browse("");
$("welcome-open").onclick = () => browse("");
$("provider").onclick = openSettings;
$("btn-settings").onclick = openSettings;
$("setup-open").onclick = openSettings;
$("setup-later").onclick = () => { setupLater = true; $("setup-banner").hidden = true; };
$("modal-close").onclick = closeModal;
$("modal").onclick = (e) => { if (e.target === $("modal")) closeModal(); };
$("btn-approve").onclick = () => decide("approved");
$("btn-reject").onclick = () => decide("rejected");
$("btn-needs").onclick = () => decide("needs_work");
$("btn-propose").onclick = () => propose(false);
$("btn-propose-all").onclick = () => propose(true);
$("btn-export").onclick = exportApex;
$("btn-exports").onclick = () => showExports();
$("btn-dash").onclick = showDashboard;
$("q").oninput = (e) => { query = e.target.value.toLowerCase(); renderList(); };

document.addEventListener("keydown", (e) => {
  const typing = ["INPUT", "TEXTAREA"].includes(document.activeElement.tagName);
  if (e.key === "Escape") { closeModal(); document.activeElement.blur(); return; }
  // With the overlay up, every other shortcut belongs to the overlay.
  if ($("modal").classList.contains("show")) return;
  if (e.key === "/" && !typing) { e.preventDefault(); $("q").focus(); return; }
  if (typing) return;
  if (e.key === "j") move(1);
  else if (e.key === "k") move(-1);
  else if (e.key === "a") decide("approved");
  else if (e.key === "r") decide("rejected");
  else if (e.key === "w") decide("needs_work");
  else if (e.key === "p") propose(false);
  else if (e.key === "o") browse("");
  else if (e.key === "d") showDashboard();
});

$("reviewer").value = localStorage.getItem("formslang.reviewer") || "";
PROPOSE_LABEL = $("btn-propose").innerHTML;
refresh(false)
  /* A run started before this window opened still owns the screen. */
  .then(() => api("/api/job"))
  .then((j) => { if (j.running) { job = j; jobStart = Date.now(); paintWorking(); poll(); } })
  .catch((e) => toast(e.message, true));
</script>
</body>
</html>
"""
