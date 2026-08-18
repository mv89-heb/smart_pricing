(() => {
  'use strict';
  const money = n => (Number(n)||0).toLocaleString('he-IL',{minimumFractionDigits:2,maximumFractionDigits:2})+' ₪';
  const esc = s => String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const iso = d => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
  const today = () => { const d=new Date(); return new Date(d.getFullYear(),d.getMonth(),d.getDate()); };
  function range(name){
    const end=today(), start=new Date(end);
    if(name==='week') start.setDate(start.getDate()-6);
    else if(name==='30days') start.setDate(start.getDate()-29);
    else if(name==='month') return [iso(new Date(end.getFullYear(),end.getMonth(),1)),iso(end)];
    else if(name==='3months') return [iso(new Date(end.getFullYear(),end.getMonth()-2,1)),iso(end)];
    else if(name==='quarter') { const q=Math.floor(end.getMonth()/3); return [iso(new Date(end.getFullYear(),q*3,1)),iso(end)]; }
    else if(name==='year') return [iso(new Date(end.getFullYear(),0,1)),iso(end)];
    return [iso(start),iso(end)];
  }
  async function api(url){
    const r=await fetch(url,{credentials:'same-origin',cache:'no-store'});
    if(r.status===401){location.href='/login';return null;}
    if(!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  }
  function build(){
    if(document.getElementById('period-display-panel')) return true;
    const left=document.getElementById('left-panel');
    if(!left) return false;
    const panel=document.createElement('section');
    panel.id='period-display-panel';
    panel.dir='rtl';
    panel.className='bg-white dark:bg-slate-800 rounded-2xl shadow-sm border-2 border-indigo-200 dark:border-indigo-900 p-4 sm:p-5 mb-4 print:hidden';
    panel.innerHTML=`
      <div class="flex flex-col gap-3">
        <div class="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3">
          <div><h3 class="font-extrabold text-lg flex items-center gap-2"><i class="fa-solid fa-chart-column text-indigo-600"></i> הצגת דוח לפי תקופה</h3><p class="text-xs text-slate-500 mt-1">הצגה נפרדת מהדיווח היומי. הדיווח היומי ממשיך לעבוד לפי התאריך שבחרת.</p></div>
          <div class="flex flex-wrap gap-2">
            <button data-range="week" class="period-btn px-3 py-2 rounded-lg bg-slate-100 dark:bg-slate-700 text-xs font-bold">שבוע</button>
            <button data-range="30days" class="period-btn px-3 py-2 rounded-lg bg-slate-100 dark:bg-slate-700 text-xs font-bold">30 יום</button>
            <button data-range="month" class="period-btn px-3 py-2 rounded-lg bg-slate-100 dark:bg-slate-700 text-xs font-bold">חודש</button>
            <button data-range="3months" class="period-btn active px-3 py-2 rounded-lg bg-indigo-600 text-white text-xs font-bold">3 חודשים</button>
            <button data-range="quarter" class="period-btn px-3 py-2 rounded-lg bg-slate-100 dark:bg-slate-700 text-xs font-bold">רבעון</button>
            <button data-range="year" class="period-btn px-3 py-2 rounded-lg bg-slate-100 dark:bg-slate-700 text-xs font-bold">מתחילת השנה</button>
            <button id="period-all" class="px-3 py-2 rounded-lg bg-emerald-600 text-white text-xs font-bold">כל הנתונים</button>
          </div>
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-2">
          <input id="period-from" type="date" class="px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 text-sm font-bold">
          <input id="period-to" type="date" class="px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 text-sm font-bold">
          <button id="period-load" class="px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-bold">הצג תקופה</button>
        </div>
        <div id="period-status" class="text-xs font-bold text-slate-500"></div>
        <div id="period-summary" class="grid grid-cols-2 lg:grid-cols-5 gap-2"></div>
        <div class="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <div class="border border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden"><div class="px-3 py-2 bg-slate-50 dark:bg-slate-900 font-extrabold text-sm">פירוט לפי ימים</div><div class="max-h-72 overflow-auto"><table class="min-w-full text-xs"><thead class="sticky top-0 bg-white dark:bg-slate-800"><tr><th class="p-2 text-right">תאריך</th><th class="p-2">שוטף</th><th class="p-2">אקסטרה</th><th class="p-2">סה״כ</th></tr></thead><tbody id="period-days"></tbody></table></div></div>
          <div class="border border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden"><div class="px-3 py-2 bg-slate-50 dark:bg-slate-900 font-extrabold text-sm">פירוט לפי מוצר</div><div class="max-h-72 overflow-auto"><table class="min-w-full text-xs"><thead class="sticky top-0 bg-white dark:bg-slate-800"><tr><th class="p-2 text-right">מוצר</th><th class="p-2">כמות</th><th class="p-2">סה״כ</th></tr></thead><tbody id="period-products"></tbody></table></div></div>
        </div>
      </div>`;
    // Put it at the very top of the daily-report column so it cannot be hidden by the daily table/date state.
    left.insertBefore(panel,left.firstChild);
    panel.querySelectorAll('.period-btn').forEach(b=>b.onclick=()=>{panel.querySelectorAll('.period-btn').forEach(x=>x.classList.remove('bg-indigo-600','text-white'));b.classList.add('bg-indigo-600','text-white');const [f,t]=range(b.dataset.range);document.getElementById('period-from').value=f;document.getElementById('period-to').value=t;load(f,t);});
    document.getElementById('period-load').onclick=()=>load(document.getElementById('period-from').value,document.getElementById('period-to').value);
    document.getElementById('period-all').onclick=loadAll;
    return true;
  }
  function render(d){
    const s=d.summary||{};
    document.getElementById('period-status').textContent=d.from&&d.to?`מציג נתונים מ-${d.from.split('-').reverse().join('/')} עד ${d.to.split('-').reverse().join('/')} | ${Number(s.days_count||0)} ימי דיווח`:'';
    document.getElementById('period-summary').innerHTML=[['סה״כ',money(s.grand_total)],['שוטף',money(s.regular_total)],['אקסטרה',money(s.extra_total)],['ימי דיווח',Number(s.days_count||0).toLocaleString('he-IL')],['ממוצע ליום',money(s.average_day)]].map(([a,b])=>`<div class="rounded-xl border border-slate-200 dark:border-slate-700 p-3"><div class="text-[11px] text-slate-500 font-bold">${a}</div><div class="font-extrabold mt-1">${b}</div></div>`).join('');
    const days=Object.entries(d.day_summary||{}).sort((a,b)=>a[0].localeCompare(b[0]));
    document.getElementById('period-days').innerHTML=days.map(([x,v])=>`<tr class="border-t border-slate-100 dark:border-slate-700"><td class="p-2 font-bold">${esc(x.split('-').reverse().join('/'))}</td><td class="p-2 text-center">${money(v.regular)}</td><td class="p-2 text-center">${money(v.extra)}</td><td class="p-2 text-center font-extrabold">${money(v.total)}</td></tr>`).join('');
    const products=Object.entries(d.product_summary||{}).sort((a,b)=>(b[1].total||0)-(a[1].total||0));
    document.getElementById('period-products').innerHTML=products.map(([x,v])=>`<tr class="border-t border-slate-100 dark:border-slate-700"><td class="p-2 font-bold">${esc(x)}</td><td class="p-2 text-center">${Number(v.quantity||0).toLocaleString('he-IL')}</td><td class="p-2 text-center font-extrabold">${money(v.total)}</td></tr>`).join('');
  }
  async function load(f,t){if(!f||!t||f>t)return;try{const d=await api(`/api/report/period?from=${encodeURIComponent(f)}&to=${encodeURIComponent(t)}`);if(d)render(d);}catch(e){console.error(e);document.getElementById('period-status').textContent='שגיאה בטעינת הדוח';}}
  async function loadAll(){try{const d=await api('/api/report/all');if(d)render(d);}catch(e){console.error(e);}}
  function init(){if(!build())return;const [f,t]=range('3months');document.getElementById('period-from').value=f;document.getElementById('period-to').value=t;load(f,t);}
  function start(){init();setTimeout(init,500);setTimeout(init,1500);}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start);else start();
})();
