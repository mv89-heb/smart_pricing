import importlib
import os

os.environ.setdefault("FLASK_ENV", "development")
os.environ.setdefault("DATABASE_URL", "sqlite:///test_production_entrypoint.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key")


def test_production_entrypoint_imports_and_exposes_app():
    module = importlib.import_module("production")
    assert module.app is not None
    assert module.app.name == "app"


def test_production_entrypoint_registers_core_routes():
    module = importlib.import_module("production")
    rules = {rule.rule for rule in module.app.url_map.iter_rules()}
    assert "/api/entries" in rules
    assert "/api/report/period" in rules
    assert "/api/dashboard/summary" in rules
    assert "/api/users/<int:user_id>/reset-password" in rules


def test_production_entrypoint_exposes_health_endpoint():
    module = importlib.import_module("production")
    rules = {rule.rule for rule in module.app.url_map.iter_rules()}
    assert "/health" in rules
