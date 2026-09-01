"""Design tokens, page shell (head/style/toast/modal) and JS every screen depends on: fetch/escape/toast helpers and the shared in-page state -- split out of formslang/ui.py."""

from __future__ import annotations

HEAD_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>FormsLang Workbench</title>
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 512 512'%3E%3Cpath fill='%23F5A640' fill-rule='evenodd' d='M112 72H322V104H112C90 104 72 122 72 144V368C72 390 90 408 112 408H322V440H112C72 440 40 408 40 368V144C40 104 72 72 112 72ZM290 72H322V440H290Z'/%3E%3Crect x='322' y='112' width='92' height='24' rx='2' fill='%23F5A640'/%3E%3Crect x='322' y='160' width='132' height='24' rx='2' fill='%23F5A640'/%3E%3Crect x='322' y='208' width='104' height='24' rx='2' fill='%23F5A640'/%3E%3Crect x='322' y='256' width='148' height='24' rx='2' fill='%23F5A640'/%3E%3Crect x='322' y='304' width='116' height='24' rx='2' fill='%23F5A640'/%3E%3Crect x='322' y='352' width='140' height='24' rx='2' fill='%23F5A640'/%3E%3C/svg%3E">
"""

STYLE_BLOCK = r"""<style>
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
  /* Same severity colours as risk, a different shape on purpose -- risk asks
     "is this dangerous to translate", this asks "is there a secret in here",
     and the two must never be mistaken for one another at a glance. */
  .sflag { font-size: 11px; line-height: 1; flex: 0 0 auto; font-style: normal; }
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
  /* Whether someone actually ran the case, kept visually apart from the
     accept/reject row above it: a different axis, a different colour. */
  .notes .tc-a.run button.on.r-pass { color: var(--green); border-color: rgba(74,222,128,.35); background: rgba(74,222,128,.08); }
  .notes .tc-a.run button.on.r-fail { color: var(--red); border-color: var(--red); background: rgba(248,113,113,.08); }
  .notes .tc-a.run button.on.r-blocked { color: var(--gold); border-color: var(--gold-deep); background: var(--gold-soft); }
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
  .settings-form label.check {
    display: flex; align-items: center; gap: 8px; flex-direction: row;
    text-transform: none; letter-spacing: 0; font: 12px var(--mono); color: var(--ink);
  }
  .settings-form label.check input[type="checkbox"] {
    all: revert; width: auto; padding: 0; accent-color: var(--gold-deep);
  }

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
"""

MODAL_HTML = r"""<div class="modal" id="modal">
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

"""

TOAST_HTML = r"""<div id="toast"></div>

"""

SCRIPT_CORE = r"""<script>
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
const sensOf = (t) => ((t.analysis || {}).sensitive || {}).level || "";
const SENS_CATEGORY_LABEL = { CREDENTIAL: "credential", BR_DOCUMENT: "CPF/CNPJ", CONTACT: "contact", FINANCIAL: "financial" };

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
"""

MODAL_JS = r"""function closeModal() { $("modal").className = "modal"; }
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
"""
