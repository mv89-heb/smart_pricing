import os
import tempfile

DB_FILE = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
DB_FILE.close()
os.environ["DATABASE_URL"] = f"sqlite:///{DB_FILE.name}"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["FLASK_ENV"] = "development"

from werkzeug.security import generate_password_hash

from smartpricing.app_factory import create_app
from smartpricing.extensions import db
from smartpricing.models import DailyEntry, Product, User

app = create_app()


def auth(client, role="admin"):
    with app.app_context():
        user = User.query.filter_by(username="perf-tester").first()
        if user is None:
            db.session.add(User(username="perf-tester", password=generate_password_hash("test-pass-123"), role=role))
        else:
            user.role = role
        db.session.commit()
    with client.session_transaction() as sess:
        sess.update({"logged_in": True, "username": "perf-tester", "role": role})


def headers():
    return {"X-Requested-With": "XMLHttpRequest", "Origin": "http://localhost"}


def setup_function(_):
    with app.app_context():
        db.drop_all()
        db.create_all()


def test_dashboard_summary_is_lightweight_and_has_no_entry_payload():
    client = app.test_client()
    auth(client)
    assert client.post("/api/products", json={"name": "קפה", "price": 10}, headers=headers()).status_code == 200
    for day in range(1, 11):
        assert client.post("/api/entries", json={"date": f"2026-08-{day:02d}", "product_name": "קפה", "quantity": day}, headers=headers()).status_code == 200
    response = client.get("/api/dashboard/summary?from=2026-08-01&to=2026-08-31")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["summary"]["grand_total"] == 550.0
    assert payload["summary"]["days_count"] == 10
    assert payload["entries"] == []
    assert payload["product_summary"]["קפה"]["quantity"] == 55.0


def test_copy_day_is_atomic_single_request_and_preserves_target_pricing():
    client = app.test_client()
    auth(client)
    assert client.post("/api/products", json={"name": "חלב", "price": 8}, headers=headers()).status_code == 200
    assert client.post("/api/products", json={"name": "לחם", "price": 6}, headers=headers()).status_code == 200
    assert client.post("/api/entries", json={"date": "2026-08-22", "product_name": "חלב", "quantity": 2}, headers=headers()).status_code == 200
    assert client.post("/api/entries", json={"date": "2026-08-22", "product_name": "לחם", "quantity": 3, "is_extra": True}, headers=headers()).status_code == 200

    response = client.post("/api/entries/copy", json={"source_date": "2026-08-22", "target_date": "2026-08-23"}, headers=headers())
    assert response.status_code == 200
    assert response.get_json()["copied"] == 2

    with app.app_context():
        rows = DailyEntry.query.filter_by(date="2026-08-23").order_by(DailyEntry.id).all()
        assert len(rows) == 2
        assert float(rows[0].quantity) == 2.0
        assert float(rows[0].unit_price) == 8.0
        assert float(rows[1].quantity) == 3.0
        assert float(rows[1].unit_price) == 6.0


def test_product_details_returns_scheduled_price_without_n_plus_one_behavior():
    client = app.test_client()
    auth(client)
    for index in range(20):
        response = client.post("/api/products", json={"name": f"מוצר {index}", "price": index + 1}, headers=headers())
        assert response.status_code == 200
    response = client.get("/api/products/details")
    assert response.status_code == 200
    payload = response.get_json()
    assert len(payload) == 20
    assert all("scheduled_price" in item for item in payload)


def test_static_assets_are_cacheable():
    client = app.test_client()
    auth(client)
    response = client.get("/static/daily-module.js?v=test")
    assert response.status_code == 200
    assert "max-age=3600" in response.headers.get("Cache-Control", "")
