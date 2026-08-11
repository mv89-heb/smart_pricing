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
    if not isinstance(value, str): return False
    try: datetime.strptime(value, "%Y-%m-%d"); return len(value) == 10
    except ValueError: return False

def valid_month(value):
    if not isinstance(value, str) or len(value) != 7 or value[4] != "-": return False
    try: datetime.strptime(value, "%Y-%m"); return True
    except ValueError: return False

def entry_total(entry):
    if entry.total_amount is not None: return money(entry.total_amount)
    return (money(entry.quantity) * money(entry.unit_price)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def entry_json(entry):
    return {"id":entry.id,"date":entry.date,"product_name":entry.product_name,"quantity":entry.quantity,"is_extra":bool(entry.is_extra),"unit_price":float(entry.unit_price or 0),"total_amount":float(entry_total(entry)),"note":entry.note}

def _column_exists(table_name, column_name):
    try: return column_name in [c["name"] for c in db.inspect(db.engine).get_columns(table_name)]
    except Exception: return True

def _run_migrations():
    for table, column, sql in [("daily_entry","total_amount","ALTER TABLE daily_entry ADD COLUMN total_amount NUMERIC(14,2)"),("product","tag","ALTER TABLE product ADD COLUMN tag VARCHAR(80)")]:
        try:
            if not _column_exists(table,column): db.session.execute(text(sql)); db.session.commit()
        except Exception: db.session.rollback()
    try:
        db.session.execute(text("UPDATE daily_entry SET total_amount = ROUND(COALESCE(quantity,0) * COALESCE(unit_price,0), 2) WHERE total_amount IS NULL")); db.session.commit()
    except Exception: db.session.rollback()
    if db.engine.name == "postgresql":
        for sql in [
            "ALTER TABLE daily_entry ALTER COLUMN unit_price TYPE NUMERIC(12,2) USING ROUND(unit_price::numeric, 2)",
            "ALTER TABLE product ALTER COLUMN price TYPE NUMERIC(12,2) USING ROUND(price::numeric, 2)"]:
            try: db.session.execute(text(sql)); db.session.commit()
            except Exception: db.session.rollback()

def log_activity(action, details):
    try:
        db.session.add(ActivityLog(action=action,details=str(details)[:1000],username=session.get("username","מערכת")))
        if ActivityLog.query.count() > 2000:
            old=ActivityLog.query.order_by(ActivityLog.timestamp.asc()).first()
            if old: db.session.delete(old)
        db.session.commit()
    except Exception: db.session.rollback()

def period_locked(date_or_month): return PeriodLock.query.filter_by(year_month=date_or_month[:7],locked=True).first() is not None

def write_access():
    if not session.get("logged_in"): return jsonify({"error":"Unauthorized"}),401
    if session.get("role","viewer") == "viewer": return jsonify({"success":False,"error":"אין הרשאות"}),403
    return None

def admin_access():
    if not session.get("logged_in"): return jsonify({"error":"Unauthorized"}),401
    if session.get("role") != "admin": return jsonify({"error":"נדרש מנהל"}),403
    return None

with app.app_context():
    db.create_all(); _run_migrations()
    if User.query.count() == 0:
        temp_pass=secrets.token_urlsafe(8)
        db.session.add(User(username="admin",password=generate_password_hash(temp_pass),role="admin")); db.session.commit()
        print(f"SECURITY NOTICE: initial admin password generated for admin: {temp_pass}")

@app.before_request
def require_login():
    if request.endpoint in {"login","static"}: return None
    if request.path.startswith("/api/") and not session.get("logged_in"): return jsonify({"error":"Unauthorized"}),401
    if not request.path.startswith("/api/") and not session.get("logged_in"): return redirect(url_for("login"))
    if request.method in {"POST","PUT","PATCH","DELETE"}:
        origin=request.headers.get("Origin")
        if origin and origin.rstrip("/") != request.host_url.rstrip("/"): return jsonify({"error":"CSRF verification failed"}),403
        if request.path.startswith("/api/") and request.headers.get("X-Requested-With") != "XMLHttpRequest": return jsonify({"error":"CSRF verification failed"}),403

@app.after_request
def security_headers(response):
    response.headers.setdefault("X-Content-Type-Options","nosniff")
    response.headers.setdefault("X-Frame-Options","SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy","strict-origin-when-cross-origin")
    if request.is_secure: response.headers.setdefault("Strict-Transport-Security","max-age=31536000; includeSubDomains")
    return response

@app.route("/")
def index():
    html=render_template("index.html")
    marker="</body>"
    if marker in html and "/static/ux-enhancements.js" not in html:
        html=html.replace(marker,'<script src="/static/ux-enhancements.js" defer></script>'+marker)
    return make_response(html)

@app.route("/periodic-report")
def periodic_report(): return send_from_directory(app.static_folder,"periodic_report.html")

@app.route("/login",methods=["GET","POST"])
def login():
    if request.method=="GET": return render_template("login.html")
    ip=request.remote_addr or "unknown"; now=time.time(); bucket=_LOGIN_BUCKETS.setdefault(ip,[]); bucket[:]=[t for t in bucket if now-t<LOGIN_WINDOW_SECONDS]
    if len(bucket)>=LOGIN_MAX_ATTEMPTS: return jsonify({"success":False,"message":"יותר מדי ניסיונות. נסה שוב בעוד מספר דקות."}),429
    bucket.append(now)
    data=request.get_json(silent=True) or {}; username=(data.get("username") or "").strip(); password=data.get("password") or ""; user=User.query.filter_by(username=username).first(); valid=False
    if user:
        try: valid=check_password_hash(user.password,password)
        except Exception: valid=False
    if not user or not valid:
        log_activity("LOGIN_FAILED",f"ניסיון התחברות כושל עבור {username[:80]}"); return jsonify({"success":False,"message":"שם משתמש או סיסמה שגויים"}),401
    session.clear(); session.permanent=True; session["logged_in"]=True; session["username"]=user.username; session["role"]=user.role; log_activity("LOGIN","התחברות למערכת")
    return jsonify({"success":True,"role":user.role,"username":user.username})

@app.route("/logout")
def logout():
    if session.get("logged_in"): log_activity("LOGOUT","התנתקות מהמערכת")
    session.clear(); return redirect(url_for("login"))

@app.route("/api/products",methods=["GET"])
def get_products(): return jsonify({p.name:float(p.price or 0) for p in Product.query.order_by(Product.name.asc()).all()})

@app.route("/api/products/details",methods=["GET"])
def get_product_details(): return jsonify([{"id":p.id,"name":p.name,"price":float(p.price or 0),"tag":p.tag or ""} for p in Product.query.order_by(Product.name.asc()).all()])

@app.route("/api/products",methods=["POST"])
def add_product():
    denied=write_access()
    if denied:return denied
    data=request.get_json(silent=True) or {}; name=(data.get("name") or "").strip(); tag=(data.get("tag") or "").strip()[:80]
    try: price=money(data.get("price"))
    except Exception:return jsonify({"success":False,"error":"מחיר לא תקין"}),400
    if not name or price<0:return jsonify({"success":False,"error":"נתונים שגויים"}),400
    if Product.query.filter_by(name=name).first():return jsonify({"success":False,"error":"מוצר קיים"}),409
    try:
        p=Product(name=name,price=price,tag=tag or None); db.session.add(p); db.session.flush(); db.session.add(PriceHistory(product_id=p.id,price=price,changed_by=session.get("username","מערכת"))); db.session.commit(); log_activity("NEW_PRODUCT",f"מוצר חדש: {name}, מחיר: {price}"); return jsonify({"success":True})
    except SQLAlchemyError:db.session.rollback();return jsonify({"success":False,"error":"שגיאת שרת"}),500

@app.route("/api/products/<path:name>",methods=["PUT"])
def update_product(name):
    denied=write_access()
    if denied:return denied
    data=request.get_json(silent=True) or {}; p=Product.query.filter_by(name=name).first()
    if not p:return jsonify({"success":False,"error":"לא נמצא"}),404
    new_name=(data.get("name") or name).strip(); tag=(data.get("tag") or p.tag or "").strip()[:80]
    try:new_price=money(data.get("price",p.price))
    except Exception:return jsonify({"success":False,"error":"מחיר לא תקין"}),400
    if not new_name or new_price<0:return jsonify({"success":False,"error":"נתונים שגויים"}),400
    if new_name!=name and Product.query.filter_by(name=new_name).first():return jsonify({"success":False,"error":"מוצר קיים"}),409
    try:
        old=money(p.price); p.name=new_name;p.tag=tag or None;p.price=new_price
        if new_name!=name: DailyEntry.query.filter_by(product_name=name).update({DailyEntry.product_name:new_name}); BillingTemplateItem.query.filter_by(product_name=name).update({BillingTemplateItem.product_name:new_name})
        if old!=new_price:db.session.add(PriceHistory(product_id=p.id,price=new_price,changed_by=session.get("username","מערכת")))
        db.session.commit();log_activity("UPDATE_PRICE",f"מוצר: {name} -> {new_name}; מחיר: {old} -> {new_price}");return jsonify({"success":True})
    except SQLAlchemyError:db.session.rollback();return jsonify({"success":False,"error":"שגיאת שרת"}),500

@app.route("/api/products/<path:name>",methods=["DELETE"])
def delete_product(name):
    denied=write_access()
    if denied:return denied
    try:
        p=Product.query.filter_by(name=name).first()
        if p:db.session.delete(p);db.session.commit();log_activity("DELETE_PRODUCT",f"מוצר: {name}")
        return jsonify({"success":True})
    except SQLAlchemyError:db.session.rollback();return jsonify({"success":False,"error":"שגיאת שרת"}),500

@app.route("/api/products/<path:name>/history")
def product_history(name):
    p=Product.query.filter_by(name=name).first()
    if not p:return jsonify({"error":"לא נמצא"}),404
    return jsonify([{"price":float(r.price),"changed_at":r.changed_at.isoformat(),"changed_by":r.changed_by} for r in PriceHistory.query.filter_by(product_id=p.id).order_by(PriceHistory.changed_at.desc()).all()])

@app.route("/api/entries/<date>")
def get_entries(date):
    if not valid_date(date):return jsonify({"error":"תאריך לא תקין"}),400
    return jsonify([entry_json(e) for e in DailyEntry.query.filter_by(date=date).order_by(DailyEntry.id.asc()).all()])

@app.route("/api/entries",methods=["POST"])
def add_entry():
    denied=write_access()
    if denied:return denied
    data=request.get_json(silent=True) or {}; date=data.get("date"); product_name=(data.get("product_name") or "").strip(); note=(data.get("note") or "").strip()[:255]
    if not valid_date(date) or not product_name:return jsonify({"success":False,"error":"נתונים שגויים"}),400
    if period_locked(date):return jsonify({"success":False,"error":"התקופה נעולה. נדרש מנהל כדי לשנות חיובים."}),423
    try:quantity=float(data.get("quantity")); assert 0<quantity<=1000000
    except (TypeError,ValueError,AssertionError):return jsonify({"success":False,"error":"כמות לא תקינה"}),400
    product=Product.query.filter_by(name=product_name).first(); current_price=money(product.price if product else 0); extra=bool(data.get("is_extra",False))
    try:
        existing=DailyEntry.query.filter_by(date=date,product_name=product_name,is_extra=extra).first()
        if existing and not note and money(existing.unit_price)==current_price:
            existing.quantity=float(existing.quantity)+quantity;existing.total_amount=(money(existing.quantity)*current_price).quantize(Decimal("0.01"))
        else:
            db.session.add(DailyEntry(date=date,product_name=product_name,quantity=quantity,is_extra=extra,unit_price=current_price,total_amount=(money(quantity)*current_price).quantize(Decimal("0.01")),note=note or None))
        db.session.commit();log_activity("ADD_ENTRY",f"{date} | {product_name} | {quantity} | {current_price}");return jsonify({"success":True})
    except SQLAlchemyError:db.session.rollback();return jsonify({"success":False,"error":"שגיאת שרת"}),500

@app.route("/api/entries/<int:entry_id>",methods=["PUT"])
def update_entry(entry_id):
    denied=write_access()
    if denied:return denied
    data=request.get_json(silent=True) or {}; e=db.session.get(DailyEntry,entry_id)
    if not e:return jsonify({"success":False,"error":"לא נמצא"}),404
    if period_locked(e.date):return jsonify({"success":False,"error":"התקופה נעולה. נדרש מנהל כדי לשנות חיובים."}),423
    before=entry_json(e)
    try:
        if "quantity" in data:
            q=float(data["quantity"])
            if q<=0 or q>1000000:raise ValueError
            e.quantity=q
        if "is_extra" in data:e.is_extra=bool(data["is_extra"])
        if "note" in data:e.note=(data["note"] or "").strip()[:255] or None
        e.total_amount=(money(e.quantity)*money(e.unit_price)).quantize(Decimal("0.01"));db.session.commit();log_activity("UPDATE_ENTRY",f"חיוב #{e.id}; לפני={before}; אחרי={entry_json(e)}");return jsonify({"success":True})
    except (TypeError,ValueError):db.session.rollback();return jsonify({"success":False,"error":"נתונים שגויים"}),400
    except SQLAlchemyError:db.session.rollback();return jsonify({"success":False,"error":"שגיאת שרת"}),500

@app.route("/api/entries/<int:entry_id>",methods=["DELETE"])
def delete_entry(entry_id):
    denied=write_access()
    if denied:return denied
    e=db.session.get(DailyEntry,entry_id)
    if not e:return jsonify({"success":True})
    if period_locked(e.date):return jsonify({"success":False,"error":"התקופה נעולה. נדרש מנהל כדי לשנות חיובים."}),423
    details=entry_json(e)
    try:db.session.delete(e);db.session.commit();log_activity("DELETE_ENTRY",f"חיוב נמחק: {details}");return jsonify({"success":True})
    except SQLAlchemyError:db.session.rollback();return jsonify({"success":False,"error":"שגיאת שרת"}),500

@app.route("/api/bulk/entries/<date>",methods=["DELETE"])
def clear_date_entries(date):
    denied=write_access()
    if denied:return denied
    if not valid_date(date):return jsonify({"success":False,"error":"תאריך לא תקין"}),400
    if period_locked(date):return jsonify({"success":False,"error":"התקופה נעולה"}),423
    try:DailyEntry.query.filter_by(date=date).delete();db.session.commit();log_activity("CLEAR_DAY",f"ניקוי יום: {date}");return jsonify({"success":True})
    except SQLAlchemyError:db.session.rollback();return jsonify({"success":False,"error":"שגיאת שרת"}),500

@app.route("/api/bulk/season",methods=["DELETE"])
def reset_season():
    denied=admin_access()
    if denied:return denied
    try:DailyEntry.query.delete();db.session.commit();log_activity("RESET_SEASON","מחיקת כל החיובים");return jsonify({"success":True})
    except SQLAlchemyError:db.session.rollback();return jsonify({"success":False,"error":"שגיאת שרת"}),500

def build_report(entries,start=None,end=None):
    regular=Decimal("0.00");extra=Decimal("0.00");products={};days={}
    for e in entries:
        total=entry_total(e)
        if e.is_extra:extra+=total
        else:regular+=total
        p=products.setdefault(e.product_name,{"quantity":0.0,"total":0.0});p["quantity"]+=float(e.quantity or 0);p["total"]=float(Decimal(str(p["total"]))+total)
        d=days.setdefault(e.date,{"regular":0.0,"extra":0.0,"total":0.0});d["extra" if e.is_extra else "regular"]+=float(total);d["total"]+=float(total)
    grand=regular+extra
    return {"from":start,"to":end,"entries":[entry_json(e) for e in entries],"summary":{"regular_total":float(regular),"extra_total":float(extra),"grand_total":float(grand),"days_count":len(days),"average_day":float(grand/len(days)) if days else 0.0},"product_summary":products,"day_summary":days}

@app.route("/api/report/month/<year_month>")
def get_monthly_report(year_month):
    if not valid_month(year_month):return jsonify({"error":"חודש לא תקין"}),400
    return jsonify([entry_json(e) for e in DailyEntry.query.filter(DailyEntry.date.like(year_month+"%")).order_by(DailyEntry.date.asc(),DailyEntry.id.asc()).all()])

@app.route("/api/report/period")
def get_period_report():
    start=(request.args.get("from") or "").strip();end=(request.args.get("to") or "").strip()
    if not valid_date(start) or not valid_date(end) or start>end:return jsonify({"error":"טווח תאריכים לא תקין"}),400
    entries=DailyEntry.query.filter(DailyEntry.date>=start,DailyEntry.date<=end).order_by(DailyEntry.date.asc(),DailyEntry.id.asc()).all();payload=build_report(entries,start,end)
    months=sorted({e.date[:7] for e in entries});locks={m:bool(PeriodLock.query.filter_by(year_month=m,locked=True).first()) for m in months};payload["locked_months"]=locks;payload["fully_locked"]=bool(months) and all(locks.values());return jsonify(payload)

@app.route("/api/report/compare")
def compare_reports():
    data=[]
    for prefix in ("a","b"):
        start=request.args.get(prefix+"_from","");end=request.args.get(prefix+"_to","")
        if not valid_date(start) or not valid_date(end) or start>end:return jsonify({"error":"טווח השוואה לא תקין"}),400
        data.append(build_report(DailyEntry.query.filter(DailyEntry.date>=start,DailyEntry.date<=end).order_by(DailyEntry.date.asc()).all(),start,end))
    a,b=data
    def pct(old,new):return None if old==0 else round((new-old)/old*100,2)
    return jsonify({"a":a,"b":b,"change":{"grand_total":pct(a["summary"]["grand_total"],b["summary"]["grand_total"]),"regular_total":pct(a["summary"]["regular_total"],b["summary"]["regular_total"]),"extra_total":pct(a["summary"]["extra_total"],b["summary"]["extra_total"]),"days_count":pct(a["summary"]["days_count"],b["summary"]["days_count"])}})

@app.route("/api/periods")
def get_periods():return jsonify([{"year_month":r.year_month,"locked":r.locked,"locked_at":r.locked_at.isoformat() if r.locked_at else None,"locked_by":r.locked_by} for r in PeriodLock.query.order_by(PeriodLock.year_month.desc()).all()])

@app.route("/api/periods/<year_month>/lock",methods=["POST"])
def lock_period(year_month):
    denied=admin_access()
    if denied:return denied
    if not valid_month(year_month):return jsonify({"success":False,"error":"חודש לא תקין"}),400
    try:
        r=PeriodLock.query.filter_by(year_month=year_month).first() or PeriodLock(year_month=year_month);db.session.add(r);r.locked=True;r.locked_at=datetime.utcnow();r.locked_by=session.get("username","מערכת");db.session.commit();log_activity("LOCK_PERIOD",f"נעילת תקופה: {year_month}");return jsonify({"success":True})
    except SQLAlchemyError:db.session.rollback();return jsonify({"success":False,"error":"שגיאת שרת"}),500

@app.route("/api/periods/<year_month>/unlock",methods=["POST"])
def unlock_period(year_month):
    denied=admin_access()
    if denied:return denied
    if not valid_month(year_month):return jsonify({"success":False,"error":"חודש לא תקין"}),400
    try:
        r=PeriodLock.query.filter_by(year_month=year_month).first()
        if r:r.locked=False;r.locked_at=None;r.locked_by=None;db.session.commit()
        log_activity("UNLOCK_PERIOD",f"פתיחת תקופה: {year_month}");return jsonify({"success":True})
    except SQLAlchemyError:db.session.rollback();return jsonify({"success":False,"error":"שגיאת שרת"}),500

@app.route("/api/templates")
def get_templates():return jsonify({t.name:[{"product_name":i.product_name,"quantity":i.quantity,"is_extra":bool(i.is_extra)} for i in t.items] for t in BillingTemplate.query.all()})

@app.route("/api/templates",methods=["POST"])
def save_template():
    denied=write_access()
    if denied:return denied
    data=request.get_json(silent=True) or {};name=(data.get("name") or "").strip()[:100];items=data.get("items") or []
    if not name or not items:return jsonify({"success":False,"error":"נתונים חסרים"}),400
    try:
        old=BillingTemplate.query.filter_by(name=name).first()
        if old:db.session.delete(old);db.session.flush()
        t=BillingTemplate(name=name);db.session.add(t)
        for i in items:
            q=float(i.get("quantity",0))
            if q<=0:raise ValueError
            db.session.add(BillingTemplateItem(template=t,product_name=i["product_name"],quantity=q,is_extra=bool(i.get("is_extra",False))))
        db.session.commit();return jsonify({"success":True})
    except (KeyError,TypeError,ValueError):db.session.rollback();return jsonify({"success":False,"error":"נתוני תבנית שגויים"}),400
    except SQLAlchemyError:db.session.rollback();return jsonify({"success":False,"error":"שגיאת שרת"}),500

@app.route("/api/templates/<path:name>",methods=["DELETE"])
def delete_template(name):
    denied=write_access()
    if denied:return denied
    try:
        t=BillingTemplate.query.filter_by(name=name).first()
        if t:db.session.delete(t);db.session.commit()
        return jsonify({"success":True})
    except SQLAlchemyError:db.session.rollback();return jsonify({"success":False,"error":"שגיאת שרת"}),500

@app.route("/api/logs")
def get_logs():
    denied=admin_access()
    if denied:return denied
    return jsonify([{"time":l.timestamp.strftime("%d/%m/%Y %H:%M"),"user":l.username,"action":l.action,"details":l.details} for l in ActivityLog.query.order_by(ActivityLog.timestamp.desc()).limit(300).all()])

@app.route("/api/users")
def get_users():
    denied=admin_access()
    if denied:return denied
    return jsonify([{"id":u.id,"username":u.username,"role":u.role} for u in User.query.order_by(User.username.asc()).all()])

@app.route("/api/users",methods=["POST"])
def create_or_update_user():
    denied=admin_access()
    if denied:return denied
    data=request.get_json(silent=True) or {};username=(data.get("username") or "").strip()[:100];password=data.get("password") or "";role=data.get("role","viewer")
    if role not in {"admin","viewer"} or not username:return jsonify({"success":False,"error":"נתוני משתמש שגויים"}),400
    if password and len(password)<8:return jsonify({"success":False,"error":"סיסמה חייבת להכיל לפחות 8 תווים"}),400
    try:
        u=User.query.filter_by(username=username).first()
        if u:
            if password:u.password=generate_password_hash(password)
            u.role=role
        else:
            if not password:return jsonify({"success":False,"error":"חובה סיסמה"}),400
            db.session.add(User(username=username,password=generate_password_hash(password),role=role))
        db.session.commit();log_activity("USER_UPDATE",f"משתמש: {username}, תפקיד: {role}");return jsonify({"success":True})
    except SQLAlchemyError:db.session.rollback();return jsonify({"success":False,"error":"שגיאת שרת"}),500

@app.route("/api/users/<int:user_id>",methods=["DELETE"])
def delete_user(user_id):
    denied=admin_access()
    if denied:return denied
    try:
        u=db.session.get(User,user_id)
        if u and u.username!=session.get("username"):db.session.delete(u);db.session.commit();log_activity("USER_DELETE",f"משתמש: {u.username}")
        return jsonify({"success":True})
    except SQLAlchemyError:db.session.rollback();return jsonify({"success":False,"error":"שגיאת שרת"}),500

@app.route("/api/backup")
def backup_data():
    denied=admin_access()
    if denied:return denied
    return jsonify({"products":{p.name:{"price":float(p.price),"tag":p.tag or ""} for p in Product.query.all()},"entries":[entry_json(e) for e in DailyEntry.query.all()],"timestamp":datetime.utcnow().isoformat()})

@app.route("/api/current_user")
def get_current_user_info():return jsonify({"username":session.get("username","אורח"),"role":session.get("role","viewer")})

@app.route("/api/csrf")
def csrf_info():return jsonify({"same_origin_required":True})

if __name__=="__main__":app.run(debug=os.environ.get("FLASK_DEBUG","false").lower()=="true")
