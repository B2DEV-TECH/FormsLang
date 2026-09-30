// WP-12: real browser, real bundled synthetic assessment, no decision writes.
export async function journeyChecks({evaluate,click,clickSelector,wait,check,screenshot,moduleSuffix='forms/shipments.xml'}){
  const before=await evaluate(`(async()=>{const r=await fetch('/api/v2/projects/'+projectUI.activeId+'/assessment');const a=(await r.json()).assessment;return [a.analysis_revision,a.review_revision,a.blueprint.source_revision];})()`);
  await clickSelector('[data-project-section="journey"]');
  await wait(()=>evaluate(`projectUI.view==='journey'&&projectUI.journeyState?.form?.node.name==='CUSTOMERS'&&!!projectUI.journeyState.generationDetail`),'saved CUSTOMERS Form in journey');
  check('journey opens persisted Form and current blockers',await evaluate(`projectUI.journeyState.form.freshness==='CURRENT'&&projectUI.journeyState.generationDetail.ready===false&&document.getElementById('project-journey-blockers').textContent.includes('MODULE_NOT_PREPARED')`));
  check('unresolved relationship remains labelled',await evaluate(`[...document.querySelectorAll('[data-journey-edge]')].some(b=>b.parentElement.textContent.includes('UNRESOLVED'))`));
  await clickSelector('[data-journey-edge]');
  await wait(()=>evaluate(`!!projectUI.journeyState.detail`),'selected relationship evidence');
  // Select the observed Form-to-Form edge by persisted classification, not display position.
  const openId=await evaluate(`projectUI.journeyState.form.neighbours.outbound.items.find(x=>x.classification==='OPENS_FORM').edge_id`);
  await clickSelector(`[data-journey-edge="${openId}"]`);
  await wait(()=>evaluate(`projectUI.journeyState.detail?.edge.id===${JSON.stringify(openId)}`),'exact opens Form evidence');
  check('selected relationship has matching saved proof and redacted source',await evaluate(`(()=>{const d=projectUI.journeyState.detail;return d.edge.source_name==='CUSTOMERS'&&d.edge.target_name==='SHIPMENTS'&&d.evidence[0].id===d.edge.evidence_refs[0]&&d.source[0].excerpt.includes('OPEN_FORM')&&!d.source[0].excerpt.includes('SHIPMENTS')&&document.getElementById('project-journey-evidence').textContent.includes('runtime behavior is unverified');})()`));
  await evaluate(`document.getElementById('project-journey-evidence').scrollIntoView({block:'start'})`);
  await screenshot('wp12-customers-evidence.png');
  const unresolvedId=await evaluate(`projectUI.journeyState.form.neighbours.outbound.items.find(x=>x.unresolved).edge_id`);
  await clickSelector(`[data-journey-edge="${unresolvedId}"]`);
  await wait(()=>evaluate(`projectUI.journeyState.detail?.edge.id===${JSON.stringify(unresolvedId)}`),'unresolved relationship evidence');
  check('unresolved target is not followable',await evaluate(`projectUI.journeyState.detail.edge.target_unresolved&&!document.getElementById('project-journey-follow')&&document.getElementById('project-journey-evidence').textContent.includes('Unresolved reference')`));
  await clickSelector(`[data-journey-edge="${openId}"]`);
  await wait(()=>evaluate(`projectUI.journeyState.detail?.edge.id===${JSON.stringify(openId)}`),'return to resolved edge');
  await click('project-journey-follow');
  check('following clears the previous Form while loading',await evaluate(`!document.getElementById('project-journey-follow')&&document.getElementById('project-journey-body').textContent.includes('Loading selected Form')`));
  await wait(()=>evaluate(`projectUI.journeyState.form?.node.name==='SHIPMENTS'&&!!projectUI.journeyState.generationDetail&&document.getElementById('project-journey-body').textContent.includes(${JSON.stringify(moduleSuffix)})`),'follow relationship to SHIPMENTS');
  check('followed Form shows its own blocker state',await evaluate(`projectUI.journeyState.form.module.endsWith(${JSON.stringify(moduleSuffix)})&&projectUI.journeyState.generationDetail.ready===false&&document.getElementById('project-journey-blockers').textContent.includes('MODULE_NOT_PREPARED')`));
  await evaluate(`document.getElementById('project-journey-blockers').scrollIntoView({block:'start'})`);
  await screenshot('wp12-followed-form.png');
  const after=await evaluate(`(async()=>{const r=await fetch('/api/v2/projects/'+projectUI.activeId+'/assessment');const a=(await r.json()).assessment;return [a.analysis_revision,a.review_revision,a.blueprint.source_revision];})()`);
  check('read-only journey keeps analysis, review and source revisions',JSON.stringify(before)===JSON.stringify(after),{before,after});
  await clickSelector('[data-project-section="overview"]');
  await wait(()=>evaluate(`projectUI.view==='overview'`),'return to Overview');
}
