"""Project-scoped human governance in the existing Workbench shell."""

REVIEW_PROJECT_STYLE = r"""
.project-review-split{display:grid;grid-template-columns:minmax(280px,42%) minmax(0,1fr);gap:16px;align-items:start}
.project-review-queue{max-height:70vh;overflow:auto;resize:horizontal;min-width:250px;max-width:100%}
.project-review-queue table{width:100%;border-collapse:collapse}
.project-review-queue td,.project-review-queue th{padding:8px;text-align:left;border-bottom:1px solid var(--border)}
.project-review-queue button{text-align:left;white-space:normal}
.project-review-detail{min-width:0;overflow-wrap:anywhere}
.project-review-detail pre{white-space:pre-wrap;max-height:260px;overflow:auto}
.project-review-detail textarea{width:100%;min-height:80px}
.project-review-detail label{display:block;margin-top:8px}
.project-review-detail details{margin:12px 0}
#project-review-filters{grid-template-columns:repeat(auto-fit,minmax(140px,1fr));align-items:end}
#project-review-filters label{min-width:0;display:grid;gap:4px}
#project-review-filters input,#project-review-filters select{width:100%;min-width:0}
@media(max-width:900px){.project-review-split{grid-template-columns:1fr}.project-review-queue{resize:none;max-height:320px}}
"""

