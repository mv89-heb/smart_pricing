"""Application factory for Smart Pricing."""
import os
import secrets
from datetime import timedelta

from flask import Flask, jsonify, request, session, url_for, redirect

from .db_setup import bootstrap_database
from .extensions import db


class _HealthMiddleware:
    """Answer GET /health before auth/routing for hosting probes."""
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        if environ.get("PATH_INFO", "") == "/health":
            body = b'{"status":"ok"}'
            start_response("200 OK", [("Content-Type", "application/json"), ("Content-Length", str(len(body))), ("Cache-Control", "no-store")])
            return [body]
        return self.wsgi_app(environ, start_response)


_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def create_app():
    app = Flask(
        __name__,
        static_folder=os.path.join(_PROJECT_ROOT, "static"),
        template_folder=os.path.join(_PROJECT_ROOT, "templates"),
    )
    secret_key = os.environ.get("SECRET_KEY")
    if not secret_key:
        if os.environ.get("FLASK_ENV", "development") == "production":
            raise RuntimeError("SECRET_KEY must be configured in production")
        secret_key = secrets.token_hex(32)
    app.config.update(
        SECRET_KEY=secret_key,
        SQLALCHEMY_DATABASE_URI=os.environ.get("DATABASE_URL", "sqlite:///local_products.db").replace("postgres://", "postgresql://", 1),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True, "pool_recycle": 1800},
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "false").lower() == "true",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
    )
    db.init_app(app)

    from .routes import admin, browser_price_sync, dashboard, entries, pages, periods, products, reports, system, templates_api, users
    for bp in (pages, products, entries, reports, dashboard, periods, templates_api, users, system, browser_price_sync, admin):
        app.register_blueprint(bp.bp)

    @app.before_request
    def require_login():
        if request.endpoint in {"pages.login", "static"}:
            return None
        if request.path.startswith("/api/") and not session.get("logged_in"):
            return jsonify({"error": "Unauthorized"}), 401
        if not request.path.startswith("/api/") and not session.get("logged_in"):
            return redirect(url_for("pages.login"))

        if session.get("logged_in") and session.get("username"):
            from .models import User
            user = User.query.filter_by(username=session.get("username")).first()
            if user is None:
                session.clear()
                if request.path.startswith("/api/"):
                    return jsonify({"error": "Unauthorized"}), 401
                return redirect(url_for("pages.login"))
            session["role"] = user.role

        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            origin = request.headers.get("Origin")
            if origin and origin.rstrip("/") != request.host_url.rstrip("/"):
                return jsonify({"error": "CSRF verification failed"}), 403
            if request.path.startswith("/api/") and request.headers.get("X-Requested-With") != "XMLHttpRequest":
                return jsonify({"error": "CSRF verification failed"}), 403

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        if request.is_secure:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        if request.path.startswith("/static/"):
            response.headers["Cache-Control"] = "public, max-age=3600"
        elif response.content_type.startswith("text/html"):
            response.headers.setdefault("Cache-Control", "no-store, max-age=0")
        return response

    app.wsgi_app = _HealthMiddleware(app.wsgi_app)
    bootstrap_database(app)
    from .services.pricing import price_for_date
    from .utils import money
    app.price_for_date = price_for_date
    app.money = money
    return app
