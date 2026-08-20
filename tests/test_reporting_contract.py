import os
import tempfile

DB_FILE = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
DB_FILE.close()
os.environ["DATABASE_URL"] = f"sqlite:///{DB_FILE.name}"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["FLASK_ENV"] = "development"

import production  # noqa: E402
from app import app, db, DailyEntry, Product  # noqa: E402


def setup_function(_):
    with app.app_context():
        db.drop_all()
        db.create_all()
        product = Product(name="חלב", price=8)
        db.session.add(product)
        db.session.add_all([
            DailyEntry(
                date="2026-08-18",
                product_name="חלב",
                quantity=2,
                is_extra=False,
                unit_price=8,
                total_amount=16,
                note="רגיל",
            ),
            DailyEntry(
                date="2026-08-19",
                product_name="חלב",
                quantity=1,
                is_extra=True,
                unit_price=8,
                total_amount=8,
                note="חריג",
            ),
        ])
        db.session.commit()


def _get(path):
    return app.test_client().get(path)


def test_dashboard_and_period_report_preserve_full_response_contract():
    dashboard = _get("/api/dashboard/summary?from=2026-08-18&to=2026-08-19")
    report = _get("/api/report/period?from=2026-08-18&to=2026-08-19")

    assert dashboard.status_code == 200
    assert report.status_code == 200
    dashboard_payload = dashboard.get_json()
    report_payload = report.get_json()

    expected_keys = {
        "from",
        "to",
        "entries",
        "summary",
        "product_summary",
        "day_summary",
        "locked_months",
        "fully_locked",
    }
    assert set(dashboard_payload) == expected_keys
    assert set(report_payload) == expected_keys
    assert dashboard_payload == report_payload

    assert dashboard_payload["summary"] == {
        "grand_total": 24.0,
        "regular_total": 16.0,
        "extra_total": 8.0,
        "days_count": 2,
        "average_day": 12.0,
    }
    assert dashboard_payload["product_summary"]["חלב"] == {
        "quantity": 3.0,
        "total": 24.0,
    }


def test_dashboard_and_period_compare_preserve_compare_contract():
    dashboard = _get(
        "/api/dashboard/compare?"
        "a_from=2026-08-18&a_to=2026-08-18&"
        "b_from=2026-08-19&b_to=2026-08-19"
    )
    report = _get(
        "/api/report/compare?"
        "a_from=2026-08-18&a_to=2026-08-18&"
        "b_from=2026-08-19&b_to=2026-08-19"
    )

    assert dashboard.status_code == 200
    assert report.status_code == 200
    assert dashboard.get_json() == report.get_json()
    assert set(dashboard.get_json()) == {"a", "b", "change"}
    assert dashboard.get_json()["a"]["grand_total"] == 16.0
    assert dashboard.get_json()["b"]["grand_total"] == 8.0


def test_legacy_report_all_uses_same_canonical_report_shape():
    response = _get("/api/report/all")
    assert response.status_code == 200
    payload = response.get_json()
    assert set(payload) == {
        "from",
        "to",
        "entries",
        "summary",
        "product_summary",
        "day_summary",
        "locked_months",
        "fully_locked",
    }
    assert payload["from"] == "2026-08-18"
    assert payload["to"] == "2026-08-19"
    assert payload["summary"]["grand_total"] == 24.0
