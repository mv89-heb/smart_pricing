"""Canonical report engine with lightweight summary mode."""
from decimal import Decimal

from sqlalchemy import case, func

from ..extensions import db
from ..models import DailyEntry, PeriodLock
from ..utils import entry_json, money, valid_date


def _empty_report(start=None, end=None):
    return {
        "from": start,
        "to": end,
        "entries": [],
        "summary": {
            "regular_total": 0.0,
            "extra_total": 0.0,
            "grand_total": 0.0,
            "days_count": 0,
            "average_day": 0.0,
        },
        "product_summary": {},
        "day_summary": {},
        "locked_months": {},
        "fully_locked": False,
    }


def _lock_payload(month_keys):
    locked = (
        {row.year_month for row in PeriodLock.query.filter(
            PeriodLock.year_month.in_(month_keys), PeriodLock.locked.is_(True)
        ).all()}
        if month_keys else set()
    )
    return {m: m in locked for m in month_keys}, bool(month_keys) and len(locked) == len(month_keys)


def _build_summary_sql(start, end):
    """Aggregate dashboard/report KPIs in SQL without materializing entries."""
    amount = func.coalesce(DailyEntry.quantity, 0) * func.coalesce(DailyEntry.unit_price, 0)
    regular_expr = case((DailyEntry.is_extra.is_(False), amount), else_=0)
    extra_expr = case((DailyEntry.is_extra.is_(True), amount), else_=0)

    totals = db.session.query(
        func.coalesce(func.sum(regular_expr), 0),
        func.coalesce(func.sum(extra_expr), 0),
        func.count(func.distinct(DailyEntry.date)),
    ).filter(DailyEntry.date >= start, DailyEntry.date <= end).first()
    regular = float(totals[0] or 0)
    extra = float(totals[1] or 0)
    days_count = int(totals[2] or 0)

    product_rows = db.session.query(
        DailyEntry.product_name,
        func.coalesce(func.sum(DailyEntry.quantity), 0),
        func.coalesce(func.sum(amount), 0),
    ).filter(
        DailyEntry.date >= start, DailyEntry.date <= end
    ).group_by(DailyEntry.product_name).order_by(DailyEntry.product_name.asc()).all()
    products = {
        name: {"quantity": float(quantity or 0), "total": float(total or 0)}
        for name, quantity, total in product_rows
    }

    day_rows = db.session.query(
        DailyEntry.date,
        func.coalesce(func.sum(regular_expr), 0),
        func.coalesce(func.sum(extra_expr), 0),
    ).filter(
        DailyEntry.date >= start, DailyEntry.date <= end
    ).group_by(DailyEntry.date).order_by(DailyEntry.date.asc()).all()
    days = {
        date: {
            "regular": float(reg or 0),
            "extra": float(ext or 0),
            "total": float((reg or 0) + (ext or 0)),
        }
        for date, reg, ext in day_rows
    }

    month_keys = sorted({date[:7] for date in days})
    locked_months, fully_locked = _lock_payload(month_keys)
    grand = regular + extra
    return {
        "from": start,
        "to": end,
        "entries": [],
        "summary": {
            "regular_total": regular,
            "extra_total": extra,
            "grand_total": grand,
            "days_count": days_count,
            "average_day": grand / days_count if days_count else 0.0,
        },
        "product_summary": products,
        "day_summary": days,
        "locked_months": locked_months,
        "fully_locked": fully_locked,
    }


def build_period_report(start, end, include_entries=True):
    """Build one consistent report for a date range.

    Dashboard/compare callers use ``include_entries=False`` and receive a
    SQL-aggregated result. The full report still returns the individual rows
    needed for editing/export.
    """
    if not include_entries:
        return _build_summary_sql(start, end)

    entries = (
        DailyEntry.query
        .filter(DailyEntry.date >= start, DailyEntry.date <= end)
        .order_by(DailyEntry.date.asc(), DailyEntry.id.asc())
        .all()
    )
    if not entries:
        return _empty_report(start, end)

    regular = extra = 0.0
    products = {}
    days = {}
    payload_entries = []
    for entry in entries:
        amount = (money(entry.quantity) * money(entry.unit_price)).quantize(Decimal("0.01"))
        amount_f = float(amount)
        if entry.is_extra:
            extra += amount_f
        else:
            regular += amount_f
        product = products.setdefault(entry.product_name, {"quantity": 0.0, "total": 0.0})
        product["quantity"] += float(entry.quantity or 0)
        product["total"] += amount_f
        day = days.setdefault(entry.date, {"regular": 0.0, "extra": 0.0, "total": 0.0})
        day["extra" if entry.is_extra else "regular"] += amount_f
        day["total"] += amount_f
        payload_entries.append(entry_json(entry))

    month_keys = sorted({e.date[:7] for e in entries})
    locked_months, fully_locked = _lock_payload(month_keys)
    grand = regular + extra
    return {
        "from": start,
        "to": end,
        "entries": payload_entries,
        "summary": {
            "regular_total": regular,
            "extra_total": extra,
            "grand_total": grand,
            "days_count": len(days),
            "average_day": grand / len(days) if days else 0.0,
        },
        "product_summary": products,
        "day_summary": days,
        "locked_months": locked_months,
        "fully_locked": fully_locked,
    }


def build_full_history_report():
    """Report over every stored entry (used by the all-data view)."""
    first_date, last_date = db.session.query(
        db.func.min(DailyEntry.date), db.func.max(DailyEntry.date)
    ).first()
    if not first_date or not last_date:
        return _empty_report()
    return build_period_report(first_date, last_date, include_entries=True)


def compare_periods(a_from, a_to, b_from, b_to):
    a = build_period_report(a_from, a_to, include_entries=False)["summary"]
    b = build_period_report(b_from, b_to, include_entries=False)["summary"]

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


def valid_range(start, end):
    return valid_date(start) and valid_date(end) and start <= end
