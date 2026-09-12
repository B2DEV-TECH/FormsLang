"""Run the shipped review JavaScript against a small DOM fixture.

These check data-loss/concurrency boundaries; visual acceptance runs separately
in Edge. Node is only a test tool, never a FormsLang runtime dependency.
"""

from __future__ import annotations

import shutil
import subprocess

import pytest

from formslang.ui.conversion import JOB_PROGRESS_JS, PROPOSE_AND_POLL_JS
from formslang.ui.review import (
    DECIDE_JS,
    LIST_AND_DETAIL_JS,
    NAVIGATION_JS,
    SYNTAX_HIGHLIGHT_JS,
)
from formslang.ui.shared import SCRIPT_CORE
from formslang.ui.shell import DATA_REFRESH_JS
from formslang.ui.validation import DEPENDENCIES_JS, TEST_CASES_JS

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="Node needed for JavaScript behavior tests")

DOM = r"""
const assert = require('node:assert/strict');
const elements = new Map();
function element(id) {
  if (!elements.has(id)) elements.set(id, {
    value: '', textContent: '', innerHTML: '', hidden: false, disabled: false,
    readOnly: false, style: {}, dataset: {}, scrollTop: 0, scrollLeft: 0,
    classList: { toggle() {}, add() {}, remove() {}, contains() { return false; } },
    querySelectorAll() { return []; }, setAttribute() {}, focus() {},
  });
  return elements.get(id);
}
const document = {
  body: element('body'), getElementById: element, querySelectorAll() { return []; },
  querySelector(selector) { return selector === 'main' ? element('main') : null; },
};
const window = { matchMedia() { return { matches: false }; }, confirm() { return true; } };
const localStorage = { setItem() {} };
let timers = [];
function setTimeout(fn) { timers.push(fn); return timers.length; }
function clearTimeout() {}
function setInterval() { return 1; }
function clearInterval() {}
function renderDeps() { return ''; }
function renderTests() { return ''; }
function loadDeps() {}
function loadTests() {}
function deferred() { let resolve, reject; const promise = new Promise((a,b) => { resolve=a; reject=b; }); return {promise,resolve,reject}; }
function unit(id) { return {id, title:id, module:'M', kind:'trigger', state:'pending',
  source:'BEGIN NULL; END;', final_code:'saved '+id, comment:'', lines:1, verdict:'AUTO'}; }
"""


def run_js(tmp_path, script, *, validation=False):
    path = tmp_path / "review-behavior.cjs"
    path.write_text(
        "process.stdout.write('FORMSLANG_UI_STARTED\\n');\n"
        + DOM
        + SCRIPT_CORE.removeprefix("<script>")
        + SYNTAX_HIGHLIGHT_JS
        + LIST_AND_DETAIL_JS
        + NAVIGATION_JS
        + DECIDE_JS
        + DATA_REFRESH_JS
        + JOB_PROGRESS_JS
        + PROPOSE_AND_POLL_JS
        + (DEPENDENCIES_JS + TEST_CASES_JS if validation else "")
        + "\n(async () => {\n"
        + "state = {tasks:[unit('a'),unit('b')],stats:{tasks:2},session:{title:'M'},session_path:'/local/session.db',context_id:'session-a'}; selected='a';\n"
        + script
        + "\n})().then(() => { process.stdout.write('FORMSLANG_UI_COMPLETE\\n'); })"
        + ".catch(e => { console.error(e); process.exitCode=1; });\n",
        encoding="utf-8",
    )
    # This bounds a hung process, not Node startup performance on a busy runner.
    try:
        result = subprocess.run([NODE, str(path)], text=True, capture_output=True, timeout=60, check=False)
    except subprocess.TimeoutExpired as exc:
        pytest.fail(
            f"Node UI test exceeded 60s; startup/completion markers locate the stall.\n"
            f"stdout: {exc.stdout!r}\nstderr: {exc.stderr!r}",
            pytrace=False,
        )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "FORMSLANG_UI_STARTED" in result.stdout.splitlines(), result.stdout + result.stderr
    # An unresolved Promise alone does not keep Node alive; exit 0 is insufficient.
    assert "FORMSLANG_UI_COMPLETE" in result.stdout.splitlines(), (
        "Node exited without completing the async assertions.\n" + result.stdout + result.stderr
    )


