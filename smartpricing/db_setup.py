"""Database bootstrap and one-way migration from the legacy Smart Pricing schema."""
from sqlalchemy import inspect, text
from werkzeug.security import generate_password_hash
from .extensions import db
from .models import Tenant, User


def _table_exists(name): return inspect(db.engine).has_table(name)
def _columns(name): return {c["name"] for c in inspect(db.engine).get_columns(name)} if _table_exists(name) else set()

def _rename_if_legacy(name, required):
    if not _table_exists(name) or set(required).issubset(_columns(name)): return
    legacy=f"legacy_v1_{name}"
    if not _table_exists(legacy): db.session.execute(text(f'ALTER TABLE "{name}" RENAME TO "{legacy}"'))


def bootstrap():
    _rename_if_legacy("product", {"name", "price"})
    _rename_if_legacy("users", {"tenant_id", "email", "password_hash"})
    _rename_if_legacy("daily_entries", {"tenant_id", "product_id", "price_at_time", "entry_type"})
    _rename_if_legacy("price_history", {"product_id", "effective_date", "changed_by"})
    _rename_if_legacy("period_locks", {"tenant_id", "year_month"})
    _rename_if_legacy("activity_logs", {"tenant_id", "action", "details"})
    _rename_if_legacy("billing_templates", {"tenant_id", "name"})
    _rename_if_legacy("billing_template_items", {"template_id", "product_id"})
    db.create_all(); _migrate_legacy_data(); _ensure_default_tenant_and_admin(); db.session.commit()


def _tenant():
    tenant=Tenant.query.order_by(Tenant.id).first()
    if not tenant:
        tenant=Tenant(name="Smart Pricing"); db.session.add(tenant); db.session.flush()
    return tenant


def _migrate_legacy_data():
    tenant=_tenant()
    if _table_exists("legacy_v1_users"):
        for r in db.session.execute(text('SELECT username,password,role FROM legacy_v1_users')).mappings():
            email=(r["username"] or "").strip().lower()
            if not email: continue
            if "@" not in email: email=f"{email}@legacy.local"
            if not db.session.scalar(text('SELECT id FROM users WHERE tenant_id=:t AND email=:e'), {"t":tenant.id,"e":email}):
                role={"admin":"admin","editor":"editor","viewer":"viewer"}.get((r["role"] or "viewer").lower(), "viewer")
                db.session.execute(text('INSERT INTO users (tenant_id,email,name,password_hash,role,is_active) VALUES (:t,:e,:n,:p,:r,1)'), {"t":tenant.id,"e":email,"n":r["username"],"p":r["password"],"r":role})
    product_map={}
    if _table_exists("legacy_v1_product"):
        for r in db.session.execute(text('SELECT id,name,price,tag FROM legacy_v1_product ORDER BY id')).mappings():
            pid=db.session.scalar(text('SELECT id FROM products WHERE tenant_id=:t AND name=:n'), {"t":tenant.id,"n":r["name"]})
            if not pid:
                db.session.execute(text('INSERT INTO products (tenant_id,sku,name,category,unit,current_price,is_active) VALUES (:t,:sku,:n,:c,:u,:p,1)'), {"t":tenant.id,"sku":f"LEG-{r['id']}","n":r["name"],"c":r["tag"] or "כללי","u":"יחידות","p":r["price"] or 0})
                pid=db.session.scalar(text('SELECT id FROM products WHERE tenant_id=:t AND name=:n'), {"t":tenant.id,"n":r["name"]})
            product_map[r["id"]]=pid
    admin_id=db.session.scalar(text('SELECT id FROM users WHERE tenant_id=:t ORDER BY id LIMIT 1'), {"t":tenant.id})
    if _table_exists("legacy_v1_price_history"):
        for r in db.session.execute(text('SELECT product_id,price,effective_from,changed_at,changed_by FROM legacy_v1_price_history')).mappings():
            pid=product_map.get(r["product_id"])
            if not pid: continue
            eff=r["effective_from"] or "2026-01-01"
            if not db.session.scalar(text('SELECT id FROM price_history WHERE product_id=:p AND effective_date=:d'), {"p":pid,"d":eff}):
                db.session.execute(text('INSERT INTO price_history (product_id,price,effective_date,changed_at,changed_by) VALUES (:p,:price,:d,:at,:by)'), {"p":pid,"price":r["price"],"d":eff,"at":r["changed_at"],"by":r["changed_by"] or "מערכת"})
    if _table_exists("legacy_v1_daily_entries"):
        for r in db.session.execute(text('SELECT date,product_name,quantity,is_extra,unit_price,note FROM legacy_v1_daily_entries')).mappings():
            pid=db.session.scalar(text('SELECT id FROM products WHERE tenant_id=:t AND name=:n'), {"t":tenant.id,"n":r["product_name"]})
            if not pid: continue
            price=r["unit_price"] if r["unit_price"] is not None else db.session.scalar(text('SELECT current_price FROM products WHERE id=:p'), {"p":pid})
            db.session.execute(text('INSERT INTO daily_entries (tenant_id,date,product_id,quantity,price_at_time,entry_type,notes,recorded_by) VALUES (:t,:d,:p,:q,:price,:type,:note,:u)'), {"t":tenant.id,"d":r["date"],"p":pid,"q":r["quantity"],"price":price or 0,"type":"extra" if r["is_extra"] else "regular","note":r["note"],"u":admin_id})


def _ensure_default_tenant_and_admin():
    tenant=_tenant()
    if not User.query.filter_by(tenant_id=tenant.id).first(): db.session.add(User(tenant_id=tenant.id,email="admin@smartpricing.local",name="מנהל מערכת",password_hash=generate_password_hash("admin123"),role="admin",is_active=True))
