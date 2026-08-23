import threading

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import inspect, text

from ..db_setup import (
    _create_all_idempotent,
    _ensure_default_tenant_and_admin,
    _normalize_legacy_table_names,
    _repair_unhashed_users,
)
from ..extensions import db
from ..legacy_recovery import recover
from ..security import audit, require_role

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
        session = db.session
        session.execute(text("SET lock_timeout = '5s'"))
        session.execute(text("SET statement_timeout = '30s'"))
        session.execute(text("SET idle_in_transaction_session_timeout = '60s'"))

        print("[recovery] normalizing legacy table names...", flush=True)
        _normalize_legacy_table_names()
        session.commit()

        print("[recovery] creating canonical schema...", flush=True)
        _create_all_idempotent()
        session.commit()

        print("[recovery] recovering legacy Smart Pricing data...", flush=True)
        results = recover()
        _ensure_default_tenant_and_admin()
        _repair_unhashed_users()
        session.commit()
        _recovery_state.update(status="completed", results=results, error=None)
        print(f"[recovery] completed: {results}", flush=True)
    except Exception as exc:
        db.session.rollback()
        _recovery_state.update(status="failed", error=repr(exc))
        print(f"[recovery] failed: {exc!r}", flush=True)
    finally:
        db.session.remove()
        _recovery_lock.release()


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

    GET /api/system/recovery?start=1 starts the recovery once. A normal GET
    only reports status. Recovery runs after the worker is already serving, so
    slow PostgreSQL work cannot block Gunicorn startup.
    """
    if _recovery_state["status"] in {"idle", "failed"} and request.args.get("start") == "1":
        audit("DB_RECOVERY_START", "Legacy Smart Pricing data recovery")
        db.session.commit()
        app = current_app._get_current_object()
        threading.Thread(
            target=_run_recovery_with_app,
            args=(app,),
            name="legacy-data-recovery",
            daemon=True,
        ).start()
    return jsonify(**_recovery_state)


def _run_recovery_with_app(app):
    with app.app_context():
        _run_recovery()
