from flask import Blueprint, request, jsonify, g
from sqlalchemy import func, select
from werkzeug.security import generate_password_hash
from ..extensions import db
from ..models import User
from ..security import require_role, audit

users_bp = Blueprint("users", __name__, url_prefix="/api/users")


@users_bp.post("")
@require_role("admin")
def create_user():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower(); name = (data.get("name") or "").strip(); password = data.get("password") or ""; role = data.get("role", "editor")
    if not email or not name or len(password) < 8: return jsonify(status="error", message="שם, אימייל וסיסמה של 8 תווים לפחות נדרשים"), 400
    if role not in {"viewer", "editor", "admin"}: return jsonify(status="error", message="תפקיד לא תקין"), 400
    if db.session.scalar(select(User.id).where(User.tenant_id == g.current_user.tenant_id, func.lower(User.email) == email)): return jsonify(status="error", message="האימייל כבר קיים"), 409
    db.session.add(User(tenant_id=g.current_user.tenant_id, email=email, name=name, password_hash=generate_password_hash(password), role=role)); audit("USER_CREATE", email); db.session.commit()
    return jsonify(status="success", message="המשתמש נוצר בהצלחה"), 201


@users_bp.put("/<int:user_id>")
@require_role("admin")
def update_user(user_id):
    user = db.session.scalar(select(User).where(User.id == user_id, User.tenant_id == g.current_user.tenant_id))
    if not user: return jsonify(status="error", message="המשתמש לא נמצא"), 404
    data = request.get_json(silent=True) or {}; role = data.get("role", user.role)
    if role not in {"viewer", "editor", "admin"}: return jsonify(status="error", message="תפקיד לא תקין"), 400
    if user.id == g.current_user.id and role != "admin": return jsonify(status="error", message="לא ניתן להוריד את מנהל המערכת המחובר"), 409
    user.name = (data.get("name") or user.name).strip(); user.role = role
    if data.get("password"):
        if len(data["password"]) < 8: return jsonify(status="error", message="סיסמה קצרה מדי"), 400
        user.password_hash = generate_password_hash(data["password"])
    audit("USER_UPDATE", user.email); db.session.commit(); return jsonify(status="success", message="פרטי המשתמש עודכנו")


@users_bp.delete("/<int:user_id>")
@require_role("admin")
def delete_user(user_id):
    user = db.session.scalar(select(User).where(User.id == user_id, User.tenant_id == g.current_user.tenant_id))
    if not user: return jsonify(status="error", message="המשתמש לא נמצא"), 404
    if user.id == g.current_user.id: return jsonify(status="error", message="לא ניתן למחוק את המשתמש הנוכחי"), 409
    if user.role == "admin" and db.session.scalar(select(func.count(User.id)).where(User.tenant_id == user.tenant_id, User.role == "admin", User.is_active.is_(True))) <= 1: return jsonify(status="error", message="לא ניתן למחוק את מנהל המערכת האחרון"), 409
    user.is_active = False; audit("USER_DELETE", user.email); db.session.commit(); return jsonify(status="success", message="המשתמש הושבת")
