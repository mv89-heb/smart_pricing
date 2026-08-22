import os
import tempfile

DB_FILE = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
DB_FILE.close()
os.environ["DATABASE_URL"] = f"sqlite:///{DB_FILE.name}"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["FLASK_ENV"] = "development"

from smartpricing.app_factory import create_app
from smartpricing.extensions import db
from smartpricing.models import DailyEntry, PeriodLock, Product

app = create_app()


def auth(client, role="admin"):
    with client.session_transaction() as sess:
        sess["logged_in"] = True
        sess["username"] = "tester"
        sess["role"] = role


def headers(origin="http://localhost"):
    return {"X-Requested-With": "XMLHttpRequest", "Origin": origin}


def setup_function(_):
    with app.app_context():
        db.drop_all()
        db.create_all()


def test_price_change_preserves_historical_price_for_old_date():
    client = app.test_client(); auth(client)
    assert client.post("/api/products", json={"name":"קפה","price":10}, headers=headers()).status_code == 200
    assert client.post("/api/entries", json={"date":"2026-08-01","product_name":"קפה","quantity":10}, headers=headers()).status_code == 200
    assert client.put("/api/products/%D7%A7%D7%A4%D7%94", json={"price":12}, headers=headers()).status_code == 200
    assert client.post("/api/entries", json={"date":"2026-08-01","product_name":"קפה","quantity":5}, headers=headers()).status_code == 200
    with app.app_context():
        rows=DailyEntry.query.order_by(DailyEntry.id.asc()).all(); assert len(rows)==1; assert float(rows[0].unit_price)==10.0; assert float(rows[0].quantity)==15.0; assert float(rows[0].total_amount)==150.0
    report=client.get("/api/report/period?from=2026-08-01&to=2026-08-01"); assert report.status_code==200; assert report.get_json()["summary"]["grand_total"]==150.0


def test_current_price_is_used_for_current_date_after_price_change():
    client=app.test_client(); auth(client)
    assert client.post("/api/products",json={"name":"קפה","price":10},headers=headers()).status_code==200
    assert client.put("/api/products/%D7%A7%D7%A4%D7%94",json={"price":12},headers=headers()).status_code==200
    assert client.post("/api/entries",json={"date":"2026-08-20","product_name":"קפה","quantity":5},headers=headers()).status_code==200
    with app.app_context(): row=DailyEntry.query.one(); assert float(row.unit_price)==12.0; assert float(row.total_amount)==60.0


def test_same_price_entries_are_aggregated_without_losing_total():
    client=app.test_client(); auth(client)
    assert client.post("/api/products",json={"name":"לחם","price":7.5},headers=headers()).status_code==200
    assert client.post("/api/entries",json={"date":"2026-08-02","product_name":"לחם","quantity":2},headers=headers()).status_code==200
    assert client.post("/api/entries",json={"date":"2026-08-02","product_name":"לחם","quantity":3},headers=headers()).status_code==200
    with app.app_context(): rows=DailyEntry.query.all(); assert len(rows)==1; assert float(rows[0].quantity)==5.0; assert float(rows[0].total_amount)==37.5


def test_period_report_and_compare():
    client=app.test_client(); auth(client)
    assert client.post("/api/products",json={"name":"חלב","price":8},headers=headers()).status_code==200
    assert client.post("/api/entries",json={"date":"2026-07-10","product_name":"חלב","quantity":10},headers=headers()).status_code==200
    assert client.post("/api/entries",json={"date":"2026-08-10","product_name":"חלב","quantity":15},headers=headers()).status_code==200
    period=client.get("/api/report/period?from=2026-08-01&to=2026-08-31"); assert period.status_code==200; payload=period.get_json(); assert payload["summary"]["grand_total"]==120.0; assert payload["summary"]["days_count"]==1; assert payload["product_summary"]["חלב"]["quantity"]==15.0
    compare=client.get("/api/report/compare?a_from=2026-07-01&a_to=2026-07-31&b_from=2026-08-01&b_to=2026-08-31"); assert compare.status_code==200; assert compare.get_json()["change"]["grand_total"]==50.0


def test_dashboard_summary_and_compare():
    client=app.test_client(); auth(client)
    assert client.post("/api/products",json={"name":"חלב","price":8},headers=headers()).status_code==200
    assert client.post("/api/entries",json={"date":"2026-08-10","product_name":"חלב","quantity":15},headers=headers()).status_code==200
    summary=client.get("/api/dashboard/summary?from=2026-08-01&to=2026-08-31"); assert summary.status_code==200; assert summary.get_json()["summary"]["grand_total"]==120.0
    compare=client.get("/api/dashboard/compare?a_from=2026-07-01&a_to=2026-07-31&b_from=2026-08-01&b_to=2026-08-31"); assert compare.status_code==200; assert compare.get_json()["change"]["grand_total"] is None


def test_period_lock_blocks_changes():
    client=app.test_client(); auth(client)
    assert client.post("/api/products",json={"name":"חלב","price":8},headers=headers()).status_code==200
    assert client.post("/api/periods/2026-08/lock",headers=headers()).status_code==200
    assert client.post("/api/entries",json={"date":"2026-08-05","product_name":"חלב","quantity":1},headers=headers()).status_code==423
    assert client.post("/api/periods/2026-08/unlock",headers=headers()).status_code==200
    assert client.post("/api/entries",json={"date":"2026-08-05","product_name":"חלב","quantity":1},headers=headers()).status_code==200


def test_viewer_cannot_write():
    client=app.test_client(); auth(client,"viewer"); assert client.post("/api/entries",json={"date":"2026-08-05","product_name":"חלב","quantity":1},headers=headers()).status_code==403


def test_editor_can_write():
    client=app.test_client(); auth(client,"editor"); assert client.post("/api/products",json={"name":"מים","price":3},headers=headers()).status_code==200; assert client.post("/api/entries",json={"date":"2026-08-05","product_name":"מים","quantity":2},headers=headers()).status_code==200


def test_cross_origin_write_is_rejected():
    client=app.test_client(); auth(client); assert client.post("/api/products",json={"name":"מים","price":3},headers=headers("https://evil.example")).status_code==403


def test_unauthenticated_api_is_rejected():
    client=app.test_client(); assert client.get("/api/report/period?from=2026-08-01&to=2026-08-31").status_code==401


def test_module_pages_are_isolated_after_login():
    client=app.test_client(); auth(client)
    daily=client.get("/"); pricing=client.get("/pricing"); dashboard=client.get("/dashboard"); reports=client.get("/periodic-report"); settings=client.get("/settings")
    for response in (daily,pricing,dashboard,reports,settings): assert response.status_code==200
    assert 'href="/pricing"' in daily.get_data(as_text=True)
    assert 'id="right-panel"' not in daily.get_data(as_text=True)
    assert 'id="dashboard-modal"' not in daily.get_data(as_text=True)
    assert 'id="entry-form"' in daily.get_data(as_text=True)
    assert 'id="pricing-body"' in pricing.get_data(as_text=True)
    assert 'id="dash-total"' in dashboard.get_data(as_text=True)
    assert 'id="reportBody"' in reports.get_data(as_text=True)
