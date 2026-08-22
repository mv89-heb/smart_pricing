from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "static" / "periodic_report.html"
SUMMARY = ROOT / "static" / "reports-summary.js"


def test_reports_summary_owner_exists():
    content = SUMMARY.read_text(encoding="utf-8")
    assert "window.ReportsSummary" in content
    assert "renderAll" in content
    assert "renderKpis" in content
    assert "renderProductSummary" in content
    assert "renderDaySummary" in content


def test_periodic_report_keeps_reports_dom_contract():
    content = REPORT.read_text(encoding="utf-8")
    for element_id in (
        "reports-module",
        "fromDate",
        "toDate",
        "rangeError",
        "grandTotal",
        "regularTotal",
        "extraTotal",
        "daysCount",
        "averageDay",
        "reportBody",
        "productSummary",
        "daySummary",
        "editModal",
    ):
        assert f'id="{element_id}"' in content


def test_periodic_report_has_no_duplicate_summary_renderers():
    content = REPORT.read_text(encoding="utf-8")
    assert content.count("function renderProductSummary(") == 0
    assert content.count("function renderDaySummary(") == 0


def test_periodic_report_delegates_summary_rendering():
    content = REPORT.read_text(encoding="utf-8")
    assert "ReportsSummary.renderAll(entries,products,renderTable)" in content
    assert "function renderAll(){ReportsSummary.renderAll(entries,products,renderTable)}" in content
