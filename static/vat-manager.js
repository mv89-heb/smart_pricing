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
      // Note: enhanceReport() (which used to bolt on an extra VAT-rate column
      // to #rows-head/#rows) was removed - period_report.html's own inline
      // script already renders an accurate, per-row VAT column sourced
      // directly from /api/report/range, so the old DOM-patching logic here
      // only produced a confusing duplicate "מע״מ" column on every row.
    } catch (e) { console.warn('VAT UI unavailable', e); }
  }

  function categorySelect(value) {
    return `<select id="vat-category" class="sp-input"><option value="">בחר קטגוריה</option>${vatConfig.categories.map(c => `<option value="${String(c).replace(/"/g,'&quot;')}" ${c===value?'selected':''}>${c}</option>`).join('')}</select>`;
  }

  function enhanceCatalog() {
    const form = document.getElementById('form');
    // product_add.html already ships its own native category <select id="category">
    // wired to the VAT preview and the submit handler - injecting a second,
    // unwired dropdown here just confused users with two "category" fields.
    if (!form || document.getElementById('category') || document.getElementById('vat-category')) return;
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

  loadVat();
  setTimeout(loadVat, 800);
})();