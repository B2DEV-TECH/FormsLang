"""Estate Intelligence UI behavior, executing the production JavaScript in Node."""

import subprocess

import pytest

from formslang.ui.modernization_generation import GENERATION_PROJECT_JS
from formslang.ui.modernization_project import PROJECT_JS
from formslang.ui.modernization_review import REVIEW_PROJECT_JS
from tests.test_project_ui_behavior import DOM, NODE

pytestmark = pytest.mark.skipif(NODE is None, reason='Node needed for JavaScript behavior tests')


def run_js(tmp_path, script):
    path = tmp_path / 'estate-ui.cjs'
    path.write_text(DOM + PROJECT_JS + REVIEW_PROJECT_JS + GENERATION_PROJECT_JS + '\n(async()=>{\n' + script +
                    "\n})().then(()=>console.log('COMPLETE')).catch(e=>{console.error(e);process.exitCode=1;});",
                    encoding='utf-8')
    result = subprocess.run([NODE, str(path)], capture_output=True, text=True, timeout=60, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'COMPLETE' in result.stdout.splitlines(), result.stdout + result.stderr


SEARCH_SETUP = r'''
$('global-search-container').hidden=true;
const result=(project,title,extra={})=>({query:'q',total:1,project_id:project,analysis_revision:'r',
  results:[{id:'id:'+title,category:'forms',category_label:'Form Module',title,subtitle:'',risk:'HIGH',
            action:{view:'system-map',focus:'form:'+title,target_id:'form:'+title},...extra}]});
'''


def test_older_search_response_never_replaces_a_newer_query(tmp_path):
    run_js(tmp_path, SEARCH_SETUP + r'''
projectUI.activeId='a';openGlobalSearch();
const slow=deferred(),fast=deferred();const calls=[];api=path=>{calls.push(path);return calls.length===1?slow.promise:fast.promise;};
const first=runGlobalSearch('ord');const second=runGlobalSearch('orders');
fast.resolve(result('a','NEW'));await second;slow.resolve(result('a','OLD'));await first;
assert.match($('global-search-list').innerHTML,/NEW/);assert.ok(!$('global-search-list').innerHTML.includes('OLD'));
assert.equal(globalSearch.results[0].title,'NEW');assert.ok(calls.every(p=>p.includes('/projects/a/search')&&p.includes('limit=20')));
''')


def test_search_response_for_a_previous_project_is_discarded(tmp_path):
    run_js(tmp_path, SEARCH_SETUP + r'''
projectUI.activeId='a';openGlobalSearch();
const pending=deferred();api=()=>pending.promise;const running=runGlobalSearch('orders');
projectUI.activeId='b';projectUI.generation++;
pending.resolve(result('a','FROM_A'));await running;
assert.ok(!$('global-search-list').innerHTML.includes('FROM_A'));assert.equal(globalSearch.results.length,0);
''')


def test_search_response_after_close_or_reopen_is_discarded(tmp_path):
    run_js(tmp_path, SEARCH_SETUP + r'''
projectUI.activeId='a';openGlobalSearch();
const pending=deferred();api=()=>pending.promise;const running=runGlobalSearch('orders');
closeGlobalSearch();openGlobalSearch();pending.resolve(result('a','STALE'));await running;
assert.ok(!$('global-search-list').innerHTML.includes('STALE'));
''')


def test_search_action_from_one_project_never_runs_against_another(tmp_path):
    run_js(tmp_path, SEARCH_SETUP + r'''
projectUI.activeId='a';openGlobalSearch();api=async()=>result('a','ORDERS');await runGlobalSearch('orders');
const item=globalSearch.results[0];let opened=null;projectSystemMapOpen=async o=>{opened=o;};
projectUI.activeId='b';projectUI.generation++;await executeSearchAction(item);
assert.equal(opened,null);assert.equal($('global-search-container').hidden,true);
projectUI.activeId='a';await executeSearchAction(item);assert.deepEqual(opened,{focus:'form:ORDERS'});
''')


def test_search_mismatched_project_id_in_response_is_ignored(tmp_path):
    run_js(tmp_path, SEARCH_SETUP + r'''
projectUI.activeId='a';openGlobalSearch();api=async()=>result('b','OTHER');await runGlobalSearch('orders');
assert.equal(globalSearch.results.length,0);
''')


def test_onboarding_offers_three_paths_and_sends_the_chosen_target(tmp_path):
    run_js(tmp_path, r'''
const choices=[{id:'unselected',label:'Analyze my Forms estate',description:'d'},{id:'apex',label:'Modernize to Oracle APEX',description:'d'},{id:'generic',label:'Target-neutral assessment package',description:'d'}];
const calls=[];api=async(path,body)=>{calls.push([path,body]);if(path==='/api/v2/source-areas')return {local:true,target_choices:choices,areas:[]};
  if(path==='/api/v2/projects'&&body)return {project:{id:'n',name:body.name,analysis_revision:null},configuration_revision:0};
  if(path.endsWith('/analyze'))return {job_id:'j'};if(path==='/api/v2/projects')return {projects:[]};return {};};
await showProjectHome();
const html=$('project-content').innerHTML;
for(const label of ['Analyze my Forms estate','Modernize to Oracle APEX','Explore Demo Project'])assert.match(html,new RegExp(label));
assert.ok(!/APEX Modernization<\/h2>/.test(html));
newProject('unselected');await projectLoadAreas();
Object.assign(projectUI.draft,{name:'Estate',sources:[{kind:'forms',root_id:'r',area_id:'x',relative_path:'f'}],step:3});renderProjectWizard();
assert.match($('project-content').innerHTML,/What do you want to do\?/);assert.match($('project-content').innerHTML,/value="unselected" checked/);
projectUI.draft.step=4;renderProjectWizard();pollProjectJob=async()=>{};renderProjectProgress=()=>{};
await startProjectAnalysis();
const created=calls.find(([p,b])=>p==='/api/v2/projects'&&b);assert.equal(created[1].target,'unselected');
''')


def test_unselected_target_labels_are_legitimate_states(tmp_path):
    run_js(tmp_path, r'''
projectUI.activeId='a';projectUI.summary=summary;
const neutral={...overviewData,project:{...overviewData.project,target:{platform:'UNSELECTED',version:'none',representation:'none'}},
  hotspots:{total:1,by_severity:{HIGH:1,MEDIUM:0},items:[{id:'hotspot:1',label:'Possible API bypass',severity:'HIGH',title:'Possible API bypass: WORK_ITEMS',statement:'Unit writes WORK_ITEMS directly.',uncertainty:['Co-writing does not prove ownership.'],finding_ids:['finding:critical'],evidence_count:3}]},
  priority:{...overviewData.priority,start_here:[{id:'finding:critical',name:'WHEN-VALIDATE-ITEM',module:'orders.xml',risk:'CRITICAL',score:130,factors:['UNRESOLVED_CRITICAL','API_BYPASS','HOTSPOT_CANDIDATE'],breakdown:[]}]}};
renderProjectOverview(neutral);const html=$('project-content').innerHTML;
assert.match(html,/Assessment only · implementation target not selected/);assert.ok(!/Unselected \(/.test(html));
assert.match(html,/Possible API bypass/);assert.match(html,/not verdicts/);assert.match(html,/Co-writing does not prove ownership/);
assert.match(html,/Why: Unresolved CRITICAL risk · Engine signal: possible API bypass · Part of a hotspot candidate/);
assert.ok(!/Verified structural anti-patterns|Ownership Conflicts/.test(html));
''')


def test_generate_view_explains_unselected_and_offers_the_assessment_package(tmp_path):
    run_js(tmp_path, r'''
projectUI.activeId='a';
api=async()=>({binding:{project_id:'a'},target:{platform:'UNSELECTED',version:'none',representation:'none'},freshness:'CURRENT',modules:[],artifacts:[]});
await projectGenerationOpen();
assert.match($('project-generation-body').innerHTML,/estate assessment/);assert.ok(!/Generate APEXlang/.test($('project-generation-body').innerHTML));
const calls=[];api=async(path,body)=>{calls.push([path,body]);return {binding:{project_id:'a',analysis_revision:'r',source_revision:'s',review_revision:1},target:{platform:'Generic Modernization'},freshness:'CURRENT',modules:[],
  artifacts:[{artifact_id:'f'.repeat(32),artifact_kind:'generic-assessment-package',package_name:'assessment-package.zip',status:'Generated',validation_status:'Not Validated',created_at:'t',sha256:'0'}]};};
await projectGenerationOpen();
const body=$('project-generation-body').innerHTML;
assert.match(body,/Generate assessment package/);assert.match(body,/download="assessment-package.zip"/);assert.match(body,/Verify package structure/);
assert.ok(!/SQLcl/.test(body));
''')


def test_system_map_offers_a_keyboard_and_table_path_to_every_relationship(tmp_path):
    run_js(tmp_path, r'''
projectUI.activeId='a';projectUI.view='system-map';
systemMapState.data={mode:'MODULE_ARCHITECTURE',description:'Module-level architecture',focus:'form:A',layers:['FORM','DATABASE'],relationships:['WRITES'],
  nodes:[{id:'form:A',name:'INTAKE',type:'FORM',layer:'FORM',findings_count:2,highest_risk:'HIGH',risk:'HIGH',hotspot_count:1,members:4,fan_in:0,fan_out:1,is_focus:true},
         {id:'table:T',name:'WORK_ITEMS',type:'TABLE',layer:'DATABASE',findings_count:0,highest_risk:'NONE',risk:'NONE',hotspot_count:1,members:0,fan_in:1,fan_out:0,is_focus:false}],
  edges:[{id:'map-edge:1',source:'form:A',target:'table:T',source_name:'INTAKE',target_name:'WORK_ITEMS',classification:'WRITES',count:2,level:'FACT',components:['WHEN-BUTTON-PRESSED'],relationships:['WRITES'],hotspot_ids:['hotspot:1'],is_hotspot:true,evidence:['e']}],
  truncation:[{reason:'EDGE_LIMIT',limit:1,available:9}],total_nodes:2,total_edges:1,reachable_nodes:2,available_edges:9,total_estate_nodes:5,total_estate_edges:9};
systemMapState.focus='form:A';renderProjectSystemMap();
const html=$('project-content').innerHTML;
assert.match(html,/tabindex="0" role="button"/);assert.match(html,/Relationships shown in the map/);assert.match(html,/data-edge-inspect="map-edge:1"/);
assert.match(html,/Showing 1 of 9 relationships/);assert.ok(!/Architectural Verdict/.test(html));
systemMapState.selectedEdge=systemMapState.data.edges[0];renderProjectSystemMap();
assert.match($('project-content').innerHTML,/not verdicts/);assert.match($('project-content').innerHTML,/WHEN-BUTTON-PRESSED/);
''')
