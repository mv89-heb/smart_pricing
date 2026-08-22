"""Database models. Schema is unchanged from the original application -
existing SQLite/PostgreSQL databases keep working with these definitions."""
from datetime import datetime

from sqlalchemy import Numeric

from .extensions import db


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    price = db.Column(Numeric(12, 2), nullable=False)
    tag = db.Column(db.String(80), nullable=True)


class DailyEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(10), nullable=False, index=True)
    product_name = db.Column(db.String(100), nullable=False, index=True)
    quantity = db.Column(db.Float, nullable=False)
    is_extra = db.Column(db.Boolean, default=False, nullable=False, index=True)
    unit_price = db.Column(Numeric(12, 2), nullable=True)
    total_amount = db.Column(Numeric(14, 2), nullable=True)
    note = db.Column(db.String(255), nullable=True)


class PriceHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id", ondelete="CASCADE"), nullable=False, index=True)
    price = db.Column(Numeric(12, 2), nullable=False)
    effective_from = db.Column(db.String(10), nullable=True, index=True)
    changed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    changed_by = db.Column(db.String(100), default="מערכת", nullable=False)


class PeriodLock(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    year_month = db.Column(db.String(7), unique=True, nullable=False, index=True)
    locked = db.Column(db.Boolean, default=False, nullable=False)
    locked_at = db.Column(db.DateTime, nullable=True)
    locked_by = db.Column(db.String(100), nullable=True)


class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    action = db.Column(db.String(50), nullable=False)
    details = db.Column(db.String(1000), nullable=False)
    username = db.Column(db.String(100), default="מערכת")


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="viewer")


class BillingTemplate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    items = db.relationship("BillingTemplateItem", backref="template", cascade="all, delete-orphan")


class BillingTemplateItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(db.Integer, db.ForeignKey("billing_template.id"), nullable=False)
    product_name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    is_extra = db.Column(db.Boolean, default=False)
