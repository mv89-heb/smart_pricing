"""Small, idempotent database performance helpers for production startup."""

from sqlalchemy import text


def ensure_indexes(db):
    """Create only the read-path indexes the current application needs.

    Statements are idempotent and intentionally avoid changing the existing
    schema or data model. They run once when a Gunicorn worker starts.
    """
    statements = (
        "CREATE INDEX IF NOT EXISTS ix_daily_entry_date ON daily_entry (date)",
        "CREATE INDEX IF NOT EXISTS ix_daily_entry_date_product ON daily_entry (date, product_name)",
        "CREATE INDEX IF NOT EXISTS ix_daily_entry_product_name ON daily_entry (product_name)",
        "CREATE INDEX IF NOT EXISTS ix_activity_log_timestamp ON activity_log (timestamp)",
    )
    with db.engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
