(function () {
    'use strict';

    // הגנה מפני הזרקה כפולה (למשל אם ה-middleware רץ פעמיים) ומצב הדפסת חשבונית
    if (document.body.classList.contains('invoice-mode') || document.getElementById('sp-sidebar')) return;

    const path = location.pathname;

    const items = [
        { label: 'דוח לפי תקופה', icon: 'fa-chart-column', href: '/', key: 'period' },
        { label: 'הוספת מוצרים', icon: 'fa-box-open', href: '/products/new', key: 'products' },
        { label: 'אנליטיקה ודאשבורד', icon: 'fa-chart-pie', href: '/dashboard', key: 'dashboard' },
        { label: 'הגדרות', icon: 'fa-gear', href: '/settings', key: 'settings' }
    ];

    const activeKey = (items.find(i => i.href === path) || {}).key || '';

    const el = (tag, className, html) => {
        const e = document.createElement(tag);
        if (className) e.className = className;
        if (html) e.innerHTML = html;
        return e;
    };

    // --- סרגל צד (דסקטופ) ---
    const sidebar = el('aside', 'sp-sidebar');
    sidebar.id = 'sp-sidebar';
    sidebar.innerHTML = '<div class="sp-brand"><div class="sp-brand-title"><i class="fa-solid fa-chart-line"></i> Smart Pricing</div><div class="sp-brand-sub">ניהול חיובים חכם</div></div>';

    const nav = el('nav', 'sp-nav');
    items.forEach(item => {
        const a = el('a', item.key === activeKey ? 'active' : '', `<i class="fa-solid ${item.icon}"></i><span>${item.label}</span>`);
        a.href = item.href;
        nav.appendChild(a);
    });
    sidebar.appendChild(nav);

    const footer = el('div', 'sp-footer');
    footer.innerHTML = '<a href="/logout" style="color:#fca5a5"><i class="fa-solid fa-right-from-bracket"></i><span>יציאה</span></a>';
    sidebar.appendChild(footer);
    document.body.prepend(sidebar);

    // --- סרגל תחתון (מובייל) ---
    const mobileNav = el('nav', 'sp-mobile-nav');
    items.forEach(item => {
        const a = el('a', item.key === activeKey ? 'active' : '', `<i class="fa-solid ${item.icon}"></i><span>${item.label.split(' ')[0]}</span>`);
        a.href = item.href;
        mobileNav.appendChild(a);
    });
    document.body.appendChild(mobileNav);

    // --- הזזת תוכן העמוד כדי שלא יוסתר מאחורי הסרגל הצדדי הקבוע ---
    document.body.classList.add('sp-report-page');
})();
