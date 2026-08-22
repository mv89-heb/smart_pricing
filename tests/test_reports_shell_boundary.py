from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_reports_page_keeps_business_dom_during_incremental_migration():
    html = (ROOT / "static" / "periodic_report.html").read_text(encoding="utf-8")

    # Business/UI contracts intentionally remain in the legacy page during
    # the incremental migration.
    for element_id in ("fromDate", "toDate", "reportBody", "productSummary", "daySummary", "editModal"):
        assert f'id="{element_id}"' in html

    # Source compatibility remains until the next migration step; the
    # runtime Module Shell removes this legacy chrome before presentation.
    assert '<header class="' in html
    assert "toggleDark()" in html
    assert "toggleFullscreen()" in html


def test_module_shell_owns_reports_runtime_boundary():
    shell = (ROOT / "static" / "module-shell.js").read_text(encoding="utf-8")

    assert "root.id = 'reports-module'" in shell
    assert "root.dataset.module = active" in shell
    assert "legacyHeader.remove()" in shell
    assert "module-shell-legacy-page module-shell-${active}-page" in shell


def test_periodic_report_does_not_load_unused_report_sort_asset():
    factory = (ROOT / "smartpricing" / "app_factory.py").read_text(encoding="utf-8")
    periodic_block = factory.split('if path == "/periodic-report":', 1)[1].split('if path == "/settings":', 1)[0]
    assert "report-sort.js" not in periodic_block
