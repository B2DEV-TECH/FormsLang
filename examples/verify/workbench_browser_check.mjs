// Real Chromium CDP acceptance: no dependency installation or remote services.
import fs from 'node:fs/promises';
import path from 'node:path';

const root = path.resolve(process.argv[2]);
const config = JSON.parse(await fs.readFile(path.join(root, 'state.json'), 'utf8'));
const origin = new URL(config.url).origin;
const result = {fixture: 'tests/fixtures/showcase/module.xml', source_sha256: config.source_sha256, ui_sha256: config.ui_sha256, provider: 'offline synthetic stub; no model ran', desktop_viewport: {width: 1360, height: 695}, checks: [], screenshots: [], exceptions: [], blockedRequests: []};
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
let socket, next = 0, failNextSettings = false, exportResponseId = null;
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
async function settleMotion() {
  // Resize/navigation now animate. Measure the settled layout without disabling
  // transitions or excluding off-screen controls from the overflow checks.
  await evaluate(`(async()=>{
    await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));
    const finite=document.getAnimations().filter(a=>a.effect?.getComputedTiming().iterations!==Infinity);
    await Promise.all(finite.map(a=>a.finished.catch(()=>{})));
  })()`);
}
async function key(key, code, virtualKey, modifiers = 0) {
  await send('Input.dispatchKeyEvent', {type: 'keyDown', key, code, windowsVirtualKeyCode: virtualKey, modifiers, ...(key === 'Enter' ? {text:'\r',unmodifiedText:'\r'} : {})});
  await send('Input.dispatchKeyEvent', {type: 'keyUp', key, code, windowsVirtualKeyCode: virtualKey, modifiers});
  await settleMotion();
}
async function realClick(selector) {
  await settleMotion();
  const point = await evaluate(`(() => {
    const node=document.querySelector(${JSON.stringify(selector)});
    if(!node||node.disabled||node.closest('[inert]'))throw Error('Unavailable control: '+${JSON.stringify(selector)});
    const r=node.getBoundingClientRect(),x=r.left+r.width/2,y=r.top+r.height/2;
    const hit=document.elementFromPoint(x,y);
    if(!r.width||!r.height||getComputedStyle(node).visibility==='hidden'||!(node===hit||node.contains(hit)))
      throw Error('Control cannot receive a pointer: '+${JSON.stringify(selector)});
    return {x,y};
  })()`);
  await send('Input.dispatchMouseEvent', {type: 'mouseMoved', ...point});
  await send('Input.dispatchMouseEvent', {type: 'mousePressed', button: 'left', clickCount: 1, ...point});
  await send('Input.dispatchMouseEvent', {type: 'mouseReleased', button: 'left', clickCount: 1, ...point});
  await settleMotion();
}
async function realDrag(selector, dx, dy = 0) {
  await settleMotion();
  const point = await evaluate(`(() => {
    const node=document.querySelector(${JSON.stringify(selector)}),r=node.getBoundingClientRect(),x=r.left+r.width/2,y=r.top+r.height/2;
    const hit=document.elementFromPoint(x,y);
    if(!r.width||!r.height||node.closest('[inert]')||!(node===hit||node.contains(hit)))throw Error('Divider cannot receive pointer');
    return {x,y};
  })()`);
  await send('Input.dispatchMouseEvent', {type: 'mouseMoved', ...point});
  await send('Input.dispatchMouseEvent', {type: 'mousePressed', button: 'left', buttons: 1, clickCount: 1, ...point});
  for (let step = 1; step <= 8; step++) {
    await send('Input.dispatchMouseEvent', {type: 'mouseMoved', button: 'left', buttons: 1, x: point.x + dx * step / 8, y: point.y + dy * step / 8});
    await sleep(20);
  }
  await send('Input.dispatchMouseEvent', {type: 'mouseReleased', button: 'left', buttons: 0, clickCount: 1, x: point.x + dx, y: point.y + dy});
  await settleMotion();
}
async function realDoubleClick(selector) {
  await settleMotion();
  const point=await evaluate(`(()=>{const n=document.querySelector(${JSON.stringify(selector)}),r=n.getBoundingClientRect(),x=r.left+r.width/2,y=r.top+r.height/2,hit=document.elementFromPoint(x,y);if(!(n===hit||n.contains(hit)))throw Error('Divider unavailable');return{x,y};})()`);
  for (const clickCount of [1,2]) {
    await send('Input.dispatchMouseEvent',{type:'mousePressed',button:'left',clickCount,...point});
    await send('Input.dispatchMouseEvent',{type:'mouseReleased',button:'left',clickCount,...point});
  }
  await settleMotion();
}
async function reloadWorkbench(description, task) {
  const previousDocument = await evaluate('performance.timeOrigin');
  await send('Page.reload');
  await waitFor(() => evaluate(`performance.timeOrigin!==${previousDocument}&&typeof state!=='undefined'&&state.tasks.length>0`), description);
  if (task) await evaluate(`select(${JSON.stringify(task)})`);
  await settleMotion();
}
async function panelGeometry() {
  return evaluate(`(() => {
    const box=selector=>{const n=document.querySelector(selector);if(!n)return null;const r=n.getBoundingClientRect();return {width:r.width,height:r.height,left:r.left,right:r.right,top:r.top,bottom:r.bottom,visible:!!r.width&&!!r.height&&getComputedStyle(n).visibility!=='hidden'};};
    return {viewport:{width:innerWidth,height:innerHeight},units:box('#unit-list'),workspace:box('#review-workspace'),code:box('#review-code'),source:box('.source-pane'),proposal:box('.proposal-pane'),evidence:box('#notes'),head:box('#review-workspace .head'),metadata:box('#t-meta'),location:box('#t-where'),fields:box('.review-fields')};
  })()`);
}
async function separatorState(selector) {
  return evaluate(`(() => {const n=document.querySelector(${JSON.stringify(selector)});return {role:n.getAttribute('role'),orientation:n.getAttribute('aria-orientation'),min:Number(n.getAttribute('aria-valuemin')),max:Number(n.getAttribute('aria-valuemax')),value:Number(n.getAttribute('aria-valuenow')),label:n.getAttribute('aria-label'),text:n.getAttribute('aria-valuetext'),focusable:n.tabIndex===0};})()`);
}
async function layoutOption(name, checked) {
  if (await evaluate(`document.querySelector('#layout-toggle').getAttribute('aria-expanded')!=='true'`)) await realClick('#layout-toggle');
  if (await evaluate(`document.querySelector('#layout-${name}').checked!==${JSON.stringify(checked)}`)) await realClick('#layout-' + name);
  if (await evaluate(`document.querySelector('#layout-toggle').getAttribute('aria-expanded')==='true'`)) await realClick('#layout-toggle');
  await settleMotion();
}
async function resetPanels() {
  if (await evaluate(`document.querySelector('#layout-toggle').getAttribute('aria-expanded')!=='true'`)) await realClick('#layout-toggle');
  await realClick('#reset-layout');
  if (await evaluate(`document.querySelector('#layout-toggle').getAttribute('aria-expanded')==='true'`)) await realClick('#layout-toggle');
  await settleMotion();
}
async function exercisePanelsWithDraft() {
  console.log('Exercising panel resizing, folding and focus with an unsaved review draft...');
  const initial = await panelGeometry();
  check('1360x695 prioritizes code with secondary evidence initially folded', initial.code.height >= 200 && !initial.evidence.visible, initial);
  const navBefore = await evaluate(`document.querySelector('#app-nav').getBoundingClientRect().width`);
  await realClick('#nav-collapse');
  const navCollapsed = await evaluate(`({width:document.querySelector('#app-nav').getBoundingClientRect().width,expanded:document.querySelector('#nav-collapse').getAttribute('aria-expanded'),persisted:localStorage.getItem('formslang.navigation')})`);
  check('Navigation folds from its visible control and returns workspace width', navCollapsed.width < navBefore - 80 && navCollapsed.expanded === 'false' && navCollapsed.persisted === 'collapsed', navCollapsed);
  await key('Enter', 'Enter', 13);
  await settleMotion();
  check('Keyboard expands navigation again', await evaluate(`document.querySelector('#nav-collapse').getAttribute('aria-expanded')==='true'`));

  for (const selector of ['#units-splitter', '#code-splitter']) {
    const a = await separatorState(selector);
    check(`${selector} exposes accessible resizing limits`, a.role === 'separator' && a.orientation === 'vertical' && a.focusable && a.label && a.text && a.min < a.max && a.value >= a.min && a.value <= a.max, a);
  }
  const unitsBefore = (await panelGeometry()).units.width;
  await realDrag('#units-splitter', 70);
  const unitsAfter = (await panelGeometry()).units.width;
  check('Dragging the unit divider changes actual pane width', unitsAfter > unitsBefore + 35, {before: unitsBefore, after: unitsAfter});
  await realClick('#units-splitter');
  await key('ArrowLeft', 'ArrowLeft', 37);
  check('Arrow key resizes the focused unit divider', (await panelGeometry()).units.width < unitsAfter);
  await key('Home', 'Home', 36);
  const unitMin = await separatorState('#units-splitter');
  check('Home reaches the unit divider minimum', Math.abs(unitMin.value - unitMin.min) <= 1, unitMin);
  await key('End', 'End', 35);
  const unitMax = await separatorState('#units-splitter');
  check('End reaches the unit divider maximum without losing the editor', Math.abs(unitMax.value - unitMax.max) <= 1 && (await panelGeometry()).code.width >= 320, unitMax);
  const shortcutState = `JSON.stringify({selected,state:state.tasks.find(t=>t.id===selected)?.state,code:document.querySelector('#out').value,note:document.querySelector('#comment').value,toast:document.querySelector('#toast').textContent,running:!!job?.running})`;
  const beforeShortcuts = await evaluate(shortcutState), shortcutResults = [];
  for (const [letter, code] of [['a',65],['r',82],['w',87],['p',80],['j',74],['k',75]]) {
    await key(letter, 'Key' + letter.toUpperCase(), code);
    shortcutResults.push({key:letter,unchanged:await evaluate(shortcutState)===beforeShortcuts});
  }
  check('Focused dividers do not trigger review or conversion shortcuts', shortcutResults.every(r=>r.unchanged), shortcutResults);
  await realDoubleClick('#units-splitter');
  check('A deliberate double-click restores the default unit width', Math.abs((await panelGeometry()).units.width - 260) <= 1);
  await resetPanels();

  const sourceBefore = (await panelGeometry()).source.width;
  await realDrag('#code-splitter', 80);
  const sourceAfter = (await panelGeometry()).source.width;
  check('Dragging the code divider redistributes source and proposal widths', sourceAfter > sourceBefore + 35 && (await panelGeometry()).proposal.width >= 160, {before: sourceBefore, after: sourceAfter});
  await realClick('#code-splitter');
  await key('ArrowLeft', 'ArrowLeft', 37, 8);
  check('Shift-arrow adjusts the code divider by keyboard', (await panelGeometry()).source.width < sourceAfter);
  await layoutOption('evidence', true);
  const evidenceBefore = await separatorState('#evidence-splitter');
  check('Evidence can open as a resizable lower pane', evidenceBefore.orientation === 'horizontal' && (await panelGeometry()).evidence.visible, evidenceBefore);
  await realDrag('#evidence-splitter', 0, -40);
  const evidenceAfter = await separatorState('#evidence-splitter');
  check('Dragging the evidence divider changes its height within limits', Math.abs(evidenceAfter.value - evidenceBefore.value) >= 15 && evidenceAfter.value >= evidenceAfter.min && evidenceAfter.value <= evidenceAfter.max, evidenceAfter);
  await realClick('#evidence-splitter');
  await key('Home', 'Home', 36);
  const evidenceMin = await separatorState('#evidence-splitter');
  check('Evidence divider keyboard minimum preserves both panes', Math.abs(evidenceMin.value - evidenceMin.min) <= 1 && (await panelGeometry()).code.height >= 100, evidenceMin);
  await realClick('#evidence-close');
  check('Evidence folds while keeping code visible', !(await panelGeometry()).evidence.visible && (await panelGeometry()).code.height >= 200);

  const beforeFold = await panelGeometry();
  await realClick('#unit-close');
  const afterFold = await panelGeometry();
  check('Unit list folds and gives its width to the editor', !afterFold.units.visible && afterFold.code.width > beforeFold.code.width + 100 && await evaluate(`document.querySelector('#unit-toggle').getAttribute('aria-expanded')==='false'`), afterFold);
  await realClick('#unit-toggle');
  check('Units can be restored from the review toolbar', (await panelGeometry()).units.visible);
  await layoutOption('details', false);
  await layoutOption('fields', false);
  const folded = await panelGeometry();
  check('Metadata and reviewer fields fold while preserving the unit title', !folded.metadata.visible && !folded.location.visible && !folded.fields.visible && folded.head.visible, folded);
  await layoutOption('details', true);
  await layoutOption('fields', true);
  check('Restoring reviewer fields keeps the typed note', await evaluate(`document.querySelector('#comment').value.includes('Synthetic local review')`));

  const originalDraft = await evaluate(`document.querySelector('#out').value`);
  await setValue('#out', originalDraft + '\n' + Array.from({length: 60}, (_, index) => `-- Synthetic scroll fixture ${index} ` + 'x'.repeat(170)).join('\n'));
  await realDrag('#code-splitter', -35);
  await evaluate(`(() => {const editor=document.querySelector('#out');editor.scrollTop=160;editor.scrollLeft=90;editor.dispatchEvent(new Event('scroll'));})()`);
  const overlay = await evaluate(`(() => {
    const editor=document.querySelector('#out'),overlay=document.querySelector('#out-hl'),a=getComputedStyle(editor),b=getComputedStyle(overlay);
    return {sameMetrics:['fontFamily','fontSize','lineHeight','letterSpacing','paddingTop','paddingLeft'].every(key=>a[key]===b[key]),editorTop:editor.scrollTop,overlayTop:overlay.scrollTop,editorLeft:editor.scrollLeft,overlayLeft:overlay.scrollLeft,hasDraft:editor.value.includes('Synthetic scroll fixture 59')};
  })()`);
  check('Divider resizing preserves textarea highlight metrics and both scroll axes', overlay.sameMetrics && overlay.editorTop > 0 && Math.abs(overlay.editorTop - overlay.overlayTop) <= 1 && Math.abs(overlay.editorLeft - overlay.overlayLeft) <= 1 && overlay.hasDraft, overlay);
  await setValue('#out', originalDraft);
  await evaluate(`document.querySelector('#out').scrollTop=0;document.querySelector('#out').scrollLeft=0;document.querySelector('#out').dispatchEvent(new Event('scroll'))`);

  const prefsBeforeFocus = await evaluate(`localStorage.getItem('formslang.workspace-layout.v1')`);
  const beforeFocus = await panelGeometry();
  await realClick('#focus-code');
  const focused = await panelGeometry();
  check('Focus expands the code workspace without discarding review context', await evaluate(`document.body.classList.contains('workspace-focus')&&document.querySelector('#focus-code').getAttribute('aria-pressed')==='true'`) && focused.code.width > beforeFocus.code.width && focused.code.height >= beforeFocus.code.height, focused);
  await shot('workbench-focus');
  await realClick('#src');
  await key('d', 'KeyD', 68);
  await waitFor(() => evaluate(`document.querySelector('#modal').classList.contains('show')`), 'project dialog within focused workspace');
  await key('Escape', 'Escape', 27);
  check('Closing a dialog preserves workspace focus and returns to visible source', await evaluate(`document.body.classList.contains('workspace-focus')&&!document.querySelector('#modal').classList.contains('show')&&document.activeElement.id==='src'&&document.activeElement.getClientRects().length>0`));
  await key('Escape', 'Escape', 27);
  await settleMotion();
  check('Escape restores the panel layout and focus control', await evaluate(`!document.body.classList.contains('workspace-focus')&&document.activeElement.id==='focus-code'`));
  check('Focus mode does not rewrite persisted panel preferences', await evaluate(`localStorage.getItem('formslang.workspace-layout.v1')===${JSON.stringify(prefsBeforeFocus)}`));
  await resetPanels();
  const reset = await panelGeometry();
  check('Reset restores code-first defaults at the user viewport', reset.units.visible && !reset.metadata.visible && !reset.location.visible && !reset.fields.visible && !reset.evidence.visible && Math.abs(reset.source.width - reset.proposal.width) < 15, reset);
  check('Resizing, folding, focus and reset preserve unsaved source edits and notes', await evaluate(`document.querySelector('#out').value.includes('Hand-authored synthetic draft')&&document.querySelector('#comment').value.includes('Synthetic local review')`));
  const d = await dimensions(false);
  check('All review controls fit the 1360x695 user viewport after layout changes', d.documentWidth <= 1361 && !d.overflow.length, d);
}
async function exercisePanelPersistence(task) {
  console.log('Exercising saved layout preferences and viewport clamps...');
  await viewport(1920, 1080);
  await layoutOption('evidence', true);
  const rail = await separatorState('#evidence-splitter');
  check('Wide desktop evidence uses a vertical divider', rail.orientation === 'vertical', rail);
  await realDrag('#evidence-splitter', -50);
  const resizedRail = await separatorState('#evidence-splitter');
  check('Wide evidence width responds to pointer dragging', Math.abs(resizedRail.value - rail.value) >= 20, resizedRail);
  await realClick('#units-splitter');
  await key('End', 'End', 35);
  const wideUnits = await separatorState('#units-splitter');
  await realDrag('#code-splitter', 40);
  await viewport(1000, 695);
  const narrow = await separatorState('#units-splitter');
  const narrowDimensions = await dimensions(false);
  check('Saved wide-pane dimensions clamp when viewport shrinks', narrow.value <= narrow.max && narrow.value >= narrow.min && narrowDimensions.documentWidth <= 1001 && !narrowDimensions.overflow.length, {divider: narrow, layout: narrowDimensions});
  await viewport(1920, 1080);
  check('Returning to a wide viewport restores the requested unit width', Math.abs((await separatorState('#units-splitter')).value - wideUnits.value) <= 2);
  await viewport(1360, 695);
  await layoutOption('evidence', false);
  await layoutOption('details', false);
  await layoutOption('fields', false);
  await realClick('#unit-close');
  await realClick('#nav-collapse');
  const saved = await evaluate(`JSON.parse(localStorage.getItem('formslang.workspace-layout.v1'))`);
  check('Saved panel preferences contain only layout settings', saved.version === 1 && Object.values(saved).every(value => ['number', 'boolean'].includes(typeof value)) && !JSON.stringify(saved).includes('Hand-authored'), saved);
  await reloadWorkbench('reloaded panel preferences', task);
  const restored = await panelGeometry();
  const loaded = await evaluate(`JSON.parse(localStorage.getItem('formslang.workspace-layout.v1'))`);
  check('Panel visibility and dimensions persist after reload', !restored.units.visible && !restored.metadata.visible && !restored.location.visible && !restored.fields.visible && !restored.evidence.visible && ['unitsWidth','codeRatio','evidenceWidth','evidenceHeight'].every(key => loaded[key] === saved[key]), {saved, loaded});
  check('Navigation collapse persists after reload', await evaluate(`document.body.classList.contains('nav-collapsed')&&document.querySelector('#nav-collapse').getAttribute('aria-expanded')==='false'`));
  check('Saved review code remains intact after layout reload', await evaluate(`document.querySelector('#out').value.includes('Hand-authored synthetic draft')`));
  await realClick('#nav-collapse');
  await resetPanels();
  await viewport(390, 844);
  await realClick('#view-compare');
  const mobileSplit = await separatorState('#code-splitter');
  check('Mobile compare uses a horizontal accessible divider', mobileSplit.orientation === 'horizontal', mobileSplit);
  await realDrag('#code-splitter', 0, 28);
  const mobileAfter = await separatorState('#code-splitter');
  check('Mobile code divider resizes the stacked panes within bounds', Math.abs(mobileAfter.value - mobileSplit.value) > 1 && mobileAfter.value >= mobileAfter.min && mobileAfter.value <= mobileAfter.max, mobileAfter);
  const mobileDims = await dimensions(false);
  check('Resizable compare controls fit 390px', mobileDims.documentWidth <= 391 && !mobileDims.overflow.length, mobileDims);
  await shot('workbench-mobile-compare');
  await viewport(1360, 695);
  await resetPanels();
}
async function exerciseLayoutRecovery(task) {
  console.log('Exercising corrupt preferences and unavailable browser storage...');
  for (const [name, stored] of [
    ['malformed JSON', '{"version":1'],
    ['out-of-range values', JSON.stringify({version:1,unitsWidth:1e20,codeRatio:-1e20,evidenceWidth:-300,evidenceHeight:1e20,units:true,evidence:false,details:true,fields:true,filters:false})],
  ]) {
    await evaluate(`localStorage.setItem('formslang.workspace-layout.v1',${JSON.stringify(stored)})`);
    await reloadWorkbench(name + ' recovery', task);
    const units = await separatorState('#units-splitter'), code = await separatorState('#code-splitter'), d = await dimensions(false);
    check(`Layout recovers usable finite bounds from ${name}`, [units,code].every(a=>[a.value,a.min,a.max].every(Number.isFinite)&&a.min<a.max&&a.value>=a.min&&a.value<=a.max) && d.documentWidth <= 1361 && !d.overflow.length, {units,code,dimensions:d});
    await resetPanels();
  }
  const injected = await send('Page.addScriptToEvaluateOnNewDocument', {source: `for(const method of ['getItem','setItem','removeItem'])Storage.prototype[method]=function(){throw new DOMException('Synthetic unavailable storage','SecurityError');};`});
  try {
    await reloadWorkbench('Workbench with storage unavailable', task);
    const before = (await panelGeometry()).units.width;
    await realDrag('#units-splitter', 45);
    await realClick('#nav-collapse');
    check('Panels and navigation remain usable when storage is blocked', (await panelGeometry()).units.width > before + 20 && await evaluate(`document.querySelector('#nav-collapse').getAttribute('aria-expanded')==='false'`));
    await realClick('#focus-code');
    await key('Escape', 'Escape', 27);
    check('Focus restores when storage is blocked', await evaluate(`!document.body.classList.contains('workspace-focus')&&document.querySelector('#out').value.includes('Hand-authored synthetic draft')`));
  } finally {
    await send('Page.removeScriptToEvaluateOnNewDocument', {identifier: injected.identifier});
    await reloadWorkbench('normal storage restored', task);
  }
}
async function contrastSamples() {
  return evaluate(`(() => {
    const parse=value=>{const n=value.match(/[\\d.]+/g)?.map(Number)||[0,0,0];return [...n.slice(0,3),n.length>3?n[3]:1];};
    const over=(a,b)=>{const alpha=a[3]+b[3]*(1-a[3]);return [0,1,2].map(i=>(a[i]*a[3]+b[i]*b[3]*(1-a[3]))/alpha).concat(alpha);};
    const background=node=>{const stack=[];for(let n=node;n;n=n.parentElement)stack.push(parse(getComputedStyle(n).backgroundColor));return stack.reverse().reduce((b,a)=>over(a,b),[255,255,255,1]);};
    const lum=rgb=>rgb.slice(0,3).map(v=>{v/=255;return v<=.04045?v/12.92:Math.pow((v+.055)/1.055,2.4);}).reduce((s,v,i)=>s+v*[.2126,.7152,.0722][i],0);
    return ['#workspace-title','.workspace-eyebrow','.nav-item[aria-current="page"]','#q','#btn-export','#reviewer','.nav-credit'].map(selector=>{
      const node=document.querySelector(selector),bg=background(node),fg=over(parse(getComputedStyle(node).color),bg),a=lum(fg),b=lum(bg);
      return {selector,ratio:Number(((Math.max(a,b)+.05)/(Math.min(a,b)+.05)).toFixed(2)),foreground:getComputedStyle(node).color,background:bg.slice(0,3)};
    });
  })()`);
}
async function shot(name) {
  await waitFor(() => evaluate(`!document.querySelector('#toast.show')&&(!document.querySelector('#toast')||getComputedStyle(document.querySelector('#toast')).opacity==='0')`), 'notification to settle', 10000);
  // Wait for fonts and two animation frames so captures reflect painted UI.
  await evaluate(`(async()=>{await document.fonts.ready;await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));})()`);
  await settleMotion();
  const data = await send('Page.captureScreenshot', {format: 'png'});
  await fs.writeFile(path.join(root, `${name}.png`), Buffer.from(data.data, 'base64'));
  result.screenshots.push(`${name}.png`);
}
async function viewport(width, height = 695) {
  await send('Emulation.setDeviceMetricsOverride', {width, height, deviceScaleFactor: 1, mobile: false});
  await settleMotion();
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
    } else if (message.method === 'Network.responseReceived' && message.params.response.url === origin + '/api/export') {
      exportResponseId = message.params.requestId;
    } else if (message.method === 'Fetch.requestPaused') {
      const {requestId, request} = message.params;
      if (failNextSettings && request.url === origin + '/api/settings') {
        failNextSettings = false;
        void send('Fetch.fulfillRequest', {requestId, responseCode: 503,
          responseHeaders: [{name: 'content-type', value: 'application/json'}],
          body: Buffer.from(JSON.stringify({error: 'Synthetic settings availability failure'})).toString('base64'),
        }).catch(error => result.exceptions.push(String(error)));
        return;
      }
      const allowed = request.url.startsWith(origin + '/') || request.url.startsWith('data:');
      if (!allowed) result.blockedRequests.push(request.url);
      void send(allowed ? 'Fetch.continueRequest' : 'Fetch.failRequest', allowed ? {requestId} : {requestId, errorReason: 'BlockedByClient'}).catch(error => result.exceptions.push(String(error)));
    }
  };
  await send('Runtime.enable');
  await send('Network.enable');
  await send('Page.enable');
  await send('Browser.setDownloadBehavior', {behavior: 'allow', downloadPath: root});
  await send('Fetch.enable', {patterns: [{urlPattern: '*'}]});
  await viewport(1360);
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
  await viewport(1360);
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
    await exercisePanelsWithDraft();
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
    await exercisePanelPersistence(task);
    await exerciseLayoutRecovery(task);
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
  console.log('Exercising theme persistence, contrast and keyboard-accessible navigation...');
  await viewport(1360, 695);
  await evaluate(`select(${JSON.stringify(task)})`);
  for (const theme of ['light', 'dark']) {
    if (await evaluate(`document.documentElement.dataset.theme!==${JSON.stringify(theme)}`)) await realClick('#theme-toggle');
    await settleMotion();
    check(`${theme} theme changes from its visible control`, await evaluate(`document.documentElement.dataset.theme===${JSON.stringify(theme)}&&document.querySelector('#theme-toggle').getAttribute('aria-pressed')===${JSON.stringify(String(theme === 'light'))}`));
    const contrast = await contrastSamples();
    check(`${theme} theme primary and secondary text contrast meets 4.5:1`, contrast.every(sample => sample.ratio >= 4.5), contrast);
    await reloadWorkbench('reloaded Workbench', task);
    check(`${theme} theme persists after reload`, await evaluate(`document.documentElement.dataset.theme===${JSON.stringify(theme)}`));
    await evaluate(`select(${JSON.stringify(task)})`);
    await shot(`workbench-${theme}`);
  }
  await viewport(1600, 1000);
  await realClick('#btn-settings');
  await waitFor(() => evaluate(`document.querySelector('#modal').classList.contains('show')&&document.querySelector('#modal-title').textContent.includes('Settings')`), 'settings dialog');
  check('Settings moves focus into its dialog', await evaluate(`document.querySelector('#modal').contains(document.activeElement)`));
  await key('Tab', 'Tab', 9);
  check('Tab remains in settings', await evaluate(`document.querySelector('#modal').contains(document.activeElement)`));
  await key('Tab', 'Tab', 9, 8);
  check('Shift-Tab wraps within settings', await evaluate(`document.querySelector('#modal').contains(document.activeElement)`));
  await shot('settings-desktop');
  await key('Escape', 'Escape', 27);
  check('Escape closes settings and restores opener focus', await evaluate(`!document.querySelector('#modal').classList.contains('show')&&document.activeElement.id==='btn-settings'`));
  failNextSettings = true;
  await realClick('#btn-settings');
  await waitFor(() => evaluate(`document.querySelector('#toast').textContent.includes('Synthetic settings availability failure')`), 'injected settings failure');
  check('Failed settings request restores the Review navigation state', await evaluate(`!document.querySelector('#modal').classList.contains('show')&&document.querySelector('#btn-review').getAttribute('aria-current')==='page'&&!document.querySelector('#btn-settings').hasAttribute('aria-current')`));
  await realClick('#btn-settings');
  await waitFor(() => evaluate(`document.querySelector('#modal').classList.contains('show')`), 'settings before resize');
  await viewport(390, 844);
  await key('Escape', 'Escape', 27);
  check('Resizing an open desktop dialog restores focus to the visible mobile menu', await evaluate(`!document.querySelector('#modal').classList.contains('show')&&document.activeElement.id==='nav-toggle'&&getComputedStyle(document.activeElement).visibility!=='hidden'`));
  check('Closed mobile navigation is hidden from interaction', await evaluate(`getComputedStyle(document.querySelector('#app-nav')).visibility==='hidden'&&!document.body.classList.contains('nav-open')`));
  await realClick('#nav-toggle');
  check('Mobile navigation opens and takes focus', await evaluate(`document.querySelector('#nav-toggle').getAttribute('aria-expanded')==='true'&&!document.querySelector('#app-nav').inert&&document.activeElement.id==='nav-close'`));
  await settleMotion();
  await key('Tab', 'Tab', 9, 8);
  check('Mobile navigation traps backward Tab', await evaluate(`document.querySelector('#app-nav').contains(document.activeElement)&&document.activeElement.id!=='nav-close'`));
  await key('Tab', 'Tab', 9);
  check('Mobile navigation wraps forward Tab', await evaluate(`document.activeElement.id==='nav-close'`));
  await shot('navigation-mobile');
  await key('Escape', 'Escape', 27);
  await settleMotion();
  check('Escape closes navigation and restores menu focus', await evaluate(`document.querySelector('#nav-toggle').getAttribute('aria-expanded')==='false'&&document.activeElement.id==='nav-toggle'&&getComputedStyle(document.querySelector('#app-nav')).visibility==='hidden'`));
  await realClick('#nav-toggle');
  await realClick('#btn-settings');
  await waitFor(() => evaluate(`document.querySelector('#modal').classList.contains('show')`), 'mobile settings');
  check('Mobile settings opens from navigation and closes drawer', await evaluate(`!document.body.classList.contains('nav-open')&&document.querySelector('#modal').contains(document.activeElement)`));
  await settleMotion();
  const settingsDimensions = await dimensions(false);
  check('Settings controls fit 390px', settingsDimensions.documentWidth <= 391 && !settingsDimensions.overflow.length, settingsDimensions);
  await shot('settings-mobile');
  await key('Escape', 'Escape', 27);
  check('Closing mobile settings restores visible menu focus', await evaluate(`!document.querySelector('#modal').classList.contains('show')&&document.activeElement.id==='nav-toggle'`));
  await evaluate(`document.activeElement.blur()`);
  await key('/', 'Slash', 191);
  check('Slash opens the mobile unit search', await evaluate(`document.querySelector('#unit-toggle').getAttribute('aria-expanded')==='true'&&document.activeElement.id==='q'`));
  await key('Escape', 'Escape', 27);
  check('Escape closes unit search and restores its opener focus', await evaluate(`document.querySelector('#unit-toggle').getAttribute('aria-expanded')==='false'&&document.activeElement.id==='unit-toggle'`));
  console.log('Capturing current project, evidence and offline export views...');
  await viewport(1600, 1000);
  await realClick('#view-evidence');
  if (await evaluate(`!!document.querySelector('#notes details summary')`)) await realClick('#notes details summary');
  await shot('unit-review-risk-panel');
  await realClick('#view-compare');
  await realClick('#btn-dash');
  await waitFor(() => evaluate(`!!document.querySelector('#modal-body .dash')`), 'project metrics');
  await shot('project-view');
  await realClick('#modal-close');
  await realClick('#btn-export');
  await waitFor(() => evaluate(`!!document.querySelector('.bind-section')&&!document.querySelector('.bind-section').hidden`), 'export binding choices');
  check('Export defaults keep AI layout and database import disabled', await evaluate(`!document.querySelector('[name="ai_layout"]').checked&&!document.querySelector('[name="import_now"]').checked`));
  await evaluate(`document.querySelector('#modal-body').scrollTop=0;document.querySelector('.sheet').scrollTop=0`);
  await shot('export-dialog');
  await realClick('#modal-go');
  const exported = await waitFor(async () => {
    if (!exportResponseId) return false;
    const body = await send('Network.getResponseBody', {requestId: exportResponseId});
    return JSON.parse(body.base64Encoded ? Buffer.from(body.body,'base64').toString('utf8') : body.body);
  }, 'real export API response');
  const zipExists = exported.zip && path.resolve(exported.zip).startsWith(root + path.sep) && (await fs.stat(exported.zip)).size > 0;
  check('Export builds a real local ZIP with inspectable binding metadata', zipExists && Array.isArray(exported.data_binding), {zip:exported.zip,bindingEntries:exported.data_binding?.length});
  if (exported.data_binding.length) {
    await waitFor(() => evaluate(`document.querySelector('#modal-go').textContent==='Show exports'&&!document.querySelector('.import-result').hidden`), 'binding result after local export');
    check('Binding results remain readable before opening export history', await evaluate(`document.querySelector('.import-result').textContent.includes('Bound:')||document.querySelector('.import-result').textContent.includes('Unbound:')`));
    await evaluate(`document.querySelector('.import-result').scrollIntoView({block:'nearest'})`);
  } else {
    await waitFor(() => evaluate(`!!document.querySelector('.exports-list .exp-row.fresh')`), 'export history without binding candidates');
    check('An export without binding candidates opens its history directly', true);
  }
  await shot('export-ready');
  if (exported.data_binding.length) await realClick('#modal-go');
  await waitFor(() => evaluate(`!!document.querySelector('.exports-list .exp-row.fresh')`), 'fresh export history row');
  const exports = await evaluate(`api('/api/exports')`);
  check('Show exports highlights the newly built ZIP using its basename', exports.exports.length>0&&await evaluate(`document.querySelector('.exp-row.fresh .exp-name').textContent.endsWith('.zip')&&!document.querySelector('.exp-row.fresh .exp-name').textContent.includes('\\\\')`));
  await shot('exports');
  await realClick('#modal-close');
  await send('Emulation.setEmulatedMedia', {features: [{name: 'prefers-reduced-motion', value: 'reduce'}]});
  check('Reduced motion removes navigation and control transitions', await evaluate(`getComputedStyle(document.querySelector('#app-nav')).transitionDuration==='0s'&&getComputedStyle(document.querySelector('#nav-toggle')).transitionDuration==='0s'`));
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
