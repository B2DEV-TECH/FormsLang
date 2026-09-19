// Real UI and real service; CDP controls the browser, never substitutes assessment responses.
import fs from 'node:fs/promises';
import path from 'node:path';
const root=path.resolve(process.argv[2]),config=JSON.parse(await fs.readFile(path.join(root,'state.json'),'utf8'));
const result={checks:[],exceptions:[],screenshots:[],fixture:'synthetic showcase + orders DDL',scope:'Phase B onboarding smoke; demo/restart acceptance follows'};
let socket,sequence=0;const pending=new Map();
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function wait(fn,name){const end=Date.now()+30000;while(Date.now()<end){if(await fn())return;await sleep(100);}throw Error('Timed out: '+name);}
function send(method,params={}){return new Promise((resolve,reject)=>{const id=++sequence;const timer=setTimeout(()=>{pending.delete(id);reject(Error('CDP timeout '+method));},30000);pending.set(id,{resolve:r=>{clearTimeout(timer);resolve(r);},reject:e=>{clearTimeout(timer);reject(e);}});socket.send(JSON.stringify({id,method,params}));});}
async function evaluate(expression){const r=await send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value;}
function check(name,passed,detail){result.checks.push({name,passed:!!passed,detail});if(!passed)throw Error(name+': '+JSON.stringify(detail));}
async function value(id,text){await evaluate(`(()=>{const n=document.getElementById(${JSON.stringify(id)});n.value=${JSON.stringify(text)};n.dispatchEvent(new Event('input',{bubbles:true}));})()`);}
async function click(id){
  const point=await evaluate(`(()=>{const n=document.getElementById(${JSON.stringify(id)});if(!n||n.disabled||n.closest('[inert]'))throw Error('Unavailable '+${JSON.stringify(id)});n.scrollIntoView({block:'center'});const r=n.getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2};})()`);
  await send('Input.dispatchMouseEvent',{type:'mousePressed',button:'left',clickCount:1,...point});
  await send('Input.dispatchMouseEvent',{type:'mouseReleased',button:'left',clickCount:1,...point});
}
async function screenshot(name){const image=await send('Page.captureScreenshot',{format:'png'});await fs.writeFile(path.join(root,name),Buffer.from(image.data,'base64'));result.screenshots.push(name);}
try{
  let page;
  await wait(async()=>{try{const pages=await(await fetch(`http://127.0.0.1:${config.debug_port}/json/list`)).json();page=pages.find(p=>p.type==='page');return !!page;}catch{return false;}},'browser CDP');
  socket=new WebSocket(page.webSocketDebuggerUrl);await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject;});
  socket.onmessage=event=>{const message=JSON.parse(event.data);if(message.id){const item=pending.get(message.id);if(!item)return;pending.delete(message.id);if(message.error)item.reject(Error(JSON.stringify(message.error)));else item.resolve(message.result);}else if(message.method==='Runtime.exceptionThrown')result.exceptions.push(message.params.exceptionDetails);};
  await send('Runtime.enable');await send('Page.enable');await send('Page.navigate',{url:config.url});
  await wait(()=>evaluate(`!!document.getElementById('project-new')`),'project landing');
  check('local first launch without account',await evaluate(`document.body.classList.contains('project-mode')`));
  await click('project-new');await click('project-next');
  check('blank name inline error and focus',await evaluate(`document.activeElement.id==='project-name'&&document.getElementById('project-name').getAttribute('aria-invalid')==='true'`));
  await value('project-name','Corporate synthetic assessment');await click('project-next');
  for(const [kind,folder] of [['forms',config.forms],['database',config.database]]){
    await click('project-'+kind);await wait(()=>evaluate(`document.getElementById('modal').classList.contains('show')&&document.getElementById('modal-title').textContent.includes(${JSON.stringify(kind)})&&!!document.getElementById('project-folder-path')`),'folder picker');
    await value('project-folder-path',folder);await click('project-folder-browse');await wait(()=>evaluate(`!!document.getElementById('project-folder-select')`),'folder inventory');
    await click('project-folder-select');await wait(()=>evaluate(`!document.getElementById('modal').classList.contains('show')&&projectUI.draft.preview!==null&&projectUI.draft.sources.length===${kind==='forms'?1:2}`),'discovery preview');
  }
  check('real preview inventory',await evaluate(`projectUI.draft.preview.inventory.forms.parseable===1&&projectUI.draft.preview.inventory.database.tables===1`),await evaluate('projectUI.draft.preview.inventory'));
  await click('project-next');check('target from backend',await evaluate(`document.getElementById('project-content').textContent.includes('26.1')&&document.getElementById('project-content').textContent.includes('APEXlang')`));
  await screenshot('target.png');await click('project-next');await click('project-next');
  await wait(()=>evaluate(`projectUI.view==='summary'&&projectUI.summary?.project.analysis_revision&&!projectUI.jobId&&projectUI.summary?.freshness.status==='CURRENT'`),'saved assessment and freshness');
  check('assessment current',await evaluate(`projectUI.summary.freshness.status==='CURRENT'`));
  const id=await evaluate('projectUI.activeId'),revision=await evaluate('projectUI.summary.project.analysis_revision');
  await screenshot('saved-assessment.png');await click('project-saved');
  await wait(()=>evaluate(`document.getElementById('project-saved-content').textContent.includes('Findings:')`),'saved evidence');
  const previousDocument=await evaluate('performance.timeOrigin');
  await send('Page.reload');await wait(()=>evaluate(`performance.timeOrigin!==${previousDocument}&&typeof projectUI!=='undefined'&&projectUI.view==='home'&&!!document.querySelector('[data-project-open]')`),'recent projects after reload');
  await evaluate(`document.querySelector('[data-project-open="${id}"]').click()`);
  await wait(()=>evaluate(`projectUI.view==='summary'&&!projectUI.jobId&&projectUI.summary?.freshness.status==='CURRENT'&&document.getElementById('project-status').textContent==='Source freshness checked.'`),'reopened assessment');
  check('same persisted assessment reopened',await evaluate('projectUI.summary.project.analysis_revision')===revision);
  await send('Emulation.setDeviceMetricsOverride',{width:700,height:900,deviceScaleFactor:1,mobile:false});
  await sleep(300);check('tablet no horizontal overflow',await evaluate('document.documentElement.scrollWidth<=innerWidth+1'));
  check('no browser exceptions',result.exceptions.length===0,result.exceptions);
}catch(error){result.failure=String(error);console.error(error);process.exitCode=1;try{result.ui=await evaluate(`({view:projectUI.view,summary:projectUI.summary,error:document.getElementById('project-error').textContent,status:document.getElementById('project-status').textContent})`);await screenshot('failure.png');}catch{}}
finally{await fs.writeFile(path.join(root,'result.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));if(socket?.readyState===1){try{await send('Browser.close');}catch{}socket.close();}}
