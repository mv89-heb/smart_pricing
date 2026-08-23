"""Production entrypoint and performance layer for Smart Pricing."""
from sqlalchemy import text, func, case
from sqlalchemy.orm import selectinload

import app as app_module

app = app_module.app
db = app_module.db
Product = app_module.Product
PriceHistory = app_module.PriceHistory
DailyEntry = app_module.DailyEntry
BillingTemplate = app_module.BillingTemplate
PeriodLock = app_module.PeriodLock

class _HealthMiddleware:
    def __init__(self, wsgi_app): self.wsgi_app = wsgi_app
    def __call__(self, environ, start_response):
        if environ.get("PATH_INFO", "") == "/health":
            body = b'{"status":"ok"}'
            start_response("200 OK", [("Content-Type", "application/json"), ("Content-Length", str(len(body))), ("Cache-Control", "no-store")])
            return [body]
        return self.wsgi_app(environ, start_response)

app.wsgi_app = _HealthMiddleware(app.wsgi_app)

def _install_indexes():
    statements = (
        "CREATE INDEX IF NOT EXISTS ix_daily_entry_date_id ON daily_entry (date, id)",
        "CREATE INDEX IF NOT EXISTS ix_daily_entry_date_product_extra ON daily_entry (date, product_name, is_extra)",
        "CREATE INDEX IF NOT EXISTS ix_price_history_product_effective_id ON price_history (product_id, effective_from, id)",
        "CREATE INDEX IF NOT EXISTS ix_period_lock_month_locked ON period_lock (year_month, locked)",
        "CREATE INDEX IF NOT EXISTS ix_activity_log_timestamp ON activity_log (timestamp)",
        "CREATE INDEX IF NOT EXISTS ix_template_item_product_name ON billing_template_item (product_name)",
    )
    with app.app_context():
        for statement in statements:
            try:
                db.session.execute(text(statement)); db.session.commit()
            except Exception:
                db.session.rollback()

        # Repair legacy rows whose cached total_amount was left at zero/stale.
        # unit_price * quantity is the canonical value used by the application.
        try:
            db.session.execute(text("""
                UPDATE daily_entry
                SET total_amount = ROUND(COALESCE(quantity, 0) * COALESCE(unit_price, 0), 2)
                WHERE total_amount IS NULL
                   OR total_amount = 0
            """))
            db.session.commit()
        except Exception:
            db.session.rollback()

def _fast_price_for_date(product, iso_date):
    row = (PriceHistory.query.filter(PriceHistory.product_id == product.id, PriceHistory.effective_from.isnot(None), PriceHistory.effective_from <= iso_date).order_by(PriceHistory.effective_from.desc(), PriceHistory.id.desc()).first())
    return app_module.money(row.price if row is not None else product.price)

def _fast_product_details():
    today = app_module.today_iso(); products = Product.query.order_by(Product.name.asc()).all(); ids = [p.id for p in products]
    scheduled = (PriceHistory.query.filter(PriceHistory.product_id.in_(ids), PriceHistory.effective_from.isnot(None), PriceHistory.effective_from > today).order_by(PriceHistory.effective_from.asc(), PriceHistory.id.asc()).all()) if ids else []
    next_by_product = {}
    for row in scheduled: next_by_product.setdefault(row.product_id, row)
    return app_module.jsonify([{"id": p.id, "name": p.name, "price": float(p.price or 0), "tag": p.tag or "", "scheduled_price": ({"id": row.id, "price": float(row.price), "effective_from": row.effective_from, "changed_at": row.changed_at.isoformat(), "changed_by": row.changed_by, "scheduled": True} if (row := next_by_product.get(p.id)) else None)} for p in products])

def _fast_templates():
    templates = BillingTemplate.query.options(selectinload(BillingTemplate.items)).order_by(BillingTemplate.name.asc()).all()
    return app_module.jsonify({t.name: [{"product_name": i.product_name, "quantity": i.quantity, "is_extra": bool(i.is_extra)} for i in t.items] for t in templates})

def _entry_value_expr():
    """Return the canonical SQL amount expression for a DailyEntry."""
    return func.coalesce(DailyEntry.quantity, 0) * func.coalesce(DailyEntry.unit_price, 0)

def _fast_period_report():
    request = app_module.request; start=(request.args.get("from") or "").strip(); end=(request.args.get("to") or "").strip()
    if not app_module.valid_date(start) or not app_module.valid_date(end) or start>end: return app_module.jsonify({"error":"טווח תאריכים לא תקין"}),400
    entries=DailyEntry.query.filter(DailyEntry.date>=start,DailyEntry.date<=end).order_by(DailyEntry.date.asc(),DailyEntry.id.asc()).all()

    # Build the report from the same canonical calculation used by the dashboard,
    # rather than trusting an old cached total_amount value.
    regular = extra = 0.0
    products = {}
    days = {}
    payload_entries = []
    for e in entries:
        amount = app_module.money(e.quantity) * app_module.money(e.unit_price)
        amount = amount.quantize(app_module.Decimal("0.01")) if hasattr(app_module, "Decimal") else amount
        amount_f = float(amount)
        if e.is_extra: extra += amount_f
        else: regular += amount_f
        p = products.setdefault(e.product_name, {"quantity": 0.0, "total": 0.0})
        p["quantity"] += float(e.quantity or 0); p["total"] += amount_f
        d = days.setdefault(e.date, {"regular": 0.0, "extra": 0.0, "total": 0.0})
        d["extra" if e.is_extra else "regular"] += amount_f; d["total"] += amount_f
        payload_entries.append({"id": e.id, "date": e.date, "product_name": e.product_name, "quantity": e.quantity,
                                "is_extra": bool(e.is_extra), "unit_price": float(e.unit_price or 0),
                                "total_amount": amount_f, "note": e.note})
    grand = regular + extra
    payload = {"from": start, "to": end, "entries": payload_entries,
               "summary": {"regular_total": regular, "extra_total": extra, "grand_total": grand,
                           "days_count": len(days), "average_day": grand / len(days) if days else 0.0},
               "product_summary": products, "day_summary": days}
    months=sorted({e.date[:7] for e in entries})
    locked={row.year_month for row in PeriodLock.query.filter(PeriodLock.year_month.in_(months),PeriodLock.locked.is_(True)).all()} if months else set()
    payload["locked_months"]={m:m in locked for m in months}; payload["fully_locked"]=bool(months) and len(locked)==len(months)
    return app_module.jsonify(payload)

