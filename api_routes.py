"""Backward-compatible shim - the API routes now live in smartpricing/routes/.
Kept so `import api_routes` (tests/conftest.py) still loads the full app."""
from wsgi import app  # noqa: F401
