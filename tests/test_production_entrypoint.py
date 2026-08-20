import os

os.environ.setdefault("FLASK_ENV", "development")
os.environ.setdefault("DATABASE_URL", "sqlite:///test_production_entrypoint.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key")

# Import the production composition root before any test issues a request.
# Flask intentionally freezes route registration after the first request.
import production  # noqa: E402


def test_production_entrypoint_imports_and_exposes_app():
    assert production.app is not None
    assert production.app.name == "app"


def test_production_entrypoint_registers_core_routes():
    rules = {rule.rule for rule in production.app.url_map.iter_rules()}
    assert "/api/entries" in rules
    assert "/api/report/period" in rules
    assert "/api/dashboard/summary" in rules
    assert "/api/users/<int:user_id>/reset-password" in rules
    assert "/api/report/all" in rules
    assert "/api/data-health" in rules


def test_production_entrypoint_exposes_health_endpoint():
    response = production.app.test_client().get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}
