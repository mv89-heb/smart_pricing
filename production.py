"""Single explicit production entrypoint for Smart Pricing.

The legacy WSGI modules remain importable for compatibility/tests, but the
production server now has one documented composition root.  API routes are
registered first; UI/admin helpers and the performance layer are then loaded
explicitly rather than through an import side effect inside api_routes.py.
"""

# Register the core API routes first.
import api_routes  # noqa: F401,E402

# Load the existing UI/admin extensions and performance layer explicitly.
import wsgi_ui  # noqa: F401,E402

app = wsgi_ui.app
