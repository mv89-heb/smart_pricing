"""Shared test bootstrap for the canonical Flask application."""
import os

os.environ.setdefault("FLASK_ENV", "development")
os.environ.setdefault("DATABASE_URL", "sqlite:///test_suite.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key")

from smartpricing.app_factory import create_app

app = create_app()
