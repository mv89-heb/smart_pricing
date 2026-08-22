"""The one production entrypoint. Run with: gunicorn wsgi:app

Everything that used to live across app.py -> api_routes.py -> wsgi_ui.py ->
wsgi.py now lives in the smartpricing/ package; this file just builds the app
once. Procfile has been updated to point at wsgi:app.
"""
from smartpricing.app_factory import create_app

app = create_app()

if __name__ == "__main__":
    app.run()
