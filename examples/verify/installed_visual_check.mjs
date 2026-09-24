// Installed-product smoke for 2.2: the lab showcase journey on the UI the
// installed engine serves. CDP drives the browser; no response is substituted.
import fs from 'node:fs/promises';
import path from 'node:path';
const root=path.resolve(process.argv[2]),config=JSON.parse(await fs.readFile(path.join(root,'state.json'),'utf8'));
const result={checks:[],exceptions:[],screenshots:[],url:config.url,version:config.version,
  scope:'installed engine: Overview -> Start Here -> Hotspot -> System Map -> Review -> Module 360 -> Reports on the modernization lab'};
const allowedOrigins=new Set([new URL(config.url).origin]),requests=[];
let socket,sequence=0;const pending=new Map();
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function wait(fn,name,timeout=30000){const end=Date.now()+timeout;while(Date.now()<end){if(await fn())return;await sleep(100);}throw Error('Timed out: '+name);}
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
async function screenshot(name){const image=await send('Page.captureScreenshot',{format:'png'});await fs.writeFile(path.join(root,name),Buffer.from(image.data,'base64'));result.screenshots.push(name);}
try{
  let page;
  await wait(async()=>{try{const pages=await(await fetch(`http://127.0.0.1:${config.debug_port}/json/list`)).json();page=pages.find(p=>p.type==='page');return !!page;}catch{return false;}},'browser CDP');
  socket=new WebSocket(page.webSocketDebuggerUrl);await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject;});
  socket.onmessage=event=>{const message=JSON.parse(event.data);if(message.id){const item=pending.get(message.id);if(!item)return;pending.delete(message.id);if(message.error)item.reject(Error(JSON.stringify(message.error)));else item.resolve(message.result);}else if(message.method==='Runtime.exceptionThrown')result.exceptions.push(message.params.exceptionDetails);else if(message.method==='Network.requestWillBeSent')requests.push(message.params.request.url);};
  await send('Runtime.enable');await send('Page.enable');await send('Network.enable');await send('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'reduce'}]});await send('Page.navigate',{url:config.url});
  await wait(()=>evaluate(`!!document.getElementById('project-home')`),'installed UI',60000);
  check('installed UI carries the 2.2 visual renderers',await evaluate(`['visualSetMode','visualModuleBody','visualHotspotCard','systemMapGeometry'].every(name=>typeof window[name]==='function')`),
    await evaluate(`['visualSetMode','visualModuleBody','visualHotspotCard','systemMapGeometry'].filter(name=>typeof window[name]!=='function')`));
  const {showcaseChecks}=await import('./project_showcase_browser_check.mjs');
  await showcaseChecks({evaluate,click,clickSelector,value,wait,check,screenshot,send,pick,forms:config.lab_forms,database:config.lab_database});
  const external=requests.filter(url=>/^https?:/.test(url)&&!allowedOrigins.has(new URL(url).origin));check('installed UI requests remain loopback',external.length===0,external);
  check('no browser exceptions',result.exceptions.length===0,result.exceptions);
  result.passed=true;
}catch(error){result.passed=false;result.failure=String(error);console.error(error);process.exitCode=1;try{await screenshot('failure.png');}catch{}}
finally{await fs.writeFile(path.join(root,'result.json'),JSON.stringify(result,null,2));console.log(JSON.stringify({passed:result.passed,checks:result.checks.length,failed:result.checks.filter(c=>!c.passed).map(c=>c.name),failure:result.failure},null,2));if(socket?.readyState===1){try{await send('Browser.close');}catch{}socket.close();}}
