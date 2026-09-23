"""FormsLang 2.2 visual layer, executing the production JavaScript in Node."""

import subprocess

import pytest

from formslang.ui.modernization_generation import GENERATION_PROJECT_JS
from formslang.ui.modernization_project import PROJECT_JS
from formslang.ui.modernization_review import REVIEW_PROJECT_JS
from formslang.ui.modernization_visual import VISUAL_PROJECT_JS
from tests.test_project_ui_behavior import DOM, NODE

pytestmark = pytest.mark.skipif(NODE is None, reason='Node needed for JavaScript behavior tests')


def run_js(tmp_path, script):
    path = tmp_path / 'visual-ui.cjs'
    path.write_text(DOM + PROJECT_JS + VISUAL_PROJECT_JS + REVIEW_PROJECT_JS + GENERATION_PROJECT_JS
                    + VISUAL_SETUP + '\n(async()=>{\n' + script +
                    "\n})().then(()=>console.log('COMPLETE')).catch(e=>{console.error(e);process.exitCode=1;});",
                    encoding='utf-8')
    result = subprocess.run([NODE, str(path)], capture_output=True, text=True, timeout=60, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'COMPLETE' in result.stdout.splitlines(), result.stdout + result.stderr


VISUAL_SETUP = r'''
const visualData={
  estate:[
    {lane:'APPLICATION',technical:'Application',executive:'Application modules',count:2,types:[{type:'FORM',count:2,technical:'Form',executive:'Application module'}]},
    {lane:'SHARED_LOGIC',technical:'Shared logic and state',executive:'Shared services and state',count:1,types:[{type:'PACKAGE',count:1,technical:'PL/SQL package',executive:'Shared PL/SQL service'}]},
    {lane:'DATA',technical:'Data',executive:'Data objects',count:3,types:[{type:'TABLE',count:2,technical:'Table',executive:'Data object'},{type:'VIEW',count:1,technical:'View',executive:'Data object'}]},
    {lane:'INTEGRATION',technical:'Integration and unresolved',executive:'External and unresolved references',count:0,types:[]}],
  relationships:{CALLS:1,WRITES:2},
  matrix:{types:[],rows:[],total_modules:0,truncated:false,classification:'CANDIDATE'},
  board:{schema:'formslang-investigation-groups/1',boundary:'Investigation groups organize review work. They are not migration waves, dependency order, effort estimates or readiness claims.',
    groups:[{id:'INVESTIGATE_FIRST',name:'Investigate first',rule:'Unresolved CRITICAL findings.',total:1,truncated:false,
             modules:[{module:'orders.xml',findings:3,unresolved:2,stale_decisions:0,hotspot_candidates:1,reasons:['HOTSPOT_HIGH','UNRESOLVED_CRITICAL']}]},
            {id:'REVIEWED',name:'Reviewed',rule:'Every finding decided.',total:0,truncated:false,modules:[]}]},
  journey:[{id:'UNDERSTAND',label:'Understand',section:'system-map',question:'What is in the estate?',facts:{forms_modules:2,database_packages:null,dependencies:7}},
           {id:'DELIVER',label:'Deliver',section:'reports',question:'What can be handed over?',facts:{}}],
  labels:{}
};
const visualCalls=[];
function visualApi(overrides={}){return async(path)=>{visualCalls.push(path);if(path.endsWith('/overview/visual'))return {visual:{...visualData,...overrides}};return {};};}
'''


def test_command_center_renders_overview_and_fills_visuals_from_the_visual_endpoint(tmp_path):
    run_js(tmp_path, r'''
projectUI.activeId='a';projectUI.summary=summary;api=visualApi();
renderProjectOverview(overviewData);await new Promise(r=>setImmediate(r));
const html=$('project-content').innerHTML;
assert.match(html,/Modernization command center/);assert.match(html,/Assessed 2026-09-20T12:00:00Z · Revision r/);
assert.match(html,/Start Priority Review/);assert.match(html,/aria-label="Presentation mode"/);
assert.match(html,/Source Coverage/);assert.match(html,/2 of 3 analyzed · 1 failed/);
assert.match(html,/Architecture Attention/);assert.match(html,/data-status="CANDIDATE"/);assert.match(html,/data-status="PROPOSED"/);
assert.match(html,/not a progress tracker/);
// 2.1 selectors the browser acceptance relies on are still present.
assert.match(html,/id="project-hotspots"/);assert.match(html,/id="project-priority"/);
assert.ok(visualCalls.includes('/api/v2/projects/a/overview/visual'));
const estate=$('visual-estate').innerHTML,journey=$('visual-journey').innerHTML,board=$('visual-board').innerHTML;
assert.match(estate,/data-visual-lane="DATA"/);assert.match(estate,/Table<\/button><span>2/);assert.match(estate,/View<\/button><span>1/);
assert.match(journey,/Explore System Map/);assert.match(journey,/Database packages<\/dt><dd>Not observed/);
assert.match(journey,/generated on request/);assert.ok(!/%/.test(journey));
assert.match(board,/They are not migration waves, dependency order, effort estimates or readiness claims\./);
assert.match(board,/orders\.xml/);assert.match(board,/Why: HIGH hotspot candidate · Unresolved CRITICAL risk/);
assert.match(board,/No modules in this group/);
''')


def test_missing_counts_are_not_observed_never_zero(tmp_path):
    run_js(tmp_path, r'''
projectUI.activeId='a';projectUI.summary=summary;api=visualApi();
renderProjectOverview({...overviewData,priority:{},source_coverage:{},hotspots:undefined});
const html=$('project-content').innerHTML;
assert.match(html,/Not observed of Not observed analyzed/);
assert.match(html,/Unresolved CRITICAL findings<\/button><span><span[^>]*>Proposed<\/span> <b>Not observed<\/b>/);
assert.match(html,/Hotspot candidates<\/button><span><span[^>]*>Candidate<\/span> <b>Not observed<\/b>/);
assert.match(html,/Explore System Map/);assert.ok(!html.includes('visual-bar'));
''')


def test_executive_mode_relabels_and_is_remembered_for_the_session_only(tmp_path):
    run_js(tmp_path, r'''
const store={};window.sessionStorage={getItem:k=>store[k]??null,setItem:(k,v)=>{store[k]=v;}};
projectUI.activeId='a';projectUI.summary=summary;api=visualApi();
renderProjectOverview(overviewData);await new Promise(r=>setImmediate(r));
assert.equal(visualMode(),'technical');assert.match($('visual-estate').innerHTML,/Shared logic and state/);
const fetches=visualCalls.length;
visualSetMode('executive');
assert.equal(store['formslang.presentationMode'],'executive');assert.equal(document.body.dataset.viewMode,'executive');
const estate=$('visual-estate').innerHTML;
assert.match(estate,/Shared services and state/);assert.match(estate,/Shared PL\/SQL service/);
// Table and View share one executive term, so their counts are folded together.
assert.match(estate,/Data object<\/button><span>3/);assert.ok(!estate.includes('>Table<'));
assert.match($('project-content').innerHTML,/id="visual-mode-executive" data-visual-mode="executive" aria-pressed="true"/);
assert.equal(visualCalls.length,fetches,'mode change must not refetch or re-analyze');
assert.equal($('visual-mode-executive').focused,true);
visualUI.mode=null;assert.equal(visualMode(),'executive','a new render in the same session keeps the mode');
''')


def test_blocked_session_storage_still_switches_mode(tmp_path):
    run_js(tmp_path, r'''
window.sessionStorage={getItem(){throw new Error('denied');},setItem(){throw new Error('denied');}};
projectUI.activeId='a';projectUI.summary=summary;api=visualApi();
assert.equal(visualMode(),'technical');
renderProjectOverview(overviewData);await new Promise(r=>setImmediate(r));
visualSetMode('executive');assert.equal(visualMode(),'executive');
assert.match($('visual-estate').innerHTML,/Application modules/);
''')


def test_command_center_escapes_hostile_visual_text(tmp_path):
    run_js(tmp_path, r'''
projectUI.activeId='a';projectUI.summary=summary;
const hostile='<img src=x onerror=alert(1)>';
api=visualApi({estate:[{lane:'APPLICATION"><script>',technical:hostile,executive:hostile,count:1,types:[{type:'FORM"x',count:1,technical:hostile,executive:hostile}]}],
  board:{boundary:hostile,groups:[{id:'X',name:hostile,rule:hostile,total:1,modules:[{module:hostile,findings:1,unresolved:1,reasons:[hostile]}]}]},
  journey:[{id:'UNDERSTAND',label:hostile,section:'system-map',question:hostile,facts:{[hostile]:1}}]});
renderProjectOverview(overviewData);await new Promise(r=>setImmediate(r));
for(const id of ['visual-estate','visual-journey','visual-board']){
  const html=$(id).innerHTML;assert.ok(!html.includes('<img'),id);assert.ok(!html.includes('<script'),id);assert.ok(!html.includes('"x'),id);assert.match(html,/&lt;img/,id);
}
''')


def test_review_revision_change_refetches_but_same_revision_reuses_visuals(tmp_path):
    run_js(tmp_path, r'''
projectUI.activeId='a';projectUI.summary=summary;api=visualApi();
renderProjectOverview(overviewData);await new Promise(r=>setImmediate(r));
renderProjectOverview(overviewData);await new Promise(r=>setImmediate(r));
assert.equal(visualCalls.filter(p=>p.endsWith('/overview/visual')).length,1);
assert.match($('visual-board').innerHTML,/orders\.xml/);
renderProjectOverview({...overviewData,assessment:{...overviewData.assessment,review_revision:3}});await new Promise(r=>setImmediate(r));
assert.equal(visualCalls.filter(p=>p.endsWith('/overview/visual')).length,2);
assert.ok(!visualCalls.some(p=>p.endsWith('/analyze')));
''')


def test_late_visual_response_for_another_project_is_discarded(tmp_path):
    run_js(tmp_path, r'''
projectUI.activeId='a';projectUI.summary=summary;const slow=deferred();api=()=>slow.promise;
renderProjectOverview(overviewData);
projectUI.generation++;projectUI.activeId='b';
slow.resolve({visual:visualData});await new Promise(r=>setImmediate(r));
assert.equal(visualUI.overview.data,null);assert.ok(!$('visual-estate').innerHTML.includes('data-visual-lane'));
''')


def test_visual_failure_keeps_the_saved_overview_usable(tmp_path):
    run_js(tmp_path, r'''
projectUI.activeId='a';projectUI.summary=summary;api=async()=>{throw new Error('Project busy.');};
renderProjectOverview(overviewData);await new Promise(r=>setImmediate(r));
assert.match($('visual-estate').innerHTML,/Estate visuals are unavailable: Project busy\. The saved assessment above is unaffected\./);
assert.match($('project-content').innerHTML,/Application Inventory/);
api=visualApi();renderProjectOverview(overviewData);await new Promise(r=>setImmediate(r));
assert.match($('visual-estate').innerHTML,/data-visual-lane="APPLICATION"/);
''')


def test_status_chips_keep_distinct_words(tmp_path):
    run_js(tmp_path, r'''
const words=['OBSERVED','CANDIDATE','PROPOSED','DECIDED','UNRESOLVED'].map(s=>visualStatus(s).replace(/<[^>]+>/g,''));
assert.equal(new Set(words).size,5);assert.equal(visualStatus('BOGUS"'),visualStatus('OBSERVED'));
''')
