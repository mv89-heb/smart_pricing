"""Application factory.

This replaces the previous chain of app.py -> api_routes.py -> wsgi_ui.py ->
wsgi.py, where each module re-imported and monkey-patched the one before it
(sometimes successfully via app.view_functions[...] = ..., sometimes silently
not via app.add_url_rule(...) with a fresh endpoint name on an already-taken
URL - see services/reports.py for the concrete bug that caused). There is now
exactly one place the app is assembled, and exactly one production entrypoint
(wsgi.py) that calls it.
"""
import os
import secrets
from datetime import timedelta

from flask import Flask, jsonify, redirect, request, session, url_for

from .db_setup import bootstrap_database
from .extensions import db


class _HealthMiddleware:
    """Answers GET /health before Flask routing/auth even runs, so hosting
    platform health probes don't need a session. Unchanged from the original
    wsgi.py behavior."""

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
        return response

    @app.after_request
    def inject_frontend_assets(response):
        """Inject shared UX assets into every HTML workspace without changing
        existing feature scripts or module-specific business logic."""
        if "text/html" not in response.headers.get("Content-Type", ""):
            return response
        try:
            body = response.get_data(as_text=True)
            head_assets = [
                '<link rel="stylesheet" href="/static/responsive-layout.css?v=1">',
                '<link rel="stylesheet" href="/static/module-shell.css?v=1">',
                '<link rel="stylesheet" href="/static/module-shell-polish.css?v=1">',
            ]
            for asset in head_assets:
                if asset not in body and "</head>" in body:
                    body = body.replace("</head>", asset + "</head>", 1)
            scripts = [
                '<script src="/static/period-report-loader.js?v=4" defer></script>',
                '<script src="/static/password-reset.js?v=4" defer></script>',
                '<script src="/static/global-filters.js?v=4" defer></script>',
                '<script src="/static/browser-price-sync.js?v=6" defer></script>',
                '<script src="/static/mobile-product-picker.js?v=2" defer></script>',
                '<script src="/static/ui-stability.js?v=3" defer></script>',
                '<script src="/static/app-shell-stability.js?v=3" defer></script>',
                '<script src="/static/report-sort.js?v=1" defer></script>',
                '<script src="/static/system-health.js?v=1" defer></script>',
                '<script src="/static/module-shell.js?v=1" defer></script>',
            ]
            for script in scripts:
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
