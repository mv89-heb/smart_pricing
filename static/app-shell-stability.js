(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const ready = fn => document.readyState === 'loading' ? document.addEventListener('DOMContentLoaded', fn) : fn();

  function installCss() {
    if ($('app-shell-stability-css')) return;
    const s = document.createElement('style');
    s.id = 'app-shell-stability-css';
    s.textContent = `
      #ux-dashboard.app-screen-hidden { display:none !important; }
      main > .grid.app-screen-hidden { display:none !important; }
      #left-panel.app-screen-hidden, #right-panel.app-screen-hidden { display:none !important; }
      #left-panel.app-screen-visible, #right-panel.app-screen-visible { display:flex !important; }
      @media (max-width:1023px) {
        #left-panel.app-screen-visible, #right-panel.app-screen-visible { width:100% !important; }
      }
    `;
    document.head.appendChild(s);
  }

  const setVisible = (el, visible) => {
    if (!el) return;
    el.classList.toggle('app-screen-hidden', !visible);
    el.classList.toggle('app-screen-visible', visible);
  };

  function workspace(view) {
    installCss();
    const dashboard = $('ux-dashboard');
    const grid = document.querySelector('main > .grid');
    const daily = $('left-panel');
    const pricing = $('right-panel');

    if (!grid || !daily || !pricing) return false;

    if (view === 'dashboard') {
      setVisible(dashboard, true);
      setVisible(grid, false);
      setVisible(daily, false);
      setVisible(pricing, false);
    } else if (view === 'daily') {
      setVisible(dashboard, false);
      setVisible(grid, true);
      setVisible(daily, true);
      setVisible(pricing, false);
    } else if (view === 'pricing') {
      setVisible(dashboard, false);
      setVisible(grid, true);
      setVisible(daily, false);
      setVisible(pricing, true);
    } else {
      return false;
    }

    document.querySelectorAll('#ux-shell-nav [data-v]').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.v === view);
    });

    if (view === 'daily' && typeof window.loadEntriesForDate === 'function') {
      window.loadEntriesForDate();
    }
    if (view === 'pricing' && typeof window.loadProducts === 'function') {
      window.loadProducts();
    }
    window.scrollTo({ top: 0, behavior: 'smooth' });
    return true;
  }

  function bindNavigation() {
    const nav = $('ux-shell-nav');
    if (!nav) return false;

    // Always expose the canonical navigation function. This fixes the race
    // between ux-enhancements.js and this stability layer.
    window.switchView = workspace;
    window.openDashboard = () => workspace('dashboard');

    if (nav.dataset.stabilityBound === '1') return true;
    nav.dataset.stabilityBound = '1';

    nav.addEventListener('click', event => {
      const btn = event.target.closest('[data-v]');
      if (!btn || !nav.contains(btn)) return;
      const view = btn.dataset.v;
      if (!['dashboard', 'daily', 'pricing'].includes(view)) return;
      event.preventDefault();
      event.stopPropagation();
      workspace(view);
    });
    return true;
  }

  function fixProductFormReset() {
    const form = $('product-form');
    if (!form || form.dataset.resetFixed === '1') return;
    form.dataset.resetFixed = '1';
    const original = window.cancelProductEdit;
    window.cancelProductEdit = function () {
      try { if (typeof original === 'function') original(); } catch (_) {}
      const tag = $('prod-tag');
      if (tag) tag.value = '';
      const originalName = $('prod-edit-original-name');
      if (originalName) originalName.value = '';
      const title = $('product-form-title');
      if (title) title.textContent = 'הוספת מוצר חדש';
      const cancel = $('product-cancel-edit-btn');
      if (cancel) cancel.classList.add('hidden');
      const text = $('product-submit-btn-text');
      if (text) text.textContent = 'שמור למחירון';
    };
  }

  function fixBulkUpdate() {
    if (typeof window.bulkUpdatePrices !== 'function' || window.bulkUpdatePrices.__stable) return;
    const promptFn = window.customPrompt;
    if (typeof promptFn !== 'function') return;
    const fixed = async function () {
      const products = window.products || {};
      const names = Object.keys(products);
      if (!names.length) return window.showToast?.('המחירון ריק.', 'error');
      const input = await promptFn('הזן אחוז לעדכון גורף של כל המחירון (לדוגמה: 5, -5):', '', 'number');
      if (input === null || input === '') return;
      const percent = Number(input);
      if (!Number.isFinite(percent)) return window.showToast?.('נא להזין מספר תקין', 'error');
      if (!confirm(`האם לעדכן את כל ${names.length} המוצרים ב-${percent}%?`)) return;
      const effective = localStorage.getItem('global_price_effective_from') || new Date().toISOString().slice(0, 10);
      let ok = 0;
      for (const name of names) {
        const oldPrice = Number(products[name]);
        const price = Math.round(oldPrice * (1 + percent / 100) * 100) / 100;
        const r = await fetch(`/api/products/${encodeURIComponent(name)}`, {
          method: 'PUT', credentials: 'same-origin',
          headers: {'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest'},
          body: JSON.stringify({ name, price, effective_from: effective })
        });
        if (r.ok) ok++;
      }
      window.showToast?.(`עודכנו ${ok} מתוך ${names.length} מוצרים`);
      if (typeof window.loadProducts === 'function') await window.loadProducts();
      if (typeof window.refreshScheduledPrices === 'function') window.refreshScheduledPrices();
    };
    fixed.__stable = true;
    window.bulkUpdatePrices = fixed;
  }

  function init() {
    installCss();
    bindNavigation();
    fixProductFormReset();
    fixBulkUpdate();

    // ux-enhancements creates the nav/dashboard asynchronously on DOM ready.
    let attempts = 0;
    const retry = () => {
      attempts += 1;
      bindNavigation();
      fixProductFormReset();
      fixBulkUpdate();
      if (attempts < 20 && !$('ux-shell-nav')) setTimeout(retry, 100);
    };
    retry();
  }

  ready(init);
})();
