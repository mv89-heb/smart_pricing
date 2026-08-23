"""WSGI entrypoint for production.

Database bootstrap/recovery is intentionally not executed while Gunicorn
imports this module. Render does not expose a Pre-Deploy Command for this
service, and doing long-running PostgreSQL work during worker startup can
trigger Gunicorn worker timeouts/OOM kills. Recovery is exposed as an
authenticated admin operation instead.
"""

import os

from smartpricing.app_factory import create_app

app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