REVIEW_PROJECT_JS = r"""
const projectReviewStates={PENDING:'Pending',APPROVE:'Accepted',MODIFY:'Changed',REJECT:'Needs Review',DEFER:'Deferred',STALE:'Needs Revalidation'};
function projectReviewCurrent(c,s){return projectCurrent(c)&&projectUI.view==='review'&&projectUI.reviewState===s;}
function projectReviewOptions(values,selected){return '<option value="">Any</option>'+Object.entries(values).map(([v,label])=>`<option value="${esc(v)}" ${selected===v?'selected':''}>${esc(label)}</option>`).join('');}
async function projectReviewOpen(options={}){
  const resume=!Object.keys(options).length&&projectUI.reviewState?.projectId===projectUI.activeId;
  projectUI.view='review';if(!resume)projectUI.reviewState={projectId:projectUI.activeId,query:'',filters:{},offset:0,limit:50,selected:new Set(),page:null,detail:null,request:0,busy:false,...options};
  projectReviewRender();$('project-step-title').focus();await projectReviewLoad();
  if(resume&&projectUI.view==='review'&&projectUI.reviewState.focusId)$(projectUI.reviewState.focusId)?.focus();
}
function projectReviewRender(){
  const s=projectUI.reviewState,p=s.page;
  const filters=[['risk','Risk',projectRiskLabels],['recommendation','Recommendation',projectRecommendationLabels],['intervention','Intervention',{AUTO:'Mechanical / AUTO',ASSISTED:'Assisted',MANUAL:'Human decision',UNKNOWN:'Unknown'}],['review','Status',projectReviewStates]];
  $('project-content').innerHTML=`${projectSectionNav('review')}<h2 id="project-step-title" tabindex="-1">Modernization Review</h2><p>Engine proposes. Evidence explains. Human decides. Code approval and generation authorization remain separate.</p><form id="project-review-filters" class="project-filter-bar"><label>Search <input id="project-review-query" type="search" maxlength="500" value="${esc(s.query)}"></label>${filters.map(([key,label,values])=>`<label>${label}<select id="project-review-${key}">${projectReviewOptions(values,s.filters[key])}</select></label>`).join('')}<label>Module <input id="project-review-module" maxlength="500" value="${esc(s.filters.module||'')}"></label><label>Source type <input id="project-review-source_type" maxlength="100" value="${esc(s.filters.source_type||'')}"></label><button class="btn primary" type="submit">Apply Filters</button></form><p id="project-review-status" role="status" aria-live="polite">${p?`${Number(p.total)} findings · ${esc(projectStatusLabel(p.freshness))}`:'Loading review queue…'}</p><div class="project-actions">${projectButton('project-review-bulk-accept','Bulk Accept')}${projectButton('project-review-bulk-defer','Bulk Defer')}${projectButton('project-review-bulk-needs','Bulk Needs Review')}</div><div class="project-review-split"><div class="project-review-queue"><table><caption>Priority queue</caption><thead><tr><th scope="col">Select</th><th scope="col">Finding / evidence</th><th scope="col">Status</th></tr></thead><tbody>${(p?.rows||[]).map(row=>`<tr><td><input type="checkbox" data-review-select="${esc(row.id)}" aria-label="Select ${esc(row.name)}" ${s.selected.has(row.id)?'checked':''}></td><td><button type="button" class="btn" data-review-item="${esc(row.id)}">${esc(row.module)} · ${esc(row.name)}</button><p>${esc(row.risk)} · ${esc(row.intervention)} · ${esc(projectRecommendationLabels[row.recommendation]||row.recommendation)}</p><p>${esc(row.reason)}</p></td><td>${esc(projectReviewStates[row.review_state]||'Needs Review')}</td></tr>`).join('')||'<tr><td colspan="3">No findings match these filters.</td></tr>'}</tbody></table><div class="project-actions">${projectButton('project-review-prev-page','Previous page')}${projectButton('project-review-next-page','Next page')}</div></div><article id="project-review-detail" class="project-review-detail" aria-label="Finding evidence and decision">Select a finding to inspect its evidence.</article></div>`;
  projectBindSectionNav();
  const queue=$('project-content').querySelector('.project-review-queue');if(queue){queue.scrollTop=s.scrollTop||0;queue.onscroll=()=>{s.scrollTop=queue.scrollTop;};}
  $('project-content').onfocusin=e=>{if(e.target.id?.startsWith('project-review-'))s.focusId=e.target.id;};
  $('project-review-filters').onsubmit=e=>{e.preventDefault();s.query=$('project-review-query').value;s.filters={};for(const key of ['risk','recommendation','intervention','review','module','source_type']){const v=$('project-review-'+key).value;if(v)s.filters[key]=v;}s.offset=0;s.page=null;s.detail=null;s.selected.clear();projectReviewLoad();};
  $('project-content').querySelectorAll('[data-review-item]').forEach(el=>el.onclick=()=>projectReviewDetail(el.dataset.reviewItem));
  $('project-content').querySelectorAll('[data-review-select]').forEach(el=>el.onchange=()=>{if(el.checked)s.selected.add(el.dataset.reviewSelect);else s.selected.delete(el.dataset.reviewSelect);});
  $('project-review-prev-page').disabled=!p||p.offset===0;$('project-review-next-page').disabled=!p||p.offset+p.limit>=p.total;
  $('project-review-prev-page').onclick=()=>{s.offset=Math.max(0,s.offset-s.limit);s.selected.clear();projectReviewLoad();};
  $('project-review-next-page').onclick=()=>{s.offset+=s.limit;s.selected.clear();projectReviewLoad();};
  $('project-review-bulk-accept').onclick=()=>projectReviewBulk('APPROVE');$('project-review-bulk-defer').onclick=()=>projectReviewBulk('DEFER');$('project-review-bulk-needs').onclick=()=>projectReviewBulk('REJECT');
  if(s.detail)projectReviewRenderDetail();
}
async function projectReviewLoad(){
  const c=projectContext(),s=projectUI.reviewState,request=++s.request;
  const params=new URLSearchParams({query:s.query,offset:String(s.offset),limit:String(s.limit),sort:'priority',...s.filters});
  if(s.page){params.set('revision',s.page.analysis_revision);params.set('review_revision',s.page.review_revision);}
  try{const page=await api(`/api/v2/projects/${c.id}/review?${params}`);if(!projectReviewCurrent(c,s)||request!==s.request)return;
    s.page=page;projectReviewRender();return page;
  }catch(e){if(!projectReviewCurrent(c,s))return;if(e.status===409){s.page=null;s.offset=0;s.selected.clear();}$('project-review-status').textContent=e.message+' Apply filters to reload current evidence.';}
}
async function projectReviewDetail(id,historyOffset=0){
  const c=projectContext(),s=projectUI.reviewState;s.selectedId=id;
  try{const params=new URLSearchParams({offset:String(historyOffset),limit:'50'});if(s.page){params.set('revision',s.page.analysis_revision);params.set('review_revision',s.page.review_revision);}
    const detail=await api(`/api/v2/projects/${c.id}/review/${encodeURIComponent(id)}?${params}`);
    if(!projectReviewCurrent(c,s)||s.selectedId!==id)return;s.detail=detail;projectReviewRenderDetail();
  }catch(e){if(projectReviewCurrent(c,s))$('project-review-status').textContent=e.message+' Reload the queue.';}
}
function projectReviewRenderDetail(){
  const s=projectUI.reviewState,d=s.detail,row=d.item;
  const score=row.priority_score!==undefined?row.priority_score:null;
  const scorePill=score!==null?`<span class="project-score-pill" data-risk="${esc(row.risk)}">Priority ${score}</span>`:'';
  const factors=(row.priority_factors||[]).map(f=>`<li>${esc(f)}</li>`).join('');
  const evidenceHtml=(d.evidence||[]).map(e=>`<section><h5>${esc(e.kind)} · ${esc(e.name)}</h5><pre>${esc(e.excerpt)}</pre>${e.truncated?'<p>Excerpt truncated.</p>':''}</section>`).join('')||'<p>No source excerpt is available for this finding.</p>';
  const stmts=(d.statements||[]).map(e=>`<p><b>${esc(e.kind)}</b>: ${esc(e.text)}</p>`).join('');

  $('project-review-detail').innerHTML=`<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;"><h3 tabindex="-1" id="project-review-heading" style="margin:0;">${esc(row.module)} · ${esc(row.name)}</h3>${scorePill}</div><p style="margin-bottom:14px;"><b>${esc(row.risk)} risk</b> · ${esc(row.intervention)} · Status: <b>${esc(projectReviewStates[row.review_state])}</b></p><p class="project-muted">The four layers below present one saved assessment and its review ledger; they are views of the same evidence, not separate models.</p><div class="review-layer-card"><div class="review-layer-header"><span>1. Observed evidence</span><span class="review-layer-badge">Saved static analysis</span></div><div class="review-layer-body"><p>Structural excerpts omit literals and comments. Inspect local source for exact values.</p>${evidenceHtml}${d.dependencies?.length?`<h5>Referenced Entities</h5>${projectDetailList(d.dependencies,'dependencies')}`:''}</div></div><div class="review-layer-card"><div class="review-layer-header"><span>2. Structural interpretation</span><span class="review-layer-badge">Engine signals</span></div><div class="review-layer-body"><p><b>Engine reasoning:</b> ${esc(row.reason)}</p>${(row.signals||[]).length?`<p><b>Signal codes:</b> ${(row.signals||[]).map(esc).join(', ')}</p>`:''}${(row.hotspot_ids||[]).length?`<p><b>Linked hotspot candidates:</b> ${Number(row.hotspot_ids.length)} — candidates for architecture review, not verdicts.</p>`:''}${factors?`<h5>Priority Factors</h5><ul style="padding-left:18px;margin:4px 0 10px;">${factors}</ul>`:''}${stmts?`<details><summary>Engine Inferences (${d.statements?.length||0})</summary>${stmts}</details>`:''}</div></div><div class="review-layer-card"><div class="review-layer-header"><span>3. Recommendation</span><span class="review-layer-badge">Engine proposal</span></div><div class="review-layer-body"><h4>Engine recommendation (PROPOSED)</h4><p>${esc(projectRecommendationLabels[d.engine_recommendation]||d.engine_recommendation)}</p><h4>Engine suggestion</h4><p>${esc(d.target_suggestion||'Needs architecture review')}</p>${projectUI.overview?.project?.target?.platform&&projectUI.overview.project.target.platform!=='Oracle APEX'?'<p class="project-muted">The engine phrases suggestions for Oracle APEX, the first supported implementation path. With no APEX target selected they are hints, not a target decision.</p>':''}</div></div><div class="review-layer-card"><div class="review-layer-header"><span>4. Human decision</span><span class="review-layer-badge">Append-only review ledger</span></div><div class="review-layer-body"><h4>Human decision</h4><p>${esc(d.human_decision?.recommendation||'No applicable decision')}</p><form id="project-review-decision"><label for="project-review-direction">Change direction</label><select id="project-review-direction">${Object.entries(projectRecommendationLabels).filter(([k])=>k!=='UNKNOWN').map(([k,v])=>`<option value="${k}">${esc(v)}</option>`).join('')}</select><label for="project-review-rationale">Rationale / follow-up note</label><textarea id="project-review-rationale" maxlength="4000" aria-describedby="project-review-form-error"></textarea><label for="project-review-reason">Reason for further review</label><select id="project-review-reason"><option value="BUSINESS_OWNER_INPUT">Needs business-owner input</option><option value="ARCHITECTURE_DECISION">Architecture decision required</option><option value="INSUFFICIENT_DATABASE_CONTEXT">Insufficient database context</option><option value="UNCLEAR_LEGACY_INTENT">Unclear legacy intent</option><option value="OTHER">Other</option></select><p id="project-review-form-error" role="alert"></p><div class="project-actions">${projectButton('project-review-accept','Accept',true)}${projectButton('project-review-change','Change')}${projectButton('project-review-needs','Needs Review')}${projectButton('project-review-defer','Defer')}</div></form><div class="project-actions">${projectButton('project-review-previous','Previous')}${projectButton('project-review-next','Next Priority')}</div><details open><summary>Decision history (${Number(d.history_total||d.history?.length||0)})</summary>${(d.history||[]).map(e=>`<p><b>${esc(projectReviewStates[e.action]||e.action)}</b> · ${esc(e.reviewer||'')} · ${esc(e.timestamp||'')} · ${e.applicable?'Current evidence':'Historical evidence'}<br>${esc(e.rationale)}<br>${esc(e.human_context?.note||'')}</p>`).join('')||'<p>No decisions recorded.</p>'}</details><details open><summary>Human annotations</summary>${(d.annotations||[]).map(a=>`<p>${esc(a.kind)} · ${a.applicable?'Current evidence':'Needs Revalidation'}<br>${esc(a.note)}</p>`).join('')}<label>Annotation type<select id="project-review-annotation-kind"><option value="CONFIRMED_BUSINESS_RULE">Confirmed business rule</option><option value="PRESENTATION_ONLY">Presentation-only behavior</option><option value="DATABASE_API_AUTHORITATIVE">Database API is authoritative</option><option value="LEGACY_LOGIC_OBSOLETE">Legacy logic is obsolete</option><option value="NEEDS_BUSINESS_OWNER_DECISION">Needs business-owner decision</option></select></label><label>Annotation note<textarea id="project-review-annotation-note" maxlength="4000"></textarea></label>${projectButton('project-review-annotate','Add annotation')}</details></div></div>`;
  $('project-review-decision').onsubmit=e=>e.preventDefault();
  const historyOffset=d.history_offset||0,historyLimit=d.history_limit||50;
  $('project-review-detail').insertAdjacentHTML('beforeend','<div class="project-actions">'+projectButton('project-review-history-previous','Previous history page')+projectButton('project-review-history-next','Next history page')+'</div>');
  $('project-review-history-previous').disabled=historyOffset===0;
  $('project-review-history-next').disabled=historyOffset+historyLimit>=Math.max(d.history_total||0,d.annotations_total||0);
  $('project-review-history-previous').onclick=()=>projectReviewDetail(row.id,Math.max(0,historyOffset-historyLimit));
  $('project-review-history-next').onclick=()=>projectReviewDetail(row.id,historyOffset+historyLimit);
  const values=action=>({action,rationale:$('project-review-rationale').value,reason_code:$('project-review-reason').value});
  $('project-review-accept').onclick=()=>projectReviewSave(values('APPROVE'));
  $('project-review-needs').onclick=()=>projectReviewSave(values('REJECT'));
  $('project-review-defer').onclick=()=>projectReviewSave({...values('DEFER'),note:$('project-review-rationale').value});
  $('project-review-change').onclick=()=>{const command={...values('MODIFY'),recommendation:$('project-review-direction').value};if(!command.rationale.trim()){$('project-review-form-error').textContent='Explain why the recommendation should change.';$('project-review-rationale').focus();return;}if(row.risk==='CRITICAL')projectReviewConfirm(command);else projectReviewSave(command);};
  $('project-review-annotate').onclick=()=>projectReviewSave({operation:'ANNOTATE',kind:$('project-review-annotation-kind').value,note:$('project-review-annotation-note').value});
  const rows=s.page?.rows||[],index=rows.findIndex(r=>r.id===row.id);
  $('project-review-previous').disabled=index<=0;$('project-review-next').disabled=index<0||index>=rows.length-1;
  $('project-review-previous').onclick=()=>projectReviewDetail(rows[index-1].id);$('project-review-next').onclick=()=>projectReviewDetail(rows[index+1].id);
}
function projectReviewConfirm(command){
  const c=projectContext(),s=projectUI.reviewState,id=s.detail.item.id,binding={...s.detail.binding};
  openModal('Review CRITICAL control');foot(null);$('modal-body').innerHTML=`<p>This change may affect a business, security, identity or approval control.</p><p>${esc(command.rationale)}</p><label><input type="checkbox" id="project-review-critical-confirm"> I reviewed the current evidence for this finding.</label>${projectButton('project-review-critical-submit','Confirm Decision',true)}`;
  $('project-review-critical-submit').onclick=()=>{if(!$('project-review-critical-confirm').checked)return;if(!projectReviewCurrent(c,s)||s.detail.item.id!==id){closeModal();return;}closeModal();projectReviewSave({...command,critical_confirmed:true},binding);};
}
async function projectReviewSave(command,exactBinding=null){
  const c=projectContext(),s=projectUI.reviewState,d=s.detail;if(s.busy||!d)return;s.busy=true;
  const draft={};for(const field of ['rationale','direction','reason','annotation-kind','annotation-note'])draft[field]=$('project-review-'+field)?.value||'';
  try{await api(`/api/v2/projects/${c.id}/review/${encodeURIComponent(d.item.id)}`,{...(exactBinding||d.binding),...command});if(!projectReviewCurrent(c,s))return;
    projectUI.overview=null;s.page=null;s.selected.clear();await projectReviewLoad();if(!projectReviewCurrent(c,s))return;await projectReviewDetail(d.item.id);if(projectReviewCurrent(c,s))$('project-review-status').textContent='Decision history saved.';
  }catch(e){if(!projectReviewCurrent(c,s))return;if(e.status===409){projectUI.overview=null;s.page=null;s.selected.clear();await projectReviewLoad();if(projectReviewCurrent(c,s))await projectReviewDetail(d.item.id);}if(projectReviewCurrent(c,s)){for(const [field,value] of Object.entries(draft)){const el=$('project-review-'+field);if(el)el.value=value;}$('project-review-status').textContent=e.message+' Your draft is preserved. Review current evidence before submitting again.';}
  }finally{s.busy=false;}
}
async function projectReviewBulk(action){
  const c=projectContext(),s=projectUI.reviewState;if(s.busy||!s.page)return;
  const findings=s.page.rows.filter(r=>s.selected.has(r.id)).map(r=>({id:r.id,revision:r.finding_revision}));
  if(!findings.length){$('project-review-status').textContent='Select findings on this page first.';return;}
  const request={project_id:c.id,analysis_revision:s.page.analysis_revision,source_revision:s.page.source_revision,review_revision:s.page.review_revision,action,findings,reason_code:'ARCHITECTURE_DECISION'};
  try{const preview=await api(`/api/v2/projects/${c.id}/review/bulk-preview`,request);if(!projectReviewCurrent(c,s))return;
    openModal('Review bulk eligibility');foot(null);$('modal-body').innerHTML=`<p>Selected: ${preview.selected} · Eligible: ${preview.eligible.length} · Excluded: ${preview.excluded.length}</p><ul>${preview.excluded.map(e=>`<li>${esc(e.id)}: ${esc(e.reasons.join(', '))}</li>`).join('')}</ul><p>Only the exact eligible set will be recorded. A concurrent change invalidates this preview.</p>${projectButton('project-review-bulk-submit','Confirm Eligible Decisions',true)}`;
    $('project-review-bulk-submit').disabled=!preview.eligible.length;
    $('project-review-bulk-submit').onclick=async()=>{if(!projectReviewCurrent(c,s)||s.busy)return;s.busy=true;$('project-review-bulk-submit').disabled=true;try{await api(`/api/v2/projects/${c.id}/review/bulk`,{...request,preview_token:preview.preview_token});if(!projectReviewCurrent(c,s))return;closeModal();projectUI.overview=null;s.page=null;s.detail=null;s.selected.clear();await projectReviewLoad();}catch(e){if(projectReviewCurrent(c,s)){closeModal();projectUI.overview=null;s.page=null;await projectReviewLoad();if(projectReviewCurrent(c,s))$('project-review-status').textContent=e.message+' Preview again before committing.';}}finally{s.busy=false;}};
  }catch(e){if(projectReviewCurrent(c,s))$('project-review-status').textContent=e.message;}
}
"""
