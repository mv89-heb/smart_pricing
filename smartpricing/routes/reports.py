from datetime import date
from flask import Blueprint, request, jsonify, g
from sqlalchemy import select
from ..models import Product
from ..services.reports import period_report

reports_bp = Blueprint("reports", __name__, url_prefix="/api/reports")


@reports_bp.get("")
def report():
    try:
        start = date.fromisoformat(request.args["start"]); end = date.fromisoformat(request.args["end"])
    except (KeyError, ValueError): return jsonify(status="error", message="טווח תאריכים לא תקין"), 400
    if end < start: return jsonify(status="error", message="תאריך הסיום חייב להיות אחרי ההתחלה"), 400
    pid = request.args.get("product_id")
    pid = int(pid) if pid else None
    if pid and not __import__("smartpricing.extensions", fromlist=["db"]).db.session.scalar(select(Product.id).where(Product.id == pid, Product.tenant_id == g.current_user.tenant_id)):
        return jsonify(status="error", message="המוצר אינו שייך לארגון"), 403
    return jsonify(period_report(g.current_user.tenant_id, start, end, pid, request.args.get("category"), request.args.get("entry_type")))
