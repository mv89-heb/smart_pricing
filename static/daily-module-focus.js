/* Resolve the page module before paint-sensitive UI is exposed. */
(function () {
    const params = new URLSearchParams(window.location.search);
    const requested = params.get('module');
    const moduleName = requested === 'pricing' ? 'pricing' : 'daily';

    document.body.dataset.uiModule = moduleName;
    document.documentElement.dataset.uiModule = moduleName;

    // The legacy index contains analytics markup for backward compatibility.
    // It must never participate in the daily workspace.
    if (moduleName === 'daily') {
        const dashboard = document.getElementById('dashboard-modal');
        if (dashboard) {
            dashboard.classList.add('hidden');
            dashboard.setAttribute('aria-hidden', 'true');
        }
    }
})();
