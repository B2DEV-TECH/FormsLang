// Real Reports controls and downloads; no intercepted requests or substituted data.
import fs from 'node:fs/promises';
import path from 'node:path';
export async function reportChecks({evaluate,click,clickSelector,wait,check,screenshot,send,root}){
  const downloads=path.join(root,'report-downloads');await fs.mkdir(downloads);
  await send('Browser.setDownloadBehavior',{behavior:'allow',downloadPath:downloads});
  await clickSelector('[data-project-section="reports"]');
  await wait(()=>evaluate(`!!projectUI.reportsState?.data`),'report snapshot');
  const binding=await evaluate('projectUI.reportsState.data.binding'),project=await evaluate('projectUI.activeId');
  check('F disclosure defaults are off',await evaluate(`!document.getElementById('reports-include-notes').checked&&!document.getElementById('reports-include-artifacts').checked`));
  check('G technical identifier disclosure is visible',await evaluate(`document.getElementById('project-reports-body').textContent.includes('not anonymous')`));
  check('F report heading focus and live status',await evaluate(`document.activeElement.id==='project-reports-title'&&document.getElementById('project-reports-status').getAttribute('role')==='status'`));
  async function download(kind,filename){
    await clickSelector(`[data-report-download="${kind}"]`);
    let data;await wait(async()=>{try{data=await fs.readFile(path.join(downloads,filename));return data.length>0&&!((await fs.readdir(downloads)).some(n=>n.endsWith('.crdownload')));}catch{return false;}},filename);
    await wait(()=>evaluate(`!projectUI.reportsState.busy`),'download control restored');return data;
  }
  const executive=await download('executive','executive-summary.html');
  check('F executive is standalone safe HTML',executive.includes('Executive Summary')&&executive.includes(binding.analysis_revision)&&!executive.includes('<script'));
  const technical=await download('technical','technical-assessment.html');
  check('F technical includes inventory and limitations',technical.includes('Application Inventory')&&technical.includes('Known Limitations'));
  await click('reports-include-notes');
  const decisions=JSON.parse(await download('decisions','decisions-sensitive.json'));
  check('F sensitive decision export has provenance',decisions.metadata.human_notes_included&&decisions.metadata.snapshot_revision===binding.snapshot_revision&&decisions.rows.length>0);
  await click('reports-include-notes');await click('reports-include-artifacts');
  const archive=await download('package','modernization-package.zip');
  check('F modernization ZIP downloaded from real service',archive[0]===0x50&&archive[1]===0x4b&&archive.length>1000);
  await screenshot('reports-delivery.png');
  await click('project-home');await wait(()=>evaluate(`!!document.querySelector('[data-project-open="${project}"]')`),'delivery recent project');
  await clickSelector(`[data-project-open="${project}"]`);await wait(()=>evaluate(`projectUI.view==='overview'&&!projectUI.jobId&&document.getElementById('project-status').textContent==='Source freshness checked.'`),'delivery reopen');
  await clickSelector('[data-project-section="reports"]');await wait(()=>evaluate(`!!projectUI.reportsState?.data`),'reopened reports');
  check('F reports reopen the same persisted snapshot',await evaluate('projectUI.reportsState.data.binding.snapshot_revision')===binding.snapshot_revision);
}
