"""Behavioral tests execute the production project UI JavaScript in Node."""

import shutil
import subprocess

import pytest

from formslang.ui.modernization_project import PROJECT_JS

NODE = shutil.which('node')
pytestmark = pytest.mark.skipif(NODE is None, reason='Node needed for JavaScript behavior tests')
DOM = r'''
const assert = require('node:assert/strict');
const elements = new Map();
function $(id) {
  if (!elements.has(id)) elements.set(id, {
    value:'',textContent:'',innerHTML:'',hidden:false,disabled:false,dataset:{},style:{},
    attrs:{},classList:{toggle(){},add(){},remove(){},contains(){return false;}},
    setAttribute(k,v){this.attrs[k]=v;},removeAttribute(k){delete this.attrs[k];},
    insertAdjacentHTML(position,html){this.innerHTML+=html;},
    focus(){this.focused=true;},querySelectorAll(){return [];},addEventListener(){},
  });
  return elements.get(id);
}
const document={body:$('body'),querySelectorAll(){return [];},querySelector(){return $('main');}};
const window={addEventListener(){}};
const esc = s=>String(s??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;');
let api, timers=[];
function setTimeout(fn){timers.push(fn);return timers.length;}
function clearTimeout(){}
function setNavigationOpen(){} function setShellSection(){} function closeModal(){}
function openModal(){} function foot(){} function toast(){}
let state={session:{},tasks:[]},modalGeneration=0;
function deferred(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};}
const summary={project:{id:'a',name:'Orders',target_platform:'Oracle APEX',target_version:'26.1',target_representation:'APEXlang',source_roots:[],analysis_revision:'r'},configuration_revision:3,inventory:{forms:{analyzed:2}},freshness:{status:'UNVERIFIED'},last_job:null};
'''