def _aggregate_period(start,end,include_products=True,include_days=True):
    base=DailyEntry.query.filter(DailyEntry.date>=start,DailyEntry.date<=end)
    amount_expr = _entry_value_expr()
    regular_expr=case((DailyEntry.is_extra.is_(False),amount_expr),else_=0); extra_expr=case((DailyEntry.is_extra.is_(True),amount_expr),else_=0)
    grand,regular,extra,days_count,quantity=base.with_entities(func.coalesce(func.sum(amount_expr),0),func.coalesce(func.sum(regular_expr),0),func.coalesce(func.sum(extra_expr),0),func.count(func.distinct(DailyEntry.date)),func.coalesce(func.sum(DailyEntry.quantity),0)).first()
    grand=float(grand or 0); regular=float(regular or 0); extra=float(extra or 0); days_count=int(days_count or 0)
    payload={"from":start,"to":end,"summary":{"grand_total":grand,"regular_total":regular,"extra_total":extra,"days_count":days_count,"average_day":grand/days_count if days_count else 0.0,"quantity_total":float(quantity or 0)}}
    if include_days:
        rows=base.with_entities(DailyEntry.date,func.coalesce(func.sum(case((DailyEntry.is_extra.is_(False),amount_expr),else_=0)),0),func.coalesce(func.sum(case((DailyEntry.is_extra.is_(True),amount_expr),else_=0)),0),func.coalesce(func.sum(amount_expr),0)).group_by(DailyEntry.date).order_by(DailyEntry.date.asc()).all()
        payload["day_summary"]={d:{"regular":float(r or 0),"extra":float(x or 0),"total":float(t or 0)} for d,r,x,t in rows}
    if include_products:
        rows=base.with_entities(DailyEntry.product_name,func.coalesce(func.sum(DailyEntry.quantity),0),func.coalesce(func.sum(amount_expr),0)).group_by(DailyEntry.product_name).order_by(func.sum(amount_expr).desc()).all()
        payload["product_summary"]={n:{"quantity":float(q or 0),"total":float(t or 0)} for n,q,t in rows}
    months=sorted({m for m, in base.with_entities(func.substr(DailyEntry.date,1,7)).distinct().all()})
    locked={row.year_month for row in PeriodLock.query.filter(PeriodLock.year_month.in_(months),PeriodLock.locked.is_(True)).all()} if months else set()
    payload["locked_months"]={m:m in locked for m in months}; payload["fully_locked"]=bool(months) and len(locked)==len(months)
    return payload

def _dashboard_summary():
    request=app_module.request; start=(request.args.get("from") or "").strip(); end=(request.args.get("to") or "").strip()
    if not app_module.valid_date(start) or not app_module.valid_date(end) or start>end:return app_module.jsonify({"error":"טווח תאריכים לא תקין"}),400
    return app_module.jsonify(_aggregate_period(start,end))

def _dashboard_compare():
    request=app_module.request; ranges=[]
    for prefix in ("a","b"):
        start=(request.args.get(prefix+"_from") or "").strip(); end=(request.args.get(prefix+"_to") or "").strip()
        if not app_module.valid_date(start) or not app_module.valid_date(end) or start>end:return app_module.jsonify({"error":"טווח השוואה לא תקין"}),400
        ranges.append((start,end))
    a=_aggregate_period(*ranges[0],include_products=False,include_days=False)["summary"]; b=_aggregate_period(*ranges[1],include_products=False,include_days=False)["summary"]
    def pct(old,new): return None if old==0 else round((new-old)/old*100,2)
    return app_module.jsonify({"a":a,"b":b,"change":{"grand_total":pct(a["grand_total"],b["grand_total"]),"regular_total":pct(a["regular_total"],b["regular_total"]),"extra_total":pct(a["extra_total"],b["extra_total"]),"days_count":pct(a["days_count"],b["days_count"])}})

app_module.price_for_date=_fast_price_for_date
app.view_functions["get_product_details"]=_fast_product_details
app.view_functions["get_templates"]=_fast_templates
app.view_functions["get_period_report"]=_fast_period_report
app.add_url_rule("/api/dashboard/summary","dashboard_summary_fast",_dashboard_summary,methods=["GET"])
app.add_url_rule("/api/dashboard/compare","dashboard_compare_fast",_dashboard_compare,methods=["GET"])
_install_indexes()
