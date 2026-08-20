"""Compatibility endpoints retained from the legacy WSGI layer.

These routes are intentionally small adapters around the canonical reporting
service. Keeping them here preserves old integrations without restoring the
legacy runtime monkey-patching that previously lived in ``wsgi_patched.py``.
"""
from flask import jsonify

import app as base
from services.reporting import period_report

app = base.app
DailyEntry = base.DailyEntry
Product = base.Product


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
    entries_count = db_count = None
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
