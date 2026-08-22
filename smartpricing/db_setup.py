"""Database bootstrap and one-way migration from the legacy Smart Pricing schema.
Never deletes the application database. Legacy tables are renamed with a legacy_v1_ prefix,
then data is copied into the clean tenant-aware schema.
"""
from sqlalchemy import inspect, text
from werkzeug.security import generate_password_hash

from .extensions import db
from .models import Tenant, User


def _table_exists(name):
    return inspect(db.engine).has_table(name)


def _columns(name):
    return {c["name"] for c in inspect(db.engine).get_columns(name)} if _table_exists(name) else set()


def _rename_if_legacy(name, required_columns):
    if not _table_exists(name):
        return False
    cols = _columns(name)
    if required_columns.issubset(cols):
        return False
    legacy = f"legacy_v1_{name}"
    if not _table_exists(legacy):
        db.session.execute(text(f'ALTER TABLE "{name}" RENAME TO "{legacy}"'))
        return True
    return False


def bootstrap():
    # Detect and isolate incompatible pre-v2 tables before create_all().
    _rename_if_legacy("users", {"tenant_id", "email", "password_hash"})
    _rename_if_legacy("daily_entries", {"tenant_id", "product_id", "price_at_time", "entry_type"})
    _rename_if_legacy("price_history", {"product_id", "effective_date", "changed_by"})
    _rename_if_legacy("period_locks", {"tenant_id", "year_month"})
    _rename_if_legacy("activity_logs", {"tenant_id", "action", "details"})
    _rename_if_legacy("billing_templates", {"tenant_id", "name"})
    _rename_if_legacy("billing_template_items", {"template_id", "product_id"})

    db.create_all()
    _migrate_legacy_data()
    _ensure_default_tenant_and_admin()
    db.session.commit()


def _migrate_legacy_data():
    if not _table_exists("legacy_v1_product") and not _table_exists("legacy_v1_daily_entries"):
        return

    tenant = Tenant.query.order_by(Tenant.id).first()
    if not tenant:
        tenant = Tenant(name="Smart Pricing")
        db.session.add(tenant)
        db.session.flush()

    product_map = {}
    if _table_exists("legacy_v1_product"):
        rows = db.session.execute(text('SELECT id, name, price, tag FROM legacy_v1_product ORDER BY id')).mappings()
        for row in rows:
            existing = db.session.execute(text('SELECT id FROM products WHERE tenant_id=:t AND name=:n'), {"t": tenant.id, "n": row["name"]}).scalar()
            if existing:
                product_map[row["id"]] = existing
                continue
            result = db.session.execute(text('INSERT INTO products (tenant_id, sku, name, category, unit, current_price, is_active) VALUES (:t,:sku,:n,:c,:u,:p,:a)'), {"t": tenant.id, "sku": f"LEG-{row['id']}", "n": row["name"], "c": row["tag"] or "כללי", "u": "יחידות", "p": row["price"] or 0, "a": True})
            new_id = db.session.execute(text('SELECT id FROM products WHERE tenant_id=:t AND name=:n'), {"t": tenant.id, "n": row["name"]}).scalar()
            product_map[row["id"]] = new_id

    admin_id = User.query.filter_by(tenant_id=tenant.id).order_by(User.id).with_entities(User.id).first()
    admin_id = admin_id[0] if admin_id else None

    if _table_exists("legacy_v1_price_history"):
        for row in db.session.execute(text('SELECT ph.product_id, ph.price, ph.effective_from, ph.changed_at, ph.changed_by FROM legacy_v1_price_history ph')).mappings():
            pid = product_map.get(row["product_id"])
            if not pid:
                continue
            eff = row["effective_from"] or "2026-01-01"
            exists = db.session.execute(text('SELECT id FROM price_history WHERE product_id=:p AND effective_date=:d'), {"p": pid, "d": eff}).scalar()
            if not exists:
                db.session.execute(text('INSERT INTO price_history (product_id, price, effective_date, changed_at, changed_by) VALUES (:p,:price,:d,:at,:by)'), {"p": pid, "price": row["price"], "d": eff, "at": row["changed_at"], "by": row["changed_by"] or "מערכת"})

    if _table_exists("legacy_v1_daily_entries"):
        rows = db.session.execute(text('SELECT date, product_name, quantity, is_extra, unit_price, total_amount, note FROM legacy_v1_daily_entries')).mappings()
        for row in rows:
            pid = db.session.execute(text('SELECT id FROM products WHERE tenant_id=:t AND name=:n'), {"t": tenant.id, "n": row["product_name"]}).scalar()
            if not pid:
                continue
            price = row["unit_price"] if row["unit_price"] is not None else db.session.execute(text('SELECT current_price FROM products WHERE id=:p'), {"p": pid}).scalar()
            db.session.execute(text('INSERT INTO daily_entries (tenant_id, date, product_id, quantity, price_at_time, entry_type, notes, recorded_by) VALUES (:t,:d,:p,:q,:price,:type,:note,:u)'), {"t": tenant.id, "d": row["date"], "p": pid, "q": row["quantity"], "price": price or 0, "type": "extra" if row["is_extra"] else "regular", "note": row["note"], "u": admin_id})


def _ensure_default_tenant_and_admin():
    tenant = Tenant.query.order_by(Tenant.id).first()
    if not tenant:
        tenant = Tenant(name="Smart Pricing")
        db.session.add(tenant)
        db.session.flush()
    if not User.query.filter_by(tenant_id=tenant.id).first():
        db.session.add(User(tenant_id=tenant.id, email="admin@smartpricing.local", name="מנהל מערכת", password_hash=generate_password_hash("admin123"), role="admin", is_active=True))
