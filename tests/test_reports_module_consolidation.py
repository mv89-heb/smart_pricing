from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];STATIC=ROOT/'static'
def test_reports_module_has_single_frontend_owner():
    source=(STATIC/'reports-module.js').read_text(encoding='utf-8')
    for marker in ('window.ReportsSummary','function setPreset','function loadReport','function renderTable','function openEdit','function saveEdit','function deleteRow','function exportExcel','renderProductSummary','renderDaySummary'): assert marker in source
def test_reports_legacy_split_controllers_are_removed_from_runtime():
    html=(ROOT/'templates/modules/reports.html').read_text(encoding='utf-8')
    for marker in ('reports-controls.js','reports-summary.js','period-report-loader.js','period-report-ui.js','global-filters.js'): assert marker not in html
def test_reports_template_has_no_inline_business_script():
    html=(ROOT/'templates/modules/reports.html').read_text(encoding='utf-8')
    for marker in ('function loadReport','function renderProductSummary','function renderDaySummary','function saveEdit'): assert marker not in html
    assert "filename='reports-module.js'" in html
def test_reports_preserves_core_hooks_and_drawer_contract():
    html=(ROOT/'templates/modules/reports.html').read_text(encoding='utf-8')
    for marker in ('id="fromDate"','id="toDate"','id="rangeError"','id="grandTotal"','id="regularTotal"','id="extraTotal"','id="daysCount"','id="reportBody"','id="productSummary"','id="daySummary"','id="editModal"','id="editId"','id="editQty"','id="editNote"','id="editExtra"','onclick="exportExcel()"'): assert marker in html
def test_backend_entry_edit_contract_is_present():
    source=(ROOT/'smartpricing/routes/entries.py').read_text(encoding='utf-8');assert '@bp.route("/api/entries/<int:entry_id>", methods=["PUT"])' in source and '@bp.route("/api/entries/<int:entry_id>", methods=["DELETE"])' in source and 'write_access()' in source and 'is_locked(entry.date)' in source and 'log_activity(' in source
