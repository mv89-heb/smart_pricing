from datetime import date
from smartpricing.app_factory import create_app
from smartpricing.db_setup import bootstrap
from smartpricing.extensions import db
from smartpricing.models import Product, PriceHistory, DailyEntry


def app():
    application = create_app({"TESTING": True, "SECRET_KEY": "test", "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with application.app_context():
        bootstrap()
    return application


def login(client):
    return client.post('/login', data={'email': 'admin@smartpricing.local', 'password': 'admin123'}, follow_redirects=False)


def test_bootstrap_and_health():
    application = app()
    with application.test_client() as client:
        assert client.get('/health').status_code == 200
        assert login(client).status_code == 302


def test_product_daily_report_and_year_effective():
    application = app()
    with application.test_client() as client:
        login(client)
        created = client.post('/api/products', json={'name': 'מוצר בדיקה', 'category': 'בדיקות', 'current_price': 12.50})
        assert created.status_code == 201
        pid = created.get_json()['id']
        entry = client.post('/api/entries', json={'date': '2026-08-23', 'product_id': pid, 'quantity': 3, 'entry_type': 'regular'})
        assert entry.status_code == 200
        assert entry.get_json()['total'] == 37.5
        report = client.get('/api/reports?start=2026-08-01&end=2026-08-31')
        assert report.status_code == 200
        assert report.get_json()['totals']['grand'] == 37.5
        validity = client.post('/api/products/apply-validity', json={'year': 2026})
        assert validity.status_code == 200
        with application.app_context():
            assert db.session.query(Product).count() == 1
            assert db.session.query(PriceHistory).filter_by(product_id=pid, effective_date=date(2026,1,1)).count() == 1
            assert db.session.query(DailyEntry).count() == 1


def test_authorization_blocks_viewer():
    application = app()
    with application.app_context():
        from smartpricing.models import Tenant, User
        from werkzeug.security import generate_password_hash
        tenant = db.session.query(Tenant).first()
        db.session.add(User(tenant_id=tenant.id, email='viewer@test.local', name='Viewer', password_hash=generate_password_hash('viewer123'), role='viewer'))
        db.session.commit()
    with application.test_client() as client:
        client.post('/login', data={'email': 'viewer@test.local', 'password': 'viewer123'})
        assert client.post('/api/products', json={'name': 'חסום', 'current_price': 1}).status_code == 403
