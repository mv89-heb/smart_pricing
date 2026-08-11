import os
import secrets
import time
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from functools import wraps

from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text, Numeric
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Configuration / security
# ---------------------------------------------------------------------------
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

# Lightweight login throttling. This intentionally stays dependency-free.
_LOGIN_BUCKETS = {}
LOGIN_WINDOW_SECONDS = 300
LOGIN_MAX_ATTEMPTS = 10

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    price = db.Column(Numeric(12, 2), nullable=False)
    tag = db.Column(db.String(80), nullable=True)


class DailyEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # Kept as ISO text for backwards compatibility with the existing database.
    # All writes and reads are strictly validated as YYYY-MM-DD.
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


# ---------------------------------------------------------------------------
# Helpers / migration compatibility
# ---------------------------------------------------------------------------
def money(value):
    return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def valid_date(value):
    if not isinstance(value, str):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return len(value) == 10
    except ValueError:
        return False


def valid_month(value):
    if not isinstance(value, str) or len(value) != 7 or value[4] != "-":
        return False
    try:
        datetime.strptime(value, "%Y-%m",)
        return True
    except ValueError:
        return False


def entry_total(entry):
    if entry.total_amount is not None:
        return money(entry.total_amount)
    return (money(entry.quantity) * money(entry.unit_price)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def entry_json(entry):
    return {
        "id": entry.id,
        "date": entry.date,
        "product_name": entry.product_name,
        "quantity": entry.quantity,
        "is_extra": bool(entry.is_extra),
        "unit_price": float(entry.unit_price or 0),
        "total_amount": float(entry_total(entry)),
        "note": entry.note,
    }


def _column_exists(table_name, column_name):
    try:
        inspector = db.inspect(db.engine)
        return column_name in [c["name"] for c in inspector.get_columns(table_name)]
    except Exception:
        return True


def _run_migrations():
    additions = [
        ("daily_entry", "total_amount", "ALTER TABLE daily_entry ADD COLUMN total_amount NUMERIC(14,2)"),
        ("product", "tag", "ALTER TABLE product ADD COLUMN tag VARCHAR(80)"),
    ]
    for table, column, sql in additions:
        try:
            if not _column_exists(table, column):
                db.session.execute(text(sql))
                db.session.commit()
        except Exception:
            db.session.rollback()

    # Backfill totals without touching the historical unit price.
    try:
        if _column_exists("daily_entry", "total_amount"):
            db.session.execute(text("UPDATE daily_entry SET total_amount = ROUND(COALESCE(quantity,0) * COALESCE(unit_price,0), 2) WHERE total_amount IS NULL"))
            db.session.commit()
    except Exception:
        db.session.rollback()

    # PostgreSQL can safely migrate the old FLOAT price to NUMERIC. SQLite keeps
    # the compatible affinity and SQLAlchemy still exposes Decimal semantics.
    try:
        if db.engine.name == "postgresql" and _column_exists("daily_entry", "unit_price"):
            db.session.execute(text("ALTER TABLE daily_entry ALTER COLUMN unit_price TYPE NUMERIC(12,2) USING ROUND(unit_price::numeric, 2)"))
            db.session.commit()
    except Exception:
        db.session.rollback()

    try:
        if db.engine.name == "postgresql" and _column_exists("product", "price"):
            db.session.execute(text("ALTER TABLE product ALTER COLUMN price TYPE NUMERIC(12,2) USING ROUND(price::numeric, 2)"))
            db.session.commit()
    except Exception:
        db.session.rollback()


def log_activity(action, details):
    try:
        db.session.add(ActivityLog(action=action, details=str(details)[:1000], username=session.get("username", "מערכת")))
        count = ActivityLog.query.count()
        if count > 2000:
            oldest = ActivityLog.query.order_by(ActivityLog.timestamp.asc()).first()
            if oldest:
                db.session.delete(oldest)
        db.session.commit()
    except Exception:
        db.session.rollback()


def period_locked(date_or_month):
    month = date_or_month[:7]
    lock = PeriodLock.query.filter_by(year_month=month, locked=True).first()
    return lock is not None


def require_write_access():
    if not session.get("logged_in"):
        return jsonify({"error": "Unauthorized"}), 401
    if session.get("role", "viewer") == "viewer":
        return jsonify({"success": False, "error": "אין הרשאות"}), 403
    return None


def admin_required():
    if not session.get("logged_in"):
        return jsonify({"error": "Unauthorized"}), 401
    if session.get("role") != "admin":
        return jsonify({"error": "נדרש מנהל"}), 403
    return None


with app.app_context():
    db.create_all()
    _run_migrations()
    if User.query.count() == 0:
        temp_pass = secrets.token_urlsafe(8)
        db.session.add(User(username="admin", password=generate_password_hash(temp_pass), role="admin"))
        db.session.commit()
        print(f"SECURITY NOTICE: initial admin password generated for admin: {temp_pass}")


# ---------------------------------------------------------------------------
# Request security
# ---------------------------------------------------------------------------
@app.before_request
def require_login():
    if request.endpoint in {"login", "static"}:
        return None

    if request.path.startswith("/api/") and not session.get("logged_in"):
        return jsonify({"error": "Unauthorized"}), 401

    if not request.path.startswith("/api/") and not session.get("logged_in"):
        return redirect(url_for("login"))

    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        # Same-origin verification protects the existing fetch-based frontend
        # without breaking it. X-Requested-With is retained for compatibility.
        origin = request.headers.get("Origin")
        if origin and origin.rstrip("/") != request.host_url.rstrip("/"):
            return jsonify({"error": "CSRF verification failed"}), 403
        if request.path.startswith("/api/") and not request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"error": "CSRF verification failed"}), 403


