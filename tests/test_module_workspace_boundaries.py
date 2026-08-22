from wsgi import app


def _client():
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    client = app.test_client()
    with client.session_transaction() as session:
        session["logged_in"] = True
        session["username"] = "test"
        session["role"] = "admin"
    return client


def test_daily_workspace_does_not_load_period_report_module():
    response = _client().get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'data-server-module="daily"' in html
    assert "/static/period-report-loader.js" not in html
    assert "#period-display-panel" in html
    assert 'body[data-server-module="daily"] #right-panel' in html


def test_pricing_workspace_has_no_daily_or_period_report_loader():
    response = _client().get("/?module=pricing")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'data-server-module="pricing"' in html
    assert "/static/period-report-loader.js" not in html
    assert 'body[data-server-module="pricing"] #left-panel' in html
    assert 'body[data-server-module="pricing"] #right-panel' in html


def test_reports_route_owns_reports_module_script():
    response = _client().get("/periodic-report")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "/static/reports-module.js?v=2" in html
