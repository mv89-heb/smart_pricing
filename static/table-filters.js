(() => {
  'use strict';

  const ROOTS = ['#left-panel', '#right-panel', '#reports-module', '#dashboard-module', '#settings-page', '.module-shell-content'];
  const state = new WeakMap();
  const norm = value => String(value ?? '').trim().toLocaleLowerCase('he');
  const escape = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));

  function installStyle() {
    if (document.getElementById('table-filters-css')) return;
    const style = document.createElement('style');
    style.id = 'table-filters-css';
    style.textContent = `
      .tf-toolbar{display:flex;align-items:center;gap:.55rem;margin:0 0 .65rem;padding:.55rem .7rem;background:var(--tf-bg,#fff);border:1px solid var(--tf-border,#e2e8f0);border-radius:.75rem;box-shadow:0 1px 2px rgba(15,23,42,.04)}
      .tf-quick{flex:1;min-width:180px;height:36px;border:1px solid var(--tf-border,#cbd5e1);border-radius:.6rem;padding:0 .75rem;background:transparent;color:inherit;font-size:.82rem;outline:none}
      .tf-quick:focus{border-color:#64748b;box-shadow:0 0 0 3px rgba(100,116,139,.12)}
      .tf-count{font-size:.72rem;font-weight:700;color:#64748b;white-space:nowrap}
      .tf-clear{height:34px;padding:0 .7rem;border:1px solid var(--tf-border,#cbd5e1);border-radius:.55rem;background:transparent;color:inherit;font-size:.72rem;font-weight:700;cursor:pointer}
      .tf-th{position:relative;white-space:nowrap}
      .tf-filter-btn{display:inline-flex;align-items:center;justify-content:center;width:23px;height:23px;margin-inline-start:.3rem;border:0;border-radius:.35rem;background:transparent;color:#64748b;cursor:pointer;vertical-align:middle}
      .tf-filter-btn:hover,.tf-filter-btn.active{background:#e2e8f0;color:#0f172a}
      .dark .tf-toolbar{--tf-bg:#0f172a;--tf-border:#334155}.dark .tf-quick{--tf-border:#475569}.dark .tf-clear{--tf-border:#475569}.dark .tf-filter-btn:hover,.dark .tf-filter-btn.active{background:#334155;color:#f8fafc}
      .tf-popover{position:fixed;z-index:10050;width:250px;padding:.7rem;background:#fff;border:1px solid #cbd5e1;border-radius:.7rem;box-shadow:0 18px 50px rgba(15,23,42,.18);color:#0f172a}
      .dark .tf-popover{background:#0f172a;border-color:#475569;color:#f8fafc}
      .tf-popover-title{font-size:.72rem;font-weight:800;margin-bottom:.45rem}.tf-popover input,.tf-popover select{width:100%;height:34px;padding:0 .55rem;border:1px solid #cbd5e1;border-radius:.5rem;background:inherit;color:inherit;font-size:.78rem}.dark .tf-popover input,.dark .tf-popover select{border-color:#475569}
      .tf-popover-actions{display:flex;justify-content:space-between;gap:.4rem;margin-top:.55rem}.tf-popover-actions button{border:1px solid #cbd5e1;border-radius:.5rem;background:transparent;color:inherit;padding:.35rem .55rem;font-size:.7rem;font-weight:700;cursor:pointer}.tf-popover-actions .primary{background:#0f172a;color:#fff;border-color:#0f172a}.dark .tf-popover-actions .primary{background:#f8fafc;color:#0f172a;border-color:#f8fafc}
      .tf-row-hidden{display:none!important}
    `;
    document.head.appendChild(style);
  }

  function rootFor(table) { return table.closest(ROOTS.join(',')) || table.parentElement; }

  function buildToolbar(table, model) {
    if (table.previousElementSibling?.classList.contains('tf-toolbar')) return table.previousElementSibling;
    const bar = document.createElement('div');
    bar.className = 'tf-toolbar';
    bar.innerHTML = `<input class="tf-quick" type="search" placeholder="חיפוש מהיר בטבלה…" aria-label="חיפוש מהיר בטבלה"><span class="tf-count"></span><button type="button" class="tf-clear">נקה</button>`;
    table.parentElement.insertBefore(bar, table);
    const input = bar.querySelector('.tf-quick');
    const count = bar.querySelector('.tf-count');
    input.addEventListener('input', () => { model.quick = norm(input.value); apply(table, model); });
    bar.querySelector('.tf-clear').addEventListener('click', () => { input.value=''; model.quick=''; model.filters.clear(); apply(table, model); });
    model.toolbar = bar; model.count = count;
    return bar;
  }

  function uniqueValues(rows, index) {
    return [...new Set(rows.map(row => norm(row.cells[index]?.innerText)).filter(Boolean))].sort((a,b)=>a.localeCompare(b,'he'));
  }

  function openPopover(table, index, button, model) {
    document.querySelectorAll('.tf-popover').forEach(node => node.remove());
    const pop = document.createElement('div');
    pop.className = 'tf-popover';
    const title = table.tHead?.rows[0]?.cells[index]?.innerText?.trim() || 'סינון';
    const current = model.filters.get(index) || {};
    const values = uniqueValues([...table.tBodies].flatMap(t => [...t.rows]), index);
    const numeric = values.length > 0 && values.every(v => /^-?\d+(?:[.,]\d+)?$/.test(v.replace(/₪|,/g,'')));
    pop.innerHTML = `<div class="tf-popover-title">סינון: ${escape(title)}</div>${numeric ? `<input data-min type="number" step="0.01" placeholder="מינימום" value="${escape(current.min ?? '')}"><input data-max type="number" step="0.01" placeholder="מקסימום" value="${escape(current.max ?? '')}" style="margin-top:.4rem">` : `<input data-value type="search" placeholder="ערך מכיל…" value="${escape(current.value ?? '')}" style="margin-bottom:.45rem"><select data-exact><option value="">כל הערכים</option>${values.map(v=>`<option value="${escape(v)}">${escape(v)}</option>`).join('')}</select>`}<div class="tf-popover-actions"><button type="button" data-reset>נקה</button><button type="button" class="primary" data-apply>החל</button></div>`;
    document.body.appendChild(pop);
    if (!numeric && current.exact) pop.querySelector('[data-exact]').value = current.exact;
    const rect = button.getBoundingClientRect();
    const left = Math.min(Math.max(8, rect.left), window.innerWidth - pop.offsetWidth - 8);
    const top = Math.min(rect.bottom + 6, window.innerHeight - pop.offsetHeight - 8);
    pop.style.left = `${left}px`; pop.style.top = `${Math.max(8, top)}px`;
    pop.querySelector('[data-reset]').onclick = () => { model.filters.delete(index); pop.remove(); apply(table, model); };
    pop.querySelector('[data-apply]').onclick = () => {
      if (numeric) model.filters.set(index, {min: pop.querySelector('[data-min]').value, max: pop.querySelector('[data-max]').value});
      else model.filters.set(index, {value: norm(pop.querySelector('[data-value]').value), exact: norm(pop.querySelector('[data-exact]').value)});
      pop.remove(); apply(table, model);
    };
    setTimeout(() => document.addEventListener('pointerdown', function close(e) { if (!pop.contains(e.target) && e.target !== button) { pop.remove(); document.removeEventListener('pointerdown', close); } }, {once:true}), 0);
  }

  function installHeaders(table, model) {
    const head = table.tHead; if (!head) return;
    [...head.rows[0].cells].forEach((cell, index) => {
      if (cell.querySelector('.tf-filter-btn')) return;
      cell.classList.add('tf-th');
      const button = document.createElement('button');
      button.type = 'button'; button.className = 'tf-filter-btn'; button.title = 'סינון עמודה'; button.setAttribute('aria-label', `סינון ${cell.innerText.trim()}`); button.innerHTML = '<i class="fa-solid fa-filter"></i>';
      button.addEventListener('click', event => { event.stopPropagation(); openPopover(table, index, button, model); });
      cell.appendChild(button);
    });
  }

  function rowMatches(row, model) {
    if (model.quick && !norm(row.innerText).includes(model.quick)) return false;
    for (const [index, filter] of model.filters) {
      const value = norm(row.cells[index]?.innerText);
      if (filter.value && !value.includes(filter.value)) return false;
      if (filter.exact && value !== filter.exact) return false;
      const numeric = Number(value.replace(/[^0-9.-]/g,''));
      if (filter.min !== '' && filter.min != null && (!Number.isFinite(numeric) || numeric < Number(filter.min))) return false;
      if (filter.max !== '' && filter.max != null && (!Number.isFinite(numeric) || numeric > Number(filter.max))) return false;
    }
    return true;
  }

  function apply(table, model) {
    let visible = 0;
    [...table.tBodies].forEach(tbody => [...tbody.rows].forEach(row => { const ok = rowMatches(row, model); row.classList.toggle('tf-row-hidden', !ok); if (ok) visible++; }));
    if (model.count) model.count.textContent = `${visible} תוצאות`;
    table.dataset.tableFiltersReady = '1';
  }

  function setup(table) {
    if (!table.tHead || !table.tBodies.length || table.dataset.tableFiltersReady === '1') return;
    const model = {quick:'', filters:new Map(), toolbar:null, count:null};
    state.set(table, model);
    buildToolbar(table, model); installHeaders(table, model); apply(table, model);
    new MutationObserver(() => { installHeaders(table, model); apply(table, model); }).observe(table.tBodies[0], {childList:true, subtree:true});
  }

  function init() {
    installStyle();
    document.querySelectorAll('table').forEach(setup);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, {once:true}); else init();
  new MutationObserver(() => requestAnimationFrame(init)).observe(document.body, {childList:true, subtree:true});
})();
