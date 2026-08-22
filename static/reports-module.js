/* Unified Reports workspace controller.
 * Owns period controls, report loading, summaries, table rendering,
 * export, edit/delete behavior and the edit drawer presentation contract.
 * Existing global function names are intentionally preserved because the
 * report HTML still uses inline onclick/oninput hooks.
 */
(function () {
  'use strict';

  let entries = [];
  let currentUserRole = 'viewer';
  let products = {};
  let loading = false;

  const $ = (id) => document.getElementById(id);
  const money = (n) => (Number(n) || 0).toLocaleString('he-IL', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }) + ' ₪';
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (m) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[m]);
  const isoToday = () => {
    const d = new Date();
    d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
    return d.toISOString().slice(0, 10);
  };

  function ym(d) { return d.toISOString().slice(0, 7); }
  function parseDate(s) {
    const [y, m, d] = s.split('-').map(Number);
    return new Date(y, m - 1, d);
  }
  function toInput(d) {
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
  }
  function monthList(from, to) {
    const out = [];
    let d = new Date(from.getFullYear(), from.getMonth(), 1);
    const end = new Date(to.getFullYear(), to.getMonth(), 1);
    while (d <= end) {
      out.push(ym(d));
      d.setMonth(d.getMonth() + 1);
    }
    return out;
  }

  async function api(url, opt = {}) {
    opt.headers = opt.headers || {};
    if (['POST', 'PUT', 'DELETE', 'PATCH'].includes((opt.method || 'GET').toUpperCase())) {
      opt.headers['X-Requested-With'] = 'XMLHttpRequest';
    }
    try {
      const r = await fetch(url, opt);
      if (r.status === 401) {
        location.href = '/login';
        return null;
      }
      return r;
    } catch (e) {
      console.error(e);
      alert('שגיאת תקשורת');
      return null;
    }
  }

  function setPreset(p) {
    const now = parseDate(isoToday());
    let from, to;
    if (p === 'current') {
      from = new Date(now.getFullYear(), now.getMonth(), 1);
      to = new Date(now.getFullYear(), now.getMonth() + 1, 0);
    } else if (p === 'previous') {
      from = new Date(now.getFullYear(), now.getMonth() - 1, 1);
      to = new Date(now.getFullYear(), now.getMonth(), 0);
    } else if (p === 'year') {
      from = new Date(now.getFullYear(), 0, 1);
      to = now;
    } else {
      return;
    }
    $('fromDate').value = toInput(from);
    $('toDate').value = toInput(to);
    loadReport();
  }

  function priceOf(e) {
    return e.unit_price !== null && e.unit_price !== undefined
      ? Number(e.unit_price)
      : Number(products[e.product_name] || 0);
  }

  function totalOf(e) { return priceOf(e) * Number(e.quantity || 0); }

  const ReportsSummary = {
    unitPrice: priceOf,
    total: totalOf,
    renderKpis(items) {
      let reg = 0;
      let ext = 0;
      const days = new Set();
      items.forEach((e) => {
        const value = totalOf(e);
        e.is_extra ? ext += value : reg += value;
        days.add(e.date);
      });
      const grand = reg + ext;
      $('grandTotal').textContent = money(grand);
      $('regularTotal').textContent = money(reg);
      $('extraTotal').textContent = money(ext);
      $('daysCount').textContent = days.size;
      $('averageDay').textContent = money(days.size ? grand / days.size : 0);
    },
    renderProductSummary(items) {
      const map = {};
      items.forEach((e) => {
        if (!map[e.product_name]) map[e.product_name] = { qty: 0, total: 0 };
        map[e.product_name].qty += Number(e.quantity || 0);
        map[e.product_name].total += totalOf(e);
      });
      $('productSummary').innerHTML = Object.entries(map)
        .sort((a, b) => a[0].localeCompare(b[0], 'he', { sensitivity: 'base' }))
        .map(([name, value]) => `<tr class="border-t border-slate-100 dark:border-slate-800"><td class="py-2 font-bold">${esc(name)}</td><td class="py-2 text-center num">${value.qty}</td><td class="py-2 text-left font-extrabold num">${money(value.total)}</td></tr>`)
        .join('') || '<tr><td colspan="3" class="py-6 text-center text-slate-400">אין נתונים</td></tr>';
    },
    renderDaySummary(items) {
      const map = {};
      items.forEach((e) => {
        map[e.date] ??= { reg: 0, ext: 0 };
        const value = totalOf(e);
        e.is_extra ? map[e.date].ext += value : map[e.date].reg += value;
      });
      $('daySummary').innerHTML = Object.entries(map)
        .sort((a, b) => a[0].localeCompare(b[0]))
        .map(([date, value]) => `<tr class="border-t border-slate-100 dark:border-slate-800"><td class="py-2 font-bold">${date.split('-').reverse().join('/')}</td><td class="py-2 text-center num">${money(value.reg)}</td><td class="py-2 text-center num">${money(value.ext)}</td><td class="py-2 text-left font-extrabold num">${money(value.reg + value.ext)}</td></tr>`)
        .join('') || '<tr><td colspan="4" class="py-6 text-center text-slate-400">אין נתונים</td></tr>';
    },
    renderAll(items) {
      this.renderKpis(items);
      renderTable();
      this.renderProductSummary(items);
      this.renderDaySummary(items);
    }
  };

  window.ReportsSummary = ReportsSummary;
  window.setPreset = setPreset;
  window.priceOf = priceOf;
  window.totalOf = totalOf;

  function renderAll() { ReportsSummary.renderAll(entries); }
  window.renderAll = renderAll;

  function renderTable() {
    const q = ($('search').value || '').toLowerCase();
    const rows = entries.filter((e) => (e.product_name + ' ' + (e.note || '')).toLowerCase().includes(q));
    const body = $('reportBody');
    $('empty').classList.toggle('hidden', rows.length !== 0);
    if (!rows.length) { body.innerHTML = ''; return; }
    body.innerHTML = rows.map((e) => {
      const value = totalOf(e);
      const actions = currentUserRole === 'viewer' ? '' : `<button onclick="openEdit(${e.id})" class="text-indigo-600 hover:bg-indigo-50 dark:hover:bg-slate-800 p-2 rounded" title="עריכה"><i class="fa-solid fa-pen"></i></button><button onclick="deleteRow(${e.id})" class="text-rose-600 hover:bg-rose-50 dark:hover:bg-slate-800 p-2 rounded" title="מחיקה"><i class="fa-solid fa-trash"></i></button>`;
      return `<tr class="border-t border-slate-100 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-950"><td class="px-4 py-3 font-bold whitespace-nowrap">${esc(e.date.split('-').reverse().join('/'))}</td><td class="px-4 py-3 font-bold">${esc(e.product_name)}</td><td class="px-4 py-3 text-center">${e.is_extra ? '<span class="px-2 py-1 rounded-full bg-amber-100 text-amber-700 text-xs font-bold">אקסטרה</span>' : '<span class="px-2 py-1 rounded-full bg-indigo-100 text-indigo-700 text-xs font-bold">שוטף</span>'}</td><td class="px-4 py-3 text-center num">${esc(e.quantity)}</td><td class="px-4 py-3 text-left num">${money(priceOf(e))}</td><td class="px-4 py-3 text-left font-extrabold num">${money(value)}</td><td class="px-4 py-3 text-right text-slate-500">${esc(e.note || '')}</td><td class="px-4 py-3 text-center no-print whitespace-nowrap">${actions}</td></tr>`;
    }).join('');
  }
  window.renderTable = renderTable;

  async function init() {
    const u = await api('/api/current_user');
    if (u && u.ok) {
      const data = await u.json();
      currentUserRole = data.role || 'viewer';
    }
    const p = await api('/api/products');
    if (p && p.ok) products = await p.json();
    const today = isoToday();
    $('fromDate').value = today.slice(0, 8) + '01';
    $('toDate').value = today;
    await loadReport();
  }

  async function loadReport() {
    if (loading) return;
    const from = $('fromDate').value;
    const to = $('toDate').value;
    const err = $('rangeError');
    err.classList.add('hidden');
    if (!from || !to || from > to) {
      err.textContent = 'טווח תאריכים לא תקין';
      err.classList.remove('hidden');
      return;
    }
    loading = true;
    $('reportBody').innerHTML = '<tr><td colspan="8" class="p-10 text-center text-slate-400"><i class="fa-solid fa-circle-notch fa-spin text-2xl"></i></td></tr>';
    try {
      const all = [];
      for (const month of monthList(parseDate(from), parseDate(to))) {
        const r = await api('/api/report/month/' + month);
        if (r && r.ok) all.push(...await r.json());
      }
      entries = all.filter((e) => e.date >= from && e.date <= to);
      $('periodTitle').textContent = 'תקופה: ' + from.split('-').reverse().join('/') + ' – ' + to.split('-').reverse().join('/');
      renderAll();
    } finally {
      loading = false;
    }
  }
  window.loadReport = loadReport;

  function openEdit(id) {
    const e = entries.find((x) => x.id === id);
    if (!e) return;
    $('editId').value = id;
    $('editProduct').textContent = e.product_name + ' · ' + e.date.split('-').reverse().join('/');
    $('editQty').value = e.quantity;
    $('editNote').value = e.note || '';
    $('editExtra').checked = !!e.is_extra;
    $('editModal').classList.remove('hidden');
    $('editModal').classList.add('flex');
    document.body.classList.add('drawer-open');
    setTimeout(() => $('editQty').focus(), 50);
  }
  window.openEdit = openEdit;

  function closeEdit() {
    $('editModal').classList.add('hidden');
    $('editModal').classList.remove('flex');
    document.body.classList.remove('drawer-open');
  }
  window.closeEdit = closeEdit;

  async function saveEdit() {
    const id = Number($('editId').value);
    const qty = Number($('editQty').value);
    if (!(qty > 0)) { alert('כמות חייבת להיות גדולה מאפס'); return; }
    const r = await api('/api/entries/' + id, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ quantity: qty, note: $('editNote').value.trim(), is_extra: $('editExtra').checked }),
    });
    if (r && r.ok) { closeEdit(); await loadReport(); }
    else if (r) { const data = await r.json().catch(() => ({})); alert(data.error || 'שמירת החיוב נכשלה'); }
  }
  window.saveEdit = saveEdit;

  async function deleteRow(id) {
    if (!confirm('למחוק את החיוב?')) return;
    const r = await api('/api/entries/' + id, { method: 'DELETE' });
    if (r && r.ok) await loadReport();
    else if (r) { const data = await r.json().catch(() => ({})); alert(data.error || 'מחיקת החיוב נכשלה'); }
  }
  window.deleteRow = deleteRow;

  function exportExcel() {
    if (!entries.length) { alert('אין נתונים לייצוא'); return; }
    const data = [['תאריך', 'מוצר', 'סוג', 'כמות', 'מחיר יחידה', 'סה״כ', 'הערה']];
    entries.forEach((e) => data.push([e.date, e.product_name, e.is_extra ? 'אקסטרה' : 'שוטף', e.quantity, priceOf(e), totalOf(e), e.note || '']));
    data.push([]);
    data.push(['', '', '', '', 'סה״כ שוטף', entries.filter((e) => !e.is_extra).reduce((s, e) => s + totalOf(e), 0), '']);
    data.push(['', '', '', '', 'סה״כ אקסטרה', entries.filter((e) => e.is_extra).reduce((s, e) => s + totalOf(e), 0), '']);
    data.push(['', '', '', '', 'סה״כ סופי', entries.reduce((s, e) => s + totalOf(e), 0), '']);
    const wb = XLSX.utils.book_new();
    const ws = XLSX.utils.aoa_to_sheet(data);
    ws['!views'] = [{ rightToLeft: true }];
    XLSX.utils.book_append_sheet(wb, ws, 'דוח חיובים');
    XLSX.writeFile(wb, 'דוח_חיובים_' + $('fromDate').value + '_' + $('toDate').value + '.xlsx');
  }
  window.exportExcel = exportExcel;

  function toggleDark() {
    document.documentElement.classList.toggle('dark');
    localStorage.setItem('theme', document.documentElement.classList.contains('dark') ? 'dark' : 'light');
    $('themeIcon').className = document.documentElement.classList.contains('dark') ? 'fa-solid fa-sun' : 'fa-solid fa-moon';
  }
  window.toggleDark = toggleDark;

  function toggleFullscreen() {
    if (!document.fullscreenElement) document.documentElement.requestFullscreen?.().catch(() => {});
    else document.exitFullscreen?.();
  }
  window.toggleFullscreen = toggleFullscreen;

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && $('editModal') && !$('editModal').classList.contains('hidden')) closeEdit();
  });

  document.addEventListener('click', (event) => {
    if (event.target === $('editModal')) closeEdit();
  });

  if (localStorage.getItem('theme') === 'dark') {
    document.documentElement.classList.add('dark');
    document.addEventListener('DOMContentLoaded', () => {
      if ($('themeIcon')) $('themeIcon').className = 'fa-solid fa-sun';
    }, { once: true });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
