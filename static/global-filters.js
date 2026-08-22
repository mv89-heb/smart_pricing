(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const esc = s => String(s ?? '').replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const norm = s => String(s ?? '').trim().toLocaleLowerCase('he');

  function style() {
    if ($('global-filters-css')) return;
    const s = document.createElement('style'); s.id = 'global-filters-css';
    s.textContent = `.gf-bar{display:flex;flex-wrap:wrap;gap:.5rem;align-items:end;padding:.75rem;background:#f8fafc;border:1px solid #e2e8f0;border-radius:.75rem;margin-bottom:.75rem}.dark .gf-bar{background:#0f172a;border-color:#334155}.gf-field{display:flex;flex-direction:column;gap:.25rem;min-width:145px}.gf-field label{font-size:.68rem;font-weight:800;color:#64748b}.gf-field input,.gf-field select{padding:.45rem .65rem;border:1px solid #cbd5e1;border-radius:.55rem;background:white;font-size:.8rem;min-height:34px}.dark .gf-field input,.dark .gf-field select{background:#1e293b;color:#f8fafc;border-color:#475569}.gf-count{font-size:.72rem;font-weight:800;color:#64748b;margin-right:auto;align-self:center}.gf-clear{padding:.45rem .7rem;border-radius:.55rem;border:1px solid #cbd5e1;background:white;font-size:.75rem;font-weight:800}.dark .gf-clear{background:#1e293b;color:#f8fafc;border-color:#475569}.gf-hidden{display:none!important}`;
    document.head.appendChild(s);
  }
  const field=(label,type,id,extra='')=>`<div class="gf-field"><label for="${id}">${label}</label><${type} id="${id}" ${extra}></${type}>`;
  function bar(id,body){const b=document.createElement('div');b.id=id;b.className='gf-bar';b.innerHTML=body+`<span class="gf-count" id="${id}-count"></span><button type="button" class="gf-clear" id="${id}-clear">נקה סינון</button>`;return b;}

  function setupDaily(){
    if($('gf-daily'))return;
    const panel=$('left-panel'); if(!panel)return;
    const table=panel.querySelector('table'); const tbody=table?.querySelector('tbody'); if(!tbody)return;
    const b=bar('gf-daily',`${field('חיפוש','input','gf-daily-q','type="search" placeholder="מוצר / הערה"')} ${field('מוצר','select','gf-daily-product','')} ${field('סוג','select','gf-daily-type','')} ${field('מינ׳ סכום','input','gf-daily-min','type="number" step="0.01" placeholder="0"')} ${field('מקס׳ סכום','input','gf-daily-max','type="number" step="0.01" placeholder="ללא"')}`);
    table.parentElement.insertBefore(b,table);
    const apply=()=>{const q=norm($('gf-daily-q').value),p=norm($('gf-daily-product').value),t=$('gf-daily-type').value,min=Number($('gf-daily-min').value||0),max=$('gf-daily-max').value===''?Infinity:Number($('gf-daily-max').value);let visible=0,opts=new Set();[...tbody.rows].forEach(r=>{const text=norm(r.innerText);const cells=[...r.cells].map(c=>norm(c.innerText));if(cells[1])opts.add(cells[1]);const type=t==='extra'?'אקסטרה':t==='regular'?'שוטף':'';const total=parseFloat((r.cells[r.cells.length-2]?.innerText||'').replace(/[^\d.-]/g,''))||0;const ok=(!q||text.includes(q))&&(!p||cells[1]===p)&&(!type||text.includes(type))&&total>=min&&total<=max;r.classList.toggle('gf-hidden',!ok);if(ok)visible++;});const sel=$('gf-daily-product');const old=sel.value;sel.innerHTML='<option value="">כל המוצרים</option>'+[...opts].sort((a,b)=>a.localeCompare(b,'he')).map(x=>`<option value="${esc(x)}">${esc(x)}</option>`).join('');sel.value=opts.has(old)?old:'';$('gf-daily-count').textContent=`${visible} תוצאות`;};
    ['gf-daily-q','gf-daily-product','gf-daily-type','gf-daily-min','gf-daily-max'].forEach(id=>$(id).addEventListener(id==='gf-daily-q'?'input':'change',apply));$('gf-daily-clear').onclick=()=>{['gf-daily-q','gf-daily-product','gf-daily-type','gf-daily-min','gf-daily-max'].forEach(id=>$(id).value='');apply();};
    return {tbody,apply};
  }
  function setupPricing(){
    if($('gf-pricing'))return;
    const body=$('price-list-table-body');if(!body)return; const table=body.closest('table');
    const b=bar('gf-pricing',`${field('חיפוש מוצר','input','gf-pricing-q','type="search" placeholder="שם מוצר / תגית"')} ${field('מינ׳ מחיר','input','gf-pricing-min','type="number" step="0.01" placeholder="0"')} ${field('מקס׳ מחיר','input','gf-pricing-max','type="number" step="0.01" placeholder="ללא"')} ${field('מחירים עתידיים','select','gf-pricing-scheduled','<option value="">הכול</option><option value="yes">יש תאריך עתידי</option><option value="no">ללא</option>')}`);
    table.parentElement.insertBefore(b,table);
    const apply=()=>{const q=norm($('gf-pricing-q').value),min=Number($('gf-pricing-min').value||0),max=$('gf-pricing-max').value===''?Infinity:Number($('gf-pricing-max').value),scheduled=$('gf-pricing-scheduled').value;let visible=0;[...body.rows].forEach(r=>{const text=norm(r.innerText),price=parseFloat((r.cells[1]?.innerText||'').replace(/[^\d.-]/g,''))||0;const hasFuture=/מתאריך|עתידי|מ-/.test(text);const ok=(!q||text.includes(q))&&price>=min&&price<=max&&(!scheduled||(scheduled==='yes'&&hasFuture)||(scheduled==='no'&&!hasFuture));r.classList.toggle('gf-hidden',!ok);if(ok)visible++;});$('gf-pricing-count').textContent=`${visible} מוצרים`;};
    ['gf-pricing-q','gf-pricing-min','gf-pricing-max'].forEach(id=>$(id).addEventListener('input',apply));$('gf-pricing-scheduled').addEventListener('change',apply);$('gf-pricing-clear').onclick=()=>{['gf-pricing-q','gf-pricing-min','gf-pricing-max','gf-pricing-scheduled'].forEach(id=>$(id).value='');apply();};
    return {tbody:body,apply};
  }
  function setupDashboard(){
    if($('gf-dashboard'))return; const card=$('ux-detail-card');if(!card)return;const header=card.querySelector('.p-4');if(!header)return;
    const b=bar('gf-dashboard',`${field('מוצר','select','gf-dashboard-product','')} ${field('סוג חיוב','select','gf-dashboard-type','<option value="">כל הסוגים</option><option value="regular">שוטף</option><option value="extra">אקסטרה</option>')} ${field('מינ׳ סכום','input','gf-dashboard-min','type="number" step="0.01" placeholder="0"')} ${field('מקס׳ סכום','input','gf-dashboard-max','type="number" step="0.01" placeholder="ללא"')}`);
    header.insertAdjacentElement('afterend',b);const tbody=$('ux-entries');
    const apply=()=>{const p=norm($('gf-dashboard-product').value),t=$('gf-dashboard-type').value,min=Number($('gf-dashboard-min').value||0),max=$('gf-dashboard-max').value===''?Infinity:Number($('gf-dashboard-max').value);let opts=new Set(),visible=0;[...tbody.rows].forEach(r=>{const cells=[...r.cells].map(c=>norm(c.innerText));if(cells[1])opts.add(cells[1]);const total=parseFloat((r.cells[5]?.innerText||'').replace(/[^\d.-]/g,''))||0;const ok=(!p||cells[1]===p)&&(!t||(t==='extra'&&cells[3]?.includes('אקסטרה'))||(t==='regular'&&cells[3]?.includes('שוטף')))&&total>=min&&total<=max;r.classList.toggle('gf-hidden',!ok);if(ok)visible++;});const sel=$('gf-dashboard-product'),old=sel.value;sel.innerHTML='<option value="">כל המוצרים</option>'+[...opts].sort((a,b)=>a.localeCompare(b,'he')).map(x=>`<option value="${esc(x)}">${esc(x)}</option>`).join('');sel.value=opts.has(old)?old:'';$('gf-dashboard-count').textContent=`${visible} תוצאות`;};
    ['gf-dashboard-product','gf-dashboard-type'].forEach(id=>$(id).addEventListener('change',apply));['gf-dashboard-min','gf-dashboard-max'].forEach(id=>$(id).addEventListener('input',apply));$('gf-dashboard-clear').onclick=()=>{['gf-dashboard-product','gf-dashboard-type','gf-dashboard-min','gf-dashboard-max'].forEach(id=>$(id).value='');apply();};
    return {tbody,apply};
  }
  function setupPeriodic(){
    if($('gf-periodic'))return; const body=$('reportBody');if(!body)return; const table=body.closest('table');if(!table)return;
    const b=bar('gf-periodic',`${field('מוצר','select','gf-periodic-product','')} ${field('סוג','select','gf-periodic-type','<option value="">כל הסוגים</option><option value="regular">שוטף</option><option value="extra">אקסטרה</option>')} ${field('מינ׳ סכום','input','gf-periodic-min','type="number" step="0.01" placeholder="0"')} ${field('מקס׳ סכום','input','gf-periodic-max','type="number" step="0.01" placeholder="ללא"')}`);table.parentElement.insertBefore(b,table);
    const apply=()=>{const p=norm($('gf-periodic-product').value),t=$('gf-periodic-type').value,min=Number($('gf-periodic-min').value||0),max=$('gf-periodic-max').value===''?Infinity:Number($('gf-periodic-max').value);let opts=new Set(),visible=0;[...body.rows].forEach(r=>{const cells=[...r.cells].map(c=>norm(c.innerText));if(cells[1])opts.add(cells[1]);const total=parseFloat((r.cells[5]?.innerText||'').replace(/[^\d.-]/g,''))||0;const ok=(!p||cells[1]===p)&&(!t||(t==='extra'&&cells[2]?.includes('אקסטרה'))||(t==='regular'&&cells[2]?.includes('שוטף')))&&total>=min&&total<=max;r.classList.toggle('gf-hidden',!ok);if(ok)visible++;});const sel=$('gf-periodic-product'),old=sel.value;sel.innerHTML='<option value="">כל המוצרים</option>'+[...opts].sort((a,b)=>a.localeCompare(b,'he')).map(x=>`<option value="${esc(x)}">${esc(x)}</option>`).join('');sel.value=opts.has(old)?old:'';$('gf-periodic-count').textContent=`${visible} תוצאות`;};
    ['gf-periodic-product','gf-periodic-type'].forEach(id=>$(id).addEventListener('change',apply));['gf-periodic-min','gf-periodic-max'].forEach(id=>$(id).addEventListener('input',apply));$('gf-periodic-clear').onclick=()=>{['gf-periodic-product','gf-periodic-type','gf-periodic-min','gf-periodic-max'].forEach(id=>$(id).value='');apply();};
    return {tbody:body,apply};
  }

  let initialized = false;
  const watchers = [];
  function init() {
    style();
    if (!initialized) {
      const setups = [setupDaily(), setupPricing(), setupDashboard(), setupPeriodic()];
      setups.filter(Boolean).forEach(x => watchers.push(x));
      initialized = watchers.length > 0;
    }
    watchers.forEach(({tbody, apply}) => {
      if (!tbody || !document.contains(tbody)) return;
      if (tbody.dataset.gfObserved === '1') return;
      tbody.dataset.gfObserved = '1';
      new MutationObserver(apply).observe(tbody, {childList:true});
      apply();
    });
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
  let pending=false;
  new MutationObserver(() => { if(pending)return; pending=true; queueMicrotask(()=>{pending=false;init();}); }).observe(document.body,{childList:true,subtree:true});
})();