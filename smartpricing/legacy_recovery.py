"""Idempotent recovery of data from the pre-rebuild Smart Pricing schema.

This module deliberately treats the old singular tables as read-only sources.
Each dataset is migrated in its own transaction so one malformed legacy row or
optional legacy table cannot roll back otherwise recoverable production data.
"""
from sqlalchemy import inspect, text
from werkzeug.security import generate_password_hash

from .extensions import db
from .models import Tenant


def _exists(name):
    return inspect(db.engine).has_table(name)


def _cols(name):
    return {c["name"] for c in inspect(db.engine).get_columns(name)} if _exists(name) else set()


def _source(*names):
    for name in names:
        if _exists(name):
            return name
    return None


def _col(cols, *names):
    for name in names:
        if name in cols:
            return name
    return None


def _tenant():
    tenant = db.session.scalar(text("SELECT id FROM tenants ORDER BY id LIMIT 1"))
    if tenant is None:
        tenant = db.session.execute(
            text("INSERT INTO tenants (name) VALUES (:name) RETURNING id"),
            {"name": "Smart Pricing"},
        ).scalar_one()
    return tenant


def _password(value):
    value = "" if value is None else str(value)
    prefixes = ("scrypt:", "pbkdf2:", "argon2:")
    return value if value.startswith(prefixes) else generate_password_hash(value)


def _migrate_users(tenant):
    source = _source("legacy_v1_users", "legacy_v1_user", "user")
    if not source:
        return 0
    cols = _cols(source)
    name_col = _col(cols, "username", "email", "name")
    pass_col = _col(cols, "password_hash", "password")
    role_col = _col(cols, "role")
    id_col = _col(cols, "id")
    if not name_col or not pass_col:
        return 0
    role_expr = f'"{role_col}"' if role_col else "'viewer'"
    id_expr = f'"{id_col}"' if id_col else "NULL"
    rows = db.session.execute(text(f'SELECT {id_expr} AS legacy_id, "{name_col}" AS login, "{pass_col}" AS password, {role_expr} AS role FROM "{source}"')).mappings()
    count = 0
    for row in rows:
        login = str(row["login"] or "").strip()
        if not login:
            continue
        email = login.lower() if "@" in login else f"{login.lower()}@legacy.local"
        role = str(row["role"] or "viewer").lower()
        role = role if role in {"admin", "editor", "viewer"} else "viewer"
        exists = db.session.scalar(text("SELECT id FROM users WHERE tenant_id=:t AND email=:e"), {"t": tenant, "e": email})
        if exists:
            continue
        db.session.execute(text("INSERT INTO users (tenant_id,email,name,password_hash,role,is_active) VALUES (:t,:e,:n,:p,:r,1)"), {"t": tenant, "e": email, "n": login, "p": _password(row["password"]), "r": role})
        count += 1
    return count


def _migrate_products(tenant):
    source = _source("legacy_v1_products", "legacy_v1_product", "product")
    if not source:
        return 0, {}
    cols = _cols(source)
    id_col = _col(cols, "id")
    name_col = _col(cols, "name", "product_name", "description")
    price_col = _col(cols, "current_price", "price")
    if not name_col or not price_col:
        return 0, {}
    category_col = _col(cols, "category", "tag")
    sku_col = _col(cols, "sku")
    unit_col = _col(cols, "unit")
    id_expr = f'"{id_col}"' if id_col else "NULL"
    cat_expr = f'"{category_col}"' if category_col else "NULL"
    sku_expr = f'"{sku_col}"' if sku_col else "NULL"
    unit_expr = f'"{unit_col}"' if unit_col else "NULL"
    rows = db.session.execute(text(f'SELECT {id_expr} AS legacy_id, "{name_col}" AS name, "{price_col}" AS price, {cat_expr} AS category, {sku_expr} AS sku, {unit_expr} AS unit FROM "{source}" ORDER BY legacy_id NULLS LAST')).mappings()
    mapping = {}
    count = 0
    for row in rows:
        name = str(row["name"] or "").strip()
        if not name:
            continue
        pid = db.session.scalar(text("SELECT id FROM products WHERE tenant_id=:t AND name=:n"), {"t": tenant, "n": name})
        if pid is None:
            pid = db.session.execute(text("INSERT INTO products (tenant_id,sku,name,category,unit,current_price,is_active) VALUES (:t,:sku,:n,:c,:u,:p,1) RETURNING id"), {"t": tenant, "sku": row["sku"] or (f"LEG-{row['legacy_id']}" if row["legacy_id"] is not None else None), "n": name, "c": row["category"] or "כללי", "u": row["unit"] or "יחידות", "p": row["price"] or 0}).scalar_one()
            count += 1
        if row["legacy_id"] is not None:
            mapping[row["legacy_id"]] = pid
    return count, mapping


