from pathlib import Path

from smartpricing.app_factory import _module_scripts


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"


def test_each_workspace_loads_the_unified_table_filter_owner():
    for path in ("/", "/periodic-report", "/static/dashboard.html"):
        scripts = " ".join(_module_scripts(path))
        assert "/static/table-filters.js" in scripts
        assert "/static/global-filters.js" not in scripts


def test_reports_has_only_reports_specific_runtime_assets():
    scripts = " ".join(_module_scripts("/periodic-report"))
    assert "/static/module-shell.js" in scripts
    assert "/static/table-filters.js" in scripts
    assert "/static/reports-module.js" in scripts
    assert "/static/global-filters.js" not in scripts
    assert "/static/period-report-ui.js" not in scripts
    assert "/static/period-report-loader.js" not in scripts


def test_module_isolation_css_hides_non_shell_body_children():
    css = (STATIC / "module-isolation.css").read_text(encoding="utf-8")
    assert "body.module-shell-ready > :not(.module-shell-sidebar):not(.module-shell-main):not(.module-shell-mobile-nav)" in css
    assert "display: none !important" in css


def test_table_filters_owns_quick_search_and_column_popover():
    js = (STATIC / "table-filters.js").read_text(encoding="utf-8")
    assert "חיפוש מהיר בטבלה" in js
    assert "tf-filter-btn" in js
    assert "tf-popover" in js
    assert "new MutationObserver" in js
