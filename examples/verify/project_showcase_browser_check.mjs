// FormsLang 2.2 showcase: the modernization lab walked through the real UI.
// The project is created in the browser from the lab's synthetic Forms XML and
// PL/SQL, analysed by the engine and traversed Estate -> Start Here -> hotspot
// -> System Map -> Review -> human decision -> architecture -> reports. Every
// expectation below is read from product state; nothing is staged.
export async function showcaseChecks({evaluate,click,clickSelector,value,wait,check,screenshot,send,pick,forms,database}){
  await click('project-home');await wait(()=>evaluate(`!!document.getElementById('project-new-estate')`),'showcase onboarding');
  await click('project-new-estate');await value('project-name','Legacy Order Management lab');await click('project-next');
  await click('project-forms');await pick(forms);await wait(()=>evaluate(`projectUI.draft.preview!==null&&projectUI.draft.sources.length===1`),'lab forms preview');
  await click('project-database');await pick(database);await wait(()=>evaluate(`projectUI.draft.preview!==null&&projectUI.draft.sources.length===2`),'lab database preview');
  await click('project-next');await wait(()=>evaluate(`!!document.querySelector('input[name="project-target"][value="unselected"]')`),'lab strategy');
  await click('project-next');await click('project-next');
  await wait(()=>evaluate(`projectUI.view==='overview'&&projectUI.summary?.project.name==='Legacy Order Management lab'&&!projectUI.jobId&&projectUI.overview?.assessment.freshness==='CURRENT'`),'lab Overview',180000);
  const id=await evaluate('projectUI.activeId');

  // 1. Estate and source coverage.
  check('showcase Estate Overview reports the lab inventory',await evaluate(`(()=>{const i=projectUI.overview.inventory;return i.forms_modules===4&&i.database_packages===5&&i.tables===11;})()`),await evaluate('projectUI.overview.inventory'));
  check('showcase hotspots come from the engine',await evaluate(`(()=>{const h=projectUI.overview.hotspots;return h.total===6&&h.by_type.api_bypass===2&&h.by_type.duplicated_rules===3&&h.by_type.global_state===1;})()`),await evaluate('projectUI.overview.hotspots'));
  check('showcase Overview draws estate, coverage and journey panels',await evaluate(`['visual-estate','visual-board','visual-journey'].every(id=>!!document.getElementById(id))&&!!document.getElementById('visual-coverage-title')`));
  await wait(()=>evaluate(`['visual-estate','visual-board','visual-journey'].every(id=>{const t=document.getElementById(id)?.textContent||'';return t&&!t.includes('Loading');})`),'Overview visuals');
  await screenshot('showcase-1-overview.png');

  // 2. Start Here explains its order.
  check('showcase Start Here explains why',await evaluate(`document.getElementById('project-priority').textContent.includes('Why:')&&document.querySelectorAll('#project-priority [data-start-here]').length>0`));

  // 3. Select an API bypass candidate in the Hotspot Explorer.
  await clickSelector('[data-visual-attention="hotspots"]');
  await wait(()=>evaluate(`projectUI.view==='hotspots'&&!!visualUI.hotspots.data`),'Hotspot Explorer');
  await evaluate(`(()=>{const s=document.getElementById('visual-hotspot-type');s.value='API_BYPASS_CANDIDATE';s.dispatchEvent(new Event('change',{bubbles:true}));})()`);
  await wait(()=>evaluate(`projectUI.view==='hotspots'&&visualUI.hotspots.data?.total===2&&visualUI.hotspots.data.items.every(h=>h.hotspot_type==='API_BYPASS_CANDIDATE')`),'API bypass filter');
  check('showcase API bypass candidate explains evidence and limits',await evaluate(`(()=>{const t=document.getElementById('project-content').textContent,h=visualUI.hotspots.data.items[0];return t.includes('Why FormsLang noticed this')&&t.includes('What this does NOT prove')&&h.uncertainty.length>0&&['APPROVALS','LOM_ORDERS'].every(n=>h.nodes.some(x=>x.name===n));})()`),await evaluate('visualUI.hotspots.data.items[0]?.nodes'));
  await screenshot('showcase-2-api-bypass.png');

  // 4. Show it on the System Map: Form -> package API -> table.
  const form=await evaluate(`visualUI.hotspots.data.items[0].nodes.find(n=>n.type==='FORM').id`);
  await clickSelector(`[data-hotspot-map="${form}"]`);
  await wait(()=>evaluate(`projectUI.view==='system-map'&&systemMapState.data?.focus===${JSON.stringify(form)}`),'map focused on APPROVALS');
  const path=await evaluate(`(()=>{const d=systemMapState.data,name=id=>d.nodes.find(n=>n.id===id)?.name;return d.edges.map(e=>[name(e.source),e.classification,name(e.target),!!e.is_hotspot].join(' '));})()`);
  check('showcase map shows the Form writing the table directly',path.includes('APPROVALS WRITES LOM_ORDERS true'),path);
  check('showcase map shows the package API writing the same table',path.includes('LOM_ORDER_API WRITES LOM_ORDERS true'),path);
  check('showcase map opens with the focus node in view',await evaluate(`(()=>{const c=document.getElementById('system-map-canvas').getBoundingClientRect(),n=document.querySelector('[data-node-id="${form}"]').getBoundingClientRect();return n.left>=c.left&&n.right<=c.right;})()`));
  check('showcase map keeps the return context',await evaluate(`document.getElementById('visual-back')?.textContent.includes('Hotspot')`));
  await screenshot('showcase-3-system-map.png');
  await clickSelector(`[data-node-id="${form}"]`);
  await wait(()=>evaluate(`(()=>{const t=document.getElementById('system-map-drawer')?.textContent||'';return t.includes('Identity')&&!t.includes('Loading');})()`),'inspector for APPROVALS');
  const squeezed=await evaluate(`[...document.querySelectorAll('#system-map-drawer .visual-drawer-section')].filter(s=>s.scrollHeight>s.clientHeight+1).map(s=>s.querySelector('h5')?.textContent)`);
  check('showcase map inspector sections do not overlap',squeezed.length===0,squeezed);

  // 5. Back to the candidate, then Review: FormsLang proposes, a human decides.
  await click('visual-back');await wait(()=>evaluate(`projectUI.view==='hotspots'&&!!document.querySelector('[data-hotspot-review]')`),'back to hotspots');
  check('showcase Back keeps the API bypass filter',await evaluate(`visualUI.hotspots.data.items.every(h=>h.hotspot_type==='API_BYPASS_CANDIDATE')`));
  await clickSelector('[data-hotspot-review]');
  await wait(()=>evaluate(`!!document.getElementById('project-review-defer')&&document.getElementById('visual-review-context')?.textContent.includes('Architecture context')`),'finding in Review');
  const finding=await evaluate('projectUI.reviewState.detail.item.id');
  check('showcase Review separates proposal from decision',await evaluate(`['3. Recommendation','4. Human decision','Engine recommendation (PROPOSED)'].every(t=>document.getElementById('project-review-detail').textContent.includes(t))`));
  const before=await evaluate(`(async()=>{const d=await api('/api/v2/projects/${id}/module-360?finding='+encodeURIComponent(${JSON.stringify(finding)}));return d.node.review_summary;})()`);

  // 6. Record a human decision and return to the architecture.
  await value('project-review-rationale','Architecture review: confirm whether LOM_ORDER_API must own every LOM_ORDERS write.');
  await click('project-review-defer');await wait(()=>evaluate(`document.getElementById('project-review-detail').textContent.includes('Deferred')`),'deferred decision');
  await wait(()=>evaluate(`!!document.getElementById('visual-review-module')`),'review context after decision');
  const deferred=(Number(before.deferred)||0)+1;
  check('showcase Review context shows the updated review state',await evaluate(`document.getElementById('visual-review-context').textContent.includes('${deferred} deferred')`),await evaluate(`document.getElementById('visual-review-context').textContent`));
  await screenshot('showcase-4-review-decision.png');
  await click('visual-review-module');await wait(()=>evaluate(`projectUI.view==='module-360'&&!!visualUI.module.data`),'Module 360 after decision');
  check('showcase Module 360 reflects the recorded decision',await evaluate(`(()=>{const r=visualUI.module.data.node.review_summary;return visualUI.module.data.node.name==='APPROVALS'&&Number(r.deferred)===${deferred}&&document.getElementById('project-content').textContent.includes('deferred');})()`),{before,after:await evaluate('visualUI.module.data.node.review_summary')});
  await screenshot('showcase-5-module-360.png');

  // 7. Deliver: the executive and technical reports carry the same picture.
  const reports=await evaluate(`(async()=>{const r=await api('/api/v2/projects/${id}/reports');const q=new URLSearchParams({...r.binding,include_notes:'0',include_artifacts:'0'});const out={};for(const kind of ['executive','technical']){const response=await fetch('/api/v2/projects/${id}/reports/'+kind+'?'+q,{credentials:'same-origin'});out[kind]={status:response.status,text:await response.text()};}return out;})()`);
  check('showcase executive report draws the estate and the attention matrix',reports.executive.status===200&&reports.executive.text.includes('Estate Architecture by Lane')&&reports.executive.text.includes('Possible API bypass')&&(reports.executive.text.match(/<figure/g)||[]).length===2,reports.executive.status);
  check('showcase technical report carries the same figures',reports.technical.status===200&&(reports.technical.text.match(/<figure/g)||[]).length===2,reports.technical.status);
  check('showcase reports contain no active SVG content',!/<script|foreignObject|onload=/i.test(reports.executive.text+reports.technical.text));
  await clickSelector('[data-project-section="reports"]');await wait(()=>evaluate(`projectUI.view==='reports'&&!!projectUI.reportsState?.data`),'Reports');
  await screenshot('showcase-6-reports.png');

  // 8. The 2.2 views at the release viewports: no page-level horizontal scroll.
  const initial=await evaluate('({width:innerWidth,height:innerHeight})');
  const views=[
    ['overview',async()=>{await clickSelector('[data-project-section="overview"]');await wait(()=>evaluate(`projectUI.view==='overview'&&!!document.getElementById('visual-board')?.textContent`),'Overview at viewport');}],
    ['system-map',async()=>{await clickSelector('[data-project-section="system-map"]');await wait(()=>evaluate(`projectUI.view==='system-map'&&!!systemMapState.data`),'System Map at viewport');}],
    ['hotspots',async()=>{await clickSelector('[data-project-section="hotspots"]');await wait(()=>evaluate(`projectUI.view==='hotspots'&&!!visualUI.hotspots.data`),'Hotspots at viewport');}],
    ['module-360',async()=>{await clickSelector(`[data-hotspot-module="${form}"]`);await wait(()=>evaluate(`projectUI.view==='module-360'&&!!visualUI.module.data`),'Module 360 at viewport');}],
  ];
  for(const [width,height] of [[1920,1080],[1440,900],[1366,768],[390,844]]){
    await send('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:false});
    await wait(()=>evaluate(`innerWidth===${width}`),`viewport ${width}`);
    const overflow=[];
    for(const [name,open] of views){await open();const wide=await evaluate('document.documentElement.scrollWidth-innerWidth');if(wide>1)overflow.push(`${name}+${wide}px`);if(width===1920&&name==='system-map')await screenshot('showcase-map-1920.png');if(width===390)await screenshot(`showcase-${name}-390.png`);}
    check(`showcase 2.2 views fit ${width}x${height} without page scroll`,overflow.length===0,overflow);
  }
  await send('Emulation.setDeviceMetricsOverride',{width:initial.width,height:initial.height,deviceScaleFactor:1,mobile:false});
}