@app.after_request
def security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    if request.is_secure:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/periodic-report")
def periodic_report():
    return send_from_directory(app.static_folder, "periodic_report.html")


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    ip = request.remote_addr or "unknown"
    now = time.time()
    bucket = _LOGIN_BUCKETS.setdefault(ip, [])
    bucket[:] = [t for t in bucket if now - t < LOGIN_WINDOW_SECONDS]
    if len(bucket) >= LOGIN_MAX_ATTEMPTS:
        return jsonify({"success": False, "message": "יותר מדי ניסיונות. נסה שוב בעוד מספר דקות."}), 429
    bucket.append(now)

    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    user = User.query.filter_by(username=username).first()
    valid = False
    if user:
        try:
            valid = check_password_hash(user.password, password)
        except Exception:
            valid = False

    if not user or not valid:
        log_activity("LOGIN_FAILED", f"ניסיון התחברות כושל עבור {username[:80]}")
        return jsonify({"success": False, "message": "שם משתמש או סיסמה שגויים"}), 401

    session.clear()
    session.permanent = True
    session["logged_in"] = True
    session["username"] = user.username
    session["role"] = user.role
    log_activity("LOGIN", "התחברות למערכת")
    return jsonify({"success": True, "role": user.role, "username": user.username})


@app.route("/logout")
def logout():
    if session.get("logged_in"):
        log_activity("LOGOUT", "התנתקות מהמערכת")
    session.clear()
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# Products / pricing
# ---------------------------------------------------------------------------
@app.route("/api/products", methods=["GET"])
def get_products():
    return jsonify({p.name: float(p.price or 0) for p in Product.query.order_by(Product.name.asc()).all()})


@app.route("/api/products/details", methods=["GET"])
def get_product_details():
    return jsonify([
        {"id": p.id, "name": p.name, "price": float(p.price or 0), "tag": p.tag or ""}
        for p in Product.query.order_by(Product.name.asc()).all()
    ])


@app.route("/api/products", methods=["POST"])
def add_product():
    denied = require_write_access()
    if denied: return denied
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    tag = (data.get("tag") or "").strip()[:80]
    try:
        price = money(data.get("price"))
    except Exception:
        return jsonify({"success": False, "error": "מחיר לא תקין"}), 400
    if not name or price < 0:
        return jsonify({"success": False, "error": "נתונים שגויים"}), 400
    if Product.query.filter_by(name=name).first():
        return jsonify({"success": False, "error": "מוצר קיים"}), 409
    try:
        product = Product(name=name, price=price, tag=tag or None)
        db.session.add(product)
        db.session.flush()
        db.session.add(PriceHistory(product_id=product.id, price=price, changed_by=session.get("username", "מערכת")))
        db.session.commit()
        log_activity("NEW_PRODUCT", f"מוצר חדש: {name}, מחיר: {price}")
        return jsonify({"success": True})
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"success": False, "error": "שגיאת שרת"}), 500


