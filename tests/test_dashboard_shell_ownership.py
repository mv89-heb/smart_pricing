from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_dashboard_is_a_first_class_module_template():
    html=(ROOT/'templates/modules/dashboard.html').read_text(encoding='utf-8')
    assert 'extends "base.html"' in html
    assert 'id="dash-total"' in html
    assert 'id="dash-chart"' in html
    assert 'href="/periodic-report"' not in html

def test_dashboard_has_one_runtime_owner():
    html=(ROOT/'templates/modules/dashboard.html').read_text(encoding='utf-8')
    assert 'dashboard-module.js?v=1' in html
    assert 'module-shell.js' not in html
