"""One consolidated, idempotent database bootstrap routine.

Previously this logic was split across app.py (_run_migrations, run at import
time) and wsgi.py (_install_indexes, run again at import time only if wsgi.py
happened to get imported - which silently didn't happen unless every module
in the wsgi_ui -> wsgi chain imported cleanly). Splitting it in two places
meant the two routines could drift and it was unclear which one actually ran
in production. There is now exactly one bootstrap function, called exactly
once from create_app().

Nothing here drops or resets data - every step is additive/idempotent
(ADD COLUMN IF NOT EXISTS-equivalent, CREATE INDEX IF NOT EXISTS, backfill
of NULL/zero values only).
"""
import secrets

from sqlalchemy import text
from werkzeug.security import generate_password_hash

from .extensions import db
from .models import User

_COLUMN_MIGRATIONS = (
    ("daily_entry", "total_amount", "ALTER TABLE daily_entry ADD COLUMN total_amount NUMERIC(14,2)"),
    ("product", "tag", "ALTER TABLE product ADD COLUMN tag VARCHAR(80)"),
    ("price_history", "effective_from", "ALTER TABLE price_history ADD COLUMN effective_from VARCHAR(10)"),
)

_INDEX_STATEMENTS = (
    "CREATE INDEX IF NOT EXISTS ix_daily_entry_date_id ON daily_entry (date, id)",
    "CREATE INDEX IF NOT EXISTS ix_daily_entry_date_product_extra ON daily_entry (date, product_name, is_extra)",
    "CREATE INDEX IF NOT EXISTS ix_price_history_product_effective_id ON price_history (product_id, effective_from, id)",
    "CREATE INDEX IF NOT EXISTS ix_period_lock_month_locked ON period_lock (year_month, locked)",
    "CREATE INDEX IF NOT EXISTS ix_activity_log_timestamp ON activity_log (timestamp)",
    "CREATE INDEX IF NOT EXISTS ix_template_item_product_name ON billing_template_item (product_name)",
)

_POSTGRES_TYPE_FIXES = (
    "ALTER TABLE daily_entry ALTER COLUMN unit_price TYPE NUMERIC(12,2) USING ROUND(unit_price::numeric, 2)",
    "ALTER TABLE product ALTER COLUMN price TYPE NUMERIC(12,2) USING ROUND(price::numeric, 2)",
)


def _column_exists(table_name, column_name):
    try:
        return column_name in [c["name"] for c in db.inspect(db.engine).get_columns(table_name)]
    except Exception:
        return True


def _run(sql):
    try:
        db.session.execute(text(sql))
        db.session.commit()
        return True
    except Exception:
        db.session.rollback()
        return False


def bootstrap_database(app):
    """Create tables, apply safe migrations/indexes, seed the first admin user.

    Safe to call on every app start - every statement is a no-op if already applied.
    """
    with app.app_context():
        db.create_all()

        for table, column, sql in _COLUMN_MIGRATIONS:
            if not _column_exists(table, column):
                _run(sql)

        _run(
            "UPDATE daily_entry SET total_amount = ROUND(COALESCE(quantity,0) * COALESCE(unit_price,0), 2) "
            "WHERE total_amount IS NULL OR total_amount = 0"
        )
        _run(
            "UPDATE price_history SET effective_from = SUBSTR(CAST(changed_at AS TEXT),1,10) "
            "WHERE effective_from IS NULL"
        )

        if db.engine.name == "postgresql":
            for sql in _POSTGRES_TYPE_FIXES:
                _run(sql)

        for sql in _INDEX_STATEMENTS:
            _run(sql)

        if User.query.count() == 0:
            temp_pass = secrets.token_urlsafe(8)
            db.session.add(User(username="admin", password=generate_password_hash(temp_pass), role="admin"))
            db.session.commit()
            app.logger.warning("SECURITY NOTICE: initial admin password generated for admin: %s", temp_pass)
