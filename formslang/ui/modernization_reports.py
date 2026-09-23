"""Explicit, snapshot-bound delivery downloads in the existing Workbench."""

REPORTS_PROJECT_JS = r"""
function projectReportsCurrent(c,s){return projectCurrent(c)&&projectUI.view==='reports'&&projectUI.reportsState===s;}
async function projectReportsOpen(){
  projectUI.view='reports';const c=projectContext(),s={busy:false};projectUI.reportsState=s;
  $('project-content').innerHTML=projectSectionNav('reports')+'<h2 id="project-reports-title" tabindex="-1">Assessment reports and delivery</h2><p id="project-reports-status" role="status">Loading saved snapshot…</p><div id="project-reports-body"></div>';projectBindSectionNav();$('project-reports-title').focus();
  try{await projectUI.opening;if(!projectReportsCurrent(c,s))return;await projectUI.openingJob;if(!projectReportsCurrent(c,s))return;const d=await api(`/api/v2/projects/${c.id}/reports`);if(!projectReportsCurrent(c,s))return;s.data=d;
    $('project-reports-status').textContent='Saved assessment: '+projectStatusLabel(d.freshness);
    const names={executive:'Executive Modernization Assessment',technical:'Technical Modernization Assessment',risk:'Risk Report','dossier-md':'Assessment Dossier (Markdown)','investigation-md':'Suggested Investigation Groups (Markdown)','investigation-json':'Suggested Investigation Groups (JSON)','decision-records-md':'Decision Records: recorded and PROPOSED (Markdown)','backlog-csv':'Findings Backlog CSV','backlog-json':'Findings Backlog JSON',decisions:'Decision History JSON',package:'Complete Assessment Package'};
    $('project-reports-body').innerHTML=`<p>Self-contained deliverables from persisted evidence. Export does not run analysis, generate code, connect to a database or send data to AI.</p><p>Stale or incomplete assessments remain explicitly labelled. Validation is not runtime equivalence.</p><fieldset><legend>Optional sensitive content</legend><label><input type="checkbox" id="reports-include-notes"> Include human rationale and annotations in decision/backlog exports (never in executive HTML)</label><label><input type="checkbox" id="reports-include-artifacts"> Include verified generated artifacts (APEXlang or the target-neutral assessment package) in the complete package. APEXlang may contain business logic.</label></fieldset><table><thead><tr><th scope="col">Deliverable</th><th scope="col">File</th><th scope="col">Action</th></tr></thead><tbody>${d.formats.map(f=>`<tr><td>${esc(names[f.id]||f.id)}</td><td>${esc(f.filename)}</td><td><button type="button" class="btn" data-report-download="${esc(f.id)}" aria-label="Download ${esc(names[f.id]||f.id)}">Download</button></td></tr>`).join('')}</tbody></table><p>Package manifest records revisions, hashes, exclusions and validation evidence. Unsupported or changed artifacts are disclosed, not regenerated.</p>`;
    $('project-reports-body').insertAdjacentHTML('afterbegin','<p class="project-state-warning">Default exports retain technical identifiers and are not anonymous. Review before sharing.</p>');
    $('project-reports-body').querySelectorAll('[data-report-download]').forEach(el=>el.onclick=()=>projectReportsDownload(el.dataset.reportDownload));
  }catch(e){if(projectReportsCurrent(c,s))$('project-reports-status').textContent=e.message;}
}
async function projectReportsDownload(kind){
  const c=projectContext(),s=projectUI.reportsState;if(s.busy)return;const format=s.data.formats.find(f=>f.id===kind);if(!format)return;
  s.busy=true;$('project-reports-status').textContent='Preparing the saved assessment snapshot…';
  const buttons=$('project-reports-body').querySelectorAll('[data-report-download]');buttons.forEach(b=>b.disabled=true);
  const query=new URLSearchParams({...s.data.binding,include_notes:$('reports-include-notes').checked?'1':'0',include_artifacts:$('reports-include-artifacts').checked?'1':'0'});
  try{const response=await fetch(`/api/v2/projects/${encodeURIComponent(c.id)}/reports/${encodeURIComponent(kind)}?${query}`,{credentials:'same-origin'});
    if(!response.ok){const detail=await response.json();const e=new Error(detail.error||'Report export failed.');e.status=response.status;throw e;}
    const blob=await response.blob();if(!projectReportsCurrent(c,s))return;
    const disposition=response.headers.get('Content-Disposition')||'',filename=/filename="([a-zA-Z0-9._-]+)"/.exec(disposition);
    const url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download=filename?filename[1]:format.filename;document.body.appendChild(link);link.click();link.remove();URL.revokeObjectURL(url);
    $('project-reports-status').textContent='Download prepared from the saved snapshot. Check the manifest and disclosed exclusions before delivery.';
  }catch(e){if(projectReportsCurrent(c,s))$('project-reports-status').textContent=e.status===409?'Evidence changed. Reload Reports and inspect the current snapshot before downloading again.':e.message;}
  finally{s.busy=false;if(projectReportsCurrent(c,s))buttons.forEach(b=>b.disabled=false);}
}
"""
