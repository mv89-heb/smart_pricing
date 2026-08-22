import os
from flask import Flask, g, jsonify, redirect, request, session, url_for
from .db_setup import bootstrap
from .extensions import db


def _database_url():
    url=os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")
    if url and url.startswith("postgres://"): return "postgresql+psycopg://"+url[len("postgres://"):]
    if url and url.startswith("postgresql://"): return "postgresql+psycopg://"+url[len("postgresql://"):]
    return url or "sqlite:///smartpricing.db"


def create_app(config_object=None):
    app=Flask(__name__,template_folder="../templates",static_folder="../static")
    app.config.update(SECRET_KEY=os.getenv("SECRET_KEY","dev-only-change-me"),SQLALCHEMY_DATABASE_URI=_database_url(),SQLALCHEMY_TRACK_MODIFICATIONS=False,SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE="Lax",SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE","0")=="1",JSON_SORT_KEYS=False)
    if config_object:
        if isinstance(config_object,dict): app.config.update(config_object)
        else: app.config.from_object(config_object)
    uri=app.config["SQLALCHEMY_DATABASE_URI"]
    app.config["SQLALCHEMY_ENGINE_OPTIONS"]={"pool_pre_ping":True} if uri.startswith("sqlite") else {"pool_pre_ping":True,"pool_recycle":1800,"pool_size":int(os.getenv("DB_POOL_SIZE","5")),"max_overflow":int(os.getenv("DB_MAX_OVERFLOW","5"))}
    db.init_app(app)
    from .routes.pages import pages_bp
    from .routes.products import products_bp
    from .routes.entries import entries_bp
    from .routes.reports import reports_bp
    from .routes.users import users_bp
    from .routes.periods import periods_bp
    from .routes.system import system_bp
    for bp in (pages_bp,products_bp,entries_bp,reports_bp,users_bp,periods_bp,system_bp): app.register_blueprint(bp)
    @app.before_request
    def load_user():
        from .models import User
        g.current_user=db.session.get(User,session.get("user_id")) if session.get("user_id") else None
        if request.path.startswith("/static/") or request.endpoint=="pages.login": return None
        if not g.current_user or not g.current_user.is_active:
            session.clear()
            if request.path.startswith("/api/"): return jsonify(status="error",message="נדרשת התחברות מחדש"),401
            return redirect(url_for("pages.login"))
    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options","nosniff"); response.headers.setdefault("X-Frame-Options","SAMEORIGIN"); response.headers.setdefault("Referrer-Policy","strict-origin-when-cross-origin")
        if request.path.startswith("/static/"): response.headers["Cache-Control"]="public, max-age=86400"
        return response
    with app.app_context(): bootstrap()
    return app
