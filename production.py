"""Backward-compatible shim.

Render's Start Command for this service is set to `gunicorn production:app`
(configured directly in the Render dashboard, separate from Procfile - Render
only reads Procfile on some plan types, and even then a dashboard override
wins). That command expects a module named production with an `app` object,
which never existed - hence `ModuleNotFoundError: No module named 'production'`.

This file makes `production:app` resolve to the same single app instance as
wsgi:app, so the deploy works with the Start Command as currently configured.
Prefer changing the Start Command in the Render dashboard to `gunicorn wsgi:app`
when convenient, then this file can be deleted - wsgi.py is the real entrypoint.
"""
from wsgi import app  # noqa: F401
