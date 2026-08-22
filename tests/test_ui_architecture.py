from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def test_base_template_is_the_single_application_shell():
    html=(ROOT/'templates/base.html').read_text(encoding='utf-8')
    assert 'saas-sidebar' in html
    assert 'saas-topbar' in html
    assert '{% block content %}' in html
    assert 'global-filters.js' not in html


def test_modules_have_separate_jinja_templates():
    modules=ROOT/'templates/modules'
    expected={'daily.html','pricing.html','dashboard.html','reports.html'}
    assert expected.issubset({p.name for p in modules.glob('*.html')})
    for name in expected:
        html=(modules/name).read_text(encoding='utf-8')
        assert '{% extends "base.html" %}' in html


def test_daily_module_has_no_other_workspace_markup():
    html=(ROOT/'templates/modules/daily.html').read_text(encoding='utf-8')
    for marker in ('pricing-body','dash-total','reportBody','users-area'):
        assert marker not in html


def test_frontend_owners_are_module_scoped():
    for name in ('daily-module.js','pricing-module.js','dashboard-module.js','reports-module.js','settings-module.js','saas-shell.js'):
        assert (ROOT/'static'/name).exists()


def test_legacy_global_filter_owners_are_not_loaded_by_new_templates():
    templates=''.join(p.read_text(encoding='utf-8') for p in (ROOT/'templates').rglob('*.html'))
    for marker in ('global-filters.js','reports-controls.js','reports-summary.js','period-report-loader.js'):
        assert marker not in templates


def test_quick_search_and_column_filter_contract_is_present():
    daily=(ROOT/'templates/modules/daily.html').read_text(encoding='utf-8')
    pricing=(ROOT/'templates/modules/pricing.html').read_text(encoding='utf-8')
    reports=(ROOT/'templates/modules/reports.html').read_text(encoding='utf-8')
    for html in (daily,pricing,reports):
        assert 'saas-quick-search' in html
        assert 'saas-filter-button' in html
