"""Backward-compatible shim.

The application used to be built directly in this file. It now lives in the
smartpricing/ package (see wsgi.py for the real entrypoint); this module just
re-exports the same names so existing code/tests that do
`from app import app, db, Product, ...` keep working unchanged.
"""
from wsgi import app  # noqa: F401  (builds/returns the single shared app instance)

from smartpricing.extensions import db  # noqa: F401
from smartpricing.models import (  # noqa: F401
    ActivityLog, BillingTemplate, BillingTemplateItem, DailyEntry, PeriodLock, PriceHistory, Product, User,
)
from smartpricing.services.pricing import price_for_date, price_history_json  # noqa: F401
from smartpricing.utils import entry_json, entry_total, money, today_iso, valid_date, valid_month  # noqa: F401
