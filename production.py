"""Single explicit production entrypoint for Smart Pricing.

Composition order is deliberate:
1. core API routes
2. compatibility routes
3. UI/admin extensions
4. WSGI infrastructure (health middleware + safe indexes)

No application module imports another WSGI layer implicitly.
"""

import api_routes  # noqa: F401,E402
import services.legacy_compat  # noqa: F401,E402
import wsgi_ui  # noqa: F401,E402
import wsgi as infrastructure  # noqa: F401,E402

app = wsgi_ui.app
