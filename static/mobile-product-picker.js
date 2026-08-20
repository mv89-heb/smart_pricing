(() => {
  'use strict';
  const SELECT_ID = 'entry-prod-select-ui';
  const MODAL_ID = 'mobile-product-picker';
  const isMobile = () => window.matchMedia('(max-width: 767px)').matches;
  const esc = s => String(s ?? '').replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  let select = null;
  let observer = null;

  function options() {
    if (!select) return [];
    return [...select.options].filter(o => o.value !== '').map(o => ({ value: o.value, text: o.textContent.trim() }));
  }

  function selectedLabel() {
    const o = select?.selectedOptions?.[0];
    return o?.textContent?.trim() || 'בחר מוצר';
  }

  function syncButton() {
    if (!isMobile() || !select) return;
    let button = document.getElementById('mobile-product-picker-button');
    if (!button) {
      button = document.createElement('button');
      button.type = 'button';
      button.id = 'mobile-product-picker-button';
      button.className = 'w-full min-h-[44px] px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-900 text-right text-sm font-bold text-slate-800 dark:text-white flex items-center justify-between gap-3';
      select.parentElement?.appendChild(button);
      select.addEventListener('change', syncButton);
      button.addEventListener('click', open);
    }
    button.innerHTML = `<span class="truncate">${esc(selectedLabel())}</span><i class="fa-solid fa-chevron-down text-slate-400 shrink-0"></i>`;
    select.classList.add('mobile-picker-source');
    select.style.display = 'none';
    const wrapper = select.closest('.ts-wrapper');
    if (wrapper) wrapper.style.display = 'none';
  }

  function close() { document.getElementById(MODAL_ID)?.remove(); }

  function open() {
    if (!select) return;
    close();
    const list = options();
    const modal = document.createElement('div');
    modal.id = MODAL_ID;
    modal.dir = 'rtl';
    modal.className = 'fixed inset-0 z-[10050] bg-slate-950/70 backdrop-blur-sm flex items-end sm:items-center justify-center';
    modal.innerHTML = `<div class="w-full sm:max-w-lg max-h-[92vh] bg-white dark:bg-slate-900 rounded-t-3xl sm:rounded-2xl shadow-2xl overflow-hidden flex flex-col" role="dialog" aria-modal="true" aria-label="בחירת מוצר"><div class="p-4 border-b dark:border-slate-700 flex items-center justify-between gap-3"><div><h3 class="text-lg font-extrabold">בחירת מוצר</h3><p class="text-xs text-slate-500 mt-0.5">${list.length} מוצרים זמינים</p></div><button type="button" id="mobile-product-close" class="w-10 h-10 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-500" aria-label="סגור"><i class="fa-solid fa-xmark"></i></button></div><div class="p-3 border-b dark:border-slate-700"><div class="relative"><i class="fa-solid fa-magnifying-glass absolute right-3 top-3 text-slate-400"></i><input id="mobile-product-search" autocomplete="off" inputmode="search" class="w-full min-h-[44px] pl-3 pr-9 rounded-xl border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-950 text-sm outline-none focus:ring-2 focus:ring-indigo-500 dark:text-white" placeholder="חיפוש מוצר..."></div></div><div id="mobile-product-list" class="overflow-y-auto overscroll-contain p-2" style="max-height:60vh"></div></div>`;
    document.body.appendChild(modal);
    const listEl = document.getElementById('mobile-product-list');
    const search = document.getElementById('mobile-product-search');
    const render = q => {
      const query = String(q || '').trim().toLocaleLowerCase('he');
      const filtered = list.filter(x => !query || x.text.toLocaleLowerCase('he').includes(query));
      listEl.innerHTML = filtered.length ? filtered.map(x => `<button type="button" class="mobile-product-option w-full min-h-[48px] text-right px-4 py-3 rounded-xl hover:bg-indigo-50 dark:hover:bg-indigo-950/40 active:bg-indigo-100 dark:active:bg-indigo-900/50 flex items-center justify-between gap-3 text-sm font-bold text-slate-800 dark:text-white" data-value="${esc(x.value)}"><span class="truncate">${esc(x.text)}</span>${x.value === select.value ? '<i class="fa-solid fa-check text-indigo-600"></i>' : ''}</button>`).join('') : '<div class="p-8 text-center text-sm font-bold text-slate-400">לא נמצאו מוצרים</div>';
      listEl.querySelectorAll('.mobile-product-option').forEach(btn => btn.addEventListener('click', () => {
        const value = btn.dataset.value;
        select.value = value;
        select.dispatchEvent(new Event('change', { bubbles: true }));
        if (window.TomSelect) {
          const ts = select.tomselect;
          if (ts) ts.setValue(value, true);
        }
        syncButton();
        close();
      }));
    };
    document.getElementById('mobile-product-close').onclick = close;
    modal.addEventListener('click', e => { if (e.target === modal) close(); });
    search.addEventListener('input', () => render(search.value));
    render('');
    requestAnimationFrame(() => search.focus());
  }

  function init() {
    select = document.getElementById(SELECT_ID);
    if (!select) return false;
    syncButton();
    if (!observer) {
      observer = new MutationObserver(() => syncButton());
      observer.observe(select, { childList: true, subtree: true });
    }
    return true;
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => init()); else init();
  const bodyObserver = new MutationObserver(() => { if (!select) init(); else syncButton(); });
  bodyObserver.observe(document.body, { childList: true, subtree: true });
  window.addEventListener('resize', () => { if (!isMobile() && document.getElementById(MODAL_ID)) close(); if (isMobile()) syncButton(); });
})();