def test_source_and_note_edits_survive_renders_and_navigation(tmp_path):
    run_js(tmp_path, r"""
renderDetail();
element('out').value = 'local edit'; element('comment').value = 'needs validation'; captureReviewDraft();
renderDetail(); // dependency response / filter / status refresh
assert.equal(element('out').value, 'local edit');
assert.equal(element('comment').value, 'needs validation');
select('b'); assert.equal(element('out').value, 'saved b');
select('a'); assert.equal(element('out').value, 'local edit');
assert.equal(reviewDrafts.size,1);
// A source replacement with the same task ID cannot inherit an old edit.
state.tasks[0].source = 'BEGIN RAISE; END;'; renderDetail();
assert.equal(element('out').value, 'saved a');
""")


def test_new_server_proposal_does_not_overwrite_local_edits(tmp_path):
    run_js(tmp_path, r"""
renderDetail(); element('out').value = 'local edit'; captureReviewDraft();
state.tasks[0].final_code = 'new server proposal'; renderDetail();
assert.equal(element('out').value, 'local edit');
assert.match(element('review-status').textContent,/Saved proposal changed/);
discardReviewDraft();
assert.equal(element('out').value, 'new server proposal');
assert.equal(reviewDrafts.size,0);
""")


def test_decision_keeps_selection_and_edits_made_during_save(tmp_path):
    run_js(tmp_path, r"""
renderDetail(); element('out').value = 'first edit'; captureReviewDraft();
const pending = deferred(); let sent;
api = async (path, body) => { sent=body; return pending.promise; };
refresh = async () => { state.tasks[0].final_code=sent.code; renderDetail(); };
const saving=decide('needs_work');
element('out').value = 'newer edit'; captureReviewDraft();
select('b');
pending.resolve({}); await saving;
assert.equal(sent.task_id,'a'); assert.equal(sent.code,'first edit');
assert.equal(sent.context_id,'session-a');
assert.equal(selected,'b');
select('a'); assert.equal(element('out').value,'newer edit');
assert.equal(reviewDrafts.size,1); assert.equal(decisionBusy,false);
""")


def test_failed_review_keeps_draft_and_reenables_controls(tmp_path):
    run_js(tmp_path, r"""
renderDetail(); element('out').value = 'review work'; captureReviewDraft();
api = async () => { throw new Error('offline'); };
await decide('approved');
assert.equal(element('out').value,'review work'); assert.equal(reviewDrafts.size,1);
assert.match(element('review-status').textContent,/Could not save/);
assert.equal(element('btn-approve').disabled,false);
assert.equal(decisionBusy,false);
""")


def test_refresh_ignores_older_response(tmp_path):
    run_js(tmp_path, r"""
const old=deferred(), current=deferred(); let calls=0;
api = () => (++calls===1 ? old.promise : current.promise);
const older=refresh(), newer=refresh();
const data = {...state, session:{title:'new'},can_export_apex:true};
current.resolve(data); await newer;
old.resolve({...data,session:{title:'old'}}); await older;
assert.equal(state.session.title,'new');
assert.equal(element('btn-module').textContent,'new');
""")


def test_reconversion_cannot_replace_unsaved_edit_or_duplicate_job(tmp_path):
    run_js(tmp_path, r"""
renderDetail(); element('out').value='local work'; captureReviewDraft();
let calls=0; api=async()=>{ calls++; return {}; };
await propose(false); await propose(true); assert.equal(calls,0);
reviewDrafts.clear(); job={running:true,queue:['a']};
await propose(false); assert.equal(calls,0);
paintReviewStatus(); assert.equal(element('out').readOnly,true);
assert.equal(element('btn-approve').disabled,true);
""")


def test_poll_waits_for_each_response_before_scheduling_next(tmp_path):
    run_js(tmp_path, r"""
job={running:true,queue:[],done:0}; const pending=deferred(); let calls=0;
api=async()=>{ calls++; return pending.promise; };
poll(); const scheduled=timers.pop(); timers=[];
const waiting=scheduled();
assert.equal(calls,1); assert.equal(timers.length,0);
pending.resolve({running:true,queue:[],done:0}); await waiting;
assert.equal(timers.length,1); assert.equal(calls,1);
""")


