"""Fast, idempotent restoration for the current monolithic Smart Pricing app.

The active production application reads the original singular table names
(`product`, `daily_entry`, `price_history`, `activity_log`, etc.). Earlier
rebuilds preserved the old rows under `legacy_v1_*` names, so the application
can come up with an empty UI even though the database still contains the data.

This module restores those rows without deleting or renaming the preserved
legacy sources. It is intentionally PostgreSQL-only and uses set-based SQL
for the large datasets so it does not hold hundreds of ORM objects in memory.
"""

from sqlalchemy import inspect, text
from werkzeug.security import generate_password_hash


def _exists(db, name):
    return inspect(db.engine).has_table(name)


def _count(db, name):
    return int(db.session.scalar(text(f'SELECT COUNT(*) FROM "{name}"')) or 0)


def _hashed(value):
    return isinstance(value, str) and value.startswith(("scrypt:", "pbkdf2:", "argon2:"))


def restore_if_needed(db):
    """Restore preserved legacy rows into the tables used by the active app."""
    if db.engine.name != "postgresql":
        return {}

    sources = {
        name: f"legacy_v1_{name}"
        for name in (
            "user",
            "product",
            "daily_entry",
            "price_history",
            "period_lock",
            "activity_log",
            "billing_template",
            "billing_template_item",
        )
    }
    available = {k: v for k, v in sources.items() if _exists(db, v)}
    if not available:
        return {"status": "no_legacy_sources"}

    # Avoid running a recovery pass on every worker restart once the active
    # tables have been populated. Individual INSERTs remain idempotent.
    results = {}
    session = db.session
    try:
        session.execute(text("SET lock_timeout = '5s'"))
        session.execute(text("SET statement_timeout = '20s'"))
        session.execute(text("SET idle_in_transaction_session_timeout = '30s'"))

        if "product" in available and _count(db, "product") == 0:
            source = available["product"]
            session.execute(text(f'''\
                INSERT INTO product (id, name, price, tag)
                SELECT id, name, price, COALESCE(tag, NULL)
                FROM "{source}"
                WHERE name IS NOT NULL AND TRIM(name) <> ''
                ON CONFLICT DO NOTHING
            '''))
            results["products"] = _count(db, "product")
        else:
            results["products"] = _count(db, "product") if _exists(db, "product") else 0

        if "user" in available:
            source = available["user"]
            rows = session.execute(text(f'SELECT id, username, password, role FROM "{source}"')).mappings().all()
            inserted = 0
            for row in rows:
                username = str(row["username"] or "").strip()
                if not username:
                    continue
                if session.scalar(text("SELECT 1 FROM \"user\" WHERE username=:u"), {"u": username}):
                    continue
                password = str(row["password"] or "")
                password = password if _hashed(password) else generate_password_hash(password)
                role = str(row["role"] or "viewer").lower()
                role = role if role in {"admin", "editor", "viewer"} else "viewer"
                session.execute(
                    text("INSERT INTO \"user\" (id, username, password, role) VALUES (:id, :username, :password, :role) ON CONFLICT DO NOTHING"),
                    {"id": row["id"], "username": username, "password": password, "role": role},
                )
                inserted += 1
            results["users_inserted"] = inserted

        if "price_history" in available and _count(db, "price_history") == 0:
            source = available["price_history"]
            session.execute(text(f'''\
                INSERT INTO price_history (id, product_id, price, effective_from, changed_at, changed_by)
                SELECT h.id, p.id, h.price,
                       COALESCE(h.effective_from, SUBSTR(CAST(h.changed_at AS TEXT), 1, 10)),
                       COALESCE(h.changed_at, NOW()),
                       COALESCE(h.changed_by, 'מערכת')
                FROM "{source}" h
                JOIN product p ON p.id = h.product_id
                ON CONFLICT DO NOTHING
            '''))
            results["price_history"] = _count(db, "price_history")
        else:
            results["price_history"] = _count(db, "price_history") if _exists(db, "price_history") else 0

        if "daily_entry" in available and _count(db, "daily_entry") == 0:
            source = available["daily_entry"]
            session.execute(text(f'''\
                INSERT INTO daily_entry (id, date, product_name, quantity, is_extra, unit_price, total_amount, note)
                SELECT id, date, product_name, quantity, COALESCE(is_extra, FALSE),
                       COALESCE(unit_price, 0),
                       COALESCE(total_amount, ROUND(COALESCE(quantity, 0) * COALESCE(unit_price, 0), 2)),
                       note
                FROM "{source}"
                WHERE date IS NOT NULL AND product_name IS NOT NULL
                ON CONFLICT DO NOTHING
            '''))
            results["daily_entries"] = _count(db, "daily_entry")
        else:
            results["daily_entries"] = _count(db, "daily_entry") if _exists(db, "daily_entry") else 0

        if "period_lock" in available and _count(db, "period_lock") == 0:
            source = available["period_lock"]
            session.execute(text(f'''\
                INSERT INTO period_lock (id, year_month, locked, locked_at, locked_by)
                SELECT id, LEFT(year_month::text, 7), COALESCE(locked, TRUE), locked_at, locked_by
                FROM "{source}"
                WHERE year_month IS NOT NULL
                ON CONFLICT DO NOTHING
            '''))
            results["period_locks"] = _count(db, "period_lock")
        else:
            results["period_locks"] = _count(db, "period_lock") if _exists(db, "period_lock") else 0

        if "activity_log" in available and _count(db, "activity_log") == 0:
            source = available["activity_log"]
            session.execute(text(f'''\
                INSERT INTO activity_log (id, timestamp, action, details, username)
                SELECT id, COALESCE(timestamp, NOW()), action, COALESCE(details, ''), COALESCE(username, 'מערכת')
                FROM "{source}"
                WHERE action IS NOT NULL
                ON CONFLICT DO NOTHING
            '''))
            results["activity_logs"] = _count(db, "activity_log")
        else:
            results["activity_logs"] = _count(db, "activity_log") if _exists(db, "activity_log") else 0

        # Keep ORM-generated IDs safe after restoring explicit legacy IDs.
        for table in ("product", "user", "price_history", "daily_entry", "period_lock", "activity_log"):
            if _exists(db, table):
                session.execute(text(f'''\
                    SELECT setval(
                        pg_get_serial_sequence('"{table}"', 'id'),
                        COALESCE((SELECT MAX(id) FROM "{table}"), 1),
                        COALESCE((SELECT MAX(id) FROM "{table}"), 0) > 0
                    )
                '''))

        session.commit()
        results["status"] = "completed"
        print(f"[startup] legacy data restoration: {results}", flush=True)
        return results
    except Exception as exc:
        session.rollback()
        results["status"] = "failed"
        results["error"] = repr(exc)
        print(f"[startup] legacy data restoration failed: {exc!r}", flush=True)
        return results
