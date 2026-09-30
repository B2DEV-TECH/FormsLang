"""WP-12 journey keeps separately fetched evidence on one saved revision."""

import json
import subprocess

import pytest

from formslang.ui.modernization_journey import JOURNEY_PROJECT_JS
from formslang.ui.modernization_project import PROJECT_JS
from tests.test_project_ui_behavior import DOM, NODE

pytestmark = pytest.mark.skipif(NODE is None, reason='Node needed for JavaScript behavior tests')


SETUP = r'''
projectUI.activeId='a';projectUI.view='journey';
const a={analysis_revision:'analysis-a',source_revision:'source-a',review_revision:1};
const b={analysis_revision:'analysis-b',source_revision:'source-b',review_revision:2};
const form={...a,node:{id:'form-a',type:'FORM',name:'CUSTOMERS'},module:'forms/customers.xml',
  neighbours:{outbound:{items:[],total:0}},freshness:'CURRENT',findings_total:0};
const s={serial:0,edge:null,detail:null,map:{...a,available_forms:[{id:'form-a',name:'CUSTOMERS'}],
  selector:{shown:1,total:1,truncated:false}}};
projectUI.journeyState=s;
'''


def run_js(tmp_path, script):
    path = tmp_path / 'journey-ui.cjs'
    path.write_text(DOM + PROJECT_JS + JOURNEY_PROJECT_JS + '\n(async()=>{\n' + SETUP + script +
                    "\n})().then(()=>console.log('COMPLETE')).catch(e=>{console.error(e);process.exitCode=1;});",
                    encoding='utf-8')
    result = subprocess.run([NODE, str(path)], capture_output=True, text=True, timeout=60, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'COMPLETE' in result.stdout.splitlines(), result.stdout + result.stderr


@pytest.mark.parametrize('changed_response', ['map', 'generation', 'module'])
def test_form_journey_rejects_cross_revision_responses(tmp_path, changed_response):
    run_js(tmp_path, f'''
const changed={json.dumps(changed_response)};
if(changed==='map')Object.assign(s.map,b);
api=async path=>{{
  if(path.includes('/module-360?'))return form;
  if(path.endsWith('/generation'))return {{binding:{{project_id:'a',...(changed==='generation'?b:a)}},
    modules:[{{module:form.module,source_id:'source-id'}}]}};
  if(path.includes('/generation/modules/'))return {{binding:{{project_id:'a',...(changed==='module'?b:a)}},
    blockers:[{{code:'MODULE_NOT_PREPARED',message:'Prepare review.'}}],ready:false}};
  throw Error('Unexpected request: '+path);
}};
await projectJourneyForm('form-a');
assert.equal(s.generationDetail,null,'mixed blocker response must not be accepted');
assert.match($('project-journey-status').textContent,/changed/i);
''')


def test_edge_journey_rejects_evidence_from_another_revision(tmp_path):
    run_js(tmp_path, r'''
s.form={...form,neighbours:{outbound:{items:[{edge_id:'map-edge:one',name:'SHIPMENTS',
  status:'OBSERVED',classification:'OPENS_FORM',unresolved:false}],total:1}}};
api=async path=>{
  assert.match(path,/system-map\/edge\?id=map-edge%3Aone$/);
  return {...b,edge:{id:'map-edge:one',source:'form-a',target:'form-b',target_layer:'FORM',
    target_unresolved:false,source_name:'CUSTOMERS',target_name:'SHIPMENTS',
    classification:'OPENS_FORM',level:'FACT',count:1,evidence_refs:[]},
    evidence:[],source:[],sampled:false};
};
await projectJourneyEdge('map-edge:one');
assert.equal(s.detail,null,'mixed edge evidence must not be accepted');
assert.match($('project-journey-status').textContent,/changed/i);
''')
