"""Real Reports JavaScript: disclosure, stale-response and conflict behavior."""

import subprocess

import pytest
from test_project_ui_behavior import DOM, NODE

from formslang.ui.modernization_project import PROJECT_JS

pytestmark = pytest.mark.skipif(NODE is None, reason='Node required')


def run(tmp_path, script):
    from formslang.ui.modernization_reports import REPORTS_PROJECT_JS
    path = tmp_path / 'reports.cjs'
    path.write_text(DOM + PROJECT_JS + REPORTS_PROJECT_JS + '\n(async()=>{' + script +
                    "\n})().then(()=>console.log('COMPLETE')).catch(e=>{console.error(e);process.exitCode=1;});", encoding='utf-8')
    result = subprocess.run([NODE, str(path)], capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'COMPLETE' in result.stdout.splitlines(), result.stdout + result.stderr


def test_reports_disclosure_defaults_and_escaped_filename(tmp_path):
    run(tmp_path, r'''
projectUI.activeId='a';api=async()=>({binding:{},freshness:'CURRENT',formats:[{id:'executive',filename:'<script>bad()</script>'}]});
await projectReportsOpen();
assert.ok(!$('project-reports-body').innerHTML.includes('<script>'));
assert.match($('project-reports-body').innerHTML,/&lt;script/);
assert.ok(!$('project-reports-body').innerHTML.includes('checked'));
assert.match($('project-reports-body').innerHTML,/not anonymous/);
assert.ok($('project-reports-title').focused);
''')


def test_reports_old_project_response_is_ignored(tmp_path):
    run(tmp_path, r'''
projectUI.activeId='a';const d=deferred();api=()=>d.promise;const pending=projectReportsOpen();
projectUI.activeId='b';$('project-reports-body').innerHTML='B';d.resolve({formats:[],binding:{}});await pending;
assert.equal($('project-reports-body').innerHTML,'B');
''')


def test_report_conflict_does_not_download_or_retry(tmp_path):
    run(tmp_path, r'''
projectUI.activeId='a';api=async()=>({binding:{review_revision:1},freshness:'CURRENT',formats:[{id:'executive',filename:'executive-summary.html'}]});
await projectReportsOpen();let count=0;global.fetch=async()=>{count++;return {ok:false,status:409,json:async()=>({error:'Changed'})};};
await projectReportsDownload('executive');
assert.equal(count,1);assert.match($('project-reports-status').textContent,/reload/i);
assert.equal(projectUI.reportsState.busy,false);
''')


def test_sensitive_download_preserves_server_filename(tmp_path):
    run(tmp_path, r'''
projectUI.activeId='a';api=async()=>({binding:{},freshness:'CURRENT',formats:[{id:'decisions',filename:'decisions.json'}]});
await projectReportsOpen();$('reports-include-notes').checked=true;
let downloaded;document.createElement=()=>({click(){downloaded=this.download;},remove(){}});document.body.appendChild=()=>{};
URL.createObjectURL=()=> 'blob:report';URL.revokeObjectURL=()=>{};
global.fetch=async()=>({ok:true,headers:{get:()=> 'attachment; filename="decisions-sensitive.json"'},blob:async()=>({})});
await projectReportsDownload('decisions');assert.equal(downloaded,'decisions-sensitive.json');
''')


def test_reports_wait_for_existing_project_open_freshness_operation(tmp_path):
    run(tmp_path, r'''
projectUI.activeId='a';const opening=deferred();projectUI.opening=opening.promise;
let calls=0;api=async()=>{calls++;return {formats:[],binding:{},freshness:'CURRENT'};};
const pending=projectReportsOpen();await Promise.resolve();
assert.equal(calls,0,'Snapshot must not race the already-running freshness operation');
opening.resolve();await pending;assert.equal(calls,1);assert.ok(projectUI.reportsState.data);
''')
