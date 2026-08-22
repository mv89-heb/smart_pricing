import os
from pathlib import Path

os.environ.setdefault("FLASK_ENV", "development")
os.environ.setdefault("DATABASE_URL", "sqlite:///test_reports_module.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key")

from wsgi import app


STATIC = Path(app.static_folder)


def _login(client, role="admin"):
    with client.session_transaction() as session:
        session["logged_in"] = True
        session["username"] = "test"
        session["role"] = role


def test_reports_module_has_single_frontend_owner():
    source = (STATIC / "reports-module.js").read_text(encoding="utf-8")
    assert "window.ReportsSummary" in source
    assert "function setPreset" in source
    assert "function loadReport" in source
    assert "function renderTable" in source
    assert "function openEdit" in source
    assert "function saveEdit" in source
    assert "function deleteRow" in source
    assert "function exportExcel" in source
    assert "renderProductSummary" in source
    assert "renderDaySummary" in source


def test_reports_legacy_split_controllers_are_removed():
    assert not (STATIC / "reports-controls.js").exists()
    assert not (STATIC / "reports-summary.js").exists()


def test_periodic_report_has_no_inline_business_script():
    html = (STATIC / "periodic_report.html").read_text(encoding="utf-8")
    assert 'id="reports-module"' in html
    assert 'data-module="reports"' in html
    for marker in ("function loadReport", "function renderProductSummary", "function renderDaySummary", "function saveEdit"):
        assert marker not in html


def test_periodic_report_preserves_all_report_hooks():
    html = (STATIC / "periodic_report.html").read_text(encoding="utf-8")
    for marker in (
        'id="fromDate"', 'id="toDate"', 'id="rangeError"',
        'id="grandTotal"', 'id="regularTotal"', 'id="extraTotal"',
        'id="daysCount"', 'id="averageDay"', 'id="reportBody"',
        'id="productSummary"', 'id="daySummary"', 'id="editModal"',
        'id="editId"', 'id="editProduct"', 'id="editQty"',
        'id="editNote"', 'id="editExtra"',
        'onclick="exportExcel()"', 'onclick="window.print()"',
    ):
        assert marker in html


def test_periodic_report_injects_unified_controller():
    client = app.test_client()
    _login(client)
    response = client.get("/periodic-report")
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "/static/reports-module.js?v=2" in body
    assert "/static/table-filters.js?v=1" in body
    assert "/static/reports-controls.js" not in body
    assert "/static/reports-summary.js" not in body
    assert "/static/global-filters.js" not in body


def test_drawer_contract_and_accessible_controls_exist():
    html = (STATIC / "periodic_report.html").read_text(encoding="utf-8")
    css = (STATIC / "reports-module.css").read_text(encoding="utf-8")
    js = (STATIC / "reports-module.js").read_text(encoding="utf-8")
    assert 'role="dialog"' in html
    assert 'aria-modal="true"' in html
    assert 'aria-label="סגירת חלון עריכה"' in html
    assert "#editModal:not(.hidden)" in css
    assert "event.key === 'Escape'" in js
    assert "event.target === $('editModal')" in js


def test_backend_entry_edit_contract_is_present():
    source = (Path(app.root_path) / "routes" / "entries.py").read_text(encoding="utf-8")
    assert '@bp.route("/api/entries/<int:entry_id>", methods=["PUT"])' in source
    assert '@bp.route("/api/entries/<int:entry_id>", methods=["DELETE"])' in source
    assert "write_access()" in source
    assert "is_locked(entry.date)" in source
    assert "log_activity(" in source
