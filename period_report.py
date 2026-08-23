from datetime import datetime
from flask import render_template, request, jsonify


def _json_error(message, status=400):
    return jsonify({'error': message}), status


def register_period_report(app, db, DailyEntry, Product=None, ActivityLog=None):
    @app.get('/api/report/range')
    def get_period_report():
        start_date=(request.args.get('start_date') or '').strip(); end_date=(request.args.get('end_date') or '').strip()
        if not start_date or not end_date: return _json_error('יש לבחור תאריך התחלה ותאריך סיום')
        try:
            start=datetime.strptime(start_date,'%Y-%m-%d').date(); end=datetime.strptime(end_date,'%Y-%m-%d').date()
        except ValueError: return _json_error('טווח תאריכים לא תקין')
        if start>end: return _json_error('תאריך ההתחלה חייב להיות לפני תאריך הסיום')
        try:
            entries=(DailyEntry.query.filter(DailyEntry.date>=start_date,DailyEntry.date<=end_date).order_by(DailyEntry.date.desc(),DailyEntry.product_name.asc(),DailyEntry.id.asc()).all())
            rows=[]; grand=regular=extra=qty=0.0
            for e in entries:
                price=float(e.unit_price or 0); amount=float(e.quantity or 0); total=price*amount; grand+=total; qty+=amount
                if e.is_extra: extra+=total
                else: regular+=total
                rows.append({'id':e.id,'date':e.date.isoformat() if hasattr(e.date,'isoformat') else str(e.date),'product_name':e.product_name,'quantity':amount,'is_extra':bool(e.is_extra),'unit_price':price,'total':total})
            return jsonify({'start_date':start_date,'end_date':end_date,'rows':rows,'summary':{'entries':len(rows),'quantity':qty,'regular_total':regular,'extra_total':extra,'grand_total':grand}})
        except Exception:
            app.logger.exception('Period report query failed'); return _json_error('שגיאה בטעינת הדוח. הנתונים לא שונו.',500)

    @app.get('/api/report/products')
    def get_report_products():
        if Product is None: return jsonify({'products':[],'count':0})
        try:
            products=Product.query.order_by(Product.name.asc()).all()
            # לגבי מוצרים שנוצרו לפני שהתווסף created_at (עמודה חדשה) - עדיין משחזרים
            # תאריך היסטורי מיומן הפעילות, כדי לא לאבד מידע קיים.
            needs_legacy_lookup = any(getattr(p, 'created_at', None) is None for p in products)
            added={}
            if needs_legacy_lookup and ActivityLog is not None:
                for log in ActivityLog.query.filter(ActivityLog.action=='NEW_PRODUCT').order_by(ActivityLog.timestamp.asc()).all():
                    prefix='מוצר חדש: '
                    if log.details.startswith(prefix):
                        name=log.details[len(prefix):].split(', מחיר:',1)[0].strip(); added.setdefault(name,log.timestamp)
            def added_at(p):
                if getattr(p, 'created_at', None):
                    return p.created_at.isoformat()
                legacy = added.get(p.name)
                return legacy.isoformat() if legacy else None
            return jsonify({'products':[{'id':p.id,'name':p.name,'price':float(p.price or 0),'added_at':added_at(p)} for p in products],'count':len(products)})
        except Exception:
            app.logger.exception('Period report product query failed'); return _json_error('שגיאה בטעינת המחירון. הנתונים לא שונו.',500)

    @app.get('/products/new')
    def product_add_page(): return render_template('product_add.html')

    @app.get('/dashboard')
    def dashboard_page(): return render_template('dashboard.html')

    @app.get('/settings')
    def settings_page(): return render_template('settings.html')

    @app.get('/period-report')
    def period_report_page_alias(): return render_template('period_report.html')

    # דוח התקופה משמש כדף הבית של המערכת (כפי שהתפריט הצדדי וכל שאר המסכים מניחים).
    @app.get('/')
    def period_report_page(): return render_template('period_report.html')
