(() => {
  const $ = (s) => document.querySelector(s);
  const isMobile = () => window.matchMedia('(max-width: 767px)').matches;

  function addPeriodicButton() {
    if (document.getElementById('periodic-report-nav')) return;
    const buttons = [...document.querySelectorAll('button')];
    const dashboard = buttons.find(b => (b.textContent || '').includes('דאשבורד'));
    const btn = document.createElement('a');
    btn.id = 'periodic-report-nav';
    btn.href = '/periodic-report';
    btn.title = 'דוח חודשי ותקופתי לפי טווח תאריכים';
    btn.className = 'text-sm font-medium text-emerald-700 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-950/40 hover:bg-emerald-100 px-3 sm:px-4 py-2 rounded-lg transition-colors flex items-center gap-2';
    btn.innerHTML = '<i class="fa-solid fa-calendar-days"></i><span class="hidden sm:inline">דוח תקופתי</span>';
    if (dashboard?.parentElement) dashboard.parentElement.insertBefore(btn, dashboard);
    else document.body.appendChild(btn);
  }

  function addMobileQuickActions() {
    if (!isMobile() || document.getElementById('mobile-quick-actions')) return;
    const bar = document.createElement('nav');
    bar.id = 'mobile-quick-actions';
    bar.dir = 'rtl';
    bar.className = 'fixed bottom-0 inset-x-0 z-40 bg-white/95 dark:bg-slate-800/95 backdrop-blur border-t border-slate-200 dark:border-slate-700 px-2 py-2 flex justify-around shadow-2xl';
    bar.innerHTML = `
      <a href="/" class="flex flex-col items-center text-[11px] font-bold text-slate-600 dark:text-slate-300 px-3 py-1"><i class="fa-solid fa-calendar-day text-base mb-1"></i>יומי</a>
      <a href="/periodic-report" class="flex flex-col items-center text-[11px] font-bold text-emerald-600 dark:text-emerald-300 px-3 py-1"><i class="fa-solid fa-chart-column text-base mb-1"></i>תקופתי</a>
      <button type="button" onclick="window.scrollTo({top:0,behavior:'smooth'})" class="flex flex-col items-center text-[11px] font-bold text-slate-600 dark:text-slate-300 px-3 py-1"><i class="fa-solid fa-arrow-up text-base mb-1"></i>למעלה</button>`;
    document.body.appendChild(bar);
    document.body.style.paddingBottom = '68px';
  }

  function keyboardShortcuts() {
    document.addEventListener('keydown', (event) => {
      const tag = (event.target?.tagName || '').toLowerCase();
      if (['input','textarea','select'].includes(tag) || event.target?.isContentEditable) return;
      if (event.key.toLowerCase() === 'r') window.location.href = '/periodic-report';
      if (event.key === '/') {
        const search = document.querySelector('input[type="search"], input[placeholder*="חיפוש"]');
        if (search) { event.preventDefault(); search.focus(); }
      }
      if (event.key === 'Escape') document.querySelectorAll('[role="dialog"], .fixed.inset-0').forEach(el => el.classList.add('hidden'));
    });
  }

  function injectHelp() {
    const badge = document.getElementById('user-badge');
    if (!badge || document.getElementById('shortcut-hint')) return;
    const hint = document.createElement('span');
    hint.id = 'shortcut-hint';
    hint.className = 'hidden lg:inline text-[10px] text-slate-400 mr-2';
    hint.textContent = 'R = דוח תקופתי · / = חיפוש';
    badge.parentElement?.appendChild(hint);
  }

  addPeriodicButton();
  addMobileQuickActions();
  keyboardShortcuts();
  injectHelp();
})();
