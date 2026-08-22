from functools import wraps
from flask import g, jsonify
from .extensions import db
from .models import ActivityLog

ROLE_LEVEL = {"viewer": 10, "editor": 20, "admin": 30}


def require_role(role="viewer"):
    def decorator(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            user = g.current_user
            if not user or ROLE_LEVEL.get(user.role, 0) < ROLE_LEVEL[role]:
                return jsonify(status="error", message="אין לך הרשאה לבצע פעולה זו"), 403
            return fn(*args, **kwargs)
        return wrapped
    return decorator


def audit(action, details=""):
    user = g.current_user
    if not user:
        return
    db.session.add(ActivityLog(tenant_id=user.tenant_id, action=action, details=details[:1200], username=user.name or user.email))
