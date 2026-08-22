from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_reports_controller_is_owned_by_reports_template():
    html=(ROOT/'templates/modules/reports.html').read_text(encoding='utf-8')
    assert 'reports-module.js?v=4' in html
    for marker in ('reports-controls.js','reports-summary.js','global-filters.js','period-report-loader.js'):
        assert marker not in html

def test_reports_controls_keep_core_dom_contract():
    html=(ROOT/'templates/modules/reports.html').read_text(encoding='utf-8')
    for element_id in ('fromDate','toDate','rangeError'):
        assert f'id="{element_id}"' in html
    assert 'onclick="loadReport()"' in html
    assert 'onclick="exportExcel()"' in html
    assert 'window.print()' in html

def test_reports_module_contains_single_summary_render_contract():
    source=(ROOT/'static/reports-module.js').read_text(encoding='utf-8')
    for marker in ('const ReportsSummary = {','renderKpis(items)','renderProductSummary(items)','renderDaySummary(items)','renderAll(items)','window.ReportsSummary = ReportsSummary;'):
        assert marker in source
