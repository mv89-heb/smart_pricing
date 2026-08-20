(() => {
  'use strict';
  const $=id=>document.getElementById(id);
  const esc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const today=()=>{const d=new Date();d.setMinutes(d.getMinutes()-d.getTimezoneOffset());return d.toISOString().slice(0,10)};
  async function api(url,opt={}){opt.credentials='same-origin';opt.headers={...(opt.headers||{})};if(['POST','PUT','PATCH','DELETE'].includes((opt.method||'GET').toUpperCase()))opt.headers['X-Requested-With']='XMLHttpRequest';const r=await fetch(url,opt);if(r.status===401){location.href='/login';return null}return r}
  function toast(msg,error=false){if(typeof window.showToast==='function')return window.showToast(msg,error?'error':'success');alert(msg)}
  function products(){
    const source=window.products;
    if(source&&typeof source==='object'&&!Array.isArray(source))return Object.entries(source).map(([name,price])=>({name,current_price:Number(price)||0}));
    return [];
  }
  function install(){
    const panel=document.getElementById('right-panel');if(!panel||document.getElementById('ai-price-sync-btn'))return;
    const header=panel.querySelector('h2')?.parentElement;if(!header)return;
    const btn=document.createElement('button');btn.id='ai-price-sync-btn';btn.type='button';btn.className='text-xs font-bold text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/40 hover:bg-emerald-100 px-2.5 py-1.5 rounded-lg transition-colors flex items-center gap-1';btn.innerHTML='<i class="fa-solid fa-wand-magic-sparkles"></i> עדכון מחירים AI';btn.addEventListener('click',open);header.appendChild(btn);
  }
  function open(){
    if($('ai-price-modal'))return;
    const modal=document.createElement('div');modal.id='ai-price-modal';modal.className='fixed inset-0 z-[10000] bg-slate-950/60 backdrop-blur-sm flex items-center justify-center p-4';modal.innerHTML=`<div class="w-full max-w-5xl max-h-[90vh] overflow-hidden rounded-2xl bg-white dark:bg-slate-900 shadow-2xl" dir="rtl"><div class="p-5 border-b dark:border-slate-700 flex justify-between items-center"><div><h3 class="text-xl font-extrabold">עדכון מחירים חד־פעמי באמצעות Google AI</h3><p class="text-xs text-slate-500 mt-1">Google Search + Gemini יחפשו מחירים. שום מחיר לא משתנה לפני אישור.</p></div><button id="ai-price-close" class="text-slate-400 text-xl"><i class="fa-solid fa-xmark"></i></button></div><div class="p-5 overflow-y-auto max-h-[65vh]"><div class="flex flex-col sm:flex-row gap-3 items-end mb-4"><div class="flex-1"><label class="block text-xs font-bold text-slate-500 mb-1">תאריך תוקף</label><input id="ai-price-effective" type="date" value="${today()}" class="w-full px-3 py-2 rounded-lg border dark:border-slate-700 bg-white dark:bg-slate-950"></div><button id="ai-price-search" class="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-bold"><i class="fa-solid fa-magnifying-glass"></i> חפש מחירים</button></div><div id="ai-price-status" class="text-sm text-slate-500 mb-3"></div><div class="overflow-x-auto"><table class="min-w-full text-sm"><thead class="bg-slate-50 dark:bg-slate-950"><tr><th class="p-3 text-right">מוצר</th><th class="p-3 text-center">מחיר קיים</th><th class="p-3 text-center">מחיר שנמצא</th><th class="p-3 text-center">ביטחון</th><th class="p-3 text-right">מקור</th><th class="p-3 text-center">אישור</th></tr></thead><tbody id="ai-price-results"></tbody></table></div></div><div class="p-4 border-t dark:border-slate-700 flex justify-between items-center gap-2"><span id="ai-price-count" class="text-xs font-bold text-slate-500"></span><div class="flex gap-2"><button id="ai-price-cancel" class="px-4 py-2 rounded-lg bg-slate-100 dark:bg-slate-800 font-bold">סגור</button><button id="ai-price-apply" disabled class="px-4 py-2 rounded-lg bg-emerald-600 disabled:opacity-40 text-white font-bold">עדכן מאושרים</button></div></div></div>`;document.body.appendChild(modal);
    $('ai-price-close').onclick=close;$('ai-price-cancel').onclick=close;$('ai-price-search').onclick=search;$('ai-price-apply').onclick=apply;
  }
  function close(){$('ai-price-modal')?.remove()}
  let results=[];
  async function search(){
    const list=products();if(!list.length){toast('לא נמצאו מוצרים במחירון',true);return}
    const status=$('ai-price-status');status.textContent=`מחפש מחירים עבור ${list.length} מוצרים...`;$('ai-price-search').disabled=true;$('ai-price-apply').disabled=true;
    try{const r=await api('/api/ai-price-sync/search',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({products:list})});const data=r?await r.json():{};if(!r?.ok){toast(data.error||'החיפוש נכשל',true);return}results=data.results||[];render();status.textContent='החיפוש הסתיים. בדוק את התוצאות ובחר מה לעדכן.';}catch(e){toast('שגיאה בחיפוש AI',true)}finally{$('ai-price-search').disabled=false}
  }
  function render(){
    const body=$('ai-price-results');let good=0;body.innerHTML=results.map((x,i)=>{const pct=Math.round((Number(x.confidence)||0)*100);const eligible=x.found&&pct>=90&&x.currency==='ILS'&&Number(x.price)>0&&Math.abs(Number(x.price)-Number(x.current_price))>0.001;if(eligible)good++;return `<tr class="border-t dark:border-slate-800"><td class="p-3 font-bold">${esc(x.name)}${x.matched_name&&x.matched_name!==x.name?`<div class="text-[11px] text-slate-500">זוהה כ: ${esc(x.matched_name)}</div>`:''}</td><td class="p-3 text-center">₪${Number(x.current_price).toFixed(2)}</td><td class="p-3 text-center font-extrabold">${x.found?'₪'+Number(x.price).toFixed(2):'—'}</td><td class="p-3 text-center"><span class="font-bold ${pct>=90?'text-emerald-600':pct>=70?'text-amber-600':'text-rose-600'}">${pct}%</span></td><td class="p-3 text-right">${x.source_url?`<a href="${esc(x.source_url)}" target="_blank" rel="noopener noreferrer" class="text-indigo-600 hover:underline">${esc(x.source_title||'מקור')}</a>`:esc(x.notes||'לא נמצא')}</td><td class="p-3 text-center">${eligible?`<input type="checkbox" class="ai-price-check w-4 h-4" data-index="${i}" checked>`:'<span class="text-slate-400">לא אושר אוטומטית</span>'}</td></tr>`}).join('');document.querySelectorAll('.ai-price-check').forEach(c=>c.addEventListener('change',updateCount));updateCount();
  }
  function updateCount(){const n=[...document.querySelectorAll('.ai-price-check:checked')].length;$('ai-price-count').textContent=`${n} מוצרים מוכנים לעדכון`;$('ai-price-apply').disabled=n===0}
  async function apply(){
    const effective=$('ai-price-effective').value;if(!effective){toast('בחר תאריך תוקף',true);return}
    const updates=[...document.querySelectorAll('.ai-price-check:checked')].map(c=>{const x=results[Number(c.dataset.index)];return{name:x.name,price:x.price}});if(!updates.length)return;
    $('ai-price-apply').disabled=true;$('ai-price-status').textContent='שומר את המחירים...';
    const r=await api('/api/ai-price-sync/apply',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({updates,effective_from:effective})});const data=r?await r.json():{};if(!r?.ok){toast(data.error||'השמירה נכשלה',true);$('ai-price-apply').disabled=false;return}
    localStorage.setItem('global_price_effective_from',effective);toast(`עודכנו ${data.applied?.length||0} מחירים`);close();if(typeof window.loadProducts==='function')await window.loadProducts();if(typeof window.refreshScheduledPrices==='function')window.refreshScheduledPrices();
  }
  const observer=new MutationObserver(install);observer.observe(document.body,{childList:true,subtree:true});install();
})();
