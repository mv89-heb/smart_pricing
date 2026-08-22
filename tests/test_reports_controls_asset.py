from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_reports_controls_asset_is_owned_only_by_periodic_report():
    factory = (ROOT / "smartpricing" / "app_factory.py").read_text(encoding="utf-8")
    reports_block = factory.split('if path == "/periodic-report":', 1)[1].split('if path == "/settings":', 1)[0]
    assert 'reports-controls.js' in reports_block

    common = factory.split('def _module_scripts', 1)[1]
    assert common.count('reports-controls.js') == 1


def test_reports_controls_keeps_legacy_dom_contract():
    html = (ROOT / "static" / "periodic_report.html").read_text(encoding="utf-8")
    for element_id in ("fromDate", "toDate", "rangeError"):
        assert f'id="{element_id}"' in html
    assert 'onclick="loadReport()"' in html
    assert 'onclick="exportExcel()"' in html
    assert 'onclick="window.print()"' in html


def test_reports_summary_asset_is_owned_only_by_periodic_report():
    factory = (ROOT / "smartpricing" / "app_factory.py").read_text(encoding="utf-8")
    reports_block = factory.split('if path == "/periodic-report":', 1)[1].split('if path == "/settings":', 1)[0]
    assert 'reports-summary.js' in reports_block
    common = factory.split('def _module_scripts', 1)[1]
    assert common.count('reports-summary.js') == 1


def test_reports_summary_exposes_single_render_contract():
    summary = (ROOT / "static" / "reports-summary.js").read_text(encoding="utf-8")
    assert 'function renderAll(entries, products, renderTable)' in summary
    assert 'renderKpis(safeEntries, safeProducts);' in summary
    assert 'renderProductSummary(safeEntries, safeProducts);' in summary
    assert 'renderDaySummary(safeEntries, safeProducts);' in summary
    assert 'renderAll,' in summary
