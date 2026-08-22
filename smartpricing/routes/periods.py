from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, g
from sqlalchemy import select
from ..extensions import db
from ..models import PeriodLock
from ..security import require_role, audit

periods_bp = Blueprint("periods", __name__, url_prefix="/api/periods")

@periods_bp.get("")
def list_periods():
    rows = db.session.scalars(select(PeriodLock).where(PeriodLock.tenant_id == g.current_user.tenant_id).order_by(PeriodLock.year_month.desc())).all()
    return jsonify([{ "year_month": r.year_month, "locked": r.locked } for r in rows])

@periods_bp.post("/<year_month>/lock")
@require_role("admin")
def lock_period(year_month):
    try: datetime.strptime(year_month, "%Y-%m")
    except ValueError: return jsonify(status="error", message="תקופה לא תקינה"), 400
    row = db.session.scalar(select(PeriodLock).where(PeriodLock.tenant_id == g.current_user.tenant_id, PeriodLock.year_month == year_month))
    if not row: row = PeriodLock(tenant_id=g.current_user.tenant_id, year_month=year_month); db.session.add(row)
    row.locked = True; row.locked_at = datetime.now(timezone.utc).replace(tzinfo=None); row.locked_by = g.current_user.name; audit("PERIOD_LOCK", year_month); db.session.commit()
    return jsonify(status="success", message="התקופה ננעלה")

@periods_bp.post("/<year_month>/unlock")
@require_role("admin")
def unlock_period(year_month):
    row = db.session.scalar(select(PeriodLock).where(PeriodLock.tenant_id == g.current_user.tenant_id, PeriodLock.year_month == year_month))
    if row: row.locked = False; audit("PERIOD_UNLOCK", year_month); db.session.commit()
    return jsonify(status="success", message="התקופה שוחררה")
