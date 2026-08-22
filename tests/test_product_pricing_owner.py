import os
import tempfile

DB_FILE = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
DB_FILE.close()
os.environ["DATABASE_URL"] = f"sqlite:///{DB_FILE.name}"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["FLASK_ENV"] = "development"

from app import app, db, PriceHistory, Product  # noqa: E402
from smartpricing.routes.products import _upsert_price_history  # noqa: E402


def setup_function(_):
    with app.app_context():
        db.drop_all()
        db.create_all()


def test_price_history_upsert_has_single_row_per_effective_date():
    with app.app_context():
        product = Product(name="בדיקת owner", price=10, tag=None)
        db.session.add(product)
        db.session.flush()

        first = _upsert_price_history(product, 10, "2026-08-22", "test")
        db.session.flush()
        second = _upsert_price_history(product, 12, "2026-08-22", "test-2")
        db.session.commit()

        assert first.id == second.id
        rows = PriceHistory.query.filter_by(product_id=product.id, effective_from="2026-08-22").all()
        assert len(rows) == 1
        assert float(rows[0].price) == 12
        assert rows[0].changed_by == "test-2"


def test_product_route_module_has_one_price_history_writer():
    source = open("smartpricing/routes/products.py", encoding="utf-8").read()
    assert source.count("PriceHistory(") == 1
    assert source.count("PriceHistory.query.filter_by(product_id=product.id, effective_from=effective)") == 1
