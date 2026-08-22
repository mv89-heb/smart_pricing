import pathlib

from tests.conftest import app

ROOT = pathlib.Path(__file__).resolve().parents[1]


def body(client, path):
    return client.get(path).get_data(as_text=True)


def test_daily_is_server_rendered_as_the_daily_module():
    html=body(app.test_client(),"/")
    assert 'id="entry-form"' in html
    assert 'href="/pricing"' in html
    assert "דיווח יומי" in html


def test_pricing_is_not_embedded_in_daily():
    daily=body(app.test_client(),"/"); pricing=body(app.test_client(),"/pricing")
    assert 'href="/pricing"' in daily
    assert 'id="pricing-body"' in pricing
    assert 'id="pricing-body"' not in daily


def test_reports_are_server_rendered_as_the_reports_module():
    html=body(app.test_client(),"/periodic-report")
    assert 'id="reportBody"' in html
    assert '/static/reports-module.js?v=5' in html
    assert '/static/period-report-loader.js' not in html
    assert '/static/period-report-ui.js' not in html


def test_no_well_known_legacy_search_assets_are_in_module_templates():
    templates=''.join(p.read_text(encoding='utf-8') for p in (ROOT/'templates'/'modules').glob('*.html'))
    for marker in ('global-filters.js','reports-controls.js','reports-summary.js','period-report-loader.js'):
        assert marker not in templates
