(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, m => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' }[m]));
  const money = (n) => `${(Number(n) || 0).toLocaleString('he-IL',{minimumFractionDigits:2,maximumFractionDigits:2})} ₪`;
  const iso = (d) => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
  const today = () => { const d = new Date(); return new Date(d.getFullYear(), d.getMonth(), d.getDate()); };

  function range(name) {
    const end = today();
    let start = new Date(end);
    if (name === 'week') start.setDate(start.getDate() - 6);
    else if (name === '30days') start.setDate(start.getDate() - 29);
    else if (name === 'month') start = new Date(end.getFullYear(), end.getMonth(), 1);
    else if (name === '3months') start = new Date(end.getFullYear(), end.getMonth() - 2, 1);
    else if (name === 'quarter') start = new Date(end.getFullYear(), Math.floor(end.getMonth()/3)*3, 1);
    else if (name === '6months') start = new Date(end.getFullYear(), end.getMonth() - 5, 1);
    else if (name === 'year') start = new Date(end.getFullYear(), 0, 1);
    return [iso(start), iso(end)];
  }

  function build() {
    if ($('period-display-panel')) return true;
    const left = $('left-panel');
    if (!left) return false;

    const panel = document.createElement('section');
    panel.id = 'period-display-panel';
    panel.className = 'bg-white dark:bg-slate-800 rounded-2xl shadow-sm border-2 border-indigo-200 dark:border-indigo-900 p-4 sm:p-5 print:hidden';
    panel.innerHTML = `
      <div class="flex flex-col gap-3">
        <div class="flex flex-col xl:flex-row xl:items-center xl:justify-between gap-3">
          <div>
            <h3 class="text-lg font-extrabold text-slate-800 dark:text-white flex items-center gap-2">
              <i class="fa-solid fa-calendar-days text-indigo-600 dark:text-indigo-400"></i>
              הצגת דוח לפי תקופה
            </h3>
            <p class="text-xs text-slate-500 dark:text-slate-400 mt-1">הצגה זו נפרדת לחלוטין מהדיווח היומי.</p>
          </div>
          <div class="flex flex-wrap gap-2">
            ${[['week','שבוע'],['30days','30 יום'],['month','חודש'],['3months','3 חודשים'],['quarter','רבעון'],['6months','6 חודשים'],['year','שנה']].map(([k,t]) => `<button type="button" data-range="${k}" class="period-range-btn px-3 py-2 rounded-lg text-xs font-bold bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-200">${t}</button>`).join('')}
            <button type="button" id="period-all-btn" class="px-3 py-2 rounded-lg text-xs font-bold bg-emerald-600 text-white">כל הנתונים</button>
          </div>
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-2">
          <input id="period-from" type="date" class="px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 text-sm font-bold">
          <input id="period-to" type="date" class="px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 text-sm font-bold">
          <button id="period-load-btn" type="button" class="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-bold">הצג תקופה</button>
        </div>
        <div id="period-status" class="text-xs font-bold text-slate-500 dark:text-slate-400"></div>
        <div id="period-summary" class="grid grid-cols-2 lg:grid-cols-5 gap-2"></div>
        <div class="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <div class="border border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden">
            <div class="px-3 py-2 bg-slate-50 dark:bg-slate-900 font-extrabold text-sm">פירוט לפי ימים</div>
            <div class="max-h-72 overflow-auto"><table class="min-w-full text-xs"><thead class="sticky top-0 bg-white dark:bg-slate-800"><tr><th class="p-2 text-right">תאריך</th><th class="p-2">שוטף</th><th class="p-2">אקסטרה</th><th class="p-2">סה״כ</th></tr></thead><tbody id="period-days"></tbody></table></div>
          </div>
          <div class="border border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden">
            <div class="px-3 py-2 bg-slate-50 dark:bg-slate-900 font-extrabold text-sm">פירוט לפי מוצר</div>
            <div class="max-h-72 overflow-auto"><table class="min-w-full text-xs"><thead class="sticky top-0 bg-white dark:bg-slate-800"><tr><th class="p-2 text-right">מוצר</th><th class="p-2">כמות</th><th class="p-2">סה״כ</th></tr></thead><tbody id="period-products"></tbody></table></div>
          </div>
        </div>
      </div>`;

    left.insertBefore(panel, left.firstElementChild);

    panel.querySelectorAll('.period-range-btn').forEach(btn => btn.addEventListener('click', () => {
      panel.querySelectorAll('.period-range-btn').forEach(x => x.classList.remove('bg-indigo-600','text-white'));
      panel.querySelectorAll('.period-range-btn').forEach(x => x.classList.add('bg-slate-100','dark:bg-slate-700','text-slate-700','dark:text-slate-200'));
      btn.classList.remove('bg-slate-100','dark:bg-slate-700','text-slate-700','dark:text-slate-200');
      btn.classList.add('bg-indigo-600','text-white');
      const [from,to] = range(btn.dataset.range);
      $('period-from').value = from; $('period-to').value = to; load(from,to);
    }));

    $('period-all-btn').addEventListener('click', async () => {
      const r = await fetch('/api/report/all', { credentials: 'same-origin', cache: 'no-store' });
      if (r.ok) render(await r.json());
      else load('2000-01-01', iso(today()));
    });
    $('period-load-btn').addEventListener('click', () => load($('period-from').value, $('period-to').value));
    return true;
  }

  async function load(from,to) {
    if (!from || !to || from > to) return;
    $('period-status').textContent = 'טוען נתוני תקופה...';
    try {
      const r = await fetch(`/api/report/period?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`, { credentials:'same-origin', cache:'no-store' });
      if (r.status === 401) { location.href = '/login'; return; }
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      render(await r.json());
    } catch (e) {
      console.error(e);
      $('period-status').textContent = 'שגיאה בטעינת הדוח';
    }
  }

  function render(data) {
    const s = data.summary || {};
    $('period-status').textContent = data.from && data.to ? `טווח: ${data.from.split('-').reverse().join('/')} — ${data.to.split('-').reverse().join('/')}` : '';
    $('period-summary').innerHTML = [
      ['סה״כ', money(s.grand_total)],
      ['שוטף', money(s.regular_total)],
      ['אקסטרה', money(s.extra_total)],
      ['ימי דיווח', Number(s.days_count||0).toLocaleString('he-IL')],
      ['ממוצע ליום', money(s.average_day)]
    ].map(([k,v]) => `<div class="rounded-xl border border-slate-200 dark:border-slate-700 p-3"><div class="text-[11px] text-slate-500 dark:text-slate-400 font-bold">${k}</div><div class="text-lg font-extrabold mt-1">${v}</div></div>`).join('');

    const days = data.day_summary || {};
    $('period-days').innerHTML = Object.entries(days).sort((a,b)=>b[0].localeCompare(a[0])).map(([d,x]) => `<tr class="border-t border-slate-100 dark:border-slate-700"><td class="p-2 font-bold">${esc(d.split('-').reverse().join('/'))}</td><td class="p-2 text-center">${money(x.regular)}</td><td class="p-2 text-center">${money(x.extra)}</td><td class="p-2 text-center font-extrabold">${money(x.total)}</td></tr>`).join('') || '<tr><td colspan="4" class="p-5 text-center text-slate-400">אין דיווחים בטווח</td></tr>';

    const products = data.product_summary || {};
    $('period-products').innerHTML = Object.entries(products).sort((a,b)=>Number(b[1].total||0)-Number(a[1].total||0)).map(([name,x]) => `<tr class="border-t border-slate-100 dark:border-slate-700"><td class="p-2 font-bold">${esc(name)}</td><td class="p-2 text-center">${Number(x.quantity||0).toLocaleString('he-IL')}</td><td class="p-2 text-center font-extrabold">${money(x.total)}</td></tr>`).join('') || '<tr><td colspan="3" class="p-5 text-center text-slate-400">אין נתונים</td></tr>';
  }

  function init() {
    if (!build()) return setTimeout(init, 500);
    const [from,to] = range('3months');
    $('period-from').value = from; $('period-to').value = to;
    const defaultBtn = document.querySelector('.period-range-btn[data-range="3months"]');
    if (defaultBtn) { defaultBtn.classList.remove('bg-slate-100','dark:bg-slate-700','text-slate-700','dark:text-slate-200'); defaultBtn.classList.add('bg-indigo-600','text-white'); }
    load(from,to);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
