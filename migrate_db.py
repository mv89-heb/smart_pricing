"""One-time database bootstrap/recovery command for deployments.

Run this before starting Gunicorn:
    python migrate_db.py
"""

from smartpricing.app_factory import create_app
from smartpricing.db_setup import bootstrap
from repair_db_indexes import repair


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        print("Repairing PostgreSQL index collisions...", flush=True)
        repair()
        print("Starting Smart Pricing database bootstrap/migration...", flush=True)
        bootstrap()
        print("Database bootstrap/migration completed successfully.", flush=True)
