// Actual generation UI/API/SQLite/exporter. No substituted responses or bytes.
export async function generationChecks({evaluate,click,clickSelector,value,wait,check,screenshot,pick,folder}){
  await click('project-home');await wait(()=>evaluate(`!!document.getElementById('project-new')`),'generation onboarding');
  await click('project-new');await value('project-name','Synthetic generation acceptance');await click('project-next');
  await click('project-forms');await pick(folder);await wait(()=>evaluate(`projectUI.draft.preview!==null`),'generation discovery');
  await click('project-next');await click('project-next');await click('project-next');
  await wait(()=>evaluate(`projectUI.view==='overview'&&!projectUI.jobId&&projectUI.overview?.assessment.freshness==='CURRENT'`),'generation assessment');
  const project=await evaluate('projectUI.activeId');
  await clickSelector('[data-project-section="generate"]');await wait(()=>evaluate(`projectUI.generationState?.data?.modules.length===1`),'generation module list');
  await clickSelector('[data-generation-module]');await wait(()=>evaluate(`!!document.getElementById('project-generation-prepare')`),'source-bound preparation');
  check('E unreviewed scope is blocked',await evaluate(`projectUI.generationState.detail.blockers.length>0&&!projectUI.generationState.detail.ready`));
  await click('project-generation-prepare');await wait(()=>evaluate(`!!document.getElementById('project-generation-plan')&&!projectUI.generationState.busy`),'prepared code session');
  // Exercise real architectural review separately from executable code approval.
  await click('project-generation-review');await wait(()=>evaluate(`!!projectUI.reviewState?.page`),'module review queue');
  const findings=await evaluate(`projectUI.reviewState.page.rows.map(r=>r.id)`);
  for(const finding of findings){
    await clickSelector(`[data-review-item="${finding}"]`);
    await wait(()=>evaluate(`projectUI.reviewState.detail?.item.id===${JSON.stringify(finding)}&&!projectUI.reviewState.busy`),'structural finding');
    await click('project-review-accept');await wait(()=>evaluate(`!projectUI.reviewState.busy&&projectUI.reviewState.detail?.item.review_state==='APPROVE'`),'accepted structural finding');
  }
  await clickSelector('[data-project-section="generate"]');await wait(()=>evaluate(`!!projectUI.generationState?.data`),'reviewed generation');
  await clickSelector('[data-generation-module]');await wait(()=>evaluate(`!!document.getElementById('generation-security')`),'target prerequisite controls');
  for(const id of ['generation-security','generation-database','generation-mapping'])await click(id);
  await value('generation-rationale','Synthetic notice validation; APEX authentication and absence of database writes reviewed.');
  await click('project-generation-plan');await wait(()=>evaluate(`!!projectUI.generationState.detail?.target_revision&&!projectUI.generationState.busy`),'saved target plan');
  check('G architecture approval does not approve executable code',await evaluate(`!projectUI.generationState.detail.ready&&projectUI.generationState.detail.tasks.length===1`));
  await clickSelector('[data-generation-task]');await wait(()=>evaluate(`!!document.getElementById('generation-code')`),'code approval evidence');
  await value('generation-code',"BEGIN IF :P0_MESSAGE IS NULL THEN raise_application_error(-20001, 'Required'); END IF; END;");
  await value('generation-code-rationale','Reviewed synthetic validation against the saved target plan and Forms evidence.');
  await click('generation-code-confirm');await click('generation-code-approve');
  await wait(()=>evaluate(`projectUI.generationState.detail?.ready&&!projectUI.generationState.busy`),'code-approved eligible scope');
  check('G explicit code approval recorded independently',await evaluate(`projectUI.generationState.detail.tasks[0].state==='approved'`));
  check('E eligible scope uses explicit target confirmations',await evaluate(`!document.getElementById('project-generation-run').disabled`));
  await click('project-generation-run');await wait(()=>evaluate(`projectUI.generationState?.data?.artifacts.length===1`),'generated immutable artifact');
  const first=await evaluate('projectUI.generationState.data.artifacts[0]');
  check('E artifact is generated not implicitly validated',first.status==='Generated'&&first.validation_status==='Not Validated');
  check('E exact generated ZIP downloadable',await evaluate(`(async()=>{const r=await fetch('/api/v2/projects/'+projectUI.activeId+'/artifacts/'+${JSON.stringify(first.artifact_id)}+'/download');return r.ok&&r.headers.get('content-type')==='application/zip'&&(await r.arrayBuffer()).byteLength===${first.size_bytes};})()`));
  await clickSelector('[data-generation-validate]');await wait(()=>evaluate(`!!projectUI.generationState?.data?.artifacts[0]?.validation`),'explicit offline validation');
  const validation=await evaluate('projectUI.generationState.data.artifacts[0].validation');
  check('E validation records mode and exact artifact hash',validation.mode==='offline-syntax'&&validation.artifact_sha256===first.sha256,validation);
  await screenshot('generation-artifact.png');
  await click('project-home');await wait(()=>evaluate(`!!document.querySelector('[data-project-open="${project}"]')`),'generated recent project');
  await clickSelector(`[data-project-open="${project}"]`);await wait(()=>evaluate(`projectUI.view==='overview'&&!projectUI.jobId`),'generated project reopened');
  await clickSelector('[data-project-section="generate"]');await wait(()=>evaluate(`projectUI.generationState?.data?.artifacts.length===1`),'saved artifacts reopened');
  check('E reopened artifact identity is unchanged',await evaluate('projectUI.generationState.data.artifacts[0].artifact_id')===first.artifact_id);
  check('E Generate keyboard and status semantics',await evaluate(`document.getElementById('project-generation-status').getAttribute('role')==='status'&&document.querySelector('[data-project-section="generate"]').getAttribute('aria-current')==='page'`));
}
