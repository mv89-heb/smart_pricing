"""Backward-compatible UI/system shim.

The canonical app is built directly from smartpricing.app_factory.
"""
from smartpricing.app_factory import create_app
from smartpricing.models import User
from smartpricing.security import admin_access

app = create_app()
