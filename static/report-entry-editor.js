(() => {
  const $ = (id) => document.getElementById(id);
  let modal = null;
  let rows = [];

  async function loadRows() {
    const start = $('start')?.value;
    const end = $('end')?.value;
    if (!start || !end) return;
    try {
      const r = await fetch(`/api/report/range?start_date=${encodeURIComponent(start)}&end_date=${encodeURIComponent(end)}`, {cache:'no-store'});
      if (r.ok) rows = (await r.json()).rows || [];
    } catch (_) {}
  }

  function ensureModal() {
    if (modal) return modal;
    modal = document.createElement('div');
    modal.id = 'report-entry-editor-modal';
    modal.style.cssText = 'display:none;position:fixed;inset:0;z-index:9999;background:rgba(15,23,42,.55);align-items:center;justify-content:center;padding:16px';
    modal.innerHTML = `<div style="background:#fff;border-radius:18px;width:min(460px,100%);padding:24px;box-shadow:0 25px 70px rgba(0,0,0,.25);direction:rtl;font-family:Heebo,Arial,sans-serif">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:18px"><div><div style="font-size:11px;color:#64748b;font-weight:800">עריכת חיוב</div><h3 style="margin:2px 0;font-size:22px;font-weight:900">עריכת שורה בדוח</h3></div><button id="re-close" type="button" style="border:0;background:#f1f5f9;border-radius:10px;width:36px;height:36px">✕</button></div>
      <label style="display:block;font-size:13px;font-weight:800;margin:10px 0">שם מוצר<input id="re-name" style="display:block;width:100%;box-sizing:border-box;margin-top:5px;padding:11px;border:1px solid #cbd5e1;border-radius:10px"></label>
      <label style="display:block;font-size:13px;font-weight:800;margin:10px 0">כמות<input id="re-qty" type="number" min="0.01" step="0.01" style="display:block;width:100%;box-sizing:border-box;margin-top:5px;padding:11px;border:1px solid #cbd5e1;border-radius:10px"></label>
      <label style="display:block;font-size:13px;font-weight:800;margin:10px 0">מחיר יחידה<input id="re-price" type="number" min="0" step="0.01" style="display:block;width:100%;box-sizing:border-box;margin-top:5px;padding:11px;border:1px solid #cbd5e1;border-radius:10px"></label>
      <label style="display:flex;align-items:center;gap:8px;font-size:13px;font-weight:800;margin:12px 0"><input id="re-extra" type="checkbox"> אקסטרה</label>
      <div id="re-error" style="display:none;background:#fef2f2;color:#b91c1c;border:1px solid #fecaca;border-radius:10px;padding:10px;font-size:13px;margin:12px 0"></div>
      <div style="display:flex;gap:8px;margin-top:18px"><button id="re-save" type="button" style="flex:1;border:0;background:#4f46e5;color:#fff;border-radius:10px;padding:12px;font-weight:800">שמור שינויים</button><button id="re-cancel" type="button" style="border:1px solid #cbd5e1;background:#fff;border-radius:10px;padding:12px 18px">ביטול</button></div>
    </div>`;
    document.body.appendChild(modal);
    $('re-close').onclick = close;
    $('re-cancel').onclick = close;
    return modal;
  }

  function close() { if (modal) modal.style.display = 'none'; }
  function currentRow(id) { return rows.find(r => Number(r.id) === Number(id)); }

  async function edit(id) {
    await loadRows();
    const entry = currentRow(id);
    if (!entry) { alert('החיוב לא נמצא. רענן את הדוח ונסה שוב.'); return; }
    ensureModal();
    $('re-name').value = entry.product_name || '';
    $('re-qty').value = entry.quantity ?? '';
    $('re-price').value = entry.unit_price ?? '';
    $('re-extra').checked = !!entry.is_extra;
    $('re-error').style.display = 'none';
    modal.style.display = 'flex';
    $('re-save').onclick = async () => {
      const btn = $('re-save'); btn.disabled = true; $('re-error').style.display = 'none';
      try {
        const payload = {product_name:$('re-name').value.trim(), quantity:$('re-qty').value, unit_price:$('re-price').value, is_extra:$('re-extra').checked};
        if (!payload.product_name) throw new Error('שם מוצר לא יכול להיות ריק');
        if (!(Number(payload.quantity) > 0)) throw new Error('הכמות חייבת להיות גדולה מאפס');
        if (!(Number(payload.unit_price) >= 0)) throw new Error('מחיר היחידה לא תקין');
        let r = await fetch(`/api/report/entries/${encodeURIComponent(id)}`, {method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
        let d = {}; try { d = await r.json(); } catch (_) {}
        if (!r.ok || !d.success) {
          // Fallback for deployments that still expose only the legacy entry endpoint.
          if (payload.product_name === entry.product_name && Number(payload.unit_price) === Number(entry.unit_price)) {
            r = await fetch(`/api/entries/${encodeURIComponent(id)}`, {method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({quantity:payload.quantity,is_extra:payload.is_extra})});
            try { d = await r.json(); } catch (_) { d = {}; }
          }
        }
        if (!r.ok || !d.success) throw new Error(d.error || `שגיאה בעדכון (${r.status})`);
        close();
        if (typeof window.loadReport === 'function') await window.loadReport();
        await loadRows(); bind();
      } catch (e) { $('re-error').textContent = e.message; $('re-error').style.display = 'block'; }
      finally { btn.disabled = false; }
    };
  }

  async function remove(id) {
    const entry = currentRow(id);
    const label = entry?.product_name ? `"${entry.product_name}"` : 'השורה הזו';
    if (!confirm(`למחוק את ${label} מהדוח?\nהחיוב יימחק בלבד; המוצר יישאר במחירון.`)) return;
    try {
      const r = await fetch(`/api/entries/${encodeURIComponent(id)}`, {method:'DELETE',headers:{'Accept':'application/json'}});
      let d = {}; try { d = await r.json(); } catch (_) {}
      if (!r.ok || !d.success) throw new Error(d.error || `שגיאה במחיקה (${r.status})`);
      if (typeof window.loadReport === 'function') await window.loadReport();
      await loadRows(); bind();
    } catch (e) { alert(e.message || 'מחיקת החיוב נכשלה'); }
  }

  function bind() {
    document.querySelectorAll('#rows .edit-entry[data-id]').forEach(btn => {
      if (btn.dataset.editorBound === '1') return;
      btn.dataset.editorBound = '1';
      btn.addEventListener('click', e => { e.preventDefault(); e.stopPropagation(); edit(btn.dataset.id); });
      const cell = btn.closest('td');
      if (cell && !cell.querySelector('.delete-entry')) {
        const del = document.createElement('button');
        del.type='button'; del.className='sp-btn !p-1.5 delete-entry'; del.title='מחיקת חיוב'; del.style.marginInlineStart='6px';
        del.innerHTML='<i class="fa-solid fa-trash"></i>';
        del.addEventListener('click', e => { e.preventDefault(); e.stopPropagation(); remove(btn.dataset.id); });
        cell.appendChild(del);
      }
    });
  }

  const observer = new MutationObserver(bind);
  window.addEventListener('DOMContentLoaded', async () => {
    ensureModal(); await loadRows(); bind();
    const tbody = $('rows'); if (tbody) observer.observe(tbody,{childList:true,subtree:true});
    setTimeout(bind,300); setTimeout(bind,1000);
  });
})();
