from datetime import date
from flask import Blueprint, request, jsonify, g
from sqlalchemy import select
from ..extensions import db
from ..models import DailyEntry, Product, PeriodLock
from ..security import require_role, audit
from ..services.pricing import effective_price

entries_bp = Blueprint("entries", __name__, url_prefix="/api/entries")


def _period_locked(tenant_id, d):
    ym = d.strftime("%Y-%m")
    return db.session.scalar(select(PeriodLock.id).where(PeriodLock.tenant_id == tenant_id, PeriodLock.year_month == ym, PeriodLock.locked.is_(True))) is not None


@entries_bp.post("")
@require_role("editor")
def create_entry():
    data = request.get_json(silent=True) or {}
    try:
        d = date.fromisoformat(data["date"]); pid = int(data["product_id"]); qty = float(data["quantity"])
    except (KeyError, TypeError, ValueError):
        return jsonify(status="error", message="נתוני דיווח לא תקינים"), 400
    if qty <= 0: return jsonify(status="error", message="הכמות חייבת להיות גדולה מאפס"), 400
    if _period_locked(g.current_user.tenant_id, d): return jsonify(status="error", message="התקופה נעולה"), 409
    product = db.session.scalar(select(Product).where(Product.id == pid, Product.tenant_id == g.current_user.tenant_id, Product.is_active.is_(True)))
    if not product: return jsonify(status="error", message="המוצר לא נמצא או אינו פעיל"), 404
    etype = data.get("entry_type", "regular")
    if etype not in {"regular", "extra", "special"}: return jsonify(status="error", message="סוג דיווח לא תקין"), 400
    price = effective_price(product.id, d)
    entry = DailyEntry(tenant_id=g.current_user.tenant_id, date=d, product_id=product.id, quantity=qty, price_at_time=price, entry_type=etype, notes=(data.get("notes") or "").strip() or None, recorded_by=g.current_user.id)
    db.session.add(entry); audit("ENTRY_CREATE", f"{product.name} x {qty} @ {d.isoformat()}"); db.session.commit()
    return jsonify(status="success", message="החיוב נשמר בהצלחה", id=entry.id, price_at_time=float(price), total=float(price) * qty)


@entries_bp.put("/<int:entry_id>")
@require_role("editor")
def update_entry(entry_id):
    entry = db.session.scalar(select(DailyEntry).where(DailyEntry.id == entry_id, DailyEntry.tenant_id == g.current_user.tenant_id))
    if not entry: return jsonify(status="error", message="הדיווח לא נמצא"), 404
    data = request.get_json(silent=True) or {}
    d = date.fromisoformat(data.get("date", entry.date.isoformat()))
    if _period_locked(g.current_user.tenant_id, entry.date) or _period_locked(g.current_user.tenant_id, d): return jsonify(status="error", message="התקופה נעולה"), 409
    qty = float(data.get("quantity", entry.quantity))
    if qty <= 0: return jsonify(status="error", message="הכמות חייבת להיות גדולה מאפס"), 400
    etype = data.get("entry_type", entry.entry_type)
    if etype not in {"regular", "extra", "special"}: return jsonify(status="error", message="סוג דיווח לא תקין"), 400
    entry.date, entry.quantity, entry.entry_type, entry.notes = d, qty, etype, (data.get("notes", entry.notes) or "").strip() or None
    entry.price_at_time = effective_price(entry.product_id, d)
    audit("ENTRY_UPDATE", str(entry.id)); db.session.commit()
    return jsonify(status="success", message="הדיווח עודכן בהצלחה")


@entries_bp.delete("/<int:entry_id>")
@require_role("editor")
def delete_entry(entry_id):
    entry = db.session.scalar(select(DailyEntry).where(DailyEntry.id == entry_id, DailyEntry.tenant_id == g.current_user.tenant_id))
    if not entry: return jsonify(status="error", message="הדיווח לא נמצא"), 404
    if _period_locked(g.current_user.tenant_id, entry.date): return jsonify(status="error", message="התקופה נעולה"), 409
    db.session.delete(entry); audit("ENTRY_DELETE", str(entry.id)); db.session.commit()
    return jsonify(status="success", message="הדיווח נמחק בהצלחה")


@entries_bp.post("/copy")
@require_role("editor")
def copy_day():
    data = request.get_json(silent=True) or {}
    try: source = date.fromisoformat(data["source_date"]); target = date.fromisoformat(data["target_date"])
    except (KeyError, ValueError, TypeError): return jsonify(status="error", message="תאריכים לא תקינים"), 400
    if _period_locked(g.current_user.tenant_id, target): return jsonify(status="error", message="תקופת היעד נעולה"), 409
    rows = db.session.scalars(select(DailyEntry).where(DailyEntry.tenant_id == g.current_user.tenant_id, DailyEntry.date == source)).all()
    for old in rows:
        db.session.add(DailyEntry(tenant_id=old.tenant_id, date=target, product_id=old.product_id, quantity=old.quantity, price_at_time=effective_price(old.product_id, target), entry_type=old.entry_type, notes=old.notes, recorded_by=g.current_user.id))
    audit("DAY_COPY", f"{source.isoformat()} -> {target.isoformat()} ({len(rows)})"); db.session.commit()
    return jsonify(status="success", message="היום הועתק בהצלחה", count=len(rows))
