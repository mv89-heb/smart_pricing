(() => {
  'use strict';

  const $ = (id) => document.getElementById(id);
  const money = (n) => (Number(n) || 0).toLocaleString('he-IL', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' ₪';
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, m => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' }[m]));

  function iso(d) {
    const x = new Date(d.getFullYear(), d.getMonth(), d.getDate());
    return x.getFullYear() + '-' + String(x.getMonth()+1).padStart(2,'0') + '-' + String(x.getDate()).padStart(2,'0');
  }

  function parse(s) {
    const [y,m,d] = String(s).split('-').map(Number);
    return new Date(y, m-1, d);
  }

  function today() {
    const d = new Date();
    return new Date(d.getFullYear(), d.getMonth(), d.getDate());
  }

  function presetRange(name) {
    const end = today();
    let start = new Date(end);
    if (name === 'week') start.setDate(start.getDate() - 6);
    else if (name === 'month') start = new Date(end.getFullYear(), end.getMonth(), 1);
    else if (name === '3months') start = new Date(end.getFullYear(), end.getMonth() - 2, 1);
    else if (name === 'quarter') {
      const q = Math.floor(end.getMonth() / 3);
      start = new Date(end.getFullYear(), q * 3, 1);
    } else if (name === 'year') start = new Date(end.getFullYear(), 0, 1);
    else if (name === '30days') start.setDate(start.getDate() - 29);
    return [iso(start), iso(end)];
  }

  async function api(url) {
    try {
      const r = await fetch(url, { credentials: 'same-origin' });
      if (r.status === 401) { location.href = '/login'; return null; }
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return await r.json();
    } catch (e) {
      console.error(e);
      return null;
    }
  }

  function buildPanel() {
    if ($('period-display-panel')) return $('period-display-panel');
    const left = $('left-panel');
    if (!left) return null;

    const panel = document.createElement('section');
    panel.id = 'period-display-panel';
    panel.className = 'bg-white dark:bg-slate-800 rounded-2xl shadow-sm border border-indigo-200 dark:border-indigo-900/60 p-4 sm:p-5 print:hidden';
    panel.innerHTML = `
      <div class="flex flex-col xl:flex-row gap-4 justify-between xl:items-center">
        <div>
          <div class="flex items-center gap-2">
            <i class="fa-solid fa-calendar-days text-indigo-600 dark:text-indigo-400"></i>
            <h3 class="font-extrabold text-lg">תצוגת דוח לפי תקופה</h3>
          </div>
          <p class="text-xs text-slate-500 mt-1">הדיווח היומי נשאר נפרד. כאן ניתן לצפות בכל החיובים שכבר דווחו.</p>
        </div>
        <div class="flex flex-wrap gap-2 items-center">
          <button data-range="week" class="period-preset px-3 py-1.5 rounded-lg bg-slate-100 dark:bg-slate-700 text-xs font-bold">שבוע</button>
          <button data-range="30days" class="period-preset px-3 py-1.5 rounded-lg bg-slate-100 dark:bg-slate-700 text-xs font-bold">30 יום</button>
          <button data-range="month" class="period-preset px-3 py-1.5 rounded-lg bg-slate-100 dark:bg-slate-700 text-xs font-bold">חודש</button>
          <button data-range="3months" class="period-preset px-3 py-1.5 rounded-lg bg-indigo-600 text-white text-xs font-bold">3 חודשים</button>
          <button data-range="quarter" class="period-preset px-3 py-1.5 rounded-lg bg-slate-100 dark:bg-slate-700 text-xs font-bold">רבעון</button>
          <button data-range="year" class="period-preset px-3 py-1.5 rounded-lg bg-slate-100 dark:bg-slate-700 text-xs font-bold">מתחילת השנה</button>
          <button data-range="all" class="period-preset px-3 py-1.5 rounded-lg bg-slate-100 dark:bg-slate-700 text-xs font-bold">כל הנתונים</button>
        </div>
      </div>
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-2 mt-4">
        <input id="period-from" type="date" class="px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 text-sm font-bold">
        <input id="period-to" type="date" class="px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 text-sm font-bold">
        <button id="period-load" class="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-bold">הצג תקופה</button>
        <button id="period-clear" class="px-4 py-2 rounded-lg bg-slate-100 dark:bg-slate-700 text-sm font-bold">נקה תצוגה</button>
        <div id="period-range-label" class="px-3 py-2 rounded-lg bg-indigo-50 dark:bg-indigo-950/30 text-indigo-700 dark:text-indigo-300 text-xs font-bold flex items-center justify-center"></div>
      </div>
      <div id="period-summary" class="grid grid-cols-2 lg:grid-cols-5 gap-2 mt-4"></div>
      <div class="grid grid-cols-1 xl:grid-cols-2 gap-4 mt-4">
        <div class="border border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden">
          <div class="px-3 py-2 bg-slate-50 dark:bg-slate-900 font-extrabold text-sm">סיכום לפי ימים</div>
          <div class="max-h-72 overflow-auto"><table class="min-w-full text-xs"><thead class="sticky top-0 bg-white dark:bg-slate-800"><tr><th class="p-2 text-right">תאריך</th><th class="p-2 text-center">שוטף</th><th class="p-2 text-center">אקסטרה</th><th class="p-2 text-left">סה״כ</th></tr></thead><tbody id="period-days"></tbody></table></div>
        </div>
        <div class="border border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden">
          <div class="px-3 py-2 bg-slate-50 dark:bg-slate-900 font-extrabold text-sm">סיכום לפי מוצר</div>
          <div class="max-h-72 overflow-auto"><table class="min-w-full text-xs"><thead class="sticky top-0 bg-white dark:bg-slate-800"><tr><th class="p-2 text-right">מוצר</th><th class="p-2 text-center">כמות</th><th class="p-2 text-left">סה״כ</th></tr></thead><tbody id="period-products"></tbody></table></div>
        </div>
      </div>
      <div id="period-empty" class="hidden mt-4 p-6 rounded-xl bg-slate-50 dark:bg-slate-900 text-center text-slate-500 text-sm font-bold">אין חיובים בטווח שנבחר.</div>`;

    const toolbar = left.querySelector('div.bg-white');
    if (toolbar) toolbar.insertAdjacentElement('afterend', panel);
    else left.prepend(panel);

    panel.querySelectorAll('.period-preset').forEach(btn => btn.addEventListener('click', () => {
      const range = btn.dataset.range;
      if (range === 'all') return loadAll();
      const [from, to] = presetRange(range);
      $('period-from').value = from;
      $('period-to').value = to;
      loadPeriod(from, to);
    }));
    $('period-load').addEventListener('click', () => loadPeriod($('period-from').value, $('period-to').value));
    $('period-clear').addEventListener('click', () => {
      $('period-summary').innerHTML = '';
      $('period-days').innerHTML = '';
      $('period-products').innerHTML = '';
      $('period-empty').classList.add('hidden');
      $('period-range-label').textContent = '';
    });
    return panel;
  }

  function render(data) {
    const s = data?.summary || {};
    $('period-range-label').textContent = data?.from && data?.to ? `${data.from.split('-').reverse().join('/')} — ${data.to.split('-').reverse().join('/')}` : '';
    $('period-summary').innerHTML = [
      ['סה״כ', money(s.grand_total)],
      ['שוטף', money(s.regular_total)],
      ['אקסטרה', money(s.extra_total)],
      ['ימי חיוב', Number(s.days_count || 0).toLocaleString('he-IL')],
      ['ממוצע ליום', money(s.average_day)]
    ].map(([label, value]) => `<div class="rounded-xl border border-slate-200 dark:border-slate-700 p-3"><div class="text-[11px] text-slate-500 font-bold">${label}</div><div class="font-extrabold mt-1">${value}</div></div>`).join('');

    const days = Object.entries(data?.day_summary || {}).sort((a,b) => a[0].localeCompare(b[0]));
    $('period-days').innerHTML = days.map(([date,x]) => `<tr class="border-t border-slate-100 dark:border-slate-700"><td class="p-2 font-bold">${esc(date.split('-').reverse().join('/'))}</td><td class="p-2 text-center">${money(x.regular)}</td><td class="p-2 text-center">${money(x.extra)}</td><td class="p-2 text-left font-extrabold">${money(x.total)}</td></tr>`).join('');

    const products = Object.entries(data?.product_summary || {}).sort((a,b) => Number(b[1].total||0)-Number(a[1].total||0));
    $('period-products').innerHTML = products.map(([name,x]) => `<tr class="border-t border-slate-100 dark:border-slate-700"><td class="p-2 font-bold">${esc(name)}</td><td class="p-2 text-center">${Number(x.quantity||0).toLocaleString('he-IL')}</td><td class="p-2 text-left font-extrabold">${money(x.total)}</td></tr>`).join('');
    const empty = !days.length;
    $('period-empty').classList.toggle('hidden', !empty);
  }

  async function loadPeriod(from, to) {
    if (!from || !to || from > to) return;
    const data = await api(`/api/report/period?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`);
    if (data) render(data);
  }

  async function loadAll() {
    const data = await api('/api/report/all');
    if (data) render(data);
  }

  function init() {
    if (!buildPanel()) return;
    const [from, to] = presetRange('3months');
    $('period-from').value = from;
    $('period-to').value = to;
    loadPeriod(from, to);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
