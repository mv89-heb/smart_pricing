from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def test_reports_page_is_a_module_template_not_a_second_shell():
    html=(ROOT/'templates/modules/reports.html').read_text(encoding='utf-8')
    for element_id in ('fromDate','toDate','reportBody','productSummary','daySummary','editModal'): assert f'id="{element_id}"' in html
    assert 'extends "base.html"' in html and '<header class="' not in html
def test_pages_route_owns_reports_template():
    source=(ROOT/'smartpricing/routes/pages.py').read_text(encoding='utf-8')
    assert '_module("modules/reports.html", "reports", "דוחות")' in source and 'send_from_directory' not in source and 'period-report-loader.js' not in source
