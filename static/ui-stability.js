(() => {
  'use strict';

  const $ = id => document.getElementById(id);

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

  function installDailySubmitGuard() {
    const form = $('entry-form');
    const btn = $('entry-submit-btn');
    if (!form || !btn || form.dataset.stabilityGuard === '1') return;
    form.dataset.stabilityGuard = '1';
    form.addEventListener('submit', () => {
      if (btn.dataset.stabilityBusy === '1') return;
      btn.dataset.stabilityBusy = '1';
      btn.classList.add('ui-action-busy');
      btn.setAttribute('aria-busy', 'true');
      setTimeout(() => {
        btn.dataset.stabilityBusy = '0';
        btn.classList.remove('ui-action-busy');
        btn.removeAttribute('aria-busy');
      }, 1500);
    }, true);
  }

  function installActionFeedback() {
    if (window.__uiStabilityFeedback) return;
    window.__uiStabilityFeedback = true;

    document.addEventListener('click', event => {
      const button = event.target.closest('button[type="submit"], button[data-loading], .js-loading-button');
      if (!button || button.disabled || button.dataset.noLoading === '1') return;
      button.classList.add('ui-action-busy');
      button.setAttribute('aria-busy', 'true');
      const original = button.innerHTML;
      button.dataset.originalHtml = original;
      const icon = button.querySelector('i');
      if (icon) icon.className = 'fa-solid fa-spinner fa-spin';
      else if (!button.querySelector('.ui-spinner')) {
        button.insertAdjacentHTML('afterbegin', '<i class="fa-solid fa-spinner fa-spin ui-spinner"></i> ');
      }
      window.setTimeout(() => {
        if (!button.isConnected) return;
        button.classList.remove('ui-action-busy');
        button.removeAttribute('aria-busy');
        if (button.dataset.originalHtml) button.innerHTML = button.dataset.originalHtml;
      }, 2500);
    }, true);
  }

  function init() {
    installProductFormReset();
    installDailySubmitGuard();
    installActionFeedback();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, {once: true});
  } else {
    init();
  }

  // Forms are created dynamically by the legacy daily/pricing UI.
  new MutationObserver(init).observe(document.body, {childList: true, subtree: true});
})();
