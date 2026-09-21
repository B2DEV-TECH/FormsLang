"""Explicit project generation and code approval using the existing shell."""

GENERATION_PROJECT_JS = r"""
function projectGenerationCurrent(c,s){return projectCurrent(c)&&projectUI.view==='generate'&&projectUI.generationState===s;}
async function projectGenerationOpen(){
  const selected=projectUI.generationState?.projectId===projectUI.activeId?projectUI.generationState.selected:null;
  projectUI.view='generate';const c=projectContext(),s={busy:false,serial:0,projectId:c.id,selected};projectUI.generationState=s;
  $('project-content').innerHTML=projectSectionNav('generate')+'<h2 id="project-generation-title" tabindex="-1">Generate reviewable APEXlang</h2><p id="project-generation-status" role="status">Loading generation scope…</p><div id="project-generation-body"></div>';projectBindSectionNav();$('project-generation-title').focus();
  try{const data=await api(`/api/v2/projects/${c.id}/generation`);if(!projectGenerationCurrent(c,s))return;s.data=data;projectGenerationRender();if(selected&&data.modules.some(m=>m.source_id===selected))await projectGenerationModule(selected);}
  catch(e){if(projectGenerationCurrent(c,s))$('project-generation-status').textContent=e.message;}
}
function projectGenerationRender(){
  const s=projectUI.generationState,d=s.data;
  $('project-generation-status').textContent='Assessment: '+projectStatusLabel(d.freshness);
  $('project-generation-body').innerHTML=`<p>${esc(d.target?.platform||'Oracle APEX')} ${esc(d.target?.version||'')} / APEXlang. One independent application per eligible module. No automatic deployment.</p><p>Architecture decisions, code approval and generation authorization are separate. AUTO does not mean ready to generate.</p><div class="project-review-split"><section aria-label="Generation modules"><h3>Selected module</h3><table><thead><tr><th scope="col">Module</th><th scope="col">Code review</th></tr></thead><tbody>${d.modules.map(m=>`<tr><td><button type="button" class="btn" data-generation-module="${esc(m.source_id)}">${esc(m.module)}</button></td><td>${m.prepared?'Prepared':'Not prepared'}</td></tr>`).join('')}</tbody></table>${d.modules.length?'':'<p>No supported analyzed Forms representation is available.</p>'}</section><section id="project-generation-detail" class="project-review-detail" aria-label="Generation prerequisites"><p>Select a module to inspect its blockers and reviewed target plan.</p></section></div><h3>Versioned artifacts</h3><p>Editing an artifact invalidates its validation. Generating again never replaces earlier files. Validation checks syntax, not runtime equivalence.</p><div id="project-generation-artifacts">${d.artifacts.map(a=>`<article><h4>${esc(a.artifact_id)}</h4><p>${esc(a.status)} · ${esc(a.validation_status)} · ${esc(a.created_at)}</p><p>${esc(a.integrity||'')}</p><code>${esc(a.sha256)}</code><div class="project-actions"><a class="btn" download="application.apex.zip" href="/api/v2/projects/${encodeURIComponent(projectUI.activeId)}/artifacts/${encodeURIComponent(a.artifact_id)}/download">Download APEXlang ZIP</a><button type="button" class="btn" data-generation-validate="${esc(a.artifact_id)}">Validate offline with SQLcl</button></div>${a.validation?`<p>${esc(a.validation.message)} ${esc(a.validation.tool_version||'')}</p>`:''}</article>`).join('')||'<p>No artifacts generated. Resolve an eligible module scope first.</p>'}</div>`;
  $('project-generation-body').querySelectorAll('[data-generation-module]').forEach(el=>el.onclick=()=>projectGenerationModule(el.dataset.generationModule));
  $('project-generation-body').querySelectorAll('[data-generation-validate]').forEach(el=>el.onclick=()=>projectGenerationWrite(`/artifacts/${encodeURIComponent(el.dataset.generationValidate)}/validate`,{},()=>projectGenerationOpen()));
}
async function projectGenerationModule(id){
  const c=projectContext(),s=projectUI.generationState;if(s.busy)return;const serial=++s.serial;s.selected=id;
  $('project-generation-detail').innerHTML='<p>Checking current source, decisions and code approvals…</p>';
  try{const d=await api(`/api/v2/projects/${c.id}/generation/modules/${encodeURIComponent(id)}`);if(!projectGenerationCurrent(c,s)||serial!==s.serial)return;s.detail=d;projectGenerationRenderModule();}
  catch(e){if(projectGenerationCurrent(c,s)&&serial===s.serial)$('project-generation-status').textContent=e.message;}
}
function projectGenerationRenderModule(){
  const s=projectUI.generationState,d=s.detail,p=d.plan||{},prepared=d.code_revision!==null;
  $('project-generation-detail').innerHTML=`<h3 tabindex="-1" id="project-generation-module-title">${esc(d.module)}</h3><p>${d.ready?'Ready for this reviewed scope':'Blocked — resolve the prerequisites below'}</p><ul>${d.blockers.map(b=>`<li><strong>${esc(b.code)}</strong>: ${esc(b.message)}</li>`).join('')}</ul>${projectButton('project-generation-review','Review architecture decisions')}${!prepared?projectButton('project-generation-prepare','Prepare code review'):''}${prepared?`<h4>Target prerequisites</h4><p>Confirm against the observed source and target design. These confirmations do not implement missing behavior.</p><label><input type="checkbox" id="generation-security" ${p.security_confirmed?'checked':''}> Target access, authorization and identity behavior reviewed</label><label><input type="checkbox" id="generation-database" ${p.database_confirmed?'checked':''}> Database objects and prerequisites reviewed</label><label><input type="checkbox" id="generation-mapping" ${p.mapping_confirmed?'checked':''}> Supported structural mappings and ownership reviewed</label><label>Rationale<textarea id="generation-rationale" maxlength="4000">${esc(p.rationale||'')}</textarea></label>${d.bindings.map((b,i)=>`<label>${esc(b.block)} · ${esc(b.table)} — confirmed row key<select id="generation-key-${i}"><option value="">Not confirmed</option>${b.columns.map(col=>`<option value="${esc(col)}" ${b.confirmed_key===col?'selected':''}>${esc(col)}</option>`).join('')}</select></label>`).join('')}${projectButton('project-generation-plan','Save reviewed target plan')}<h4>Code approval</h4><p>Each executable unit requires its own review. Unsupported execution mappings remain blocked.</p>${d.tasks.map(t=>`<p><button type="button" class="btn" data-generation-task="${esc(t.id)}">${esc(t.title)}</button> ${esc(t.state)}</p>`).join('')||'<p>No executable conversion units in this module.</p>'}<div id="project-generation-code"></div><div class="project-actions">${projectButton('project-generation-run','Generate APEXlang',true)}</div>`:''}`;
  $('project-generation-review').onclick=()=>projectReviewOpen({filters:{module:d.module}});
  if(prepared)$('project-generation-code').insertAdjacentHTML('beforebegin','<p>Save the reviewed target plan before approving code. Changing the plan requires code revalidation.</p>');
  if(!prepared){$('project-generation-prepare').onclick=()=>projectGenerationWrite(`/generation/modules/${encodeURIComponent(d.source_id)}/prepare`,d.binding,result=>{s.detail=result;projectGenerationRenderModule();});return;}
  $('project-generation-plan').onclick=()=>{
    const keys={};d.bindings.forEach((b,i)=>{const value=$('generation-key-'+i).value;if(value)keys[b.block]=value;});
    const plan={security_confirmed:$('generation-security').checked,database_confirmed:$('generation-database').checked,mapping_confirmed:$('generation-mapping').checked,rationale:$('generation-rationale').value,keys};
    return projectGenerationWrite(`/generation/modules/${encodeURIComponent(d.source_id)}/plan`,{...d.binding,code_revision:d.code_revision,target_revision:d.target_revision,plan},result=>{s.detail=result;projectGenerationRenderModule();});
  };
  $('project-generation-run').disabled=!d.ready;
  $('project-generation-run').onclick=()=>projectGenerationWrite('/generation',{...d.binding,scopes:[{source_id:d.source_id,target_revision:d.target_revision,code_revision:d.code_revision}]},()=>projectGenerationOpen());
  $('project-generation-detail').querySelectorAll('[data-generation-task]').forEach(el=>el.onclick=()=>projectGenerationCode(el.dataset.generationTask));
}
async function projectGenerationCode(id){
  const c=projectContext(),s=projectUI.generationState;if(s.busy)return;const d=s.detail,serial=++s.serial;
  try{const task=await api(`/api/v2/projects/${c.id}/generation/modules/${encodeURIComponent(d.source_id)}/code/${encodeURIComponent(id)}`);if(!projectGenerationCurrent(c,s)||serial!==s.serial)return;
    $('project-generation-code').innerHTML=`<h4>${esc(task.title)}</h4><p>${esc(task.notice)}</p><details><summary>Bounded, redacted source evidence</summary><pre>${esc(task.source_excerpt)}</pre></details><label>Target PL/SQL<textarea id="generation-code" maxlength="64000" spellcheck="false">${esc(task.code)}</textarea></label><label>Code review rationale<textarea id="generation-code-rationale" maxlength="4000">${esc(task.comment)}</textarea></label><label><input type="checkbox" id="generation-code-confirm"> I reviewed this exact target code against the authorized source and target behavior.</label>${projectButton('generation-code-draft','Save draft')}${projectButton('generation-code-approve','Approve target code')}<details><summary>Code history</summary>${task.history.map(h=>`<p>${esc(h.state)} · ${esc(h.decided_at)}<br>${esc(h.comment)}</p>`).join('')||'No code decisions yet.'}</details>`;
    const save=state=>projectGenerationWrite(`/generation/modules/${encodeURIComponent(d.source_id)}/code/${encodeURIComponent(id)}`,{...task.binding,target_revision:task.target_revision,code_revision:task.code_revision,state,code:$('generation-code').value,rationale:$('generation-code-rationale').value,code_confirmed:$('generation-code-confirm').checked},async()=>{s.busy=false;await projectGenerationModule(d.source_id);});
    $('generation-code-draft').onclick=()=>save('pending');$('generation-code-approve').onclick=()=>save('approved');
  }catch(e){if(projectGenerationCurrent(c,s)&&serial===s.serial)$('project-generation-status').textContent=e.message;}
}
async function projectGenerationWrite(path,request,complete){
  const c=projectContext(),s=projectUI.generationState;if(s.busy)return;s.busy=true;
  $('project-generation-status').textContent='Working locally. Generation and validation never deploy to a database.';
  try{const result=await api(`/api/v2/projects/${c.id}${path}`,request);if(!projectGenerationCurrent(c,s))return;await complete(result);if(projectGenerationCurrent(c,s))$('project-generation-status').textContent='Saved. Evidence and previous artifacts remain preserved.';}
  catch(e){if(projectGenerationCurrent(c,s))$('project-generation-status').textContent=e.status===409?'Evidence changed. Your draft remains visible; reload the module and review current revisions before submitting again.':e.message;}
  finally{s.busy=false;}
}
"""
