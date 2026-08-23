(() => {
  'use strict';

  const $ = id => document.getElementById(id);

  // The legacy inline UI had a typo (product-tag vs prod-tag) that could
  // abort the rest of the reset flow. Keep the public function name stable
  // while providing one safe implementation used by all screens.
  function installProductFormReset() {
    const form = $('product-form');
    if (!form || form.dataset.stabilityReset === '1') return;
    form.dataset.stabilityReset = '1';

    window.cancelProductEdit = function cancelProductEditStable() {
      form.reset();
      const original = $('prod-edit-original-name');
      const title = $('product-form-title');
      const cancel = $('product-cancel-edit-btn');
      const submitText = $('product-submit-btn-text');
      const effective = $('prod-effective-from');
      if (original) original.value = '';
      if (title) title.textContent = 'הוספת מוצר חדש';
      if (cancel) cancel.classList.add('hidden');
      if (submitText) submitText.textContent = 'שמור למחירון';
      if (effective) effective.value = localStorage.getItem('global_price_effective_from') || effective.value;
      $('prod-name')?.focus();
    };
  }

  // Prevent accidental double-submit while the active submit handler is
  // waiting for the server. This applies to the daily entry form only.
  function installDailySubmitGuard() {
    const form = $('entry-form');
    const btn = $('entry-submit-btn');
    if (!form || !btn || form.dataset.stabilityGuard === '1') return;
    form.dataset.stabilityGuard = '1';
    form.addEventListener('submit', () => {
      if (btn.dataset.stabilityBusy === '1') return;
      btn.dataset.stabilityBusy = '1';
      setTimeout(() => { btn.dataset.stabilityBusy = '0'; }, 1500);
    }, true);
  }

  // Keep the selected daily date and period panel synchronized when users
  // switch views. The daily screen remains a real daily-entry screen; the
  // period display is additive and never replaces it.
  function installViewSafety() {
    if (window.__uiStabilityViewSafety) return;
    window.__uiStabilityViewSafety = true;
    window.addEventListener('hashchange', () => {
      if (location.hash === '#daily' && typeof window.switchView === 'function') window.switchView('daily');
      if (location.hash === '#pricing' && typeof window.switchView === 'function') window.switchView('pricing');
      if (location.hash === '#dashboard' && typeof window.switchView === 'function') window.switchView('dashboard');
    });
  }

  function init() {
    installProductFormReset();
    installDailySubmitGuard();
    installViewSafety();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
  new MutationObserver(init).observe(document.body, { childList: true, subtree: true });
})();
