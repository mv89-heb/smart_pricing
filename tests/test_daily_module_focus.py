from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_daily_module_assets_are_present():
    css = (ROOT / "static" / "daily-module-focus.css").read_text(encoding="utf-8")
    js = (ROOT / "static" / "daily-module-focus.js").read_text(encoding="utf-8")
    pages = (ROOT / "smartpricing" / "routes" / "pages.py").read_text(encoding="utf-8")

    assert 'body[data-ui-module="daily"] #right-panel' in css
    assert 'body[data-ui-module="daily"] #dashboard-modal' in css
    assert 'body[data-ui-module="pricing"] #left-panel' in css
    assert 'params.get(\'module\')' in js
    assert 'daily-module-focus.css?v=1' in pages
    assert 'daily-module-focus.js?v=1' in pages


def test_daily_module_does_not_own_periodic_report_route():
    pages = (ROOT / "smartpricing" / "routes" / "pages.py").read_text(encoding="utf-8")
    assert 'def periodic_report()' in pages
    assert 'send_from_directory(current_app.static_folder, "periodic_report.html")' in pages
