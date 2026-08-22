from werkzeug.security import generate_password_hash

from app import app, db
from smartpricing.models import User


def setup_function(_):
    with app.app_context():
        db.drop_all()
        db.create_all()
        db.session.add(User(username="admin", password=generate_password_hash("admin-pass-123"), role="admin"))
        db.session.commit()


def _login(client, username="admin", password="admin-pass-123"):
    response = client.post(
        "/login",
        json={"username": username, "password": password},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert response.status_code == 200


def test_role_change_invalidates_stale_admin_session():
    client = app.test_client()
    _login(client)

    with app.app_context():
        user = User.query.filter_by(username="admin").first()
        user.role = "editor"
        db.session.commit()

    response = client.get("/api/users")
    assert response.status_code == 403


def test_last_admin_cannot_be_demoted():
    client = app.test_client()
    _login(client)

    with app.app_context():
        admin = User.query.filter_by(username="admin").first()
        response = client.post(
            "/api/users",
            json={"username": admin.username, "role": "viewer", "password": ""},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        assert response.status_code == 400
        db.session.refresh(admin)
        assert admin.role == "admin"
