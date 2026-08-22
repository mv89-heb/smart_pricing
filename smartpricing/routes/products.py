from datetime import date
from flask import Blueprint, request, jsonify, g
from sqlalchemy import select
from ..extensions import db
from ..models import Product, PriceHistory, PeriodLock
from ..security import require_role, audit
from ..services.pricing import set_price

products_bp = Blueprint("products", __name__, url_prefix="/api/products")


def _locked(tenant_id, value):
    return db.session.scalar(select(PeriodLock.id).where(PeriodLock.tenant_id == tenant_id, PeriodLock.year_month == value, PeriodLock.locked.is_(True))) is not None


@products_bp.post("")
@require_role("editor")
def create_product():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify(status="error", message="שם המוצר הינו שדה חובה"), 400
    if db.session.scalar(select(Product.id).where(Product.tenant_id == g.current_user.tenant_id, Product.name == name)):
        return jsonify(status="error", message="מוצר בשם זה כבר קיים"), 409
    try:
        price = float(data.get("current_price", 0))
        if price < 0: raise ValueError
    except (TypeError, ValueError):
        return jsonify(status="error", message="מחיר לא תקין"), 400
    product = Product(tenant_id=g.current_user.tenant_id, sku=data.get("sku"), name=name, category=data.get("category") or "כללי", unit=data.get("unit") or "יחידות", current_price=price)
    db.session.add(product); db.session.flush()
    set_price(product, price, date.today(), g.current_user.name)
    audit("PRODUCT_CREATE", name)
    db.session.commit()
    return jsonify(status="success", message="המוצר התווסף בהצלחה", id=product.id), 201


@products_bp.put("/<int:product_id>")
@require_role("editor")
def update_product(product_id):
    product = db.session.scalar(select(Product).where(Product.id == product_id, Product.tenant_id == g.current_user.tenant_id))
    if not product: return jsonify(status="error", message="המוצר לא נמצא"), 404
    data = request.get_json(silent=True) or {}
    product.name = (data.get("name") or product.name).strip()
    product.category = data.get("category") or product.category
    product.unit = data.get("unit") or product.unit
    if "current_price" in data:
        try: price = float(data["current_price"])
        except (TypeError, ValueError): return jsonify(status="error", message="מחיר לא תקין"), 400
        set_price(product, price, date.today(), g.current_user.name)
    audit("PRODUCT_UPDATE", product.name)
    db.session.commit()
    return jsonify(status="success", message="המוצר עודכן בהצלחה")


@products_bp.delete("/<int:product_id>")
@require_role("admin")
def delete_product(product_id):
    product = db.session.scalar(select(Product).where(Product.id == product_id, Product.tenant_id == g.current_user.tenant_id))
    if not product: return jsonify(status="error", message="המוצר לא נמצא"), 404
    if db.session.scalar(select(db.func.count()).select_from(__import__("smartpricing.models", fromlist=["DailyEntry"]).DailyEntry).where(__import__("smartpricing.models", fromlist=["DailyEntry"]).DailyEntry.product_id == product.id)):
        return jsonify(status="error", message="לא ניתן למחוק מוצר שכבר שימש בדיווחים; השבת אותו במקום זאת"), 409
    db.session.delete(product); audit("PRODUCT_DELETE", product.name); db.session.commit()
    return jsonify(status="success", message="המוצר נמחק בהצלחה")


@products_bp.post("/<int:product_id>/price")
@require_role("editor")
def set_product_price(product_id):
    product = db.session.scalar(select(Product).where(Product.id == product_id, Product.tenant_id == g.current_user.tenant_id))
    if not product: return jsonify(status="error", message="המוצר לא נמצא"), 404
    data = request.get_json(silent=True) or {}
    try: eff = date.fromisoformat(data["effective_date"]); price = float(data["price"])
    except (KeyError, TypeError, ValueError): return jsonify(status="error", message="מחיר או תאריך לא תקינים"), 400
    if price < 0: return jsonify(status="error", message="מחיר לא יכול להיות שלילי"), 400
    if _locked(g.current_user.tenant_id, eff.strftime("%Y-%m")): return jsonify(status="error", message="התקופה נעולה"), 409
    set_price(product, price, eff, g.current_user.name); audit("PRICE_CHANGE", f"{product.name}: {price} @ {eff.isoformat()}"); db.session.commit()
    return jsonify(status="success", message="המחיר נשמר")


@products_bp.post("/apply-validity")
@require_role("editor")
def apply_validity():
    data = request.get_json(silent=True) or {}
    try: year = int(data.get("year")); eff = date(year, 1, 1)
    except (TypeError, ValueError): return jsonify(status="error", message="שנה לא תקינה"), 400
    if _locked(g.current_user.tenant_id, f"{year:04d}-01"): return jsonify(status="error", message="ינואר של השנה הזו נעול"), 409
    products = db.session.scalars(select(Product).where(Product.tenant_id == g.current_user.tenant_id)).all()
    for product in products: set_price(product, product.current_price, eff, g.current_user.name)
    audit("PRICEBOOK_VALIDITY", f"01/01/{year} לכל {len(products)} המוצרים"); db.session.commit()
    return jsonify(status="success", message=f"תוקף המחירון הוחל מ-01/01/{year}", count=len(products))


@products_bp.post("/<int:product_id>/toggle")
@require_role("editor")
def toggle_product(product_id):
    product = db.session.scalar(select(Product).where(Product.id == product_id, Product.tenant_id == g.current_user.tenant_id))
    if not product: return jsonify(status="error", message="המוצר לא נמצא"), 404
    product.is_active = not product.is_active; audit("PRODUCT_STATUS", product.name); db.session.commit()
    return jsonify(status="success", message="סטטוס המוצר עודכן")
