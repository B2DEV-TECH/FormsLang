"""Execute the actual Generate workspace against the established DOM harness."""

import subprocess

import pytest
from test_project_ui_behavior import DOM, NODE

from formslang.ui.modernization_project import PROJECT_JS

pytestmark = pytest.mark.skipif(NODE is None, reason='Node required')


def run(tmp_path, script):
    from formslang.ui.modernization_generation import GENERATION_PROJECT_JS
    path = tmp_path / 'generation-ui.cjs'
    path.write_text(DOM + PROJECT_JS + GENERATION_PROJECT_JS + '\n(async()=>{' + script +
                    '\n})().catch(e=>{console.error(e);process.exitCode=1;});', encoding='utf-8')
    result = subprocess.run([NODE, str(path)], capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stdout + result.stderr


def test_generation_labels_boundaries_and_escapes(tmp_path):
    run(tmp_path, r'''
projectUI.activeId='a';projectUI.summary=summary;
api=async()=>({binding:{},target:{platform:'Oracle APEX',version:'26.1'},freshness:'CURRENT',modules:[{source_id:'s',module:'<script>bad()</script>',prepared:false}],artifacts:[]});
await projectGenerationOpen();
assert.match($('project-content').innerHTML,/APEXlang/);
assert.match($('project-generation-body').innerHTML,/&lt;script>/);
assert.ok(!$('project-generation-body').innerHTML.includes('<script>'));
assert.match($('project-generation-body').innerHTML,/No automatic deployment/);
''')


def test_generation_late_response_does_not_cross_project(tmp_path):
    run(tmp_path, r'''
projectUI.activeId='a';projectUI.summary=summary;
const late=deferred();api=()=>late.promise;const pending=projectGenerationOpen();
projectUI.activeId='b';projectUI.generation++;projectUI.view='overview';$('project-content').innerHTML='Project B';
late.resolve({modules:[],artifacts:[]});await pending;
assert.equal($('project-content').innerHTML,'Project B');
''')


def test_generation_conflict_never_replays_write(tmp_path):
    run(tmp_path, r'''
projectUI.activeId='a';projectUI.view='generate';projectUI.generationState={};
const s=projectUI.generationState;let writes=0;api=async()=>{writes++;const e=new Error('Evidence changed');e.status=409;throw e;};
await projectGenerationWrite('/generation',{},()=>{});
assert.equal(writes,1);assert.equal(s.busy,false);
assert.match($('project-generation-status').textContent,/reload/i);
''')


def test_generation_restores_selected_module_only_for_same_project(tmp_path):
    run(tmp_path, r'''
projectUI.activeId='a';projectUI.generationState={projectId:'a',selected:'module-a'};
api=async()=>({target:{},modules:[{source_id:'module-a',module:'A'}],artifacts:[]});
let selected=[];projectGenerationModule=async id=>selected.push(id);
await projectGenerationOpen();assert.deepEqual(selected,['module-a']);
projectUI.activeId='b';await projectGenerationOpen();assert.deepEqual(selected,['module-a']);
''')
