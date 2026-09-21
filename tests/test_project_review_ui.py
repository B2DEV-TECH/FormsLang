"""Execute production governance UI with the existing DOM harness."""

import subprocess

import pytest
from test_project_ui_behavior import DOM, NODE

from formslang.ui.modernization_project import PROJECT_JS

pytestmark = pytest.mark.skipif(NODE is None, reason='Node required')


def run(tmp_path, script):
    from formslang.ui import modernization_review
    path = tmp_path / 'review-ui.cjs'
    path.write_text(DOM + PROJECT_JS + modernization_review.REVIEW_PROJECT_JS +
        '\n(async()=>{' + script + "\n})().catch(e=>{console.error(e);process.exitCode=1;});", encoding='utf-8')
    result = subprocess.run([NODE, str(path)], capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stdout + result.stderr


def test_queue_and_detail_escape_untrusted_text(tmp_path):
    run(tmp_path, r'''
projectUI.activeId='a';projectUI.summary=summary;projectUI.overview=overviewData;
api=async(path)=>path.includes('/review/')?{...inventoryDetail,binding:{project_id:'a',analysis_revision:'r',source_revision:'s',review_revision:2,finding_revision:'f'},engine_recommendation:'MANUAL_REVIEW',history:[{rationale:'<script>bad()</script>'}],annotations:[{note:'<img src=x onerror=bad()>',kind:'CONFIRMED_BUSINESS_RULE'}],evidence:[],statements:[]}:inventoryPage;
await projectReviewOpen();await projectReviewDetail('finding:critical');
assert.match($('project-content').innerHTML,/Modernization Review/);
assert.match($('project-review-detail').innerHTML,/&lt;script>/);
assert.ok(!$('project-review-detail').innerHTML.includes('<script>'));
assert.match($('project-review-detail').innerHTML,/Engine recommendation/);
assert.match($('project-review-detail').innerHTML,/Human decision/);
''')


def test_late_project_response_cannot_overwrite_new_project(tmp_path):
    run(tmp_path, r'''
projectUI.activeId='a';projectUI.summary=summary;projectUI.overview=overviewData;
const late=deferred();api=()=>late.promise;const pending=projectReviewOpen();
projectUI.activeId='b';projectUI.generation++;projectUI.view='overview';
$('project-content').innerHTML='New project';late.resolve(inventoryPage);await pending;
assert.equal($('project-content').innerHTML,'New project');
''')


def test_stale_mutation_shows_conflict_without_replay(tmp_path):
    run(tmp_path, r'''
projectUI.activeId='a';projectUI.summary=summary;projectUI.overview=overviewData;
let writes=0;api=async(path,body)=>{if(body){writes++;const e=new Error('Evidence changed');e.status=409;throw e;}return path.includes('/review/')?{...inventoryDetail,binding:{project_id:'a',analysis_revision:'r',source_revision:'s',review_revision:2,finding_revision:'f'},engine_recommendation:'MANUAL_REVIEW',history:[],annotations:[],evidence:[],statements:[]}:inventoryPage;};
const renderDetail=projectReviewRenderDetail;projectReviewRenderDetail=()=>{renderDetail();$('project-review-rationale').value='';};
await projectReviewOpen();await projectReviewDetail('finding:critical');
$('project-review-rationale').value='Keep my architectural explanation';
await projectReviewSave({action:'APPROVE'});
assert.equal(writes,1);assert.match($('project-review-status').textContent,/changed|reload/i);
assert.equal($('project-review-rationale').value,'Keep my architectural explanation');
''')


def test_saved_decision_invalidates_client_overview(tmp_path):
    run(tmp_path, r'''
projectUI.activeId='a';projectUI.summary=summary;projectUI.overview=overviewData;
api=async(path,body)=>body?{saved:true}:path.includes('/review/')?{...inventoryDetail,binding:{project_id:'a',analysis_revision:'r',source_revision:'s',review_revision:2,finding_revision:'f'},engine_recommendation:'MANUAL_REVIEW',history:[],annotations:[],evidence:[],statements:[]}:inventoryPage;
await projectReviewOpen();await projectReviewDetail('finding:critical');await projectReviewSave({action:'APPROVE'});
assert.equal(projectUI.overview,null);
''')


def test_history_paging_keeps_revision_fence_and_filters(tmp_path):
    run(tmp_path, r'''
projectUI.activeId='a';projectUI.summary=summary;projectUI.overview=overviewData;
let last='';api=async(path)=>{last=path;return path.includes('/review/')?{...inventoryDetail,binding:{project_id:'a'},engine_recommendation:'MANUAL_REVIEW',history:[],history_total:75,history_offset:path.includes('offset=50')?50:0,history_limit:50,annotations:[],evidence:[],statements:[]}:inventoryPage;};
await projectReviewOpen({filters:{risk:'CRITICAL'}});await projectReviewDetail('finding:critical');
assert.equal($('project-review-history-next').disabled,false);
await $('project-review-history-next').onclick();
assert.match(last,/offset=50/);assert.match(last,/revision=r/);assert.match(last,/review_revision=2/);
assert.equal(projectUI.reviewState.filters.risk,'CRITICAL');
assert.equal($('project-review-history-next').disabled,true);
assert.equal($('project-review-history-previous').disabled,false);
''')


def test_return_navigation_restores_same_project_queue_only(tmp_path):
    run(tmp_path, r'''
projectUI.activeId='a';projectUI.summary=summary;projectUI.overview=overviewData;
api=async()=>inventoryPage;
await projectReviewOpen({filters:{risk:'HIGH'},query:'ownership',offset:50});
const saved=projectUI.reviewState;saved.selected.add('finding:high');
projectUI.view='overview';await projectReviewOpen();
assert.equal(projectUI.reviewState,saved);assert.equal(saved.filters.risk,'HIGH');
assert.equal(saved.query,'ownership');assert.equal(saved.offset,50);assert.ok(saved.selected.has('finding:high'));
projectUI.activeId='b';await projectReviewOpen();
assert.notEqual(projectUI.reviewState,saved);assert.equal(projectUI.reviewState.query,'');
''')
