from decimal import Decimal

from flask import Blueprint, jsonify, request
from sqlalchemy.exc import SQLAlchemyError

from ..extensions import db
from ..models import DailyEntry, Product
from ..security import log_activity, write_access
from ..services.periods import is_locked
from ..services.pricing import price_for_date
from ..utils import entry_json, money, valid_date

bp = Blueprint("entries", __name__)


@bp.post("/api/entries")
def create_entry():
    denied = write_access()
    if denied:
        return denied
    data = request.get_json(silent=True) or {}
    date_value = str(data.get("date") or "").strip()
    name = str(data.get("product_name") or "").strip()
    if not valid_date(date_value) or not name:
        return jsonify({"success": False, "error": "נתונים שגויים"}), 400
    if is_locked(date_value):
        return jsonify({"success": False, "error": "התקופה נעולה"}), 423
    product = Product.query.filter_by(name=name).first()
    if not product:
        return jsonify({"success": False, "error": "מוצר לא נמצא"}), 404
    try:
        quantity = float(data.get("quantity"))
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "כמות לא תקינה"}), 400
    if quantity <= 0:
        return jsonify({"success": False, "error": "כמות חייבת להיות חיובית"}), 400
    is_extra = bool(data.get("is_extra", False))
    selected_price = price_for_date(product, date_value)
    note = str(data.get("note") or "").strip()[:255] or None
    try:
        existing = (
            DailyEntry.query.filter_by(date=date_value, product_name=product.name, is_extra=is_extra)
            .order_by(DailyEntry.id.asc())
            .first()
        )
        if existing is not None:
            effective_price = money(existing.unit_price)
            existing.quantity = float(existing.quantity or 0) + quantity
            existing.total_amount = (money(existing.quantity) * effective_price).quantize(Decimal("0.01"))
            if note:
                existing.note = note
            db.session.commit()
            return jsonify(entry_json(existing))
        entry = DailyEntry(
            date=date_value, product_name=product.name, quantity=quantity, is_extra=is_extra,
            unit_price=selected_price, total_amount=(money(quantity) * selected_price).quantize(Decimal("0.01")), note=note,
        )
        db.session.add(entry)
        db.session.commit()
        return jsonify(entry_json(entry))
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"success": False, "error": "שגיאת שרת"}), 500


@bp.get("/api/entries/<string:date_value>")
def get_entries(date_value):
    if not valid_date(date_value):
        return jsonify({"error": "תאריך לא תקין"}), 400
    return jsonify([entry_json(row) for row in DailyEntry.query.filter_by(date=date_value).order_by(DailyEntry.id.asc()).all()])


@bp.route("/api/entries/<int:entry_id>", methods=["PUT"])
def update_entry(entry_id):
    """Previously missing - the main screen and the periodic report screen
    both call PUT /api/entries/<id> to edit a quantity, but no such route
    existed, so editing an entry from either screen silently failed.

    The periodic report screen's edit dialog also sends `note` and `is_extra`
    in the same request (see static/periodic_report.html saveEdit()) - both
    are accepted here too, as optional fields, so that screen's edit dialog
    isn't silently dropping half of what it submits."""
    denied = write_access()
    if denied:
        return denied
    entry = db.session.get(DailyEntry, entry_id)
    if not entry:
        return jsonify({"success": False, "error": "חיוב לא נמצא"}), 404
    if is_locked(entry.date):
        return jsonify({"success": False, "error": "התקופה נעולה"}), 423
    data = request.get_json(silent=True) or {}
    try:
        quantity = float(data.get("quantity"))
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "כמות לא תקינה"}), 400
    if quantity <= 0:
        return jsonify({"success": False, "error": "כמות חייבת להיות חיובית"}), 400
    try:
        entry.quantity = quantity
        entry.total_amount = (money(quantity) * money(entry.unit_price)).quantize(Decimal("0.01"))
        if "note" in data:
            entry.note = (str(data.get("note") or "").strip()[:255]) or None
        if "is_extra" in data:
            entry.is_extra = bool(data.get("is_extra"))
        db.session.commit()
        log_activity("UPDATE_ENTRY", f"עדכון חיוב #{entry.id}: {entry.product_name}, כמות {quantity}")
        return jsonify(entry_json(entry))
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"success": False, "error": "שגיאת שרת"}), 500


@bp.route("/api/entries/<int:entry_id>", methods=["DELETE"])
def delete_entry(entry_id):
    """Previously missing - see update_entry above; deleting a single entry
    from either screen silently failed with no backend route to handle it."""
    denied = write_access()
    if denied:
        return denied
    entry = db.session.get(DailyEntry, entry_id)
    if not entry:
        return jsonify({"success": False, "error": "חיוב לא נמצא"}), 404
    if is_locked(entry.date):
        return jsonify({"success": False, "error": "התקופה נעולה"}), 423
    try:
        product_name = entry.product_name
        db.session.delete(entry)
        db.session.commit()
        log_activity("DELETE_ENTRY", f"מחיקת חיוב #{entry_id}: {product_name}")
        return jsonify({"success": True})
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"success": False, "error": "שגיאת שרת"}), 500
