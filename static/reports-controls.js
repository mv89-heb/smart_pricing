(() => {
  'use strict';

  function initReportsControls() {
    const root = document.getElementById('reports-module') || document.body;
    const from = document.getElementById('fromDate');
    const to = document.getElementById('toDate');
    const error = document.getElementById('rangeError');
    if (!from || !to || !error || root.dataset.reportsControlsReady === 'true') return;

    root.dataset.reportsControlsReady = 'true';
    root.classList.add('reports-controls-enabled');

    const controls = from.closest('section');
    if (controls) {
      controls.dataset.reportsControls = 'true';
    }

    function validateRange() {
      const invalid = !from.value || !to.value || from.value > to.value;
      if (invalid) {
        error.textContent = 'טווח תאריכים לא תקין';
        error.classList.remove('hidden');
      } else {
        error.classList.add('hidden');
      }
      return !invalid;
    }

    from.addEventListener('change', validateRange, { passive: true });
    to.addEventListener('change', validateRange, { passive: true });

    root.addEventListener('keydown', (event) => {
      if (event.key !== 'Enter' || event.target !== from && event.target !== to) return;
      if (validateRange() && typeof window.loadReport === 'function') {
        window.loadReport();
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initReportsControls, { once: true });
  } else {
    initReportsControls();
  }
})();
