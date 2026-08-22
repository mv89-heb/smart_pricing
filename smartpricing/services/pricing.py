"""Canonical price lookups.

All price-by-date decisions live here so daily billing, reports, scheduling,
and dashboard code use exactly the same historical-price semantics.
"""
from ..models import PriceHistory
from ..utils import money, today_iso


def price_for_date(product, iso_date):
    """Return the price effective on ``iso_date`` with an indexed DB lookup.

    If the requested date predates the first known history row, the earliest
    known price is retained for backward compatibility. If no history exists,
    the product's current price is used.
    """
    candidate = (
        PriceHistory.query
        .filter(
            PriceHistory.product_id == product.id,
            PriceHistory.effective_from.isnot(None),
            PriceHistory.effective_from <= iso_date,
        )
        .order_by(PriceHistory.effective_from.desc(), PriceHistory.id.desc())
        .first()
    )
    if candidate is not None:
        return money(candidate.price)

    earliest = (
        PriceHistory.query
        .filter(
            PriceHistory.product_id == product.id,
            PriceHistory.effective_from.isnot(None),
        )
        .order_by(PriceHistory.effective_from.asc(), PriceHistory.id.asc())
        .first()
    )
    if earliest is not None:
        return money(earliest.price)

    return money(product.price)


def price_history_json(product):
    today = today_iso()
    rows = (
        PriceHistory.query.filter_by(product_id=product.id)
        .order_by(PriceHistory.effective_from.desc(), PriceHistory.id.desc())
        .all()
    )
    return [
        {
            "id": r.id,
            "price": float(r.price),
            "effective_from": r.effective_from,
            "changed_at": r.changed_at.isoformat(),
            "changed_by": r.changed_by,
            "scheduled": bool(r.effective_from and r.effective_from > today),
        }
        for r in rows
    ]
