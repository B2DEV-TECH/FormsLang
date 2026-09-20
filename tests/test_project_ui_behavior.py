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
const missingElements = new Set();
function $(id) {
  if (missingElements.has(id)) return null;
  if (!elements.has(id)) elements.set(id, {
    value:'',textContent:'',innerHTML:'',hidden:false,disabled:false,dataset:{},style:{},
    attrs:{},classList:{toggle(){},add(){},remove(){},contains(){return false;}},
    setAttribute(k,v){this.attrs[k]=v;},removeAttribute(k){delete this.attrs[k];},
    insertAdjacentHTML(position,html){this.innerHTML+=html;},
    focus(){this.focused=true;},querySelector(){return null;},querySelectorAll(){return [];},addEventListener(){},
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
const overviewData={
  project:{id:'a',name:'Orders',client_label:'Example Corp',target:{platform:'Oracle APEX',version:'26.1',representation:'APEXlang'}},
  assessment:{status:'Current',completion_state:'COMPLETE',freshness:'CURRENT',analysis_revision:'r',source_revision:'s',review_revision:2,assessment_timestamp:'2026-09-20T12:00:00Z'},freshness:{status:'CURRENT',reasons:[]},
  analysis_revision:'r',source_revision:'s',review_revision:2,assessment_timestamp:'2026-09-20T12:00:00Z',
  inventory:{forms_modules:2,plsql_libraries:1,database_packages:1,views:1,tables:1,triggers:4,program_units:3,dependencies:7,modernization_findings:4,business_rule_candidates:2},
  risk_distribution:{CRITICAL:1,HIGH:1,MEDIUM:0,LOW:0,UNKNOWN:2},
  recommendation_distribution:{PRESERVE:1,CONVERT:0,REPLACE_WITH_APEX_NATIVE:1,REFACTOR:0,MOVE_TO_PLSQL_API:1,MANUAL_REVIEW:1,DROP:0,UNKNOWN:0},
  intervention_distribution:{AUTO:1,ASSISTED:2,MANUAL:1,UNKNOWN:0},
  automation_potential:{total:4,categories:{AUTO:{count:1,percent:25},ASSISTED:{count:2,percent:50},MANUAL:{count:1,percent:25},UNKNOWN:{count:0,percent:0}}},
  priority:{total:3,critical:1,high:1,manual:1,stale:0,first_finding_id:'finding:critical'},
  source_coverage:{forms:{discovered:3,analyzed:2,failed:1},database:{discovered:2,analyzed:2,failed:0},libraries:{discovered:1,without_semantic_representation:1}},
  warnings:[{code:'UNSUPPORTED_REPRESENTATION',message:'One library needs a semantic representation.',remediation:'Supply XML.'}],
  review_progress:{reviewed:1,total:4,critical_resolved:0,critical_total:1}
};
const inventoryPage={category:'findings',query:'',filters:{},sort:'name',offset:0,limit:50,total:2,analysis_revision:'r',source_revision:'s',review_revision:2,assessment_timestamp:'2026-09-20T12:00:00Z',freshness:'CURRENT',rows:[
  {id:'finding:critical',name:'WHEN-VALIDATE-ITEM',module:'orders.xml',source_type:'TRIGGER',risk:'CRITICAL',recommendation:'MANUAL_REVIEW',intervention:'MANUAL',review_state:'PENDING',reason:'Approval control.',priority_factors:['UNRESOLVED_CRITICAL']},
  {id:'finding:high',name:'PRE-INSERT',module:'orders.xml',source_type:'TRIGGER',risk:'HIGH',recommendation:'MOVE_TO_PLSQL_API',intervention:'ASSISTED',review_state:'PENDING',reason:'Reuse ORDER_API.',priority_factors:['UNRESOLVED_HIGH']}
]};
const inventoryDetail={category:'findings',item:inventoryPage.rows[0],dependencies:[{id:'edge:1',source:'ORDERS',target:'ORDER_API',relationship:'CALLS'}],dependencies_total:1,related_findings:[inventoryPage.rows[0]],related_findings_total:1,analysis_revision:'r',source_revision:'s',review_revision:2,assessment_timestamp:'2026-09-20T12:00:00Z',freshness:'CURRENT'};
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
assert.match($('project-content').innerHTML,/Orders/);assert.equal(reads,2);
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


def test_demo_pending_open_cannot_start_analysis_of_switched_project(tmp_path):
    run_js(tmp_path, r'''
projectEnter('home');projectUI.activeId=null;
const opening=deferred(),calls=[];
// Distinguish demo creation POST from the subsequent project GET.
api=(path,body)=>{calls.push([path,body]);
  if(path==='/api/v2/projects/demo')return body===undefined?opening.promise:Promise.resolve({project:{id:'demo'}});
  return Promise.reject(new Error('Unexpected request '+path));
};
const pending=projectDemo();await Promise.resolve();await Promise.resolve();
assert.equal(projectUI.activeId,'demo');
projectEnter('summary');projectUI.activeId='b';projectUI.summary={...summary,project:{...summary.project,id:'b'}};
opening.resolve({...summary,project:{...summary.project,id:'demo'}});await pending;
assert.ok(!calls.some(([path])=>path.endsWith('/analyze')),JSON.stringify(calls));
assert.equal(projectUI.activeId,'b');
''')


def test_overview_renders_real_distributions_priority_and_coverage(tmp_path):
    run_js(tmp_path, r'''
projectUI.activeId='a';projectUI.summary=summary;
renderProjectOverview(overviewData);
const html=$('project-content').innerHTML;
assert.match(html,/Application Inventory/);assert.match(html,/Forms Modules/);
assert.match(html,/Critical/);assert.match(html,/Unknown/);
assert.match(html,/Use Native APEX/);assert.match(html,/Move to PL\/SQL API/);
assert.match(html,/Mechanical \/ AUTO/);assert.match(html,/Start Priority Review/);
assert.match(html,/Forms representations/);assert.match(html,/2 \/ 3 analyzed/);
assert.match(html,/One library needs a semantic representation/);
assert.match(html,/2026-09-20T12:00:00Z/);assert.match(html,/Oracle APEX 26.1 \/ APEXlang/);
assert.equal(projectUI.overview.analysis_revision,'r');
''')


def test_overview_zero_critical_has_explanatory_empty_state(tmp_path):
    run_js(tmp_path, r'''
projectUI.activeId='a';projectUI.summary=summary;
renderProjectOverview({...overviewData,risk_distribution:{...overviewData.risk_distribution,CRITICAL:0},priority:{...overviewData.priority,critical:0}});
assert.match($('project-content').innerHTML,/No unresolved CRITICAL findings/);
''')


def test_overview_priority_uses_unresolved_counts_not_raw_risk_total(tmp_path):
    run_js(tmp_path, r'''
projectUI.activeId='a';projectUI.summary=summary;
renderProjectOverview({...overviewData,risk_distribution:{...overviewData.risk_distribution,CRITICAL:2},priority:{...overviewData.priority,critical:1}});
const priority=$('project-content').innerHTML.split('id="project-priority"')[1];
assert.match(priority,/<b>1<\/b> Critical/);assert.ok(!priority.includes('<b>2</b> Critical'));
''')


def test_stale_overview_refresh_does_not_require_summary_button(tmp_path):
    run_js(tmp_path, r'''
projectUI.activeId='a';projectUI.summary=summary;
renderProjectOverview({...overviewData,assessment:{...overviewData.assessment,freshness:'STALE'}});
missingElements.add('project-analyze');
let calls=[];api=async(path,body)=>{calls.push([path,body]);if(path.endsWith('/analyze'))return {job_id:'job-refresh'};if(path.includes('/jobs/'))return {job_id:'job-refresh',status:'RUNNING',phase:'DISCOVERY',processed:0,total:null};return {...summary,last_job:{job_id:'job-refresh',operation:'ANALYZE',status:'RUNNING'}};};
await $('project-refresh').onclick();
assert.equal(projectUI.jobId,'job-refresh');assert.match(calls[0][0],/\/analyze$/);
assert.equal(projectUI.view,'progress');
''')


def test_overview_escapes_hostile_project_and_warning_text(tmp_path):
    run_js(tmp_path, r'''
projectUI.activeId='a';projectUI.summary=summary;
renderProjectOverview({...overviewData,project:{...overviewData.project,name:'<img src=x onerror=alert(1)>'},warnings:[{message:'<script>bad()</script>',remediation:'<b>unsafe</b>'}]});
const html=$('project-content').innerHTML;
assert.ok(!html.includes('<img'));assert.ok(!html.includes('<script>'));assert.ok(!html.includes('<b>unsafe'));
assert.match(html,/&lt;img/);assert.match(html,/&lt;script/);
''')


def test_overview_navigation_and_status_are_accessible(tmp_path):
    run_js(tmp_path, r'''
projectUI.activeId='a';projectUI.summary=summary;renderProjectOverview(overviewData);
const html=$('project-content').innerHTML;
assert.match(html,/<nav[^>]+aria-label="Project sections"/);
assert.match(html,/aria-current="page"[^>]*>Overview/);
assert.match(html,/<h2[^>]*>Orders<\/h2>/);assert.match(html,/Assessment status/);
assert.match(html,/aria-label="Risk distribution"/);assert.match(html,/project-priority/);
assert.equal($('project-status').attrs['aria-live'],'polite');
''')


def test_open_project_loads_saved_overview_without_reanalysis(tmp_path):
    run_js(tmp_path, r'''
const calls=[];api=async(path,body)=>{calls.push([path,body]);if(path.endsWith('/overview'))return overviewData;if(path.endsWith('/freshness'))return {job_id:'freshness-a'};return summary;};
await openProject('a',false);
assert.ok(calls.some(([path])=>path==='/api/v2/projects/a/overview'));
assert.ok(!calls.some(([path])=>path.endsWith('/analyze')));
assert.match($('project-content').innerHTML,/Application Inventory/);
''')


def test_completed_freshness_poll_returns_to_saved_overview(tmp_path):
    run_js(tmp_path, r'''
projectUI.activeId='a';projectUI.jobId='freshness-a';projectUI.operation='FRESHNESS';projectUI.summary=summary;projectUI.view='summary';
api=async(path)=>path.includes('/jobs/')?{job_id:'freshness-a',status:'COMPLETED',phase:'FRESHNESS',processed:0,total:null}:path.endsWith('/overview')?{overview:overviewData}:summary;
await pollProjectJob();assert.equal(projectUI.view,'overview');assert.equal(projectUI.overview.assessment.freshness,'CURRENT');
assert.match($('project-content').innerHTML,/Application Inventory/);
''')


def test_inventory_sends_category_search_filters_and_revision_on_pages(tmp_path):
    run_js(tmp_path, r'''
projectUI.activeId='a';projectUI.summary=summary;projectUI.overview=overviewData;const calls=[];
api=async(path)=>{calls.push(path);return {...inventoryPage,offset:path.includes('offset=50')?50:0};};
await projectOpenInventory({category:'findings',filters:{risk:'HIGH',recommendation:'MOVE_TO_PLSQL_API'}});
assert.match(calls[0],/category=findings/);assert.match(calls[0],/risk=HIGH/);assert.match(calls[0],/recommendation=MOVE_TO_PLSQL_API/);
assert.match($('project-content').innerHTML,/Inventory/);assert.match($('project-content').innerHTML,/<table/);assert.match($('project-content').innerHTML,/PRE-INSERT/);
$('project-inventory-search').value='order api';await projectApplyInventoryFilters();
assert.match(calls[1],/query=order\+api/);
await projectInventoryPage(50);assert.match(calls[2],/offset=50/);assert.match(calls[2],/revision=r/);
''')


def test_inventory_tabs_and_empty_state_use_safe_observed_language(tmp_path):
    run_js(tmp_path, r'''
projectUI.activeId='a';projectUI.summary=summary;projectUI.overview={...overviewData,source_coverage:{...overviewData.source_coverage,database:{sources:0,analyzed:0}}};
api=async(path)=>({...inventoryPage,category:'tables',rows:[],total:0});
await projectOpenInventory({category:'tables'});const html=$('project-content').innerHTML;
for(const label of ['Forms','Libraries','Packages','Routines','Views','Tables','Dependencies','Business Rules','Findings'])assert.match(html,new RegExp(label));
assert.match(html,/No observed Tables match the current search and filters/);assert.match(html,/<caption>/);assert.match(html,/scope="col"/);
assert.match(html,/No database source was supplied/);
''')


def test_inventory_tab_arrow_keys_activate_and_focus_adjacent_category(tmp_path):
    run_js(tmp_path, r'''
projectUI.activeId='a';projectUI.summary=summary;projectUI.overview=overviewData;
const content=$('project-content'),tabs=['forms','libraries','packages'].map(category=>({dataset:{projectCategory:category},focused:false,focus(){this.focused=true;}}));
content.querySelectorAll=selector=>selector==='[data-project-category]'?tabs:[];
content.querySelector=selector=>tabs.find(tab=>selector.includes(tab.dataset.projectCategory))||null;
api=async()=>({...inventoryPage,category:'libraries',rows:[],total:0});
let prevented=false;await projectInventoryTabKey({key:'ArrowRight',currentTarget:tabs[0],preventDefault(){prevented=true;}});
assert.equal(prevented,true);assert.equal(projectUI.inventoryState.category,'libraries');assert.equal(tabs[1].focused,true);
''')


def test_inventory_detail_is_bounded_escaped_and_restores_focus(tmp_path):
    run_js(tmp_path, r'''
projectUI.activeId='a';projectUI.summary=summary;projectUI.overview=overviewData;
api=async(path)=>path.includes('/inventory/findings/')?{...inventoryDetail,item:{...inventoryDetail.item,name:'<img onerror=bad()>'}}:inventoryPage;
await projectOpenInventory({category:'findings'});const trigger=$('detail-trigger');trigger.focus();
projectUI.inventoryState.offset=50;projectUI.inventoryState.filters={risk:'CRITICAL'};
await projectInventoryDetail('finding:critical',trigger);
assert.match($('modal-body').innerHTML,/CALLS/);assert.match($('modal-body').innerHTML,/Approval control/);
assert.ok(!$('modal-body').innerHTML.includes('<img'));assert.match($('modal-body').innerHTML,/&lt;img/);
projectCloseInventoryDetail();assert.equal(trigger.focused,true);assert.equal(projectUI.inventoryState.offset,50);assert.deepEqual(projectUI.inventoryState.filters,{risk:'CRITICAL'});
''')


def test_dependency_detail_names_source_relationship_and_target(tmp_path):
    run_js(tmp_path, r'''
projectUI.activeId='a';projectUI.summary=summary;projectUI.overview=overviewData;
projectUI.inventoryState={category:'dependencies',revision:'r',selectedId:null,returnFocus:null};
api=async()=>({category:'dependencies',item:{id:'edge:1',source:'ORDERS',relationship:'CALLS',target:'ORDER_API'},dependencies:[],dependencies_total:0,related_findings:[],related_findings_total:0,analysis_revision:'r'});
await projectInventoryDetail('edge:1');const html=$('modal-body').innerHTML;
assert.match(html,/ORDERS/);assert.match(html,/CALLS/);assert.match(html,/ORDER_API/);
''')


def test_priority_inventory_carries_transparent_filter_and_revision(tmp_path):
    run_js(tmp_path, r'''
projectUI.activeId='a';projectUI.summary=summary;projectUI.overview=overviewData;let path;
api=async(value)=>{path=value;return inventoryPage;};await projectOpenInventory({category:'findings',priority:true});
assert.match(path,/priority=unresolved/);assert.match(path,/revision=r/);assert.equal(projectUI.inventoryState.category,'findings');
''')


def test_priority_review_deep_link_carries_project_finding_filter_and_revision(tmp_path):
    run_js(tmp_path, r'''
projectUI.activeId='a';projectUI.summary=summary;projectUI.overview=overviewData;const calls=[];
api=async(path)=>{calls.push(path);return path.includes('/inventory/findings/')?inventoryDetail:inventoryPage;};
await projectOpenPriorityReview();
assert.deepEqual(projectUI.reviewContext,{project_id:'a',finding_id:'finding:critical',filters:{priority:'unresolved'},analysis_revision:'r'});
assert.match(calls[0],/priority=unresolved/);assert.match(calls[0],/revision=r/);
assert.match(calls[1],/inventory\/findings\/finding%3Acritical\?revision=r/);
assert.match($('modal-body').innerHTML,/Approval control/);
''')


def test_priority_filter_survives_search_and_filter_changes(tmp_path):
    run_js(tmp_path, r'''
projectUI.activeId='a';projectUI.summary=summary;projectUI.overview=overviewData;let path;
api=async(value)=>{path=value;return inventoryPage;};await projectOpenInventory({category:'findings',priority:true});
$('project-inventory-search').value='approval';await projectApplyInventoryFilters();
assert.match(path,/priority=unresolved/);assert.match(path,/query=approval/);
''')


def test_late_inventory_and_search_responses_cannot_overwrite_new_state(tmp_path):
    run_js(tmp_path, r'''
projectUI.activeId='a';projectUI.summary=summary;projectUI.overview=overviewData;
const old=deferred(),recent=deferred();let n=0;api=()=>++n===1?old.promise:recent.promise;
const first=projectOpenInventory({category:'forms'});projectUI.activeId='b';projectUI.generation++;projectUI.summary={...summary,project:{...summary.project,id:'b',name:'Finance'}};projectUI.overview={...overviewData,project:{...overviewData.project,id:'b',name:'Finance'}};
const second=projectOpenInventory({category:'packages'});recent.resolve({...inventoryPage,category:'packages',rows:[{id:'package:new',name:'FINANCE_API',spec:true,body:true}],total:1,analysis_revision:'b'.repeat(64)});await second;
old.resolve({...inventoryPage,category:'forms',rows:[{id:'form:old',name:'ORDERS'}],total:1});await first;
assert.equal(projectUI.activeId,'b');assert.equal(projectUI.inventoryState.category,'packages');assert.match($('project-content').innerHTML,/FINANCE_API/);assert.ok(!$('project-content').innerHTML.includes('ORDERS'));
const searchOld=deferred(),searchNew=deferred();n=0;api=()=>++n===1?searchOld.promise:searchNew.promise;
$('project-inventory-search').value='old';const oldSearch=projectApplyInventoryFilters();$('project-inventory-search').value='new';const newSearch=projectApplyInventoryFilters();
searchNew.resolve({...inventoryPage,query:'new',rows:[{id:'new',name:'NEW RESULT'}],total:1,analysis_revision:'b'.repeat(64)});await newSearch;
searchOld.resolve({...inventoryPage,query:'old',rows:[{id:'old',name:'OLD RESULT'}],total:1,analysis_revision:'b'.repeat(64)});await oldSearch;
assert.match($('project-content').innerHTML,/NEW RESULT/);assert.ok(!$('project-content').innerHTML.includes('OLD RESULT'));
''')


def test_inventory_revision_conflict_resets_and_reloads_first_page(tmp_path):
    run_js(tmp_path, r'''
projectUI.activeId='a';projectUI.summary=summary;projectUI.overview=overviewData;const calls=[];
api=async(path)=>{calls.push(path);if(path.includes('offset=50')){const e=new Error('Assessment changed; reload inventory from the first page');e.status=409;e.code='PROJECT_CONFLICT';throw e;}if(path.endsWith('/overview'))return {overview:overviewData};return inventoryPage;};
await projectOpenInventory({category:'findings'});await projectInventoryPage(50);
assert.equal(projectUI.inventoryState.offset,0);assert.equal(projectUI.inventoryState.revision,'r');
assert.equal(calls.filter(path=>path.includes('offset=0')).length,2);
assert.match($('project-status').textContent,/assessment changed/i);assert.ok(!$('project-content').innerHTML.includes('mixed'));
''')


def test_inventory_revision_conflict_refreshes_overview_before_reloading_page(tmp_path):
    run_js(tmp_path, r'''
projectUI.activeId='a';projectUI.summary=summary;projectUI.overview=overviewData;const calls=[];
const newer={...overviewData,assessment:{...overviewData.assessment,analysis_revision:'n'},inventory:{...overviewData.inventory,forms_modules:9}};
api=async(path)=>{calls.push(path);if(path.includes('offset=50')){const e=new Error('Assessment changed');e.status=409;throw e;}if(path.endsWith('/overview'))return {overview:newer};return {...inventoryPage,analysis_revision:'n'};};
await projectOpenInventory({category:'findings'});await projectInventoryPage(50);
assert.equal(projectUI.overview.assessment.analysis_revision,'n');assert.equal(projectUI.inventoryState.revision,'n');
renderProjectOverview(projectUI.overview);assert.match($('project-content').innerHTML,/Forms Modules<\/dt><dd>9/);
assert.ok(calls.some(path=>path.endsWith('/overview')));
''')