@app.route("/api/products/<path:name>", methods=["PUT"])
def update_product(name):
    denied = require_write_access()
    if denied: return denied
    data = request.get_json(silent=True) or {}
    product = Product.query.filter_by(name=name).first()
    if not product:
        return jsonify({"success": False, "error": "לא נמצא"}), 404
    new_name = (data.get("name") or name).strip()
    tag = (data.get("tag") or product.tag or "").strip()[:80]
    try:
        new_price = money(data.get("price", product.price))
    except Exception:
        return jsonify({"success": False, "error": "מחיר לא תקין"}), 400
    if not new_name or new_price < 0:
        return jsonify({"success": False, "error": "נתונים שגויים"}), 400
    if new_name != name and Product.query.filter_by(name=new_name).first():
        return jsonify({"success": False, "error": "מוצר קיים"}), 409
    try:
        old_price = money(product.price)
        product.name = new_name
        product.tag = tag or None
        product.price = new_price
        if new_name != name:
            DailyEntry.query.filter_by(product_name=name).update({DailyEntry.product_name: new_name})
            BillingTemplateItem.query.filter_by(product_name=name).update({BillingTemplateItem.product_name: new_name})
        if new_price != old_price:
            db.session.add(PriceHistory(product_id=product.id, price=new_price, changed_by=session.get("username", "מערכת")))
        db.session.commit()
        log_activity("UPDATE_PRICE", f"מוצר: {name} -> {new_name}; מחיר: {old_price} -> {new_price}")
        return jsonify({"success": True})
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"success": False, "error": "שגיאת שרת"}), 500


@app.route("/api/products/<path:name>", methods=["DELETE"])
def delete_product(name):
    denied = require_write_access()
    if denied: return denied
    try:
        product = Product.query.filter_by(name=name).first()
        if product:
            db.session.delete(product)
            db.session.commit()
            log_activity("DELETE_PRODUCT", f"מוצר: {name}")
        return jsonify({"success": True})
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"success": False, "error": "שגיאת שרת"}), 500


@app.route("/api/products/<path:name>/history", methods=["GET"])
def product_history(name):
    product = Product.query.filter_by(name=name).first()
    if not product:
        return jsonify({"error": "לא נמצא"}), 404
    rows = PriceHistory.query.filter_by(product_id=product.id).order_by(PriceHistory.changed_at.desc()).all()
    return jsonify([{"price": float(r.price), "changed_at": r.changed_at.isoformat(), "changed_by": r.changed_by} for r in rows])


# ---------------------------------------------------------------------------
# Billing entries
# ---------------------------------------------------------------------------
@app.route("/api/entries/<date>", methods=["GET"])
def get_entries(date):
    if not valid_date(date):
        return jsonify({"error": "תאריך לא תקין"}), 400
    return jsonify([entry_json(e) for e in DailyEntry.query.filter_by(date=date).order_by(DailyEntry.id.asc()).all()])


@app.route("/api/entries", methods=["POST"])
def add_entry():
    denied = require_write_access()
    if denied: return denied
    data = request.get_json(silent=True) or {}
    date = data.get("date")
    product_name = (data.get("product_name") or "").strip()
    note = (data.get("note") or "").strip()[:255]
    if not valid_date(date) or not product_name:
        return jsonify({"success": False, "error": "נתונים שגויים"}), 400
    if period_locked(date):
        return jsonify({"success": False, "error": "התקופה נעולה. נדרש מנהל כדי לשנות חיובים."}), 423
    try:
        quantity = float(data.get("quantity"))
        if quantity <= 0 or quantity > 1000000:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "כמות לא תקינה"}), 400

    product = Product.query.filter_by(name=product_name).first()
    current_price = money(product.price if product else 0)
    is_extra = bool(data.get("is_extra", False))
    try:
        existing = DailyEntry.query.filter_by(date=date, product_name=product_name, is_extra=is_extra).first()
        # Critical historical-pricing fix: merge only when the unit price is
        # unchanged. A price change starts a new line and never rewrites history.
        if existing and not note and money(existing.unit_price) == current_price:
            existing.quantity = float(existing.quantity) + quantity
            existing.total_amount = (money(existing.quantity) * current_price).quantize(Decimal("0.01"))
        else:
            entry = DailyEntry(
                date=date,
                product_name=product_name,
                quantity=quantity,
                is_extra=is_extra,
                unit_price=current_price,
                total_amount=(money(quantity) * current_price).quantize(Decimal("0.01")),
                note=note or None,
            )
            db.session.add(entry)
        db.session.commit()
        log_activity("ADD_ENTRY", f"{date} | {product_name} | {quantity} | {current_price}")
        return jsonify({"success": True})
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"success": False, "error": "שגיאת שרת"}), 500


