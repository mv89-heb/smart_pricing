from datetime import date
from decimal import Decimal
from sqlalchemy import select
from ..extensions import db
from ..models import PriceHistory, Product


def effective_price(product_id: int, target_date: date):
    value = db.session.scalar(select(PriceHistory.price).where(PriceHistory.product_id == product_id, PriceHistory.effective_date <= target_date).order_by(PriceHistory.effective_date.desc()).limit(1))
    if value is not None:
        return Decimal(value)
    value = db.session.scalar(select(Product.current_price).where(Product.id == product_id))
    return Decimal(value or 0)


def set_price(product, price, effective_date, changed_by):
    price = Decimal(str(price)).quantize(Decimal("0.01"))
    row = db.session.scalar(select(PriceHistory).where(PriceHistory.product_id == product.id, PriceHistory.effective_date == effective_date))
    if row:
        row.price = price
        row.changed_by = changed_by
    else:
        db.session.add(PriceHistory(product_id=product.id, price=price, effective_date=effective_date, changed_by=changed_by))
    if effective_date <= date.today():
        product.current_price = price
