from datetime import date, datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import CheckConstraint, Index, UniqueConstraint

from .extensions import db


def israel_now():
    return datetime.now(ZoneInfo("Asia/Jerusalem"))


def israel_date():
    return israel_now().date()


class Tenant(db.Model):
    __tablename__ = "tenants"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    email = db.Column(db.String(160), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="viewer")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    tenant = db.relationship("Tenant", backref=db.backref("users", lazy=True, cascade="all, delete-orphan"))
    __table_args__ = (UniqueConstraint("tenant_id", "email", name="uq_user_tenant_email"),)


class Product(db.Model):
    __tablename__ = "products"
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    sku = db.Column(db.String(60), nullable=True)
    name = db.Column(db.String(140), nullable=False)
    category = db.Column(db.String(80), nullable=False, default="כללי")
    unit = db.Column(db.String(30), nullable=False, default="יחידות")
    current_price = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    tenant = db.relationship("Tenant", backref=db.backref("products", lazy=True, cascade="all, delete-orphan"))
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_product_tenant_name"), Index("ix_product_tenant_category", "tenant_id", "category"))


class PriceHistory(db.Model):
    __tablename__ = "price_history"
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    price = db.Column(db.Numeric(12, 2), nullable=False)
    effective_date = db.Column(db.Date, nullable=False, index=True)
    changed_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    changed_by = db.Column(db.String(120), nullable=False, default="מערכת")
    product = db.relationship("Product", backref=db.backref("price_history", lazy="dynamic", cascade="all, delete-orphan"))
    __table_args__ = (UniqueConstraint("product_id", "effective_date", name="uq_price_product_date"), Index("ix_price_product_date_desc", "product_id", "effective_date"))


class DailyEntry(db.Model):
    __tablename__ = "daily_entries"
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, default=israel_date, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True)
    quantity = db.Column(db.Numeric(12, 2), nullable=False)
    price_at_time = db.Column(db.Numeric(12, 2), nullable=False)
    entry_type = db.Column(db.String(20), nullable=False, default="regular", index=True)
    notes = db.Column(db.Text, nullable=True)
    recorded_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    product = db.relationship("Product")
    recorder = db.relationship("User")
    __table_args__ = (CheckConstraint("quantity > 0", name="ck_daily_quantity_positive"), CheckConstraint("entry_type in ('regular','extra','special')", name="ck_daily_entry_type"), Index("ix_entry_tenant_date", "tenant_id", "date"))


class PeriodLock(db.Model):
    __tablename__ = "period_locks"
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    year_month = db.Column(db.String(7), nullable=False)
    locked = db.Column(db.Boolean, nullable=False, default=False)
    locked_at = db.Column(db.DateTime, nullable=True)
    locked_by = db.Column(db.String(120), nullable=True)
    __table_args__ = (UniqueConstraint("tenant_id", "year_month", name="uq_lock_tenant_period"),)


class ActivityLog(db.Model):
    __tablename__ = "activity_logs"
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), index=True)
    action = db.Column(db.String(60), nullable=False)
    details = db.Column(db.String(1200), nullable=False, default="")
    username = db.Column(db.String(120), nullable=False, default="מערכת")


class BillingTemplate(db.Model):
    __tablename__ = "billing_templates"
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    items = db.relationship("BillingTemplateItem", backref="template", cascade="all, delete-orphan", lazy=True)
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_template_tenant_name"),)


class BillingTemplateItem(db.Model):
    __tablename__ = "billing_template_items"
    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(db.Integer, db.ForeignKey("billing_templates.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    quantity = db.Column(db.Numeric(12, 2), nullable=False)
    is_extra = db.Column(db.Boolean, nullable=False, default=False)
    product = db.relationship("Product")
