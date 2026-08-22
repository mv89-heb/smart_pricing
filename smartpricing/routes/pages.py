from flask import Blueprint, render_template, request, redirect, url_for, session, g
from sqlalchemy import func, select
from werkzeug.security import check_password_hash
from ..extensions import db
from ..models import User, Product, DailyEntry, israel_date

pages_bp = Blueprint("pages", __name__)

@pages_bp.route("/login", methods=["GET", "POST"])
def login():
    if g.current_user: return redirect(url_for("pages.index"))
    error=None
    if request.method=="POST":
        email=(request.form.get("email") or "").strip().lower(); user=db.session.scalar(select(User).where(func.lower(User.email)==email,User.is_active.is_(True)))
        if user and check_password_hash(user.password_hash,request.form.get("password","")):
            session.clear(); session["user_id"]=user.id; return redirect(url_for("pages.index"))
        error="כתובת אימייל או סיסמה שגויים"
    return render_template("login.html",error=error)

@pages_bp.get("/logout")
def logout(): session.clear(); return redirect(url_for("pages.login"))

@pages_bp.get("/")
def index():
    module=request.args.get("module","dashboard")
    if module=="pricing": return render_template("modules/pricing.html",products=db.session.scalars(select(Product).where(Product.tenant_id==g.current_user.tenant_id).order_by(Product.name)).all())
    if module=="daily":
        products=db.session.scalars(select(Product).where(Product.tenant_id==g.current_user.tenant_id,Product.is_active.is_(True)).order_by(Product.name)).all(); entries=db.session.execute(select(DailyEntry,Product).join(Product).where(DailyEntry.tenant_id==g.current_user.tenant_id).order_by(DailyEntry.date.desc(),DailyEntry.id.desc()).limit(100)).all(); return render_template("modules/daily.html",products=products,entries=entries)
    if module=="reports": return render_template("modules/reports.html",products=db.session.scalars(select(Product).where(Product.tenant_id==g.current_user.tenant_id,Product.is_active.is_(True)).order_by(Product.name)).all())
    if module=="users": return render_template("modules/users.html",users=db.session.scalars(select(User).where(User.tenant_id==g.current_user.tenant_id).order_by(User.name)).all())
    today=israel_date(); start=today.replace(day=1); revenue=db.session.scalar(select(func.coalesce(func.sum(DailyEntry.quantity*DailyEntry.price_at_time),0)).where(DailyEntry.tenant_id==g.current_user.tenant_id,DailyEntry.date>=start)); count=db.session.scalar(select(func.count(DailyEntry.id)).where(DailyEntry.tenant_id==g.current_user.tenant_id,DailyEntry.date>=start)) or 0; active=db.session.scalar(select(func.count(Product.id)).where(Product.tenant_id==g.current_user.tenant_id,Product.is_active.is_(True))) or 0; recent=db.session.execute(select(DailyEntry,Product,User).join(Product).outerjoin(User,DailyEntry.recorded_by==User.id).where(DailyEntry.tenant_id==g.current_user.tenant_id).order_by(DailyEntry.date.desc(),DailyEntry.id.desc()).limit(10)).all(); return render_template("modules/dashboard.html",metrics={"monthly_revenue":float(revenue or 0),"monthly_entries":count,"active_products":active},activities=recent)
