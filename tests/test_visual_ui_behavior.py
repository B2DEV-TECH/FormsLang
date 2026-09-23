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
    {lane:'INTEGRATION',technical:'Integration, unresolved and other',executive:'External, unresolved and other references',count:0,types:[]}],
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
assert.match(html,/Modernization command center/);assert.match(html,/Assessed <time datetime="2026-09-20T12:00:00Z" title="2026-09-20T12:00:00Z">2026-09-20 12:00 UTC<\/time> · Revision r/);
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


def test_coverage_uses_the_projection_shape_and_a_readable_timestamp(tmp_path):
    # The projection sends database {sources, analyzed}; analyzed is null when not counted.
    run_js(tmp_path, r'''
projectUI.activeId='a';projectUI.summary=summary;api=visualApi();
const coverage=database=>({...overviewData,assessment:{...overviewData.assessment,assessment_timestamp:'2026-09-23T23:22:04.766385+00:00'},source_coverage:{forms:{discovered:4,analyzed:4},database,libraries:{discovered:0,without_semantic_representation:0}}});
renderProjectOverview(coverage({sources:20,analyzed:null}));
let html=$('project-content').innerHTML;
assert.match(html,/Database sources<\/dt><dd>20 supplied sources<\/dd>/);assert.ok(!html.includes('Not observed analyzed'));
assert.match(html,/4 of 4 analyzed<\/dd>/);assert.match(html,/>2026-09-23 23:22 UTC<\/time>/);
renderProjectOverview(coverage({sources:20,analyzed:18}));
assert.match($('project-content').innerHTML,/Database sources<\/dt><dd>18 analyzed from 20 supplied sources<\/dd><\/div>/);
renderProjectOverview({...coverage({}),assessment:{...overviewData.assessment,assessment_timestamp:'not-a-date'}});
html=$('project-content').innerHTML;
assert.match(html,/Database sources<\/dt><dd>Not observed<\/dd>/);assert.match(html,/>not-a-date<\/time>/);
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


MAP_SETUP = r'''
const lanes=[{id:'APPLICATION',technical:'Application',executive:'Application modules'},{id:'SHARED_LOGIC',technical:'Shared logic and state',executive:'Shared services and state'},
  {id:'DATA',technical:'Data',executive:'Data objects'},{id:'INTEGRATION',technical:'Integration, unresolved and other',executive:'External, unresolved and other references'}];
const mapLabels={lanes,relationships:{WRITES:{technical:'Writes',executive:'Changes data'},CALLS:{technical:'Calls',executive:'Uses service'}},
  statuses:{OBSERVED:'Observed in the supplied sources',CANDIDATE:'Candidate that needs architecture review',PROPOSED:'Engine proposal, not a decision',DECIDED:'Human decision recorded',UNRESOLVED:'Referenced but not found in the supplied sources'}};
const typeLabels={FORM:['Form','Application module'],PACKAGE:['PL/SQL package','Shared PL/SQL service'],TABLE:['Table','Data object'],UNKNOWN:['Unresolved reference','Unresolved reference']};
const node=(id,name,type,layer,lane,extra={})=>({id,name,type,layer,lane,presentation_type:{technical:typeLabels[type][0],executive:typeLabels[type][1]},
  status:'OBSERVED',unresolved:false,findings_count:0,highest_risk:'NONE',risk:'NONE',hotspot_count:0,members:1,fan_in:0,fan_out:0,module:'',
  review_summary:{total:0,decided:0,open:0,stale:0,deferred:0},...extra});
function mapData(extra={}){return {mode:'MODULE_ARCHITECTURE',view:'ESTATE',description:'Module-level architecture',focus:null,analysis_revision:'r',labels:mapLabels,
  layers:['FORM','DATABASE','UNRESOLVED'],relationships:['CALLS','WRITES'],available_forms:[{id:'form:A',name:'INTAKE'}],
  nodes:[node('form:A','INTAKE','FORM','FORM','APPLICATION',{findings_count:2,highest_risk:'HIGH',hotspot_count:1,fan_out:2,module:'intake.xml',review_summary:{total:2,decided:1,open:1,stale:0,deferred:0}}),
         node('pkg:P','ORDER_API','PACKAGE','DATABASE','SHARED_LOGIC',{fan_in:1}),
         node('table:T','WORK_ITEMS','TABLE','DATABASE','DATA',{fan_in:1}),
         node('ref:X','LEGACY_PKG','UNKNOWN','UNRESOLVED','INTEGRATION',{status:'UNRESOLVED',unresolved:true})],
  edges:[{id:'e1',source:'form:A',target:'table:T',source_name:'INTAKE',target_name:'WORK_ITEMS',classification:'WRITES',count:2,level:'FACT',status:'OBSERVED',
          components:['WHEN-BUTTON-PRESSED'],relationships:['WRITES'],hotspot_ids:['h1'],is_hotspot:true,evidence:['x']},
         {id:'e2',source:'form:A',target:'pkg:P',source_name:'INTAKE',target_name:'ORDER_API',classification:'CALLS',count:1,level:'INFERENCE',status:'CANDIDATE',
          components:[],relationships:['CALLS'],hotspot_ids:[],is_hotspot:false,evidence:[]}],
  layout:{mode:'ESTATE',node_width:184,node_height:54,width:1000,height:300,cycle_nodes:[],
    positions:{'form:A':{x:28,y:68},'pkg:P':{x:276,y:68},'table:T':{x:524,y:68},'ref:X':{x:772,y:68}},
    columns:lanes.map((l,i)=>({id:l.id,label:l.technical,x:28+i*248,width:184,count:1}))},
  truncation:[],total_nodes:4,total_edges:2,reachable_nodes:4,available_edges:2,total_estate_nodes:4,total_estate_edges:2,...extra};}
const mapDetail={node:{},relationships:{inbound:{},outbound:{WRITES:1,CALLS:1}},hotspots:[{id:'h1',title:'Direct table write',severity:'HIGH'}],hotspots_total:1,
  findings:[{id:'f1',name:'WHEN-BUTTON-PRESSED',risk:'HIGH',review_state:'PENDING'}],findings_total:2};
const mapCalls=[];
function mapApi(data,detail){return async path=>{mapCalls.push(path);
  if(path.includes('/system-map/node'))return detail?detail(path):mapDetail;
  return typeof data==='function'?data(path):data;};}
const tick=()=>new Promise(r=>setImmediate(r));
projectUI.activeId='a';projectUI.summary=summary;
'''


def run_map(tmp_path, script):
    run_js(tmp_path, MAP_SETUP + script)


def test_system_map_opens_on_the_estate_by_lane_from_the_server_layout(tmp_path):
    run_map(tmp_path, r'''
api=mapApi(mapData());
await projectSystemMapOpen();
const call=mapCalls.find(p=>p.includes('/system-map?'));
assert.match(call,/view=ESTATE/);assert.ok(!/focus=/.test(call),'the estate view asks for no focus');
const html=$('project-content').innerHTML;
assert.match(html,/transform="translate\(276,68\)"/,'positions come from the server layout');
assert.match(html,/Shared logic and state · 1/);assert.match(html,/marker-end="url\(#visual-map-arrow\)"/);
for(const id of ['system-map-search','system-map-view','system-map-lens','system-map-depth','system-map-edge','system-map-layer',
  'system-map-fit','system-map-reset','system-map-legend-toggle','system-map-zoom-in','system-map-pan-left','system-map-minimap'])
  assert.match(html,new RegExp('id="'+id+'"'),id);
assert.match(html,/id="system-map-depth" disabled/,'depth only applies to a focus');
assert.match(html,/class="map-edge visual-map-edge edge-calls is-candidate" data-edge-id="e2"/,'an inferred relationship is drawn as a candidate');
assert.match(html,/class="map-node visual-map-node is-unresolved" data-node-id="ref:X"/);
assert.match(html,/Relationship table \(2\)/);assert.match(html,/Ctrl \+ mouse wheel zooms\. The wheel alone scrolls the page\./);
assert.match(html,/id="system-map-legend" class="visual-map-legend" hidden/);
''')


def test_rule_candidate_nodes_are_drawn_as_candidates(tmp_path):
    run_map(tmp_path, r'''
const d=mapData();
d.nodes.push(node('rule:R','Conditional rejection candidate: ORDER_API.X','UNKNOWN','OTHER','INTEGRATION',{status:'CANDIDATE',presentation_type:{technical:'Business rule candidate',executive:'Business rule candidate'}}));
d.layout.positions['rule:R']={x:772,y:136};
api=mapApi(d);
await projectSystemMapOpen();
const html=$('project-content').innerHTML;
assert.match(html,/class="map-node visual-map-node is-candidate" data-node-id="rule:R"/);
assert.match(html,/aria-label="[^"]*candidate, not observed structure/);
assert.ok(!/is-candidate" data-node-id="form:A"/.test(html),'observed nodes stay observed');
''')


def test_executive_mode_relabels_the_map_without_refetching(tmp_path):
    run_map(tmp_path, r'''
api=mapApi(mapData());await projectSystemMapOpen();const before=mapCalls.length;
visualSetMode('executive');
const html=$('project-content').innerHTML;
assert.match(html,/Shared services and state · 1/);assert.match(html,/aria-label="INTAKE, Application module, Application modules, 2 findings, highest risk HIGH, 1 hotspot candidates"/);
assert.match(html,/>Changes data</);assert.match(html,/<title>INTAKE Uses service ORDER_API \(1\)<\/title>/);
assert.equal(mapCalls.length,before,'a presentation change never refetches');
''')


def test_focus_request_opens_the_focus_view_for_any_node(tmp_path):
    run_map(tmp_path, r'''
const focusLayout={...mapData().layout,mode:'FOCUS',columns:[{id:'IN_1',label:'Reaches focus (1 hop)',x:28,width:184,count:1},{id:'FOCUS',label:'Focus',x:276,width:184,count:1}]};
api=mapApi(()=>mapData({view:'FOCUS',focus:'pkg:P',layout:focusLayout}));
await projectSystemMapOpen({focus:'pkg:P'});
assert.equal(systemMapState.view,'FOCUS');assert.match(mapCalls.at(-1),/view=FOCUS/);assert.match(mapCalls.at(-1),/focus=pkg%3AP/);
const html=$('project-content').innerHTML;
assert.match(html,/Focus: <b>ORDER_API<\/b>\. What reaches it is on the left; what it reaches is on the right\./);
assert.match(html,/<option value="pkg:P" selected>ORDER_API<\/option>/,'a non-Form focus stays selectable');
assert.match(html,/Reaches focus \(1 hop\) · 1/);assert.match(html,/class="map-node visual-map-node is-focus" data-node-id="pkg:P"/);
assert.ok(!html.includes('id="system-map-depth" disabled'));
''')


def test_a_new_focus_layout_opens_centred_on_the_focus_node(tmp_path):
    run_map(tmp_path, r'''
const focusLayout={...mapData().layout,mode:'FOCUS',columns:[{id:'IN_1',label:'Reaches focus (1 hop)',x:28,width:184,count:1},{id:'FOCUS',label:'Focus',x:276,width:184,count:1}]};
api=mapApi(()=>mapData({view:'FOCUS',focus:'pkg:P',layout:focusLayout}));
$('system-map-canvas').clientWidth=400;
await projectSystemMapOpen({focus:'pkg:P'});
assert.equal($('system-map-canvas').scrollLeft,(276+92)-200,'the focus column is centred');
assert.equal($('system-map-canvas').scrollTop,20);
$('system-map-canvas').scrollLeft=7;
await loadProjectSystemMap();
assert.equal($('system-map-canvas').scrollLeft,7,'a refresh of the same layout keeps where the user scrolled');
''')

def test_map_controls_risk_and_edges_are_accessible_without_colour_or_pointer(tmp_path):
    run_map(tmp_path, r'''
api=mapApi(()=>mapData({layout:{...mapData().layout,positions:{...mapData().layout.positions,'form:A':{x:'28" onload="x',y:68}}}}));
await projectSystemMapOpen();
const html=$('project-content').innerHTML;
for(const name of ['Zoom out','Zoom in','Pan left','Pan up','Pan down','Pan right'])assert.match(html,new RegExp(`aria-label="${name}"`));
assert.match(html,/aria-label="INTAKE, Form, [^"]*, 2 findings, highest risk HIGH, 1 hotspot candidates"/,'risk is announced, not only coloured');
assert.match(html,/data-edge-id="e1" aria-hidden="true"/,'edges point to the table as the accessible path');
assert.ok(!html.includes('onload'),'layout numbers are coerced before they reach SVG attributes');
''')

def test_truncation_copy_names_what_is_shown_and_how_to_reach_the_rest(tmp_path):
    run_map(tmp_path, r'''
api=mapApi(mapData({truncation:[{reason:'NODE_LIMIT',limit:100,available:4812},{reason:'EDGE_LIMIT',limit:200,available:12050},{reason:'SELECTOR_LIMIT',limit:250,available:900}]}));
await projectSystemMapOpen();
const html=$('project-content').innerHTML;
assert.match(html,/Showing 100 of 4,812 nodes in this view\. Refocus, search or filter to explore the rest\./);
assert.match(html,/Showing 200 of 12,050 relationships in this view\./);
assert.match(html,/The Form selector lists 250 of 900 Forms\. Use Search \(Ctrl\+K\) to focus any other Form\./);
''')


def test_lens_lane_and_search_change_emphasis_without_calling_the_server(tmp_path):
    run_map(tmp_path, r'''
api=mapApi(mapData());await projectSystemMapOpen({view:'ESTATE',lane:'DATA'});const before=mapCalls.length;
let html=$('project-content').innerHTML;
assert.match(html,/Highlighting the Data lane/);
assert.match(html,/class="map-node visual-map-node is-dim" data-node-id="form:A"/);assert.match(html,/class="map-node visual-map-node" data-node-id="table:T"/);
$('system-map-clear-lane').onclick();
systemMapState.lens='HOTSPOTS';renderProjectSystemMap();html=$('project-content').innerHTML;
assert.match(html,/Hotspots lens\.<\/b> Emphasises what is linked to a hotspot candidate\. Candidates need architecture review; they are not verdicts\./);
assert.match(html,/is-dim" data-node-id="pkg:P"/);assert.match(html,/class="map-node visual-map-node" data-node-id="table:T"/);
assert.match(html,/edge-writes is-hotspot" data-edge-id="e1"/);
systemMapState.lens='REVIEW';renderProjectSystemMap();
assert.match($('project-content').innerHTML,/1 open · 0 stale · 1 decided/);assert.match($('project-content').innerHTML,/Review status is not migration readiness/);
systemMapState.lens='ARCHITECTURE';renderProjectSystemMap();
$('system-map-search').value='order';$('system-map-search').oninput();
assert.match($('system-map-svg-host').innerHTML,/is-dim" data-node-id="form:A"/);assert.match($('system-map-svg-host').innerHTML,/class="map-node visual-map-node" data-node-id="pkg:P"/);
assert.match($('system-map-search-status').textContent,/^1 node matches in this view/);
$('system-map-search').value='zzz';$('system-map-search').oninput();
assert.match($('system-map-search-status').textContent,/Ctrl\+K searches the whole project/);
assert.equal(mapCalls.length,before,'lens, lane and search never call the server');
''')


def test_node_drawer_has_the_six_sections_and_no_source_text(tmp_path):
    run_map(tmp_path, r'''
api=mapApi(mapData());await projectSystemMapOpen();
systemMapSelectNode('form:A');
assert.match($('system-map-drawer').innerHTML,/Loading findings…/);
await tick();
assert.match(mapCalls.at(-1),/\/system-map\/node\?id=form%3AA$/);
const drawer=$('system-map-drawer').innerHTML;
for(const s of ['Identity','Architecture','Modernization attention','Review','Evidence','Actions'])assert.match(drawer,new RegExp('<h5>'+s+'</h5>'),s);
assert.match(drawer,/Direct table write/);assert.match(drawer,/data-status="CANDIDATE"/);assert.match(drawer,/they are not verdicts/);
assert.match(drawer,/1 of 2 findings decided/);assert.match(drawer,/Review status, not migration readiness/);
assert.match(drawer,/data-map-finding="f1"/);assert.match(drawer,/Showing 1 of 2 findings\./);assert.match(drawer,/The map never shows source text/);
assert.match(drawer,/id="system-map-set-focus" data-focus-id="form:A"/);assert.match(drawer,/id="system-map-view-findings" data-module="intake.xml"/);
const calls=mapCalls.length;systemMapSelectNode('form:A');await tick();assert.equal(mapCalls.length,calls,'detail is cached per node and revision');
''')


def test_late_node_detail_for_another_selection_is_discarded(tmp_path):
    run_map(tmp_path, r'''
const slow=deferred();
api=mapApi(mapData(),path=>path.includes('form%3AA')?slow.promise:{...mapDetail,hotspots:[],hotspots_total:0,findings:[],findings_total:0});
await projectSystemMapOpen();
systemMapSelectNode('form:A');systemMapSelectNode('pkg:P');await tick();
slow.resolve({...mapDetail,hotspots:[{id:'h',title:'STALE ANSWER',severity:'HIGH'}]});await tick();
assert.equal(systemMapState.detail.id,'pkg:P');assert.ok(!$('system-map-drawer').innerHTML.includes('STALE ANSWER'));
assert.match($('system-map-drawer').innerHTML,/<h4>ORDER_API<\/h4>/);
''')


def test_edge_drawer_keeps_candidate_and_observed_apart(tmp_path):
    run_map(tmp_path, r'''
api=mapApi(mapData());await projectSystemMapOpen();
systemMapSelectEdge('e2');let drawer=$('system-map-drawer').innerHTML;
assert.match(drawer,/data-status="CANDIDATE"/);assert.ok(!drawer.includes('data-status="OBSERVED"'));
assert.match(drawer,/evidence level INFERENCE/);assert.match(drawer,/Not linked to a hotspot candidate/);assert.match(drawer,/data-map-focus="pkg:P"/);
systemMapSelectEdge('e1');drawer=$('system-map-drawer').innerHTML;
assert.match(drawer,/data-status="OBSERVED"/);assert.match(drawer,/From components:<\/b> WHEN-BUTTON-PRESSED/);
assert.match(drawer,/Linked to 1 hotspot candidate\(s\)\. Candidates need architecture review; they are not verdicts\./);
''')


def test_map_escapes_hostile_names_everywhere(tmp_path):
    run_map(tmp_path, r'''
const hostile='<img src=x onerror=alert(1)>"';const d=mapData();
d.nodes[0].name=hostile;d.nodes[0].module=hostile;d.edges[0].source_name=hostile;d.edges[0].components=[hostile];
d.edges[0].classification='WRITES"><script>';d.nodes[1].highest_risk='HIGH" onload="x';d.available_forms=[{id:'form:A"',name:hostile}];
api=mapApi(d);await projectSystemMapOpen();systemMapSelectNode('form:A');await tick();
let html=$('project-content').innerHTML+$('system-map-drawer').innerHTML+$('system-map-svg-host').innerHTML;
systemMapSelectEdge('e1');html+=$('system-map-drawer').innerHTML;
assert.ok(!html.includes('<img'));assert.ok(!html.includes('<script'));assert.ok(!html.includes('" onload="'));assert.ok(!html.includes('form:A""'));
assert.match(html,/&lt;img/);
''')


def test_plain_wheel_scrolls_the_page_and_ctrl_wheel_zooms(tmp_path):
    run_map(tmp_path, r'''
api=mapApi(mapData());await projectSystemMapOpen();
let prevented=false;
$('system-map-canvas').onwheel({ctrlKey:false,metaKey:false,deltaY:100,preventDefault(){prevented=true;}});
assert.equal(prevented,false);assert.equal(systemMapState.zoom,1);
$('system-map-canvas').onwheel({ctrlKey:true,deltaY:-100,preventDefault(){prevented=true;}});
assert.equal(prevented,true);assert.equal(systemMapState.zoom,1.25);assert.match($('system-map-svg-host').innerHTML,/width:1250px;height:375px/);
$('system-map-zoom-out').onclick();$('system-map-zoom-out').onclick();assert.equal(systemMapState.zoom,0.8);
''')


def test_arrow_keys_move_between_neighbouring_nodes(tmp_path):
    run_map(tmp_path, r'''
const d=mapData();d.nodes.push(node('form:B','ZETA','FORM','FORM','APPLICATION'));d.layout.positions['form:B']={x:28,y:136};
api=mapApi(d);await projectSystemMapOpen();
assert.equal(systemMapNeighbour('form:A','ArrowDown'),'form:B');assert.equal(systemMapNeighbour('form:B','ArrowUp'),'form:A');
assert.equal(systemMapNeighbour('form:B','ArrowRight'),'pkg:P');assert.equal(systemMapNeighbour('form:A','ArrowLeft'),null);
''')


def test_legend_toggle_and_reset_to_the_default_estate_view(tmp_path):
    run_map(tmp_path, r'''
api=mapApi(mapData());await projectSystemMapOpen({focus:'form:A'});
$('system-map-legend-toggle').onclick();
assert.equal($('system-map-legend').hidden,false);assert.equal($('system-map-legend-toggle').attrs['aria-expanded'],'true');
Object.assign(systemMapState,{lens:'REVIEW',lane:'DATA',query:'x',edge_type:'WRITES',zoom:2});renderProjectSystemMap();
$('system-map-reset').onclick();await tick();
assert.equal(systemMapState.view,'ESTATE');assert.equal(systemMapState.focus,null);assert.equal(systemMapState.lens,'ARCHITECTURE');
assert.equal(systemMapState.lane,null);assert.equal(systemMapState.edge_type,'');assert.equal(systemMapState.zoom,1);
assert.match(mapCalls.at(-1),/view=ESTATE/);assert.ok(!/edge_type|focus=/.test(mapCalls.at(-1)));
''')


PHASE_D_SETUP = r'''
const pair=(technical,executive)=>({technical,executive});
function moduleData(extra={}){return {node:node('form:A','INTAKE','FORM','FORM','APPLICATION',{fan_out:2,findings_count:2,highest_risk:'HIGH',hotspot_count:1,members:12,module:'intake.xml',
    review_summary:{total:2,decided:1,open:1,stale:0,deferred:0}}),module:'intake.xml',analysis_revision:'r',labels:mapLabels,
  composition:[{type:'BLOCK',count:2},{type:'TRIGGER',count:9}],
  neighbours:{inbound:{items:[],total:0},outbound:{items:[
    {id:'table:T',name:'WORK_ITEMS',type:'TABLE',layer:'DATABASE',presentation_type:pair('Table','Data object'),lane:'DATA',unresolved:false,classification:'WRITES',presentation_label:pair('Writes','Changes data'),status:'OBSERVED',count:2,is_hotspot:true,edge_id:'e1'},
    {id:'pkg:P',name:'ORDER_API',type:'PACKAGE',layer:'DATABASE',presentation_type:pair('PL/SQL package','Shared PL/SQL service'),lane:'SHARED_LOGIC',unresolved:false,classification:'CALLS',presentation_label:pair('Calls','Uses service'),status:'CANDIDATE',count:1,is_hotspot:false,edge_id:'e2'}],total:25}},
  relationships:{inbound:{},outbound:{WRITES:1,CALLS:1}},hotspots:[{id:'h1',title:'Direct table write',severity:'HIGH',statement:'INTAKE writes WORK_ITEMS directly.'}],hotspots_total:1,
  findings:[{id:'f1',name:'WHEN-BUTTON-PRESSED',risk:'HIGH',review_state:'PENDING'}],findings_total:2,
  risk_distribution:{HIGH:1,LOW:1},recommendation_distribution:{MOVE_TO_DB:2},business_rule_candidates:1,
  boundary:'Module 360 lists what the supplied sources show about one module. It is not a migration plan, an effort estimate or a readiness verdict.',...extra};}
function hotspotData(extra={}){return {items:[{id:'h1',hotspot_type:'API_BYPASS_CANDIDATE',label:'Possible API bypass',classification:'CANDIDATE',severity:'HIGH',
    title:'Direct write to WORK_ITEMS',statement:'INTAKE writes WORK_ITEMS although WORK_API.CLOSE_ITEM also writes it.',module:'intake.xml',finding_ids:['f1','f2'],evidence_count:3,
    uncertainty:['The API may not cover this write.','Dynamic SQL is not visible.'],recommended_action:'Architecture review required: decide the owner.',
    evidence:{table:'WORK_ITEMS',potential_existing_api_owners:{values:['WORK_API.CLOSE_ITEM'],total:4}},
    nodes:[{id:'form:A',name:'INTAKE',type:'FORM',layer:'FORM',presentation_type:pair('Form','Application module')},{id:'table:T',name:'WORK_ITEMS',type:'TABLE',layer:'DATABASE',presentation_type:pair('Table','Data object')}],nodes_total:2}],
  total:1,offset:0,limit:20,estate_total:3,by_type:{},by_severity:{HIGH:1,MEDIUM:2},
  types:[{id:'API_BYPASS_CANDIDATE',label:'Possible API bypass'},{id:'GLOBAL_STATE_COUPLING',label:'Global state coupling'}],severities:['HIGH','MEDIUM'],
  matrix:{types:[{id:'API_BYPASS_CANDIDATE',label:'Possible API bypass'},{id:'GLOBAL_STATE_COUPLING',label:'Global state coupling'}],
    rows:[{module:'UNKNOWN',total:2,cells:[0,2]},{module:'intake.xml',total:1,cells:[1,0]}],total_modules:2,truncated:false,classification:'CANDIDATE'},
  filters:{},classification:'CANDIDATE',boundary:'Hotspot candidates are derived from saved structural evidence. They need architecture review; they are not verdicts, defects or migration priorities.',
  labels:mapLabels,analysis_revision:'r',...extra};}
const dCalls=[];
function dApi(routes={}){return async path=>{dCalls.push(path);
  if(path.includes('/module-360'))return routes.module?routes.module(path):moduleData();
  if(path.includes('/hotspots'))return routes.hotspots?routes.hotspots(path):hotspotData();
  if(path.includes('/system-map/node'))return mapDetail;
  if(path.includes('/system-map'))return mapData();
  return {};};}
'''


def run_d(tmp_path, script):
    run_js(tmp_path, MAP_SETUP + PHASE_D_SETUP + script)


def test_module_360_shows_one_module_without_source_text(tmp_path):
    run_d(tmp_path, r'''
api=dApi();await visualModuleOpen({node:'form:A'});
assert.equal(projectUI.view,'module-360');assert.match(dCalls.at(-1),/\/module-360\?node=form%3AA$/);
const html=$('project-content').innerHTML;
assert.match(html,/Module 360 · INTAKE/);
for(const s of ['Identity','Modernization attention','Architecture','Review','Evidence','Actions'])assert.match(html,new RegExp('>'+s+'</h3>'),s);
assert.match(html,/It is not a migration plan, an effort estimate or a readiness verdict/);
assert.match(html,/TRIGGER <b>9<\/b>/);assert.match(html,/Nothing in the supplied sources reaches this module\./);
assert.match(html,/Showing 2 of 25\. Hotspot-linked relationships first/);
assert.match(html,/Writes · hotspot candidate/);
// The candidate relationship keeps its own chip; observed and candidate never merge.
assert.match(html,/data-status="CANDIDATE">Candidate<\/span><\/td><td>1</);assert.match(html,/data-status="OBSERVED">Observed<\/span><\/td><td>2</);
assert.match(html,/1 of 2 findings decided/);assert.match(html,/Business-rule candidates:<\/b> 1/);assert.match(html,/Review status, not migration readiness/);
assert.match(html,/Showing 1 of 2 findings\./);assert.match(html,/Module 360 never shows source text/);
assert.match(html,/data-module-map="table:T"/);assert.ok(!html.includes('data-module-node="table:T"'),'only Forms open a Module 360');
assert.match(html,/id="visual-module-map" data-id="form:A"/);
visualSetMode('executive');
const exec=$('project-content').innerHTML;assert.match(exec,/Changes data · hotspot candidate/);assert.match(exec,/Uses service/);assert.match(exec,/Application module/);
assert.equal(dCalls.filter(p=>p.includes('/module-360')).length,1,'mode switch does not refetch');
visualSetMode('technical');
''')


def test_module_360_by_logical_module_and_error_keeps_a_way_out(tmp_path):
    run_d(tmp_path, r'''
api=dApi({module:async()=>{const e=new Error('Unknown module');e.status=400;throw e;}});
await visualModuleOpen('pkgs/order_api.sql');
assert.match(dCalls.at(-1),/\/module-360\?module=pkgs%2Forder_api\.sql$/);
const html=$('project-content').innerHTML;
assert.match(html,/Module 360 is unavailable: Unknown module/);assert.match(html,/id="visual-module-inventory"/);
''')


def test_late_module_answer_for_another_module_is_discarded(tmp_path):
    run_d(tmp_path, r'''
const slow=deferred();
api=dApi({module:path=>path.includes('form%3AA')?slow.promise:moduleData({node:node('form:B','ORDERS','FORM','FORM','APPLICATION',{module:'orders.xml'})})});
const first=visualModuleOpen({node:'form:A'});await visualModuleOpen({node:'form:B'});
slow.resolve(moduleData({node:node('form:A','STALE ANSWER','FORM','FORM','APPLICATION')}));await first;
assert.ok(!$('project-content').innerHTML.includes('STALE ANSWER'));assert.match($('project-content').innerHTML,/Module 360 · ORDERS/);
''')


def test_hotspot_explorer_explains_why_and_what_it_does_not_prove(tmp_path):
    run_d(tmp_path, r'''
api=dApi();await visualHotspotsOpen({});
assert.equal(projectUI.view,'hotspots');assert.match(dCalls.at(-1),/\/hotspots\?offset=0&limit=20$/);
const html=$('project-content').innerHTML;
assert.match(html,/Why FormsLang noticed this/);assert.match(html,/What this does NOT prove/);
assert.match(html,/INTAKE writes WORK_ITEMS although/);assert.match(html,/The API may not cover this write\./);assert.match(html,/Dynamic SQL is not visible\./);
assert.match(html,/WORK_API\.CLOSE_ITEM \(\+3 more\)/);assert.match(html,/potential existing api owners/);
assert.match(html,/they are not verdicts, defects or migration priorities/);
assert.match(html,/data-status="CANDIDATE"/);assert.ok(!html.includes('data-status="DECIDED"'),'a candidate is never shown as decided');
assert.match(html,/Showing 1 of 1 matching candidates \(3 in the estate\)/);
assert.match(html,/data-hotspot-map="form:A"/);assert.match(html,/data-hotspot-module="form:A"/);assert.ok(!html.includes('data-hotspot-module="table:T"'));
assert.match(html,/data-hotspot-review="f1"/);assert.match(html,/Review the linked finding \(1 of 2\)/);
// Attention matrix: counts only, fixed intensity buckets, no module row invented for cross-module candidates.
assert.match(html,/Attention matrix/);assert.match(html,/<th scope="row">Across modules<\/th>/);
assert.match(html,/data-matrix-module="intake.xml" data-matrix-type="API_BYPASS_CANDIDATE"/);
assert.ok(!html.includes('data-matrix-module="UNKNOWN"'));assert.match(html,/data-level="3"/);assert.ok(!/style="[^"]*background/.test(html));
''')


def test_hotspot_filters_reload_from_the_server_and_empty_estate_says_so(tmp_path):
    run_d(tmp_path, r'''
api=dApi();await visualHotspotsOpen({module:'intake.xml'});
assert.match(dCalls.at(-1),/&module=intake\.xml$/);assert.match($('project-content').innerHTML,/Module: <b><span title="intake\.xml">intake\.xml<\/span><\/b>/);
$('visual-hotspot-type').value='GLOBAL_STATE_COUPLING';$('visual-hotspot-type').onchange();await tick();
assert.match(dCalls.at(-1),/type=GLOBAL_STATE_COUPLING/);assert.match(dCalls.at(-1),/module=intake\.xml/);
$('visual-hotspot-clear-module').onclick();await tick();assert.ok(!dCalls.at(-1).includes('module='));
api=dApi({hotspots:()=>hotspotData({items:[],total:0,estate_total:0,matrix:{types:[],rows:[],total_modules:0,truncated:false}})});
await visualHotspotsOpen({});
assert.match($('project-content').innerHTML,/has no hotspot candidates\. That is an observation about the supplied sources, not a clean bill of health\./);
''')


def test_module_ids_are_shown_by_file_name_with_the_full_id_as_tooltip(tmp_path):
    run_d(tmp_path, r'''
const id='0f1e2d3c4b5a/forms/INTAKE.xml';
api=dApi({hotspots:()=>{const d=hotspotData();d.items[0].module=id;d.matrix.rows=[{module:id,total:1,cells:[1,0]}];return d;}});
await visualHotspotsOpen({module:id});
const html=$('project-content').innerHTML;
assert.match(html,/Module: <b><span title="0f1e2d3c4b5a\/forms\/INTAKE\.xml">INTAKE\.xml<\/span><\/b>/);
assert.match(html,/<th scope="row"><span title="0f1e2d3c4b5a\/forms\/INTAKE\.xml">INTAKE\.xml<\/span><\/th>/);
assert.match(html,/Possible API bypass · <span title="0f1e2d3c4b5a\/forms\/INTAKE\.xml">INTAKE\.xml<\/span>/);
// The full id still drives filtering: only the label is shortened.
assert.match(html,/data-matrix-module="0f1e2d3c4b5a\/forms\/INTAKE\.xml"/);
assert.equal((html.match(/>0f1e2d3c4b5a\//g)||[]).length,0,'the source-root hash is never the visible text');
''')


def test_phase_d_views_escape_hostile_text(tmp_path):
    run_d(tmp_path, r'''
const hostile='<img src=x onerror=alert(1)>"';
api=dApi({module:()=>moduleData({node:node('form:A',hostile,'FORM','FORM','APPLICATION',{module:hostile}),module:hostile,composition:[{type:hostile,count:1}],
  findings:[{id:hostile,name:hostile,risk:hostile,review_state:hostile}],hotspots:[{id:'h',title:hostile,severity:hostile,statement:hostile}]}),
  hotspots:()=>{const d=hotspotData();Object.assign(d.items[0],{title:hostile,statement:hostile,label:hostile,module:hostile,uncertainty:[hostile],recommended_action:hostile,
    evidence:{[hostile]:hostile,list:{values:[hostile],total:1}},nodes:[{id:hostile,name:hostile,type:'FORM',layer:'FORM'}],finding_ids:[hostile]});
    d.matrix.rows=[{module:hostile,total:1,cells:[1,0]}];return d;}});
await visualModuleOpen({node:'form:A'});
let html=$('project-content').innerHTML;assert.ok(!html.includes('<img'));assert.ok(!html.includes('"<'));assert.match(html,/&lt;img src=x onerror=alert\(1\)>&quot;/);
await visualHotspotsOpen({});
html=$('project-content').innerHTML;assert.ok(!html.includes('<img'));assert.match(html,/&lt;img src=x onerror=alert\(1\)>&quot;/);
''')


def test_back_returns_along_the_path_the_reader_took(tmp_path):
    run_d(tmp_path, r'''
api=dApi();
await projectSystemMapOpen({focus:'form:A'});
assert.ok(!$('project-content').innerHTML.includes('id="visual-back"'),'no back button without a cross-navigation');
await visualModuleOpen({node:'form:A'});
assert.match($('project-content').innerHTML,/Back to System Map · INTAKE/);
await visualHotspotsOpen({module:'intake.xml'});
assert.match($('project-content').innerHTML,/Back to Module 360 · INTAKE/);
visualGoBack();await tick();await tick();
assert.equal(projectUI.view,'module-360');assert.match($('project-content').innerHTML,/Back to System Map · INTAKE/);
visualGoBack();await tick();await tick();
assert.equal(projectUI.view,'system-map');assert.equal(systemMapState.focus,'form:A');assert.equal(systemMapState.view,'FOCUS');
assert.ok(!$('project-content').innerHTML.includes('id="visual-back"'),'the chain ends where it started');
// The section navigation starts a fresh chain.
await visualModuleOpen({node:'form:A'});assert.ok(visualUI.back);
visualUI.back=null;await visualHotspotsOpen({},{remember:false});assert.ok(!$('project-content').innerHTML.includes('Back to'));
''')


def test_back_chain_is_bounded(tmp_path):
    run_d(tmp_path, r'''
api=dApi();await projectSystemMapOpen({focus:'form:A'});
for(let i=0;i<30;i++){await visualModuleOpen({node:'form:A'});await visualHotspotsOpen({});}
let depth=0;for(let p=visualUI.back;p;p=p.prior)depth++;
assert.ok(depth<=VISUAL_BACK_DEPTH,String(depth));
''')


def test_review_detail_gains_architecture_context_and_discards_late_answers(tmp_path):
    run_d(tmp_path, r'''
const slow=deferred();
api=dApi({module:path=>path.includes('finding=f1')?slow.promise:moduleData()});
projectUI.view='review';projectUI.reviewState={detail:{item:{id:'f2'}}};
const first=visualReviewContext({id:'f1'});
await visualReviewContext({id:'f2'});
assert.match(dCalls.at(-1),/\/module-360\?finding=f2$/);
let html=$('visual-review-context').innerHTML;
assert.match(html,/Architecture context:<\/b> INTAKE · Form · 0 incoming · 2 outgoing relationships/);
assert.match(html,/data-status="CANDIDATE"/);assert.match(html,/1 hotspot candidate\(s\)/);assert.match(html,/1 of 2 findings decided<\/p>/);
assert.match(html,/id="visual-review-module" data-id="form:A"/);assert.match(html,/id="visual-review-map" data-id="form:A"/);
slow.resolve(moduleData({node:node('form:Z','STALE ANSWER','FORM','FORM','APPLICATION')}));await first;
assert.ok(!$('visual-review-context').innerHTML.includes('STALE ANSWER'));
// A deferred finding is not a decided one; the context says so after the decision.
api=dApi({module:()=>moduleData({node:node('form:A','INTAKE','FORM','FORM','APPLICATION',{review_summary:{total:2,decided:1,open:0,stale:0,deferred:1}})})});
await visualReviewContext({id:'f2'});assert.match($('visual-review-context').innerHTML,/1 of 2 findings decided · 1 deferred<\/p>/);
api=dApi();await visualReviewContext({id:'f2'});
// Opening Module 360 from Review offers the way back to Review.
$('visual-review-module').onclick();await tick();await tick();
assert.equal(projectUI.view,'module-360');assert.match($('project-content').innerHTML,/Back to Review/);
''')


def test_review_context_failure_is_quiet_and_leaves_review_usable(tmp_path):
    run_d(tmp_path, r'''
api=dApi({module:async()=>{throw new Error('The finding is not placed on the System Map');}});
projectUI.view='review';projectUI.reviewState={detail:{item:{id:'f1'}}};
await visualReviewContext({id:'f1'});
assert.match($('visual-review-context').innerHTML,/Architecture context is unavailable for this finding: The finding is not placed on the System Map/);
''')


def test_search_result_can_open_the_system_map_focused_on_it(tmp_path):
    run_d(tmp_path, r'''
api=dApi();
globalSearchRender([{project_id:'a',id:'pkg1',category:'packages',category_label:'Package',title:'ORDER_API',subtitle:'Package',map_focus:'pkg:P',action:{view:'inventory',category:'packages',target_id:'pkg1'}},
                    {project_id:'a',id:'r1',category:'business_rules',title:'NO_MAP',subtitle:'Rule',map_focus:null,action:{view:'inventory',category:'business_rules',target_id:'r1'}}],'order');
const list=$('global-search-list').innerHTML;
assert.match(list,/data-search-map="0"/);assert.ok(!list.includes('data-search-map="1"'));assert.match(list,/aria-label="Show ORDER_API on the System Map"/);
await executeSearchMap(globalSearch.results[0]);
assert.equal(projectUI.view,'system-map');assert.equal(systemMapState.view,'FOCUS');assert.equal(systemMapState.focus,'pkg:P');
assert.match(dCalls.find(p=>p.includes('/system-map?')),/focus=pkg%3AP/);
''')


def test_section_nav_lists_hotspots_and_keeps_the_2_1_sections(tmp_path):
    run_d(tmp_path, r'''
const nav=projectSectionNav('hotspots');
for(const id of ['overview','system-map','hotspots','inventory','review','dependencies','generate','reports','settings'])assert.match(nav,new RegExp('data-project-section="'+id+'"'),id);
assert.match(nav,/data-project-section="hotspots" aria-current="page"/);
''')
