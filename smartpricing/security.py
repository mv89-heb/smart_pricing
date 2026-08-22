"""Authorization helpers and activity logging, used the same way by every route module."""
import time

from flask import jsonify, session

from .extensions import db
from .models import ActivityLog, User

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


def current_user():
    """Resolve the authenticated user from the database, not a stale session role."""
    if not session.get("logged_in") or not session.get("username"):
        return None
    return User.query.filter_by(username=session.get("username")).first()


def write_access():
    """Return an error response if the current user cannot perform writes."""
    user = current_user()
    if not user:
        session.clear()
        return jsonify({"error": "Unauthorized"}), 401
    if user.role == "viewer":
        return jsonify({"success": False, "error": "אין הרשאות"}), 403
    # Keep the session compatible with the DB after an admin/editor role change.
    session["role"] = user.role
    return None


def admin_access():
    """Return an error response if the current database user is not an admin."""
    user = current_user()
    if not user:
        session.clear()
        return jsonify({"error": "Unauthorized"}), 401
    if user.role != "admin":
        session["role"] = user.role
        return jsonify({"error": "נדרש מנהל"}), 403
    session["role"] = "admin"
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
