(() => {
  'use strict';

  // Compatibility layer only: keep the legacy bulk-price action stable.
  // Navigation ownership belongs exclusively to module-shell.js.
  function fixBulkUpdate() {
    if (typeof window.bulkUpdatePrices !== 'function' || window.bulkUpdatePrices.__stable) return;
    const promptFn = window.customPrompt;
    if (typeof promptFn !== 'function') return;

    const fixed = async function () {
      const products = window.products || {};
      const names = Object.keys(products);
      if (!names.length) return window.showToast?.('המחירון ריק.', 'error');

      const input = await promptFn(
        'הזן אחוז לעדכון גורף של כל המחירון (לדוגמה: 5, -5):',
        '',
        'number'
      );
      if (input === null || input === '') return;

      const percent = Number(input);
      if (!Number.isFinite(percent)) {
        return window.showToast?.('נא להזין מספר תקין', 'error');
      }

      if (!confirm(`האם לעדכן את כל ${names.length} המוצרים ב-${percent}%?`)) return;

      const effective = localStorage.getItem('global_price_effective_from') ||
        new Date().toISOString().slice(0, 10);

      let ok = 0;
      for (const name of names) {
        const oldPrice = Number(products[name]);
        const price = Math.round(oldPrice * (1 + percent / 100) * 100) / 100;
        const r = await fetch(`/api/products/${encodeURIComponent(name)}`, {
          method: 'PUT',
          credentials: 'same-origin',
          headers: {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
          },
          body: JSON.stringify({name, price, effective_from: effective})
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
    fixBulkUpdate();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, {once: true});
  } else {
    init();
  }
})();
