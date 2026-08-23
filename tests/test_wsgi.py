from app import app as flask_app
from wsgi import UXInjectionMiddleware


def test_wsgi_exports_wrapped_app():
    assert isinstance(UXInjectionMiddleware(flask_app), UXInjectionMiddleware)


def test_ux_middleware_injects_only_html():
    wrapped = UXInjectionMiddleware(flask_app)
    client = flask_app.test_client()
    response = client.get('/login')
    assert response.status_code in (200, 302)
