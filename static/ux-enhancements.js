(() => {
  const $ = (id) => document.getElementById(id);
  const PERIODIC = '/periodic-report';
  const money = (n) => '₪' + (Number(n) || 0).toLocaleString('he-IL', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const num = (n) => (Number(n) || 0).toLocaleString('he-IL', { maximumFractionDigits: 2 });
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const parseDate = (s) => { const [y,m,d] = s.split('-').map(Number); return new Date(y,m-1,d); };
  const fmt = (d) => d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0');
  const addDays = (d,n) => { const x = new Date(d); x.setDate(x.getDate()+n); return x; };
  const daysBetween = (a,b) => Math.round((parseDate(b)-parseDate(a))/86400000)+1;
  const rangePreset = (kind) => {
    const now = new Date();
    if (kind === 'month') return [new Date(now.getFullYear(),now.getMonth(),1), new Date(now.getFullYear(),now.getMonth()+1,0)];
    if (kind === 'prev') return [new Date(now.getFullYear(),now.getMonth()-1,1), new Date(now.getFullYear(),now.getMonth(),0)];
    if (kind === 'quarter') { const q=Math.floor(now.getMonth()/3)*3; return [new Date(now.getFullYear(),q,1),new Date(now.getFullYear(),q+3,0)]; }
    if (kind === 'year') return [new Date(now.getFullYear(),0,1),new Date(now.getFullYear(),11,31)];
    if (kind === '7') return [addDays(now,-6),now];
    return [new Date(now.getFullYear(),now.getMonth(),1),new Date(now.getFullYear(),now.getMonth()+1,0)];
  };
  async function api(url,opt={}) { const r=await fetch(url,{credentials:'same-origin',...opt}); if(r.status===401) location.href='/login'; return r; }
  function notify(message, type='info') {
    const old=$('dashboard-toast'); if(old) old.remove();
    const d=document.createElement('div'); d.id='dashboard-toast'; d.className=`fixed top-20 left-4 z-[100] px-4 py-3 rounded-xl shadow-xl text-sm font-bold ${type==='error'?'bg-rose-600':'bg-slate-900'} text-white`;
    d.textContent=message; document.body.appendChild(d); setTimeout(()=>d.remove(),3200);
  }
  function addNav() {
    if($('analytics-nav')) return;
    const b=[...document.querySelectorAll('button')].find(x=>(x.textContent||'').includes('דאשבורד')); const w=b?.parentElement; if(!w) return;
    const make=(id,href,text,icon,cls)=>{const x=document.createElement('a');x.id=id;x.href=href;x.className=cls;x.innerHTML=`<i class="fa-solid ${icon}"></i><span class="hidden sm:inline">${text}</span>`;return x;};
    w.insertBefore(make('analytics-nav','#main-dashboard','דשבורד','fa-chart-pie','text-sm font-bold text-violet-700 dark:text-violet-300 bg-violet-50 dark:bg-violet-950/40 px-3 py-2 rounded-lg flex items-center gap-2'),b);
    w.insertBefore(make('periodic-report-nav',PERIODIC,'דוח תקופתי','fa-calendar-days','text-sm font-bold text-emerald-700 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-950/40 px-3 py-2 rounded-lg flex items-center gap-2'),b);
  }
  let report=null, compare=null, chart=null;
  function createDashboard() {
    if($('main-dashboard')||!document.querySelector('main')) return;
    const s=document.createElement('section'); s.id='main-dashboard'; s.className='mb-6 scroll-mt-20'; s.dir='rtl';
    s.innerHTML=`<div class="rounded-3xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 shadow-sm overflow-hidden">
      <div class="p-4 sm:p-6 border-b border-slate-200 dark:border-slate-700 bg-gradient-to-l from-indigo-50 via-white to-emerald-50 dark:from-slate-900 dark:via-slate-800 dark:to-slate-900">
        <div class="flex flex-col gap-4">
          <div class="flex flex-col xl:flex-row xl:items-end justify-between gap-4">
            <div><div class="text-xs font-extrabold text-indigo-600 dark:text-indigo-400">מרכז שליטה כספי</div><h2 class="text-2xl sm:text-3xl font-extrabold mt-1">דשבורד חיובים</h2><p id="dash-sub" class="text-sm text-slate-500 mt-1">בחר תקופה כדי לקבל תמונת מצב מלאה.</p></div>
            <div class="flex flex-wrap items-end gap-2">
              <label class="text-xs font-bold text-slate-500">מתאריך<input id="dash-from" type="date" class="block mt-1 px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900"></label>
              <label class="text-xs font-bold text-slate-500">עד תאריך<input id="dash-to" type="date" class="block mt-1 px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900"></label>
              <button id="dash-refresh" class="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-bold">עדכן</button>
            </div>
          </div>
          <div class="flex flex-wrap gap-2">
            <button data-preset="7" class="dash-preset px-3 py-1.5 rounded-lg bg-slate-100 dark:bg-slate-700 font-bold text-xs">7 ימים</button>
            <button data-preset="month" class="dash-preset px-3 py-1.5 rounded-lg bg-indigo-50 text-indigo-700 font-bold text-xs">החודש</button>
            <button data-preset="prev" class="dash-preset px-3 py-1.5 rounded-lg bg-slate-100 dark:bg-slate-700 font-bold text-xs">חודש קודם</button>
            <button data-preset="quarter" class="dash-preset px-3 py-1.5 rounded-lg bg-slate-100 dark:bg-slate-700 font-bold text-xs">רבעון</button>
            <button data-preset="year" class="dash-preset px-3 py-1.5 rounded-lg bg-slate-100 dark:bg-slate-700 font-bold text-xs">שנה</button>
            <button id="dash-export" class="mr-auto px-3 py-1.5 rounded-lg bg-emerald-50 text-emerald-700 font-bold text-xs">ייצוא Excel</button>
            <a href="${PERIODIC}" class="px-3 py-1.5 rounded-lg bg-violet-50 text-violet-700 font-bold text-xs">דוח מפורט</a>
          </div>
        </div>
      </div>
      <div class="p-4 sm:p-6">
        <div class="grid grid-cols-2 lg:grid-cols-5 gap-3">
          <div class="rounded-2xl bg-slate-950 text-white p-4"><div class="text-xs text-slate-300">סה״כ סופי</div><div id="dash-total" class="text-2xl sm:text-3xl font-extrabold mt-1">₪0.00</div><div id="dash-change" class="text-xs mt-1 text-slate-300">—</div></div>
          <div class="rounded-2xl border border-indigo-100 dark:border-slate-700 p-4"><div class="text-xs text-slate-500">שוטף</div><div id="dash-regular" class="text-xl font-extrabold text-indigo-600 mt-1">₪0.00</div></div>
          <div class="rounded-2xl border border-amber-100 dark:border-slate-700 p-4"><div class="text-xs text-slate-500">אקסטרה</div><div id="dash-extra" class="text-xl font-extrabold text-amber-600 mt-1">₪0.00</div></div>
          <div class="rounded-2xl border dark:border-slate-700 p-4"><div class="text-xs text-slate-500">ימי חיוב</div><div id="dash-days" class="text-xl font-extrabold mt-1">0</div></div>
          <div class="rounded-2xl border dark:border-slate-700 p-4"><div class="text-xs text-slate-500">ממוצע ליום</div><div id="dash-avg" class="text-xl font-extrabold mt-1">₪0.00</div></div>
        </div>
        <div class="grid lg:grid-cols-5 gap-4 mt-4">
          <div class="lg:col-span-3 rounded-2xl border dark:border-slate-700 p-4"><div class="flex justify-between items-center"><h3 class="font-extrabold">מגמת חיובים</h3><span id="dash-status" class="text-xs font-bold"></span></div><div class="h-64 mt-2"><canvas id="dash-chart"></canvas></div></div>
          <div class="lg:col-span-2 rounded-2xl border dark:border-slate-700 p-4"><h3 class="font-extrabold mb-3">סיכום לפי מוצר</h3><div id="dash-products" class="space-y-3 max-h-64 overflow-auto"></div></div>
        </div>
        <div class="grid lg:grid-cols-2 gap-4 mt-4">
          <div class="rounded-2xl border dark:border-slate-700 p-4"><div class="flex justify-between items-center"><h3 class="font-extrabold">השוואה לתקופה קודמת</h3><span id="dash-compare-label" class="text-xs text-slate-500"></span></div><div id="dash-compare" class="mt-3"></div></div>
          <div class="rounded-2xl border dark:border-slate-700 p-4"><h3 class="font-extrabold">🔎 חריגות ותובנות</h3><div id="dash-insights" class="mt-3 space-y-2"></div></div>
        </div>
        <div class="mt-4 rounded-2xl border dark:border-slate-700 overflow-hidden">
          <div class="p-4 border-b dark:border-slate-700 flex flex-col md:flex-row md:items-center justify-between gap-3"><div><h3 class="font-extrabold">חיובים בתקופה</h3><p class="text-xs text-slate-500">עריכה או מחיקה מעדכנות מיד את כל המדדים.</p></div><div class="flex gap-2"><input id="dash-search" placeholder="חיפוש מוצר / הערה" class="px-3 py-2 rounded-lg border dark:border-slate-600 bg-white dark:bg-slate-900 text-sm"><select id="dash-type" class="px-3 py-2 rounded-lg border dark:border-slate-600 bg-white dark:bg-slate-900 text-sm"><option value="all">כל הסוגים</option><option value="regular">שוטף</option><option value="extra">אקסטרה</option></select><span id="dash-count" class="text-xs font-bold text-slate-500 self-center"></span></div></div>
          <div class="overflow-x-auto"><table class="min-w-full text-sm"><thead class="bg-slate-50 dark:bg-slate-900"><tr><th class="p-3 text-right">תאריך</th><th class="p-3 text-right">מוצר</th><th class="p-3 text-right">כמות</th><th class="p-3 text-right">סוג</th><th class="p-3 text-right">מחיר</th><th class="p-3 text-right">סה״כ</th><th class="p-3 text-right">הערה</th><th class="p-3">פעולות</th></tr></thead><tbody id="dash-entries"></tbody></table></div>
        </div>
      </div>
    </div>`;
    document.querySelector('main').prepend(s);
    const [a,b]=rangePreset('month'); $('dash-from').value=fmt(a); $('dash-to').value=fmt(b);
    $('dash-refresh').onclick=load; $('dash-from').onchange=load; $('dash-to').onchange=load; $('dash-search').oninput=renderEntries; $('dash-type').onchange=renderEntries;
    document.querySelectorAll('.dash-preset').forEach(btn=>btn.onclick=()=>{const[x,y]=rangePreset(btn.dataset.preset);$('dash-from').value=fmt(x);$('dash-to').value=fmt(y);load()});
    $('dash-export').onclick=exportExcel; load();
  }
  async function fetchReport(from,to){const r=await api(`/api/report/period?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`); if(!r?.ok) return null; return r.json();}
  async function load(){
    const from=$('dash-from')?.value,to=$('dash-to')?.value;
    if(!from||!to||from>to){notify('טווח תאריכים לא תקין','error');return;}
    $('dash-refresh').disabled=true; $('dash-refresh').textContent='טוען...';
    try {
      report=await fetchReport(from,to); if(!report){notify('לא ניתן לטעון את הדוח','error');return;}
      const length=daysBetween(from,to), prevTo=addDays(parseDate(from),-1), prevFrom=addDays(prevTo,-length+1);
      compare=await fetchReport(fmt(prevFrom),fmt(prevTo));
      renderDashboard();
    } finally { $('dash-refresh').disabled=false; $('dash-refresh').textContent='עדכן'; }
  }
  function renderDashboard(){
    const s=report.summary||{}; $('dash-sub').textContent=`נתונים לתקופה ${report.from} עד ${report.to}`; $('dash-total').textContent=money(s.grand_total); $('dash-regular').textContent=money(s.regular_total); $('dash-extra').textContent=money(s.extra_total); $('dash-days').textContent=num(s.days_count); $('dash-avg').textContent=money(s.average_day);
    const prev=compare?.summary?.grand_total||0, cur=Number(s.grand_total)||0; const pct=prev?((cur-prev)/prev*100):null; $('dash-change').textContent=pct===null?'אין תקופה להשוואה':`${pct>=0?'▲':'▼'} ${Math.abs(pct).toFixed(1)}% לעומת התקופה הקודמת`; $('dash-change').className='text-xs mt-1 '+(pct===null?'text-slate-300':pct>=0?'text-emerald-300':'text-rose-300');
    const days=report.day_summary||{},labels=Object.keys(days).sort(); if(chart) chart.destroy(); if(window.Chart) chart=new Chart($('dash-chart'),{type:'line',data:{labels:labels.map(x=>x.slice(5)),datasets:[{label:'סה״כ',data:labels.map(x=>days[x].total),tension:.3},{label:'שוטף',data:labels.map(x=>days[x].regular),tension:.3},{label:'אקסטרה',data:labels.map(x=>days[x].extra),tension:.3}]},options:{responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},plugins:{legend:{position:'bottom'}},scales:{y:{beginAtZero:true}}}});
    const ps=Object.entries(report.product_summary||{}).sort((a,b)=>b[1].total-a[1].total),max=ps[0]?.[1]?.total||1; $('dash-products').innerHTML=ps.length?ps.slice(0,12).map(([n,x])=>`<button data-product="${esc(n)}" class="w-full text-right"><div class="flex justify-between font-bold text-sm"><span>${esc(n)}</span><span>${money(x.total)}</span></div><div class="h-2 bg-slate-100 dark:bg-slate-700 rounded mt-1"><div class="h-2 bg-indigo-500 rounded" style="width:${Math.min(100,x.total/max*100)}%"></div></div></button>`).join(''):'<div class="text-slate-400 text-center py-6">אין נתונים</div>';
    $('dash-products').querySelectorAll('[data-product]').forEach(b=>b.onclick=()=>{ $('dash-search').value=b.dataset.product; $('dash-type').value='all'; renderEntries(); $('dash-entries').scrollIntoView({behavior:'smooth',block:'center'}); });
    const locked=(report.locked_months||{}); const lockedCount=Object.values(locked).filter(Boolean).length; $('dash-status').textContent=lockedCount?`🔒 ${lockedCount} חודשים נעולים`:'🟢 התקופה פתוחה לעריכה'; $('dash-status').className='text-xs font-bold '+(lockedCount?'text-amber-600':'text-emerald-600');
    renderCompare(); renderInsights(); renderEntries();
  }
  function renderCompare(){
    const cur=report.summary||{}, old=compare?.summary||{}; const rows=[['סה״כ',cur.grand_total,old.grand_total],['שוטף',cur.regular_total,old.regular_total],['אקסטרה',cur.extra_total,old.extra_total],['ממוצע יומי',cur.average_day,old.average_day]];
    $('dash-compare-label').textContent=compare?`${compare.from} – ${compare.to}`:'אין נתונים';
    $('dash-compare').innerHTML=compare?`<div class="space-y-2">${rows.map(([n,a,b])=>{const p=b?((a-b)/b*100):null;return `<div class="flex items-center justify-between gap-3 text-sm"><span class="font-bold">${n}</span><span>${money(a)}</span><span class="text-xs font-bold ${p===null?'text-slate-400':p>=0?'text-emerald-600':'text-rose-600'}">${p===null?'—':`${p>=0?'▲':'▼'} ${Math.abs(p).toFixed(1)}%`}</span></div>`}).join('')}</div>`:'<div class="text-slate-400">לא נמצאו נתוני השוואה.</div>';
  }
  function renderInsights(){
    const days=Object.entries(report.day_summary||{}), totals=days.map(([,x])=>Number(x.total)||0), avg=Number(report.summary?.average_day)||0; const insights=[];
    const maxDay=days.sort((a,b)=>b[1].total-a[1].total)[0]; if(maxDay) insights.push(`📌 היום הגבוה ביותר: <b>${esc(maxDay[0])}</b> — ${money(maxDay[1].total)}`);
    const high=days.filter(([,x])=>avg>0&&x.total>avg*1.5); if(high.length) insights.push(`⚠️ ${high.length} ימים מעל 150% מהממוצע היומי.`);
    const ps=Object.entries(report.product_summary||{}).sort((a,b)=>b[1].total-a[1].total); if(ps[0]) insights.push(`🏆 המוצר המוביל: <b>${esc(ps[0][0])}</b> — ${money(ps[0][1].total)}.`);
    const extras=Number(report.summary?.extra_total)||0, grand=Number(report.summary?.grand_total)||0; if(grand&&extras/grand>=.25) insights.push(`🟠 אקסטרה מהווה ${(extras/grand*100).toFixed(1)}% מהחיובים בתקופה.`);
    if(compare?.summary?.grand_total){const p=(grand-compare.summary.grand_total)/compare.summary.grand_total*100;if(Math.abs(p)>=10) insights.push(`${p>0?'📈':'📉'} שינוי של ${Math.abs(p).toFixed(1)}% לעומת התקופה הקודמת.`);}
    $('dash-insights').innerHTML=insights.length?insights.map(x=>`<div class="rounded-xl bg-slate-50 dark:bg-slate-900 p-3 text-sm">${x}</div>`).join(''):'<div class="text-slate-400">אין חריגות משמעותיות.</div>';
  }
  function renderEntries(){
    if(!report)return; const q=($('dash-search')?.value||'').toLowerCase(); const type=$('dash-type')?.value||'all'; const rows=(report.entries||[]).filter(e=>(e.product_name+' '+(e.note||'')).toLowerCase().includes(q)).filter(e=>type==='all'||(type==='extra'?e.is_extra:!e.is_extra));
    $('dash-count').textContent=`${rows.length} מתוך ${(report.entries||[]).length} חיובים`; $('dash-entries').innerHTML=rows.length?rows.map(e=>`<tr class="border-t border-slate-100 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-900"><td class="p-3 font-bold whitespace-nowrap">${esc(e.date.split('-').reverse().join('/'))}</td><td class="p-3 font-bold">${esc(e.product_name)}</td><td class="p-3">${num(e.quantity)}</td><td class="p-3">${e.is_extra?'<span class="text-amber-700 font-bold">אקסטרה</span>':'<span class="text-indigo-700 font-bold">שוטף</span>'}</td><td class="p-3">${money(e.unit_price)}</td><td class="p-3 font-extrabold">${money(e.total_amount)}</td><td class="p-3 max-w-48 truncate">${esc(e.note||'—')}</td><td class="p-3 whitespace-nowrap"><button onclick="window.editDashEntry(${e.id})" class="px-2 py-1 rounded bg-indigo-50 text-indigo-700 font-bold text-xs">ערוך</button><button onclick="window.deleteDashEntry(${e.id})" class="mr-1 px-2 py-1 rounded bg-rose-50 text-rose-700 font-bold text-xs">מחק</button></td></tr>`).join(''):'<tr><td colspan="8" class="p-8 text-center text-slate-400">אין חיובים בטווח</td></tr>';
  }
  window.editDashEntry=async(id)=>{
    const e=(report?.entries||[]).find(x=>x.id===id); if(!e)return;
    const modal=document.createElement('div'); modal.id='dash-edit-modal'; modal.className='fixed inset-0 z-[90] bg-slate-950/60 backdrop-blur-sm flex items-center justify-center p-4';
    modal.innerHTML=`<div class="w-full max-w-md rounded-2xl bg-white dark:bg-slate-800 p-5 shadow-2xl"><div class="flex justify-between items-center mb-4"><div><div class="text-xs text-slate-500">עריכת חיוב</div><h3 class="text-xl font-extrabold">${esc(e.product_name)}</h3></div><button id="dash-edit-close" class="text-slate-400 text-xl">×</button></div><div class="grid grid-cols-2 gap-3"><label class="text-xs font-bold text-slate-500">כמות<input id="edit-q" type="number" min="0.01" step="0.01" value="${esc(e.quantity)}" class="w-full mt-1 px-3 py-2 rounded-lg border dark:border-slate-600 bg-white dark:bg-slate-900"></label><label class="text-xs font-bold text-slate-500">סוג<select id="edit-type" class="w-full mt-1 px-3 py-2 rounded-lg border dark:border-slate-600 bg-white dark:bg-slate-900"><option value="regular" ${!e.is_extra?'selected':''}>שוטף</option><option value="extra" ${e.is_extra?'selected':''}>אקסטרה</option></select></label></div><label class="block text-xs font-bold text-slate-500 mt-3">הערה<textarea id="edit-note" rows="3" class="w-full mt-1 px-3 py-2 rounded-lg border dark:border-slate-600 bg-white dark:bg-slate-900">${esc(e.note||'')}</textarea></label><div class="mt-4 rounded-xl bg-slate-50 dark:bg-slate-900 p-3 text-sm"><div class="flex justify-between"><span>מחיר יחידה</span><b>${money(e.unit_price)}</b></div><div class="flex justify-between mt-1"><span>סה״כ חדש</span><b id="edit-total">${money(e.quantity*e.unit_price)}</b></div></div><div class="flex gap-2 mt-4"><button id="edit-save" class="flex-1 bg-indigo-600 text-white rounded-lg py-2 font-bold">שמור</button><button id="edit-cancel" class="px-5 bg-slate-100 dark:bg-slate-700 rounded-lg font-bold">ביטול</button></div></div>`;
    document.body.appendChild(modal); const q=$('edit-q'), total=$('edit-total'); q.oninput=()=>total.textContent=money(Number(q.value)*Number(e.unit_price)); const close=()=>modal.remove(); $('dash-edit-close').onclick=close; $('edit-cancel').onclick=close;
    $('edit-save').onclick=async()=>{const quantity=Number(q.value), is_extra=$('edit-type').value==='extra', note=$('edit-note').value.trim();if(!Number.isFinite(quantity)||quantity<=0){notify('כמות לא תקינה','error');return} const r=await api(`/api/entries/${id}`,{method:'PUT',headers:{'Content-Type':'application/json','X-Requested-With':'XMLHttpRequest'},body:JSON.stringify({quantity,is_extra,note})});const b=r?await r.json():{};if(!r?.ok||!b.success){notify(b.error||'העדכון נכשל','error');return}close();await load();notify('החיוב עודכן');};
  };
  window.deleteDashEntry=async(id)=>{if(!confirm('למחוק את החיוב? הפעולה תתועד ביומן.'))return;const r=await api(`/api/entries/${id}`,{method:'DELETE',headers:{'X-Requested-With':'XMLHttpRequest'}});const b=r?await r.json():{};if(!r?.ok||!b.success){notify(b.error||'המחיקה נכשלה','error');return}await load();notify('החיוב נמחק');};
  function exportExcel(){
    if(!report?.entries?.length){notify('אין נתונים לייצוא','error');return}
    if(!window.XLSX){notify('רכיב Excel אינו זמין','error');return}
    const data=[['תאריך','מוצר','סוג','כמות','מחיר יחידה','סה״כ','הערה'],...report.entries.map(e=>[e.date,e.product_name,e.is_extra?'אקסטרה':'שוטף',e.quantity,e.unit_price,e.total_amount,e.note||'']),[],['','','','','סה״כ שוטף',report.summary.regular_total,''],['','','','','סה״כ אקסטרה',report.summary.extra_total,''],['','','','','סה״כ סופי',report.summary.grand_total,'']];
    const wb=XLSX.utils.book_new(),ws=XLSX.utils.aoa_to_sheet(data);ws['!views']=[{rightToLeft:true}];XLSX.utils.book_append_sheet(wb,ws,'דוח תקופה');XLSX.writeFile(wb,`דוח_חיובים_${report.from}_${report.to}.xlsx`);
  }
  function mobile(){if(!matchMedia('(max-width:767px)').matches||$('mobile-quick-actions'))return;const n=document.createElement('nav');n.id='mobile-quick-actions';n.className='fixed bottom-0 inset-x-0 z-40 bg-white/95 dark:bg-slate-800/95 border-t px-2 py-2 flex justify-around shadow-2xl';n.innerHTML=`<a href="#main-dashboard" class="font-bold text-violet-600 text-xs p-2">📊 דשבורד</a><a href="#entry-form-container" class="font-bold text-slate-600 text-xs p-2">📝 יומי</a><a href="${PERIODIC}" class="font-bold text-emerald-600 text-xs p-2">📅 תקופתי</a>`;document.body.appendChild(n);document.body.style.paddingBottom='60px';}
  function keys(){document.addEventListener('keydown',e=>{if(['INPUT','TEXTAREA','SELECT'].includes(e.target?.tagName))return;if(e.key.toLowerCase()==='d')$('main-dashboard')?.scrollIntoView({behavior:'smooth'});if(e.key.toLowerCase()==='r')location.href=PERIODIC;if(e.key==='/'){const x=document.querySelector('input[type=search],input[placeholder*="חיפוש"]');if(x){e.preventDefault();x.focus();}}});}
  function boot(){addNav();createDashboard();mobile();keys();}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);else boot();
})();
