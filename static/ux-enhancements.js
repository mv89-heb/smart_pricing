(() => {
  const $=id=>document.getElementById(id), PERIODIC='/periodic-report';
  const money=n=>'₪'+(Number(n)||0).toLocaleString('he-IL',{minimumFractionDigits:2,maximumFractionDigits:2});
  const esc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const fmt=d=>d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0');
  const bounds=(off=0)=>{const d=new Date();d.setMonth(d.getMonth()+off);return [new Date(d.getFullYear(),d.getMonth(),1),new Date(d.getFullYear(),d.getMonth()+1,0)]};
  async function api(url,opt={}){const r=await fetch(url,{credentials:'same-origin',...opt});if(r.status===401)location.href='/login';return r}

  function addNav(){
    if($('analytics-nav'))return; const b=[...document.querySelectorAll('button')].find(x=>(x.textContent||'').includes('דאשבורד')); const w=b?.parentElement;if(!w)return;
    const a=(id,href,text,icon,cls)=>{const x=document.createElement('a');x.id=id;x.href=href;x.className=cls;x.innerHTML=`<i class="fa-solid ${icon}"></i><span class="hidden sm:inline">${text}</span>`;return x};
    w.insertBefore(a('analytics-nav','#main-dashboard','דאשבורד','fa-chart-pie','text-sm font-medium text-violet-700 dark:text-violet-300 bg-violet-50 dark:bg-violet-950/40 px-3 py-2 rounded-lg flex items-center gap-2'),b);
    w.insertBefore(a('periodic-report-nav',PERIODIC,'דוח תקופתי','fa-calendar-days','text-sm font-medium text-emerald-700 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-950/40 px-3 py-2 rounded-lg flex items-center gap-2'),b);
  }

  function createDashboard(){
    if($('main-dashboard')||!document.querySelector('main'))return;
    const s=document.createElement('section');s.id='main-dashboard';s.className='mb-6 scroll-mt-20';s.dir='rtl';
    s.innerHTML=`<div class="rounded-3xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 shadow-sm overflow-hidden">
      <div class="p-4 sm:p-6 border-b border-slate-200 dark:border-slate-700 bg-gradient-to-l from-indigo-50 to-white dark:from-slate-900 dark:to-slate-800">
        <div class="flex flex-col xl:flex-row xl:items-end justify-between gap-4"><div><div class="text-xs font-extrabold text-indigo-600">מרכז שליטה</div><h2 class="text-2xl sm:text-3xl font-extrabold mt-1">דשבורד חיובים</h2><p id="dash-sub" class="text-sm text-slate-500 mt-1">בחר טווח תאריכים להצגת הנתונים.</p></div>
        <div class="flex flex-wrap items-end gap-2"><label class="text-xs font-bold text-slate-500">מתאריך<input id="dash-from" type="date" class="block mt-1 px-3 py-2 rounded-xl border bg-white dark:bg-slate-900"></label><label class="text-xs font-bold text-slate-500">עד תאריך<input id="dash-to" type="date" class="block mt-1 px-3 py-2 rounded-xl border bg-white dark:bg-slate-900"></label><button id="dash-refresh" class="px-4 py-2 rounded-xl bg-indigo-600 text-white font-bold">עדכן</button><button id="dash-month" class="px-3 py-2 rounded-xl border font-bold">החודש</button><button id="dash-prev" class="px-3 py-2 rounded-xl border font-bold">חודש קודם</button></div></div></div>
      <div class="p-4 sm:p-6"><div class="grid grid-cols-2 lg:grid-cols-5 gap-3">
        <div class="rounded-2xl bg-slate-900 text-white p-4"><div class="text-xs text-slate-300">סה״כ סופי</div><div id="dash-total" class="text-2xl sm:text-3xl font-extrabold mt-1">₪0.00</div></div>
        <div class="rounded-2xl border p-4"><div class="text-xs text-slate-500">שוטף</div><div id="dash-regular" class="text-xl font-extrabold text-indigo-600 mt-1">₪0.00</div></div>
        <div class="rounded-2xl border p-4"><div class="text-xs text-slate-500">אקסטרה</div><div id="dash-extra" class="text-xl font-extrabold text-amber-600 mt-1">₪0.00</div></div>
        <div class="rounded-2xl border p-4"><div class="text-xs text-slate-500">ימי חיוב</div><div id="dash-days" class="text-xl font-extrabold mt-1">0</div></div>
        <div class="rounded-2xl border p-4"><div class="text-xs text-slate-500">ממוצע ליום</div><div id="dash-avg" class="text-xl font-extrabold mt-1">₪0.00</div></div></div>
        <div class="grid lg:grid-cols-5 gap-4 mt-4"><div class="lg:col-span-3 rounded-2xl border p-4"><div class="flex justify-between"><h3 class="font-extrabold">מגמת חיובים</h3><span id="dash-lock" class="text-xs font-bold"></span></div><div class="h-64 mt-2"><canvas id="dash-chart"></canvas></div></div><div class="lg:col-span-2 rounded-2xl border p-4"><h3 class="font-extrabold mb-3">סיכום לפי מוצר</h3><div id="dash-products" class="space-y-3 max-h-64 overflow-auto"></div></div></div>
        <div class="mt-4 rounded-2xl border overflow-hidden"><div class="p-4 border-b flex justify-between"><div><h3 class="font-extrabold">חיובים בתקופה</h3><p class="text-xs text-slate-500">עריכה ומחיקה מעדכנות מיד את הדשבורד.</p></div><span id="dash-count" class="text-xs font-bold text-slate-500"></span></div><div class="overflow-x-auto"><table class="min-w-full text-sm"><thead class="bg-slate-50 dark:bg-slate-900"><tr><th class="p-3 text-right">תאריך</th><th class="p-3 text-right">מוצר</th><th class="p-3 text-right">כמות</th><th class="p-3 text-right">סוג</th><th class="p-3 text-right">מחיר</th><th class="p-3 text-right">סה״כ</th><th class="p-3 text-right">הערה</th><th class="p-3">פעולות</th></tr></thead><tbody id="dash-entries"></tbody></table></div></div>
      </div></div>`;
    document.querySelector('main').prepend(s);
    const [a,b]=bounds();$('dash-from').value=fmt(a);$('dash-to').value=fmt(b);
    $('dash-refresh').onclick=load;$('dash-from').onchange=load;$('dash-to').onchange=load;
    $('dash-month').onclick=()=>{const[x,y]=bounds();$('dash-from').value=fmt(x);$('dash-to').value=fmt(y);load()};
    $('dash-prev').onclick=()=>{const[x,y]=bounds(-1);$('dash-from').value=fmt(x);$('dash-to').value=fmt(y);load()};
    load();
  }

  let data,chart;
  async function load(){
    const f=$('dash-from').value,t=$('dash-to').value;if(!f||!t||f>t){alert('טווח תאריכים לא תקין');return}
    const r=await api(`/api/report/period?from=${encodeURIComponent(f)}&to=${encodeURIComponent(t)}`);if(!r?.ok)return;
    data=await r.json();const s=data.summary||{};$('dash-sub').textContent=`נתונים לתקופה ${data.from} עד ${data.to}`;$('dash-total').textContent=money(s.grand_total);$('dash-regular').textContent=money(s.regular_total);$('dash-extra').textContent=money(s.extra_total);$('dash-days').textContent=s.days_count||0;$('dash-avg').textContent=money(s.average_day);
    const locks=data.locked_months||{};const locked=Object.values(locks).filter(Boolean).length;$('dash-lock').textContent=locked?`🔒 ${locked} חודשים נעולים`:'🟢 התקופה פתוחה לעריכה';$('dash-lock').className='text-xs font-bold '+(locked?'text-amber-600':'text-emerald-600');
    const days=data.day_summary||{},labels=Object.keys(days).sort();if(chart)chart.destroy();if(window.Chart)chart=new Chart($('dash-chart'),{type:'line',data:{labels:labels.map(x=>x.slice(5)),datasets:[{label:'סה״כ',data:labels.map(x=>days[x].total),tension:.3},{label:'שוטף',data:labels.map(x=>days[x].regular),tension:.3},{label:'אקסטרה',data:labels.map(x=>days[x].extra),tension:.3}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{position:'bottom'}},scales:{y:{beginAtZero:true}}}});
    const ps=Object.entries(data.product_summary||{}).sort((a,b)=>b[1].total-a[1].total),max=ps[0]?.[1]?.total||1;$('dash-products').innerHTML=ps.length?ps.map(([n,x])=>`<div><div class="flex justify-between font-bold text-sm"><span>${esc(n)}</span><span>${money(x.total)}</span></div><div class="h-2 bg-slate-100 dark:bg-slate-700 rounded mt-1"><div class="h-2 bg-indigo-500 rounded" style="width:${Math.min(100,x.total/max*100)}%"></div></div></div>`).join(''):'<div class="text-slate-400 text-center py-6">אין נתונים</div>';
    const rows=data.entries||[];$('dash-count').textContent=`${rows.length} חיובים`;$('dash-entries').innerHTML=rows.length?rows.map(e=>`<tr class="border-t hover:bg-slate-50 dark:hover:bg-slate-900"><td class="p-3 font-bold whitespace-nowrap">${esc(e.date)}</td><td class="p-3 font-bold">${esc(e.product_name)}</td><td class="p-3">${esc(e.quantity)}</td><td class="p-3">${e.is_extra?'אקסטרה':'שוטף'}</td><td class="p-3">${money(e.unit_price)}</td><td class="p-3 font-extrabold">${money(e.total_amount)}</td><td class="p-3 max-w-48 truncate">${esc(e.note||'—')}</td><td class="p-3 whitespace-nowrap"><button onclick="window.editDashEntry(${e.id})" class="px-2 py-1 rounded bg-indigo-50 text-indigo-700 font-bold text-xs">ערוך</button><button onclick="window.deleteDashEntry(${e.id})" class="mr-1 px-2 py-1 rounded bg-rose-50 text-rose-700 font-bold text-xs">מחק</button></td></tr>`).join(''):'<tr><td colspan="8" class="p-8 text-center text-slate-400">אין חיובים בטווח</td></tr>';
  }
  window.editDashEntry=async id=>{const e=(data?.entries||[]).find(x=>x.id===id);if(!e)return;const q=prompt(`כמות חדשה עבור ${e.product_name}`,e.quantity);if(q===null)return;const n=prompt('הערה',e.note||'');if(n===null)return;const num=Number(q);if(!Number.isFinite(num)||num<=0){alert('כמות לא תקינה');return}const r=await api(`/api/entries/${id}`,{method:'PUT',headers:{'Content-Type':'application/json','X-Requested-With':'XMLHttpRequest'},body:JSON.stringify({quantity:num,note:n})});const b=r?await r.json():{};if(!r?.ok||!b.success){alert(b.error||'העדכון נכשל');return}load()};
  window.deleteDashEntry=async id=>{if(!confirm('למחוק את החיוב?'))return;const r=await api(`/api/entries/${id}`,{method:'DELETE',headers:{'X-Requested-With':'XMLHttpRequest'}});const b=r?await r.json():{};if(!r?.ok||!b.success){alert(b.error||'המחיקה נכשלה');return}load()};

  function mobile(){if(!matchMedia('(max-width:767px)').matches||$('mobile-quick-actions'))return;const n=document.createElement('nav');n.id='mobile-quick-actions';n.className='fixed bottom-0 inset-x-0 z-40 bg-white/95 dark:bg-slate-800/95 border-t px-2 py-2 flex justify-around shadow-2xl';n.innerHTML=`<a href="#main-dashboard" class="font-bold text-violet-600 text-xs p-2">📊 דשבורד</a><a href="#entry-form-container" class="font-bold text-slate-600 text-xs p-2">📝 יומי</a><a href="${PERIODIC}" class="font-bold text-emerald-600 text-xs p-2">📅 תקופתי</a>`;document.body.appendChild(n);document.body.style.paddingBottom='60px'}
  function keys(){document.addEventListener('keydown',e=>{if(['INPUT','TEXTAREA','SELECT'].includes(e.target?.tagName))return;if(e.key.toLowerCase()==='d')$('main-dashboard')?.scrollIntoView({behavior:'smooth'});if(e.key.toLowerCase()==='r')location.href=PERIODIC;if(e.key==='/'){const x=document.querySelector('input[type=search],input[placeholder*="חיפוש"]');if(x){e.preventDefault();x.focus()}}})}
  function boot(){addNav();createDashboard();mobile();keys()}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);else boot();
})();
