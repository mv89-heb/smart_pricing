"""WSGI entrypoint with safe deployment-time database recovery."""

import os
import threading

from sqlalchemy import text

from smartpricing.app_factory import create_app
from smartpricing.extensions import db
from repair_db_indexes import repair
from smartpricing.db_setup import bootstrap

app = create_app()


def _run_startup_migration():
    """Repair schema and migrate legacy data without blocking Gunicorn startup."""
    if os.getenv("AUTO_MIGRATE", "1") != "1":
        return

    uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    if uri.startswith("sqlite"):
        return

    with app.app_context():
        lock_key = 729384019
        session = db.session
        acquired = False
        try:
            session.execute(text("SET lock_timeout = '5s'"))
            acquired = bool(session.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": lock_key}))
            if not acquired:
                print("[startup] migration already running; serving application.", flush=True)
                return

            print("[startup] repairing PostgreSQL indexes...", flush=True)
            repaired = repair()
            print(f"[startup] repaired {repaired} index collision(s).", flush=True)
            print("[startup] migrating legacy Smart Pricing data...", flush=True)
            bootstrap()
            print("[startup] database migration completed; serving application.", flush=True)
        except Exception as exc:
            session.rollback()
            print(f"[startup] database recovery deferred/failed: {exc!r}", flush=True)
        finally:
            if acquired:
                try:
                    session.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": lock_key})
                    session.commit()
                except Exception:
                    session.rollback()


# Render has no Pre-Deploy Command configured for this service. Run recovery
# in a daemon thread so Gunicorn binds $PORT immediately. The migration is
# idempotent and protected by a PostgreSQL advisory lock.
if os.getenv("AUTO_MIGRATE", "1") == "1":
    threading.Thread(target=_run_startup_migration, name="db-recovery", daemon=True).start()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
