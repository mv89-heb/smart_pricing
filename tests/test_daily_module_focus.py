from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_daily_module_has_its_own_template_and_controller():
    html=(ROOT/'templates/modules/daily.html').read_text(encoding='utf-8')
    js=(ROOT/'static/daily-module.js').read_text(encoding='utf-8')
    assert 'extends "base.html"' in html
    assert 'id="entry-form"' in html
    assert 'id="daily-table"' in html
    assert 'id="daily-drawer"' in html
    assert 'daily-module.js' in html
    assert 'async function loadEntries' in js
    assert 'async function addEntry' in js


def test_daily_template_contains_no_pricing_or_dashboard_business_dom():
    html=(ROOT/'templates/modules/daily.html').read_text(encoding='utf-8')
    for marker in ('pricing-body','dash-total','reportBody','dashboard-modal','right-panel'):
        assert marker not in html


def test_daily_route_is_server_owned_by_daily_template():
    pages=(ROOT/'smartpricing/routes/pages.py').read_text(encoding='utf-8')
    assert 'render_template("modules/daily.html", active_module=module, module_title=title)' in pages
    assert 'def index()' in pages
    assert 'def pricing()' in pages
