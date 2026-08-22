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
            .order_by(DailyEntry.id.asc()).first()
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


@bp.post("/api/entries/copy")
def copy_entries():
    """Copy a whole day in one request/transaction instead of one HTTP request per row."""
    denied = write_access()
    if denied:
        return denied
    data = request.get_json(silent=True) or {}
    source_date = str(data.get("source_date") or "").strip()
    target_date = str(data.get("target_date") or "").strip()
    if not valid_date(source_date) or not valid_date(target_date):
        return jsonify({"success": False, "error": "תאריך לא תקין"}), 400
    if is_locked(target_date):
        return jsonify({"success": False, "error": "תקופת היעד נעולה"}), 423
    source = DailyEntry.query.filter_by(date=source_date).order_by(DailyEntry.id.asc()).all()
    if not source:
        return jsonify({"success": True, "copied": 0})

    names = {e.product_name for e in source}
    products = {p.name: p for p in Product.query.filter(Product.name.in_(names)).all()}
    if len(products) != len(names):
        missing = sorted(names - products.keys())
        return jsonify({"success": False, "error": f"מוצרים חסרים: {', '.join(missing)}"}), 409

    try:
        existing_rows = DailyEntry.query.filter_by(date=target_date).all()
        existing = {(e.product_name, bool(e.is_extra)): e for e in existing_rows}
        prices = {name: price_for_date(product, target_date) for name, product in products.items()}
        copied = 0
        for src in source:
            key = (src.product_name, bool(src.is_extra))
            dst = existing.get(key)
            if dst is not None:
                dst.quantity = float(dst.quantity or 0) + float(src.quantity or 0)
                dst.total_amount = (money(dst.quantity) * money(dst.unit_price)).quantize(Decimal("0.01"))
                if src.note:
                    dst.note = src.note
            else:
                unit_price = prices[src.product_name]
                dst = DailyEntry(
                    date=target_date,
                    product_name=src.product_name,
                    quantity=float(src.quantity or 0),
                    is_extra=bool(src.is_extra),
                    unit_price=unit_price,
                    total_amount=(money(src.quantity) * unit_price).quantize(Decimal("0.01")),
                    note=src.note,
                )
                db.session.add(dst)
                existing[key] = dst
            copied += 1
        db.session.commit()
        log_activity("COPY_DAY", f"הועתקו {copied} חיובים מ-{source_date} ל-{target_date}")
        return jsonify({"success": True, "copied": copied})
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
