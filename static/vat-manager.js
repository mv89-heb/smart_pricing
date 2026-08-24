(() => {
  'use strict';
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const money = v => new Intl.NumberFormat('he-IL',{minimumFractionDigits:2,maximumFractionDigits:2}).format(Number(v)||0) + ' ₪';
  let vatProducts = [], vatByName = new Map();
  let vatConfig = {default_rate:18,categories:['כללי','ירקות','פירות','מוצרי מזון','חד פעמי','אחר'],zero_vat_categories:['ירקות','פירות']};

  async function loadVat() {
    try {
      const [cfgRes, prodRes] = await Promise.all([fetch('/api/vat/config',{cache:'no-store'}), fetch('/api/vat/products',{cache:'no-store'})]);
      if (cfgRes.ok) vatConfig = await cfgRes.json();
      if (prodRes.ok) {
        const d = await prodRes.json();
        vatProducts = d.products || [];
        vatByName = new Map(vatProducts.map(p => [p.name,p]));
      }
      enhanceCatalog();
      enhanceReport();
    } catch (e) { console.warn('VAT UI unavailable', e); }
  }

  function categorySelect(value) {
    return `<select id="vat-category" class="sp-input"><option value="">בחר קטגוריה</option>${vatConfig.categories.map(c => `<option value="${esc(c)}" ${c===value?'selected':''}>${esc(c)}</option>`).join('')}</select>`;
  }

  function enhanceCatalog() {
    const form = document.getElementById('form');
    if (!form || document.getElementById('vat-category')) return;
    const priceInput = document.getElementById('price');
    const currentName = document.getElementById('name');
    const wrap = document.createElement('div');
    wrap.id = 'vat-category-wrap';
    wrap.innerHTML = `<label class="block text-sm font-black mb-2">קטגוריה</label>${categorySelect('כללי')}<div class="sp-help">המחיר במחירון הוא לפני מע״מ. ירקות ופירות מחושבים ב-0% כאשר נבחרת הקטגוריה.</div><div id="vat-preview" class="text-xs font-bold text-slate-500 mt-2"></div>`;
    priceInput?.closest('div')?.parentElement?.after(wrap);
    const updatePreview = () => {
      const cat = document.getElementById('vat-category')?.value || 'כללי';
      const rate = (vatConfig.zero_vat_categories || []).includes(cat) ? 0 : Number(vatConfig.default_rate || 18);
      const price = Number(priceInput?.value || 0);
      const total = price * (1 + rate/100);
      const el = document.getElementById('vat-preview');
      if (el) el.textContent = `מע״מ: ${rate}% · מחיר כולל מע״מ: ${money(total)}`;
    };
    document.getElementById('vat-category')?.addEventListener('change', updatePreview);
    priceInput?.addEventListener('input', updatePreview);
    updatePreview();

    const originalFetch = window.fetch;
    if (!window.__vatFetchWrapped) {
      window.__vatFetchWrapped = true;
      window.fetch = async (...args) => {
        const response = await originalFetch(...args);
        try {
          const url = String(args[0]?.url || args[0] || '');
          const options = args[1] || {};
          if (/\/api\/products(?:\/|$)/.test(url) && ['POST','PUT'].includes(String(options.method||'GET').toUpperCase()) && response.ok) {
            const body = options.body ? JSON.parse(options.body) : {};
            const name = (body.name || '').trim();
            const category = document.getElementById('vat-category')?.value || 'כללי';
            setTimeout(async () => {
              if (!name) return;
              const r = await originalFetch(`/api/vat/products/by-name/${encodeURIComponent(name)}`, {cache:'no-store'});
              if (!r.ok) return;
              const p = await r.json();
              await originalFetch(`/api/vat/products/${p.id}`, {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({category})});
            }, 50);
          }
        } catch (_) {}
        return response;
      };
    }
  }

  function enhanceReport() {
    const head = document.getElementById('rows-head');
    const rows = document.getElementById('rows');
    if (!head || !rows) return;
    if (!head.querySelector('[data-vat-column="rate"]')) {
      const th = document.createElement('th'); th.dataset.vatColumn='rate'; th.className='text-center'; th.textContent='מע״מ'; head.querySelector('tr')?.appendChild(th);
      const th2 = document.createElement('th'); th2.dataset.vatColumn='gross'; th2.className='text-center'; th2.textContent='כולל מע״מ'; head.querySelector('tr')?.appendChild(th2);
    }
    const render = () => {
      rows.querySelectorAll('tr').forEach(tr => {
        if (tr.dataset.vatDone === '1') return;
        const cells = tr.querySelectorAll('td');
        if (cells.length < 6) return;
        const name = cells[1].textContent.trim();
        const p = vatByName.get(name);
        const total = Number((cells[5].textContent || '').replace(/[^0-9.-]/g,'')) || 0;
        const rate = p ? Number(p.vat_rate || 0) : Number(vatConfig.default_rate || 18);
        const gross = total * (1 + rate/100);
        const a = document.createElement('td'); a.className='text-center sp-number'; a.dataset.vatColumn='rate'; a.textContent=`${rate}%`;
        const b = document.createElement('td'); b.className='text-center font-black sp-number'; b.dataset.vatColumn='gross'; b.textContent=money(gross);
        tr.appendChild(a); tr.appendChild(b); tr.dataset.vatDone='1';
      });
    };
    new MutationObserver(render).observe(rows,{childList:true});
    render();
  }

  loadVat();
  setTimeout(loadVat, 800);
})();
