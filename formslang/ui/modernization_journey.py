"""One read-only path through saved Form, relationship, evidence and blockers."""

JOURNEY_PROJECT_JS = r'''
function projectJourneyCurrent(c,s){return projectCurrent(c)&&projectUI.view==='journey'&&projectUI.journeyState===s;}
async function projectJourneyOpen(){
  projectUI.view='journey';const c=projectContext(),s={serial:0,edge:null,detail:null};projectUI.journeyState=s;
  $('project-content').innerHTML=projectSectionNav('journey')+'<header><h2 id="project-step-title" tabindex="-1">Explore a Form</h2><p>Follow saved relationships, inspect bounded source evidence and see current generation blockers. Read-only prototype.</p></header><p id="project-journey-status" role="status">Loading saved assessment...</p><div id="project-journey-body"></div>';
  projectBindSectionNav();$('project-step-title').focus();
  try{
    s.map=await api(`/api/v2/projects/${encodeURIComponent(c.id)}/system-map?view=FOCUS`);
    if(!projectJourneyCurrent(c,s))return;
    if(s.map.available_forms.length)await projectJourneyForm(s.map.available_forms[0].id);
    else $('project-journey-status').textContent='No analyzed Form is available in the saved assessment.';
  }catch(e){if(projectJourneyCurrent(c,s))$('project-journey-status').textContent=e.message;}
}
async function projectJourneyForm(nodeId){
  const c=projectContext(),s=projectUI.journeyState,serial=++s.serial;
  s.edge=null;s.detail=null;s.form=null;s.generationDetail=null;$('project-journey-status').textContent='Opening Form and current generation status...';
  $('project-journey-body').innerHTML='<p role="status">Loading selected Form and its current blockers...</p>';
  try{
    const form=await api(`/api/v2/projects/${encodeURIComponent(c.id)}/module-360?node=${encodeURIComponent(nodeId)}`);
    if(!projectJourneyCurrent(c,s)||serial!==s.serial)return;
    if(form.node.layer!=='FORM')throw Error('The selected node is not a Form.');
    s.form=form;
    const generation=await api(`/api/v2/projects/${encodeURIComponent(c.id)}/generation`);
    if(!projectJourneyCurrent(c,s)||serial!==s.serial)return;
    s.generation=generation;s.generationDetail=null;
    const scope=(generation.modules||[]).find(m=>m.module===form.module);
    if(scope)s.generationDetail=await api(`/api/v2/projects/${encodeURIComponent(c.id)}/generation/modules/${encodeURIComponent(scope.source_id)}`);
    if(projectJourneyCurrent(c,s)&&serial===s.serial)projectJourneyRender();
  }catch(e){if(projectJourneyCurrent(c,s)&&serial===s.serial)$('project-journey-status').textContent=e.message;}
}
async function projectJourneyEdge(edgeId){
  const c=projectContext(),s=projectUI.journeyState,serial=++s.serial;
  s.edge=edgeId;s.detail=null;projectJourneyRender();
  try{
    const detail=await api(`/api/v2/projects/${encodeURIComponent(c.id)}/system-map/edge?id=${encodeURIComponent(edgeId)}`);
    if(!projectJourneyCurrent(c,s)||serial!==s.serial)return;
    if(detail.edge.source!==s.form.node.id)throw Error('Relationship no longer belongs to this Form. Reload the project.');
    s.detail=detail;projectJourneyRender();
  }catch(e){if(projectJourneyCurrent(c,s)&&serial===s.serial)$('project-journey-status').textContent=e.message;}
}
function projectJourneyBlockers(detail){
  if(!detail)return '<p>No generation scope is available for this Form and target.</p>';
  const blockers=detail.blockers||[];
  if(detail.ready)return '<p>Current generation check reports this reviewed scope ready. This is not a runtime equivalence claim.</p>';
  const groups=new Map();for(const b of blockers){const group=groups.get(b.code)||{count:0,message:b.message};group.count++;groups.set(b.code,group);}
  return `<p><b>Blocked:</b> ${blockers.length} current blocker records in ${groups.size} categories.</p><ul>${[...groups].map(([code,g])=>`<li><b>${esc(code)}</b> (${g.count}): ${esc(g.message)}</li>`).join('')}</ul>`;
}
function projectJourneyEvidence(detail){
  if(!detail)return '<p>Select a relationship to inspect its saved evidence.</p>';
  const e=detail.edge;
  const facts=detail.evidence.map(p=>`<li><b>${esc(p.level)}</b> ${esc(p.text||'No structural text')} <code>${esc(p.id)}</code>${p.location?.line?` · decoded body line ${Number(p.location.line)}`:''}</li>`).join('');
  const excerpts=detail.source.map(p=>`<details open><summary>${esc(p.name)} · bounded structural excerpt${p.truncated?' (truncated)':''}</summary><pre>${esc(p.excerpt)}</pre></details>`).join('');
  const limits=[e.level==='FACT'?'Observed structural relationship; runtime behavior is unverified.':'Engine inference; requires human confirmation.',
    'Literals, comments and sensitive context are omitted from source excerpts.',
    detail.sampled?'Only a bounded sample of component edges is shown.':'',
    detail.evidence.length<e.evidence_refs.length?'Some referenced evidence is unavailable in this saved assessment.':''].filter(Boolean);
  return `<h3>${esc(e.source_name)} → ${esc(e.target_name)}</h3><p><b>${esc(e.classification)}</b> · ${esc(e.level)} · ${Number(e.count)} component relationship${e.count===1?'':'s'}</p>${e.target_unresolved?'<p class="project-state-warning"><b>Unresolved reference.</b> The target name is observed, but no supplied object is confirmed as its destination.</p>':''}<h4>Saved evidence</h4>${facts?`<ul>${facts}</ul>`:'<p>No evidence text is available for this relationship.</p>'}${excerpts||'<p>No source excerpt is available for this relationship.</p>'}<h4>What this does not prove</h4><ul>${limits.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>${e.target_layer==='FORM'&&!e.target_unresolved?`<button type="button" class="btn" id="project-journey-follow">Open related Form: ${esc(e.target_name)}</button>`:''}`;
}
function projectJourneyRender(){
  const s=projectUI.journeyState,f=s.form;if(!f)return;
  const outbound=f.neighbours.outbound,items=outbound.items||[],fresh=f.freshness||'UNVERIFIED';
  $('project-journey-status').textContent=`Saved assessment ${String(f.analysis_revision||'').slice(0,12)} · source ${projectStatusLabel(fresh)} · ${items.length} of ${outbound.total} outbound relationships shown.`;
  $('project-journey-body').innerHTML=`<section class="project-panel project-panel-wide"><h3>1. Open a Form</h3><div class="project-actions">${s.map.available_forms.map(x=>`<button type="button" class="btn ${x.id===f.node.id?'primary':''}" data-journey-form="${esc(x.id)}" aria-pressed="${x.id===f.node.id}">${esc(x.name)}</button>`).join('')}</div>${s.map.selector?.truncated?`<p>Form selector is limited to ${Number(s.map.selector.shown)} of ${Number(s.map.selector.total)} Forms.</p>`:''}<p><b>${esc(f.node.name)}</b> · ${esc(f.module)} · ${Number(f.findings_total||0)} saved findings</p>${fresh!=='CURRENT'?'<p class="project-state-warning">Saved evidence may be stale or incomplete. Reassess source freshness before relying on it.</p>':''}</section><section class="project-panel project-panel-wide"><h3>2. Follow a relationship</h3>${items.length?`<ul class="project-journey-relations">${items.map(x=>`<li><button type="button" class="btn" data-journey-edge="${esc(x.edge_id)}" aria-pressed="${x.edge_id===s.edge}">${esc(x.presentation_label?.technical||x.classification)} → ${esc(x.name)}</button> <span>${esc(x.status)}${x.unresolved?' · UNRESOLVED':''}</span></li>`).join('')}</ul>`:'<p>No outbound relationships were observed.</p>'}${outbound.total>items.length?'<p>Additional relationships are outside the Module 360 display limit.</p>':''}</section><section class="project-panel project-panel-wide" id="project-journey-evidence"><h3>3. Inspect evidence and limits</h3>${projectJourneyEvidence(s.detail)}</section><section class="project-panel project-panel-wide" id="project-journey-blockers"><h3>4. Generation status for this Form</h3>${projectJourneyBlockers(s.generationDetail)}<p>These are the existing project service checks. This prototype cannot change decisions or generate code.</p></section>`;
  $('project-journey-body').querySelectorAll('[data-journey-form]').forEach(el=>el.onclick=()=>projectJourneyForm(el.dataset.journeyForm));
  $('project-journey-body').querySelectorAll('[data-journey-edge]').forEach(el=>el.onclick=()=>projectJourneyEdge(el.dataset.journeyEdge));
  if(s.detail?.edge.target_layer==='FORM'&&!s.detail.edge.target_unresolved)$('project-journey-follow').onclick=()=>projectJourneyForm(s.detail.edge.target);
}
'''
