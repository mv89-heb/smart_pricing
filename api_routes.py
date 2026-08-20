"""Core API routes used by the production UI and test suite.

The Flask application owns models/authentication; this module provides the
business endpoints that are intentionally layered onto the production app.
"""
from datetime import datetime
from decimal import Decimal

import app as base
from flask import jsonify, request
from sqlalchemy import func, case
from sqlalchemy.exc import SQLAlchemyError

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
    return base.price_for_date(product, iso_date)


def _entry_payload(entry):
    return base.entry_json(entry)


def _period_payload(start, end):
    entries = (DailyEntry.query.filter(DailyEntry.date >= start, DailyEntry.date <= end)
               .order_by(DailyEntry.date.asc(), DailyEntry.id.asc()).all())
    regular = extra = 0.0
    products = {}
    days = {}
    payload_entries = []
    for entry in entries:
        amount = float((base.money(entry.quantity) * base.money(entry.unit_price)).quantize(Decimal("0.01")))
        if entry.is_extra:
            extra += amount
        else:
            regular += amount
        product = products.setdefault(entry.product_name, {"quantity": 0.0, "total": 0.0})
        product["quantity"] += float(entry.quantity or 0)
        product["total"] += amount
        day = days.setdefault(entry.date, {"regular": 0.0, "extra": 0.0, "total": 0.0})
        day["extra" if entry.is_extra else "regular"] += amount
        day["total"] += amount
        payload_entries.append(_entry_payload(entry))
    grand = regular + extra
    return {
        "from": start,
        "to": end,
        "entries": payload_entries,
        "summary": {
            "regular_total": regular,
            "extra_total": extra,
            "grand_total": grand,
            "days_count": len(days),
            "average_day": grand / len(days) if days else 0.0,
        },
        "product_summary": products,
        "day_summary": days,
    }


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
        product.name = name
        existing = (PriceHistory.query.filter_by(product_id=product.id, effective_from=effective)
                    .order_by(PriceHistory.id.desc()).first())
        if existing:
            existing.price = price
            existing.changed_at = datetime.utcnow()
            existing.changed_by = request.environ.get("REMOTE_USER") or "מערכת"
        else:
            db.session.add(PriceHistory(product_id=product.id, price=price, effective_from=effective,
                                        changed_by="מערכת"))
        if effective <= base.today_iso():
            product.price = price
        db.session.commit()
        base.log_activity("PRICE_UPDATE", f"מחיר מוצר: {product.name}, {price}, תקף מ-{effective}")
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
    unit_price = _price_for_date(product, date_value)
    note = str(data.get("note") or "").strip()[:255] or None
    try:
        existing = (DailyEntry.query.filter_by(date=date_value, product_name=product.name, is_extra=is_extra)
                    .order_by(DailyEntry.id.asc()).first())
        if existing is not None:
            existing.quantity = float(existing.quantity or 0) + quantity
            existing.unit_price = unit_price
            existing.total_amount = (base.money(existing.quantity) * unit_price).quantize(Decimal("0.01"))
            if note:
                existing.note = note
            db.session.commit()
            return jsonify(_entry_payload(existing))
        entry = DailyEntry(date=date_value, product_name=product.name, quantity=quantity,
                           is_extra=is_extra, unit_price=unit_price,
                           total_amount=(base.money(quantity) * unit_price).quantize(Decimal("0.01")), note=note)
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
    return jsonify([_entry_payload(row) for row in
                    DailyEntry.query.filter_by(date=date_value).order_by(DailyEntry.id.asc()).all()])


@app.route("/api/report/period", methods=["GET"])
def get_period_report():
    start = str(request.args.get("from") or "").strip()
    end = str(request.args.get("to") or "").strip()
    if not _valid_range(start, end):
        return jsonify({"error": "טווח תאריכים לא תקין"}), 400
    return jsonify(_period_payload(start, end))


@app.route("/api/report/compare", methods=["GET"])
def compare_report():
    a_from = str(request.args.get("a_from") or "").strip()
    a_to = str(request.args.get("a_to") or "").strip()
    b_from = str(request.args.get("b_from") or "").strip()
    b_to = str(request.args.get("b_to") or "").strip()
    if not all((_valid_range(a_from, a_to), _valid_range(b_from, b_to))):
        return jsonify({"error": "טווח השוואה לא תקין"}), 400
    a = _period_payload(a_from, a_to)["summary"]
    b = _period_payload(b_from, b_to)["summary"]
    def pct(old, new):
        return None if old == 0 else round((new - old) / old * 100, 2)
    return jsonify({"a": a, "b": b, "change": {
        "grand_total": pct(a["grand_total"], b["grand_total"]),
        "regular_total": pct(a["regular_total"], b["regular_total"]),
        "extra_total": pct(a["extra_total"], b["extra_total"]),
        "days_count": pct(a["days_count"], b["days_count"]),
    }})


@app.route("/api/dashboard/summary", methods=["GET"])
def dashboard_summary():
    start = str(request.args.get("from") or "").strip()
    end = str(request.args.get("to") or "").strip()
    if not _valid_range(start, end):
        return jsonify({"error": "טווח תאריכים לא תקין"}), 400
    return jsonify(_period_payload(start, end))


@app.route("/api/dashboard/compare", methods=["GET"])
def dashboard_compare():
    a_from = str(request.args.get("a_from") or "").strip()
    a_to = str(request.args.get("a_to") or "").strip()
    b_from = str(request.args.get("b_from") or "").strip()
    b_to = str(request.args.get("b_to") or "").strip()
    if not all((_valid_range(a_from, a_to), _valid_range(b_from, b_to))):
        return jsonify({"error": "טווח השוואה לא תקין"}), 400
    a = _period_payload(a_from, a_to)["summary"]
    b = _period_payload(b_from, b_to)["summary"]
    def pct(old, new):
        return None if old == 0 else round((new - old) / old * 100, 2)
    return jsonify({"a": a, "b": b, "change": {
        "grand_total": pct(a["grand_total"], b["grand_total"]),
        "regular_total": pct(a["regular_total"], b["regular_total"]),
        "extra_total": pct(a["extra_total"], b["extra_total"]),
        "days_count": pct(a["days_count"], b["days_count"]),
    }})


@app.post("/api/periods/<string:year_month>/lock")
def lock_period(year_month):
    denied = _deny_write()
    if denied:
        return denied
    if not base.valid_month(year_month):
        return jsonify({"success": False, "error": "חודש לא תקין"}), 400
    row = PeriodLock.query.filter_by(year_month=year_month).first()
    if row is None:
        row = PeriodLock(year_month=year_month, locked=True,
                         locked_at=datetime.utcnow(), locked_by="מערכת")
        db.session.add(row)
    else:
        row.locked = True
        row.locked_at = datetime.utcnow()
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


# Expose the helper on the Flask object for legacy callers/tests.
app.price_for_date = _price_for_date

# Importing this module is the production composition step.  The existing
# wsgi_ui layer remains responsible for UI-only endpoints.
