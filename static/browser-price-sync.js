(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const esc = s => String(s ?? '').replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const today = () => { const d=new Date(); d.setMinutes(d.getMinutes()-d.getTimezoneOffset()); return d.toISOString().slice(0,10); };
  async function api(url,opt={}) { opt.credentials='same-origin'; opt.headers={...(opt.headers||{})}; if(['POST','PUT','PATCH','DELETE'].includes((opt.method||'GET').toUpperCase())) opt.headers['X-Requested-With']='XMLHttpRequest'; const r=await fetch(url,opt); if(r.status===401){location.href='/login';return null;} return r; }
  function toast(msg,error=false){if(typeof window.showToast==='function')return window.showToast(msg,error?'error':'success');alert(msg)}
  async function getProducts(){
    const r=await api('/api/products'); if(!r?.ok)return [];
    const data=await r.json().catch(()=>({}));
    const list=Array.isArray(data)?data:Object.entries(data||{}).map(([name,price])=>({name,price}));
    return list.map(p=>({name:String(p.name||'').trim(),current_price:Number(p.price ?? p.current_price ?? 0)||0,tag:p.tag||''})).filter(p=>p.name).sort((a,b)=>a.name.localeCompare(b.name,'he',{sensitivity:'base'}));
  }
  function install(){
    const panel=$('right-panel'); if(!panel||$('browser-price-sync-btn'))return true;
    const btn=document.createElement('button');btn.id='browser-price-sync-btn';btn.type='button';btn.className='text-xs font-bold text-indigo-700 dark:text-indigo-300 bg-indigo-50 dark:bg-indigo-950/40 hover:bg-indigo-100 px-2.5 py-1.5 rounded-lg transition-colors flex items-center gap-1';btn.innerHTML='<i class="fa-solid fa-globe"></i> עדכון מחירים';btn.addEventListener('click',open);
    const heading=panel.querySelector('h2');
    if(heading?.parentElement) heading.parentElement.appendChild(btn); else panel.prepend(btn);
    return true;
  }
  function open(){
    if($('browser-price-modal'))return;
    const effective=localStorage.getItem('global_price_effective_from')||today();
    const modal=document.createElement('div');modal.id='browser-price-modal';modal.className='fixed inset-0 z-[10000] bg-slate-950/60 backdrop-blur-sm flex items-center justify-center p-4';
    modal.innerHTML=`<div class="w-full max-w-6xl max-h-[90vh] overflow-hidden rounded-2xl bg-white dark:bg-slate-900 shadow-2xl" dir="rtl"><div class="p-5 border-b dark:border-slate-700 flex justify-between items-center"><div><h3 class="text-xl font-extrabold">עדכון מחירים חד־פעמי</h3><p class="text-xs text-slate-500 mt-1">כל מוצרי המחירון יוצגו. החיפוש מתבצע ללא API והמחירים לא משתנים לפני אישור.</p></div><button id="browser-price-close" class="text-slate-400 text-xl"><i class="fa-solid fa-xmark"></i></button></div><div class="p-5 overflow-y-auto max-h-[65vh]"><div class="flex flex-col sm:flex-row gap-3 items-end mb-4"><div class="flex-1"><label class="block text-xs font-bold text-slate-500 mb-1">תאריך תוקף לכל העדכונים</label><input id="browser-price-effective" type="date" value="${effective}" class="w-full px-3 py-2 rounded-lg border dark:border-slate-700 bg-white dark:bg-slate-950"></div><button id="browser-price-search" class="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-bold"><i class="fa-solid fa-magnifying-glass"></i> התחל בדיקה</button></div><div class="flex gap-2 flex-wrap mb-3"><button type="button" id="browser-price-select-found" class="px-3 py-1.5 rounded-lg bg-slate-100 dark:bg-slate-800 text-xs font-bold">בחר תוצאות שנמצאו</button><button type="button" id="browser-price-select-all" class="px-3 py-1.5 rounded-lg bg-slate-100 dark:bg-slate-800 text-xs font-bold">בחר הכל</button><button type="button" id="browser-price-select-none" class="px-3 py-1.5 rounded-lg bg-slate-100 dark:bg-slate-800 text-xs font-bold">נקה בחירה</button></div><div id="browser-price-status" class="text-sm text-slate-500 mb-3">לחץ "התחל בדיקה" כדי לבדוק את כל מוצרי המחירון.</div><div class="overflow-x-auto"><table class="min-w-full text-sm"><thead class="bg-slate-50 dark:bg-slate-950"><tr><th class="p-3 text-right">מוצר</th><th class="p-3 text-center">מחיר קיים</th><th class="p-3 text-center">מחיר שנמצא</th><th class="p-3 text-center">ביטחון</th><th class="p-3 text-right">מקור</th><th class="p-3 text-center">עדכון</th></tr></thead><tbody id="browser-price-results"></tbody></table></div></div><div class="p-4 border-t dark:border-slate-700 flex justify-between items-center gap-2"><span id="browser-price-count" class="text-xs font-bold text-slate-500"></span><div class="flex gap-2"><button id="browser-price-cancel" class="px-4 py-2 rounded-lg bg-slate-100 dark:bg-slate-800 font-bold">סגור</button><button id="browser-price-apply" disabled class="px-4 py-2 rounded-lg bg-emerald-600 disabled:opacity-40 text-white font-bold">עדכן מאושרים</button></div></div></div>`;
    document.body.appendChild(modal);$('browser-price-close').onclick=close;$('browser-price-cancel').onclick=close;$('browser-price-search').onclick=search;$('browser-price-apply').onclick=apply;$('browser-price-select-all').onclick=()=>selectChecks(true);$('browser-price-select-none').onclick=()=>selectChecks(false);$('browser-price-select-found').onclick=()=>selectChecks(null);
  }
  function close(){$('browser-price-modal')?.remove()}
  let results=[];
  async function search(){
    const list=await getProducts();
    if(!list.length){toast('לא נמצאו מוצרים במחירון. בדוק שהמחירון נטען והמשתמש מחובר.',true);return;}
    const status=$('browser-price-status');status.innerHTML=`נמצאו <b>${list.length}</b> מוצרים במחירון. מתחיל בדיקה...`;$('browser-price-search').disabled=true;$('browser-price-apply').disabled=true;
    try{const r=await api('/api/browser-price-sync/search',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({products:list})});const data=r?await r.json():{};if(!r?.ok){toast(data.error||'החיפוש נכשל',true);return;}results=data.results||[];render();status.textContent=`הבדיקה הסתיימה: ${results.length} מתוך ${list.length} מוצרים. מוצגים גם מוצרים שלא נמצא להם מחיר.`;}catch(e){toast('שגיאה בבדיקת המחירים',true)}finally{$('browser-price-search').disabled=false;}
  }
  function render(){
    $('browser-price-results').innerHTML=results.map((x,i)=>{const pct=Math.round((Number(x.confidence)||0)*100);const eligible=x.found&&x.currency==='ILS'&&Number(x.price)>0&&pct>=80&&Math.abs(Number(x.price)-Number(x.current_price))>0.001;return `<tr class="border-t dark:border-slate-800"><td class="p-3 font-bold">${esc(x.name)}</td><td class="p-3 text-center">₪${Number(x.current_price).toFixed(2)}</td><td class="p-3 text-center font-extrabold">${x.found?'₪'+Number(x.price).toFixed(2):'—'}</td><td class="p-3 text-center"><span class="font-bold ${pct>=80?'text-emerald-600':pct>=60?'text-amber-600':'text-rose-600'}">${x.found?pct+'%':'—'}</span></td><td class="p-3 text-right">${x.source_url?`<a href="${esc(x.source_url)}" target="_blank" rel="noopener noreferrer" class="text-indigo-600 hover:underline">${esc(x.source_title||'מקור')}</a>`:esc(x.notes||'לא נמצא מחיר')}</td><td class="p-3 text-center">${x.found?`<input type="checkbox" class="browser-price-check w-4 h-4" data-index="${i}" ${eligible?'checked':''}>`:'<span class="text-slate-400">לא נמצא</span>'}</td></tr>`}).join('');document.querySelectorAll('.browser-price-check').forEach(c=>c.addEventListener('change',updateCount));updateCount();
  }
  function selectChecks(mode){document.querySelectorAll('.browser-price-check').forEach(c=>{const x=results[Number(c.dataset.index)];const found=!!x?.found&&x.currency==='ILS'&&Number(x.price)>0;if(mode===null)c.checked=found&&Number(x.confidence)>=0.8&&Math.abs(Number(x.price)-Number(x.current_price))>0.001;else c.checked=mode;});updateCount();}
  function updateCount(){const n=[...document.querySelectorAll('.browser-price-check:checked')].length;$('browser-price-count').textContent=`${n} מוצרים מוכנים לעדכון מתוך ${results.length}`;$('browser-price-apply').disabled=n===0}
  async function apply(){const effective=$('browser-price-effective').value;if(!effective){toast('בחר תאריך תוקף',true);return;}const updates=[...document.querySelectorAll('.browser-price-check:checked')].map(c=>{const x=results[Number(c.dataset.index)];return{name:x.name,price:x.price}});if(!updates.length)return;$('browser-price-apply').disabled=true;$('browser-price-status').textContent=`שומר ${updates.length} מחירים...`;const r=await api('/api/browser-price-sync/apply',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({updates,effective_from:effective})});const data=r?await r.json():{};if(!r?.ok){toast(data.error||'השמירה נכשלה',true);$('browser-price-apply').disabled=false;return;}localStorage.setItem('global_price_effective_from',effective);toast(`עודכנו ${data.applied?.length||0} מחירים`);close();if(typeof window.loadProducts==='function')await window.loadProducts();if(typeof window.refreshScheduledPrices==='function')window.refreshScheduledPrices();}
  let observer;
  function boot(){
    if(install()){ observer?.disconnect(); observer=null; return; }
    if(!observer){observer=new MutationObserver(()=>{if(install()){observer.disconnect();observer=null;}});observer.observe(document.body,{childList:true,subtree:true});}
  }
  boot();
})();