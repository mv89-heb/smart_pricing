(() => {
  'use strict';

  const $ = (id) => document.getElementById(id);
  const today = () => {
    const d = new Date();
    d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
    return d.toISOString().slice(0, 10);
  };
  const esc = (s) => String(s ?? '').replace(/[&<>\"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[m]));

  async function api(url, options = {}) {
    options.credentials = 'same-origin';
    options.headers = {...(options.headers || {})};
    if (['POST','PUT','PATCH','DELETE'].includes((options.method || 'GET').toUpperCase())) {
      options.headers['X-Requested-With'] = 'XMLHttpRequest';
    }
    try {
      const r = await fetch(url, options);
      if (r.status === 401) { location.href = '/login'; return null; }
      return r;
    } catch (_) {
      toast('שגיאת תקשורת עם השרת', 'error');
      return null;
    }
  }

  function toast(message, type = 'success') {
    if (typeof window.showToast === 'function') return window.showToast(message, type);
    const old = $('price-schedule-toast');
    if (old) old.remove();
    const el = document.createElement('div');
    el.id = 'price-schedule-toast';
    el.className = `fixed top-24 left-4 z-[10000] px-4 py-3 rounded-xl shadow-xl text-sm font-bold text-white ${type === 'error' ? 'bg-rose-600' : 'bg-slate-900'}`;
    el.textContent = message;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 3000);
  }

  /* ----------------------------------------------------------------------
     WORKSPACES
     The dashboard, daily billing and pricing list are three separate views.
     The original page renders daily + pricing in one grid, so we explicitly
     control visibility and remove BOTH hiding classes used by older scripts.
  ---------------------------------------------------------------------- */
  function installWorkspaceCss() {
    if ($('billing-workspace-css')) return;
    const s = document.createElement('style');
    s.id = 'billing-workspace-css';
    s.textContent = `
      .billing-workspace-hidden { display:none !important; }
      main > .grid.billing-workspace-full { display:grid !important; grid-column:1/-1 !important; width:100% !important; }
      main > .grid.billing-workspace-full > #left-panel,
      main > .grid.billing-workspace-full > #right-panel { width:100% !important; grid-column:1/-1 !important; }
    `;
    document.head.appendChild(s);
  }

  function setHidden(el, hidden) {
    if (!el) return;
    el.classList.toggle('billing-workspace-hidden', hidden);
    // Remove legacy classes which previously caused the empty-screen bug.
    el.classList.remove('ux-hidden');
    if (hidden) el.classList.add('billing-workspace-hidden');
  }

  function setWorkspace(view, options = {}) {
    installWorkspaceCss();

    const dashboard = $('ux-dashboard');
    const grid = document.querySelector('main > .grid');
    const daily = $('left-panel');
    const pricing = $('right-panel');

    if (!grid || !daily || !pricing) return false;

    // Dashboard is independent from the daily/pricing workspace.
    if (view === 'dashboard') {
      setHidden(dashboard, false);
      setHidden(grid, true);
      grid.classList.remove('billing-workspace-full');
    } else if (view === 'daily' || view === 'pricing') {
      setHidden(dashboard, true);
      setHidden(grid, false);
      grid.classList.add('billing-workspace-full');
      setHidden(daily, view !== 'daily');
      setHidden(pricing, view !== 'pricing');
    } else {
      return false;
    }

    document.querySelectorAll('#ux-shell-nav [data-v]').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.v === view);
    });

    // Load the selected workspace every time it becomes visible.
    if (!options.skipLoad) {
      if (view === 'daily') {
        if (typeof window.loadEntries === 'function') {
          try { window.loadEntries(); } catch (_) {}
        }
      }
      if (view === 'pricing') {
        if (typeof window.loadProducts === 'function') {
          try { window.loadProducts(); } catch (_) {}
        }
        refreshScheduledPanel();
      }
    }

    window.scrollTo({ top: 0, behavior: 'smooth' });
    return true;
  }

  function installWorkspaceNavigation() {
    const nav = $('ux-shell-nav');
    if (!nav || nav.dataset.workspaceFixed === '1') return;
    nav.dataset.workspaceFixed = '1';

    // Capture phase prevents the older ux-enhancements handler from running
    // after this handler and hiding the grid again.
    nav.addEventListener('click', (event) => {
      const btn = event.target.closest('[data-v]');
      if (!btn) return;
      const view = btn.dataset.v;
      if (!['dashboard', 'daily', 'pricing'].includes(view)) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      setWorkspace(view);
    }, true);

    // Dashboard is the safe initial state, but only if the dashboard exists.
    if ($('ux-dashboard')) setWorkspace('dashboard', {skipLoad: true});
  }

  /* ----------------------------------------------------------------------
     PRICE SCHEDULING
  ---------------------------------------------------------------------- */
  function inject() {
    const form = $('product-form');
    if (!form || $('prod-effective-from')) return;

    const wrap = document.createElement('div');
    wrap.className = 'rounded-lg border border-indigo-100 dark:border-slate-700 bg-indigo-50/50 dark:bg-indigo-950/20 p-3';
    wrap.innerHTML = `
      <label class="block text-xs font-bold text-indigo-700 dark:text-indigo-300 mb-1">מחיר תקף החל מתאריך</label>
      <input type="date" id="prod-effective-from" class="w-full px-3 py-2 border border-indigo-200 dark:border-slate-600 rounded-lg outline-none focus:ring-2 focus:ring-indigo-500 text-sm bg-white dark:bg-slate-900 dark:text-white">
      <p class="text-[11px] text-slate-500 mt-1">שינוי עתידי לא משנה חיובים שכבר נרשמו.</p>`;

    const tag = $('prod-tag')?.parentElement?.parentElement;
    if (tag) tag.insertAdjacentElement('afterend', wrap);
    else form.insertBefore(wrap, form.lastElementChild);

    $('prod-effective-from').value = today();

    const info = document.createElement('div');
    info.id = 'scheduled-price-panel';
    info.className = 'px-4 pb-3';
    form.insertAdjacentElement('afterend', info);
    refreshScheduledPanel();
  }

  async function refreshScheduledPanel() {
    const panel = $('scheduled-price-panel');
    if (!panel) return;
    const r = await api('/api/products/details');
    if (!r || !r.ok) return;
    const products = await r.json().catch(() => []);
    const scheduled = products.filter(p => p.scheduled_price);
    if (!scheduled.length) { panel.innerHTML = ''; return; }

    panel.innerHTML = `<div class="rounded-xl border border-amber-200 dark:border-amber-900/50 bg-amber-50/70 dark:bg-amber-950/20 p-3">
      <div class="text-xs font-extrabold text-amber-700 dark:text-amber-300 mb-2">מחירים מתוזמנים</div>
      <div class="space-y-2">${scheduled.map(p => `<div class="flex items-center justify-between gap-2 text-xs">
        <div><span class="font-bold">${esc(p.name)}</span><span class="text-slate-500 mr-2">₪${Number(p.scheduled_price.price).toFixed(2)} מ-${esc(p.scheduled_price.effective_from.split('-').reverse().join('/'))}</span></div>
        <button type="button" class="cancel-scheduled-price text-rose-600 font-bold hover:underline" data-name="${esc(p.name)}">בטל</button>
      </div>`).join('')}</div></div>`;

    panel.querySelectorAll('.cancel-scheduled-price').forEach(btn => btn.addEventListener('click', async () => {
      if (!confirm(`לבטל את כל המחירים העתידיים עבור ${btn.dataset.name}?`)) return;
      const res = await api(`/api/products/${encodeURIComponent(btn.dataset.name)}/scheduled`, {method:'DELETE'});
      if (res && res.ok) {
        toast('המחיר העתידי בוטל');
        refreshScheduledPanel();
        if (typeof window.loadProducts === 'function') window.loadProducts();
      } else toast('לא ניתן לבטל את המחיר העתידי', 'error');
    }));
  }

  function installSubmitGuard() {
    const form = $('product-form');
    if (!form || form.dataset.scheduleGuard === '1') return;
    form.dataset.scheduleGuard = '1';

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      event.stopImmediatePropagation();

      const name = ($('prod-name')?.value || '').trim();
      const price = $('prod-price')?.value;
      const tag = ($('prod-tag')?.value || '').trim();
      const effective = $('prod-effective-from')?.value || today();
      const original = ($('prod-edit-original-name')?.value || '').trim();

      if (!name || price === '' || !effective) {
        toast('יש למלא מוצר, מחיר ותאריך', 'error');
        return;
      }

      const editing = Boolean(original);
      const url = editing ? `/api/products/${encodeURIComponent(original)}` : '/api/products';
      const method = editing ? 'PUT' : 'POST';
      const res = await api(url, {
        method,
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({name, price:Number(price), tag, effective_from:effective})
      });
      const data = res ? await res.json().catch(() => ({})) : {};

      if (res && res.ok) {
        toast(effective > today() ? `מחיר ₪${Number(price).toFixed(2)} תוזמן ל-${effective.split('-').reverse().join('/')}` : 'המחיר עודכן');
        if ($('prod-effective-from')) $('prod-effective-from').value = today();
        if (typeof window.cancelProductEdit === 'function') window.cancelProductEdit();
        if (typeof window.loadProducts === 'function') await window.loadProducts();
        refreshScheduledPanel();
      } else {
        toast(data.error || 'שגיאה בעדכון המחיר', 'error');
      }
    }, true);
  }

  function observe() {
    const observer = new MutationObserver(() => {
      installWorkspaceNavigation();
      inject();
      installSubmitGuard();
    });
    observer.observe(document.body, {childList:true, subtree:true});
    installWorkspaceNavigation();
    inject();
    installSubmitGuard();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', observe);
  } else {
    observe();
  }

  window.refreshScheduledPrices = refreshScheduledPanel;
  window.setBillingWorkspace = setWorkspace;
})();
