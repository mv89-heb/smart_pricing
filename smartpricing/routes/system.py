from flask import Blueprint, jsonify
from sqlalchemy import inspect, text
from ..extensions import db

system_bp = Blueprint("system", __name__)


@system_bp.get("/health")
def health():
    try:
        db.session.execute(text("SELECT 1"))
        return jsonify(status="ok", database="ok")
    except Exception:
        db.session.rollback()
        return jsonify(status="degraded", database="error"), 503


@system_bp.get("/api/system/health")
def detailed_health():
    required = ["tenants", "users", "products", "price_history", "daily_entries", "period_locks", "activity_logs", "billing_templates", "billing_template_items"]
    inspector = inspect(db.engine)
    missing = [name for name in required if not inspector.has_table(name)]
    return jsonify(status="ok" if not missing else "degraded", database=str(db.engine.url).split("@")[0], missing_tables=missing)
