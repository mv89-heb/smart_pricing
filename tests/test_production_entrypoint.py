import importlib
import os

os.environ.setdefault("FLASK_ENV", "development")
os.environ.setdefault("DATABASE_URL", "sqlite:///test_production_entrypoint.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key")


def test_production_entrypoints_expose_app():
    wsgi=importlib.import_module('wsgi'); production=importlib.import_module('production')
    assert wsgi.app is not None
    assert production.app is not None
    assert type(wsgi.app) is type(production.app)


def test_production_entrypoint_registers_password_reset_route():
    module=importlib.import_module('production')
    rules={rule.rule for rule in module.app.url_map.iter_rules()}
    assert '/api/users/<int:user_id>/reset-password' in rules
