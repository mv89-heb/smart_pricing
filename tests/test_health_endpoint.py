def test_health_endpoint_requires_login():
    import app
    import wsgi_ui
    client = wsgi_ui.app.test_client()
    response = client.get('/api/system/health')
    assert response.status_code == 401