def _migrate_history(tenant, product_map):
    source = _source("legacy_v1_price_history")
    if not source:
        return 0
    cols = _cols(source)
    product_col = _col(cols, "product_id")
    price_col = _col(cols, "price", "current_price")
    date_col = _col(cols, "effective_from", "effective_date", "date", "changed_at")
    if not product_col or not price_col or not date_col:
        return 0
    changed_at_col = _col(cols, "changed_at")
    changed_by_col = _col(cols, "changed_by")
    at_expr = f',"{changed_at_col}" AS changed_at' if changed_at_col else ',NULL AS changed_at'
    by_expr = f',"{changed_by_col}" AS changed_by' if changed_by_col else ',NULL AS changed_by'
    rows = db.session.execute(text(f'SELECT "{product_col}" AS product_id, "{price_col}" AS price, "{date_col}" AS effective_date{at_expr}{by_expr} FROM "{source}"')).mappings()
    count = 0
    for row in rows:
        pid = product_map.get(row["product_id"])
        if pid is None:
            pid = db.session.scalar(text("SELECT id FROM products WHERE tenant_id=:t AND id=:p"), {"t": tenant, "p": row["product_id"]})
        if pid is None or row["effective_date"] is None:
            continue
        if db.session.scalar(text("SELECT id FROM price_history WHERE product_id=:p AND effective_date=CAST(:d AS date)"), {"p": pid, "d": row["effective_date"]}) is not None:
            continue
        db.session.execute(text("INSERT INTO price_history (product_id,price,effective_date,changed_at,changed_by) VALUES (:p,:price,CAST(:d AS date),COALESCE(:at,NOW()),:by)"), {"p": pid, "price": row["price"] or 0, "d": row["effective_date"], "at": row["changed_at"], "by": str(row["changed_by"] or "מערכת")})
        count += 1
    return count


def _migrate_entries(tenant, product_map):
    source = _source("legacy_v1_daily_entries", "legacy_v1_daily_entry", "daily_entry")
    if not source:
        return 0
    cols = _cols(source)
    date_col = _col(cols, "date", "entry_date")
    qty_col = _col(cols, "quantity", "qty")
    product_id_col = _col(cols, "product_id")
    product_name_col = _col(cols, "product_name", "name")
    price_col = _col(cols, "unit_price", "price_at_time", "price")
    extra_col = _col(cols, "is_extra")
    note_col = _col(cols, "note", "notes")
    user_col = _col(cols, "recorded_by", "user_id")
    if not date_col or not qty_col:
        return 0
    pid_expr = f'"{product_id_col}"' if product_id_col else "NULL"
    name_expr = f'"{product_name_col}"' if product_name_col else "NULL"
    price_expr = f'"{price_col}"' if price_col else "NULL"
    extra_expr = f'"{extra_col}"' if extra_col else "FALSE"
    note_expr = f'"{note_col}"' if note_col else "NULL"
    user_expr = f'"{user_col}"' if user_col else "NULL"
    rows = db.session.execute(text(f'SELECT "{date_col}" AS date, "{qty_col}" AS quantity, {pid_expr} AS product_id, {name_expr} AS product_name, {price_expr} AS unit_price, {extra_expr} AS is_extra, {note_expr} AS note, {user_expr} AS user_id FROM "{source}"')).mappings()
    count = 0
    for row in rows:
        pid = product_map.get(row["product_id"]) if row["product_id"] is not None else None
        if pid is None and row["product_name"]:
            pid = db.session.scalar(text("SELECT id FROM products WHERE tenant_id=:t AND name=:n"), {"t": tenant, "n": str(row["product_name"]).strip()})
        if pid is None or row["date"] is None or row["quantity"] is None or float(row["quantity"]) <= 0:
            continue
        price = row["unit_price"]
        if price is None:
            price = db.session.scalar(text("SELECT current_price FROM products WHERE id=:p"), {"p": pid}) or 0
        entry_type = "extra" if bool(row["is_extra"]) else "regular"
        exists = db.session.scalar(text("SELECT id FROM daily_entries WHERE tenant_id=:t AND date=:d AND product_id=:p AND quantity=:q AND price_at_time=:price AND entry_type=:et"), {"t": tenant, "d": row["date"], "p": pid, "q": row["quantity"], "price": price, "et": entry_type})
        if exists:
            continue
        db.session.execute(text("INSERT INTO daily_entries (tenant_id,date,product_id,quantity,price_at_time,entry_type,notes,recorded_by) VALUES (:t,:d,:p,:q,:price,:et,:note,NULL)"), {"t": tenant, "d": row["date"], "p": pid, "q": row["quantity"], "price": price or 0, "et": entry_type, "note": row["note"]})
        count += 1
    return count


