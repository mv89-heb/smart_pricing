import os
from pathlib import Path

os.environ.setdefault("FLASK_ENV", "development")
os.environ.setdefault("DATABASE_URL", "sqlite:///test_module_navigation.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key")

from smartpricing.app_factory import create_app

app = create_app()
ROOT = Path(__file__).resolve().parents[1]


def _login(client, role="admin"):
    with client.session_transaction() as session:
        session.update(logged_in=True, username="test", role=role)


def body(client, path):
    _login(client)
    response = client.get(path)
    assert response.status_code == 200
    return response.get_data(as_text=True)


def test_all_module_routes_are_registered():
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    assert {"/", "/pricing", "/dashboard", "/periodic-report", "/settings"}.issubset(rules)


def test_each_module_renders_inside_one_application_shell():
    for path, module, marker in (("/","daily","id=\"entry-form\""),("/pricing","pricing","id=\"pricing-body\""),("/dashboard","dashboard","id=\"dash-total\""),("/periodic-report","reports","id=\"reportBody\""),("/settings","settings","id=\"users-area\"")):
        html=body(app.test_client(),path)
        assert f'data-module="{module}"' in html
        assert marker in html
        assert html.count('<aside class="saas-sidebar"')==1
        assert html.count('<header class="saas-topbar"')==1


def test_daily_has_no_other_module_business_dom():
    html=body(app.test_client(),"/")
    for marker in ("id=\"pricing-body\"","id=\"dash-total\"","id=\"reportBody\"","id=\"users-area\""):
        assert marker not in html
    assert "דיווח יומי" in html


def test_pricing_is_not_embedded_in_daily():
    daily=body(app.test_client(),"/"); pricing=body(app.test_client(),"/pricing")
    assert 'href="/pricing"' in daily
    assert 'id="pricing-body"' in pricing
    assert 'id="pricing-body"' not in daily


def test_reports_are_server_rendered_as_the_reports_module():
    html=body(app.test_client(),"/periodic-report")
    assert 'id="reportBody"' in html
    assert '/static/reports-module.js?v=4' in html
    assert '/static/period-report-loader.js' not in html
    assert '/static/period-report-ui.js' not in html


def test_no_well_known_legacy_search_assets_are_in_module_templates():
    templates=''.join(p.read_text(encoding='utf-8') for p in (ROOT/'templates'/'modules').glob('*.html'))
    for marker in ('global-filters.js','reports-controls.js','reports-summary.js','period-report-loader.js'):
        assert marker not in templates
