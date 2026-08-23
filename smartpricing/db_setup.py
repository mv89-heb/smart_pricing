"""Database bootstrap and safe one-way migration from legacy Smart Pricing schemas."""
from sqlalchemy import inspect, text
from werkzeug.security import generate_password_hash

from .extensions import db
from .models import Tenant, User

_PASSWORD_HASH_PREFIXES = ("scrypt:", "pbkdf2:", "argon2:")


def _table_exists(name):
    return inspect(db.engine).has_table(name)


def _columns(name):
    return {c["name"] for c in inspect(db.engine).get_columns(name)} if _table_exists(name) else set()


def _has_rows(name):
    return bool(_table_exists(name) and db.session.scalar(text(f'SELECT 1 FROM "{name}" LIMIT 1')))


def _rename_if_legacy(name, required):
    if not _table_exists(name):
        return
    if set(required).issubset(_columns(name)):
        return
    legacy = f"legacy_v1_{name}"
    if not _table_exists(legacy):
        db.session.execute(text(f'ALTER TABLE "{name}" RENAME TO "{legacy}"'))


def _rename_populated_singular_sources():
    """The pre-rebuild application used singular table names.

    The previous migration only renamed malformed tables. That was incorrect for
    valid legacy tables such as ``product`` and ``daily_entry``: they were valid
    tables, so they were left untouched and their rows were never migrated.
    If the corresponding new plural table is present and empty, preserve the
    singular table as an explicit legacy source. This is intentionally one-way
    and never drops data.
    """
    pairs = (
        ("user", "users"),
        ("product", "products"),
        ("daily_entry", "daily_entries"),
        ("billing_template", "billing_templates"),
        ("billing_template_item", "billing_template_items"),
        ("period_lock", "period_locks"),
        ("activity_log", "activity_logs"),
    )
    for old, new in pairs:
        legacy = f"legacy_v1_{old}"
        if _table_exists(old) and _has_rows(old) and _table_exists(new) and not _has_rows(new) and not _table_exists(legacy):
            db.session.execute(text(f'ALTER TABLE "{old}" RENAME TO "{legacy}"'))


def _normalize_legacy_table_names():
    _rename_populated_singular_sources()
    if _table_exists("products") and not {"tenant_id", "name", "current_price"}.issubset(_columns("products")):
        if not _table_exists("legacy_v1_products"):
            db.session.execute(text('ALTER TABLE "products" RENAME TO "legacy_v1_products"'))
    _rename_if_legacy("product", {"name", "price"})
    _rename_if_legacy("users", {"tenant_id", "email", "password_hash"})
    _rename_if_legacy("daily_entries", {"tenant_id", "product_id", "price_at_time", "entry_type"})
    _rename_if_legacy("price_history", {"product_id", "effective_date", "changed_by"})
    _rename_if_legacy("period_locks", {"tenant_id", "year_month"})
    _rename_if_legacy("activity_logs", {"tenant_id", "action", "details"})
    _rename_if_legacy("billing_templates", {"tenant_id", "name"})
    _rename_if_legacy("billing_template_items", {"template_id", "product_id"})


def _looks_hashed(value):
    return isinstance(value, str) and value.startswith(_PASSWORD_HASH_PREFIXES)


def _ensure_password_hash(value):
    value = "" if value is None else str(value)
    return value if _looks_hashed(value) else generate_password_hash(value)


def _create_all_idempotent():
    indexes = []
    for table in db.metadata.tables.values():
        for index in list(table.indexes):
            indexes.append(index)
            table.indexes.remove(index)
    try:
        db.create_all()
    finally:
        for index in indexes:
            index.table.indexes.add(index)
    for index in indexes:
        table_name = index.table.name
        index_name = index.name
        columns = ", ".join(f'"{column.name}"' for column in index.columns)
        unique = "UNIQUE " if index.unique else ""
        db.session.execute(text(f'CREATE {unique}INDEX IF NOT EXISTS "{index_name}" ON "{table_name}" ({columns})'))