def _migrate_activity(tenant):
    source = _source("legacy_v1_activity_logs", "legacy_v1_activity_log", "activity_log")
    if not source:
        return 0
    cols = _cols(source)
    action_col = _col(cols, "action", "event")
    details_col = _col(cols, "details", "description")
    timestamp_col = _col(cols, "timestamp", "created_at")
    username_col = _col(cols, "username", "user")
    if not action_col:
        return 0
    details_expr = f'"{details_col}"' if details_col else "''"
    timestamp_expr = f'"{timestamp_col}"' if timestamp_col else "NULL"
    username_expr = f'"{username_col}"' if username_col else "'מערכת'"
    rows = db.session.execute(text(f'SELECT "{action_col}" AS action, {details_expr} AS details, {timestamp_expr} AS timestamp, {username_expr} AS username FROM "{source}"')).mappings()
    count = 0
    for row in rows:
        if not row["action"]:
            continue
        exists = db.session.scalar(text("SELECT id FROM activity_logs WHERE tenant_id=:t AND action=:a AND details=:d AND username=:u AND timestamp IS NOT DISTINCT FROM :ts"), {"t": tenant, "a": str(row["action"]), "d": str(row["details"] or ""), "u": str(row["username"] or "מערכת"), "ts": row["timestamp"]})
        if exists:
            continue
        db.session.execute(text("INSERT INTO activity_logs (tenant_id,timestamp,action,details,username) VALUES (:t,COALESCE(:ts,NOW()),:a,:d,:u)"), {"t": tenant, "ts": row["timestamp"], "a": str(row["action"]), "d": str(row["details"] or ""), "u": str(row["username"] or "מערכת")})
        count += 1
    return count


def recover():
    """Recover all known legacy datasets and return per-dataset counts."""
    results = {}
    tenant = _tenant()
    db.session.commit()

    stages = [
        ("users", lambda: _migrate_users(tenant)),
        ("products", lambda: _migrate_products(tenant)),
        ("history", None),
        ("daily_entries", None),
        ("activity_logs", lambda: _migrate_activity(tenant)),
    ]
    product_map = {}
    for name, fn in stages:
        try:
            if name == "history":
                value = _migrate_history(tenant, product_map)
            elif name == "daily_entries":
                value = _migrate_entries(tenant, product_map)
            else:
                value = fn()
                if name == "products":
                    value, product_map = value
            db.session.commit()
            results[name] = value
            print(f"[recovery] {name}: {value}", flush=True)
        except Exception as exc:
            db.session.rollback()
            results[name] = f"error: {exc!r}"
            print(f"[recovery] {name} failed: {exc!r}", flush=True)
    return results
