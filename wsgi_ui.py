"""Production entrypoint with UI helpers and admin password reset."""

import wsgi as base
from flask import jsonify, request
from werkzeug.security import generate_password_hash
from sqlalchemy.exc import SQLAlchemyError

app = base.app
User = base.User
admin_access = base.admin_access
log_activity = base.log_activity


@app.post("/api/users/<int:user_id>/reset-password")
def reset_user_password(user_id):
    """Allow an authenticated admin to set a user's password."""
    denied = admin_access()
    if denied:
        return denied

    data = request.get_json(silent=True) or {}
    password = data.get("password") or ""
    if not isinstance(password, str) or len(password) < 8:
        return jsonify({"success": False, "error": "סיסמה חייבת להכיל לפחות 8 תווים"}), 400
    if len(password) > 128:
        return jsonify({"success": False, "error": "סיסמה ארוכה מדי"}), 400

    user = User.query.get(user_id)
    if not user:
        return jsonify({"success": False, "error": "המשתמש לא נמצא"}), 404

    try:
        user.password = generate_password_hash(password)
        db = base.db
        db.session.commit()
        log_activity("USER_PASSWORD_RESET", f"איפוס סיסמה למשתמש: {user.username}")
        return jsonify({"success": True, "username": user.username})
    except SQLAlchemyError:
        base.db.session.rollback()
        return jsonify({"success": False, "error": "שגיאת שרת"}), 500


def _inject_period_report(response):
    content_type = response.headers.get("Content-Type", "")
    if "text/html" not in content_type:
        return response
    try:
        body = response.get_data(as_text=True)
        marker = "</body>"
        scripts = [
            '<script src="/static/period-report-loader.js?v=1" defer></script>',
            '<script src="/static/password-reset.js?v=1" defer></script>',
        ]
        for script in scripts:
            if script not in body and marker in body:
                body = body.replace(marker, script + marker, 1)
        response.set_data(body)
        response.headers["Cache-Control"] = "no-store, max-age=0"
    except Exception:
        pass
    return response


app.after_request(_inject_period_report)
