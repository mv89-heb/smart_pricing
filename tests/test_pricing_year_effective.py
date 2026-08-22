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
from smartpricing.models import PriceHistory, Product, User
from smartpricing.services.pricing import price_for_date

app = create_app()


def setup_function(_):
    with app.app_context():
        db.drop_all()
        db.create_all()
        db.session.add(
            User(
                username="test",
                password=generate_password_hash("test-pass-123"),
                role="admin",
            )
        )
        db.session.commit()


def _client():
    client = app.test_client()
    with client.session_transaction() as session:
        session.update(logged_in=True, username="test", role="admin")
    return client


def test_year_start_effective_applies_current_price_to_every_product():
    with app.app_context():
        first = Product(name="מוצר א", price=12.5, tag=None)
        second = Product(name="מוצר ב", price=30, tag="X")
        db.session.add_all([first, second])
        db.session.commit()

    response = _client().post(
        "/api/products/apply-year-effective",
        json={"year": 2026},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert response.status_code == 200
    assert response.get_json()["updated"] == 2

    with app.app_context():
        products = Product.query.order_by(Product.id).all()
        rows = PriceHistory.query.filter_by(effective_from="2026-01-01").order_by(PriceHistory.product_id).all()
        assert len(rows) == 2
        assert [float(row.price) for row in rows] == [12.5, 30.0]
        assert price_for_date(products[0], "2026-01-01") == 12.5
        assert price_for_date(products[1], "2026-06-01") == 30


def test_year_start_effective_updates_existing_baseline_without_duplicates():
    with app.app_context():
        product = Product(name="מוצר", price=25, tag=None)
        db.session.add(product)
        db.session.flush()
        db.session.add(PriceHistory(product_id=product.id, price=20, effective_from="2026-01-01", changed_by="old"))
        db.session.commit()

    response = _client().post(
        "/api/products/apply-year-effective",
        json={"year": 2026},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert response.status_code == 200

    with app.app_context():
        rows = PriceHistory.query.filter_by(effective_from="2026-01-01").all()
        assert len(rows) == 1
        assert float(rows[0].price) == 25
        assert rows[0].changed_by == "test"


def test_year_start_effective_rejects_locked_start_period():
    with app.app_context():
        db.session.add(Product(name="מוצר", price=10, tag=None))
        db.session.commit()

        from smartpricing.models import PeriodLock
        db.session.add(PeriodLock(period="2026-01", locked=True))
        db.session.commit()

    response = _client().post(
        "/api/products/apply-year-effective",
        json={"year": 2026},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert response.status_code == 423
