// Drive the frozen Workbench with one saved project and its real persisted assessment.
import fs from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {journeyChecks} from './project_journey_browser_check.mjs';
import {reportChecks} from './project_reports_browser_check.mjs';

const root=path.resolve(process.argv[2]);
const config=JSON.parse(await fs.readFile(path.join(root,'state.json'),'utf8'));
const result={checks:[],screenshots:[],exceptions:[]};
let socket,sequence=0;const pending=new Map();
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function wait(fn,name,timeout=30000){const end=Date.now()+timeout;while(Date.now()<end){if(await fn())return;await sleep(100);}throw Error('Timed out: '+name);}
function send(method,params={}){return new Promise((resolve,reject)=>{const id=++sequence;const timer=setTimeout(()=>{pending.delete(id);reject(Error('CDP timeout '+method));},30000);pending.set(id,{resolve:r=>{clearTimeout(timer);resolve(r);},reject:e=>{clearTimeout(timer);reject(e);}});socket.send(JSON.stringify({id,method,params}));});}
async function evaluate(expression){const r=await send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value;}
function check(name,passed,detail){result.checks.push({name,passed:!!passed,detail});if(!passed)throw Error(name+': '+JSON.stringify(detail));}
async function click(id){return clickSelector('#'+id);}
async function value(id,text){await evaluate(`(()=>{const n=document.getElementById(${JSON.stringify(id)});n.value=${JSON.stringify(text)};n.dispatchEvent(new Event('input',{bubbles:true}));})()`);}
async function clickSelector(selector){const point=await evaluate(`(()=>{const n=document.querySelector(${JSON.stringify(selector)});if(!n||n.disabled||n.closest('[inert]'))throw Error('Unavailable control');n.scrollIntoView({block:'center'});const r=n.getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2};})()`);await send('Input.dispatchMouseEvent',{type:'mousePressed',button:'left',clickCount:1,...point});await send('Input.dispatchMouseEvent',{type:'mouseReleased',button:'left',clickCount:1,...point});}
async function screenshot(name){const image=await send('Page.captureScreenshot',{format:'png'});await fs.writeFile(path.join(root,name),Buffer.from(image.data,'base64'));result.screenshots.push(name);}
try{
  let page;
  await wait(async()=>{try{const pages=await(await fetch(`http://127.0.0.1:${config.debug_port}/json/list`)).json();page=pages.find(p=>p.type==='page');return !!page;}catch{return false;}},'browser CDP');
  socket=new WebSocket(page.webSocketDebuggerUrl);await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject;});
  socket.onmessage=event=>{const message=JSON.parse(event.data);if(message.id){const item=pending.get(message.id);if(!item)return;pending.delete(message.id);if(message.error)item.reject(Error(JSON.stringify(message.error)));else item.resolve(message.result);}else if(message.method==='Runtime.exceptionThrown')result.exceptions.push(message.params.exceptionDetails);};
  await send('Runtime.enable');await send('Page.enable');await send('Page.navigate',{url:config.url});
  await wait(()=>evaluate(`!!document.querySelector('[data-project-open]')`),'saved project on Workbench landing');
  const candidates=await evaluate(`[...document.querySelectorAll('[data-project-open]')].map(n=>({id:n.dataset.projectOpen,text:n.textContent}))`);
  const match=candidates.find(c=>c.id===config.project_id);
  check('exact CLI-created project appears in frozen Workbench',!!match&&match.text.includes('Synthetic beta A to B journey'),candidates);
  await clickSelector(`[data-project-open="${match.id}"]`);
  await wait(()=>evaluate(`projectUI.view==='overview'&&!!projectUI.overview?.assessment`),'saved composite Overview');
  check('same composite project contains three Forms and one package',await evaluate(`projectUI.summary.inventory.forms.analyzed===3&&projectUI.summary.inventory.database.package_bodies===1`));
  check('saved composite assessment has current source',await evaluate(`projectUI.overview.assessment.freshness==='CURRENT'`));
  await journeyChecks({evaluate,click,clickSelector,wait,check,screenshot,moduleSuffix:'/shipments.xml'});
  await clickSelector('[data-project-section="generate"]');
  await wait(()=>evaluate(`projectUI.view==='generate'&&!!projectUI.generationState?.data`),'generation section');
  check('notice.xml generation scope belongs to the same project',await evaluate(`projectUI.generationState.data.modules.some(m=>m.module.endsWith('/notice.xml')&&!m.prepared)&&document.getElementById('project-content').textContent.includes('notice.xml')`));
  const notice=await evaluate(`projectUI.generationState.data.modules.find(m=>m.module.endsWith('/notice.xml'))`);
  await clickSelector(`[data-generation-module="${notice.source_id}"]`);
  await wait(()=>evaluate(`!!document.getElementById('project-generation-prepare')`),'NOTICE module blockers');
  check('unreviewed NOTICE remains blocked',await evaluate(`!projectUI.generationState.detail.ready&&projectUI.generationState.detail.blockers.length>0`));
  await click('project-generation-prepare');
  await wait(()=>evaluate(`!!document.getElementById('project-generation-plan')&&!projectUI.generationState.busy`),'prepared NOTICE code session');
  await click('project-generation-review');
  await wait(()=>evaluate(`!!projectUI.reviewState?.page`),'NOTICE review queue');
  const findings=await evaluate(`projectUI.reviewState.page.rows.map(r=>({id:r.id,module:r.module}))`);
  check('NOTICE review filters unrelated Forms',findings.length>0&&findings.every(r=>r.module.endsWith('/notice.xml')),findings);
  for(const finding of findings){
    await clickSelector(`[data-review-item="${finding.id}"]`);
    await wait(()=>evaluate(`projectUI.reviewState.detail?.item.id===${JSON.stringify(finding.id)}&&!projectUI.reviewState.busy`),'NOTICE finding');
    await click('project-review-accept');
    await wait(()=>evaluate(`!projectUI.reviewState.busy&&projectUI.reviewState.detail?.item.review_state==='APPROVE'`),'recorded NOTICE approval');
  }
  const review=await evaluate(`({id:projectUI.reviewState.detail.item.id,history:projectUI.reviewState.detail.history.length})`);
  check('NOTICE decision has persisted history',review.history>0,review);
  await clickSelector('[data-project-section="generate"]');
  await wait(()=>evaluate(`!!projectUI.generationState?.data`),'reviewed generation');
  await clickSelector(`[data-generation-module="${notice.source_id}"]`);
  await wait(()=>evaluate(`!!document.getElementById('generation-security')`),'target prerequisite controls');
  for(const id of ['generation-security','generation-database','generation-mapping'])await click(id);
  await value('generation-rationale','Synthetic NOTICE scope: target access and absence of database writes reviewed.');
  await click('project-generation-plan');
  await wait(()=>evaluate(`!!projectUI.generationState.detail?.target_revision&&!projectUI.generationState.busy`),'saved target plan');
  check('architecture review does not approve code',await evaluate(`!projectUI.generationState.detail.ready&&projectUI.generationState.detail.tasks.length===1`));
  await clickSelector('[data-generation-task]');
  await wait(()=>evaluate(`!!document.getElementById('generation-code')`),'code approval evidence');
  await value('generation-code',"BEGIN IF :P0_MESSAGE IS NULL THEN raise_application_error(-20001, 'Required'); END IF; END;");
  await value('generation-code-rationale','Reviewed synthetic validation against the saved target plan and Forms evidence.');
  await click('generation-code-confirm');await click('generation-code-approve');
  await wait(()=>evaluate(`projectUI.generationState.detail?.ready&&!projectUI.generationState.busy`),'code-approved NOTICE scope');
  check('only explicit code approval enables NOTICE',await evaluate(`projectUI.generationState.detail.tasks[0].state==='approved'&&!document.getElementById('project-generation-run').disabled`));
  await click('project-generation-run');
  await wait(()=>evaluate(`projectUI.generationState?.data?.artifacts.length===1`),'generated immutable artifact');
  const artifact=await evaluate('projectUI.generationState.data.artifacts[0]');
  check('generated artifact starts unvalidated',artifact.status==='Generated'&&artifact.validation_status==='Not Validated',artifact);
  const response=await fetch(`${config.url}/api/v2/projects/${match.id}/artifacts/${artifact.artifact_id}/download`);
  const bytes=Buffer.from(await response.arrayBuffer());
  const hash=createHash('sha256').update(bytes).digest('hex');
  check('NOTICE ZIP download matches recorded SHA-256',response.ok&&response.headers.get('content-type')==='application/zip'&&bytes.length===artifact.size_bytes&&hash===artifact.sha256,{size:bytes.length,hash,expected:artifact.sha256});
  await fs.writeFile(path.join(root,'notice.apex.zip'),bytes);
  await clickSelector('[data-generation-validate]');
  await wait(()=>evaluate(`!!projectUI.generationState?.data?.artifacts[0]?.validation`),'explicit offline validation');
  const validation=await evaluate('projectUI.generationState.data.artifacts[0].validation');
  check('validation records offline mode and artifact hash',validation.mode==='offline-syntax'&&validation.artifact_sha256===artifact.sha256,validation);
  await screenshot('notice-generation.png');
  await reportChecks({evaluate,click,clickSelector,wait,check,screenshot,send,root});
  await clickSelector('[data-project-section="review"]');
  await wait(()=>evaluate(`!!projectUI.reviewState?.page`),'reopened review queue');
  check('NOTICE review history survives reopen',await evaluate(`(async()=>{const r=await fetch('/api/v2/projects/'+projectUI.activeId+'/review/'+encodeURIComponent(${JSON.stringify(review.id)}));const d=await r.json();return d.item.review_state==='APPROVE'&&d.history.length>=${review.history};})()`));
  await clickSelector('[data-project-section="generate"]');
  await wait(()=>evaluate(`projectUI.generationState?.data?.artifacts.length===1`),'reopened artifact');
  check('NOTICE artifact identity survives reopen',await evaluate('projectUI.generationState.data.artifacts[0].artifact_id')===artifact.artifact_id);
  check('no browser exceptions',result.exceptions.length===0,result.exceptions);
}catch(error){result.failure=String(error);console.error(error);process.exitCode=1;try{result.ui=await evaluate(`({view:projectUI.view,summary:projectUI.summary,status:document.getElementById('project-status')?.textContent})`);await screenshot('failure.png');}catch{}}
finally{await fs.writeFile(path.join(root,'result.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));if(socket?.readyState===1){try{await send('Browser.close');}catch{}socket.close();}}