def bootstrap():
    _normalize_legacy_table_names()
    _create_all_idempotent()
    _migrate_legacy_data()
    _ensure_default_tenant_and_admin()
    _repair_unhashed_users()
    db.session.commit()


def _tenant():
    tenant = Tenant.query.order_by(Tenant.id).first()
    if not tenant:
        tenant = Tenant(name="Smart Pricing")
        db.session.add(tenant)
        db.session.flush()
    return tenant


def _legacy_table(*names):
    for name in names:
        if _table_exists(name):
            return name
    return None


def _migrate_legacy_data():
    tenant = _tenant()

    user_map = {}
    users_table = _legacy_table("legacy_v1_users", "legacy_v1_user")
    if users_table:
        cols = _columns(users_table)
        username_col = "username" if "username" in cols else "email"
        password_col = "password_hash" if "password_hash" in cols else ("password" if "password" in cols else None)
        role_col = "role" if "role" in cols else None
        if password_col:
            role_sql = f'"{role_col}"' if role_col else "'viewer'"
            for r in db.session.execute(text(f'SELECT id,"{username_col}" AS username,"{password_col}" AS password,{role_sql} AS role FROM "{users_table}"')).mappings():
                username = (r["username"] or "").strip()
                if not username:
                    continue
                email = username.lower() if "@" in username else f"{username.lower()}@legacy.local"
                existing = db.session.scalar(text('SELECT id FROM users WHERE tenant_id=:t AND email=:e'), {"t": tenant.id, "e": email})
                if existing:
                    user_map[r["id"]] = existing
                    continue
                role = {"admin": "admin", "editor": "editor", "viewer": "viewer"}.get((r["role"] or "viewer").lower(), "viewer")
                new_id = db.session.execute(text('INSERT INTO users (tenant_id,email,name,password_hash,role,is_active) VALUES (:t,:e,:n,:p,:r,1) RETURNING id'), {"t": tenant.id, "e": email, "n": username, "p": _ensure_password_hash(r["password"]), "r": role}).scalar_one()
                user_map[r["id"]] = new_id

    product_map = {}
    product_table = _legacy_table("legacy_v1_products", "legacy_v1_product")
    if product_table:
        cols = _columns(product_table)
        price_col = "current_price" if "current_price" in cols else ("price" if "price" in cols else None)
        if price_col:
            category_col = "category" if "category" in cols else ("tag" if "tag" in cols else None)
            sku_col = "sku" if "sku" in cols else None
            unit_col = "unit" if "unit" in cols else None
            category_sql = f',"{category_col}" AS category' if category_col else ',NULL AS category'
            sku_sql = f',"{sku_col}" AS sku' if sku_col else ',NULL AS sku'
            unit_sql = f',"{unit_col}" AS unit' if unit_col else ',NULL AS unit'
            for r in db.session.execute(text(f'SELECT id,name,"{price_col}" AS price{category_sql}{sku_sql}{unit_sql} FROM "{product_table}" ORDER BY id')).mappings():
                if not r["name"]:
                    continue
                pid = db.session.scalar(text('SELECT id FROM products WHERE tenant_id=:t AND name=:n'), {"t": tenant.id, "n": r["name"]})
                if not pid:
                    pid = db.session.execute(text('INSERT INTO products (tenant_id,sku,name,category,unit,current_price,is_active) VALUES (:t,:sku,:n,:c,:u,:p,1) RETURNING id'), {"t": tenant.id, "sku": r["sku"] or f"LEG-{r['id']}", "n": r["name"], "c": r["category"] or "כללי", "u": r["unit"] or "יחידות", "p": r["price"] or 0}).scalar_one()
                product_map[r["id"]] = pid

    history_table = _legacy_table("legacy_v1_price_history")
    if history_table:
        cols = _columns(history_table)
        price_col = "price" if "price" in cols else None
        date_col = "effective_from" if "effective_from" in cols else ("effective_date" if "effective_date" in cols else None)
        changed_at_col = "changed_at" if "changed_at" in cols else None
        changed_by_col = "changed_by" if "changed_by" in cols else None
        if price_col and date_col:
            at_sql = f',"{changed_at_col}" AS changed_at' if changed_at_col else ',NULL AS changed_at'
            by_sql = f',"{changed_by_col}" AS changed_by' if changed_by_col else ',NULL AS changed_by'
            for r in db.session.execute(text(f'SELECT product_id,"{price_col}" AS price,"{date_col}" AS effective_date{at_sql}{by_sql} FROM "{history_table}"')).mappings():
                pid = product_map.get(r["product_id"])
                if not pid:
                    pid = db.session.scalar(text('SELECT id FROM products WHERE tenant_id=:t AND id=:p'), {"t": tenant.id, "p": r["product_id"]})
                if not pid or r["effective_date"] is None:
                    continue
                if not db.session.scalar(text('SELECT id FROM price_history WHERE product_id=:p AND effective_date=:d'), {"p": pid, "d": r["effective_date"]}):
                    db.session.execute(text('INSERT INTO price_history (product_id,price,effective_date,changed_at,changed_by) VALUES (:p,:price,:d,:at,:by)'), {"p": pid, "price": r["price"] or 0, "d": r["effective_date"], "at": r["changed_at"], "by": r["changed_by"] or "מערכת"})

    entries_table = _legacy_table("legacy_v1_daily_entries", "legacy_v1_daily_entry")
    if entries_table:
        cols = _columns(entries_table)
        product_name_col = "product_name" if "product_name" in cols else None
        product_id_col = "product_id" if "product_id" in cols else None
        date_col = "date" if "date" in cols else ("entry_date" if "entry_date" in cols else None)
        qty_col = "quantity" if "quantity" in cols else ("qty" if "qty" in cols else None)
        price_col = "unit_price" if "unit_price" in cols else ("price_at_time" if "price_at_time" in cols else None)
        extra_col = "is_extra" if "is_extra" in cols else None
        note_col = "note" if "note" in cols else ("notes" if "notes" in cols else None)
        user_col = "recorded_by" if "recorded_by" in cols else ("user_id" if "user_id" in cols else None)
        if date_col and qty_col:
            product_expr = f'"{product_name_col}" AS product_name' if product_name_col else 'NULL AS product_name'
            product_id_expr = f',"{product_id_col}" AS product_id' if product_id_col else ',NULL AS product_id'
            price_expr = f',"{price_col}" AS unit_price' if price_col else ',NULL AS unit_price'
            extra_expr = f',"{extra_col}" AS is_extra' if extra_col else ',0 AS is_extra'
            note_expr = f',"{note_col}" AS note' if note_col else ',NULL AS note'
            user_expr = f',"{user_col}" AS user_id' if user_col else ',NULL AS user_id'
            for r in db.session.execute(text(f'SELECT "{date_col}" AS date,{product_expr}{product_id_expr},"{qty_col}" AS quantity{price_expr}{extra_expr}{note_expr}{user_expr} FROM "{entries_table}"')).mappings():
                pid = product_map.get(r["product_id"]) if r["product_id"] is not None else None
                if not pid and r["product_name"]:
                    pid = db.session.scalar(text('SELECT id FROM products WHERE tenant_id=:t AND name=:n'), {"t": tenant.id, "n": r["product_name"]})
                if not pid or r["date"] is None or r["quantity"] is None:
                    continue
                price = r["unit_price"]
                if price is None:
                    price = db.session.scalar(text('SELECT current_price FROM products WHERE id=:p'), {"p": pid}) or 0
                recorded_by = user_map.get(r["user_id"]) if r["user_id"] is not None else None
                entry_type = "extra" if r["is_extra"] else "regular"
                exists = db.session.scalar(text('SELECT id FROM daily_entries WHERE tenant_id=:t AND date=:d AND product_id=:p AND quantity=:q AND price_at_time=:price AND entry_type=:et'), {"t": tenant.id, "d": r["date"], "p": pid, "q": r["quantity"], "price": price, "et": entry_type})
                if not exists:
                    db.session.execute(text('INSERT INTO daily_entries (tenant_id,date,product_id,quantity,price_at_time,entry_type,notes,recorded_by) VALUES (:t,:d,:p,:q,:price,:type,:note,:u)'), {"t": tenant.id, "d": r["date"], "p": pid, "q": r["quantity"], "price": price, "type": entry_type, "note": r["note"], "u": recorded_by})

    locks_table = _legacy_table("legacy_v1_period_locks", "legacy_v1_period_lock")
    if locks_table:
        cols = _columns(locks_table)
        ym_col = "year_month" if "year_month" in cols else ("month" if "month" in cols else None)
        if ym_col:
            locked_col = "locked" if "locked" in cols else None
            locked_at_col = "locked_at" if "locked_at" in cols else None
            locked_by_col = "locked_by" if "locked_by" in cols else None
            l_sql = f',"{locked_col}" AS locked' if locked_col else ',1 AS locked'
            la_sql = f',"{locked_at_col}" AS locked_at' if locked_at_col else ',NULL AS locked_at'
            lb_sql = f',"{locked_by_col}" AS locked_by' if locked_by_col else ',NULL AS locked_by'
            for r in db.session.execute(text(f'SELECT "{ym_col}" AS year_month{l_sql}{la_sql}{lb_sql} FROM "{locks_table}"')).mappings():
                if r["year_month"] and not db.session.scalar(text('SELECT id FROM period_locks WHERE tenant_id=:t AND year_month=:ym'), {"t": tenant.id, "ym": str(r["year_month"])[:7]}):
                    db.session.execute(text('INSERT INTO period_locks (tenant_id,year_month,locked,locked_at,locked_by) VALUES (:t,:ym,:locked,:at,:by)'), {"t": tenant.id, "ym": str(r["year_month"])[:7], "locked": bool(r["locked"]), "at": r["locked_at"], "by": r["locked_by"]})

    activity_table = _legacy_table("legacy_v1_activity_logs", "legacy_v1_activity_log")
    if activity_table:
        cols = _columns(activity_table)
        action_col = "action" if "action" in cols else ("event" if "event" in cols else None)
        details_col = "details" if "details" in cols else ("description" if "description" in cols else None)
        timestamp_col = "timestamp" if "timestamp" in cols else ("created_at" if "created_at" in cols else None)
        username_col = "username" if "username" in cols else ("user" if "user" in cols else None)
        if action_col:
            details_sql = f',"{details_col}" AS details' if details_col else ',NULL AS details'
            ts_sql = f',"{timestamp_col}" AS timestamp' if timestamp_col else ',NULL AS timestamp'
            un_sql = f',"{username_col}" AS username' if username_col else ',NULL AS username'
            for r in db.session.execute(text(f'SELECT "{action_col}" AS action{details_sql}{ts_sql}{un_sql} FROM "{activity_table}"')).mappings():
                if r["action"]:
                    exists = db.session.scalar(text('SELECT id FROM activity_logs WHERE tenant_id=:t AND action=:a AND details=:d AND username=:u'), {"t": tenant.id, "a": r["action"], "d": r["details"] or "", "u": r["username"] or "מערכת"})
                    if not exists:
                        db.session.execute(text('INSERT INTO activity_logs (tenant_id,timestamp,action,details,username) VALUES (:t,:ts,:a,:d,:u)'), {"t": tenant.id, "ts": r["timestamp"], "a": r["action"], "d": r["details"] or "", "u": r["username"] or "מערכת"})


def _repair_unhashed_users():
    for user in db.session.scalars(db.select(User)).all():
        if not _looks_hashed(user.password_hash):
            user.password_hash = generate_password_hash(user.password_hash or "")


def _ensure_default_tenant_and_admin():
    tenant = _tenant()
    if not User.query.filter_by(tenant_id=tenant.id).first():
        db.session.add(User(tenant_id=tenant.id, email="admin@smartpricing.local", name="admin", password_hash=generate_password_hash("admin123"), role="admin", is_active=True))
