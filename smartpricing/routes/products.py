from flask import Blueprint, jsonify, request
from sqlalchemy.exc import SQLAlchemyError

from ..extensions import db
from ..models import PriceHistory, Product
from ..security import log_activity, write_access
from ..services.periods import is_locked
from ..services.pricing import price_history_json
from ..utils import money, today_iso, valid_date

bp = Blueprint("products", __name__)


@bp.get("/api/products")
def get_products():
    return jsonify({p.name: float(p.price or 0) for p in Product.query.order_by(Product.name.asc()).all()})


@bp.get("/api/products/details")
def get_product_details():
    return jsonify([
        {
            "id": p.id,
            "name": p.name,
            "price": float(p.price or 0),
            "tag": p.tag or "",
            "scheduled_price": next((x for x in price_history_json(p) if x["scheduled"]), None),
        }
        for p in Product.query.order_by(Product.name.asc()).all()
    ])


@bp.get("/api/products/<path:product_name>/history")
def get_product_history(product_name):
    """Previously missing - static/price-scheduling.js calls this to work out
    which price was in effect on a given date while composing a new entry
    (effectivePrice()), and had no backend route to hit."""
    product = Product.query.filter_by(name=product_name).first()
    if not product:
        return jsonify({"error": "מוצר לא נמצא"}), 404
    return jsonify(price_history_json(product))


@bp.post("/api/products")
def add_product():
    denied = write_access()
    if denied:
        return denied
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    tag = (data.get("tag") or "").strip()[:80]
    try:
        price = money(data.get("price"))
    except Exception:
        return jsonify({"success": False, "error": "מחיר לא תקין"}), 400
    effective = (data.get("effective_from") or today_iso()).strip()
    if not name or price < 0 or not valid_date(effective):
        return jsonify({"success": False, "error": "נתונים שגויים"}), 400
    if effective > today_iso():
        return jsonify({"success": False, "error": "מוצר חדש חייב להתחיל במחיר תקף מהיום. ניתן לתזמן שינוי מחיר למוצר קיים."}), 400
    if Product.query.filter_by(name=name).first():
        return jsonify({"success": False, "error": "מוצר קיים"}), 409
    try:
        p = Product(name=name, price=price, tag=tag or None)
        db.session.add(p)
        db.session.flush()
        db.session.add(PriceHistory(product_id=p.id, price=price, effective_from=effective, changed_by=request.environ.get("REMOTE_USER") or "מערכת"))
        db.session.commit()
        log_activity("NEW_PRODUCT", f"מוצר חדש: {name}, מחיר {price}, תקף מ-{effective}")
        return jsonify({"success": True})
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"success": False, "error": "שגיאת שרת"}), 500


@bp.route("/api/products/<path:product_name>", methods=["PUT"])
def update_product(product_name):
    from datetime import datetime

    denied = write_access()
    if denied:
        return denied
    product = Product.query.filter_by(name=product_name).first()
    if not product:
        return jsonify({"success": False, "error": "מוצר לא נמצא"}), 404
    data = request.get_json(silent=True) or {}
    name = str(data.get("name") or product.name).strip()[:100]
    if not name:
        return jsonify({"success": False, "error": "שם מוצר לא תקין"}), 400
    try:
        price = money(data.get("price"))
    except Exception:
        return jsonify({"success": False, "error": "מחיר לא תקין"}), 400
    if price < 0:
        return jsonify({"success": False, "error": "מחיר לא תקין"}), 400
    effective = str(data.get("effective_from") or today_iso()).strip()
    if not valid_date(effective):
        return jsonify({"success": False, "error": "תאריך תוקף לא תקין"}), 400
    if name != product.name and Product.query.filter(Product.name == name, Product.id != product.id).first():
        return jsonify({"success": False, "error": "מוצר קיים"}), 409
    if is_locked(effective):
        return jsonify({"success": False, "error": "התקופה נעולה"}), 423
    try:
        old_name = product.name
        product.name = name
        existing = (
            PriceHistory.query.filter_by(product_id=product.id, effective_from=effective)
            .order_by(PriceHistory.id.desc())
            .first()
        )
        if existing:
            existing.price = price
            existing.changed_at = datetime.utcnow()
            existing.changed_by = request.environ.get("REMOTE_USER") or "מערכת"
        else:
            db.session.add(PriceHistory(product_id=product.id, price=price, effective_from=effective, changed_by="מערכת"))
        if effective <= today_iso():
            product.price = price
        db.session.commit()
        log_activity("PRICE_UPDATE", f"מחיר מוצר: {old_name} -> {product.name}, {price}, תקף מ-{effective}")
        return jsonify({"success": True, "name": product.name, "price": float(product.price), "effective_from": effective})
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"success": False, "error": "שגיאת שרת"}), 500


@bp.route("/api/products/<path:product_name>/scheduled", methods=["DELETE"])
def cancel_scheduled_prices(product_name):
    denied = write_access()
    if denied:
        return denied
    product = Product.query.filter_by(name=product_name).first()
    if not product:
        return jsonify({"success": False, "error": "מוצר לא נמצא"}), 404
    today = today_iso()
    rows = PriceHistory.query.filter(PriceHistory.product_id == product.id, PriceHistory.effective_from > today).all()
    try:
        count = len(rows)
        for row in rows:
            db.session.delete(row)
        db.session.commit()
        if count:
            log_activity("CANCEL_SCHEDULED_PRICE", f"בוטלו {count} מחירי עתיד עבור {product.name}")
        return jsonify({"success": True, "cancelled": count})
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"success": False, "error": "שגיאת שרת"}), 500


@bp.route("/api/products/<path:product_name>", methods=["DELETE"])
def delete_product(product_name):
    """Previously missing - the price list's delete button
    (deleteProduct() in templates/index.html) had no backend route to hit.
    Deleting a product does not touch previously recorded daily_entry rows -
    each entry already stores its own unit_price/total_amount snapshot at the
    time it was created, independent of the product's current price, exactly
    like changing a product's price does not affect past entries."""
    denied = write_access()
    if denied:
        return denied
    product = Product.query.filter_by(name=product_name).first()
    if not product:
        return jsonify({"success": False, "error": "מוצר לא נמצא"}), 404
    try:
        name = product.name
        db.session.delete(product)
        db.session.commit()
        log_activity("DELETE_PRODUCT", f"נמחק מוצר: {name}")
        return jsonify({"success": True})
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"success": False, "error": "שגיאת שרת"}), 500
