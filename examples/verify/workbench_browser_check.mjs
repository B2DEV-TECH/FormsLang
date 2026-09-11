// Real Chromium CDP acceptance: no dependency installation or remote services.
import fs from 'node:fs/promises';
import path from 'node:path';

const root = path.resolve(process.argv[2]);
const config = JSON.parse(await fs.readFile(path.join(root, 'state.json'), 'utf8'));
const origin = new URL(config.url).origin;
const result = {fixture: 'tests/fixtures/showcase/module.xml', source_sha256: config.source_sha256, ui_sha256: config.ui_sha256, provider: 'offline synthetic stub; no model ran', desktop_viewport: {width: 1366, height: 768}, checks: [], screenshots: [], exceptions: [], blockedRequests: []};
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
let socket, next = 0;
const pending = new Map();

function check(name, passed, detail = undefined) {
  result.checks.push({name, passed: Boolean(passed), ...(detail === undefined ? {} : {detail})});
  if (!passed) console.error(`FAIL: ${name}: ${JSON.stringify(detail)}`);
}
async function waitFor(fn, description, timeout = 30000) {
  const deadline = Date.now() + timeout;
  let last;
  while (Date.now() < deadline) {
    try { const value = await fn(); if (value) return value; } catch (error) { last = String(error); }
    await sleep(100);
  }
  throw new Error(`Timed out waiting for ${description}${last ? ': ' + last : ''}`);
}
function send(method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = ++next;
    const timer = setTimeout(() => { pending.delete(id); reject(new Error(`CDP timeout: ${method}`)); }, 30000);
    pending.set(id, {resolve: value => { clearTimeout(timer); resolve(value); }, reject: error => { clearTimeout(timer); reject(error); }});
    socket.send(JSON.stringify({id, method, params}));
  });
}
async function evaluate(expression) {
  const r = await send('Runtime.evaluate', {expression, awaitPromise: true, returnByValue: true});
  if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails));
  return r.result.value;
}
async function click(selector) {
  await evaluate(`(() => {const node=document.querySelector(${JSON.stringify(selector)});if(!node||node.disabled)throw Error('Control unavailable: '+${JSON.stringify(selector)});node.click();})()`);
}
async function setValue(selector, value) {
  await evaluate(`(() => {const node=document.querySelector(${JSON.stringify(selector)});node.value=${JSON.stringify(value)};node.dispatchEvent(new Event('input',{bubbles:true}));node.dispatchEvent(new Event('change',{bubbles:true}));})()`);
}
async function shot(name) {
  await waitFor(() => evaluate(`!document.querySelector('#toast.show')&&(!document.querySelector('#toast')||getComputedStyle(document.querySelector('#toast')).opacity==='0')`), 'notification to settle', 10000);
  // Wait for fonts and two animation frames so captures reflect painted UI.
  await evaluate(`(async()=>{await document.fonts.ready;await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));})()`);
  const data = await send('Page.captureScreenshot', {format: 'png'});
  await fs.writeFile(path.join(root, `${name}.png`), Buffer.from(data.data, 'base64'));
  result.screenshots.push(`${name}.png`);
}
async function viewport(width, height = 768) {
  await send('Emulation.setDeviceMetricsOverride', {width, height, deviceScaleFactor: 1, mobile: false});
  await sleep(100);
}
async function dimensions(blueprint) {
  return evaluate(`(() => {
    const root=${blueprint ? "document.querySelector('#bp')" : 'document.documentElement'};
    const sheet=document.querySelector('.sheet');
    const rect=sheet?.getBoundingClientRect();
    const visible=node=>{const r=node.getBoundingClientRect();return r.width&&r.height&&getComputedStyle(node).visibility!=='hidden';};
    const overflow=[...root.querySelectorAll('button,input,textarea,select')].filter(visible).map(node=>({id:node.id,label:node.textContent.trim().slice(0,55),left:node.getBoundingClientRect().left,right:node.getBoundingClientRect().right})).filter(r=>r.left < -1 || r.right > innerWidth+1);
    return {width:innerWidth,documentWidth:document.documentElement.scrollWidth,rootWidth:root.scrollWidth,rootClientWidth:root.clientWidth,modal:rect?{left:rect.left,right:rect.right,width:rect.width}:null,overflow};
  })()`);
}

