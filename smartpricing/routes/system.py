from flask import Blueprint, jsonify, session

from ..extensions import db

bp = Blueprint("system", __name__)

_REQUIRED_TABLES = ["product", "daily_entry", "price_history", "period_lock", "activity_log", "user", "billing_template", "billing_template_item"]


@bp.get("/api/system/health")
def system_health():
    """Authenticated, low-detail readiness check used by the UI and deploy debugging."""
    if not session.get("logged_in"):
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    try:
        from sqlalchemy import text
        inspector = db.inspect(db.engine)
        existing = set(inspector.get_table_names())
        missing = [table for table in _REQUIRED_TABLES if table not in existing]
        if missing:
            return jsonify({"ok": False, "error": "מסד הנתונים אינו מעודכן", "database": db.engine.name, "tables_checked": len(_REQUIRED_TABLES), "missing": missing}), 503
        db.session.execute(text("SELECT 1"))
        return jsonify({"ok": True, "database": db.engine.name, "tables_checked": len(_REQUIRED_TABLES), "missing": []})
    except Exception:
        return jsonify({"ok": False, "error": "מסד הנתונים אינו זמין", "database": db.engine.name, "tables_checked": len(_REQUIRED_TABLES)}), 503
