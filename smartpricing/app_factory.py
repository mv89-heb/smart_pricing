"""Application factory for Smart Pricing."""
import os
import secrets
from datetime import timedelta

from flask import Flask, jsonify, redirect, request, session, url_for

from .db_setup import bootstrap_database
from .extensions import db


class _HealthMiddleware:
    """Answer GET /health before auth/routing for hosting probes."""

    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        if environ.get("PATH_INFO", "") == "/health":
            body = b'{"status":"ok"}'
            start_response(
                "200 OK",
                [
                    ("Content-Type", "application/json"),
                    ("Content-Length", str(len(body))),
                    ("Cache-Control", "no-store"),
                ],
            )
            return [body]
        return self.wsgi_app(environ, start_response)


_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _asset(path, version):
    return f'<script src="/static/{path}?v={version}" defer></script>'


def _module_scripts(path):
    """Load feature JS only in the workspace that owns it.

    The previous global injection loaded every feature observer on every HTML
    page, creating hidden coupling and duplicate DOM work between modules.
    """
    common = [_asset("module-shell.js", 1)]
    if path == "/":
        return common + [
            _asset("period-report-loader.js", 4),
            _asset("global-filters.js", 4),
            _asset("browser-price-sync.js", 6),
            _asset("mobile-product-picker.js", 2),
            _asset("ui-stability.js", 3),
            _asset("app-shell-stability.js", 3),
            _asset("report-sort.js", 1),
        ]
    if path == "/periodic-report":
        return common + [_asset("report-sort.js", 1)]
    if path == "/settings":
        return common + [_asset("password-reset.js", 4), _asset("report-sort.js", 1)]
    if path == "/static/dashboard.html":
        return common
    return common


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
        SQLALCHEMY_DATABASE_URI=os.environ.get(
            "DATABASE_URL", "sqlite:///local_products.db"
        ).replace("postgres://", "postgresql://", 1),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "false").lower() == "true",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
    )
    db.init_app(app)

    from .routes import (
        admin,
        browser_price_sync,
        dashboard,
        entries,
        pages,
        periods,
        products,
        reports,
        system,
        templates_api,
        users,
    )

    for bp in (
        pages,
        products,
        entries,
        reports,
        dashboard,
        periods,
        templates_api,
        users,
        system,
        browser_price_sync,
        admin,
    ):
        app.register_blueprint(bp.bp)

    @app.before_request
    def require_login():
        if request.endpoint in {"pages.login", "static"}:
            return None
        if request.path.startswith("/api/") and not session.get("logged_in"):
            return jsonify({"error": "Unauthorized"}), 401
        if not request.path.startswith("/api/") and not session.get("logged_in"):
            return redirect(url_for("pages.login"))
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
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response

    @app.after_request
    def inject_frontend_assets(response):
        """Inject shared shell CSS and only the JS owned by this module."""
        if "text/html" not in response.headers.get("Content-Type", ""):
            return response
        try:
            body = response.get_data(as_text=True)
            for asset in (
                '<link rel="stylesheet" href="/static/responsive-layout.css?v=1">',
                '<link rel="stylesheet" href="/static/module-shell.css?v=1">',
                '<link rel="stylesheet" href="/static/module-shell-polish.css?v=1">',
            ):
                if asset not in body and "</head>" in body:
                    body = body.replace("</head>", asset + "</head>", 1)
            for script in _module_scripts(request.path):
                if script not in body and "</body>" in body:
                    body = body.replace("</body>", script + "</body>", 1)
            response.set_data(body)
            response.headers["Cache-Control"] = "no-store, max-age=0"
        except Exception:
            pass
        return response

    app.wsgi_app = _HealthMiddleware(app.wsgi_app)
    bootstrap_database(app)

    from .services.pricing import price_for_date
    from .utils import money

    app.price_for_date = price_for_date
    app.money = money
    return app
