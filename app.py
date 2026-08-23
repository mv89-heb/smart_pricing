import os
import secrets
import time
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory, make_response
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text, Numeric
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
secret_key = os.environ.get("SECRET_KEY")
if not secret_key:
    if os.environ.get("FLASK_ENV", "development") == "production":
        raise RuntimeError("SECRET_KEY must be configured in production")
    secret_key = secrets.token_hex(32)
app.config.update(
    SECRET_KEY=secret_key,
    SQLALCHEMY_DATABASE_URI=os.environ.get("DATABASE_URL", "sqlite:///local_products.db").replace("postgres://", "postgresql://", 1),
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "false").lower() == "true",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
)
db = SQLAlchemy(app)
_LOGIN_BUCKETS = {}
LOGIN_WINDOW_SECONDS = 300
LOGIN_MAX_ATTEMPTS = 10

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    price = db.Column(Numeric(12, 2), nullable=False)
    tag = db.Column(db.String(80), nullable=True)

class DailyEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(10), nullable=False, index=True)
    product_name = db.Column(db.String(100), nullable=False, index=True)
    quantity = db.Column(db.Float, nullable=False)
    is_extra = db.Column(db.Boolean, default=False, nullable=False, index=True)
    unit_price = db.Column(Numeric(12, 2), nullable=True)
    total_amount = db.Column(Numeric(14, 2), nullable=True)
    note = db.Column(db.String(255), nullable=True)

class PriceHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id", ondelete="CASCADE"), nullable=False, index=True)
    price = db.Column(Numeric(12, 2), nullable=False)
    effective_from = db.Column(db.String(10), nullable=True, index=True)
    changed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    changed_by = db.Column(db.String(100), default="מערכת", nullable=False)

class PeriodLock(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    year_month = db.Column(db.String(7), unique=True, nullable=False, index=True)
    locked = db.Column(db.Boolean, default=False, nullable=False)
    locked_at = db.Column(db.DateTime, nullable=True)
    locked_by = db.Column(db.String(100), nullable=True)

class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    action = db.Column(db.String(50), nullable=False)
    details = db.Column(db.String(1000), nullable=False)
    username = db.Column(db.String(100), default="מערכת")

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="viewer")

class BillingTemplate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    items = db.relationship("BillingTemplateItem", backref="template", cascade="all, delete-orphan")

class BillingTemplateItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(db.Integer, db.ForeignKey("billing_template.id"), nullable=False)
    product_name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    is_extra = db.Column(db.Boolean, default=False)

def money(value):
    return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def valid_date(value):
    if not isinstance(value, str) or len(value) != 10: return False
    try: datetime.strptime(value, "%Y-%m-%d"); return True
    except ValueError: return False

def valid_month(value):
    if not isinstance(value, str) or len(value) != 7 or value[4] != "-": return False
    try: datetime.strptime(value, "%Y-%m"); return True
    except ValueError: return False

def today_iso():
    return datetime.utcnow().strftime("%Y-%m-%d")

