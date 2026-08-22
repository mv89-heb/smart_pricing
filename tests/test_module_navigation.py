import os

os.environ.setdefault("FLASK_ENV", "development")
os.environ.setdefault("DATABASE_URL", "sqlite:///test_module_navigation.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key")

from wsgi import app


def test_settings_route_is_registered():
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/settings" in rules


def test_module_shell_assets_are_injected_into_settings_page():
    client = app.test_client()
    with client.session_transaction() as session:
        session["logged_in"] = True
        session["username"] = "test"
        session["role"] = "admin"
    response = client.get("/settings")
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "/static/module-shell.css?v=1" in body
    assert "/static/module-shell.js?v=1" in body


def test_main_navigation_urls_are_present_in_shell_asset():
    from pathlib import Path

    shell = Path(app.static_folder, "module-shell.js").read_text(encoding="utf-8")
    assert "href:'/'" in shell
    assert "href:'/?module=pricing'" in shell
    assert "href:'/periodic-report'" in shell
    assert "href:'/static/dashboard.html'" in shell
    assert "href:'/settings'" in shell
