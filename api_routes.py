"""Core API routes for Smart Pricing.

This module owns the application's business API routes. Production-specific
composition is intentionally kept outside this module so importing the routes
does not implicitly import other WSGI layers.
"""
from datetime import datetime, timezone
from decimal import Decimal

import app as base
from flask import jsonify, request
from sqlalchemy.exc import SQLAlchemyError

from services.reporting import compare_periods, period_report

app = base.app
db = base.db
Product = base.Product
DailyEntry = base.DailyEntry
PriceHistory = base.PriceHistory
PeriodLock = base.PeriodLock
BillingTemplate = base.BillingTemplate


def _deny_write():
    return base.write_access()


def _period_is_locked(date_value):
    return PeriodLock.query.filter_by(year_month=date_value[:7], locked=True).first() is not None


def _price_for_date(product, iso_date):
    rows = (PriceHistory.query.filter_by(product_id=product.id)
            .order_by(PriceHistory.effective_from.asc(), PriceHistory.id.asc()).all())
    if not rows:
        return base.money(product.price)
    candidates = [row for row in rows if row.effective_from and row.effective_from <= iso_date]
    if candidates:
        return base.money(candidates[-1].price)
    return base.money(rows[0].price)


def _entry_payload(entry):
    return base.entry_json(entry)


def _period_payload(start, end):
    return period_report(base, start, end)


def _valid_range(start, end):
    return base.valid_date(start) and base.valid_date(end) and start <= end


@app.route("/api/products/<path:product_name>", methods=["PUT"])
def update_product(product_name):
    denied = _deny_write()
    if denied:
        return denied
    product = Product.query.filter_by(name=product_name).first()
    if not product:
        return jsonify({"success": False, "error": "מוצר לא נמצא"}), 404
    data = request.get_json(silent=True) or {}
    name = str(data.get("name") or product.name).strip()[:100]
    if not name:
        return jsonify({"success": False, "error": "שם מוצר לא תקין"}), 400
    try:
        price = base.money(data.get("price"))
    except Exception:
        return jsonify({"success": False, "error": "מחיר לא תקין"}), 400
    if price < 0:
        return jsonify({"success": False, "error": "מחיר לא תקין"}), 400
    effective = str(data.get("effective_from") or base.today_iso()).strip()
    if not base.valid_date(effective):
        return jsonify({"success": False, "error": "תאריך תוקף לא תקין"}), 400
    if name != product.name and Product.query.filter(Product.name == name, Product.id != product.id).first():
        return jsonify({"success": False, "error": "מוצר קיים"}), 409
    if _period_is_locked(effective):
        return jsonify({"success": False, "error": "התקופה נעולה"}), 423
    try:
        old_name = product.name
        product.name = name
        existing = (PriceHistory.query.filter_by(product_id=product.id, effective_from=effective)
                    .order_by(PriceHistory.id.desc()).first())
        if existing:
            existing.price = price
            existing.changed_at = datetime.now(timezone.utc)
            existing.changed_by = request.environ.get("REMOTE_USER") or "מערכת"
        else:
            db.session.add(PriceHistory(product_id=product.id, price=price, effective_from=effective,
                                        changed_by="מערכת"))
        if effective <= base.today_iso():
            product.price = price
        db.session.commit()
        base.log_activity("PRICE_UPDATE", f"מחיר מוצר: {old_name} -> {product.name}, {price}, תקף מ-{effective}")
        return jsonify({"success": True, "name": product.name, "price": float(product.price),
                        "effective_from": effective})
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"success": False, "error": "שגיאת שרת"}), 500


@app.route("/api/products/<path:product_name>/scheduled", methods=["DELETE"])
def cancel_scheduled_prices(product_name):
    denied = _deny_write()
    if denied:
        return denied
    product = Product.query.filter_by(name=product_name).first()
    if not product:
        return jsonify({"success": False, "error": "מוצר לא נמצא"}), 404
    today = base.today_iso()
    rows = PriceHistory.query.filter(PriceHistory.product_id == product.id,
                                     PriceHistory.effective_from > today).all()
    try:
        count = len(rows)
        for row in rows:
            db.session.delete(row)
        db.session.commit()
        if count:
            base.log_activity("CANCEL_SCHEDULED_PRICE", f"בוטלו {count} מחירי עתיד עבור {product.name}")
        return jsonify({"success": True, "cancelled": count})
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"success": False, "error": "שגיאת שרת"}), 500


