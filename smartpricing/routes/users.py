from flask import Blueprint, jsonify, request
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import generate_password_hash

from ..extensions import db
from ..models import User
from ..security import admin_access, log_activity

bp = Blueprint("users", __name__)

_VALID_ROLES = {"admin", "editor", "viewer"}


@bp.post("/api/users/<int:user_id>/reset-password")
def reset_user_password(user_id):
    denied = admin_access()
    if denied:
        return denied
    data = request.get_json(silent=True) or {}
    password = data.get("password") or ""
    if not isinstance(password, str) or len(password) < 8:
        return jsonify({"success": False, "error": "סיסמה חייבת להכיל לפחות 8 תווים"}), 400
    if len(password) > 128:
        return jsonify({"success": False, "error": "סיסמה ארוכה מדי"}), 400
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"success": False, "error": "המשתמש לא נמצא"}), 404
    try:
        user.password = generate_password_hash(password)
        db.session.commit()
        log_activity("USER_PASSWORD_RESET", f"איפוס סיסמה למשתמש: {user.username}")
        return jsonify({"success": True, "username": user.username})
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"success": False, "error": "שגיאת שרת"}), 500


@bp.get("/api/users")
def list_users():
    """Previously missing - the admin panel's user table had no route to load from."""
    denied = admin_access()
    if denied:
        return denied
    return jsonify([{"id": u.id, "username": u.username, "role": u.role} for u in User.query.order_by(User.username.asc()).all()])


@bp.post("/api/users")
def create_or_update_user():
    """Previously missing. Also serves as the admin panel's "edit user" action:
    the form disables the username field and allows an empty password when
    editing, so an existing username with a blank password updates the role
    only, without touching the stored password hash."""
    denied = admin_access()
    if denied:
        return denied
    data = request.get_json(silent=True) or {}
    username = str(data.get("username") or "").strip()[:100]
    password = data.get("password") or ""
    role = str(data.get("role") or "").strip()
    if not username or role not in _VALID_ROLES:
        return jsonify({"success": False, "error": "נתונים שגויים"}), 400
    user = User.query.filter_by(username=username).first()
    try:
        if user:
            user.role = role
            if password:
                if len(password) < 8:
                    return jsonify({"success": False, "error": "סיסמה חייבת להכיל לפחות 8 תווים"}), 400
                user.password = generate_password_hash(password)
            db.session.commit()
            log_activity("USER_UPDATED", f"עודכן משתמש: {username} ({role})")
            return jsonify({"success": True, "id": user.id, "username": user.username, "role": user.role})
        if not password or len(password) < 8:
            return jsonify({"success": False, "error": "סיסמה חייבת להכיל לפחות 8 תווים"}), 400
        new_user = User(username=username, password=generate_password_hash(password), role=role)
        db.session.add(new_user)
        db.session.commit()
        log_activity("USER_CREATED", f"נוצר משתמש: {username} ({role})")
        return jsonify({"success": True, "id": new_user.id, "username": new_user.username, "role": new_user.role})
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"success": False, "error": "שגיאת שרת"}), 500


@bp.route("/api/users/<int:user_id>", methods=["DELETE"])
def delete_user(user_id):
    """Previously missing. Refuses to remove the last remaining admin account
    so the system can never be left with no one able to manage it."""
    denied = admin_access()
    if denied:
        return denied
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"success": False, "error": "המשתמש לא נמצא"}), 404
    if user.role == "admin" and User.query.filter_by(role="admin").count() <= 1:
        return jsonify({"success": False, "error": "לא ניתן למחוק את מנהל המערכת האחרון"}), 400
    try:
        username = user.username
        db.session.delete(user)
        db.session.commit()
        log_activity("USER_DELETED", f"נמחק משתמש: {username}")
        return jsonify({"success": True})
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"success": False, "error": "שגיאת שרת"}), 500
