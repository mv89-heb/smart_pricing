from flask import (Blueprint, jsonify, make_response, redirect, render_template,
                    request, send_from_directory, session, url_for)
from werkzeug.security import check_password_hash

from ..models import User
from ..security import log_activity, login_rate_limited

bp = Blueprint("pages", __name__)


def _inject_page_assets(html):
    """Attach page-level assets without mixing module markup into templates."""
    if "</head>" not in html:
        return html
    assets = (
        '<link rel="stylesheet" href="/static/daily-module-focus.css?v=1">'
        '<script src="/static/daily-module-focus.js?v=1" defer></script>'
    )
    return html.replace("</head>", assets + "</head>", 1)


@bp.route("/")
def index():
    html = render_template("index.html")
    html = _inject_page_assets(html)
    if "</body>" in html:
        html = html.replace(
            "</body>",
            '<script src="/static/ux-enhancements.js?v=2" defer></script>'
            '<script src="/static/price-scheduling.js?v=2" defer></script></body>',
        )
    return make_response(html)


@bp.route("/periodic-report")
def periodic_report():
    from flask import current_app
    return send_from_directory(current_app.static_folder, "periodic_report.html")


@bp.route("/settings")
def settings():
    return render_template("settings.html")


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
    """Return the current session user for the shell and page UI."""
    return jsonify({"username": session.get("username"), "role": session.get("role", "viewer")})
