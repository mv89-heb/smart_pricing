from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_reports_controller_is_owned_only_by_periodic_report():
    factory = (ROOT / "smartpricing" / "app_factory.py").read_text(encoding="utf-8")
    reports_block = factory.split('if path == "/periodic-report":', 1)[1].split('if path == "/settings":', 1)[0]
    assert 'reports-module.js' in reports_block
    assert 'reports-controls.js' not in reports_block
    assert 'reports-summary.js' not in reports_block


def test_reports_controls_keep_legacy_dom_contract():
    html = (ROOT / "static" / "periodic_report.html").read_text(encoding="utf-8")
    for element_id in ("fromDate", "toDate", "rangeError"):
        assert f'id="{element_id}"' in html
    assert 'onclick="loadReport()"' in html
    assert 'onclick="exportExcel()"' in html
    assert 'onclick="window.print()"' in html


def test_reports_module_contains_single_summary_render_contract():
    source = (ROOT / "static" / "reports-module.js").read_text(encoding="utf-8")
    assert 'const ReportsSummary = {' in source
    assert 'renderKpis(items)' in source
    assert 'renderProductSummary(items)' in source
    assert 'renderDaySummary(items)' in source
    assert 'renderAll(items)' in source
    assert 'window.ReportsSummary = ReportsSummary;' in source
