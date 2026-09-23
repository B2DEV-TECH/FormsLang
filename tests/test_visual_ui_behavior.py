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


MAP_SETUP = r'''
const lanes=[{id:'APPLICATION',technical:'Application',executive:'Application modules'},{id:'SHARED_LOGIC',technical:'Shared logic and state',executive:'Shared services and state'},
  {id:'DATA',technical:'Data',executive:'Data objects'},{id:'INTEGRATION',technical:'Integration and unresolved',executive:'External and unresolved references'}];
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


def test_executive_mode_relabels_the_map_without_refetching(tmp_path):
    run_map(tmp_path, r'''
api=mapApi(mapData());await projectSystemMapOpen();const before=mapCalls.length;
visualSetMode('executive');
const html=$('project-content').innerHTML;
assert.match(html,/Shared services and state · 1/);assert.match(html,/aria-label="INTAKE, Application module, Application modules, 2 findings, 1 hotspot candidates"/);
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
