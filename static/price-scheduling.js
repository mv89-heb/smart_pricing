(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const today = () => { const d = new Date(); d.setMinutes(d.getMinutes() - d.getTimezoneOffset()); return d.toISOString().slice(0, 10); };
  const esc = s => String(s ?? '').replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const api = async (url, options = {}) => {
    options.credentials = 'same-origin';
    options.headers = { ...(options.headers || {}) };
    if (['POST','PUT','PATCH','DELETE'].includes((options.method || 'GET').toUpperCase())) options.headers['X-Requested-With'] = 'XMLHttpRequest';
    try {
      const r = await fetch(url, options);
      if (r.status === 401) { location.href = '/login'; return null; }
      return r;
    } catch (_) { toast('שגיאת תקשורת עם השרת', 'error'); return null; }
  };
  const toast = (message, type = 'success') => {
    if (typeof window.showToast === 'function') return window.showToast(message, type);
    const old = $('price-schedule-toast'); if (old) old.remove();
    const el = document.createElement('div'); el.id = 'price-schedule-toast';
    el.className = `fixed top-24 left-4 z-[10000] px-4 py-3 rounded-xl shadow-xl text-sm font-bold text-white ${type === 'error' ? 'bg-rose-600' : 'bg-slate-900'}`;
    el.textContent = message; document.body.appendChild(el); setTimeout(() => el.remove(), 3000);
  };

  const priceCache = new Map();
  let priceRequestToken = 0;
  const invalidatePriceCache = () => priceCache.clear();

  function installEffectiveDate() {
    const form = $('product-form');
    if (!form || $('prod-effective-from')) return;
    const wrap = document.createElement('div');
    wrap.id = 'global-effective-date-wrap';
    wrap.className = 'rounded-lg border border-indigo-100 dark:border-slate-700 bg-indigo-50/50 dark:bg-indigo-950/20 p-3 mt-3';
    wrap.innerHTML = `<div class="flex flex-col sm:flex-row sm:items-end gap-2"><div class="flex-1"><label for="prod-effective-from" class="block text-xs font-bold text-indigo-700 dark:text-indigo-300 mb-1">תאריך תוקף לעדכוני המחירון</label><input type="date" id="prod-effective-from" class="w-full px-3 py-2 border border-indigo-200 dark:border-slate-600 rounded-lg outline-none focus:ring-2 focus:ring-indigo-500 text-sm bg-white dark:bg-slate-900 dark:text-white"><p class="text-[11px] text-slate-500 mt-1">מגדירים פעם אחת והתאריך נשמר כברירת המחדל לכל המוצרים.</p></div><button type="button" id="remember-effective-date" class="px-3 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold">קבע כברירת מחדל</button></div>`;
    const anchor = $('prod-tag')?.closest('.space-y-3') || $('prod-tag')?.parentElement;
    if (anchor?.parentElement) anchor.parentElement.insertBefore(wrap, anchor.nextSibling); else form.insertBefore(wrap, form.lastElementChild);
    $('prod-effective-from').value = localStorage.getItem('global_price_effective_from') || today();
    $('prod-effective-from').addEventListener('change', () => localStorage.setItem('global_price_effective_from', $('prod-effective-from').value));
    $('remember-effective-date').addEventListener('click', () => {
      const value = $('prod-effective-from').value;
      if (!value) return toast('בחר תאריך תוקף', 'error');
      localStorage.setItem('global_price_effective_from', value);
      toast(`תאריך ${value.split('-').reverse().join('/')} נשמר כברירת המחדל`);
    });
  }

  async function refreshScheduledPanel() {
    const form = $('product-form'); if (!form || !$('right-panel')) return;
    let panel = $('scheduled-price-panel');
    if (!panel) { panel = document.createElement('div'); panel.id = 'scheduled-price-panel'; panel.className = 'px-4 pb-3'; form.insertAdjacentElement('afterend', panel); }
    const r = await api('/api/products/details'); if (!r || !r.ok) return;
    const products = await r.json().catch(() => []);
    const scheduled = products.filter(p => p.scheduled_price);
    if (!scheduled.length) { panel.innerHTML = ''; return; }
    panel.innerHTML = `<div class="rounded-xl border border-amber-200 dark:border-amber-900/50 bg-amber-50/70 dark:bg-amber-950/20 p-3"><div class="text-xs font-extrabold text-amber-700 dark:text-amber-300 mb-2">מחירים מתוזמנים</div><div class="space-y-2">${scheduled.map(p => `<div class="flex items-center justify-between gap-2 text-xs"><div><span class="font-bold">${esc(p.name)}</span><span class="text-slate-500 mr-2">₪${Number(p.scheduled_price.price).toFixed(2)} מ-${esc(p.scheduled_price.effective_from.split('-').reverse().join('/'))}</span></div><button type="button" class="cancel-scheduled-price text-rose-600 font-bold hover:underline" data-name="${esc(p.name)}">בטל</button></div>`).join('')}</div></div>`;
    panel.querySelectorAll('.cancel-scheduled-price').forEach(btn => btn.addEventListener('click', async () => {
      if (!confirm(`לבטל את כל המחירים העתידיים עבור ${btn.dataset.name}?`)) return;
      const res = await api(`/api/products/${encodeURIComponent(btn.dataset.name)}/scheduled`, { method: 'DELETE' });
      if (res && res.ok) { toast('המחיר העתידי בוטל'); invalidatePriceCache(); await refreshScheduledPanel(); if (typeof window.loadProducts === 'function') await window.loadProducts(); }
      else toast('לא ניתן לבטל את המחיר העתידי', 'error');
    }));
  }

  function installProductSubmit() {
    const form = $('product-form'); if (!form || form.dataset.stablePriceSubmit === '1') return;
    form.dataset.stablePriceSubmit = '1';
    form.addEventListener('submit', async event => {
      event.preventDefault(); event.stopImmediatePropagation();
      const name = ($('prod-name')?.value || '').trim();
      const price = $('prod-price')?.value;
      const tag = ($('prod-tag')?.value || '').trim();
      const original = ($('prod-edit-original-name')?.value || '').trim();
      const effective = $('prod-effective-from')?.value || localStorage.getItem('global_price_effective_from') || today();
      if (!name || price === '' || !effective) return toast('יש למלא מוצר, מחיר ותאריך תוקף', 'error');
      const numericPrice = Number(price);
      if (!Number.isFinite(numericPrice) || numericPrice < 0) return toast('מחיר לא תקין', 'error');
      localStorage.setItem('global_price_effective_from', effective);
      const editing = Boolean(original);
      const url = editing ? `/api/products/${encodeURIComponent(original)}` : '/api/products';
      const method = editing ? 'PUT' : 'POST';
      const res = await api(url, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name, price: numericPrice, tag, effective_from: effective }) });
      const data = res ? await res.json().catch(() => ({})) : {};
      if (!res || !res.ok) return toast(data.error || 'שגיאה בשמירת המוצר', 'error');
      invalidatePriceCache();
      if (typeof window.cancelProductEdit === 'function') window.cancelProductEdit();
      if ($('prod-effective-from')) $('prod-effective-from').value = effective;
      toast(effective > today() ? `המחיר תוזמן ל-${effective.split('-').reverse().join('/')}` : 'המוצר עודכן בהצלחה');
      if (typeof window.loadProducts === 'function') await window.loadProducts();
      await refreshScheduledPanel();
    }, true);
  }

  async function effectivePrice(name, date) {
    const key = `${name}@@${date}`;
    if (priceCache.has(key)) return priceCache.get(key);
    const r = await api(`/api/products/${encodeURIComponent(name)}/history`); if (!r || !r.ok) return null;
    const rows = await r.json().catch(() => []);
    const valid = Array.isArray(rows) ? rows.filter(x => x?.effective_from && x.effective_from <= date) : [];
    if (!valid.length) return null;
    valid.sort((a,b) => a.effective_from !== b.effective_from ? a.effective_from.localeCompare(b.effective_from) : Number(a.id || 0) - Number(b.id || 0));
    const value = Number(valid[valid.length - 1].price);
    if (!Number.isFinite(value)) return null;
    priceCache.set(key, value); return value;
  }

  function quantity() {
    const raw = ($('entry-qty')?.value || '1').trim();
    if (!/^[\d\.\+\-\*\/\(\)\s]+$/.test(raw)) return 0;
    try { const value = Function('"use strict";return (' + raw + ')')(); return Number.isFinite(value) && value > 0 ? value : 0; } catch (_) { return 0; }
  }

  window.updateLivePreview = async function () {
    const name = $('entry-prod-select-ui')?.value, qty = quantity(), box = $('live-preview-box');
    if (!box) return;
    const token = ++priceRequestToken;
    if (!name || qty <= 0) { box.textContent = ''; return; }
    box.textContent = 'מעדכן מחיר...';
    const date = $('current-date')?.value || today();
    const price = await effectivePrice(name, date);
    if (token !== priceRequestToken) return;
    if (price === null) { box.textContent = 'לא ניתן לטעון מחיר'; return; }
    box.textContent = `מחיר ${price.toLocaleString('he-IL',{minimumFractionDigits:2,maximumFractionDigits:2})} ₪ × ${qty} = סה"כ ${(Math.round(price * qty * 100) / 100).toLocaleString('he-IL',{minimumFractionDigits:2,maximumFractionDigits:2})} ₪`;
  };

  function installPreviewSync() {
    const date = $('current-date'), qty = $('entry-qty'), select = $('entry-prod-select-ui');
    if (date && date.dataset.stablePriceSync !== '1') { date.dataset.stablePriceSync = '1'; date.addEventListener('change', () => { invalidatePriceCache(); window.updateLivePreview(); }); }
    if (qty && qty.dataset.stablePriceSync !== '1') { qty.dataset.stablePriceSync = '1'; qty.addEventListener('input', window.updateLivePreview); }
    if (select && select.dataset.stablePriceSync !== '1') { select.dataset.stablePriceSync = '1'; select.addEventListener('change', window.updateLivePreview); }
  }

  function installBulkUpdate() {
    if (typeof window.bulkUpdatePrices !== 'function' || window.bulkUpdatePrices.__stable) return;
    window.bulkUpdatePrices = async function () {
      if (!window.products || !Object.keys(window.products).length) return toast('המחירון ריק', 'error');
      const promptFn = window.customPrompt;
      const value = await promptFn('הזן אחוז לעדכון גורף של כל המחירון (לדוגמה: 5, -5):', '', 'number');
      if (!value) return;
      const percent = Number(value);
      if (!Number.isFinite(percent)) return toast('נא להזין מספר תקין', 'error');
      const names = Object.keys(window.products);
      if (!confirm(`האם לעדכן את כל ${names.length} המוצרים ב-${percent}%?`)) return;
      const effective = $('prod-effective-from')?.value || localStorage.getItem('global_price_effective_from') || today();
      localStorage.setItem('global_price_effective_from', effective);
      let success = 0;
      for (const name of names) {
        const oldPrice = Number(window.products[name]);
        const newPrice = Math.round(oldPrice * (1 + percent / 100) * 100) / 100;
        const r = await api(`/api/products/${encodeURIComponent(name)}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name, price: newPrice, effective_from: effective }) });
        if (r?.ok) success++;
      }
      invalidatePriceCache();
      toast(`עודכנו ${success} מתוך ${names.length} מוצרים`);
      if (typeof window.loadProducts === 'function') await window.loadProducts();
      await refreshScheduledPanel();
      window.updateLivePreview();
    };
    window.bulkUpdatePrices.__stable = true;
  }

  function init() {
    installEffectiveDate();
    installProductSubmit();
    installPreviewSync();
    installBulkUpdate();
    refreshScheduledPanel();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();

  let observerInstalled = false;
  const observeRightPanel = () => {
    const panel = $('right-panel');
    if (!panel || observerInstalled) return;
    observerInstalled = true;
    const observer = new MutationObserver(() => {
      installEffectiveDate();
      installProductSubmit();
      installPreviewSync();
      installBulkUpdate();
    });
    observer.observe(panel, { childList: true, subtree: true });
  };
  observeRightPanel();
  if (!observerInstalled) {
    const bootstrap = new MutationObserver(() => {
      if (!observerInstalled) observeRightPanel();
      if (observerInstalled) bootstrap.disconnect();
    });
    bootstrap.observe(document.body, { childList: true, subtree: true });
  }
  window.refreshScheduledPrices = refreshScheduledPanel;
})();
