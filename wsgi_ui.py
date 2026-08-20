"""Production entrypoint with UI helpers and API-free browser price discovery."""
import os
from datetime import datetime
import app as base
from flask import jsonify, request, session
from werkzeug.security import generate_password_hash
from sqlalchemy.exc import SQLAlchemyError
from services.browser_price_search import search_products

app = base.app
User = base.User
admin_access = base.admin_access
log_activity = base.log_activity

try:
    import wsgi as performance
except Exception:
    performance = None

@app.get("/api/system/health")
def system_health():
    """Authenticated, low-detail readiness check used by the UI and deploy debugging."""
    if not session.get("logged_in"):
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    required = ["product", "daily_entry", "price_history", "period_lock", "activity_log", "user", "billing_template", "billing_template_item"]
    try:
        inspector = base.db.inspect(base.db.engine)
        existing = set(inspector.get_table_names())
        missing = [table for table in required if table not in existing]
        if missing:
            return jsonify({"ok": False, "error": "מסד הנתונים אינו מעודכן", "database": base.db.engine.name, "tables_checked": len(required), "missing": missing}), 503
        base.db.session.execute(base.text("SELECT 1"))
        return jsonify({"ok": True, "database": base.db.engine.name, "tables_checked": len(required), "missing": []})
    except Exception:
        return jsonify({"ok": False, "error": "מסד הנתונים אינו זמין", "database": base.db.engine.name, "tables_checked": len(required)}), 503

@app.post("/api/users/<int:user_id>/reset-password")
def reset_user_password(user_id):
    denied = admin_access()
    if denied: return denied
    data = request.get_json(silent=True) or {}
    password = data.get("password") or ""
    if not isinstance(password, str) or len(password) < 8:
        return jsonify({"success": False, "error": "סיסמה חייבת להכיל לפחות 8 תווים"}), 400
    if len(password) > 128:
        return jsonify({"success": False, "error": "סיסמה ארוכה מדי"}), 400
    user = User.query.get(user_id)
    if not user: return jsonify({"success": False, "error": "המשתמש לא נמצא"}), 404
    try:
        user.password = generate_password_hash(password)
        base.db.session.commit()
        log_activity("USER_PASSWORD_RESET", f"איפוס סיסמה למשתמש: {user.username}")
        return jsonify({"success": True, "username": user.username})
    except SQLAlchemyError:
        base.db.session.rollback()
        return jsonify({"success": False, "error": "שגיאת שרת"}), 500

@app.post("/api/browser-price-sync/search")
def browser_price_sync_search():
    denied = admin_access()
    if denied: return denied
    data = request.get_json(silent=True) or {}
    products = data.get("products")
    if not isinstance(products, list) or not products:
        return jsonify({"success": False, "error": "לא נבחרו מוצרים"}), 400
    if len(products) > 100:
        return jsonify({"success": False, "error": "ניתן לבדוק עד 100 מוצרים בפעולה אחת"}), 400
    try:
        results = search_products(products)
        return jsonify({"success": True, "results": results})
    except Exception as exc:
        return jsonify({"success": False, "error": f"חיפוש המחירים נכשל: {str(exc)[:300]}"}), 500

@app.post("/api/browser-price-sync/apply")
def browser_price_sync_apply():
    denied = admin_access()
    if denied: return denied
    data = request.get_json(silent=True) or {}
    updates, effective_from = data.get("updates"), data.get("effective_from")
    if not isinstance(updates, list) or not updates: return jsonify({"success": False, "error": "אין עדכונים"}), 400
    if not isinstance(effective_from, str) or len(effective_from) != 10:
        return jsonify({"success": False, "error": "תאריך תוקף לא תקין"}), 400
    try: datetime.strptime(effective_from, "%Y-%m-%d")
    except ValueError: return jsonify({"success": False, "error": "תאריך תוקף לא תקין"}), 400
    applied=[]
    try:
        for item in updates[:100]:
            name=str(item.get("name") or "").strip()[:100]
            try: price=float(item.get("price"))
            except (TypeError,ValueError): continue
            if not name or price<=0: continue
            product=base.Product.query.filter_by(name=name).first()
            if not product: continue
            value=base.money(price)
            existing = base.PriceHistory.query.filter_by(product_id=product.id, effective_from=effective_from).order_by(base.PriceHistory.id.desc()).first()
            if existing:
                existing.price=value
                existing.changed_at=datetime.utcnow()
                existing.changed_by=session.get("username","browser-search")
            else:
                base.db.session.add(base.PriceHistory(product_id=product.id,price=value,effective_from=effective_from,changed_by=session.get("username","browser-search")))
            if effective_from <= base.today_iso(): product.price=value
            applied.append({"name":name,"price":float(value),"effective_from":effective_from})
        base.db.session.commit()
    except Exception:
        base.db.session.rollback()
        return jsonify({"success":False,"error":"שמירת העדכונים נכשלה"}),500
    log_activity("BROWSER_PRICE_SYNC_APPLIED", f"עודכנו {len(applied)} מוצרים באמצעות חיפוש Google בדפדפן")
    return jsonify({"success":True,"applied":applied})

def _inject_period_report(response):
    if "text/html" not in response.headers.get("Content-Type", ""): return response
    try:
        body=response.get_data(as_text=True); marker="</body>"
        scripts = [
            '<script src="/static/period-report-loader.js?v=4" defer></script>',
            '<script src="/static/password-reset.js?v=4" defer></script>',
            '<script src="/static/global-filters.js?v=4" defer></script>',
            '<script src="/static/browser-price-sync.js?v=5" defer></script>',
            '<script src="/static/ui-stability.js?v=3" defer></script>',
            '<script src="/static/app-shell-stability.js?v=2" defer></script>',
            '<script src="/static/report-sort.js?v=1" defer></script>',
            '<script src="/static/system-health.js?v=1" defer></script>',
        ]
        for script in scripts:
            if script not in body and marker in body: body=body.replace(marker,script+marker,1)
        response.set_data(body)
        response.headers["Cache-Control"]="no-store, max-age=0"
    except Exception: pass
    return response

app.after_request(_inject_period_report)
