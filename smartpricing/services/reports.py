"""Canonical report engine with lightweight summary mode."""
from decimal import Decimal

from ..extensions import db
from ..models import DailyEntry, PeriodLock
from ..utils import entry_json, money, valid_date


def build_period_report(start, end, include_entries=True):
    """Build one consistent report for a date range.

    ``include_entries=False`` is used by dashboard/compare endpoints so they
    do not serialize every billing row just to calculate KPIs and charts.
    """
    query = (
        DailyEntry.query
        .filter(DailyEntry.date >= start, DailyEntry.date <= end)
        .order_by(DailyEntry.date.asc(), DailyEntry.id.asc())
    )
    entries = query.all()

    regular = extra = 0.0
    products = {}
    days = {}
    payload_entries = [] if include_entries else None

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

        if include_entries:
            payload_entries.append(entry_json(entry))

    grand = regular + extra
    months = sorted(days.keys())
    month_keys = sorted({d[:7] for d in months})
    locked = (
        {row.year_month for row in PeriodLock.query.filter(
            PeriodLock.year_month.in_(month_keys), PeriodLock.locked.is_(True)
        ).all()}
        if month_keys else set()
    )

    return {
        "from": start,
        "to": end,
        "entries": payload_entries if include_entries else [],
        "summary": {
            "regular_total": regular,
            "extra_total": extra,
            "grand_total": grand,
            "days_count": len(days),
            "average_day": grand / len(days) if days else 0.0,
        },
        "product_summary": products,
        "day_summary": days,
        "locked_months": {m: m in locked for m in month_keys},
        "fully_locked": bool(month_keys) and len(locked) == len(month_keys),
    }


def build_full_history_report():
    """Report over every stored entry (used by the all-data view)."""
    first_date, last_date = db.session.query(
        db.func.min(DailyEntry.date), db.func.max(DailyEntry.date)
    ).first()
    if not first_date or not last_date:
        return {
            "from": None, "to": None, "entries": [],
            "summary": {"regular_total": 0.0, "extra_total": 0.0, "grand_total": 0.0, "days_count": 0, "average_day": 0.0},
            "product_summary": {}, "day_summary": {}, "locked_months": {}, "fully_locked": False,
        }
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
