(() => {
  function attach() {
    if (document.querySelector('script[data-period-report-loaded]')) return;
    const left = document.getElementById('left-panel');
    if (!left) return setTimeout(attach, 300);
    const s = document.createElement('script');
    s.src = '/static/period-report-ui.js?v=1';
    s.defer = true;
    s.dataset.periodReportLoaded = '1';
    document.head.appendChild(s);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', attach); else attach();
})();
