"""Compatibility endpoints retained from the legacy WSGI layer.

These routes are intentionally small adapters around canonical services. They
preserve older frontend/integration URLs without restoring the legacy runtime
monkey-patching that previously lived in ``wsgi_patched.py``.
"""
from datetime import datetime, timezone

from flask import jsonify

import app as base
from services.reporting import period_report

app = base.app
DailyEntry = base.DailyEntry
Product = base.Product
PeriodLock = base.PeriodLock


@app.get("/api/report/all")
def report_all():
    """Return all stored billing history using the canonical report shape."""
    entries = DailyEntry.query.order_by(DailyEntry.date.asc(), DailyEntry.id.asc()).all()
    if not entries:
        return jsonify(period_report(base, "1970-01-01", "1970-01-01"))
    return jsonify(period_report(base, entries[0].date, entries[-1].date))


@app.get("/api/data-health")
def data_health():
    """Return a non-sensitive summary of whether billing data exists."""
    try:
        entries_count = DailyEntry.query.count()
        products_count = Product.query.count()
        first_entry = DailyEntry.query.order_by(DailyEntry.date.asc(), DailyEntry.id.asc()).first()
        last_entry = DailyEntry.query.order_by(DailyEntry.date.desc(), DailyEntry.id.desc()).first()
        return jsonify({
            "entries_count": entries_count,
            "products_count": products_count,
            "first_entry_date": first_entry.date if first_entry else None,
            "last_entry_date": last_entry.date if last_entry else None,
            "data_present": entries_count > 0 or products_count > 0,
        })
    except Exception:
        return jsonify({"error": "נתוני המערכת אינם זמינים"}), 503


def _period_lock_payload(year_month):
    row = PeriodLock.query.filter_by(year_month=year_month).first()
    return {
        "year_month": year_month,
        "locked": bool(row and row.locked),
        "locked_at": row.locked_at.isoformat() if row and row.locked_at else None,
    }


# Legacy dashboard compatibility: the existing dashboard uses /api/period-locks/*.
# The canonical API uses /api/periods/*; these adapters preserve the existing UI
# contract while delegating to the same PeriodLock model and write policy.
@app.get("/api/period-locks/<string:year_month>")
def legacy_period_lock_status(year_month):
    if not base.valid_month(year_month):
        return jsonify({"error": "חודש לא תקין"}), 400
    return jsonify(_period_lock_payload(year_month))


@app.post("/api/period-locks/<string:year_month>")
def legacy_period_lock_lock(year_month):
    denied = base.write_access()
    if denied:
        return denied
    if not base.valid_month(year_month):
        return jsonify({"success": False, "error": "חודש לא תקין"}), 400
    row = PeriodLock.query.filter_by(year_month=year_month).first()
    now = datetime.now(timezone.utc)
    if row is None:
        row = PeriodLock(year_month=year_month, locked=True, locked_at=now, locked_by="מערכת")
        base.db.session.add(row)
    else:
        row.locked = True
        row.locked_at = now
        row.locked_by = "מערכת"
    base.db.session.commit()
    return jsonify({"success": True, "year_month": year_month, "locked": True})


@app.delete("/api/period-locks/<string:year_month>")
def legacy_period_lock_unlock(year_month):
    denied = base.write_access()
    if denied:
        return denied
    if not base.valid_month(year_month):
        return jsonify({"success": False, "error": "חודש לא תקין"}), 400
    row = PeriodLock.query.filter_by(year_month=year_month).first()
    if row is None:
        row = PeriodLock(year_month=year_month, locked=False)
        base.db.session.add(row)
    else:
        row.locked = False
    base.db.session.commit()
    return jsonify({"success": True, "year_month": year_month, "locked": False})
