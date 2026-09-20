"""Project onboarding and saved assessments, using the versioned project API."""

PROJECT_HTML = r'''<section id="project-workspace" aria-label="Modernization project" hidden>
  <div class="project-toolbar"><button class="btn" id="project-home">Recent Projects</button><button class="btn" id="project-resume">New Project</button><button class="btn" id="project-legacy">Open Existing Session</button></div>
  <p id="project-error" role="alert"></p>
  <p id="project-status" role="status" aria-live="polite"></p>
  <div id="project-content"></div>
</section>
'''

PROJECT_JS = r'''
const projectUI = {view:'legacy',draft:null,activeId:null,generation:0,jobId:null,timer:null,summary:null,overview:null,areas:null,previewRequest:0,busy:false,inventoryState:null,reviewContext:null};
const projectSteps = ['Project','Sources','Target','Analyze'];
function projectError(message, field) {
  $('project-error').textContent=message;
  if (field) { $(field).setAttribute('aria-invalid','true'); $(field).focus(); }
}
function projectContext(){return {generation:projectUI.generation,id:projectUI.activeId};}
function projectCurrent(c){return c.generation===projectUI.generation && c.id===projectUI.activeId;}
function projectEnter(view) {
  clearTimeout(projectUI.timer);projectUI.timer=null;projectUI.generation++;projectUI.view=view;
  projectUI.busy=false;projectUI.jobId=null;
  document.body.classList.add('project-mode');$('project-workspace').hidden=false;
  $('project-error').textContent='';$('project-status').textContent='';
  $('workspace-title').textContent='Modernization Projects';$('workspace-caption').textContent='Local static assessment';
  setNavigationOpen(false);setShellSection('btn-modernization');
}
function projectLeave() {
  projectSaveDraft();clearTimeout(projectUI.timer);projectUI.generation++;projectUI.view='legacy';projectUI.busy=false;
  document.body.classList.remove('project-mode');$('project-workspace').hidden=true;
  $('workspace-title').textContent=state.session.title || 'Welcome to FormsLang';
}
function projectSaveDraft() {
  if(projectUI.view!=='wizard'||!projectUI.draft)return;
  if(projectUI.draft.step===1){projectUI.draft.name=$('project-name').value;projectUI.draft.description=$('project-description').value;projectUI.draft.client_label=$('project-client').value;}
}
function newProject() {
  projectSaveDraft();projectEnter('wizard');projectUI.activeId=null;
  if(!projectUI.draft)projectUI.draft={step:1,name:'',description:'',client_label:'',sources:[],labels:{},preview:null};
  renderProjectWizard();
}
function projectButton(id,label,primary=false){return `<button type="button" class="btn ${primary?'primary':''}" id="${id}">${esc(label)}</button>`;}
function projectStats(inventory={}) {
  const f=inventory.forms||{},d=inventory.database||{};
  const counts=[['Forms candidates',f.discovered],['Forms XML supported',f.parseable],['Forms analyzed',f.analyzed],['FMB needing XML',f.fmb_without_xml],['Database packages',d.packages],['Tables',d.tables],['Views',d.views],['Source warnings',inventory.warnings]];
  return '<dl class="project-stats">'+counts.filter(([,n])=>Number.isInteger(n)).map(([label,n])=>`<div><dt>${esc(label)}</dt><dd>${n}</dd></div>`).join('')+'</dl>';
}
function projectSourceList(draft) {
  return draft.sources.map((s,i)=>`<li><b>${esc(s.kind)}</b> ${esc(draft.labels[s.root_id]||s.relative_path||s.area_id)} <button class="btn" data-project-remove="${i}" aria-label="Remove source ${i+1}">Remove</button></li>`).join('');
}
function renderProjectWizard() {
  const d=projectUI.draft,step=d.step,t=projectUI.areas?.target_profile;
  const fields=step===1?`<div class="project-fields"><label for="project-name">Project name (required)</label><input id="project-name" required maxlength="200" aria-describedby="project-error" value="${esc(d.name)}"><label for="project-description">Description (optional)</label><textarea id="project-description">${esc(d.description)}</textarea><label for="project-client">Organization / client (optional)</label><input id="project-client" value="${esc(d.client_label)}"></div>`:
    step===2?`<p>Select source folders. Discovery checks supported representations; binary files are not parsed directly.</p><div class="project-actions">${projectButton('project-forms','Choose Forms Folder')}${projectButton('project-database','Choose Database Folder')}${projectButton('project-supporting','Add Supporting Source')}</div><ul id="project-source-list">${projectSourceList(d)}</ul><div id="project-preview">${d.preview?projectStats(d.preview.inventory):'Select at least one source folder to discover its contents.'}</div>${projectButton('project-details','View discovery details')}`:
    step===3?`<dl><dt>Target platform</dt><dd>${esc(t?.platform||'Loading target profile…')}</dd><dt>Version</dt><dd>${esc(t?.version||'')}</dd><dt>Representation</dt><dd>${esc(t?.representation||'')}</dd></dl><p>Local static analysis. No database credentials or AI provider required.</p><details><summary>Advanced options</summary><p>Reference database: skipped. AI assistance: off for project analysis. Naming rules: engine defaults.</p><p>Connected validation and generation settings are outside this onboarding phase. Existing settings do not initiate external calls here.</p></details>`:
    `<h3>${esc(d.name)}</h3><ul>${d.sources.map(s=>`<li>${esc(s.kind)}: ${esc(d.labels[s.root_id]||s.relative_path||s.area_id)}</li>`).join('')}</ul><p>Target: ${esc(t?.platform||'')} ${esc(t?.version||'')} / ${esc(t?.representation||'')}</p><p>Mode: Local static analysis. Source code stays local.</p>${d.preview?projectStats(d.preview.inventory):''}`;
  $('project-content').innerHTML=`<ol class="project-steps">${projectSteps.map((name,i)=>`<li ${step===i+1?'aria-current="step"':''}>${i+1}. ${name}</li>`).join('')}</ol><h2 id="project-step-title" tabindex="-1">${step}. ${projectSteps[step-1]}</h2>${fields}<div class="project-actions">${step>1?projectButton('project-back','Back'):''}${projectButton('project-next',step===4?'Analyze Project':'Continue',true)}</div>`;
  $('project-next').onclick=()=>step===4?startProjectAnalysis():projectNext();
  if(step>1)$('project-back').onclick=()=>{projectSaveDraft();d.step--;renderProjectWizard();};
  if(step===2){
    for(const kind of ['forms','database','supporting'])$('project-'+kind).onclick=()=>projectPickSource(kind);
    $('project-details').onclick=()=>previewSources(0,true);
    $('project-content').querySelectorAll('[data-project-remove]').forEach(el=>el.onclick=()=>{d.sources.splice(Number(el.dataset.projectRemove),1);d.preview=null;renderProjectWizard();if(d.sources.length)previewSources();});
  }
  $('project-step-title').focus();
}
function projectNext() {
  projectSaveDraft();const d=projectUI.draft;$('project-error').textContent='';
  if(d.step===1 && (!d.name.trim()||d.name.trim().length>200)){projectError('Project name is required (maximum 200 characters).','project-name');return;}
  if(d.step===2 && !d.sources.length){projectError('Select at least one source folder.');return;}
  if(d.step===3 && !projectUI.areas?.target_profile){projectError('Target profile is unavailable. Retry source selection.');return;}
  d.step=Math.min(4,d.step+1);renderProjectWizard();
  if(d.step===3 && !projectUI.areas)projectLoadAreas();
}
async function projectLoadAreas() {
  const c=projectContext();
  try {const data=await api('/api/v2/source-areas');if(!projectCurrent(c))return;projectUI.areas=data;if(projectUI.view==='wizard')renderProjectWizard();return data;}
  catch(e){if(projectCurrent(c))projectError(e.message);}
}
async function previewSources(offset=0,details=false) {
  const c=projectContext(),request=++projectUI.previewRequest,sources=projectUI.draft?.sources.map(s=>({...s}));
  if(!sources?.length)return;
  $('project-status').textContent='Discovering source inventory…';
  try {
    const result=await api('/api/v2/discovery-preview',{sources,offset,limit:50});
    if(!projectCurrent(c)||request!==projectUI.previewRequest)return;
    projectUI.draft.preview=result;$('project-status').textContent='Source inventory ready. Deep analysis has not run yet.';
    $('project-preview').innerHTML=projectStats(result.inventory);
    if(details){
      $('project-preview').innerHTML+=`<table class="project-table"><thead><tr><th>Source</th><th>Representation</th><th>Status</th></tr></thead><tbody>${result.entries.map(e=>`<tr><td>${esc(e.candidate.relative_path)}</td><td>${esc(e.candidate.representation)}</td><td>${esc(e.support)}</td></tr>`).join('')}</tbody></table>`+projectDiagnostics(result.diagnostics)+`<p>${offset+1}–${Math.min(offset+50,result.total)} of ${result.total} candidates</p>`+(offset?projectButton('project-prev-files','Previous'): '')+(offset+50<result.total?projectButton('project-next-files','Next'): '');
      if(offset)$('project-prev-files').onclick=()=>previewSources(Math.max(0,offset-50),true);
      if(offset+50<result.total)$('project-next-files').onclick=()=>previewSources(offset+50,true);
    }
  }catch(e){if(projectCurrent(c)&&request===projectUI.previewRequest){$('project-status').textContent='';projectError(e.message+' Select another folder or retry discovery.');}}
}
function projectDiagnostics(items=[],conversion=false) {
  return items.length?'<ul class="project-diagnostics">'+items.map(d=>`<li><b>${esc(d.relative_path)}</b>: ${esc(d.safe_message)} <span>${esc(d.remediation)}</span>${conversion&&d.error_code==='FORMS2XML_REQUIRED'?`<button class="btn" data-project-convert="${esc(d.source_id)}">Convert with configured Forms2XML tool</button>`:''}</li>`).join('')+'</ul>':'';
}
function projectBindConversions(){
  $('project-content').querySelectorAll('[data-project-convert]').forEach(el=>el.onclick=()=>projectConvert(el.dataset.projectConvert));
}
function projectConvert(sourceId){
  const c=projectContext(),configuration=projectUI.summary.configuration_revision;
  openModal('Convert a staged copy with Oracle Forms2XML');foot(null);
  $('modal-body').innerHTML=`<div class="project-picker"><p>This explicit action invokes your installed Oracle Forms tooling on a temporary copy. The original FMB is not modified. No Oracle binaries are bundled.</p><p>If tooling is unavailable, provide an existing Forms2XML export. A conversion can take up to three minutes; closing this dialog does not stop the tool.</p>${projectButton('project-convert-confirm','Convert staged copy',true)}</div>`;
  $('project-convert-confirm').onclick=async()=>{
    if(!projectCurrent(c)||$('project-convert-confirm').disabled)return;
    $('project-convert-confirm').disabled=true;closeModal();$('project-status').textContent='Converting a staged copy with Oracle Forms2XML…';
    try{const result=await api(`/api/v2/projects/${c.id}/convert`,{source_id:sourceId,expected_configuration:configuration,confirmed:true});if(!projectCurrent(c))return;
      if(result.safe_failure){projectError(`${result.safe_failure.safe_message} ${result.safe_failure.remediation}`);$('project-status').textContent='Conversion did not complete.';}
      else await openProject(c.id);
    }catch(e){if(projectCurrent(c))projectError(e.message+' Reload Project to inspect the conversion job.');}
  };
}
async function showProjectHome() {
  projectSaveDraft();projectEnter('home');projectUI.activeId=null;const c=projectContext();
  $('project-content').innerHTML=`<h2 id="project-step-title" tabindex="-1">Oracle Forms → APEX Modernization</h2><p>Create a project, discover your sources, and run a local assessment.</p><div class="project-actions">${projectButton('project-new','New Project',true)}${projectButton('project-demo','Explore Demo Project')}${projectButton('project-open','Open Project')}</div><h3>Recent Projects</h3><div id="project-recents">Loading recent projects…</div>`;
  $('project-new').onclick=newProject;$('project-demo').onclick=projectDemo;$('project-open').onclick=projectOpenLocator;$('project-step-title').focus();
  try {const data=await api('/api/v2/projects');if(!projectCurrent(c))return;
    $('project-recents').innerHTML=data.projects.length?data.projects.map(row=>row.project?.name&&!row.warning?`<article class="project-recent"><button class="btn" data-project-open="${esc(row.project.id)}">${esc(row.project.name)}</button><p>${esc(row.project.target_platform)} ${esc(row.project.target_version)} · ${esc(row.analyzed_at||'Not analyzed')}</p>${projectStats(row.inventory)}</article>`:`<p>${esc(row.warning||'Project unavailable; open its relocated descriptor.')}</p>`).join(''):'No projects yet. Create a project or explore the synthetic demo.';
    $('project-recents').querySelectorAll('[data-project-open]').forEach(el=>el.onclick=()=>openProject(el.dataset.projectOpen));
  }catch(e){if(projectCurrent(c))projectError(e.message+' Retry Recent Projects.');}
}
async function openProject(id,check=true) {
  projectSaveDraft();projectEnter('summary');projectUI.activeId=id;const c=projectContext();
  $('project-content').innerHTML='<p>Opening saved project…</p>';
  try {
    const summary=await api('/api/v2/projects/'+id);if(!projectCurrent(c))return;
    projectUI.summary=summary;renderProjectSummary(summary);
    if(summary.last_job && ['QUEUED','RUNNING'].includes(summary.last_job.status)){projectUI.jobId=summary.last_job.job_id;projectUI.operation=summary.last_job.operation;if(projectUI.operation==='ANALYZE')renderProjectProgress(summary);await pollProjectJob();return;}
    if(summary.project.analysis_revision)await projectLoadOverview(c);
    if(!projectCurrent(c))return;
    if(check && summary.project.analysis_revision){
      $('project-status').textContent='Saved assessment loaded. Checking source freshness…';
      const job=await api(`/api/v2/projects/${id}/freshness`,{});if(!projectCurrent(c))return;
      projectUI.jobId=job.job_id;projectUI.operation='FRESHNESS';await pollProjectJob();
    }
    return projectCurrent(c)?c:undefined;
  }catch(e){if(projectCurrent(c))projectError(e.message+' Reload the project to retry.');}
}
async function projectLoadOverview(c=projectContext(),render=true) {
  try {
    const payload=await api(`/api/v2/projects/${c.id}/overview`);if(!projectCurrent(c))return;
    const data=payload?.overview||payload;
    if(data?.assessment&&data?.inventory){projectUI.overview=data;if(render)renderProjectOverview(data);return data;}
  }catch(e){if(projectCurrent(c))projectError(e.message+' The saved project remains available; retry Overview.');}
}
const projectRiskLabels={CRITICAL:'Critical',HIGH:'High',MEDIUM:'Medium',LOW:'Low',UNKNOWN:'Unknown'};
const projectRecommendationLabels={PRESERVE:'Preserve',CONVERT:'Convert',REPLACE_WITH_APEX_NATIVE:'Use Native APEX',REFACTOR:'Refactor',MOVE_TO_PLSQL_API:'Move to PL/SQL API',MANUAL_REVIEW:'Human Review',DROP:'Drop',UNKNOWN:'Unresolved'};
const projectInterventionLabels={AUTO:'Mechanical / AUTO',ASSISTED:'Assisted',MANUAL:'Human decision',UNKNOWN:'Unknown'};
function projectStatusLabel(value){return {CURRENT:'Current',STALE:'Stale',INCOMPLETE:'Incomplete',MISSING_SOURCE:'Missing Source',UNVERIFIED:'Unverified'}[String(value||'UNVERIFIED').toUpperCase()]||'Unverified';}
function projectSectionNav(active='overview') {
  const links=[['overview','Overview'],['inventory','Inventory'],['review','Review'],['blueprint','Blueprint'],['generate','Generate'],['reports','Reports'],['settings','Project Settings']];
  return `<nav class="project-section-nav" aria-label="Project sections">${links.map(([id,label])=>`<button type="button" class="btn" data-project-section="${id}" ${active===id?'aria-current="page"':''} ${['generate','reports'].includes(id)?'title="Planned for a later FormsLang 2.0 phase"':''}>${label}</button>`).join('')}</nav>`;
}
function projectBindSectionNav() {
  $('project-content').querySelectorAll('[data-project-section]').forEach(el=>el.onclick=()=>{
    const section=el.dataset.projectSection;
    if(section==='overview')renderProjectOverview(projectUI.overview);
    else if(section==='inventory')projectOpenInventory({category:'forms'});
    else if(section==='review')projectOpenPriorityReview();
    else if(section==='blueprint'){projectLeave();browse('');}
    else if(section==='settings')renderProjectSummary(projectUI.summary);
    else {$('project-status').textContent=`${section==='generate'?'Generation':'Reports'} is planned for a later FormsLang 2.0 phase.`;}
  });
}
const projectInventoryCategories={forms:'Forms',libraries:'Libraries',packages:'Packages',routines:'Routines',views:'Views',tables:'Tables',dependencies:'Dependencies',business_rules:'Business Rules',findings:'Findings'};
const projectInventoryColumns={
  forms:[['name','Module'],['module','Representation'],['dependencies','Dependencies'],['findings','Findings'],['highest_risk','Highest Risk'],['source_status','Source Status']],
  libraries:[['name','Library'],['representation','Representation'],['semantic_support','Semantic Support'],['source_status','Source Status']],
  packages:[['name','Package'],['spec','Spec'],['body','Body'],['subprograms','Subprograms'],['dependencies','Dependencies'],['findings','Findings'],['highest_risk','Highest Risk']],
  routines:[['name','Procedure / Function'],['module','Module'],['dependencies','Dependencies'],['findings','Findings'],['highest_risk','Highest Risk']],
  views:[['name','View'],['module','Source'],['dependencies','Dependencies'],['findings','Findings'],['highest_risk','Highest Risk']],
  tables:[['name','Table'],['columns','Columns'],['constraints','Constraints'],['dependencies','References'],['findings','Findings'],['highest_risk','Highest Risk']],
  dependencies:[['source','Source'],['relationship','Relationship'],['target','Target']],
  business_rules:[['name','Candidate'],['module','Module'],['candidate_kind','Observed As'],['risk','Risk'],['recommendation','Recommendation'],['intervention','Intervention']],
  findings:[['name','Finding'],['module','Module'],['risk','Risk'],['recommendation','Recommendation'],['intervention','Intervention'],['review_state','Review Status']],
};
function projectInventoryRevision(){return projectUI.overview?.assessment?.analysis_revision||projectUI.overview?.analysis_revision||null;}
function projectInventoryLabel(field,value) {
  if(value===null||value===undefined||value==='')return 'Not observed';
  if(field==='recommendation')return projectRecommendationLabels[value]||value;
  if(field==='risk')return projectRiskLabels[value]||value;
  if(field==='intervention')return projectInterventionLabels[value]||value;
  if(typeof value==='boolean')return value?'Available':'Not observed';
  return ['review_state','source_status','semantic_support','relationship','candidate_kind'].includes(field)?String(value).replaceAll('_',' '):String(value);
}
function projectInventoryUrl(state) {
  const params=new URLSearchParams({category:state.category,query:state.query||'',sort:state.sort||'name',offset:String(state.offset||0),limit:String(state.limit||50)});
  if(state.revision)params.set('revision',state.revision);
  for(const [key,value] of Object.entries(state.filters||{}))if(value)params.set(key,value);
  return `/api/v2/projects/${projectUI.activeId}/inventory?${params}`;
}
function projectInventoryTable(state,page) {
  const columns=projectInventoryColumns[state.category]||projectInventoryColumns.forms,label=projectInventoryCategories[state.category]||'Inventory',rows=page?.rows||[];
  const body=rows.length?rows.map(row=>`<tr>${columns.map(([field],index)=>`<td>${index===0?`<button type="button" class="project-inventory-item" data-project-item="${esc(row.id)}">${esc(projectInventoryLabel(field,row[field]))}</button>`:esc(projectInventoryLabel(field,row[field]))}</td>`).join('')}</tr>`).join(''):`<tr><td colspan="${columns.length}"><p class="project-empty">No observed ${esc(label)} match the current search and filters.</p></td></tr>`;
  return `<div class="project-table-wrap"><table class="project-table project-inventory-table"><caption>${esc(label)} from assessment revision ${esc(String(page?.analysis_revision||state.revision||'not loaded').slice(0,12))}</caption><thead><tr>${columns.map(([,heading])=>`<th scope="col">${esc(heading)}</th>`).join('')}</tr></thead><tbody>${body}</tbody></table></div><div class="project-pagination"><p>${page?.total?`${Number(page.offset)+1}–${Math.min(Number(page.offset)+Number(page.limit),Number(page.total))} of ${Number(page.total)}`:'No matching rows'}</p>${Number(page?.offset||0)>0?projectButton('project-inventory-prev','Previous'):''}${Number(page?.offset||0)+Number(page?.limit||50)<Number(page?.total||0)?projectButton('project-inventory-next','Next'):''}</div>`;
}
function projectRenderInventory(page=null,focusId='') {
  const state=projectUI.inventoryState,label=projectInventoryCategories[state.category];
  const risk=state.filters.risk||'',recommendation=state.filters.recommendation||'';
  const noDatabase=projectUI.overview?.source_coverage?.database?.sources===0;
  $('project-content').innerHTML=`${projectSectionNav('inventory')}<header><h2 id="project-step-title" tabindex="-1">Inventory</h2><p>Browse observed application structure and modernization findings from the saved assessment.</p></header>${noDatabase?'<p class="project-state-warning">No database source was supplied. Cross-layer recommendations may have limited evidence.</p>':''}<div class="project-inventory-tabs" role="tablist" aria-label="Inventory categories">${Object.entries(projectInventoryCategories).map(([key,name])=>`<button type="button" class="btn" role="tab" data-project-category="${key}" aria-selected="${state.category===key}">${esc(name)}</button>`).join('')}</div><form id="project-inventory-filters" class="project-filter-bar"><label for="project-inventory-search">Search inventory</label><input id="project-inventory-search" type="search" maxlength="500" value="${esc(state.query||'')}"><label for="project-inventory-risk">Risk</label><select id="project-inventory-risk"><option value="">Any risk</option>${Object.entries(projectRiskLabels).map(([key,name])=>`<option value="${key}" ${risk===key?'selected':''}>${esc(name)}</option>`).join('')}</select><label for="project-inventory-recommendation">Recommendation</label><select id="project-inventory-recommendation"><option value="">Any recommendation</option>${Object.entries(projectRecommendationLabels).map(([key,name])=>`<option value="${key}" ${recommendation===key?'selected':''}>${esc(name)}</option>`).join('')}</select>${projectButton('project-inventory-apply','Apply Filters',true)}${projectButton('project-inventory-clear','Clear')}</form><p id="project-inventory-status" role="status" aria-live="polite">${page?`${Number(page.total||0)} ${esc(label)} found.`:'Loading inventory…'}</p><div id="project-inventory-results">${projectInventoryTable(state,page)}</div>`;
  $('project-inventory-search').value=state.query||'';$('project-inventory-risk').value=risk;$('project-inventory-recommendation').value=recommendation;
  projectBindSectionNav();
  $('project-content').querySelectorAll('[data-project-category]').forEach(el=>{el.onclick=()=>projectOpenInventory({category:el.dataset.projectCategory});el.onkeydown=projectInventoryTabKey;});
  $('project-content').querySelectorAll('[data-project-item]').forEach(el=>el.onclick=()=>projectInventoryDetail(el.dataset.projectItem,el));
  $('project-inventory-filters').onsubmit=e=>{e.preventDefault();projectApplyInventoryFilters();};
  $('project-inventory-apply').onclick=projectApplyInventoryFilters;$('project-inventory-clear').onclick=()=>projectOpenInventory({category:state.category});
  if(page&&page.offset>0)$('project-inventory-prev').onclick=()=>projectInventoryPage(Math.max(0,page.offset-page.limit),'project-inventory-next');
  if(page&&page.offset+page.limit<page.total)$('project-inventory-next').onclick=()=>projectInventoryPage(page.offset+page.limit,'project-inventory-prev');
  if(focusId)$(focusId)?.focus();
}
function projectInventoryTabKey(event) {
  if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
  const tabs=Array.from($('project-content').querySelectorAll('[data-project-category]'));
  const current=tabs.indexOf(event.currentTarget);if(current<0||!tabs.length)return;
  event.preventDefault();
  const next=event.key==='Home'?0:event.key==='End'?tabs.length-1:(current+(event.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;
  tabs[next].focus();projectOpenInventory({category:tabs[next].dataset.projectCategory});
}
async function projectOpenInventory(options={}) {
  const initial={category:'forms',query:'',filters:{},sort:'name',offset:0,limit:50,revision:projectInventoryRevision(),request:0,selectedId:null,returnFocus:null};
  projectUI.inventoryState={...initial,...options,filters:{...(options.filters||{})}};
  if(options.priority)projectUI.inventoryState.filters.priority='unresolved';
  projectUI.view='inventory';projectRenderInventory();$('project-step-title').focus();
  return projectLoadInventory();
}
async function projectLoadInventory(resetOnConflict=true,focusId='') {
  const c=projectContext(),state=projectUI.inventoryState,request=++state.request;
  try {
    const page=await api(projectInventoryUrl(state));
    if(!projectCurrent(c)||projectUI.inventoryState!==state||request!==state.request)return;
    state.offset=Number(page.offset||0);state.limit=Number(page.limit||50);state.revision=page.analysis_revision;state.page=page;
    projectRenderInventory(page,focusId);$('project-status').textContent='';
    return page;
  }catch(e){
    if(!projectCurrent(c)||projectUI.inventoryState!==state||request!==state.request)return;
    const conflict=e.status===409||e.code==='PROJECT_CONFLICT'||/assessment changed|revision/i.test(e.message||'');
    if(conflict&&resetOnConflict){
      const refreshed=await projectLoadOverview(c,false);if(!refreshed||!projectCurrent(c)||projectUI.inventoryState!==state)return;
      state.offset=0;state.revision=projectInventoryRevision();state.page=null;projectUI.view='inventory';projectRenderInventory();
      await projectLoadInventory(false,focusId);if(projectCurrent(c)&&projectUI.inventoryState===state)$('project-status').textContent='The assessment changed. Overview and Inventory were reloaded from the first page.';return;
    }
    projectError((e.message||'Inventory could not be loaded')+' Retry Inventory.');
  }
}
function projectApplyInventoryFilters() {
  const state=projectUI.inventoryState,priority=state.filters.priority;state.query=$('project-inventory-search').value.trim();state.filters={};
  if(priority)state.filters.priority=priority;
  if($('project-inventory-risk').value)state.filters.risk=$('project-inventory-risk').value;
  if($('project-inventory-recommendation').value)state.filters.recommendation=$('project-inventory-recommendation').value;
  state.offset=0;state.page=null;projectRenderInventory();return projectLoadInventory(true,'project-inventory-search');
}
function projectInventoryPage(offset,focusId='') {const state=projectUI.inventoryState;state.offset=Math.max(0,Number(offset)||0);return projectLoadInventory(true,focusId);}
async function projectOpenPriorityReview() {
  const findingId=projectUI.overview?.priority?.first_finding_id||null;
  projectUI.reviewContext={project_id:projectUI.activeId,finding_id:findingId,filters:{priority:'unresolved'},analysis_revision:projectInventoryRevision()};
  const page=await projectOpenInventory({category:'findings',priority:true});
  if(findingId&&page?.rows?.some(row=>row.id===findingId))await projectInventoryDetail(findingId);
  return page;
}
function projectDetailList(items,kind) {
  if(!items?.length)return '<p class="project-empty">No observed '+esc(kind)+'.</p>';
  return `<ul>${items.map(row=>`<li><b>${esc(row.name||row.source||row.id||'Observed item')}</b>${row.relationship?` ${esc(row.relationship)} ${esc(row.target)}`:''}${row.risk?` · ${esc(projectRiskLabels[row.risk]||row.risk)}`:''}${row.reason?`<span>${esc(row.reason)}</span>`:''}</li>`).join('')}</ul>`;
}
async function projectInventoryDetail(itemId,trigger=null) {
  const c=projectContext(),state=projectUI.inventoryState,category=state.category,revision=state.revision;state.selectedId=itemId;state.returnFocus=trigger;
  try {
    const detail=await api(`/api/v2/projects/${c.id}/inventory/${encodeURIComponent(category)}/${encodeURIComponent(itemId)}?revision=${encodeURIComponent(revision||'')}`);
    if(!projectCurrent(c)||projectUI.inventoryState!==state||state.selectedId!==itemId)return;
    openModal('Inventory detail');foot(null);
    const item=detail.item||{};
    const relationship=item.relationship?`<dt>Observed relationship</dt><dd>${esc(item.source||'Unknown source')} ${esc(projectInventoryLabel('relationship',item.relationship))} ${esc(item.target||'Unknown target')}</dd>`:'';
    $('modal-body').innerHTML=`<article class="project-inventory-detail"><h3>${esc(item.name||item.id||'Observed item')}</h3><dl><dt>Identity</dt><dd>${esc(item.id||'Not observed')}</dd><dt>Type</dt><dd>${esc(item.type||item.source_type||'Not observed')}</dd><dt>Source status</dt><dd>${esc(item.source_status||'Not observed')}</dd><dt>Risk</dt><dd>${esc(projectRiskLabels[item.risk||item.highest_risk]||item.risk||item.highest_risk||'Unknown')}</dd><dt>Recommendation</dt><dd>${esc(projectRecommendationLabels[item.recommendation]||item.recommendation||'Not observed')}</dd>${relationship}</dl><h4>Dependencies (${Number(detail.dependencies_total||0)})</h4>${projectDetailList(detail.dependencies,'dependencies')}<h4>Related findings (${Number(detail.related_findings_total||0)})</h4>${projectDetailList(detail.related_findings,'related findings')}${projectButton('project-detail-close','Back to Inventory')}</article>`;
    $('project-detail-close').onclick=projectCloseInventoryDetail;
  }catch(e){if(projectCurrent(c)&&projectUI.inventoryState===state)projectError(e.message+' Retry the inventory detail.');}
}
function projectCloseInventoryDetail(){const target=projectUI.inventoryState?.returnFocus;closeModal();projectUI.inventoryState.selectedId=null;if(target?.focus)target.focus();}
function projectDistribution(title,values,labels,kind) {
  const entries=Object.entries(labels);
  return `<section class="project-panel" aria-label="${esc(title)} distribution"><h3>${esc(title)}</h3><dl class="project-distribution">${entries.map(([key,label])=>`<div><dt><button type="button" class="project-metric-link" data-project-filter="${esc(kind)}" data-project-value="${esc(key)}">${esc(label)}</button></dt><dd>${Number(values?.[key]||0)}</dd></div>`).join('')}</dl></section>`;
}
function projectInventorySummary(values={}) {
  const rows=[['Forms Modules',values.forms_modules],['PL/SQL Libraries',values.libraries],['Database Packages',values.database_packages],['Views',values.views],['Tables',values.tables],['Triggers',values.triggers],['Program Units',values.program_units],['Dependencies',values.dependencies],['Modernization Findings',values.modernization_findings]];
  return `<section class="project-panel project-panel-wide"><h3>Application Inventory</h3><dl class="project-overview-inventory">${rows.map(([label,count])=>`<div><dt>${esc(label)}</dt><dd>${Number(count||0)}</dd></div>`).join('')}</dl></section>`;
}
function projectCoverage(coverage={}) {
  const forms=coverage.forms||{},database=coverage.database||{},libraries=coverage.libraries||{};
  const amount=(value)=>Number.isInteger(value)?value:'Not observed';
  return `<section class="project-panel"><h3>Source Coverage</h3><dl class="project-coverage"><div><dt>Forms representations</dt><dd>${amount(forms.analyzed)} / ${amount(forms.discovered)} analyzed${Number.isInteger(forms.parseable)?` · ${forms.parseable} parseable`:''}</dd></div><div><dt>Database sources</dt><dd>${amount(database.analyzed)} analyzed${Number.isInteger(database.sources)?` from ${database.sources} supplied sources`:''}</dd></div><div><dt>Libraries</dt><dd>${amount(libraries.discovered)} discovered · ${amount(libraries.without_semantic_representation)} without semantic representation</dd></div></dl></section>`;
}
function projectOverviewWarnings(items=[],summary={}) {
  if(!items.length)return '<p class="project-empty">No analysis limitations were recorded for this assessment.</p>';
  const bounded=summary.truncated?`<p class="project-muted">Showing ${Number(summary.shown||items.length)} of ${Number(summary.total||items.length)} warnings. Open Inventory diagnostics for the complete list.</p>`:'';
  return `<ul class="project-warnings">${items.map(item=>`<li><b>${esc(item.message||item.code||'Assessment warning')}</b>${item.remediation?`<span>${esc(item.remediation)}</span>`:''}</li>`).join('')}</ul>${bounded}`;
}
function renderProjectOverview(data) {
  if(!data)return;projectUI.view='overview';projectUI.overview=data;
  $('project-status').setAttribute('aria-live','polite');
  const p=data.project||{},assessment=data.assessment||{},target=p.target||{},freshness=assessment.freshness||data.freshness?.status||'UNVERIFIED';
  const state=projectStatusLabel(freshness),priority=data.priority||{},coverage=data.source_coverage||{},review=data.review_progress||{};
  const timestamp=assessment.assessment_timestamp||data.assessment_timestamp||'Not analyzed';
  const critical=Number(priority.critical||0);
  const stateMessage=state==='Stale'?'Source changed since this assessment. Saved metrics remain visible; refresh analysis before treating them as current.':state==='Missing Source'?'A source folder cannot be found. Relink it or continue viewing the saved assessment.':state==='Incomplete'?'This assessment is incomplete. Review source warnings and failed inputs.':state==='Unverified'?'Source freshness has not been verified.':'';
  $('workspace-title').textContent=p.name||projectUI.summary?.project?.name||'Modernization Project';
  $('project-content').innerHTML=`${projectSectionNav('overview')}<header class="project-overview-header"><div><h2 id="project-step-title" tabindex="-1">${esc(p.name||'Modernization Project')}</h2><p>${esc(target.platform||'Oracle APEX')} ${esc(target.version||'')} / ${esc(target.representation||'')}</p></div><p class="project-assessment-state"><span>Assessment status</span><b data-status="${esc(String(freshness).toUpperCase())}">${esc(state)}</b></p></header>${stateMessage?`<aside class="project-state-warning" role="status"><p>${esc(stateMessage)}</p><div class="project-actions">${projectButton('project-refresh','Refresh Analysis',true)}${state==='Missing Source'?projectButton('project-relink-missing','Relink Source'):''}</div></aside>`:''}<div class="project-overview-grid">${projectInventorySummary(data.inventory)}${projectDistribution('Risk',data.risk_distribution,projectRiskLabels,'risk')}${projectDistribution('Recommended Direction',data.recommendation_distribution,projectRecommendationLabels,'recommendation')}${projectDistribution('Intervention',data.intervention_distribution,projectInterventionLabels,'intervention')}<section class="project-panel" id="project-priority"><h3>Priority Review</h3>${critical?`<p><b>${critical}</b> Critical · <b>${Number(priority.high||0)}</b> High · <b>${Number(priority.manual||0)}</b> Human Decisions</p>`:'<p class="project-empty">No unresolved CRITICAL findings in the current assessment.</p>'}<p>${Number(priority.total||0)} unresolved findings ordered by transparent evidence factors.</p>${projectButton('project-start-priority','Start Priority Review',true)}</section><section class="project-panel"><h3>Automation Potential</h3><dl class="project-distribution">${Object.entries(projectInterventionLabels).map(([key,label])=>`<div><dt>${esc(label)}</dt><dd>${Number(data.automation_potential?.[key]?.percent??data.automation_potential?.categories?.[key]?.percent??0)}%</dd></div>`).join('')}</dl><p class="project-muted">Based on modernization decision categories, not effort or project-duration estimation. AUTO does not mean generation-ready.</p></section>${projectCoverage(coverage)}<section class="project-panel"><h3>Assessment Warnings</h3>${projectOverviewWarnings(data.warnings,data.warning_summary)}</section><section class="project-panel project-panel-wide"><h3>Assessment Record</h3><p>Assessed ${esc(timestamp)} · Analysis revision ${esc(String(assessment.analysis_revision||data.analysis_revision||'Unavailable').slice(0,12))}</p><p>Reviewed ${Number(review.reviewed||0)} / ${Number(review.total||0)} findings. Generation and validation readiness are not assessed in Phase C.</p></section></div>`;
  projectBindSectionNav();
  $('project-content').querySelectorAll('[data-project-filter]').forEach(el=>el.onclick=()=>projectOpenInventory({category:'findings',filters:{[el.dataset.projectFilter]:el.dataset.projectValue}}));
  $('project-start-priority').onclick=projectOpenPriorityReview;
  if(stateMessage)$('project-refresh').onclick=startProjectAnalysis;
  if(state==='Missing Source')$('project-relink-missing').onclick=()=>renderProjectSummary(projectUI.summary);
  $('project-step-title').focus();
}
function renderProjectSummary(data) {
  const p=data.project,f=data.freshness||{status:'UNVERIFIED'};projectUI.summary=data;
  $('workspace-title').textContent=p.name;
  const warning=f.status==='STALE'?'Source or engine changed since this assessment. Refresh Analysis or view saved evidence.':f.status==='MISSING_SOURCE'?'A source folder or file cannot be found. Relink its root or view saved evidence.':f.status==='INCOMPLETE'?'Assessment is incomplete. Review source warnings before relying on coverage.':f.status==='UNVERIFIED'?'Source freshness has not been verified.':'';
  $('project-content').innerHTML=`<h2 id="project-step-title" tabindex="-1">${esc(p.name)}</h2><p>${esc(p.target_platform)} ${esc(p.target_version)} / ${esc(p.target_representation)}</p><p>Source status: <b>${esc(f.status)}</b></p><p>${esc(warning)}</p><p>Last analyzed: ${esc(data.analyzed_at||'Not analyzed')}</p>${projectStats(data.inventory)}<div class="project-actions">${projectButton('project-analyze',p.analysis_revision?'Refresh Analysis':'Analyze Project',true)}${p.analysis_revision?projectButton('project-saved','View Saved Assessment'):''}${projectButton('project-reload','Reload Project')}</div><h3>Source folders</h3><ul>${p.source_roots.map(r=>`<li>${esc(r.kind)}: ${esc(r.path||r.id)} <button class="btn" data-project-relink="${esc(r.id)}">Relink</button></li>`).join('')}</ul><div id="project-saved-content"></div><p class="project-muted">Project summary. The full Overview experience follows in Phase C.</p>`;
  $('project-analyze').onclick=startProjectAnalysis;$('project-reload').onclick=()=>openProject(p.id);
  if(data.last_job?.safe_failure){
    const failure=data.last_job.safe_failure;
    $('project-content').insertAdjacentHTML('beforeend',`<p>Last operation: ${esc(failure.safe_message)} ${esc(failure.remediation)}</p>`);
  }
  if(p.analysis_revision)$('project-saved').onclick=projectViewSaved;
  $('project-content').querySelectorAll('[data-project-relink]').forEach(el=>el.onclick=()=>relinkProjectRoot(el.dataset.projectRelink));
}
async function projectViewSaved() {
  const c=projectContext();
  try {const data=await api(`/api/v2/projects/${c.id}/assessment`);if(!projectCurrent(c))return;
    const a=data.assessment;
    if(!a){$('project-saved-content').textContent='No assessment has been committed yet.';return;}
    const diagnostics=a.diagnostics||[];
    const render=offset=>{
      if(!projectCurrent(c))return;
      $('project-saved-content').innerHTML=`<h3>Saved assessment</h3><p>Completion: ${esc(a.completion_state||a.status)} · Assessed ${esc(a.analyzed_at)}</p>${projectStats(a.inventory)}<p>Findings: ${a.blueprint.findings.length}</p>${projectDiagnostics(diagnostics.slice(offset,offset+50),true)}`+(offset?projectButton('project-earlier-diagnostics','Previous warnings'):'')+(offset+50<diagnostics.length?projectButton('project-more-diagnostics','More warnings'):'');
      if(offset)$('project-earlier-diagnostics').onclick=()=>render(Math.max(0,offset-50));
      if(offset+50<diagnostics.length)$('project-more-diagnostics').onclick=()=>render(offset+50);
      projectBindConversions();
    };
    render(0);
  }catch(e){if(projectCurrent(c))projectError(e.message);}
}
async function startProjectAnalysis() {
  if(projectUI.busy)return;
  const draft=projectUI.draft;
  if(projectUI.view==='wizard' && (!draft?.name.trim()||!draft.sources.length||draft.step!==4)){projectError('Complete project details and source selection before analysis.');return;}
  const origin=projectUI.view,c=projectContext();projectUI.busy=true;$('project-error').textContent='';
  const startButton=origin==='wizard'?$('project-next'):$('project-analyze')||$('project-refresh');if(startButton)startButton.disabled=true;
  try {
    let summary=projectUI.summary;
    if(projectUI.view==='wizard'){
      summary=await api('/api/v2/projects',{name:draft.name.trim(),description:draft.description,client_label:draft.client_label,sources:draft.sources.map(s=>({...s}))});
      if(!projectCurrent(c))return;
      projectUI.activeId=summary.project.id;c.id=summary.project.id;projectUI.draft=null;
    }
    projectUI.summary=summary;
    const job=await api(`/api/v2/projects/${c.id}/analyze`,{expected_revision:summary.project.analysis_revision,expected_configuration:summary.configuration_revision});
    if(!projectCurrent(c))return;
    projectUI.jobId=job.job_id;projectUI.operation='ANALYZE';projectUI.busy=false;
    renderProjectProgress(summary);await pollProjectJob();
  }catch(e){if(projectCurrent(c)){projectUI.busy=false;projectError(e.message+' Reload Project before retrying if its revision changed.');if(projectUI.activeId){if(origin==='overview'&&projectUI.overview)renderProjectOverview(projectUI.overview);else{projectUI.view='summary';renderProjectSummary(projectUI.summary);}}else if($('project-next'))$('project-next').disabled=false;}}
}
function renderProjectProgress(summary){
  projectUI.view='progress';
  $('project-content').innerHTML=`<h2 id="project-step-title" tabindex="-1">Analyzing ${esc(summary.project.name)}</h2><p>Source code stays local. No AI or database connection is used.</p><div id="project-progress" role="progressbar" aria-label="Analysis progress"></div><p id="project-elapsed"></p><div id="project-run-inventory"></div><div id="project-run-errors"></div>${projectButton('project-cancel','Cancel Analysis')}`;
  $('project-cancel').onclick=projectCancel;$('project-step-title').focus();
}
async function pollProjectJob() {
  const c=projectContext(),jobId=projectUI.jobId;if(!jobId)return;
  try {
    const job=await api(`/api/v2/projects/${c.id}/jobs/${jobId}`);
    if(!projectCurrent(c)||projectUI.jobId!==jobId)return;
    const running=['QUEUED','RUNNING'].includes(job.status);
    $('project-status').textContent=`${job.phase||job.operation}: ${job.processed||0}${job.total!=null?' / '+job.total:''} · Warnings: ${job.warnings_count||0} · ${job.status}`;
    if(projectUI.view==='progress'){
      const progress=$('project-progress');progress.textContent=job.phase||job.status;
      if(job.total>0){progress.setAttribute('aria-valuemax',job.total);progress.setAttribute('aria-valuenow',job.processed||0);}else{progress.removeAttribute('aria-valuemax');progress.removeAttribute('aria-valuenow');}
      $('project-elapsed').textContent=`Elapsed: ${Math.floor((job.elapsed_ms||0)/1000)} seconds`;
      if(job.inventory)$('project-run-inventory').innerHTML=projectStats(job.inventory);
      $('project-run-errors').innerHTML=projectDiagnostics(job.diagnostics||[]);
    }
    if(running){projectUI.timer=setTimeout(pollProjectJob,600);return;}
    projectUI.jobId=null;
    const summary=await api(`/api/v2/projects/${c.id}`);if(!projectCurrent(c))return;
    projectUI.view='summary';renderProjectSummary(summary);
    $('project-status').textContent=job.status==='CANCELLED'?'Analysis cancelled. The last committed assessment is preserved.':job.status==='FAILED'?'Analysis failed. The last committed assessment is preserved.':projectUI.operation==='FRESHNESS'?'Source freshness checked.':'Assessment created and saved.';
    if(job.safe_failure)projectError(`${job.safe_failure.safe_message} ${job.safe_failure.remediation}`);
    $('project-saved-content').innerHTML=projectDiagnostics(job.diagnostics||[],true);projectBindConversions();
    if(projectUI.operation==='FRESHNESS'&&summary.project.analysis_revision&&['COMPLETED','COMPLETED_WITH_WARNINGS'].includes(job.status)){
      await projectLoadOverview(c);if(projectCurrent(c))$('project-status').textContent='Source freshness checked.';
    }
    if(projectUI.operation==='ANALYZE'&&['COMPLETED','COMPLETED_WITH_WARNINGS'].includes(job.status))await openProject(c.id);
  }catch(e){if(projectCurrent(c)){projectError(e.message+' Reload Project to reconnect to its durable job.');projectUI.busy=false;}}
}
async function projectCancel() {
  const c=projectContext(),job=projectUI.jobId;if(!job)return;
  $('project-cancel').disabled=true;
  try {await api(`/api/v2/projects/${c.id}/jobs/${job}/cancel`,{});if(projectCurrent(c)&&projectUI.jobId===job)$('project-status').textContent='Cancellation requested. Waiting for the current safe boundary…';}
  catch(e){if(projectCurrent(c)){projectError(e.message);$('project-cancel').disabled=false;}}
}
function projectSourceSelection(area,kind,relative) {
  return {area_id:area,root_id:crypto.randomUUID().replaceAll('-',''),kind,relative_path:relative};
}
async function projectPickSource(kind,onSelect) {
  const c=projectContext(),request=(projectUI.pickerRequest||0)+1;projectUI.pickerRequest=request;
  let generation=modalGeneration;
  const current=()=>projectCurrent(c)&&request===projectUI.pickerRequest&&generation===modalGeneration;
  try {
    const areas=await api('/api/v2/source-areas');if(!current())return;projectUI.areas=areas;
    openModal(onSelect?'Relink source folder':'Choose '+kind+' source folder');foot(null);
    generation=modalGeneration;
    $('modal-body').innerHTML=`<div class="project-picker">${areas.local?'<label for="project-folder-path">Local folder path</label><input id="project-folder-path" aria-describedby="project-picker-error">'+projectButton('project-folder-browse','Browse Folder'):''}<p id="project-picker-error" role="alert"></p><div id="project-area-list"></div><div id="project-folder-list"></div></div>`;
    const choose=async(selection,label)=>{if(!current())return;closeModal();if(onSelect){await onSelect(selection);return;}projectUI.draft.sources.push(selection);projectUI.draft.labels[selection.root_id]=label;projectUI.draft.preview=null;renderProjectWizard();await previewSources();};
    const browseArea=async(area,relative='',label='')=>{
      try{const data=await api(`/api/v2/source-areas/${area}/browse?relative=${encodeURIComponent(relative)}`);if(!current())return;
        $('project-folder-list').innerHTML=`<p>${esc(label||area)}${relative?' / '+esc(relative):''}</p>${projectButton('project-folder-select','Use This Folder',true)}${relative?projectButton('project-folder-up','Parent Folder'):''}<ul>${data.directories.map((n,i)=>`<li><button class="btn" data-project-folder="${i}">${esc(n)}</button></li>`).join('')}</ul>${data.truncated?'<p>Folder listing limited. Enter a more specific path or choose a subfolder.</p>':''}`;
        $('project-folder-select').onclick=()=>choose(projectSourceSelection(area,kind,relative),(label||area)+(relative?'/'+relative:''));
        if(relative)$('project-folder-up').onclick=()=>browseArea(area,relative.split('/').slice(0,-1).join('/'),label);
        $('project-folder-list').querySelectorAll('[data-project-folder]').forEach(el=>el.onclick=()=>browseArea(area,[relative,data.directories[Number(el.dataset.projectFolder)]].filter(Boolean).join('/'),label));
      }catch(e){if(current())$('project-picker-error').textContent=e.message;}
    };
    $('project-area-list').innerHTML=areas.areas.map((a,i)=>`<button class="btn" data-project-area="${i}">${esc(a.name)}</button>`).join('')||(!areas.local?'No authorized source areas. Ask the host administrator to configure source areas for your organization.':'');
    $('project-area-list').querySelectorAll('[data-project-area]').forEach(el=>el.onclick=()=>{const a=areas.areas[Number(el.dataset.projectArea)];browseArea(a.id,'',a.name);});
    if(areas.local){$('project-folder-path').value=areas.browse_root||'';$('project-folder-browse').onclick=async()=>{try{const path=$('project-folder-path').value.trim();const result=await api('/api/v2/source-selections',{path,kind});if(current())await browseArea(result.selection.area_id,'',path);}catch(e){if(current())$('project-picker-error').textContent=e.message;}};$('project-folder-path').focus();}
  }catch(e){if(current())projectError(e.message);}
}
async function relinkProjectRoot(rootId) {
  const c=projectContext(),summary=projectUI.summary,root=summary.project.source_roots.find(r=>r.id===rootId);
  await projectPickSource(root.kind,async(selection)=>{
    try{await api(`/api/v2/projects/${c.id}/relink`,{root_id:rootId,selection,expected_configuration:summary.configuration_revision});if(projectCurrent(c))await openProject(c.id);}
    catch(e){if(projectCurrent(c))projectError(e.message+' Reload Project before retrying.');}
  });
}
function projectOpenLocator() {
  const c=projectContext();openModal('Open modernization project');$('modal-body').innerHTML='<p>Select an existing .formslang/project.json. Its source paths do not grant access; relink sources if needed.</p>';
  foot({placeholder:'Full path to .formslang/project.json',button:'Open Project',run:async(locator)=>{try{const result=await api('/api/v2/projects/open',{locator});if(projectCurrent(c)){closeModal();await openProject(result.project.id);}}catch(e){if(projectCurrent(c))projectError(e.message);}}});
}
async function projectDemo() {
  const c=projectContext();if(projectUI.busy)return;projectUI.busy=true;$('project-demo').disabled=true;
  try{const result=await api('/api/v2/projects/demo',{});if(projectCurrent(c)){projectUI.busy=false;const opened=await openProject(result.project.id,false);if(opened&&projectCurrent(opened))await startProjectAnalysis();}}
  catch(e){if(projectCurrent(c)){projectUI.busy=false;$('project-demo').disabled=false;projectError(e.message);}}
}
function initProjects(){
  $('project-home').onclick=showProjectHome;$('project-resume').onclick=newProject;
  $('project-legacy').onclick=()=>{projectLeave();browse('');};$('btn-modernization').onclick=showProjectHome;
  if(!state.session.title&&!state.tasks.length)showProjectHome();
}
'''
