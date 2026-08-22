"""Small stateless helpers shared across services and routes.

These are unchanged in behavior from the original app.py - only consolidated
into one place instead of being duplicated in app.py / api_routes.py / wsgi.py.
"""
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP


def money(value):
    return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def valid_date(value):
    if not isinstance(value, str) or len(value) != 10:
        return False
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def valid_month(value):
    if not isinstance(value, str) or len(value) != 7 or value[4] != "-":
        return False
    try:
        datetime.strptime(value, "%Y-%m")
        return True
    except ValueError:
        return False


def today_iso():
    return datetime.utcnow().strftime("%Y-%m-%d")


def entry_total(entry):
    if entry.total_amount is not None:
        return money(entry.total_amount)
    return (money(entry.quantity) * money(entry.unit_price)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def entry_json(entry):
    return {
        "id": entry.id,
        "date": entry.date,
        "product_name": entry.product_name,
        "quantity": entry.quantity,
        "is_extra": bool(entry.is_extra),
        "unit_price": float(entry.unit_price or 0),
        "total_amount": float(entry_total(entry)),
        "note": entry.note,
    }
