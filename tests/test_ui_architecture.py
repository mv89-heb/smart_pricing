from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def test_base_template_is_the_single_application_shell():
    html=(ROOT/'templates/base.html').read_text(encoding='utf-8');assert 'saas-sidebar' in html and 'saas-topbar' in html and '{% block content %}' in html and 'global-filters.js' not in html
def test_modules_have_separate_jinja_templates():
    modules=ROOT/'templates/modules';expected={'daily.html','pricing.html','dashboard.html','reports.html'};assert expected.issubset({p.name for p in modules.glob('*.html')})
    for name in expected: assert '{% extends "base.html" %}' in (modules/name).read_text(encoding='utf-8')
def test_daily_module_has_no_other_workspace_markup():
    html=(ROOT/'templates/modules/daily.html').read_text(encoding='utf-8')
    for marker in ('pricing-body','dash-total','reportBody','users-area'): assert marker not in html
def test_frontend_owners_are_module_scoped():
    for name in ('daily-module.js','pricing-module.js','dashboard-module.js','reports-module.js','settings-module.js','saas-shell.js','table-filters.js'): assert (ROOT/'static'/name).exists()
def test_legacy_global_filter_owners_are_not_loaded_by_new_templates():
    templates=''.join(p.read_text(encoding='utf-8') for p in (ROOT/'templates').rglob('*.html'))
    for marker in ('global-filters.js','reports-controls.js','reports-summary.js','period-report-loader.js'): assert marker not in templates
def test_shared_inline_filter_runtime_is_used_by_operational_modules():
    for name in ('daily.html','pricing.html','reports.html'):
        html=(ROOT/'templates/modules'/name).read_text(encoding='utf-8');assert "filename='table-filters.js'" in html
    source=(ROOT/'static/table-filters.js').read_text(encoding='utf-8');assert 'חיפוש מהיר בטבלה' in source and 'tf-filter-btn' in source and 'tf-popover' in source
