(() => {
  'use strict';

  const SELECT_ID = 'entry-prod-select-ui';
  const MODAL_ID = 'mobile-product-picker';
  const BUTTON_ID = 'mobile-product-picker-button';
  const isMobile = () => window.matchMedia('(max-width:767px)').matches;
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (m) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[m]));

  let select = null;
  let syncing = false;
  let domObserver = null;
  let resizeInstalled = false;

  function getOptions() {
    return select
      ? [...select.options]
          .filter((o) => o.value !== '')
          .map((o) => ({ value: o.value, text: o.textContent.trim() }))
          .filter((o) => o.text)
      : [];
  }

  async function ensureOptions() {
    const list = getOptions();
    if (list.length) return list;

    try {
      const response = await fetch('/api/products', {
        credentials: 'same-origin',
        cache: 'no-store'
      });
      if (!response.ok) return [];

      const data = await response.json();
      const products = Array.isArray(data)
        ? data.reduce((acc, item) => {
            if (item?.name) acc[item.name] = item.price;
            return acc;
          }, {})
        : (data || {});

      if (select && !getOptions().length) {
        const groups = {};

        Object.keys(products)
          .sort((a, b) => a.localeCompare(b, 'he'))
          .forEach((name) => {
            const category = name.includes('-')
              ? name.split('-')[0].trim()
              : 'כללי';

            if (!groups[category]) groups[category] = [];
            groups[category].push(name);
          });

        Object.keys(groups)
          .sort((a, b) => a.localeCompare(b, 'he'))
          .forEach((category) => {
            const group = document.createElement('optgroup');
            group.label = category;

            groups[category].forEach((name) => {
              const option = document.createElement('option');
              option.value = name;
              option.textContent = name;
              group.appendChild(option);
            });

            select.appendChild(group);
          });
      }
    } catch (_) {
      // Keep the existing select usable when the API is unavailable.
    }

    return getOptions();
  }

  function selectedLabel() {
    return select?.selectedOptions?.[0]?.textContent?.trim() || 'בחר מוצר';
  }

  function syncButton() {
    if (!isMobile() || !select || syncing) return;

    let button = document.getElementById(BUTTON_ID);
    if (!button) {
      button = document.createElement('button');
      button.type = 'button';
      button.id = BUTTON_ID;
      button.className = 'w-full min-h-[44px] px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-900 text-right text-sm font-bold text-slate-800 dark:text-white flex items-center justify-between gap-3';
      (select.closest('.ts-wrapper')?.parentElement || select.parentElement)?.appendChild(button);
      button.addEventListener('click', open);
      select.addEventListener('change', syncButton);
    }

    button.innerHTML = `<span class="truncate">${esc(selectedLabel())}</span><i class="fa-solid fa-chevron-down text-slate-400 shrink-0"></i>`;
    select.style.display = 'none';

    const wrapper = select.closest('.ts-wrapper');
    if (wrapper) wrapper.style.display = 'none';
  }

  function close() {
    document.getElementById(MODAL_ID)?.remove();
  }

  async function open() {
    if (!select) return;

    close();
    const list = await ensureOptions();
    const modal = document.createElement('div');

    modal.id = MODAL_ID;
    modal.dir = 'rtl';
    modal.className = 'fixed inset-0 z-[10050] bg-slate-950/70 backdrop-blur-sm flex items-end sm:items-center justify-center';
    modal.innerHTML = `<div class="w-full sm:max-w-lg max-h-[92vh] bg-white dark:bg-slate-900 rounded-t-3xl sm:rounded-2xl shadow-2xl overflow-hidden flex flex-col" role="dialog" aria-modal="true"><div class="p-4 border-b dark:border-slate-700 flex items-center justify-between"><div><h3 class="text-lg font-extrabold">בחירת מוצר</h3><p class="text-xs text-slate-500">${list.length} מוצרים זמינים</p></div><button type="button" id="mobile-product-close" class="w-10 h-10 rounded-full bg-slate-100 dark:bg-slate-800"><i class="fa-solid fa-xmark"></i></button></div><div class="p-3 border-b dark:border-slate-700"><input id="mobile-product-search" autocomplete="off" inputmode="search" class="w-full min-h-[44px] px-3 rounded-xl border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-950 text-sm dark:text-white" placeholder="חיפוש מוצר..."></div><div id="mobile-product-list" class="overflow-y-auto overscroll-contain p-2" style="max-height:60vh"></div></div>`;

    document.body.appendChild(modal);

    const box = document.getElementById('mobile-product-list');
    const search = document.getElementById('mobile-product-search');

    const render = (queryText) => {
      const query = String(queryText || '').trim().toLocaleLowerCase('he');
      const filtered = list.filter((item) => !query || item.text.toLocaleLowerCase('he').includes(query));

      box.innerHTML = filtered.length
        ? filtered.map((item) => `<button type="button" class="mobile-product-option w-full min-h-[52px] text-right px-4 py-3 rounded-xl hover:bg-indigo-50 dark:hover:bg-indigo-950/40 flex items-center justify-between gap-3 text-sm font-bold text-slate-800 dark:text-white" data-value="${esc(item.value)}"><span class="truncate">${esc(item.text)}</span>${item.value === select.value ? '<i class="fa-solid fa-check text-indigo-600"></i>' : ''}</button>`).join('')
        : '<div class="p-8 text-center text-sm font-bold text-slate-400">לא נמצאו מוצרים</div>';

      box.querySelectorAll('.mobile-product-option').forEach((button) => {
        button.onclick = () => {
          syncing = true;
          const value = button.dataset.value;

          if (select.tomselect) {
            select.tomselect.setValue(value, true);
          } else {
            select.value = value;
            select.dispatchEvent(new Event('change', { bubbles: true }));
          }

          syncing = false;
          syncButton();
          close();
        };
      });
    };

    document.getElementById('mobile-product-close').onclick = close;
    modal.onclick = (event) => {
      if (event.target === modal) close();
    };
    search.oninput = () => render(search.value);
    render('');
    requestAnimationFrame(() => search.focus());
  }

  function init() {
    const found = document.getElementById(SELECT_ID);
    if (!found) return false;

    if (select !== found) {
      select = found;
      select.addEventListener('change', syncButton);
    }
    if (isMobile()) syncButton();
    return true;
  }

  function watchUntilReady() {
    if (init()) {
      domObserver?.disconnect();
      domObserver = null;
      return;
    }
    if (!domObserver) {
      domObserver = new MutationObserver(() => {
        if (init()) {
          domObserver.disconnect();
          domObserver = null;
        }
      });
      domObserver.observe(document.body, { childList: true, subtree: true });
    }
  }

  function handleResize() {
    if (!isMobile()) {
      close();
      const button = document.getElementById(BUTTON_ID);
      if (button) button.remove();

      if (select) {
        select.style.display = '';
        const wrapper = select.closest('.ts-wrapper');
        if (wrapper) wrapper.style.display = '';
      }
    } else {
      syncButton();
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', watchUntilReady, { once: true });
  } else {
    watchUntilReady();
  }

  if (!resizeInstalled) {
    resizeInstalled = true;
    window.addEventListener('resize', handleResize, { passive: true });
  }
})();
