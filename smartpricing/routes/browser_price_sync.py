from datetime import datetime

from flask import Blueprint, jsonify, request, session

from ..extensions import db
from ..models import PriceHistory, Product
from ..security import admin_access, log_activity
from ..utils import money, today_iso
from services.browser_price_search import search_products

bp = Blueprint("browser_price_sync", __name__)


@bp.post("/api/browser-price-sync/search")
def browser_price_sync_search():
    denied = admin_access()
    if denied:
        return denied
    data = request.get_json(silent=True) or {}
    products = data.get("products")
    if not isinstance(products, list) or not products:
        return jsonify({"success": False, "error": "לא נבחרו מוצרים"}), 400
    if len(products) > 100:
        return jsonify({"success": False, "error": "ניתן לבדוק עד 100 מוצרים בפעולה אחת"}), 400
    try:
        results = search_products(products)
        return jsonify({"success": True, "results": results})
    except Exception as exc:
        return jsonify({"success": False, "error": f"חיפוש המחירים נכשל: {str(exc)[:300]}"}), 500


@bp.post("/api/browser-price-sync/apply")
def browser_price_sync_apply():
    denied = admin_access()
    if denied:
        return denied
    data = request.get_json(silent=True) or {}
    updates, effective_from = data.get("updates"), data.get("effective_from")
    if not isinstance(updates, list) or not updates:
        return jsonify({"success": False, "error": "אין עדכונים"}), 400
    if not isinstance(effective_from, str) or len(effective_from) != 10:
        return jsonify({"success": False, "error": "תאריך תוקף לא תקין"}), 400
    try:
        datetime.strptime(effective_from, "%Y-%m-%d")
    except ValueError:
        return jsonify({"success": False, "error": "תאריך תוקף לא תקין"}), 400
    applied = []
    try:
        for item in updates[:100]:
            name = str(item.get("name") or "").strip()[:100]
            try:
                price = float(item.get("price"))
            except (TypeError, ValueError):
                continue
            if not name or price <= 0:
                continue
            product = Product.query.filter_by(name=name).first()
            if not product:
                continue
            value = money(price)
            existing = PriceHistory.query.filter_by(product_id=product.id, effective_from=effective_from).order_by(PriceHistory.id.desc()).first()
            if existing:
                existing.price = value
                existing.changed_at = datetime.utcnow()
                existing.changed_by = session.get("username", "browser-search")
            else:
                db.session.add(PriceHistory(product_id=product.id, price=value, effective_from=effective_from, changed_by=session.get("username", "browser-search")))
            if effective_from <= today_iso():
                product.price = value
            applied.append({"name": name, "price": float(value), "effective_from": effective_from})
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"success": False, "error": "שמירת העדכונים נכשלה"}), 500
    log_activity("BROWSER_PRICE_SYNC_APPLIED", f"עודכנו {len(applied)} מוצרים באמצעות חיפוש Google בדפדפן")
    return jsonify({"success": True, "applied": applied})
