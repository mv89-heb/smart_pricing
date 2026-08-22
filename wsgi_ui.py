"""Backward-compatible shim - UI/system routes now live in smartpricing/routes/.
Kept so `from wsgi_ui import app` (tests) still works, exposing the same
`User`/`admin_access` names those tests import."""
from wsgi import app  # noqa: F401

from smartpricing.models import User  # noqa: F401
from smartpricing.security import admin_access  # noqa: F401
