(() => {
  const $ = (id) => document.getElementById(id);
  let editorModal;

  function ensureModal() {
    if (editorModal) return editorModal;
    editorModal = document.createElement('div');
    editorModal.id = 'report-entry-editor-modal';
    editorModal.style.cssText = 'display:none;position:fixed;inset:0;z-index:9999;background:rgba(15,23,42,.55);align-items:center;justify-content:center;padding:16px;';
    editorModal.innerHTML = `
      <div style="background:#fff;border-radius:18px;width:min(460px,100%);padding:24px;box-shadow:0 25px 70px rgba(0,0,0,.25);direction:rtl;font-family:Heebo,Arial,sans-serif">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:18px">
          <div><div style="font-size:11px;color:#64748b;font-weight:800;letter-spacing:.08em">עריכת חיוב</div><h3 style="margin:2px 0 0;font-size:22px;font-weight:900">עריכת שורה בדוח</h3></div>
          <button id="re-close" type="button" style="border:0;background:#f1f5f9;border-radius:10px;width:36px;height:36px;cursor:pointer">✕</button>
        </div>
        <label style="display:block;font-size:13px;font-weight:800;margin:10px 0">שם מוצר<input id="re-name" style="display:block;width:100%;box-sizing:border-box;margin-top:5px;padding:11px;border:1px solid #cbd5e1;border-radius:10px;font-size:15px"></label>
        <label style="display:block;font-size:13px;font-weight:800;margin:10px 0">כמות<input id="re-qty" type="number" min="0.01" step="0.01" style="display:block;width:100%;box-sizing:border-box;margin-top:5px;padding:11px;border:1px solid #cbd5e1;border-radius:10px;font-size:15px"></label>
        <label style="display:block;font-size:13px;font-weight:800;margin:10px 0">מחיר יחידה<input id="re-price" type="number" min="0" step="0.01" style="display:block;width:100%;box-sizing:border-box;margin-top:5px;padding:11px;border:1px solid #cbd5e1;border-radius:10px;font-size:15px"></label>
        <label style="display:flex;align-items:center;gap:8px;font-size:13px;font-weight:800;margin:12px 0"><input id="re-extra" type="checkbox"> אקסטרה</label>
        <div id="re-error" style="display:none;background:#fef2f2;color:#b91c1c;border:1px solid #fecaca;border-radius:10px;padding:10px;font-size:13px;margin:12px 0"></div>
        <div style="display:flex;gap:8px;margin-top:18px"><button id="re-save" type="button" style="flex:1;border:0;background:#4f46e5;color:#fff;border-radius:10px;padding:12px;font-weight:800;cursor:pointer">שמור שינויים</button><button id="re-cancel" type="button" style="border:1px solid #cbd5e1;background:#fff;border-radius:10px;padding:12px 18px;cursor:pointer">ביטול</button></div>
        <div style="font-size:11px;color:#64748b;margin-top:10px">שינוי שם או מחיר יעדכן את המוצר במחירון ואת כל החיובים המקושרים אליו.</div>
      </div>`;
    document.body.appendChild(editorModal);
    ['re-close','re-cancel'].forEach(id => $(id).addEventListener('click', close));
    return editorModal;
  }

  function close() { if (editorModal) editorModal.style.display = 'none'; }

  function findEntryForRow(tr) {
    if (!window.rows) return null;
    const cells = tr.querySelectorAll('td');
    if (cells.length < 6) return null;
    const dateText = cells[0].textContent.trim();
    const name = cells[1].textContent.trim();
    const type = cells[2].textContent.includes('אקסטרה');
    const qty = Number(cells[3].textContent.replace(/,/g, ''));
    const candidates = window.rows.filter(r => String(r.product_name || '') === name && !!r.is_extra === type && Number(r.quantity) === qty);
    if (candidates.length === 1) return candidates[0];
    const byDate = candidates.find(r => {
      const p = String(r.date).slice(0,10).split('-');
      return p.length === 3 && `${p[2]}/${p[1]}/${p[0]}` === dateText;
    });
    return byDate || candidates[0] || null;
  }

  function decorateRows() {
    const tbody = $('rows');
    const head = document.querySelector('#rows-head tr');
    if (!tbody || !head) return;
    if (!head.querySelector('[data-report-edit-column]')) {
      const th = document.createElement('th');
      th.textContent = 'פעולות';
      th.dataset.reportEditColumn = '1';
      head.appendChild(th);
    }
    tbody.querySelectorAll('tr').forEach(tr => {
      if (tr.dataset.editorReady || tr.children.length < 6) return;
      const entry = findEntryForRow(tr);
      if (!entry) return;
      tr.dataset.editorReady = '1';
      const td = document.createElement('td');
      td.innerHTML = '<button type="button" title="עריכת חיוב" style="border:1px solid #cbd5e1;background:#fff;border-radius:8px;padding:6px 9px;cursor:pointer">✎ עריכה</button>';
      td.querySelector('button').addEventListener('click', () => open(entry));
      tr.appendChild(td);
    });
  }

  function open(entry) {
    ensureModal();
    $('re-name').value = entry.product_name || '';
    $('re-qty').value = entry.quantity ?? '';
    $('re-price').value = entry.unit_price ?? '';
    $('re-extra').checked = !!entry.is_extra;
    $('re-error').style.display = 'none';
    editorModal.style.display = 'flex';
    $('re-save').onclick = async () => {
      const btn = $('re-save');
      btn.disabled = true;
      try {
        const response = await fetch(`/api/report/entries/${entry.id}`, {
          method: 'PUT', headers: {'Content-Type':'application/json'},
          body: JSON.stringify({
            product_name: $('re-name').value.trim(),
            quantity: $('re-qty').value,
            unit_price: $('re-price').value,
            is_extra: $('re-extra').checked
          })
        });
        const data = await response.json();
        if (!response.ok || !data.success) throw new Error(data.error || 'העדכון נכשל');
        close();
        if (typeof window.loadReport === 'function') await window.loadReport();
        if (typeof window.loadProducts === 'function') await window.loadProducts();
        alert('החיוב והמוצר עודכנו בהצלחה');
      } catch (err) {
        $('re-error').textContent = err.message;
        $('re-error').style.display = 'block';
      } finally { btn.disabled = false; }
    };
  }

  const observer = new MutationObserver(decorateRows);
  window.addEventListener('DOMContentLoaded', () => {
    const tbody = $('rows');
    if (tbody) observer.observe(tbody, {childList:true, subtree:true});
    setTimeout(decorateRows, 300);
    setTimeout(decorateRows, 1000);
  });
})();
