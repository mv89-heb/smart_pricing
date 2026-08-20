from datetime import datetime


def test_price_for_date_uses_effective_history(app, db):
    product = app.Product(name='בדיקת מחיר היסטורי', price=20, tag=None)
    db.session.add(product)
    db.session.flush()
    db.session.add_all([
        app.PriceHistory(product_id=product.id, price=10, effective_from='2026-01-01', changed_by='test'),
        app.PriceHistory(product_id=product.id, price=20, effective_from='2026-08-01', changed_by='test'),
    ])
    db.session.commit()
    assert app.price_for_date(product, '2026-03-01') == app.money(10)
    assert app.price_for_date(product, '2026-08-20') == app.money(20)
    assert app.price_for_date(product, '2025-12-31') == app.money(10)