def run_js(tmp_path, script):
    path = tmp_path / 'project-ui.cjs'
    path.write_text(DOM + PROJECT_JS + '\n(async()=>{\n' + script +
                    "\n})().then(()=>console.log('COMPLETE')).catch(e=>{console.error(e);process.exitCode=1;});", encoding='utf-8')
    result = subprocess.run([NODE, str(path)], capture_output=True, text=True, timeout=60, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'COMPLETE' in result.stdout.splitlines(), result.stdout + result.stderr


def test_name_and_sources_are_required_before_analysis(tmp_path):
    run_js(tmp_path, r'''
api=async()=>{throw new Error('No API call expected');};
newProject(); $('project-name').value='  '; projectNext();
assert.equal(projectUI.draft.step,1);
assert.match($('project-error').textContent,/name/i);
assert.equal($('project-name').attrs['aria-invalid'],'true');
$('project-name').value='Orders'; projectNext();
assert.equal(projectUI.draft.step,2);
projectNext(); assert.equal(projectUI.draft.step,2);
await startProjectAnalysis(); assert.equal(projectUI.activeId,null);
''')


def test_late_discovery_cannot_populate_another_screen(tmp_path):
    run_js(tmp_path, r'''
newProject();projectUI.draft.sources=[{root_id:'x',kind:'forms',area_id:'x',relative_path:''}];
const response=deferred();api=()=>response.promise;
const pending=previewSources(); projectLeave();
$('project-preview').innerHTML='new screen';
response.resolve({inventory:{forms:{parseable:33}},entries:[],diagnostics:[],total:33});await pending;
assert.equal($('project-preview').innerHTML,'new screen');
''')


def test_old_job_response_cannot_update_switched_project(tmp_path):
    run_js(tmp_path, r'''
projectUI.activeId='a';projectUI.jobId='job-a';projectUI.view='progress';
const response=deferred();api=()=>response.promise;
const pending=pollProjectJob();projectUI.activeId='b';projectUI.generation++;
$('project-status').textContent='B';
response.resolve({status:'RUNNING',phase:'FORMS_PARSING',processed:8,total:10});await pending;
assert.equal($('project-status').textContent,'B'); assert.equal(timers.length,0);
''')


def test_draft_survives_navigation_and_escapes_user_content(tmp_path):
    run_js(tmp_path, r'''
newProject();$('project-name').value='<img src=x onerror=alert(1)>';projectNext();
projectLeave();newProject();assert.equal(projectUI.draft.step,2);
assert.equal(projectUI.draft.name,'<img src=x onerror=alert(1)>');
renderProjectSummary({...summary,project:{...summary.project,name:'<script>bad()</script>'}});
assert.ok(!$('project-content').innerHTML.includes('<script>'));
''')


def test_analysis_write_keeps_captured_project_and_preconditions(tmp_path):
    run_js(tmp_path, r'''
projectUI.activeId='a';projectUI.view='summary';projectUI.summary=summary;
const response=deferred(),calls=[];api=(path,body)=>{calls.push([path,body]);return response.promise;};
const pending=startProjectAnalysis();projectUI.activeId='b';projectUI.generation++;
$('project-status').textContent='Project B';response.resolve({job_id:'job-a'});await pending;
assert.deepEqual(calls,[['/api/v2/projects/a/analyze',{expected_revision:'r',expected_configuration:3}]]);
assert.equal(projectUI.jobId,null);assert.equal($('project-status').textContent,'Project B');
''')


def test_saved_summary_precedes_freshness_completion(tmp_path):
    run_js(tmp_path, r'''
const check=deferred();let reads=0;
api=(path)=>{if(path.endsWith('/freshness'))return check.promise;reads++;return Promise.resolve(summary);};
const pending=openProject('a');await Promise.resolve();await Promise.resolve();
assert.match($('project-content').innerHTML,/Orders/);assert.equal(reads,1);
projectLeave();check.resolve({job_id:'freshness-a'});await pending;
assert.equal(projectUI.jobId,null);
''')


def test_analysis_conflict_restores_controls_and_shows_reload(tmp_path):
    run_js(tmp_path, r'''
projectUI.activeId='a';projectUI.view='summary';projectUI.summary=summary;
api=async()=>{throw new Error('Project revision changed');};await startProjectAnalysis();
assert.equal(projectUI.busy,false);assert.match($('project-error').textContent,/Reload Project/);
assert.match($('project-content').innerHTML,/project-reload/);
''')


def test_cancel_response_cannot_overwrite_terminal_state(tmp_path):
    run_js(tmp_path, r'''
projectUI.activeId='a';projectUI.jobId='job-a';const response=deferred();api=()=>response.promise;
const pending=projectCancel();projectUI.jobId=null;$('project-status').textContent='Assessment created';
response.resolve({status:'COMPLETED'});await pending;
assert.equal($('project-status').textContent,'Assessment created');
''')


def test_preview_pagination_requests_only_fifty_entries(tmp_path):
    run_js(tmp_path, r'''
newProject();projectUI.draft.sources=[{root_id:'x',kind:'forms',area_id:'x',relative_path:''}];
let sent;api=async(path,body)=>{sent={path,body};return {inventory:{},entries:[],diagnostics:[],total:120};};
await previewSources(50,true);assert.equal(sent.body.limit,50);assert.equal(sent.body.offset,50);
assert.match($('project-preview').innerHTML,/project-next-files/);assert.match($('project-preview').innerHTML,/project-prev-files/);
''')


def test_authenticated_picker_has_no_raw_path_fallback(tmp_path):
    run_js(tmp_path, r'''
newProject();api=async()=>({local:false,areas:[],target_profile:{platform:'Oracle APEX',version:'26.1',representation:'APEXlang'}});
await projectPickSource('forms');assert.match($('project-area-list').innerHTML,/host administrator/);
assert.ok(!$('modal-body').innerHTML.includes('project-folder-path'));
''')


def test_newest_discovery_wins_even_in_same_wizard(tmp_path):
    run_js(tmp_path, r'''
newProject();projectUI.draft.sources=[{root_id:'x',kind:'forms',area_id:'x',relative_path:''}];
const first=deferred(),second=deferred();let n=0;api=()=>++n===1?first.promise:second.promise;
const old=previewSources(),recent=previewSources();second.resolve({inventory:{forms:{parseable:2}},entries:[],diagnostics:[],total:2});await recent;
first.resolve({inventory:{forms:{parseable:99}},entries:[],diagnostics:[],total:99});await old;
assert.equal(projectUI.draft.preview.total,2);
''')


def test_closed_picker_cannot_be_reopened_by_late_request(tmp_path):
    run_js(tmp_path, r'''
newProject();const response=deferred();api=()=>response.promise;
const pending=projectPickSource('forms');modalGeneration++;
$('modal-body').innerHTML='unrelated dialog';response.resolve({local:false,areas:[]});await pending;
assert.equal($('modal-body').innerHTML,'unrelated dialog');
''')


def test_source_selection_identity_does_not_collapse_path_spellings(tmp_path):
    run_js(tmp_path, r'''
const first=projectSourceSelection('area','forms','lib/a_b'),second=projectSourceSelection('area','forms','lib/a/b');
assert.notEqual(first.root_id,second.root_id);assert.equal(first.relative_path,'lib/a_b');assert.equal(second.relative_path,'lib/a/b');
''')


def test_conversion_requires_explicit_confirmation_and_captures_project(tmp_path):
    run_js(tmp_path, r'''
projectUI.activeId='a';projectUI.summary=summary;let calls=[];
api=async(path,body)=>{calls.push({path,body});return {status:'FAILED',safe_failure:{safe_message:'No Oracle tool',remediation:'Supply XML'}};};
projectConvert('source-a');assert.equal(calls.length,0);
await $('project-convert-confirm').onclick();
assert.equal(calls[0].path,'/api/v2/projects/a/convert');assert.equal(calls[0].body.confirmed,true);
assert.equal(calls[0].body.expected_configuration,3);
assert.match($('project-error').textContent,/Supply XML/);
''')


def test_saved_diagnostics_are_bounded_and_pageable(tmp_path):
    run_js(tmp_path, r'''
projectUI.activeId='a';projectUI.summary=summary;
const diagnostics=Array.from({length:51},(_,i)=>({relative_path:'source-'+i,safe_message:'Invalid XML',remediation:'Repair XML',error_code:'INVALID_XML'}));
api=async()=>({assessment:{analyzed_at:'2026-09-19',completion_state:'INCOMPLETE',inventory:{},blueprint:{findings:[]},diagnostics}});
await projectViewSaved();assert.ok(!$('project-saved-content').innerHTML.includes('source-50'));
await $('project-more-diagnostics').onclick();assert.match($('project-saved-content').innerHTML,/source-50/);
''')


def test_failed_run_is_visible_after_reopen(tmp_path):
    run_js(tmp_path, r'''
renderProjectSummary({...summary,last_job:{job_id:'failed-a',status:'FAILED',safe_failure:{safe_message:'No supported sources',remediation:'Select Forms2XML'}}});
assert.match($('project-content').innerHTML,/No supported sources/);assert.match($('project-content').innerHTML,/Select Forms2XML/);
''')


def test_reopen_live_analysis_exposes_cancel_again(tmp_path):
    run_js(tmp_path, r'''
api=async(path)=>path.includes('/jobs/')?{status:'RUNNING',phase:'BLUEPRINT',processed:0,total:null,job_id:'running-a'}:{...summary,last_job:{job_id:'running-a',operation:'ANALYZE',status:'RUNNING'}};
await openProject('a');assert.equal(projectUI.view,'progress');assert.match($('project-content').innerHTML,/project-cancel/);assert.equal(projectUI.jobId,'running-a');
''')


def test_unavailable_recent_locator_shows_remediation(tmp_path):
    run_js(tmp_path, r'''
api=async()=>({projects:[{project:{id:'missing'},warning:'Project is unavailable. Open its descriptor or restore its location.'}]});
await showProjectHome();assert.match($('project-recents').innerHTML,/restore its location/);
''')