@app.route("/api/entries", methods=["POST"])
def create_entry():
    denied = _deny_write()
    if denied:
        return denied
    data = request.get_json(silent=True) or {}
    date_value = str(data.get("date") or "").strip()
    name = str(data.get("product_name") or "").strip()
    if not base.valid_date(date_value) or not name:
        return jsonify({"success": False, "error": "נתונים שגויים"}), 400
    if _period_is_locked(date_value):
        return jsonify({"success": False, "error": "התקופה נעולה"}), 423
    product = Product.query.filter_by(name=name).first()
    if not product:
        return jsonify({"success": False, "error": "מוצר לא נמצא"}), 404
    try:
        quantity = float(data.get("quantity"))
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "כמות לא תקינה"}), 400
    if quantity <= 0:
        return jsonify({"success": False, "error": "כמות חייבת להיות חיובית"}), 400
    is_extra = bool(data.get("is_extra", False))
    selected_price = _price_for_date(product, date_value)
    note = str(data.get("note") or "").strip()[:255] or None
    try:
        existing = (DailyEntry.query.filter_by(date=date_value, product_name=product.name, is_extra=is_extra)
                    .order_by(DailyEntry.id.asc()).first())
        if existing is not None:
            effective_price = base.money(existing.unit_price)
            existing.quantity = float(existing.quantity or 0) + quantity
            existing.total_amount = (base.money(existing.quantity) * effective_price).quantize(Decimal("0.01"))
            if note:
                existing.note = note
            db.session.commit()
            return jsonify(_entry_payload(existing))
        entry = DailyEntry(date=date_value, product_name=product.name, quantity=quantity,
                           is_extra=is_extra, unit_price=selected_price,
                           total_amount=(base.money(quantity) * selected_price).quantize(Decimal("0.01")), note=note)
        db.session.add(entry)
        db.session.commit()
        return jsonify(_entry_payload(entry))
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"success": False, "error": "שגיאת שרת"}), 500


@app.route("/api/entries/<string:date_value>", methods=["GET"])
def get_entries(date_value):
    if not base.valid_date(date_value):
        return jsonify({"error": "תאריך לא תקין"}), 400
    return jsonify([_entry_payload(row) for row in DailyEntry.query.filter_by(date=date_value).order_by(DailyEntry.id.asc()).all()])


@app.route("/api/report/period", methods=["GET"])
def get_period_report():
    start = str(request.args.get("from") or "").strip()
    end = str(request.args.get("to") or "").strip()
    if not _valid_range(start, end):
        return jsonify({"error": "טווח תאריכים לא תקין"}), 400
    return jsonify(_period_payload(start, end))


def _compare_payload(a_from, a_to, b_from, b_to):
    return compare_periods(base, a_from, a_to, b_from, b_to)


@app.route("/api/report/compare", methods=["GET"])
def compare_report():
    values = [str(request.args.get(key) or "").strip() for key in ("a_from", "a_to", "b_from", "b_to")]
    if not _valid_range(values[0], values[1]) or not _valid_range(values[2], values[3]):
        return jsonify({"error": "טווח השוואה לא תקין"}), 400
    return jsonify(_compare_payload(*values))


@app.route("/api/dashboard/summary", methods=["GET"])
def dashboard_summary():
    start = str(request.args.get("from") or "").strip()
    end = str(request.args.get("to") or "").strip()
    if not _valid_range(start, end):
        return jsonify({"error": "טווח תאריכים לא תקין"}), 400
    return jsonify(_period_payload(start, end))


@app.route("/api/dashboard/compare", methods=["GET"])
def dashboard_compare():
    values = [str(request.args.get(key) or "").strip() for key in ("a_from", "a_to", "b_from", "b_to")]
    if not _valid_range(values[0], values[1]) or not _valid_range(values[2], values[3]):
        return jsonify({"error": "טווח השוואה לא תקין"}), 400
    return jsonify(_compare_payload(*values))


@app.post("/api/periods/<string:year_month>/lock")
def lock_period(year_month):
    denied = _deny_write()
    if denied:
        return denied
    if not base.valid_month(year_month):
        return jsonify({"success": False, "error": "חודש לא תקין"}), 400
    row = PeriodLock.query.filter_by(year_month=year_month).first()
    if row is None:
        row = PeriodLock(year_month=year_month, locked=True, locked_at=datetime.now(timezone.utc), locked_by="מערכת")
        db.session.add(row)
    else:
        row.locked = True
        row.locked_at = datetime.now(timezone.utc)
        row.locked_by = "מערכת"
    db.session.commit()
    return jsonify({"success": True, "year_month": year_month, "locked": True})


@app.post("/api/periods/<string:year_month>/unlock")
def unlock_period(year_month):
    denied = _deny_write()
    if denied:
        return denied
    if not base.valid_month(year_month):
        return jsonify({"success": False, "error": "חודש לא תקין"}), 400
    row = PeriodLock.query.filter_by(year_month=year_month).first()
    if row is None:
        row = PeriodLock(year_month=year_month, locked=False)
        db.session.add(row)
    else:
        row.locked = False
    db.session.commit()
    return jsonify({"success": True, "year_month": year_month, "locked": False})


@app.get("/api/templates")
def get_templates():
    return jsonify({
        template.name: [
            {"product_name": item.product_name, "quantity": item.quantity, "is_extra": bool(item.is_extra)}
            for item in template.items
        ]
        for template in BillingTemplate.query.order_by(BillingTemplate.name.asc()).all()
    })


# Compatibility hooks used by the existing frontend/services.
app.price_for_date = _price_for_date
app.money = base.money
