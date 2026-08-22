from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_reports_page_is_a_module_template_not_a_second_shell():
    html=(ROOT/'templates/modules/reports.html').read_text(encoding='utf-8')
    for element_id in ('fromDate','toDate','reportBody','productSummary','daySummary','editModal'):
        assert f'id="{element_id}"' in html
    assert 'extends "base.html"' in html
    assert '<header class="' not in html

def test_pages_route_owns_reports_template():
    source=(ROOT/'smartpricing/routes/pages.py').read_text(encoding='utf-8')
    assert 'render_template("modules/reports.html"' in source
    assert 'send_from_directory' not in source
    assert 'period-report-loader.js' not in source
