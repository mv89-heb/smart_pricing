(() => {
  'use strict';
  const $ = id => document.getElementById(id);

  function install() {
    if ($('system-health-widget')) return;
    const host = document.querySelector('header');
    if (!host) return;
    const widget = document.createElement('div');
    widget.id = 'system-health-widget';
    widget.className = 'no-print fixed bottom-4 left-4 z-[9998] hidden';
    widget.innerHTML = '<div id="system-health-card" class="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-xl px-4 py-3 text-xs font-bold"><div id="system-health-title">בודק תקינות...</div><div id="system-health-details" class="mt-1 text-slate-500"></div></div>';
    document.body.appendChild(widget);
  }

  async function check() {
    try {
      const response = await fetch('/api/system/health', { credentials: 'same-origin', cache: 'no-store' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (!data.ok) throw new Error(data.error || 'health check failed');
      return data;
    } catch (error) {
      return { ok: false, error: error.message };
    }
  }

  async function run() {
    install();
    const data = await check();
    const widget = $('system-health-widget');
    if (!widget) return;
    const title = $('system-health-title');
    const details = $('system-health-details');
    if (data.ok) {
      title.textContent = '✓ המערכת תקינה';
      details.textContent = `${data.database} · ${data.tables_checked} טבלאות נבדקו`;
    } else {
      title.textContent = '⚠ נדרשת בדיקה';
      details.textContent = data.error || 'שגיאת מערכת';
    }
    widget.classList.remove('hidden');
    setTimeout(() => widget.classList.add('hidden'), 4500);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', run);
  else run();
})();