@app.route("/api/entries/<int:entry_id>", methods=["PUT"])
def update_entry(entry_id):
    denied = require_write_access()
    if denied: return denied
    data = request.get_json(silent=True) or {}
    entry = db.session.get(DailyEntry, entry_id)
    if not entry:
        return jsonify({"success": False, "error": "לא נמצא"}), 404
    if period_locked(entry.date):
        return jsonify({"success": False, "error": "התקופה נעולה. נדרש מנהל כדי לשנות חיובים."}), 423
    before = entry_json(entry)
    try:
        if "quantity" in data:
            q = float(data["quantity"])
            if q <= 0 or q > 1000000: raise ValueError
            entry.quantity = q
        if "is_extra" in data:
            entry.is_extra = bool(data["is_extra"])
        if "note" in data:
            entry.note = (data["note"] or "").strip()[:255] or None
        entry.total_amount = (money(entry.quantity) * money(entry.unit_price)).quantize(Decimal("0.01"))
        db.session.commit()
        after = entry_json(entry)
        log_activity("UPDATE_ENTRY", f"חיוב #{entry.id}; לפני={before}; אחרי={after}")
        return jsonify({"success": True})
    except (TypeError, ValueError):
        db.session.rollback()
        return jsonify({"success": False, "error": "נתונים שגויים"}), 400
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"success": False, "error": "שגיאת שרת"}), 500


@app.route("/api/entries/<int:entry_id>", methods=["DELETE"])
def delete_entry(entry_id):
    denied = require_write_access()
    if denied: return denied
    entry = db.session.get(DailyEntry, entry_id)
    if not entry:
        return jsonify({"success": True})
    if period_locked(entry.date):
        return jsonify({"success": False, "error": "התקופה נעולה. נדרש מנהל כדי לשנות חיובים."}), 423
    details = entry_json(entry)
    try:
        db.session.delete(entry)
        db.session.commit()
        log_activity("DELETE_ENTRY", f"חיוב נמחק: {details}")
        return jsonify({"success": True})
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"success": False, "error": "שגיאת שרת"}), 500


@app.route("/api/bulk/entries/<date>", methods=["DELETE"])
def clear_date_entries(date):
    denied = require_write_access()
    if denied: return denied
    if not valid_date(date): return jsonify({"success": False, "error": "תאריך לא תקין"}), 400
    if period_locked(date): return jsonify({"success": False, "error": "התקופה נעולה"}), 423
    try:
        DailyEntry.query.filter_by(date=date).delete()
        db.session.commit()
        log_activity("CLEAR_DAY", f"ניקוי יום: {date}")
        return jsonify({"success": True})
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"success": False, "error": "שגיאת שרת"}), 500


@app.route("/api/bulk/season", methods=["DELETE"])
def reset_season():
    denied = admin_required()
    if denied: return denied
    try:
        DailyEntry.query.delete()
        db.session.commit()
        log_activity("RESET_SEASON", "מחיקת כל החיובים")
        return jsonify({"success": True})
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"success": False, "error": "שגיאת שרת"}), 500


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------
def build_report(entries, start=None, end=None):
    regular = Decimal("0.00")
    extra = Decimal("0.00")
    product_summary = {}
    day_summary = {}
    for e in entries:
        total = entry_total(e)
        if e.is_extra:
            extra += total
        else:
            regular += total
        p = product_summary.setdefault(e.product_name, {"quantity": 0.0, "total": 0.0})
        p["quantity"] += float(e.quantity or 0)
        p["total"] = float(Decimal(str(p["total"])) + total)
        d = day_summary.setdefault(e.date, {"regular": 0.0, "extra": 0.0, "total": 0.0})
        d["extra" if e.is_extra else "regular"] += float(total)
        d["total"] += float(total)
    grand = regular + extra
    return {
        "from": start,
        "to": end,
        "entries": [entry_json(e) for e in entries],
        "summary": {
            "regular_total": float(regular),
            "extra_total": float(extra),
            "grand_total": float(grand),
            "days_count": len(day_summary),
            "average_day": float(grand / len(day_summary)) if day_summary else 0.0,
        },
        "product_summary": product_summary,
        "day_summary": day_summary,
    }