try {
  console.log('Opening isolated headless browser...');
  const pages = await waitFor(async () => {
    const r = await fetch(`http://127.0.0.1:${config.debug_port}/json/list`);
    return r.ok && (await r.json()).filter(t => t.type === 'page');
  }, 'local browser debugger');
  if (!pages.length) throw new Error('No CDP page');
  socket = new WebSocket(pages[0].webSocketDebuggerUrl);
  await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject; });
  socket.onmessage = event => {
    const message = JSON.parse(event.data);
    if (message.id) {
      const promise = pending.get(message.id); if (!promise) return;
      pending.delete(message.id);
      message.error ? promise.reject(new Error(JSON.stringify(message.error))) : promise.resolve(message.result);
    } else if (message.method === 'Runtime.exceptionThrown') {
      result.exceptions.push(message.params.exceptionDetails);
    } else if (message.method === 'Fetch.requestPaused') {
      const {requestId, request} = message.params;
      const allowed = request.url.startsWith(origin + '/') || request.url.startsWith('data:');
      if (!allowed) result.blockedRequests.push(request.url);
      void send(allowed ? 'Fetch.continueRequest' : 'Fetch.failRequest', allowed ? {requestId} : {requestId, errorReason: 'BlockedByClient'}).catch(error => result.exceptions.push(String(error)));
    }
  };
  await send('Runtime.enable');
  await send('Page.enable');
  await send('Browser.setDownloadBehavior', {behavior: 'allow', downloadPath: root});
  await send('Fetch.enable', {patterns: [{urlPattern: '*'}]});
  await viewport(1366);
  await send('Page.navigate', {url: config.url});
  await waitFor(() => evaluate(`typeof state!=='undefined'&&state.tasks?.length>0&&!!document.querySelector('#btn-blueprint')`), 'Workbench tasks');

  console.log('Exercising Blueprint overview, AI proposal, source evidence and review...');
  await click('#btn-blueprint');
  await waitFor(() => evaluate(`!!document.querySelector('#bp-ai-overview')`), 'Blueprint overview');
  const overview = await evaluate(`({routes:document.querySelectorAll('.bp-route').length,settingsHidden:document.querySelector('#bp-settings')?.hidden,inspectHidden:document.querySelector('#bp-inspect')?.hidden})`);
  check('Blueprint provides connected source and progressive disclosure', overview.routes > 0 && overview.settingsHidden && overview.inspectHidden, overview);
  await shot('blueprint-overview');
  await click('#bp-ai-overview');
  await waitFor(() => evaluate(`document.querySelector('#bp-ai-status')?.dataset.running==='true'`), 'visible AI progress');
  check('AI job shows progress before a response', true);
  await shot('blueprint-running');
  await click('#modal-close');
  await click('#btn-blueprint');
  await waitFor(() => evaluate(`document.querySelectorAll('.bp-ai-section').length>0`), 'offline AI proposal');
  const ai = await evaluate(`({sections:document.querySelectorAll('.bp-ai-section').length,links:document.querySelectorAll('#bp-ai-narrative [data-bp-node]').length,text:document.querySelector('#bp-ai-narrative').textContent})`);
  check('AI proposal is linked to evidence and explicitly synthetic', ai.sections > 0 && ai.links > 0 && ai.text.includes('no AI model ran'), ai);
  check('Reopening Blueprint reconnects the AI job', true);
  await shot('blueprint-ai');
  await click('#bp-ai-save');
  const briefing = await waitFor(async () => fs.readFile(path.join(root, 'formslang-ai-briefing.html'), 'utf8'), 'downloaded AI briefing');
  check('AI briefing download preserves proposal status and provenance', briefing.includes('AI proposal') && briefing.includes('no AI model ran') && briefing.includes('Source revision:'));

  await evaluate(`bpFilter({entity_type:'BUSINESS_RULE'})`);
  await waitFor(() => evaluate(`!!document.querySelector('#bp-list [data-bp-node]')`), 'rule candidate list');
  await evaluate(`(() => {const buttons=[...document.querySelectorAll('#bp-list [data-bp-node]')];(buttons.find(b=>b.textContent.includes('WHEN-VALIDATE-ITEM'))||buttons[0]).click();})()`);
  await waitFor(() => evaluate(`!!document.querySelector('#bp-decide')`), 'selected candidate');
  const detail = await evaluate(`({evidence:document.querySelectorAll('.bp-evidence').length,reviewHidden:document.querySelector('#bp-review-form').hidden})`);
  check('Candidate shows source evidence before review form', detail.evidence > 0 && detail.reviewHidden, detail);
  await evaluate(`document.querySelector('#bp-detail').scrollIntoView({block:'start'})`);
  await shot('blueprint-inspect');
  await evaluate(`document.querySelector('#bp-detail .bp-evidence').scrollIntoView({block:'center'})`);
  await shot('blueprint-source-evidence');
  const ruleId = await evaluate(`bpSelectedNode`);
  check('Rule candidate links to its source unit', await evaluate(`document.querySelector('#bp-detail').textContent.includes('Open its source unit and dependencies')`));
  await evaluate(`(() => {const link=[...document.querySelectorAll('#bp-detail [data-bp-node]')].find(n=>n.textContent.includes('Open its source unit and dependencies'));if(!link)throw Error('Missing source-unit link');link.click();})()`);
  await waitFor(() => evaluate(`bpSelectedNode!==${JSON.stringify(ruleId)}&&!!document.querySelector('#bp-back')`), 'source unit detail');
  check('Source-unit navigation reveals dependencies', await evaluate(`document.querySelectorAll('#bp-detail .bp-deps [data-bp-node]').length>0`));
  await click('#bp-back');
  await waitFor(() => evaluate(`bpSelectedNode===${JSON.stringify(ruleId)}`), 'previous rule candidate');
  check('Previous component returns to the rule candidate', true);
  await click('#bp-decide');
  await setValue('#bp-action', 'DEFER');
  await setValue('#bp-reviewer', 'Synthetic browser reviewer');
  await setValue('#bp-comment', 'Browser acceptance fixture: confirm transaction ownership before deciding.');
  const candidate = await evaluate(`document.querySelector('#bp-list [aria-pressed="true"]').dataset.bpNode`);
  await click('[data-bp-tab="understand"]');
  await evaluate(`bpExplore(${JSON.stringify(candidate)})`);
  await click('[data-bp-tab="inspect"]');
  check('Unsaved architecture rationale survives component navigation', await evaluate(`document.querySelector('#bp-comment').value.includes('Browser acceptance fixture:')`));
  if (await evaluate(`document.querySelector('#bp-review-form').hidden`)) await click('#bp-decide');
  await click('#bp-save');
  await waitFor(() => evaluate(`document.querySelector('#bp-detail')?.textContent.includes('Browser acceptance fixture:')`), 'persisted architecture review');
  check('Human architecture decision persists', true);
  await shot('blueprint-review');
  await click('[data-bp-tab="plan"]');
  await waitFor(() => evaluate(`!document.querySelector('#bp-plan').hidden`), 'modernization plan');
  await shot('blueprint-plan');
  for (const width of [720, 390]) {
    await viewport(width, 900);
    await click('[data-bp-tab="understand"]');
    const d = await dimensions(true);
    check(`Blueprint overview fits ${width}px`, d.modal.left >= 0 && d.modal.right <= width + 1 && d.rootWidth <= d.rootClientWidth + 1 && !d.overflow.length, d);
    await shot(`blueprint-${width}`);
  }

  console.log('Exercising conversion, editable drafts, review tabs and responsive layout...');
  await viewport(1366);
  await click('#modal-close');
  await evaluate(`(() => {const task=state.tasks.find(t=>t.owner==='BK_PRODUTO.VL_PRECO'&&t.name==='WHEN-VALIDATE-ITEM');if(!task)throw Error('Synthetic price validation fixture is missing');select(task.id);})()`);
  const task = await evaluate(`selected`);
  await click('#btn-propose');
  await waitFor(() => evaluate(`!job?.running&&state.tasks.find(t=>t.id===${JSON.stringify(task)})?.proposal`), 'offline conversion proposal');
  check('Conversion produces an explicit offline placeholder', await evaluate(`document.querySelector('#out').value.includes('nothing was converted')`));
  const hasTabs = await evaluate(`!!document.querySelector('#review-workspace')`);
  check('Conversion has focused code and evidence views', hasTabs);
  if (hasTabs) {
    // This is a visible human draft entered through the real editor, never
    // a fabricated model output or a runtime-tested migration claim.
    await setValue('#out', '-- Hand-authored synthetic draft (no AI model)\n-- Confirm page item and validation timing.\nreturn :P0_VL_PRECO is null\n    or :P0_VL_PRECO > 0;');
    await setValue('#comment', 'Synthetic local review only. Confirm page item and validation timing; runtime was not tested.');
    await shot('workbench-review');
    for (const view of ['source', 'proposal', 'evidence', 'compare']) {
      await click(`#view-${view}`);
      check(`Conversion ${view} view opens`, await evaluate(`document.querySelector('#review-workspace').dataset.view===${JSON.stringify(view)}`));
      if (view === 'evidence') await shot('conversion-evidence');
      if (view === 'source') await shot('workbench-source');
    }
    const second = await evaluate(`state.tasks.find(t=>t.id!==selected).id`);
    await evaluate(`select(${JSON.stringify(second)});select(${JSON.stringify(task)})`);
    check('Draft survives moving between units', await evaluate(`document.querySelector('#out').value.includes('Hand-authored synthetic draft')&&document.querySelector('#comment').value.includes('Synthetic local review')`));
    await evaluate(`refresh()`);
    check('Draft survives state refresh', await evaluate(`document.querySelector('#out').value.includes('Hand-authored synthetic draft')`));
    await setValue('#reviewer', 'Synthetic browser reviewer');
    await click('#btn-needs');
    await waitFor(() => evaluate(`state.tasks.find(t=>t.id===${JSON.stringify(task)})?.state==='needs_work'`), 'conversion review decision');
    check('Conversion review persists human decision', true);
    await evaluate(`select(${JSON.stringify(task)})`);
    await shot('conversion-reviewed');
  }
  for (const width of [720, 390]) {
    await viewport(width, 900);
    if (hasTabs) await click('#view-proposal');
    const d = await dimensions(false);
    check(`Conversion controls fit ${width}px`, d.documentWidth <= width + 1 && !d.overflow.length, d);
    await shot(`conversion-${width}`);
    if (hasTabs) {
      await click('#unit-toggle');
      check(`Unit drawer opens at ${width}px`, await evaluate(`document.querySelector('#unit-toggle').getAttribute('aria-expanded')==='true'`));
      await click('#unit-list .row');
      check(`Selecting a unit closes drawer at ${width}px`, await evaluate(`document.querySelector('#unit-toggle').getAttribute('aria-expanded')==='false'`));
    }
  }
  check('No page JavaScript exceptions', result.exceptions.length === 0, result.exceptions);
  check('No page request attempted outside the isolated Workbench', result.blockedRequests.length === 0, result.blockedRequests);
} catch (error) {
  result.error = String(error.stack || error);
  check('Acceptance completed', false, result.error);
  if (socket?.readyState === WebSocket.OPEN) await shot('failure').catch(() => {});
} finally {
  result.passed = result.checks.length > 0 && result.checks.every(c => c.passed);
  await fs.writeFile(path.join(root, 'result.json'), JSON.stringify(result, null, 2));
  if (socket?.readyState === WebSocket.OPEN) await send('Browser.close').catch(() => {});
  socket?.close();
  console.log(`${result.passed ? 'PASS' : 'FAIL'}: ${result.checks.filter(c => c.passed).length}/${result.checks.length} checks; ${result.screenshots.length} screenshots; ${path.join(root, 'result.json')}`);
  process.exitCode = result.passed ? 0 : 1;
}