def entry_total(entry):
    if entry.total_amount is not None: return money(entry.total_amount)
    return (money(entry.quantity) * money(entry.unit_price)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def entry_json(entry):
    return {"id": entry.id, "date": entry.date, "product_name": entry.product_name, "quantity": entry.quantity,
            "is_extra": bool(entry.is_extra), "unit_price": float(entry.unit_price or 0),
            "total_amount": float(entry_total(entry)), "note": entry.note}

def _column_exists(table_name, column_name):
    try: return column_name in [c["name"] for c in db.inspect(db.engine).get_columns(table_name)]
    except Exception: return True

def _run_migrations():
    migrations = [
        ("daily_entry", "total_amount", "ALTER TABLE daily_entry ADD COLUMN total_amount NUMERIC(14,2)"),
        ("product", "tag", "ALTER TABLE product ADD COLUMN tag VARCHAR(80)"),
        ("price_history", "effective_from", "ALTER TABLE price_history ADD COLUMN effective_from VARCHAR(10)"),
    ]
    for table, column, sql in migrations:
        try:
            if not _column_exists(table, column): db.session.execute(text(sql)); db.session.commit()
        except Exception: db.session.rollback()
    try:
        db.session.execute(text("UPDATE daily_entry SET total_amount = ROUND(COALESCE(quantity,0) * COALESCE(unit_price,0), 2) WHERE total_amount IS NULL")); db.session.commit()
    except Exception: db.session.rollback()
    try:
        db.session.execute(text("UPDATE price_history SET effective_from = SUBSTR(CAST(changed_at AS TEXT),1,10) WHERE effective_from IS NULL")); db.session.commit()
    except Exception: db.session.rollback()
    if db.engine.name == "postgresql":
        for sql in [
            "ALTER TABLE daily_entry ALTER COLUMN unit_price TYPE NUMERIC(12,2) USING ROUND(unit_price::numeric, 2)",
            "ALTER TABLE product ALTER COLUMN price TYPE NUMERIC(12,2) USING ROUND(price::numeric, 2)",
        ]:
            try: db.session.execute(text(sql)); db.session.commit()
            except Exception: db.session.rollback()

def log_activity(action, details):
    try:
        db.session.add(ActivityLog(action=action, details=str(details)[:1000], username=session.get("username", "מערכת")))
        if ActivityLog.query.count() > 2000:
            old = ActivityLog.query.order_by(ActivityLog.timestamp.asc()).first()
            if old: db.session.delete(old)
        db.session.commit()
    except Exception: db.session.rollback()

def period_locked(value): return PeriodLock.query.filter_by(year_month=value[:7], locked=True).first() is not None

def write_access():
    if not session.get("logged_in"): return jsonify({"error": "Unauthorized"}), 401
    if session.get("role", "viewer") == "viewer": return jsonify({"success": False, "error": "אין הרשאות"}), 403
    return None

def admin_access():
    if not session.get("logged_in"): return jsonify({"error": "Unauthorized"}), 401
    if session.get("role") != "admin": return jsonify({"error": "נדרש מנהל"}), 403
    return None

def price_for_date(product, iso_date):
    rows = PriceHistory.query.filter_by(product_id=product.id).order_by(PriceHistory.effective_from.asc(), PriceHistory.id.asc()).all()
    if not rows: return money(product.price)
    candidates = [r for r in rows if r.effective_from and r.effective_from <= iso_date]
    if candidates: return money(candidates[-1].price)
    return money(rows[0].price)

def price_history_json(product):
    today = today_iso()
    rows = PriceHistory.query.filter_by(product_id=product.id).order_by(PriceHistory.effective_from.desc(), PriceHistory.id.desc()).all()
    return [{"id": r.id, "price": float(r.price), "effective_from": r.effective_from, "changed_at": r.changed_at.isoformat(), "changed_by": r.changed_by, "scheduled": bool(r.effective_from and r.effective_from > today)} for r in rows]

with app.app_context():
    db.create_all(); _run_migrations()
    if User.query.count() == 0:
        temp_pass = secrets.token_urlsafe(8)
        db.session.add(User(username="admin", password=generate_password_hash(temp_pass), role="admin")); db.session.commit()
        print(f"SECURITY NOTICE: initial admin password generated for admin: {temp_pass}")

@app.before_request
def require_login():
    if request.endpoint in {"login", "static"}: return None
    if request.path.startswith("/api/") and not session.get("logged_in"): return jsonify({"error": "Unauthorized"}), 401
    if not request.path.startswith("/api/") and not session.get("logged_in"): return redirect(url_for("login"))
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        origin = request.headers.get("Origin")
        if origin and origin.rstrip("/") != request.host_url.rstrip("/"): return jsonify({"error": "CSRF verification failed"}), 403
        if request.path.startswith("/api/") and request.headers.get("X-Requested-With") != "XMLHttpRequest": return jsonify({"error": "CSRF verification failed"}), 403

@app.after_request
def security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    if request.is_secure: response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response

@app.route("/")
def index():
    html = render_template("index.html")
    if "</body>" in html:
        html = html.replace("</body>", '<script src="/static/ux-enhancements.js?v=2" defer></script><script src="/static/price-scheduling.js?v=2" defer></script></body>')
    return make_response(html)

@app.route("/periodic-report")
def periodic_report(): return send_from_directory(app.static_folder, "periodic_report.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET": return render_template("login.html")
    ip = request.remote_addr or "unknown"; now = time.time(); bucket = _LOGIN_BUCKETS.setdefault(ip, []); bucket[:] = [t for t in bucket if now - t < LOGIN_WINDOW_SECONDS]
    if len(bucket) >= LOGIN_MAX_ATTEMPTS: return jsonify({"success": False, "message": "יותר מדי ניסיונות. נסה שוב בעוד מספר דקות."}), 429
    bucket.append(now); data = request.get_json(silent=True) or {}; username = (data.get("username") or "").strip(); password = data.get("password") or ""; user = User.query.filter_by(username=username).first(); valid = False
    if user:
        try: valid = check_password_hash(user.password, password)
        except Exception: valid = False
    if not user or not valid: return jsonify({"success": False, "message": "שם משתמש או סיסמה שגויים"}), 401
    session.clear(); session.permanent = True; session.update({"logged_in": True, "username": user.username, "role": user.role}); log_activity("LOGIN", "התחברות למערכת")
    return jsonify({"success": True, "role": user.role, "username": user.username})

@app.route("/logout")
def logout():
    if session.get("logged_in"): log_activity("LOGOUT", "התנתקות מהמערכת")
    session.clear(); return redirect(url_for("login"))

@app.route("/api/products")
def get_products(): return jsonify({p.name: float(p.price or 0) for p in Product.query.order_by(Product.name.asc()).all()})

@app.route("/api/products/details")
def get_product_details():
    return jsonify([{"id": p.id, "name": p.name, "price": float(p.price or 0), "tag": p.tag or "", "scheduled_price": next((x for x in price_history_json(p) if x["scheduled"]), None)} for p in Product.query.order_by(Product.name.asc()).all()])

@app.route("/api/products", methods=["POST"])
def add_product():
    denied = write_access()
    if denied: return denied
    data = request.get_json(silent=True) or {}; name = (data.get("name") or "").strip(); tag = (data.get("tag") or "").strip()[:80]
    try: price = money(data.get("price"))
    except Exception: return jsonify({"success": False, "error": "מחיר לא תקין"}), 400
    effective = (data.get("effective_from") or today_iso()).strip()
    if not name or price < 0 or not valid_date(effective): return jsonify({"success": False, "error": "נתונים שגויים"}), 400
    if effective > today_iso(): return jsonify({"success": False, "error": "מוצר חדש חייב להתחיל במחיר תקף מהיום. ניתן לתזמן שינוי מחיר למוצר קיים."}), 400
    if Product.query.filter_by(name=name).first(): return jsonify({"success": False, "error": "מוצר קיים"}), 409
    try:
        p = Product(name=name, price=price, tag=tag or None); db.session.add(p); db.session.flush(); db.session.add(PriceHistory(product_id=p.id, price=price, effective_from=effective, changed_by=session.get("username", "מערכת"))); db.session.commit()
        log_activity("NEW_PRODUCT", f"מוצר חדש: {name}, מחיר {price}, תקף מ-{effective}"); return jsonify({"success": True})
    except SQLAlchemyError:
        db.session.rollback(); return jsonify({"success": False, "error": "שגיאת שרת"}), 500