@app.route("/api/report/month/<year_month>", methods=["GET"])
def get_monthly_report(year_month):
    if not valid_month(year_month): return jsonify({"error": "חודש לא תקין"}), 400
    entries = DailyEntry.query.filter(DailyEntry.date.like(year_month + "%")).order_by(DailyEntry.date.asc(), DailyEntry.id.asc()).all()
    return jsonify([entry_json(e) for e in entries])


@app.route("/api/report/period", methods=["GET"])
def get_period_report():
    start = (request.args.get("from") or "").strip()
    end = (request.args.get("to") or "").strip()
    if not valid_date(start) or not valid_date(end) or start > end:
        return jsonify({"error": "טווח תאריכים לא תקין"}), 400
    entries = DailyEntry.query.filter(DailyEntry.date >= start, DailyEntry.date <= end).order_by(DailyEntry.date.asc(), DailyEntry.id.asc()).all()
    payload = build_report(entries, start, end)
    months = sorted({e.date[:7] for e in entries})
    locks = {m: bool(PeriodLock.query.filter_by(year_month=m, locked=True).first()) for m in months}
    payload["locked_months"] = locks
    payload["fully_locked"] = bool(months) and all(locks.values())
    return jsonify(payload)


@app.route("/api/report/compare", methods=["GET"])
def compare_reports():
    ranges = []
    for prefix in ("a", "b"):
        start = request.args.get(f"{prefix}_from", "")
        end = request.args.get(f"{prefix}_to", "")
        if not valid_date(start) or not valid_date(end) or start > end:
            return jsonify({"error": "טווח השוואה לא תקין"}), 400
        entries = DailyEntry.query.filter(DailyEntry.date >= start, DailyEntry.date <= end).order_by(DailyEntry.date.asc()).all()
        ranges.append(build_report(entries, start, end))
    a, b = ranges
    def pct(old, new):
        return None if old == 0 else round(((new - old) / old) * 100, 2)
    return jsonify({"a": a, "b": b, "change": {
        "grand_total": pct(a["summary"]["grand_total"], b["summary"]["grand_total"]),
        "regular_total": pct(a["summary"]["regular_total"], b["summary"]["regular_total"]),
        "extra_total": pct(a["summary"]["extra_total"], b["summary"]["extra_total"]),
        "days_count": pct(a["summary"]["days_count"], b["summary"]["days_count"]),
    }})


# ---------------------------------------------------------------------------
# Period locking
# ---------------------------------------------------------------------------
@app.route("/api/periods", methods=["GET"])
def get_periods():
    rows = PeriodLock.query.order_by(PeriodLock.year_month.desc()).all()
    return jsonify([{"year_month": r.year_month, "locked": r.locked, "locked_at": r.locked_at.isoformat() if r.locked_at else None, "locked_by": r.locked_by} for r in rows])


@app.route("/api/periods/<year_month>/lock", methods=["POST"])
def lock_period(year_month):
    denied = admin_required()
    if denied: return denied
    if not valid_month(year_month): return jsonify({"success": False, "error": "חודש לא תקין"}), 400
    try:
        row = PeriodLock.query.filter_by(year_month=year_month).first()
        if not row:
            row = PeriodLock(year_month=year_month)
            db.session.add(row)
        row.locked = True
        row.locked_at = datetime.utcnow()
        row.locked_by = session.get("username", "מערכת")
        db.session.commit()
        log_activity("LOCK_PERIOD", f"נעילת תקופה: {year_month}")
        return jsonify({"success": True})
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"success": False, "error": "שגיאת שרת"}), 500


@app.route("/api/periods/<year_month>/unlock", methods=["POST"])
def unlock_period(year_month):
    denied = admin_required()
    if denied: return denied
    if not valid_month(year_month): return jsonify({"success": False, "error": "חודש לא תקין"}), 400
    try:
        row = PeriodLock.query.filter_by(year_month=year_month).first()
        if row:
            row.locked = False
            row.locked_at = None
            row.locked_by = None
            db.session.commit()
        log_activity("UNLOCK_PERIOD", f"פתיחת תקופה: {year_month}")
        return jsonify({"success": True})
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"success": False, "error": "שגיאת שרת"}), 500


# ---------------------------------------------------------------------------
# Templates / admin / backup
# ---------------------------------------------------------------------------
@app.route("/api/templates", methods=["GET"])
def get_templates():
    return jsonify({t.name: [{"product_name": i.product_name, "quantity": i.quantity, "is_extra": bool(i.is_extra)} for i in t.items] for t in BillingTemplate.query.all()})


