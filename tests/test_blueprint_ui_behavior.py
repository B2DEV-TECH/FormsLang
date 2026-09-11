"""Race-condition regression tests for the actual Blueprint UI JavaScript."""

from __future__ import annotations

import shutil
import subprocess

import pytest

from formslang.ui.blueprint import BLUEPRINT_JS

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="Node needed for JavaScript behavior tests")

DOM = r"""
const assert = require('node:assert/strict');
const elements = new Map();
function $(id) {
  if (!elements.has(id)) elements.set(id, {
    value: '', textContent: '', innerHTML: '', hidden: false, disabled: false,
    dataset: {}, listeners: {}, setAttribute() {}, focus() {},
    addEventListener(type,fn) { this.listeners[type]=fn; },
  });
  return elements.get(id);
}
const window = { addEventListener() {} };
const document = { querySelectorAll() { return []; } };
const esc = s => String(s ?? '').replaceAll('<','&lt;');
let modalGeneration = 1, timers = [];
function setTimeout(fn) { timers.push(fn); return timers.length; }
function clearTimeout() {}
function deferred() { let resolve, reject; const promise = new Promise((a,b) => {resolve=a;reject=b;}); return {promise,resolve,reject}; }
let api;
function toast() {}
function context() { bpScreen=1; bpContext={screen:1,generation:modalGeneration,d:{context_id:'local-session',source_revision:'revision-a'}}; return bpContext; }
const running = {status:'running',job_id:'job-a',elapsed_seconds:3};
const finished = {status:'completed',job_id:'job-a',result:{sections:[]}};
"""


def run_js(tmp_path, script):
    path = tmp_path / "blueprint-behavior.cjs"
    path.write_text(
        DOM + BLUEPRINT_JS + "\n(async()=>{\ncontext();\n" + script
        + "\n})().catch(e=>{console.error(e);process.exitCode=1;});\n",
        encoding="utf-8",
    )
    result = subprocess.run([NODE, str(path)], capture_output=True, text=True, timeout=15, check=False)
    assert result.returncode == 0, result.stdout + result.stderr


def test_initial_ai_status_cannot_overwrite_newer_start(tmp_path):
    run_js(tmp_path, r"""
const initial=deferred(),start=deferred();
api=(path,body)=>body?start.promise:initial.promise;
const old=bpResumeAI('application');
const newRequest=bpStartAI('application');
start.resolve(finished); await newRequest;
assert.match($('bp-ai-status').textContent,/proposal ready/);
initial.resolve(running); await old;
assert.match($('bp-ai-status').textContent,/proposal ready/);
assert.equal($('bp-ai-overview').disabled,false);
assert.equal(bpPolls.size,0);
""")


def test_inflight_poll_cannot_restore_running_after_discard(tmp_path):
    run_js(tmp_path, r"""
$('bp-ai-cancel').dataset.job='job-a';
const polling=deferred(),cancel=deferred();
api=(path)=>path.includes('/cancel')?cancel.promise:polling.promise;
const old=bpResumeAI('application','','job-a');
const discarding=bpCancelAI('application');
cancel.resolve({status:'cancelled',job_id:'job-a'}); await discarding;
assert.match($('bp-ai-status').textContent,/Result discarded/);
polling.resolve(running); await old;
assert.match($('bp-ai-status').textContent,/Result discarded/);
assert.equal($('bp-ai-overview').disabled,false);
assert.equal($('bp-ai-cancel').hidden,true);
assert.equal(bpPolls.size,0);
""")


@pytest.mark.parametrize("operation", ["bpResumeAI('application')", "bpStartAI('application')"])
def test_late_response_cannot_write_into_reopened_modal(tmp_path, operation):
    run_js(tmp_path, f"""
const delayed=deferred();api=()=>delayed.promise;
const pending={operation};
modalGeneration++;bpDetach();
$('bp-ai-status').textContent='another screen';
delayed.resolve(finished);await pending;
assert.equal($('bp-ai-status').textContent,'another screen');
assert.equal(bpAdvisory,null);
assert.equal(bpPolls.size,0);
""")


def test_old_entity_explanation_cannot_replace_selected_component(tmp_path):
    run_js(tmp_path, r"""
bpSelectedFinding='first';const delayed=deferred();api=()=>delayed.promise;
const pending=bpResumeAI('entity','first');
bpSelectedFinding='second';$('bp-ai-result').textContent='second component';
delayed.resolve({status:'completed',result:{text:'first component'}});await pending;
assert.equal($('bp-ai-result').textContent,'second component');
assert.equal(bpPolls.size,0);
""")


def test_ai_error_from_old_request_cannot_replace_success(tmp_path):
    run_js(tmp_path, r"""
const old=deferred(),recent=deferred();api=(path,body)=>body?recent.promise:old.promise;
const pending=bpResumeAI('application');const started=bpStartAI('application');
recent.resolve(finished);await started;
old.reject(new Error('old network failure'));await pending;
assert.match($('bp-ai-status').textContent,/proposal ready/);
assert.equal($('bp-ai-overview').disabled,false);
""")


def test_failed_discard_resumes_status_check(tmp_path):
    run_js(tmp_path, r"""
$('bp-ai-cancel').dataset.job='job-a';
api=async()=>{throw new Error('temporary network error');};
await bpCancelAI('application');
assert.match($('bp-ai-status').textContent,/temporary network error/);
assert.equal(bpPolls.size,1);
assert.equal($('bp-ai-cancel').disabled,false);
""")


def test_blueprint_review_preserves_newer_edits_during_save(tmp_path):
    run_js(tmp_path, r"""
bpDraftScope='local-session';$('reviewer').value='Test Reviewer';
bpResumeAI=async()=>{};
const detail={entity:{id:'trigger-a',name:'WHEN-VALIDATE-ITEM',type:'TRIGGER',attributes:{}},
  finding:{entity:'trigger-a',revision:'r1',recommendation:'REFACTOR',suggested_target:'Domain layer',
    classification:[],unresolved_questions:[],statements:[]},
  neighbors:[],evidence:[],inbound:[],outbound:[],evidence_total:0};
bpDetail(detail);
$('bp-comment').value='first rationale';$('bp-comment').listeners.input();
const pending=deferred();let submitted;
api=(path,body)=>{submitted=body;return pending.promise;};
showBlueprint=async()=>{bpDetail(detail);};
const saving=$('bp-save').onclick();
$('bp-comment').value='newer rationale';$('bp-comment').listeners.input();
pending.resolve({});await saving;
assert.equal(submitted.comment,'first rationale');
assert.equal($('bp-comment').value,'newer rationale');
assert.equal(bpDrafts.size,1);
""")
