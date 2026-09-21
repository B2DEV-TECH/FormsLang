// Real UI and real service; CDP controls the browser, never substitutes assessment responses.
import fs from 'node:fs/promises';
import path from 'node:path';
const root=path.resolve(process.argv[2]),config=JSON.parse(await fs.readFile(path.join(root,'state.json'),'utf8'));
const result={checks:[],exceptions:[],screenshots:[],fixture:'synthetic showcase + orders DDL + bundled dispatch demo + code-reviewed notice generation + 250 cancellation modules',scope:'Phase C/D/E/F/G real assessment, review/code governance, generation/validation, delivery, reopen, stale source and demo'};
const allowedOrigins=new Set([new URL(config.url).origin]),requests=[];
let socket,sequence=0;const pending=new Map();
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function wait(fn,name){const end=Date.now()+30000;while(Date.now()<end){if(await fn())return;await sleep(100);}throw Error('Timed out: '+name);}
function send(method,params={}){return new Promise((resolve,reject)=>{const id=++sequence;const timer=setTimeout(()=>{pending.delete(id);reject(Error('CDP timeout '+method));},30000);pending.set(id,{resolve:r=>{clearTimeout(timer);resolve(r);},reject:e=>{clearTimeout(timer);reject(e);}});socket.send(JSON.stringify({id,method,params}));});}
async function evaluate(expression){const r=await send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value;}
function check(name,passed,detail){result.checks.push({name,passed:!!passed,detail});if(!passed)throw Error(name+': '+JSON.stringify(detail));}
async function value(id,text){await evaluate(`(()=>{const n=document.getElementById(${JSON.stringify(id)});n.value=${JSON.stringify(text)};n.dispatchEvent(new Event('input',{bubbles:true}));})()`);}
async function click(id){return clickSelector('#'+id);}
async function clickSelector(selector){
  const point=await evaluate(`(()=>{const n=document.querySelector(${JSON.stringify(selector)});if(!n||n.disabled||n.closest('[inert]'))throw Error('Unavailable control');n.scrollIntoView({block:'center'});const r=n.getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2};})()`);
  await send('Input.dispatchMouseEvent',{type:'mousePressed',button:'left',clickCount:1,...point});
  await send('Input.dispatchMouseEvent',{type:'mouseReleased',button:'left',clickCount:1,...point});
}
async function pick(folder){
  await wait(()=>evaluate(`document.getElementById('modal').classList.contains('show')&&!!document.getElementById('project-folder-path')`),'visible folder picker');
  await value('project-folder-path',folder);await click('project-folder-browse');
  await wait(()=>evaluate(`!!document.getElementById('project-folder-select')`),'folder inventory');await click('project-folder-select');
}
async function settled(status){await wait(()=>evaluate(`projectUI.view==='overview'&&!projectUI.jobId&&projectUI.summary?.freshness.status===${JSON.stringify(status)}&&projectUI.overview?.assessment.freshness===${JSON.stringify(status)}&&document.getElementById('project-status').textContent==='Source freshness checked.'`),'source status '+status);}
function owned(file){const target=path.resolve(file),relative=path.relative(root,target);if(!relative||relative.startsWith('..')||path.isAbsolute(relative))throw Error('Fixture path outside owned run');return target;}
async function screenshot(name){const image=await send('Page.captureScreenshot',{format:'png'});await fs.writeFile(path.join(root,name),Buffer.from(image.data,'base64'));result.screenshots.push(name);}
try{
  let page;
  await wait(async()=>{try{const pages=await(await fetch(`http://127.0.0.1:${config.debug_port}/json/list`)).json();page=pages.find(p=>p.type==='page');return !!page;}catch{return false;}},'browser CDP');
  socket=new WebSocket(page.webSocketDebuggerUrl);await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject;});
  socket.onmessage=event=>{const message=JSON.parse(event.data);if(message.id){const item=pending.get(message.id);if(!item)return;pending.delete(message.id);if(message.error)item.reject(Error(JSON.stringify(message.error)));else item.resolve(message.result);}else if(message.method==='Runtime.exceptionThrown')result.exceptions.push(message.params.exceptionDetails);else if(message.method==='Network.requestWillBeSent')requests.push(message.params.request.url);};
  await send('Runtime.enable');await send('Page.enable');await send('Network.enable');await send('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'reduce'}]});await send('Page.navigate',{url:config.url});
  await wait(()=>evaluate(`!!document.getElementById('project-new')`),'project landing');
  check('local first launch without account',await evaluate(`document.body.classList.contains('project-mode')`));
  await click('project-new');await click('project-next');
  check('blank name inline error and focus',await evaluate(`document.activeElement.id==='project-name'&&document.getElementById('project-name').getAttribute('aria-invalid')==='true'`));
  check('name error associated and labelled',await evaluate(`document.getElementById('project-name').getAttribute('aria-describedby')==='project-error'&&!!document.querySelector('label[for="project-name"]')`));
  await send('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});await send('Input.dispatchKeyEvent',{type:'keyUp',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});
  check('keyboard tab reaches description',await evaluate(`document.activeElement.id==='project-description'`));
  await value('project-name','Corporate synthetic assessment');await click('project-next');
  for(const [kind,folder] of [['forms',config.forms],['database',config.database]]){
    await click('project-'+kind);await wait(()=>evaluate(`document.getElementById('modal').classList.contains('show')&&document.getElementById('modal-title').textContent.includes(${JSON.stringify(kind)})&&!!document.getElementById('project-folder-path')`),'folder picker');
    await value('project-folder-path',folder);await click('project-folder-browse');await wait(()=>evaluate(`!!document.getElementById('project-folder-select')`),'folder inventory');
    await click('project-folder-select');await wait(()=>evaluate(`!document.getElementById('modal').classList.contains('show')&&projectUI.draft.preview!==null&&projectUI.draft.sources.length===${kind==='forms'?1:2}`),'discovery preview');
  }
  check('real preview inventory',await evaluate(`projectUI.draft.preview.inventory.forms.parseable===1&&projectUI.draft.preview.inventory.database.tables===1`),await evaluate('projectUI.draft.preview.inventory'));
  await click('project-next');check('target from backend',await evaluate(`document.getElementById('project-content').textContent.includes('26.1')&&document.getElementById('project-content').textContent.includes('APEXlang')`));
  await screenshot('target.png');await click('project-next');await click('project-next');
  await wait(()=>evaluate(`projectUI.view==='overview'&&projectUI.summary?.project.analysis_revision&&!projectUI.jobId&&projectUI.overview?.assessment.freshness==='CURRENT'`),'saved assessment Overview and freshness');
  check('assessment current',await evaluate(`projectUI.summary.freshness.status==='CURRENT'&&projectUI.overview.assessment.freshness==='CURRENT'`));
  check('real Overview metrics',await evaluate(`projectUI.overview.inventory.forms_modules===1&&projectUI.overview.inventory.tables===1&&projectUI.overview.inventory.modernization_findings>0`),await evaluate('projectUI.overview.inventory'));
  const id=await evaluate('projectUI.activeId'),revision=await evaluate('projectUI.summary.project.analysis_revision');
  await screenshot('project-overview.png');
  await clickSelector('[data-project-section="dependencies"]');
  await wait(()=>evaluate(`projectUI.view==='inventory'&&projectUI.inventoryState?.category==='dependencies'&&!!projectUI.inventoryState.page`),'project dependency navigation');
  check('G Dependencies retains current project',await evaluate('projectUI.activeId')===id);
  await clickSelector('[data-project-section="overview"]');await wait(()=>evaluate(`projectUI.view==='overview'`),'Overview after Dependencies');
  const selectedRisk=await evaluate(`Object.entries(projectUI.overview.risk_distribution).find(([,count])=>count>0)?.[0]`);
  await clickSelector(`[data-project-filter="risk"][data-project-value="${selectedRisk}"]`);
  await wait(()=>evaluate(`projectUI.view==='inventory'&&projectUI.inventoryState?.filters.risk===${JSON.stringify(selectedRisk)}&&projectUI.inventoryState?.page?.rows.length>0`),'risk-filtered findings inventory');
  check('risk card opens reconciled findings',await evaluate(`projectUI.inventoryState.page.rows.every(row=>row.risk===${JSON.stringify(selectedRisk)})`));
  const detailTrigger=await evaluate(`document.querySelector('[data-project-item]')?.dataset.projectItem||''`);check('detail row has stable identity',!!detailTrigger,detailTrigger);
  await clickSelector('[data-project-item]');await wait(()=>evaluate(`document.getElementById('modal').classList.contains('show')&&!!document.getElementById('project-detail-close')`),'inventory detail');
  await click('project-detail-close');check('detail close restores row focus',await evaluate(`document.activeElement?.dataset.projectItem===${JSON.stringify(detailTrigger)}`));
  await clickSelector('[data-project-category="dependencies"]');
  await wait(()=>evaluate(`projectUI.inventoryState?.category==='dependencies'&&!!projectUI.inventoryState.page`),'dependency inventory');
  check('dependency category uses real projection',await evaluate(`projectUI.inventoryState.page.total>=0`));
  if(await evaluate(`projectUI.inventoryState.page.rows.length>0`)){
    const dependency=await evaluate(`projectUI.inventoryState.page.rows[0]`);
    await clickSelector('[data-project-item]');
    await wait(()=>evaluate(`document.getElementById('modal').classList.contains('show')&&!!document.getElementById('project-detail-close')`),'dependency detail');
    check('dependency detail names both ends and relationship',await evaluate(`(()=>{const text=document.getElementById('modal-body').textContent;const relationship=projectInventoryLabel('relationship',${JSON.stringify(dependency.relationship)});return text.includes(${JSON.stringify(dependency.source)})&&text.includes(relationship)&&text.includes(${JSON.stringify(dependency.target)});})()`),dependency);
    await click('project-detail-close');
  }
  await clickSelector('[data-project-section="overview"]');await wait(()=>evaluate(`projectUI.view==='overview'`),'return to Overview');
  const previousDocument=await evaluate('performance.timeOrigin');
  await fs.writeFile(path.join(root,'restart.request'),'restart');let restarted;
  await wait(async()=>{try{restarted=JSON.parse(await fs.readFile(path.join(root,'restart.ready'),'utf8'));return true;}catch{return false;}},'fresh server process');
  check('server process actually replaced',restarted.previous_pid!==restarted.current_pid,restarted);allowedOrigins.add(new URL(restarted.url).origin);
  await send('Page.navigate',{url:restarted.url});await wait(()=>evaluate(`performance.timeOrigin!==${previousDocument}&&typeof projectUI!=='undefined'&&projectUI.view==='home'&&!!document.querySelector('[data-project-open]')`),'recent projects after server restart');
  await clickSelector(`[data-project-open="${id}"]`);await settled('CURRENT');
  check('same persisted assessment reopened',await evaluate('projectUI.summary.project.analysis_revision')===revision);
  const original=await fs.readFile(owned(path.join(config.forms,'orders.xml')));
  await fs.appendFile(owned(path.join(config.forms,'orders.xml')),'\n<!-- changed synthetic source -->');
  await click('project-home');await wait(()=>evaluate(`!!document.querySelector('[data-project-open="${id}"]')`),'stale recent project');await clickSelector(`[data-project-open="${id}"]`);await settled('STALE');
  check('stale source keeps saved assessment',await evaluate(`projectUI.summary.project.analysis_revision===${JSON.stringify(revision)}&&projectUI.overview.inventory.forms_modules===1&&document.getElementById('project-content').textContent.includes('Stale')`));await screenshot('stale-overview.png');
  await fs.writeFile(owned(path.join(config.forms,'orders.xml')),original);
  const moved=owned(path.join(root,'sources/forms-relocated'));await fs.rename(owned(config.forms),moved);
  await click('project-home');await wait(()=>evaluate(`!!document.querySelector('[data-project-open="${id}"]')`),'missing-source recent project');await clickSelector(`[data-project-open="${id}"]`);await settled('MISSING_SOURCE');
  await click('project-relink-missing');check('missing source offers relink',await evaluate(`!!document.querySelector('[data-project-relink]')`));
  const formsRoot=await evaluate(`projectUI.summary.project.source_roots.find(r=>r.kind==='forms').id`);
  await clickSelector(`[data-project-relink="${formsRoot}"]`);await pick(moved);await settled('CURRENT');
  check('same-content relink preserves assessment',await evaluate('projectUI.summary.project.analysis_revision')===revision);
  await fs.writeFile(owned(path.join(moved,'bad.xml')),'<FormModule><broken>');await clickSelector('[data-project-section="settings"]');await click('project-analyze');await settled('INCOMPLETE');await clickSelector('[data-project-section="settings"]');await click('project-saved');
  await wait(()=>evaluate(`document.getElementById('project-saved-content').textContent.includes('bad.xml')`),'malformed source remediation');
  check('partial failure retains valid form',await evaluate(`projectUI.summary.inventory.forms.analyzed===1&&document.getElementById('project-saved-content').textContent.includes('bad.xml')`));await screenshot('partial-failure.png');
  const cancelFolder=owned(path.join(root,'sources/cancel-forms'));await fs.mkdir(cancelFolder);
  for(let i=0;i<250;i++)await fs.writeFile(owned(path.join(cancelFolder,`form-${i}.xml`)),`<Module><FormModule Name="CANCEL_${i}"><Trigger Name="WHEN-NEW-FORM-INSTANCE" TriggerText="null;"/></FormModule></Module>`);
  await click('project-home');await click('project-new');await value('project-name','Cancellation acceptance');await click('project-next');await click('project-forms');await pick(cancelFolder);
  await wait(()=>evaluate(`projectUI.draft.preview!==null&&projectUI.draft.sources.length===1`),'cancel estate preview');await click('project-next');await click('project-next');await click('project-next');
  await wait(()=>evaluate(`projectUI.view==='progress'&&!!document.getElementById('project-cancel')`),'cancellable progress');
  check('labelled progress and live status',await evaluate(`document.getElementById('project-progress').getAttribute('role')==='progressbar'&&document.getElementById('project-progress').getAttribute('aria-label')==='Analysis progress'&&document.getElementById('project-status').getAttribute('aria-live')==='polite'`));
  await click('project-cancel');await wait(()=>evaluate(`projectUI.view==='summary'&&!projectUI.jobId&&document.getElementById('project-status').textContent.includes('Analysis cancelled')`),'cancelled job');
  check('cancel does not publish assessment',await evaluate(`!projectUI.summary.project.analysis_revision`));
  await click('project-home');await wait(()=>evaluate(`!!document.querySelector('[data-project-open="${id}"]')`),'previous project');await clickSelector(`[data-project-open="${id}"]`);await settled('INCOMPLETE');
  check('project switch isolates cancellation',await evaluate(`projectUI.activeId===${JSON.stringify(id)}&&projectUI.summary.project.name==='Corporate synthetic assessment'&&!!projectUI.summary.project.analysis_revision`));
  await click('project-home');await wait(()=>evaluate(`!!document.getElementById('project-demo')`),'demo action');
  await click('project-demo');
  await wait(()=>evaluate(`projectUI.view==='overview'&&projectUI.summary?.project.name==='Synthetic dispatch desk'&&!projectUI.jobId&&projectUI.overview?.assessment.freshness==='CURRENT'&&document.getElementById('project-status').textContent==='Source freshness checked.'`),'real demo Overview');
  check('bundled demo follows real project path',await evaluate(`projectUI.summary.inventory.forms.analyzed===2&&projectUI.summary.inventory.database.package_bodies===1&&projectUI.overview.inventory.forms_modules===2&&projectUI.overview.risk_distribution.CRITICAL>0`));
  await clickSelector('[data-project-filter="risk"][data-project-value="CRITICAL"]');await wait(()=>evaluate(`projectUI.inventoryState?.filters.risk==='CRITICAL'&&projectUI.inventoryState.page?.rows.length>0`),'demo Critical inventory');
  check('demo Critical card is evidence-backed',await evaluate(`projectUI.inventoryState.page.rows.every(row=>row.risk==='CRITICAL')`));
  await clickSelector('[data-project-category="packages"]');await wait(()=>evaluate(`projectUI.inventoryState?.category==='packages'&&!!projectUI.inventoryState.page`),'package inventory');
  await value('project-inventory-search','SHIPMENT_API');await click('project-inventory-apply');await wait(()=>evaluate(`projectUI.inventoryState?.query==='SHIPMENT_API'&&projectUI.inventoryState.page?.total===1`),'package search');
  check('package search uses persisted projection',await evaluate(`projectUI.inventoryState.page.rows[0].name==='SHIPMENT_API'`));
  await screenshot('demo-inventory.png');
  const {reviewChecks}=await import('./project_review_browser_check.mjs');
  await reviewChecks({evaluate,click,clickSelector,value,wait,check,screenshot,send});
  const {generationChecks}=await import('./project_generation_browser_check.mjs');
  await generationChecks({evaluate,click,clickSelector,value,wait,check,screenshot,pick,folder:config.generation});
  const {reportChecks}=await import('./project_reports_browser_check.mjs');
  await reportChecks({evaluate,click,clickSelector,wait,check,screenshot,send,root});
  await send('Emulation.setDeviceMetricsOverride',{width:700,height:900,deviceScaleFactor:1,mobile:false});
  await sleep(300);check('tablet no horizontal overflow',await evaluate('document.documentElement.scrollWidth<=innerWidth+1'));
  check('reduced motion preference retained',await evaluate(`matchMedia('(prefers-reduced-motion: reduce)').matches`));
  const external=requests.filter(url=>/^https?:/.test(url)&&!allowedOrigins.has(new URL(url).origin));check('application requests remain loopback',external.length===0,external);
  check('no browser exceptions',result.exceptions.length===0,result.exceptions);
}catch(error){result.failure=String(error);console.error(error);process.exitCode=1;try{result.ui=await evaluate(`({view:projectUI.view,summary:projectUI.summary,error:document.getElementById('project-error').textContent,status:document.getElementById('project-status').textContent})`);await screenshot('failure.png');}catch{}}
finally{await fs.writeFile(path.join(root,'result.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));if(socket?.readyState===1){try{await send('Browser.close');}catch{}socket.close();}}
