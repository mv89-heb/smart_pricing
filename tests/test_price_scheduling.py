import os
import pytest

os.environ.setdefault("FLASK_ENV", "development")
os.environ.setdefault("DATABASE_URL", "sqlite:///test_price_scheduling.db")

from app import app, db, Product, PriceHistory, DailyEntry, User
from werkzeug.security import generate_password_hash

@pytest.fixture()
def client():
    app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI="sqlite:///test_price_scheduling.db")
    with app.app_context():
        db.drop_all()
        db.create_all()
        user = User(username="admin", password=generate_password_hash("password123"), role="admin")
        db.session.add(user)
        db.session.commit()
    with app.test_client() as client:
        with client.session_transaction() as session:
            session["logged_in"] = True
            session["username"] = "admin"
            session["role"] = "admin"
        yield client
    with app.app_context():
        db.session.remove()
        db.drop_all()

JSON_HEADERS = {"Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest"}

def test_future_price_does_not_change_existing_or_current_price(client):
    created = client.post("/api/products", json={"name": "קולה", "price": 8, "effective_from": "2026-08-01"}, headers=JSON_HEADERS)
    assert created.status_code == 200

    scheduled = client.put("/api/products/%D7%A7%D7%95%D7%9C%D7%94", json={"name": "קולה", "price": 9, "effective_from": "2099-01-01"}, headers=JSON_HEADERS)
    assert scheduled.status_code == 200

    with app.app_context():
        product = Product.query.filter_by(name="קולה").first()
        assert float(product.price) == 8.0
        rows = PriceHistory.query.filter_by(product_id=product.id).order_by(PriceHistory.effective_from.asc()).all()
        assert [(r.effective_from, float(r.price)) for r in rows] == [("2026-08-01", 8.0), ("2099-01-01", 9.0)]

    before = client.post("/api/entries", json={"date": "2098-12-31", "product_name": "קולה", "quantity": 2, "is_extra": False}, headers=JSON_HEADERS)
    after = client.post("/api/entries", json={"date": "2099-01-01", "product_name": "קולה", "quantity": 2, "is_extra": False}, headers=JSON_HEADERS)
    assert before.status_code == 200
    assert after.status_code == 200
    assert before.get_json()["unit_price"] == 8.0
    assert after.get_json()["unit_price"] == 9.0

    old_entry = client.get("/api/entries/2098-12-31").get_json()[0]
    new_entry = client.get("/api/entries/2099-01-01").get_json()[0]
    assert old_entry["unit_price"] == 8.0
    assert old_entry["total_amount"] == 16.0
    assert new_entry["unit_price"] == 9.0
    assert new_entry["total_amount"] == 18.0


def test_cancel_future_prices(client):
    client.post("/api/products", json={"name": "מיץ", "price": 5, "effective_from": "2026-08-01"}, headers=JSON_HEADERS)
    client.put("/api/products/%D7%9E%D7%99%D7%A5", json={"name": "מיץ", "price": 7, "effective_from": "2099-01-01"}, headers=JSON_HEADERS)
    response = client.delete("/api/products/%D7%9E%D7%99%D7%A5/scheduled", headers=JSON_HEADERS)
    assert response.status_code == 200
    assert response.get_json()["cancelled"] == 1

    with app.app_context():
        product = Product.query.filter_by(name="מיץ").first()
        rows = PriceHistory.query.filter_by(product_id=product.id).all()
        assert [(r.effective_from, float(r.price)) for r in rows] == [("2026-08-01", 5.0)]
