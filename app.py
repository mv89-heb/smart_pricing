"""Compatibility exports for older integrations.

The application is constructed directly from the canonical application factory;
no module imports wsgi as an owner.
"""
from smartpricing.app_factory import create_app
from smartpricing.extensions import db
from smartpricing.models import ActivityLog, BillingTemplate, BillingTemplateItem, DailyEntry, PeriodLock, PriceHistory, Product, User
from smartpricing.services.pricing import price_for_date, price_history_json
from smartpricing.utils import entry_json, entry_total, money, today_iso, valid_date, valid_month

app = create_app()
