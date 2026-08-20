"""Canonical reporting calculations used by the dashboard and period report.

The public response shape is intentionally compatible with the existing UI.
The summary aggregation is performed in SQL while detailed rows are fetched
only for the full period report.
"""
from sqlalchemy import case, func


def _amount_expr(DailyEntry):
    return func.coalesce(DailyEntry.quantity, 0) * func.coalesce(DailyEntry.unit_price, 0)


def _validate(base, start, end):
    if not base.valid_date(start) or not base.valid_date(end) or start > end:
        raise ValueError("טווח תאריכים לא תקין")


def period_summary(base, start, end):
    """Return the canonical aggregate summary for a date range."""
    _validate(base, start, end)
    DailyEntry = base.DailyEntry
    PeriodLock = base.PeriodLock
    query = DailyEntry.query.filter(DailyEntry.date >= start, DailyEntry.date <= end)
    amount = _amount_expr(DailyEntry)
    regular = case((DailyEntry.is_extra.is_(False), amount), else_=0)
    extra = case((DailyEntry.is_extra.is_(True), amount), else_=0)
    grand, regular_total, extra_total, days_count, quantity_total = query.with_entities(
        func.coalesce(func.sum(amount), 0),
        func.coalesce(func.sum(regular), 0),
        func.coalesce(func.sum(extra), 0),
        func.count(func.distinct(DailyEntry.date)),
        func.coalesce(func.sum(DailyEntry.quantity), 0),
    ).first()

    months = [month for month, in query.with_entities(func.substr(DailyEntry.date, 1, 7)).distinct().all()]
    locked = {
        row.year_month
        for row in PeriodLock.query.filter(
            PeriodLock.year_month.in_(months), PeriodLock.locked.is_(True)
        ).all()
    } if months else set()

    grand = float(grand or 0)
    days_count = int(days_count or 0)
    return {
        "from": start,
        "to": end,
        "summary": {
            "grand_total": grand,
            "regular_total": float(regular_total or 0),
            "extra_total": float(extra_total or 0),
            "days_count": days_count,
            "average_day": grand / days_count if days_count else 0.0,
            "quantity_total": float(quantity_total or 0),
        },
        "locked_months": {month: month in locked for month in sorted(months)},
        "fully_locked": bool(months) and len(locked) == len(months),
    }


def period_report(base, start, end):
    """Return full period report data in the existing API response shape."""
    payload = period_summary(base, start, end)
    DailyEntry = base.DailyEntry
    entries = (DailyEntry.query
               .filter(DailyEntry.date >= start, DailyEntry.date <= end)
               .order_by(DailyEntry.date.asc(), DailyEntry.id.asc()).all())
    products = {}
    days = {}
    payload_entries = []

    for entry in entries:
        amount = float((base.money(entry.quantity) * base.money(entry.unit_price)).quantize(base.Decimal("0.01")))
        product = products.setdefault(entry.product_name, {"quantity": 0.0, "total": 0.0})
        product["quantity"] += float(entry.quantity or 0)
        product["total"] += amount
        day = days.setdefault(entry.date, {"regular": 0.0, "extra": 0.0, "total": 0.0})
        day["extra" if entry.is_extra else "regular"] += amount
        day["total"] += amount
        payload_entries.append(base.entry_json(entry))

    payload["entries"] = payload_entries
    payload["product_summary"] = products
    payload["day_summary"] = days
    return payload


def compare_periods(base, a_from, a_to, b_from, b_to):
    """Compare two ranges while preserving the existing response contract."""
    a = period_summary(base, a_from, a_to)["summary"]
    b = period_summary(base, b_from, b_to)["summary"]

    def pct(old, new):
        return None if old == 0 else round((new - old) / old * 100, 2)

    return {
        "a": a,
        "b": b,
        "change": {
            "grand_total": pct(a["grand_total"], b["grand_total"]),
            "regular_total": pct(a["regular_total"], b["regular_total"]),
            "extra_total": pct(a["extra_total"], b["extra_total"]),
            "days_count": pct(a["days_count"], b["days_count"]),
        },
    }
