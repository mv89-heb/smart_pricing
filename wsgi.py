"""WSGI entrypoint with safe deployment-time database recovery."""

import os

from sqlalchemy import text

from smartpricing.app_factory import create_app
from smartpricing.db_setup import bootstrap
from smartpricing.extensions import db
from repair_db_indexes import repair


app = create_app()


def _run_startup_migration():
    """Repair schema collisions and migrate legacy data before serving traffic.

    Render does not expose a Pre-Deploy Command on this service, so the WSGI
    entrypoint is the reliable deployment hook. The migration is idempotent and
    preserves legacy tables/rows; a PostgreSQL advisory lock prevents concurrent
    Gunicorn workers from running it at the same time.
    """
    if os.getenv("AUTO_MIGRATE", "1") != "1":
        return

    uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    if uri.startswith("sqlite"):
        # Local/test SQLite databases should not be mutated during module import.
        return

    with app.app_context():
        lock_key = 729384019
        db.session.execute(text("SELECT pg_advisory_lock(:key)"), {"key": lock_key})
        try:
            print("[startup] repairing PostgreSQL indexes...", flush=True)
            repaired = repair()
            print(f"[startup] repaired {repaired} index collision(s).", flush=True)
            print("[startup] migrating legacy Smart Pricing data...", flush=True)
            bootstrap()
            print("[startup] database migration completed; serving application.", flush=True)
        finally:
            db.session.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": lock_key})
            db.session.commit()


_run_startup_migration()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
