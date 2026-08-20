"""Production infrastructure for Smart Pricing.

This module intentionally contains only infrastructure concerns: health checks
and database indexes/repairs. Application routes and business calculations are
owned by ``api_routes.py`` and ``services`` respectively.
"""
from sqlalchemy import text

import app as app_module

app = app_module.app
db = app_module.db


class _HealthMiddleware:
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


def _install_indexes():
    """Install safe performance indexes without changing stored data."""
    statements = (
        "CREATE INDEX IF NOT EXISTS ix_daily_entry_date_id ON daily_entry (date, id)",
        "CREATE INDEX IF NOT EXISTS ix_daily_entry_date_product_extra ON daily_entry (date, product_name, is_extra)",
        "CREATE INDEX IF NOT EXISTS ix_price_history_product_effective_id ON price_history (product_id, effective_from, id)",
        "CREATE INDEX IF NOT EXISTS ix_period_lock_month_locked ON period_lock (year_month, locked)",
        "CREATE INDEX IF NOT EXISTS ix_activity_log_timestamp ON activity_log (timestamp)",
        "CREATE INDEX IF NOT EXISTS ix_template_item_product_name ON billing_template_item (product_name)",
    )
    with app.app_context():
        for statement in statements:
            try:
                db.session.execute(text(statement))
                db.session.commit()
            except Exception:
                db.session.rollback()


# Keep the health endpoint available before authentication, while every normal
# application route continues through Flask's existing authentication hooks.
app.wsgi_app = _HealthMiddleware(app.wsgi_app)
_install_indexes()
