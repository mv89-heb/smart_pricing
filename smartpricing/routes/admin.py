from flask import Blueprint, jsonify

from ..extensions import db
from ..models import ActivityLog, BillingTemplate, DailyEntry, PeriodLock, PriceHistory, Product
from ..security import admin_access, log_activity, write_access
from ..services.periods import is_locked
from ..utils import entry_json, valid_date

bp = Blueprint("admin", __name__)


@bp.get("/api/logs")
def get_logs():
    denied = admin_access()
    if denied:
        return denied
    rows = ActivityLog.query.order_by(ActivityLog.timestamp.desc()).limit(200).all()
    return jsonify([
        {"time": row.timestamp.isoformat() if row.timestamp else None, "user": row.username, "action": row.action, "details": row.details}
        for row in rows
    ])


@bp.get("/api/backup")
def download_backup():
    """Return a complete data export without password hashes."""
    denied = admin_access()
    if denied:
        return denied
    from datetime import datetime, timezone

    products = Product.query.order_by(Product.name.asc()).all()
    return jsonify({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "products": [{"id": p.id, "name": p.name, "price": float(p.price or 0), "tag": p.tag or ""} for p in products],
        "price_history": [
            {"id": r.id, "product_id": r.product_id, "price": float(r.price), "effective_from": r.effective_from, "changed_at": r.changed_at.isoformat(), "changed_by": r.changed_by}
            for r in PriceHistory.query.order_by(PriceHistory.product_id.asc(), PriceHistory.id.asc()).all()
        ],
        "daily_entries": [entry_json(e) for e in DailyEntry.query.order_by(DailyEntry.date.asc(), DailyEntry.id.asc()).all()],
        "period_locks": [{"year_month": r.year_month, "locked": r.locked} for r in PeriodLock.query.order_by(PeriodLock.year_month.asc()).all()],
        "templates": {
            t.name: [{"product_name": i.product_name, "quantity": i.quantity, "is_extra": bool(i.is_extra)} for i in t.items]
            for t in BillingTemplate.query.order_by(BillingTemplate.name.asc()).all()
        },
    })


@bp.route("/api/bulk/entries/<string:date_value>", methods=["DELETE"])
def clear_day(date_value):
    denied = write_access()
    if denied:
        return denied
    if not valid_date(date_value):
        return jsonify({"success": False, "error": "תאריך לא תקין"}), 400
    if is_locked(date_value):
        return jsonify({"success": False, "error": "התקופה נעולה"}), 423
    try:
        count = DailyEntry.query.filter_by(date=date_value).delete()
        db.session.commit()
        if count:
            log_activity("BULK_CLEAR_DAY", f"נמחקו {count} חיובים לתאריך {date_value}")
        return jsonify({"success": True, "deleted": count})
    except Exception:
        db.session.rollback()
        return jsonify({"success": False, "error": "שגיאת שרת"}), 500


@bp.route("/api/bulk/season", methods=["DELETE"])
def reset_season():
    """Clear operational billing data while retaining configuration/master data."""
    denied = admin_access()
    if denied:
        return denied
    try:
        entries_count = DailyEntry.query.delete()
        locks_count = PeriodLock.query.delete()
        db.session.commit()
        log_activity("SEASON_RESET", f"איפוס עונה: נמחקו {entries_count} חיובים ו-{locks_count} נעילות תקופה")
        return jsonify({"success": True, "deleted_entries": entries_count, "deleted_locks": locks_count})
    except Exception:
        db.session.rollback()
        return jsonify({"success": False, "error": "שגיאת שרת"}), 500
