"""Production compatibility entrypoint for Render/Gunicorn.

The application is always constructed through smartpricing.app_factory.
This module exists only because some Render services use production:app.
"""
from smartpricing.app_factory import create_app

app = create_app()
