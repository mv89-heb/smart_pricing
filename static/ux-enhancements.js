(() => {
  const isMobile = () => window.matchMedia('(max-width: 767px)').matches;
  const DASHBOARD = '/static/dashboard.html';
  const PERIODIC = '/periodic-report';

  function addNavigation() {
    if (document.getElementById('analytics-nav')) return;
    const buttons = [...document.querySelectorAll('button')];
    const dashboard = buttons.find(b => (b.textContent || '').includes('דאשבורד'));
    const wrap = dashboard?.parentElement;
    if (!wrap) return;
    const make = (id, href, label, icon, cls) => {
      const a = document.createElement('a');
      a.id = id; a.href = href; a.title = label;
      a.className = cls;
      a.innerHTML = `<i class="fa-solid ${icon}"></i><span class="hidden sm:inline">${label}</span>`;
      return a;
    };
    wrap.insertBefore(make('analytics-nav', DASHBOARD, 'מרכז שליטה', 'fa-chart-pie', 'text-sm font-medium text-violet-700 dark:text-violet-300 bg-violet-50 dark:bg-violet-950/40 hover:bg-violet-100 px-3 sm:px-4 py-2 rounded-lg transition-colors flex items-center gap-2'), dashboard);
    wrap.insertBefore(make('periodic-report-nav', PERIODIC, 'דוח תקופתי', 'fa-calendar-days', 'text-sm font-medium text-emerald-700 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-950/40 hover:bg-emerald-100 px-3 sm:px-4 py-2 rounded-lg transition-colors flex items-center gap-2'), dashboard);
  }

  function addMobileQuickActions() {
    if (!isMobile() || document.getElementById('mobile-quick-actions')) return;
    const bar = document.createElement('nav');
    bar.id = 'mobile-quick-actions'; bar.dir = 'rtl';
    bar.className = 'fixed bottom-0 inset-x-0 z-40 bg-white/95 dark:bg-slate-800/95 backdrop-blur border-t border-slate-200 dark:border-slate-700 px-2 py-2 flex justify-around shadow-2xl';
    bar.innerHTML = `<a href="/" class="flex flex-col items-center text-[11px] font-bold text-slate-600 dark:text-slate-300 px-3 py-1"><i class="fa-solid fa-calendar-day text-base mb-1"></i>יומי</a><a href="${DASHBOARD}" class="flex flex-col items-center text-[11px] font-bold text-violet-600 dark:text-violet-300 px-3 py-1"><i class="fa-solid fa-chart-pie text-base mb-1"></i>דאשבורד</a><a href="${PERIODIC}" class="flex flex-col items-center text-[11px] font-bold text-emerald-600 dark:text-emerald-300 px-3 py-1"><i class="fa-solid fa-chart-column text-base mb-1"></i>תקופתי</a>`;
    document.body.appendChild(bar); document.body.style.paddingBottom = '68px';
  }

  function keyboardShortcuts() {
    document.addEventListener('keydown', e => {
      const tag = (e.target?.tagName || '').toLowerCase();
      if (['input','textarea','select'].includes(tag) || e.target?.isContentEditable) return;
      if (e.key.toLowerCase() === 'r') location.href = PERIODIC;
      if (e.key.toLowerCase() === 'd') location.href = DASHBOARD;
      if (e.key === '/') { const s=document.querySelector('input[type="search"],input[placeholder*="חיפוש"]'); if(s){e.preventDefault();s.focus();} }
      if (e.key === 'Escape') document.querySelectorAll('[role="dialog"],.fixed.inset-0').forEach(x=>x.classList.add('hidden'));
    });
  }

  function injectHelp() {
    const badge=document.getElementById('user-badge'); if(!badge||document.getElementById('shortcut-hint')) return;
    const hint=document.createElement('span'); hint.id='shortcut-hint'; hint.className='hidden lg:inline text-[10px] text-slate-400 mr-2'; hint.textContent='D = Dashboard · R = דוח · / = חיפוש'; badge.parentElement?.appendChild(hint);
  }
  addNavigation(); addMobileQuickActions(); keyboardShortcuts(); injectHelp();
})();
