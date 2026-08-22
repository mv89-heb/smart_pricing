"""Canonical report engine.

BUG FIX: previously the dashboard endpoints (/api/dashboard/summary,
/api/dashboard/compare) and the periodic report endpoint (/api/report/period)
used two different implementations that could disagree:

- api_routes.py registered a plain implementation for all four routes.
- wsgi.py *tried* to install faster replacements via app.add_url_rule() with
  new endpoint names for the two dashboard routes, but Flask/Werkzeug always
  matches the first-registered rule for an identical URL+method, so those
  replacements were silently dead code - confirmed by testing the running
  app. The result: /api/report/period returned locked_months/fully_locked
  (because wsgi.py overrode that endpoint's *view function* in place, which
  does work), while /api/dashboard/summary never did (because it used
  add_url_rule instead), even though both screens are meant to reflect the
  same period-lock state.

Both endpoints now call the exact same build_period_report() function below,
so the dashboard and the periodic report can never again disagree about what
a given date range contains.
"""
from decimal import Decimal

from ..extensions import db
from ..models import DailyEntry, PeriodLock
from ..utils import entry_json, money, valid_date


def build_period_report(start, end):
    entries = (
        DailyEntry.query.filter(DailyEntry.date >= start, DailyEntry.date <= end)
        .order_by(DailyEntry.date.asc(), DailyEntry.id.asc())
        .all()
    )
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

    grand = regular + extra
    months = sorted({e.date[:7] for e in entries})
    locked = (
        {row.year_month for row in PeriodLock.query.filter(PeriodLock.year_month.in_(months), PeriodLock.locked.is_(True)).all()}
        if months
        else set()
    )
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
        "locked_months": {m: m in locked for m in months},
        "fully_locked": bool(months) and len(locked) == len(months),
    }


def build_full_history_report():
    """Report over every stored entry (used by the 'all data' view)."""
    first_date, last_date = db.session.query(db.func.min(DailyEntry.date), db.func.max(DailyEntry.date)).first()
    if not first_date or not last_date:
        return {
            "from": None, "to": None, "entries": [],
            "summary": {"regular_total": 0.0, "extra_total": 0.0, "grand_total": 0.0, "days_count": 0, "average_day": 0.0},
            "product_summary": {}, "day_summary": {}, "locked_months": {}, "fully_locked": False,
        }
    return build_period_report(first_date, last_date)


def compare_periods(a_from, a_to, b_from, b_to):
    a = build_period_report(a_from, a_to)["summary"]
    b = build_period_report(b_from, b_to)["summary"]

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
