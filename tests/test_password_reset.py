import os

os.environ.setdefault("FLASK_ENV", "development")
os.environ.setdefault("DATABASE_URL", "sqlite:///test_password_reset.db")

from wsgi_ui import app
from app import db, User
from werkzeug.security import generate_password_hash, check_password_hash


def test_admin_can_reset_user_password():
    app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI="sqlite:///test_password_reset.db")
    with app.app_context():
        db.drop_all()
        db.create_all()
        admin = User(username="admin", password=generate_password_hash("old-admin-pass"), role="admin")
        viewer = User(username="worker", password=generate_password_hash("old-worker-pass"), role="viewer")
        db.session.add_all([admin, viewer])
        db.session.commit()
        viewer_id = viewer.id

    try:
        with app.test_client() as client:
            with client.session_transaction() as session:
                session.update({"logged_in": True, "username": "admin", "role": "admin"})
            response = client.post(
                f"/api/users/{viewer_id}/reset-password",
                json={"password": "new-worker-pass"},
                headers={"X-Requested-With": "XMLHttpRequest"},
            )
            assert response.status_code == 200
            assert response.get_json()["success"] is True

        with app.app_context():
            updated = db.session.get(User, viewer_id)
            assert check_password_hash(updated.password, "new-worker-pass")
            assert not check_password_hash(updated.password, "old-worker-pass")
    finally:
        with app.app_context():
            db.session.remove()
            db.drop_all()


def test_viewer_cannot_reset_password():
    app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI="sqlite:///test_password_reset_viewer.db")
    with app.app_context():
        db.drop_all()
        db.create_all()
        admin = User(username="admin", password=generate_password_hash("old-admin-pass"), role="admin")
        viewer = User(username="worker", password=generate_password_hash("old-worker-pass"), role="viewer")
        db.session.add_all([admin, viewer])
        db.session.commit()
        viewer_id = viewer.id

    try:
        with app.test_client() as client:
            with client.session_transaction() as session:
                session.update({"logged_in": True, "username": "worker", "role": "viewer"})
            response = client.post(
                f"/api/users/{viewer_id}/reset-password",
                json={"password": "new-worker-pass"},
                headers={"X-Requested-With": "XMLHttpRequest"},
            )
            assert response.status_code == 403
    finally:
        with app.app_context():
            db.session.remove()
            db.drop_all()


def test_password_reset_rejects_short_password():
    app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI="sqlite:///test_password_reset_short.db")
    with app.app_context():
        db.drop_all()
        db.create_all()
        admin = User(username="admin", password=generate_password_hash("old-admin-pass"), role="admin")
        viewer = User(username="worker", password=generate_password_hash("old-worker-pass"), role="viewer")
        db.session.add_all([admin, viewer])
        db.session.commit()
        viewer_id = viewer.id

    try:
        with app.test_client() as client:
            with client.session_transaction() as session:
                session.update({"logged_in": True, "username": "admin", "role": "admin"})
            response = client.post(
                f"/api/users/{viewer_id}/reset-password",
                json={"password": "123"},
                headers={"X-Requested-With": "XMLHttpRequest"},
            )
            assert response.status_code == 400
            assert response.get_json()["success"] is False
    finally:
        with app.app_context():
            db.session.remove()
            db.drop_all()
