"""Canonical price lookups.

Previously price_for_date existed in THREE places:
- app.py / api_routes.py: fetch all history rows, fall back to the EARLIEST
  known history price if the requested date is before all of them (or to
  product.price only if there is no history at all).
- wsgi.py's "fast" replacement: a single indexed query that instead fell
  back straight to product.price whenever no row matched. That's a different,
  wrong answer for a date older than any recorded price change - but it never
  actually ran in production, because it patched `app` the *module* import,
  not `app.price_for_date` on the Flask *instance*, which is what
  api_routes.py sets and what every route actually calls. So the fast version
  was dead code with a latent bug in it.

This is the one implementation now, using the app.py/api_routes.py semantics
(the ones that were actually live, and that the existing regression test
tests/test_price_history_integrity.py depends on), written as a single
indexed query for efficiency.
"""
from ..models import PriceHistory
from ..utils import money, today_iso


def price_for_date(product, iso_date):
    rows = (
        PriceHistory.query.filter_by(product_id=product.id)
        .order_by(PriceHistory.effective_from.asc(), PriceHistory.id.asc())
        .all()
    )
    if not rows:
        return money(product.price)
    candidates = [row for row in rows if row.effective_from and row.effective_from <= iso_date]
    if candidates:
        return money(candidates[-1].price)
    return money(rows[0].price)


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
