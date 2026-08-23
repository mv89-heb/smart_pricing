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


def _rename_if_legacy(name, required):
    if not _table_exists(name) or set(required).issubset(_columns(name)):
        return
    legacy = f"legacy_v1_{name}"
    if not _table_exists(legacy):
        db.session.execute(text(f'ALTER TABLE "{name}" RENAME TO "{legacy}"'))


def _normalize_legacy_table_names():
    # The rebuild introduced a plural products table. Older releases could
    # already have a products/product table with the old schema. Never query
    # that table as the new schema until it has been moved aside.
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


def bootstrap():
    _normalize_legacy_table_names()
    db.create_all()
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

    users_table = _legacy_table("legacy_v1_users")
    if users_table:
        cols = _columns(users_table)
        username_col = "username" if "username" in cols else "email"
        password_col = "password_hash" if "password_hash" in cols else "password"
        for r in db.session.execute(text(f'SELECT "{username_col}" AS username, "{password_col}" AS password, role FROM "{users_table}"')).mappings():
            username = (r["username"] or "").strip()
            if not username:
                continue
            email = username.lower() if "@" in username else f"{username.lower()}@legacy.local"
            if not db.session.scalar(text('SELECT id FROM users WHERE tenant_id=:t AND email=:e'), {"t": tenant.id, "e": email}):
                role = {"admin": "admin", "editor": "editor", "viewer": "viewer"}.get((r["role"] or "viewer").lower(), "viewer")
                db.session.execute(text('INSERT INTO users (tenant_id,email,name,password_hash,role,is_active) VALUES (:t,:e,:n,:p,:r,1)'), {"t": tenant.id, "e": email, "n": username, "p": _ensure_password_hash(r["password"]), "r": role})

    product_table = _legacy_table("legacy_v1_products", "legacy_v1_product")
    product_map = {}
    if product_table:
        cols = _columns(product_table)
        price_col = "current_price" if "current_price" in cols else "price"
        category_col = "category" if "category" in cols else ("tag" if "tag" in cols else None)
        category_sql = f',"{category_col}" AS category' if category_col else ',NULL AS category'
        for r in db.session.execute(text(f'SELECT id,name,"{price_col}" AS price{category_sql} FROM "{product_table}" ORDER BY id')).mappings():
            pid = db.session.scalar(text('SELECT id FROM products WHERE tenant_id=:t AND name=:n'), {"t": tenant.id, "n": r["name"]})
            if not pid:
                db.session.execute(text('INSERT INTO products (tenant_id,sku,name,category,unit,current_price,is_active) VALUES (:t,:sku,:n,:c,:u,:p,1)'), {"t": tenant.id, "sku": f"LEG-{r['id']}", "n": r["name"], "c": r["category"] or "כללי", "u": "יחידות", "p": r["price"] or 0})
                pid = db.session.scalar(text('SELECT id FROM products WHERE tenant_id=:t AND name=:n'), {"t": tenant.id, "n": r["name"]})
            product_map[r["id"]] = pid

    admin_id = db.session.scalar(text('SELECT id FROM users WHERE tenant_id=:t ORDER BY id LIMIT 1'), {"t": tenant.id})

    history_table = _legacy_table("legacy_v1_price_history")
    if history_table:
        for r in db.session.execute(text(f'SELECT product_id,price,effective_from,changed_at,changed_by FROM "{history_table}"')).mappings():
            pid = product_map.get(r["product_id"])
            if not pid:
                pid = db.session.scalar(text('SELECT id FROM products WHERE tenant_id=:t AND id=:p'), {"t": tenant.id, "p": r["product_id"]})
            if not pid:
                continue
            eff = r["effective_from"] or "2026-01-01"
            if not db.session.scalar(text('SELECT id FROM price_history WHERE product_id=:p AND effective_date=:d'), {"p": pid, "d": eff}):
                db.session.execute(text('INSERT INTO price_history (product_id,price,effective_date,changed_at,changed_by) VALUES (:p,:price,:d,:at,:by)'), {"p": pid, "price": r["price"], "d": eff, "at": r["changed_at"], "by": r["changed_by"] or "מערכת"})

    entries_table = _legacy_table("legacy_v1_daily_entries")
    if entries_table:
        cols = _columns(entries_table)
        extra_sql = '"is_extra"' if "is_extra" in cols else '0'
        note_sql = '"note"' if "note" in cols else ('"notes"' if "notes" in cols else 'NULL')
        for r in db.session.execute(text(f'SELECT date,product_name,quantity,{extra_sql} AS is_extra,unit_price,{note_sql} AS note FROM "{entries_table}"')).mappings():
            pid = db.session.scalar(text('SELECT id FROM products WHERE tenant_id=:t AND name=:n'), {"t": tenant.id, "n": r["product_name"]})
            if not pid:
                continue
            price = r["unit_price"] if r["unit_price"] is not None else db.session.scalar(text('SELECT current_price FROM products WHERE id=:p'), {"p": pid})
            db.session.execute(text('INSERT INTO daily_entries (tenant_id,date,product_id,quantity,price_at_time,entry_type,notes,recorded_by) VALUES (:t,:d,:p,:q,:price,:type,:note,:u)'), {"t": tenant.id, "d": r["date"], "p": pid, "q": r["quantity"], "price": price or 0, "type": "extra" if r["is_extra"] else "regular", "note": r["note"], "u": admin_id})


def _repair_unhashed_users():
    for user in db.session.scalars(db.select(User)).all():
        if not _looks_hashed(user.password_hash):
            user.password_hash = generate_password_hash(user.password_hash or "")


def _ensure_default_tenant_and_admin():
    tenant = _tenant()
    if not User.query.filter_by(tenant_id=tenant.id).first():
        db.session.add(User(tenant_id=tenant.id, email="admin@smartpricing.local", name="admin", password_hash=generate_password_hash("admin123"), role="admin", is_active=True))
