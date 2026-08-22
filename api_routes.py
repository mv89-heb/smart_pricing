"""Backward-compatible API shim.

API routes are registered by smartpricing.app_factory; this module exists only
for integrations that still import api_routes.
"""
from smartpricing.app_factory import create_app

app = create_app()
