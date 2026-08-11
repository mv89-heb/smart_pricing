"""Production entrypoint and performance layer for Smart Pricing.

This module keeps the existing application architecture intact while adding
safe runtime optimizations that do not change business rules.
"""
from functools import wraps

from sqlalchemy import text
from sqlalchemy.orm import selectinload

import app as app_module

app = app_module.app

db = app_module.db
Product = app_module.Product
PriceHistory = app_module.PriceHistory
DailyEntry = app_module.DailyEntry
BillingTemplate = app_module.BillingTemplate
PeriodLock = app_module.PeriodLock
ActivityLog = app_module.ActivityLog


def _install_indexes():
    """Create the indexes used by the hottest application queries.

    IF NOT EXISTS makes this safe to run on every worker boot and preserves
    compatibility with both PostgreSQL and SQLite.
    """
    statements = (
        "CREATE INDEX IF NOT EXISTS ix_daily_entry_date_id ON daily_entry (date, id)",
        "CREATE INDEX IF NOT EXISTS ix_daily_entry_date_product_extra ON daily_entry (date, product_name, is_extra)",
        "CREATE INDEX IF NOT EXISTS ix_price_history_product_effective_id ON price_history (product_id, effective_from, id)",
        "CREATE INDEX IF NOT EXISTS ix_period_lock_month_locked ON period_lock (year_month, locked)",
        "CREATE INDEX IF NOT EXISTS ix_activity_log_timestamp ON activity_log (timestamp)",
        "CREATE INDEX IF NOT EXISTS ix_template_item_product_name ON billing_template_item (product_name)",
    )
    with app.app_context():
        for statement in statements:
            try:
                db.session.execute(text(statement))
                db.session.commit()
            except Exception:
                db.session.rollback()


def _fast_price_for_date(product, iso_date):
    """Return the latest effective price with one indexed query.

    The previous implementation loaded the complete price history for a
    product into Python and filtered it there. That becomes increasingly
    expensive as price history grows.
    """
    row = (
        PriceHistory.query
        .filter(
            PriceHistory.product_id == product.id,
            PriceHistory.effective_from.isnot(None),
            PriceHistory.effective_from <= iso_date,
        )
        .order_by(PriceHistory.effective_from.desc(), PriceHistory.id.desc())
        .first()
    )
    return app_module.money(row.price if row is not None else product.price)


def _fast_product_details():
    """Load all products and their next scheduled price without N+1 queries."""
    today = app_module.today_iso()
    products = Product.query.order_by(Product.name.asc()).all()
    if not products:
        return app_module.jsonify([])

    product_ids = [p.id for p in products]
    scheduled = (
        PriceHistory.query
        .filter(
            PriceHistory.product_id.in_(product_ids),
            PriceHistory.effective_from.isnot(None),
            PriceHistory.effective_from > today,
        )
        .order_by(PriceHistory.effective_from.asc(), PriceHistory.id.asc())
        .all()
    )
    next_by_product = {}
    for row in scheduled:
        next_by_product.setdefault(row.product_id, row)

    payload = []
    for product in products:
        row = next_by_product.get(product.id)
        payload.append({
            "id": product.id,
            "name": product.name,
            "price": float(product.price or 0),
            "tag": product.tag or "",
            "scheduled_price": (
                {
                    "id": row.id,
                    "price": float(row.price),
                    "effective_from": row.effective_from,
                    "changed_at": row.changed_at.isoformat(),
                    "changed_by": row.changed_by,
                    "scheduled": True,
                }
                if row else None
            ),
        })
    return app_module.jsonify(payload)


def _fast_templates():
    """Avoid one SQL query per template when reading template items."""
    templates = (
        BillingTemplate.query
        .options(selectinload(BillingTemplate.items))
        .order_by(BillingTemplate.name.asc())
        .all()
    )
    return app_module.jsonify({
        template.name: [
            {
                "product_name": item.product_name,
                "quantity": item.quantity,
                "is_extra": bool(item.is_extra),
            }
            for item in template.items
        ]
        for template in templates
    })


def _fast_period_report():
    """Keep the report response identical while reducing lock queries from N+1 to 1."""
    request = app_module.request
    start = (request.args.get("from") or "").strip()
    end = (request.args.get("to") or "").strip()
    if not app_module.valid_date(start) or not app_module.valid_date(end) or start > end:
        return app_module.jsonify({"error": "טווח תאריכים לא תקין"}), 400

    entries = (
        DailyEntry.query
        .filter(DailyEntry.date >= start, DailyEntry.date <= end)
        .order_by(DailyEntry.date.asc(), DailyEntry.id.asc())
        .all()
    )
    payload = app_module.build_report(entries, start, end)

    months = sorted({entry.date[:7] for entry in entries})
    locked_months = set()
    if months:
        locked_months = {
            row.year_month
            for row in PeriodLock.query
            .filter(PeriodLock.year_month.in_(months), PeriodLock.locked.is_(True))
            .all()
        }
    payload["locked_months"] = {month: month in locked_months for month in months}
    payload["fully_locked"] = bool(months) and len(locked_months) == len(months)
    return app_module.jsonify(payload)


# Patch only the hot functions. Business logic and URLs remain unchanged.
app_module.price_for_date = _fast_price_for_date
app.view_functions["get_product_details"] = _fast_product_details
app.view_functions["get_templates"] = _fast_templates
app.view_functions["get_period_report"] = _fast_period_report

_install_indexes()
