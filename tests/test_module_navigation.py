import os
from pathlib import Path

os.environ.setdefault("FLASK_ENV", "development")
os.environ.setdefault("DATABASE_URL", "sqlite:///test_module_navigation.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key")

from wsgi import app


def _login(client, role="admin"):
    with client.session_transaction() as session:
        session["logged_in"] = True
        session["username"] = "test"
        session["role"] = role


def test_settings_route_is_registered():
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/settings" in rules


def test_module_shell_assets_are_injected_into_settings_page():
    client = app.test_client()
    _login(client)
    response = client.get("/settings")
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "/static/module-shell.css?v=1" in body
    assert "/static/module-shell-polish.css?v=1" in body
    assert "/static/module-shell.js?v=1" in body


def test_main_navigation_urls_are_present_in_shell_asset():
    shell = Path(app.static_folder, "module-shell.js").read_text(encoding="utf-8")
    for href in ("href:'/'", "href:'/?module=pricing'", "href:'/periodic-report'", "href:'/static/dashboard.html'", "href:'/settings'"):
        assert href in shell


def test_shell_has_distinct_module_metadata():
    shell = Path(app.static_folder, "module-shell.js").read_text(encoding="utf-8")
    for key in ("daily", "pricing", "reports", "dashboard", "settings"):
        assert f"{key}:" in shell
    assert "subtitle:'מוצרים, מחירים ותזמון עדכונים'" in shell
    assert "subtitle:'דוחות תקופתיים, סיכומים וייצוא'" in shell
    assert "subtitle:'מגמות, KPI וניתוח ביצועים'" in shell
    assert "subtitle:'משתמשים, גיבוי והעדפות מערכת'" in shell


def test_settings_page_is_rendered_inside_application_shell():
    client = app.test_client()
    _login(client)
    response = client.get("/settings")
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'id="settings-page"' in body
    assert "module-shell-settings" in body


def test_dashboard_and_report_keep_their_module_shell_assets():
    client = app.test_client()
    _login(client)
    for path in ("/periodic-report", "/static/dashboard.html"):
        response = client.get(path)
        body = response.get_data(as_text=True)
        assert response.status_code == 200
        assert "/static/module-shell.css?v=1" in body
        assert "/static/module-shell-polish.css?v=1" in body
        assert "/static/module-shell.js?v=1" in body


def test_ux_state_styles_exist_for_core_workspaces():
    css = Path(app.static_folder, "module-shell-polish.css").read_text(encoding="utf-8")
    assert ".ui-action-busy" in css
    assert "אין מוצרים להצגה" in css
    assert "אין חיובים להצגה ליום שנבחר" in css
    assert ".module-shell-reports-page #empty" in css


def test_product_form_stability_has_one_owner():
    stable = Path(app.static_folder, "app-shell-stability.js").read_text(encoding="utf-8")
    ui = Path(app.static_folder, "ui-stability.js").read_text(encoding="utf-8")
    assert "function fixProductFormReset" not in stable
    assert "window.cancelProductEdit" in ui
    assert "function fixBulkUpdate" in stable


def test_feature_scripts_are_scoped_to_their_own_modules():
    from smartpricing.app_factory import _module_scripts

    def paths(scripts):
        return {item.split("/static/", 1)[1].split("?", 1)[0] for item in scripts}

    daily = paths(_module_scripts("/"))
    reports = paths(_module_scripts("/periodic-report"))
    dashboard = paths(_module_scripts("/static/dashboard.html"))
    settings = paths(_module_scripts("/settings"))

    assert "module-shell.js" in daily and "global-filters.js" in daily
    assert "module-shell.js" in reports and "report-sort.js" in reports
    assert "module-shell.js" in dashboard
    assert "module-shell.js" in settings and "password-reset.js" in settings
    assert "browser-price-sync.js" not in reports
    assert "browser-price-sync.js" not in dashboard
    assert "global-filters.js" not in settings
    assert "app-shell-stability.js" not in reports
