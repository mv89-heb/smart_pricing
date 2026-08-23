(() => {
  'use strict';

  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));

  async function api(url, options = {}) {
    options.credentials = 'same-origin';
    options.headers = Object.assign({'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest'}, options.headers || {});
    const response = await fetch(url, options);
    if (response.status === 401) {
      window.location.href = '/login';
      return null;
    }
    return response;
  }

  function showToast(message, success = true) {
    const toast = document.createElement('div');
    toast.className = `fixed bottom-5 left-5 z-[10001] px-4 py-3 rounded-xl shadow-xl text-white font-bold text-sm ${success ? 'bg-emerald-600' : 'bg-rose-600'}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3500);
  }

  async function init() {
    const me = await api('/api/current_user', {headers: {}});
    if (!me || !me.ok) return;
    const current = await me.json();
    if (current.role !== 'admin') return;

    if (document.getElementById('password-reset-admin-btn')) return;

    const button = document.createElement('button');
    button.id = 'password-reset-admin-btn';
    button.type = 'button';
    button.title = 'איפוס סיסמאות משתמשים';
    button.className = 'fixed bottom-5 right-5 z-[9998] bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-3 rounded-xl shadow-xl font-bold text-sm flex items-center gap-2';
    button.innerHTML = '<i class="fa-solid fa-key"></i><span>איפוס סיסמאות</span>';
    button.addEventListener('click', openPanel);
    document.body.appendChild(button);
  }

  async function openPanel() {
    let modal = document.getElementById('password-reset-modal');
    if (modal) { modal.classList.remove('hidden'); return; }

    const response = await api('/api/users', {headers: {}});
    if (!response || !response.ok) {
      showToast('לא ניתן לטעון את המשתמשים', false);
      return;
    }
    const users = await response.json();

    modal = document.createElement('div');
    modal.id = 'password-reset-modal';
    modal.className = 'fixed inset-0 z-[10000] bg-slate-950/60 backdrop-blur-sm flex items-center justify-center p-4';
    modal.innerHTML = `
      <div class="w-full max-w-lg bg-white dark:bg-slate-800 rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-700 overflow-hidden" dir="rtl">
        <div class="p-5 bg-slate-900 text-white flex items-center justify-between">
          <div><h2 class="text-lg font-extrabold">איפוס סיסמת משתמש</h2><p class="text-xs text-slate-300 mt-1">פעולה זמינה למנהלים בלבד</p></div>
          <button type="button" id="password-reset-close" class="text-slate-300 hover:text-white text-xl"><i class="fa-solid fa-xmark"></i></button>
        </div>
        <form id="password-reset-form" class="p-5 space-y-4">
          <div>
            <label class="block text-sm font-bold mb-1">משתמש</label>
            <select id="password-reset-user" required class="w-full px-3 py-2.5 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900">
              ${users.map(u => `<option value="${u.id}">${esc(u.username)} — ${u.role === 'admin' ? 'מנהל' : 'צופה'}</option>`).join('')}
            </select>
          </div>
          <div>
            <label class="block text-sm font-bold mb-1">סיסמה חדשה</label>
            <input id="password-reset-password" type="password" minlength="8" maxlength="128" autocomplete="new-password" required class="w-full px-3 py-2.5 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900" placeholder="לפחות 8 תווים">
          </div>
          <div>
            <label class="block text-sm font-bold mb-1">אימות סיסמה</label>
            <input id="password-reset-confirm" type="password" minlength="8" maxlength="128" autocomplete="new-password" required class="w-full px-3 py-2.5 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900">
          </div>
          <p id="password-reset-error" class="hidden text-sm font-bold text-rose-600"></p>
          <div class="flex gap-2 pt-2">
            <button type="submit" class="flex-1 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg py-2.5 font-bold">אפס סיסמה</button>
            <button type="button" id="password-reset-cancel" class="px-5 bg-slate-100 dark:bg-slate-700 rounded-lg py-2.5 font-bold">ביטול</button>
          </div>
        </form>
      </div>`;
    document.body.appendChild(modal);

    const close = () => modal.classList.add('hidden');
    modal.querySelector('#password-reset-close').addEventListener('click', close);
    modal.querySelector('#password-reset-cancel').addEventListener('click', close);
    modal.addEventListener('click', e => { if (e.target === modal) close(); });

    modal.querySelector('#password-reset-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const userId = modal.querySelector('#password-reset-user').value;
      const password = modal.querySelector('#password-reset-password').value;
      const confirm = modal.querySelector('#password-reset-confirm').value;
      const error = modal.querySelector('#password-reset-error');
      error.classList.add('hidden');

      if (password.length < 8) { error.textContent = 'הסיסמה חייבת להכיל לפחות 8 תווים'; error.classList.remove('hidden'); return; }
      if (password !== confirm) { error.textContent = 'הסיסמאות אינן זהות'; error.classList.remove('hidden'); return; }

      const save = modal.querySelector('button[type="submit"]');
      save.disabled = true;
      save.textContent = 'מאפס...';
      try {
        const r = await api(`/api/users/${encodeURIComponent(userId)}/reset-password`, {method: 'POST', body: JSON.stringify({password})});
        const data = r ? await r.json() : null;
        if (!r || !r.ok || !data?.success) throw new Error(data?.error || 'שגיאה באיפוס הסיסמה');
        modal.querySelector('#password-reset-password').value = '';
        modal.querySelector('#password-reset-confirm').value = '';
        close();
        showToast(`הסיסמה של ${data.username} אופסה בהצלחה`);
      } catch (err) {
        error.textContent = err.message || 'שגיאה באיפוס הסיסמה';
        error.classList.remove('hidden');
      } finally {
        save.disabled = false;
        save.textContent = 'אפס סיסמה';
      }
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
