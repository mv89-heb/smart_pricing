import os
import tempfile

DB_FILE = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
DB_FILE.close()
os.environ["DATABASE_URL"] = f"sqlite:///{DB_FILE.name}"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["FLASK_ENV"] = "development"

from app import app, db, Product, PeriodLock, PriceHistory
import wsgi_ui  # noqa: F401,E402


def auth(client):
    with client.session_transaction() as sess:
        sess["logged_in"] = True
        sess["username"] = "admin"
        sess["role"] = "admin"


def headers(origin="http://localhost"):
    return {"X-Requested-With": "XMLHttpRequest", "Origin": origin}


def setup_function(_):
    with app.app_context():
        db.drop_all()
        db.create_all()


def test_period_lock_state_endpoint():
    client = app.test_client()
    auth(client)

    response = client.get("/api/periods/2026-08")
    assert response.status_code == 200
    assert response.get_json() == {
        "year_month": "2026-08",
        "locked": False,
        "locked_at": None,
    }

    assert client.post("/api/periods/2026-08/lock", headers=headers()).status_code == 200
    response = client.get("/api/periods/2026-08")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["year_month"] == "2026-08"
    assert payload["locked"] is True
    assert payload["locked_at"]


def test_browser_price_sync_respects_period_lock():
    client = app.test_client()
    auth(client)

    assert client.post(
        "/api/products",
        json={"name": "חלב", "price": 8},
        headers=headers(),
    ).status_code == 200

    with app.app_context():
        product = Product.query.filter_by(name="חלב").one()
        before_history = [
            (row.price, row.effective_from)
            for row in PriceHistory.query.filter_by(product_id=product.id).all()
        ]

    assert client.post("/api/periods/2026-08/lock", headers=headers()).status_code == 200

    response = client.post(
        "/api/browser-price-sync/apply",
        json={
            "effective_from": "2026-08-20",
            "updates": [{"name": "חלב", "price": 9}],
        },
        headers=headers(),
    )

    assert response.status_code == 423
    with app.app_context():
        product = Product.query.filter_by(name="חלב").one()
        after_history = [
            (row.price, row.effective_from)
            for row in PriceHistory.query.filter_by(product_id=product.id).all()
        ]
        assert float(product.price) == 8.0
        assert after_history == before_history


def test_browser_price_sync_applies_valid_update():
    client = app.test_client()
    auth(client)

    assert client.post(
        "/api/products",
        json={"name": "לחם", "price": 7.5},
        headers=headers(),
    ).status_code == 200

    response = client.post(
        "/api/browser-price-sync/apply",
        json={
            "effective_from": "2026-08-20",
            "updates": [{"name": "לחם", "price": 8.25}],
        },
        headers=headers(),
    )

    assert response.status_code == 200
    assert response.get_json()["applied"][0]["price"] == 8.25
    with app.app_context():
        product = Product.query.filter_by(name="לחם").one()
        assert float(product.price) == 8.25
        rows = PriceHistory.query.filter_by(product_id=product.id).all()
        assert len(rows) == 1
        assert float(rows[0].price) == 8.25
