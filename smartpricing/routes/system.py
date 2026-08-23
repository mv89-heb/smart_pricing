import threading

from flask import Blueprint, jsonify
from sqlalchemy import inspect, text

from ..db_setup import (
    _create_all_idempotent,
    _ensure_default_tenant_and_admin,
    _normalize_legacy_table_names,
    _repair_unhashed_users,
)
from ..extensions import db
from ..legacy_recovery import recover
from ..security import require_role, audit

system_bp = Blueprint("system", __name__)

_recovery_lock = threading.Lock()
_recovery_state = {
    "status": "idle",
    "results": None,
    "error": None,
}


def _run_recovery():
    if not _recovery_lock.acquire(blocking=False):
        return
    try:
        _recovery_state.update(status="running", results=None, error=None)
        with db.engine.begin() as connection:
            connection.execute(text("SET lock_timeout = '5s'"))
            connection.execute(text("SET statement_timeout = '30s'"))
            connection.execute(text("SET idle_in_transaction_session_timeout = '60s'"))

        with system_bp._state.app.app_context() if False else _app_context():
            _normalize_legacy_table_names()
            db.session.commit()
            _create_all_idempotent()
            db.session.commit()
            results = recover()
            _ensure_default_tenant_and_admin()
            _repair_unhashed_users()
            db.session.commit()
            _recovery_state.update(status="completed", results=results, error=None)
    except Exception as exc:
        db.session.rollback()
        _recovery_state.update(status="failed", error=repr(exc))
        print(f"[recovery] failed: {exc!r}", flush=True)
    finally:
        db.session.remove()
        _recovery_lock.release()


def _app_context():
    # The Flask application is attached to the blueprint after registration.
    # Importing the app here would create a second application, so obtain the
    # current application from Flask's context when the worker thread starts.
    from flask import current_app
    return current_app._get_current_object().app_context()


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


@system_bp.get("/api/system/recovery")
@require_role("admin")
def recovery():
    """Start or inspect the one-time legacy-data recovery.

    GET /api/system/recovery?start=1 starts the recovery once. The normal GET
    only reports status. The operation is deliberately outside Gunicorn import
    so a slow PostgreSQL operation cannot kill the web worker during boot.
    """
    if _recovery_state["status"] in {"idle", "failed"} and __import__("flask").request.args.get("start") == "1":
        audit("DB_RECOVERY_START", "Legacy Smart Pricing data recovery")
        db.session.commit()
        app = __import__("flask").current_app._get_current_object()
        thread = threading.Thread(target=_run_recovery_with_app, args=(app,), name="legacy-data-recovery", daemon=True)
        thread.start()
    return jsonify(**_recovery_state)


def _run_recovery_with_app(app):
    with app.app_context():
        _run_recovery()
