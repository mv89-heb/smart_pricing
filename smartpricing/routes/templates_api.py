from flask import Blueprint, jsonify, request
from sqlalchemy.exc import SQLAlchemyError

from ..extensions import db
from ..models import BillingTemplate, BillingTemplateItem
from ..security import log_activity, write_access

bp = Blueprint("templates_api", __name__)


@bp.get("/api/templates")
def get_templates():
    return jsonify({
        template.name: [
            {"product_name": item.product_name, "quantity": item.quantity, "is_extra": bool(item.is_extra)}
            for item in template.items
        ]
        for template in BillingTemplate.query.order_by(BillingTemplate.name.asc()).all()
    })


@bp.post("/api/templates")
def save_template():
    """Previously missing - "שמור כתבנית" on the main screen had no route to
    hit. Saving under an existing name overwrites its items (the frontend
    already confirms this with the user before sending the request)."""
    denied = write_access()
    if denied:
        return denied
    data = request.get_json(silent=True) or {}
    name = str(data.get("name") or "").strip()[:100]
    items = data.get("items")
    if not name or not isinstance(items, list) or not items:
        return jsonify({"success": False, "error": "נתוני תבנית שגויים"}), 400
    cleaned = []
    for item in items:
        product_name = str((item or {}).get("product_name") or "").strip()
        try:
            quantity = float((item or {}).get("quantity"))
        except (TypeError, ValueError):
            continue
        if not product_name or quantity <= 0:
            continue
        cleaned.append({"product_name": product_name, "quantity": quantity, "is_extra": bool((item or {}).get("is_extra"))})
    if not cleaned:
        return jsonify({"success": False, "error": "אין פריטים תקינים בתבנית"}), 400
    try:
        template = BillingTemplate.query.filter_by(name=name).first()
        if template:
            BillingTemplateItem.query.filter_by(template_id=template.id).delete()
        else:
            template = BillingTemplate(name=name)
            db.session.add(template)
            db.session.flush()
        for item in cleaned:
            db.session.add(BillingTemplateItem(template_id=template.id, product_name=item["product_name"], quantity=item["quantity"], is_extra=item["is_extra"]))
        db.session.commit()
        log_activity("TEMPLATE_SAVED", f"נשמרה תבנית: {name} ({len(cleaned)} פריטים)")
        return jsonify({"success": True, "name": name})
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"success": False, "error": "שגיאת שרת"}), 500


@bp.route("/api/templates/<path:name>", methods=["DELETE"])
def delete_template(name):
    """Previously missing - the templates modal's per-row delete button had no
    backend route to hit."""
    denied = write_access()
    if denied:
        return denied
    template = BillingTemplate.query.filter_by(name=name).first()
    if not template:
        return jsonify({"success": False, "error": "תבנית לא נמצאה"}), 404
    try:
        db.session.delete(template)
        db.session.commit()
        log_activity("TEMPLATE_DELETED", f"נמחקה תבנית: {name}")
        return jsonify({"success": True})
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"success": False, "error": "שגיאת שרת"}), 500
