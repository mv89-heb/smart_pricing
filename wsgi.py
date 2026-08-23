"""WSGI entrypoint with non-blocking production database recovery."""

import os
import threading

from sqlalchemy import text

from smartpricing.app_factory import create_app
from smartpricing.extensions import db
from repair_db_indexes import repair
from smartpricing.db_setup import (
    _create_all_idempotent,
    _ensure_default_tenant_and_admin,
    _normalize_legacy_table_names,
    _repair_unhashed_users,
)
from smartpricing.legacy_recovery import recover

app = create_app()


def _run_startup_migration():
    """Prepare the schema and recover legacy data without blocking Gunicorn.

    Render does not provide a pre-deploy command for this service, so recovery
    runs in a daemon thread. PostgreSQL statement and lock timeouts are applied
    explicitly: a blocked legacy query must fail and be retried on a later
    deployment rather than keeping the recovery worker stuck indefinitely.
    """
    if os.getenv("AUTO_MIGRATE", "1") != "1":
        return

    uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    if uri.startswith("sqlite"):
        return

    with app.app_context():
        lock_key = 729384019
        session = db.session
        acquired = False
        statement_timeout_ms = max(
            1000, int(os.getenv("DB_MIGRATION_STATEMENT_TIMEOUT_MS", "8000"))
        )
        try:
            session.execute(text("SET lock_timeout = '5s'"))
            session.execute(
                text(f"SET statement_timeout = '{statement_timeout_ms}ms'")
            )
            session.execute(text("SET idle_in_transaction_session_timeout = '15s'"))

            acquired = bool(
                session.scalar(
                    text("SELECT pg_try_advisory_lock(:key)"), {"key": lock_key}
                )
            )
            if not acquired:
                print("[startup] migration already running; serving application.", flush=True)
                return

            print("[startup] repairing PostgreSQL indexes...", flush=True)
            repaired = repair()
            print(f"[startup] repaired {repaired} index collision(s).", flush=True)

            print("[startup] normalizing legacy table names...", flush=True)
            _normalize_legacy_table_names()
            session.commit()

            print("[startup] creating canonical schema...", flush=True)
            _create_all_idempotent()
            session.commit()

            print("[startup] recovering legacy Smart Pricing data...", flush=True)
            results = recover()
            print(f"[startup] recovery results: {results}", flush=True)

            _ensure_default_tenant_and_admin()
            _repair_unhashed_users()
            session.commit()
            print("[startup] database recovery completed; serving application.", flush=True)
        except Exception as exc:
            session.rollback()
            print(f"[startup] database recovery failed: {exc!r}", flush=True)
        finally:
            if acquired:
                try:
                    session.execute(
                        text("SELECT pg_advisory_unlock(:key)"), {"key": lock_key}
                    )
                    session.commit()
                except Exception:
                    session.rollback()


# Render has no Pre-Deploy Command configured for this service. Run recovery
# in a daemon thread so Gunicorn binds $PORT immediately. The migration is
# idempotent and protected by a PostgreSQL advisory lock.
if os.getenv("AUTO_MIGRATE", "1") == "1":
    threading.Thread(
        target=_run_startup_migration,
        name="db-recovery",
        daemon=True,
    ).start()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