def test_untrusted_code_is_escaped_and_large_editing_uses_plain_text(tmp_path):
    run_js(tmp_path, r"""
assert.ok(withLineNumbers("<img src=x onerror='bad()'>").includes('&lt;img'));
assert.ok(!withLineNumbers('<script>bad()</script>').includes('<script>'));
state.tasks[0].source = '<unsafe>' + 'x'.repeat(160000); renderDetail();
assert.equal(element('src').textContent,state.tasks[0].source);
element('out').value = 'x'.repeat(160000); syncOutHighlight();
assert.equal(element('out-hl').hidden,true);
assert.equal(esc("a'b\"c"),'a&#39;b&quot;c');
""")


def test_actor_context_switch_isolates_drafts_and_cached_evidence(tmp_path):
    run_js(tmp_path, r"""
renderDetail(); element('out').value='first actor edit'; element('comment').value='private draft'; captureReviewDraft();
const originalKey=editorTask.key;
deps={a:{old_actor:true}}; tests={a:{old_actor:true}};
api=async()=>({...state,context_id:'another-actor-same-session',can_export_apex:true});
await refresh();
assert.equal(state.session_path,'/local/session.db');
assert.equal(element('out').value,'saved a');
assert.equal(element('comment').value,'');
assert.notEqual(editorTask.key,originalKey);
assert.deepEqual(deps,{}); assert.deepEqual(tests,{});
assert.equal(reviewDrafts.get(originalKey).code,'first actor edit');
""")


def test_saved_decision_cannot_move_new_actor_selection(tmp_path):
    run_js(tmp_path, r"""
renderDetail(); api=async()=>({});
refresh=async()=>{state.context_id='another-actor-same-session';renderDetail();};
await decide('needs_work');
assert.equal(selected,'a');
""")


def test_late_decision_error_does_not_attach_to_another_actor(tmp_path):
    run_js(tmp_path, r"""
renderDetail();const pending=deferred();api=()=>pending.promise;
const saving=decide('approved');
state.context_id='another-actor-same-session';renderDetail();
pending.reject(new Error('old actor request failed'));await saving;
assert.equal(reviewError,'');
assert.doesNotMatch(element('review-status').textContent,/old actor request failed/);
""")


@pytest.mark.parametrize("loader,cache", [("loadDeps", "deps"), ("loadTests", "tests")])
@pytest.mark.parametrize("failed", [False, True])
def test_evidence_response_cannot_write_into_another_context(tmp_path, loader, cache, failed):
    settle = "pending.reject(new Error('old context error'))" if failed else "pending.resolve({old_actor:true})"
    run_js(tmp_path, f"""
let renders=0;renderDetail=()=>{{renders++;}};
const pending=deferred();let requested;
api=(path)=>{{requested=path;return pending.promise;}};
const loading={loader}('a');
assert.equal(new URL(requested,'http://localhost').searchParams.get('context_id'),'session-a');
state.context_id='another-actor-same-session';{cache}={{a:{{new_actor:true}}}};
{settle};await loading;
assert.deepEqual({cache}.a,{{new_actor:true}});assert.equal(renders,0);
""", validation=True)


@pytest.mark.parametrize("operation", ["decideCase('case-a','accepted','a')", "recordRun('case-a','pass','a')"])
def test_test_review_cannot_refresh_another_context(tmp_path, operation):
    run_js(tmp_path, f"""
renderDetail=()=>{{}};const pending=deferred();let sent,calls=0;
api=(path,body)=>{{calls++;sent=body;return pending.promise;}};
const saving={operation};
state.context_id='another-actor-same-session';tests={{a:{{new_actor:true}}}};
pending.resolve({{}});await saving;
assert.equal(sent.context_id,'session-a');assert.equal(calls,1);
assert.deepEqual(tests.a,{{new_actor:true}});
""", validation=True)


def test_new_test_refresh_supersedes_inflight_evidence_request(tmp_path):
    run_js(tmp_path, r"""
let renders=0;renderDetail=()=>{renders++;};
const older=deferred(),newer=deferred();let calls=0;
api=()=>++calls===1?older.promise:newer.promise;
const first=loadTests('a');delete tests.a;
const second=loadTests('a');newer.resolve({cases:['new decision']});await second;
older.resolve({cases:['old decision']});await first;
assert.deepEqual(tests.a,{cases:['new decision']});assert.equal(renders,1);
""", validation=True)
