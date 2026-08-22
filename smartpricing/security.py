"""Authorization helpers and activity logging, used the same way by every route module."""
import time

from flask import jsonify, session

from .extensions import db
from .models import ActivityLog

LOGIN_WINDOW_SECONDS = 300
LOGIN_MAX_ATTEMPTS = 10
_LOGIN_BUCKETS = {}


def login_rate_limited(ip):
    """Return True (and register the attempt) if this IP is over the login rate limit."""
    now = time.time()
    bucket = _LOGIN_BUCKETS.setdefault(ip or "unknown", [])
    bucket[:] = [t for t in bucket if now - t < LOGIN_WINDOW_SECONDS]
    if len(bucket) >= LOGIN_MAX_ATTEMPTS:
        return True
    bucket.append(now)
    return False


def write_access():
    """Return an error response if the current session cannot perform write actions, else None."""
    if not session.get("logged_in"):
        return jsonify({"error": "Unauthorized"}), 401
    if session.get("role", "viewer") == "viewer":
        return jsonify({"success": False, "error": "אין הרשאות"}), 403
    return None


def admin_access():
    """Return an error response if the current session is not an admin, else None."""
    if not session.get("logged_in"):
        return jsonify({"error": "Unauthorized"}), 401
    if session.get("role") != "admin":
        return jsonify({"error": "נדרש מנהל"}), 403
    return None


def log_activity(action, details):
    try:
        db.session.add(ActivityLog(action=action, details=str(details)[:1000], username=session.get("username", "מערכת")))
        if ActivityLog.query.count() > 2000:
            old = ActivityLog.query.order_by(ActivityLog.timestamp.asc()).first()
            if old:
                db.session.delete(old)
        db.session.commit()
    except Exception:
        db.session.rollback()
