import importlib
import os

os.environ.setdefault("FLASK_ENV", "development")
os.environ.setdefault("DATABASE_URL", "sqlite:///test_production_entrypoint.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key")


def test_production_entrypoint_imports_and_exposes_app():
    module = importlib.import_module("wsgi_ui")
    assert module.app is not None
    assert module.User is not None
    assert module.admin_access is not None


def test_production_entrypoint_registers_password_reset_route():
    module = importlib.import_module("wsgi_ui")
    rules = {rule.rule for rule in module.app.url_map.iter_rules()}
    assert "/api/users/<int:user_id>/reset-password" in rules
