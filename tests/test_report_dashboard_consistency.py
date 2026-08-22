import os
import tempfile

DB_FILE=tempfile.NamedTemporaryFile(suffix='.db',delete=False);DB_FILE.close()
os.environ['DATABASE_URL']=f'sqlite:///{DB_FILE.name}';os.environ['SECRET_KEY']='test-secret-key';os.environ['FLASK_ENV']='development'

from smartpricing.app_factory import create_app
from smartpricing.extensions import db
from smartpricing.models import DailyEntry
from smartpricing.services.reports import build_period_report

app=create_app()

def setup_function(_):
    with app.app_context(): db.drop_all();db.create_all()

def _login(client):
    with client.session_transaction() as session: session.update(logged_in=True,username='test',role='admin')

def test_dashboard_and_period_report_share_canonical_engine():
    with app.app_context():
        db.session.add(DailyEntry(date='2026-08-20',product_name='מוצר בדיקה',quantity=2,unit_price=10,is_extra=False,total_amount=20));db.session.commit()
    client=app.test_client();_login(client)
    report=client.get('/api/report/period?from=2026-08-20&to=2026-08-20');dashboard=client.get('/api/dashboard/summary?from=2026-08-20&to=2026-08-20')
    assert report.status_code==200 and dashboard.status_code==200 and report.get_json()==dashboard.get_json()
    with app.app_context(): assert report.get_json()==build_period_report('2026-08-20','2026-08-20')
