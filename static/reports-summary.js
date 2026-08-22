/* Reports summary owner — extracted incrementally from periodic_report.html. */
(function () {
  'use strict';

  function get(id) {
    return document.getElementById(id);
  }

  function money(value) {
    return (Number(value) || 0).toLocaleString('he-IL', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }) + ' ₪';
  }

  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, function (char) {
      return ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;',
      })[char];
    });
  }

  function unitPrice(entry, products) {
    return entry.unit_price !== null && entry.unit_price !== undefined
      ? Number(entry.unit_price)
      : Number(products?.[entry.product_name] || 0);
  }

  function total(entry, products) {
    return unitPrice(entry, products) * Number(entry.quantity || 0);
  }

  function renderProductSummary(entries, products) {
    const grouped = {};
    entries.forEach(function (entry) {
      if (!grouped[entry.product_name]) grouped[entry.product_name] = { qty: 0, total: 0 };
      grouped[entry.product_name].qty += Number(entry.quantity || 0);
      grouped[entry.product_name].total += total(entry, products);
    });

    const target = get('productSummary');
    if (!target) return;

    target.innerHTML = Object.entries(grouped)
      .sort((a, b) => a[0].localeCompare(b[0], 'he', { sensitivity: 'base' }))
      .map(([name, value]) => `
        <tr class="border-t border-slate-100 dark:border-slate-800">
          <td class="py-2 font-bold">${escapeHtml(name)}</td>
          <td class="py-2 text-center num">${value.qty}</td>
          <td class="py-2 text-left font-extrabold num">${money(value.total)}</td>
        </tr>`)
      .join('') || '<tr><td colspan="3" class="py-6 text-center text-slate-400">אין נתונים</td></tr>';
  }

  function renderDaySummary(entries, products) {
    const grouped = {};
    entries.forEach(function (entry) {
      grouped[entry.date] ??= { reg: 0, ext: 0 };
      const value = total(entry, products);
      entry.is_extra ? grouped[entry.date].ext += value : grouped[entry.date].reg += value;
    });

    const target = get('daySummary');
    if (!target) return;

    target.innerHTML = Object.entries(grouped)
      .sort((a, b) => a[0].localeCompare(b[0]))
      .map(([date, value]) => `
        <tr class="border-t border-slate-100 dark:border-slate-800">
          <td class="py-2 font-bold">${date.split('-').reverse().join('/')}</td>
          <td class="py-2 text-center num">${money(value.reg)}</td>
          <td class="py-2 text-center num">${money(value.ext)}</td>
          <td class="py-2 text-left font-extrabold num">${money(value.reg + value.ext)}</td>
        </tr>`)
      .join('') || '<tr><td colspan="4" class="py-6 text-center text-slate-400">אין נתונים</td></tr>';
  }

  function renderKpis(entries, products) {
    let regular = 0;
    let extra = 0;
    const days = new Set();

    entries.forEach(function (entry) {
      const value = total(entry, products);
      entry.is_extra ? extra += value : regular += value;
      days.add(entry.date);
    });

    const grand = regular + extra;
    if (get('grandTotal')) get('grandTotal').textContent = money(grand);
    if (get('regularTotal')) get('regularTotal').textContent = money(regular);
    if (get('extraTotal')) get('extraTotal').textContent = money(extra);
    if (get('daysCount')) get('daysCount').textContent = days.size;
    if (get('averageDay')) get('averageDay').textContent = money(days.size ? grand / days.size : 0);
  }

  function renderAll(entries, products, renderTable) {
    const safeEntries = Array.isArray(entries) ? entries : [];
    const safeProducts = products || {};
    renderKpis(safeEntries, safeProducts);
    if (typeof renderTable === 'function') renderTable();
    renderProductSummary(safeEntries, safeProducts);
    renderDaySummary(safeEntries, safeProducts);
  }

  window.ReportsSummary = Object.freeze({
    renderAll,
    renderKpis,
    renderProductSummary,
    renderDaySummary,
    total,
    unitPrice,
  });
})();