@app.route("/api/templates", methods=["POST"])
def save_template():
    denied = require_write_access()
    if denied: return denied
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()[:100]
    items = data.get("items") or []
    if not name or not items: return jsonify({"success": False, "error": "נתונים חסרים"}), 400
    try:
        existing = BillingTemplate.query.filter_by(name=name).first()
        if existing: db.session.delete(existing); db.session.flush()
        t = BillingTemplate(name=name)
        db.session.add(t)
        for i in items:
            qty = float(i.get("quantity", 0))
            if qty <= 0: raise ValueError
            db.session.add(BillingTemplateItem(template=t, product_name=i["product_name"], quantity=qty, is_extra=bool(i.get("is_extra", False))))
        db.session.commit()
        return jsonify({"success": True})
    except (KeyError, TypeError, ValueError):
        db.session.rollback(); return jsonify({"success": False, "error": "נתוני תבנית שגויים"}), 400
    except SQLAlchemyError:
        db.session.rollback(); return jsonify({"success": False, "error": "שגיאת שרת"}), 500


@app.route("/api/templates/<path:name>", methods=["DELETE"])
def delete_template(name):
    denied = require_write_access()
    if denied: return denied
    try:
        t = BillingTemplate.query.filter_by(name=name).first()
        if t: db.session.delete(t); db.session.commit()
        return jsonify({"success": True})
    except SQLAlchemyError:
        db.session.rollback(); return jsonify({"success": False, "error": "שגיאת שרת"}), 500


@app.route("/api/logs", methods=["GET"])
def get_logs():
    denied = admin_required()
    if denied: return denied
    return jsonify([{"time": l.timestamp.strftime("%d/%m/%Y %H:%M"), "user": l.username, "action": l.action, "details": l.details} for l in ActivityLog.query.order_by(ActivityLog.timestamp.desc()).limit(300).all()])


@app.route("/api/users", methods=["GET"])
def get_users():
    denied = admin_required()
    if denied: return denied
    return jsonify([{"id": u.id, "username": u.username, "role": u.role} for u in User.query.order_by(User.username.asc()).all()])


@app.route("/api/users", methods=["POST"])
def create_or_update_user():
    denied = admin_required()
    if denied: return denied
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()[:100]
    password = data.get("password") or ""
    role = data.get("role", "viewer")
    if role not in {"admin", "viewer"} or not username:
        return jsonify({"success": False, "error": "נתוני משתמש שגויים"}), 400
    if password and len(password) < 8:
        return jsonify({"success": False, "error": "סיסמה חייבת להכיל לפחות 8 תווים"}), 400
    try:
        user = User.query.filter_by(username=username).first()
        if user:
            if password: user.password = generate_password_hash(password)
            user.role = role
        else:
            if not password: return jsonify({"success": False, "error": "חובה סיסמה"}), 400
            db.session.add(User(username=username, password=generate_password_hash(password), role=role))
        db.session.commit()
        log_activity("USER_UPDATE", f"משתמש: {username}, תפקיד: {role}")
        return jsonify({"success": True})
    except SQLAlchemyError:
        db.session.rollback(); return jsonify({"success": False, "error": "שגיאת שרת"}), 500


@app.route("/api/users/<int:user_id>", methods=["DELETE"])
def delete_user(user_id):
    denied = admin_required()
    if denied: return denied
    try:
        user = db.session.get(User, user_id)
        if user and user.username != session.get("username"):
            db.session.delete(user); db.session.commit(); log_activity("USER_DELETE", f"משתמש: {user.username}")
        return jsonify({"success": True})
    except SQLAlchemyError:
        db.session.rollback(); return jsonify({"success": False, "error": "שגיאת שרת"}), 500


@app.route("/api/backup", methods=["GET"])
def backup_data():
    denied = admin_required()
    if denied: return denied
    return jsonify({"products": {p.name: {"price": float(p.price), "tag": p.tag or ""} for p in Product.query.all()}, "entries": [entry_json(e) for e in DailyEntry.query.all()], "timestamp": datetime.utcnow().isoformat()})


@app.route("/api/current_user", methods=["GET"])
def get_current_user_info():
    return jsonify({"username": session.get("username", "אורח"), "role": session.get("role", "viewer")})


@app.route("/api/csrf", methods=["GET"])
def csrf_info():
    # Same-origin protection is enforced globally. This endpoint exposes the
    # current security mode for future frontend upgrades without storing a
    # token in the client-side session.
    return jsonify({"same_origin_required": True})


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "false").lower() == "true")
