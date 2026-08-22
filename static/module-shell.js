(() => {
  'use strict';
  if (window.__smartPricingModuleShell || window.location.pathname === '/login') return;
  window.__smartPricingModuleShell = true;

  const modules = {
    daily: {label:'דיווח יומי', subtitle:'הזנה וניהול חיובים לפי יום', icon:'fa-calendar-day', href:'/'},
    pricing: {label:'מחירון', subtitle:'מוצרים, מחירים ותזמון עדכונים', icon:'fa-tags', href:'/?module=pricing'},
    reports: {label:'דוחות', subtitle:'דוחות תקופתיים, סיכומים וייצוא', icon:'fa-file-invoice-dollar', href:'/periodic-report'},
    dashboard: {label:'דשבורד', subtitle:'מגמות, KPI וניתוח ביצועים', icon:'fa-chart-pie', href:'/static/dashboard.html'},
    settings: {label:'הגדרות', subtitle:'משתמשים, גיבוי והעדפות מערכת', icon:'fa-gear', href:'/settings'}
  };

  function currentModule() {
    const path = window.location.pathname;
    if (path === '/periodic-report') return 'reports';
    if (path === '/static/dashboard.html') return 'dashboard';
    if (path === '/settings') return 'settings';
    if (path === '/') return new URLSearchParams(window.location.search).get('module') === 'pricing' ? 'pricing' : 'daily';
    return 'daily';
  }

  function roleLabel(role) { return role === 'admin' ? 'מנהל' : role === 'editor' ? 'עורך' : 'צפייה'; }

  function linkMarkup(key) {
    const m = modules[key];
    return `<a class="module-shell-link" data-module="${key}" href="${m.href}"><i class="fa-solid ${m.icon}"></i><span>${m.label}</span></a>`;
  }

  function createSidebar(active, user) {
    const el = document.createElement('aside');
    el.className = 'module-shell-sidebar';
    el.innerHTML = `
      <div class="module-shell-brand">
        <div class="module-shell-brand-mark"><i class="fa-solid fa-layer-group"></i></div>
        <div class="module-shell-brand-title">Smart Pricing</div>
        <div class="module-shell-brand-subtitle">ניהול חיובים ומחירים</div>
      </div>
      <nav class="module-shell-nav" aria-label="ניווט ראשי">
        <div class="module-shell-section">מערכת</div>
        ${linkMarkup('daily')}
        ${linkMarkup('pricing')}
        ${linkMarkup('reports')}
        ${linkMarkup('dashboard')}
        ${linkMarkup('settings')}
      </nav>
      <div class="module-shell-sidebar-footer">
        <div class="module-shell-user">
          <div class="module-shell-avatar"><i class="fa-solid fa-user"></i></div>
          <div><div class="module-shell-user-name">${escapeHtml(user?.username || 'משתמש')}</div><div class="module-shell-user-role">${roleLabel(user?.role)}</div></div>
        </div>
      </div>`;
    el.querySelectorAll('[data-module]').forEach(a => {
      if (a.dataset.module === active) a.classList.add('active');
    });
    return el;
  }

  function createTopbar(active) {
    const m = modules[active];
    const el = document.createElement('div');
    el.className = 'module-shell-topbar';
    el.innerHTML = `
      <div class="module-shell-title">
        <button class="module-shell-mobile-toggle" type="button" aria-label="תפריט" onclick="document.body.classList.toggle('module-shell-mobile-open')"><i class="fa-solid fa-bars"></i></button>
        <div class="module-shell-title-icon"><i class="fa-solid ${m.icon}"></i></div>
        <div><h1>${m.label}</h1><p>${m.subtitle}</p></div>
      </div>
      <div class="module-shell-actions">
        <button class="module-shell-icon-btn" type="button" title="מצב כהה" onclick="window.moduleShellToggleTheme?.()"><i class="fa-solid fa-moon"></i></button>
        <button class="module-shell-icon-btn" type="button" title="מסך מלא" onclick="document.documentElement.requestFullscreen?.().catch(()=>{})"><i class="fa-solid fa-expand"></i></button>
        <a class="module-shell-icon-btn" href="/logout" title="יציאה"><i class="fa-solid fa-right-from-bracket"></i></a>
      </div>`;
    return el;
  }

  function createMobileNav(active) {
    const el = document.createElement('nav');
    el.className = 'module-shell-mobile-nav';
    el.innerHTML = Object.entries(modules).map(([key,m]) => `<a data-module="${key}" href="${m.href}" class="${key===active?'active':''}"><i class="fa-solid ${m.icon}"></i><span>${m.label}</span></a>`).join('');
    return el;
  }

  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  }

  async function getUser() {
    try {
      const response = await fetch('/api/current_user', {credentials:'same-origin', cache:'no-store'});
      if (!response.ok) return null;
      return await response.json();
    } catch (_) { return null; }
  }

  function setupIndex(active) {
    const app = document.querySelector('.app-ui');
    if (!app) return;
    const main = app.querySelector(':scope > main');
    if (!main) return;
    const right = document.getElementById('right-panel');
    const left = document.getElementById('left-panel');

    if (active === 'pricing') {
      right?.classList.add('module-shell-pricing-view');
      left?.classList.add('module-shell-hidden');
      document.body.classList.add('module-shell-pricing');
    } else {
      left?.classList.add('module-shell-daily-view');
      right?.classList.add('module-shell-hidden');
      document.body.classList.add('module-shell-daily');
    }

    const title = document.querySelector('title');
    if (title) title.textContent = `${modules[active].label} | Smart Pricing`;
    main.classList.add('module-shell-content');
  }

  function setupLegacyPage() {
    const root = document.body.firstElementChild;
    if (!root) return;
    root.classList.add('module-shell-legacy-root');
    const frame = document.createElement('div');
    frame.className = 'module-shell-legacy-page';
    const content = document.createElement('div');
    content.className = 'module-shell-content module-shell-page-frame';
    frame.appendChild(content);
    document.body.insertBefore(frame, root);
    content.appendChild(root);
  }

  function setupSettings() {
    const root = document.getElementById('settings-page');
    if (root) root.classList.add('module-shell-settings');
  }

  function applyTheme() {
    if (localStorage.getItem('theme') === 'dark') document.documentElement.classList.add('dark');
    window.moduleShellToggleTheme = () => {
      const dark = document.documentElement.classList.toggle('dark');
      localStorage.setItem('theme', dark ? 'dark' : 'light');
    };
  }

  async function init() {
    const active = currentModule();
    const user = await getUser();
    document.body.classList.add('module-shell-ready');
    applyTheme();

    const sidebar = createSidebar(active, user);
    const main = document.createElement('div');
    main.className = 'module-shell-main';
    main.appendChild(createTopbar(active));

    if (window.location.pathname === '/') setupIndex(active);
    else if (active === 'settings') setupSettings();
    else setupLegacyPage();

    if (window.location.pathname === '/') {
      const app = document.querySelector('.app-ui');
      if (app) main.appendChild(app);
    } else {
      const legacyFrame = document.querySelector('.module-shell-legacy-page');
      if (legacyFrame) main.appendChild(legacyFrame);
    }

    document.body.prepend(main);
    document.body.prepend(sidebar);
    document.body.appendChild(createMobileNav(active));

    const title = document.querySelector('title');
    if (title) title.textContent = `${modules[active].label} | Smart Pricing`;
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, {once:true});
  else init();
})();
