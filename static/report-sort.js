(() => {
  'use strict';
  const norm = value => String(value ?? '').trim().toLocaleLowerCase('he');

  function sortRows(tbody, keyFn, descending = false) {
    if (!tbody || tbody.dataset.reportSortInstalled === '1') return;
    tbody.dataset.reportSortInstalled = '1';
    const sort = () => {
      const rows = [...tbody.rows];
      rows.sort((a, b) => {
        const av = norm(keyFn(a));
        const bv = norm(keyFn(b));
        const cmp = av.localeCompare(bv, 'he', { numeric: true, sensitivity: 'base' });
        return descending ? -cmp : cmp;
      });
      rows.forEach(row => tbody.appendChild(row));
    };
    const observer = new MutationObserver(() => requestAnimationFrame(sort));
    observer.observe(tbody, { childList: true });
    sort();
  }

  function init() {
    sortRows(document.getElementById('price-list-table-body'), row => row.cells[0]?.innerText || '');
    sortRows(document.getElementById('reportBody'), row => `${row.cells[1]?.innerText || ''}|${row.cells[0]?.innerText || ''}`);
    sortRows(document.getElementById('period-products'), row => row.cells[0]?.innerText || '');
    sortRows(document.getElementById('users-table-body'), row => row.cells[0]?.innerText || '');
    sortRows(document.getElementById('logs-table-body'), row => row.cells[0]?.innerText || '', true);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
  new MutationObserver(init).observe(document.body, { childList: true, subtree: true });
})();
