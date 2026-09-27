(() => {
  'use strict';
  const normalize = value => String(value ?? '').trim().toLocaleLowerCase('he');
  const uniqueSorted = values => [...new Set(values.filter(Boolean).map(v => String(v).trim()))]
    .sort((a,b) => a.localeCompare(b,'he'));
  function populateSelect(select, values, allLabel='הכל') {
    if (!select) return;
    const current = select.value;
    select.innerHTML = '<option value="">'+allLabel+'</option>' +
      uniqueSorted(values).map(v => '<option value="'+escapeHtml(v)+'">'+escapeHtml(v)+'</option>').join('');
    if ([...select.options].some(o => o.value === current)) select.value = current;
  }
  const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g,c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function filterRows(rows, filters={}) {
    const q = normalize(filters.query);
    const product = normalize(filters.product);
    const category = normalize(filters.category);
    const type = filters.type || '';
    const min = filters.minPrice === '' || filters.minPrice == null ? null : Number(filters.minPrice);
    const max = filters.maxPrice === '' || filters.maxPrice == null ? null : Number(filters.maxPrice);
    return (rows || []).filter(row => {
      const name = normalize(row.product_name ?? row.name);
      const rowCategory = normalize(row.category || 'כללי');
      const rowType = row.is_extra ? 'extra' : 'regular';
      if (q && ![row.product_name,row.name,row.date,row.category,row.is_extra ? 'אקסטרה' : 'רגיל'].some(v => normalize(v).includes(q))) return false;
      if (product && name !== product) return false;
      if (category && rowCategory !== category) return false;
      if (type && rowType !== type) return false;
      const price = Number(row.unit_price ?? row.price ?? 0);
      if (min != null && Number.isFinite(min) && price < min) return false;
      if (max != null && Number.isFinite(max) && price > max) return false;
      return true;
    });
  }
  window.SmartFilters = { normalize, uniqueSorted, populateSelect, filterRows, escapeHtml };
})();