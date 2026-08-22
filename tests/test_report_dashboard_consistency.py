from smartpricing.models import DailyEntry
from smartpricing.services.reports import build_period_report


def test_dashboard_and_period_report_share_canonical_engine(app):
    with app.app_context():
        DailyEntry(
            date="2026-08-20",
            product_name="מוצר בדיקה",
            quantity=2,
            unit_price=10,
            is_extra=False,
        ).save()

        client = app.test_client()
        report = client.get("/api/report/period?from=2026-08-20&to=2026-08-20")
        dashboard = client.get("/api/dashboard/summary?from=2026-08-20&to=2026-08-20")

        assert report.status_code == 200
        assert dashboard.status_code == 200
        assert report.get_json() == dashboard.get_json()
        assert report.get_json() == build_period_report("2026-08-20", "2026-08-20")
