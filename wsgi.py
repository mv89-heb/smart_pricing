from app import app, db
from performance import ensure_indexes

# One-time, idempotent startup optimization for the existing schema.
# Fail fast if the database itself is unavailable; do not silently serve a
# partially initialized application.
with app.app_context():
    ensure_indexes(db)

__all__ = ["app"]
