(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const ready = fn => document.readyState === 'loading' ? document.addEventListener('DOMContentLoaded', fn) : fn();
  const hide = (el, yes) => { if (!el) return; el.classList.toggle('app-view-hidden', !!yes); };

  function installCss() {
    if ($('app-shell-stability-css')) return;
    const s = document.createElement('style'); s.id = 'app-shell-stability-css';
    s.textContent = `
      .app-view-hidden{display:none!important}
      #ux-dashboard{width:100%!important}
      #right-panel.app-workspace-panel,#left-panel.app-workspace-panel{min-width:0}
      #right-panel.app-workspace-panel .sticky{position:static!important}
      @media(max-width:1023px){#right-panel.app-workspace-panel,#left-panel.app-workspace-panel{width:100%!important}}
      .app-workspace-banner{display:flex;align-items:center;justify-content:space-between;gap:.75rem;margin-bottom:1rem;padding:.75rem 1rem;border:1px solid #e2e8f0;border-radius:.9rem;background:#fff}
      .dark .app-workspace-banner{background:#1e293b;border-color:#334155}
    `;
    document.head.appendChild(s);
  }

  function normalizeLegacyIds() {
    // Old UI had a typo in reset logic. Keep both ids compatible.
    const tag = $('prod-tag'); const legacy = $('product-tag');
    if (tag && !legacy) { tag.dataset.canonical = '1'; }
  }

  function workspace(view) {
    installCss();
    const dashboard = $('ux-dashboard'), grid = document.querySelector('main > .grid'), daily = $('left-panel'), pricing = $('right-panel');
    if (!grid || !daily || !pricing) return;
    grid.classList.add('app-workspace-grid'); daily.classList.add('app-workspace-panel'); pricing.classList.add('app-workspace-panel');
    if (view === 'dashboard') {
      hide(dashboard, false); hide(grid, true);
    } else if (view === 'daily') {
      hide(dashboard, true); hide(grid, false); hide(daily, false); hide(pricing, true);
    } else if (view === 'pricing') {
      hide(dashboard, true); hide(grid, false); hide(daily, true); hide(pricing, false);
    }
    document.querySelectorAll('#ux-shell-nav [data-v]').forEach(b => b.classList.toggle('active', b.dataset.v === view));
    if (view === 'daily' && typeof window.loadEntriesForDate === 'function') window.loadEntriesForDate();
    if (view === 'pricing' && typeof window.loadProducts === 'function') window.loadProducts();
    window.scrollTo({top:0,behavior:'smooth'});
  }

  function installNavigation() {
    const nav = $('ux-shell-nav'); if (!nav || nav.dataset.stabilityInstalled === '1') return;
    nav.dataset.stabilityInstalled = '1';
    // Define the function expected by the legacy UX script.
    window.switchView = workspace;
    nav.addEventListener('click', e => {
      const btn = e.target.closest('[data-v]'); if (!btn) return;
      const v = btn.dataset.v; if (!['dashboard','daily','pricing'].includes(v)) return;
      e.preventDefault(); e.stopImmediatePropagation(); workspace(v);
    }, true);
    workspace('dashboard');
  }

  function installFallbackNavigation() {
    if ($('ux-shell-nav')) return;
    const header = document.querySelector('header'); if (!header) return;
    const nav = document.createElement('div'); nav.id = 'ux-shell-nav';
    nav.innerHTML = `<div class="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8 py-2 flex gap-1 overflow-x-auto" dir="rtl"><button class="ux-nav active" data-v="dashboard"><i class="fa-solid fa-chart-pie"></i><span class="ux-label">דשבורד</span></button><button class="ux-nav" data-v="daily"><i class="fa-solid fa-calendar-day"></i><span class="ux-label">דיווח יומי</span></button><button class="ux-nav" data-v="pricing"><i class="fa-solid fa-tags"></i><span class="ux-label">מחירון</span></button><a class="ux-nav" href="/periodic-report"><i class="fa-solid fa-calendar-days"></i><span class="ux-label">דוחות</span></a></div>`;
    header.insertAdjacentElement('afterend', nav); installNavigation();
  }

  function fixProductFormReset() {
    const form = $('product-form'); if (!form || form.dataset.resetFixed === '1') return;
    form.dataset.resetFixed = '1';
    const original = window.cancelProductEdit;
    window.cancelProductEdit = function() {
      try { if (typeof original === 'function') original(); } catch (_) {}
      const tag = $('prod-tag'); if (tag) tag.value = '';
      const originalName = $('prod-edit-original-name'); if (originalName) originalName.value = '';
      const title = $('product-form-title'); if (title) title.textContent = 'הוספת מוצר חדש';
      const cancel = $('product-cancel-edit-btn'); if (cancel) cancel.classList.add('hidden');
      const text = $('product-submit-btn-text'); if (text) text.textContent = 'שמור למחירון';
    };
  }

  function fixBulkUpdate() {
    if (typeof window.bulkUpdatePrices !== 'function' || window.bulkUpdatePrices.__stable) return;
    const promptFn = window.customPrompt;
    const fixed = async function() {
      const products = window.products || {};
      const names = Object.keys(products);
      if (!names.length) return window.showToast ? window.showToast('המחירון ריק.','error') : alert('המחירון ריק.');
      const input = await promptFn('הזן אחוז לעדכון גורף של כל המחירון (לדוגמה: 5, -5):','','number');
      if (input === null || input === '') return;
      const percent = Number(input); if (!Number.isFinite(percent)) return window.showToast('נא להזין מספר תקין','error');
      if (!confirm(`האם לעדכן את כל ${names.length} המוצרים ב-${percent}%?`)) return;
      const effective = localStorage.getItem('global_price_effective_from') || new Date().toISOString().slice(0,10);
      let ok = 0;
      for (const name of names) {
        const oldPrice = Number(products[name]);
        const price = Math.round(oldPrice * (1 + percent / 100) * 100) / 100;
        const r = await fetch(`/api/products/${encodeURIComponent(name)}`, {method:'PUT',credentials:'same-origin',headers:{'Content-Type':'application/json','X-Requested-With':'XMLHttpRequest'},body:JSON.stringify({name,price,effective_from:effective})});
        if (r.ok) ok++;
      }
      if (typeof window.showToast === 'function') window.showToast(`עודכנו ${ok} מתוך ${names.length} מוצרים`);
      if (typeof window.loadProducts === 'function') await window.loadProducts();
      if (typeof window.refreshScheduledPrices === 'function') window.refreshScheduledPrices();
    };
    fixed.__stable = true; window.bulkUpdatePrices = fixed;
  }

  function observe() {
    installCss(); normalizeLegacyIds();
    const observer = new MutationObserver(() => {
      installNavigation(); fixProductFormReset(); fixBulkUpdate();
    });
    observer.observe(document.body, {childList:true, subtree:true});
    setTimeout(() => { installNavigation(); if (!$('ux-shell-nav')) installFallbackNavigation(); fixProductFormReset(); fixBulkUpdate(); }, 0);
    setTimeout(() => { installNavigation(); fixProductFormReset(); fixBulkUpdate(); }, 500);
  }
  ready(observe);
})();
