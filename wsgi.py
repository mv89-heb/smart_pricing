from app import app, db, DailyEntry
from performance import ensure_indexes
from period_report import register_period_report

# One-time, idempotent startup optimization for the existing schema.
# Fail fast if the database itself is unavailable; do not silently serve a
# partially initialized application.
with app.app_context():
    ensure_indexes(db)

register_period_report(app, db, DailyEntry)

__all__ = ["app"]
