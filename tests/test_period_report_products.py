"""Regression tests for products appearing in a selected period."""
from datetime import datetime


def test_product_added_inside_period_is_visible_without_entry():
    from period_report import _products_to_zero_rows
    products = [type("P", (), {"id": 7, "name": "בננות", "price": 12.5,
                                "created_at": datetime(2026, 8, 20, 10, 0)})()]
    rows = _products_to_zero_rows(products, "2026-08-01", "2026-08-24", set())
    assert rows == [{
        "id": None, "product_id": 7, "date": "2026-08-20",
        "product_name": "בננות", "quantity": 0.0, "is_extra": False,
        "unit_price": 12.5, "total": 0.0,
    }]


def test_product_outside_period_is_not_added():
    from period_report import _products_to_zero_rows
    products = [type("P", (), {"id": 8, "name": "מוצר עתידי", "price": 5,
                                "created_at": datetime(2026, 9, 1)})()]
    assert _products_to_zero_rows(products, "2026-08-01", "2026-08-24", set()) == []


def test_product_with_existing_entry_is_not_duplicated():
    from period_report import _products_to_zero_rows
    products = [type("P", (), {"id": 9, "name": "אבוקדו", "price": 14,
                                "created_at": datetime(2026, 8, 10)})()]
    assert _products_to_zero_rows(products, "2026-08-01", "2026-08-24", {9}) == []
