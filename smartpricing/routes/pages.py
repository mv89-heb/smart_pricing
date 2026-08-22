from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from ..models import User
from ..security import log_activity, login_rate_limited

bp = Blueprint("pages", __name__)


def _module(template, module, title):
    return render_template(template, active_module=module, module_title=title)


@bp.route("/")
def index():
    return _module("modules/daily.html", "daily", "דיווח יומי")


@bp.route("/pricing")
def pricing():
    return _module("modules/pricing.html", "pricing", "מחירון")


@bp.route("/dashboard")
def dashboard():
    return _module("modules/dashboard.html", "dashboard", "דשבורד")


@bp.route("/periodic-report")
def periodic_report():
    return _module("modules/reports.html", "reports", "דוחות")


@bp.route("/settings")
def settings():
    return _module("settings.html", "settings", "הגדרות")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")
    if login_rate_limited(request.remote_addr):
        return jsonify({"success": False, "message": "יותר מדי ניסיונות. נסה שוב בעוד מספר דקות."}), 429
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    user = User.query.filter_by(username=username).first()
    valid = False
    if user:
        try:
            valid = check_password_hash(user.password, password)
        except Exception:
            valid = False
    if not user or not valid:
        return jsonify({"success": False, "message": "שם משתמש או סיסמה שגויים"}), 401
    session.clear()
    session.permanent = True
    session.update({"logged_in": True, "username": user.username, "role": user.role})
    log_activity("LOGIN", "התחברות למערכת")
    return jsonify({"success": True, "role": user.role, "username": user.username})


@bp.route("/logout")
def logout():
    if session.get("logged_in"):
        log_activity("LOGOUT", "התנתקות מהמערכת")
    session.clear()
    return redirect(url_for("pages.login"))


@bp.get("/api/current_user")
def current_user():
    return jsonify({"username": session.get("username"), "role": session.get("role", "viewer")})
