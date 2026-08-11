import os
import tempfile

DB_FILE = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
DB_FILE.close()
os.environ["DATABASE_URL"] = f"sqlite:///{DB_FILE.name}"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["FLASK_ENV"] = "development"

from app import app, db, Product, DailyEntry, PeriodLock


def auth(client, role="admin"):
    with client.session_transaction() as sess:
        sess["logged_in"] = True
        sess["username"] = "tester"
        sess["role"] = role


def headers(origin="http://localhost"):
    return {"X-Requested-With": "XMLHttpRequest", "Origin": origin}


def setup_function(_):
    with app.app_context():
        db.drop_all()
        db.create_all()


def test_price_change_does_not_rewrite_previous_entry():
    client = app.test_client()
    auth(client)

    assert client.post("/api/products", json={"name": "קפה", "price": 10}, headers=headers()).status_code == 200
    assert client.post("/api/entries", json={"date": "2026-08-01", "product_name": "קפה", "quantity": 10}, headers=headers()).status_code == 200
    assert client.put("/api/products/%D7%A7%D7%A4%D7%94", json={"price": 12}, headers=headers()).status_code == 200
    assert client.post("/api/entries", json={"date": "2026-08-01", "product_name": "קפה", "quantity": 5}, headers=headers()).status_code == 200

    with app.app_context():
        rows = DailyEntry.query.order_by(DailyEntry.id.asc()).all()
        assert len(rows) == 2
        assert float(rows[0].unit_price) == 10.0
        assert float(rows[0].total_amount) == 100.0
        assert float(rows[1].unit_price) == 12.0
        assert float(rows[1].total_amount) == 60.0

    report = client.get("/api/report/period?from=2026-08-01&to=2026-08-01")
    assert report.status_code == 200
    assert report.get_json()["summary"]["grand_total"] == 160.0


def test_same_price_entries_are_aggregated_without_losing_total():
    client = app.test_client()
    auth(client)
    assert client.post("/api/products", json={"name": "לחם", "price": 7.5}, headers=headers()).status_code == 200
    assert client.post("/api/entries", json={"date": "2026-08-02", "product_name": "לחם", "quantity": 2}, headers=headers()).status_code == 200
    assert client.post("/api/entries", json={"date": "2026-08-02", "product_name": "לחם", "quantity": 3}, headers=headers()).status_code == 200

    with app.app_context():
        rows = DailyEntry.query.all()
        assert len(rows) == 1
        assert float(rows[0].quantity) == 5.0
        assert float(rows[0].total_amount) == 37.5


def test_period_report_and_compare():
    client = app.test_client()
    auth(client)
    assert client.post("/api/products", json={"name": "חלב", "price": 8}, headers=headers()).status_code == 200
    assert client.post("/api/entries", json={"date": "2026-07-10", "product_name": "חלב", "quantity": 10}, headers=headers()).status_code == 200
    assert client.post("/api/entries", json={"date": "2026-08-10", "product_name": "חלב", "quantity": 15}, headers=headers()).status_code == 200

    period = client.get("/api/report/period?from=2026-08-01&to=2026-08-31")
    assert period.status_code == 200
    payload = period.get_json()
    assert payload["summary"]["grand_total"] == 120.0
    assert payload["summary"]["days_count"] == 1
    assert payload["product_summary"]["חלב"]["quantity"] == 15.0

    compare = client.get("/api/report/compare?a_from=2026-07-01&a_to=2026-07-31&b_from=2026-08-01&b_to=2026-08-31")
    assert compare.status_code == 200
    assert compare.get_json()["change"]["grand_total"] == 50.0


def test_period_lock_blocks_changes():
    client = app.test_client()
    auth(client)
    assert client.post("/api/products", json={"name": "חלב", "price": 8}, headers=headers()).status_code == 200
    assert client.post("/api/periods/2026-08/lock", headers=headers()).status_code == 200

    response = client.post("/api/entries", json={"date": "2026-08-05", "product_name": "חלב", "quantity": 1}, headers=headers())
    assert response.status_code == 423

    unlock = client.post("/api/periods/2026-08/unlock", headers=headers())
    assert unlock.status_code == 200
    assert client.post("/api/entries", json={"date": "2026-08-05", "product_name": "חלב", "quantity": 1}, headers=headers()).status_code == 200


def test_viewer_cannot_write():
    client = app.test_client()
    auth(client, role="viewer")
    response = client.post("/api/entries", json={"date": "2026-08-05", "product_name": "חלב", "quantity": 1}, headers=headers())
    assert response.status_code == 403


def test_cross_origin_write_is_rejected():
    client = app.test_client()
    auth(client)
    response = client.post("/api/products", json={"name": "מים", "price": 3}, headers=headers("https://evil.example"))
    assert response.status_code == 403


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
    assert "Dashboard חיובים" in dashboard.get_data(as_text=True)
    assert periodic.status_code == 200
    assert "דוח חיובים חודשי ותקופתי" in periodic.get_data(as_text=True)
