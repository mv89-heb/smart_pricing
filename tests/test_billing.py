import os
from pathlib import Path

os.environ.setdefault("FLASK_ENV", "development")
os.environ.setdefault("DATABASE_URL", "sqlite:///test_billing.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key")

from wsgi import app
from smartpricing.extensions import db
from smartpricing.models import DailyEntry


def auth(client, role="admin"):
    with client.session_transaction() as session:
        session["logged_in"] = True
        session["username"] = "test"
        session["role"] = role


def headers(origin=None):
    result = {"X-Requested-With": "XMLHttpRequest"}
    if origin:
        result["Origin"] = origin
    return result


def test_unauthenticated_api_is_rejected():
    client = app.test_client()
    response = client.get("/api/report/period?from=2026-08-01&to=2026-08-31")
    assert response.status_code == 401


def test_dashboard_and_periodic_pages_are_available_after_login():
    client = app.test_client()
    auth(client)
    dashboard = client.get("/static/dashboard.html")
    periodic = client.get("/periodic-report")
    assert dashboard.status_code == 200
    assert "dashboard-module" in dashboard.get_data(as_text=True).lower() or "דשבורד" in dashboard.get_data(as_text=True)
    assert periodic.status_code == 200
    assert "דוח חיובים חודשי ותקופתי" in periodic.get_data(as_text=True)
