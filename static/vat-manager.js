(() => {
  'use strict';
  const money = v => new Intl.NumberFormat('he-IL',{minimumFractionDigits:2,maximumFractionDigits:2}).format(Number(v)||0) + ' ₪';
  let vatProducts = [], vatByName = new Map(), vatById = new Map();
  let vatConfig = {default_rate:18,categories:['כללי','ירקות','פירות','ממרחים וממתיקים','דגנים','שמנים','חד-פעמי','מוצרי מזון','אחר'],zero_vat_categories:['ירקות']};

  async function loadVat() {
    try {
      const [cfgRes, prodRes] = await Promise.all([
        fetch('/api/vat/config',{cache:'no-store'}),
        fetch('/api/vat/products',{cache:'no-store'})
      ]);
      if (cfgRes.ok) vatConfig = await cfgRes.json();
      if (prodRes.ok) {
        const d = await prodRes.json();
        vatProducts = d.products || [];
        vatByName = new Map(vatProducts.map(p => [p.name,p]));
        vatById = new Map(vatProducts.map(p => [Number(p.id),p]));
      }
      enhanceCatalog();
      enhanceReport();
    } catch (e) { console.warn('VAT UI unavailable', e); }
  }

  function categorySelect(value) {
    return `<select id="vat-category" class="sp-input"><option value="">בחר קטגוריה</option>${vatConfig.categories.map(c => `<option value="${String(c).replace(/"/g,'&quot;')}" ${c===value?'selected':''}>${c}</option>`).join('')}</select>`;
  }

  function enhanceCatalog() {
    const form = document.getElementById('form');
    if (!form || document.getElementById('vat-category')) return;
    const priceInput = document.getElementById('price');
    const wrap = document.createElement('div');
    wrap.id = 'vat-category-wrap';
    wrap.innerHTML = `<label class="block text-sm font-black mb-2">קטגוריה</label>${categorySelect('כללי')}<div class="sp-help">המחיר במחירון הוא לפני מע״מ. ירקות מחושבים ב-0% כאשר נבחרת הקטגוריה.</div><div id="vat-preview" class="text-xs font-bold text-slate-500 mt-2"></div>`;
    priceInput?.closest('div')?.parentElement?.after(wrap);
    document.getElementById('vat-category')?.addEventListener('change', updatePreview);
    priceInput?.addEventListener('input', updatePreview);
    updatePreview();
  }

  function updatePreview() {
    const priceInput = document.getElementById('price');
    const cat = document.getElementById('vat-category')?.value || 'כללי';
    const rate = (vatConfig.zero_vat_categories || []).includes(cat) ? 0 : Number(vatConfig.default_rate || 18);
    const price = Number(priceInput?.value || 0);
    const total = price * (1 + rate/100);
    const el = document.getElementById('vat-preview');
    if (el) el.textContent = `מע״מ: ${rate}% · מחיר כולל מע״מ: ${money(total)}`;
  }

  function ensureReportColumns() {
    const head = document.getElementById('rows-head');
    const tr = head?.querySelector('tr');
    if (!tr) return;
    if (!tr.querySelector('[data-vat-column="rate"]')) {
      const th = document.createElement('th');
      th.dataset.vatColumn = 'rate';
      th.className = 'text-center';
      th.textContent = 'מע״מ';
      tr.appendChild(th);
    }
  }

  function effectiveRate(row) {
    const product = row?.product_id != null ? vatById.get(Number(row.product_id)) : null;
    const byName = product || vatByName.get(String(row?.product_name || '').trim());
    if (byName) return Number(byName.vat_rate ?? 0);
    return Number(vatConfig.default_rate || 18);
  }

  function enhanceReport() {
    const head = document.getElementById('rows-head');
    const tbody = document.getElementById('rows');
    if (!head || !tbody) return;
    ensureReportColumns();
    const render = () => {
      ensureReportColumns();
      tbody.querySelectorAll('tr').forEach(tr => {
        const cells = tr.querySelectorAll('td');
        if (cells.length < 6) return;
        const existing = tr.querySelector('[data-vat-column="rate"]');
        const productName = cells[1]?.textContent?.trim() || '';
        const rowData = Array.from(tbody.children).indexOf(tr);
        const sourceRows = window.__periodReportRows || [];
        const row = sourceRows[rowData] || {product_name: productName};
        const rate = effectiveRate(row);
        if (existing) {
          existing.textContent = `${rate}%`;
        } else {
          const td = document.createElement('td');
          td.dataset.vatColumn = 'rate';
          td.className = 'text-center sp-number font-bold';
          td.textContent = `${rate}%`;
          tr.appendChild(td);
        }
      });
    };
    render();
    if (!tbody.__vatObserver) {
      tbody.__vatObserver = new MutationObserver(() => requestAnimationFrame(render));
      tbody.__vatObserver.observe(tbody,{childList:true});
    }
  }

  loadVat();
  setTimeout(loadVat, 800);
})();