from datetime import datetime, date
from difflib import SequenceMatcher
from flask import render_template, request, jsonify
from sqlalchemy import text


def _json_error(message, status=400):
    return jsonify({'error': message}), status


def _normalize(value):
    return ' '.join((value or '').split()).casefold()


def _canonical_product(raw_name, products):
    raw = (raw_name or '').strip()
    if not raw or not products:
        return raw, None
    normalized = _normalize(raw)
    exact = [p for p in products if _normalize(p.name) == normalized]
    if len(exact) == 1:
        return exact[0].name, exact[0]
    candidates = []
    for p in products:
        candidate = _normalize(p.name)
        if not candidate:
            continue
        ratio = SequenceMatcher(None, normalized, candidate).ratio()
        gap = abs(len(normalized) - len(candidate))
        if ratio >= 0.80 and gap <= 3:
            candidates.append((ratio, p))
    candidates.sort(key=lambda x: x[0], reverse=True)
    if candidates:
        best_ratio, best = candidates[0]
        second_ratio = candidates[1][0] if len(candidates) > 1 else 0
        if best_ratio >= 0.86 and (len(candidates) == 1 or best_ratio - second_ratio >= 0.06):
            return best.name, best
    return raw, None


def _vat_settings(db):
    try:
        result = db.session.execute(text('''
            SELECT product_id, category, vat_rate
            FROM product_vat_settings
        ''')).mappings().all()
        settings = {}
        for row in result:
            category = (row['category'] or 'כללי').strip()
            rate = 0.0 if category == 'ירקות' else float(row['vat_rate'] or 0)
            settings[int(row['product_id'])] = {'category': category, 'vat_rate': rate}
        return settings
    except Exception:
        db.session.rollback()
        return {}


def _vat_for_product(settings, product):
    if product is not None and product.id in settings:
        return settings[product.id]
    return {'category': 'כללי', 'vat_rate': 18.0}


def _render_period_report_page():
    # The page owns its complete markup/scripts. Do not inject a second renderer
    # after the template: doing so caused duplicate headers/renderers and made
    # the visible table differ from the API data.
    return render_template('period_report.html')


def register_period_report(app, db, DailyEntry, Product=None, ActivityLog=None):
    @app.get('/api/report/range')
    def get_period_report():
        start_date = (request.args.get('start_date') or '').strip()
        end_date = (request.args.get('end_date') or '').strip()
        if not start_date or not end_date:
            return _json_error('יש לבחור תאריך התחלה ותאריך סיום')
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            return _json_error('טווח תאריכים לא תקין')
        if start > end:
            return _json_error('תאריך ההתחלה חייב להיות לפני תאריך הסיום')
        try:
            products = Product.query.order_by(Product.name.asc()).all() if Product is not None else []
            vat_settings = _vat_settings(db)
            rows = []
            net_total = regular_net = extra_net = qty = vat_total = gross_total = 0.0
            entries = (DailyEntry.query.filter(DailyEntry.date >= start_date, DailyEntry.date <= end_date)
                       .order_by(DailyEntry.date.desc(), DailyEntry.product_name.asc(), DailyEntry.id.asc()).all())
            existing_names = set()
            for e in entries:
                display_name, product = _canonical_product(e.product_name, products)
                price = float(e.unit_price or 0)
                amount = float(e.quantity or 0)
                total = price * amount
                vat = _vat_for_product(vat_settings, product)
                vat_amount = total * vat['vat_rate'] / 100.0
                total_with_vat = total + vat_amount
                net_total += total
                vat_total += vat_amount
                gross_total += total_with_vat
                qty += amount
                if e.is_extra:
                    extra_net += total
                else:
                    regular_net += total
                existing_names.add(_normalize(display_name))
                rows.append({
                    'id': e.id,
                    'product_id': getattr(product, 'id', None),
                    'date': str(e.date)[:10],
                    'product_name': display_name,
                    'quantity': amount,
                    'is_extra': bool(e.is_extra),
                    'unit_price': price,
                    'total': total,
                    'category': vat['category'],
                    'vat_rate': vat['vat_rate'],
                    'vat_amount': vat_amount,
                    'total_with_vat': total_with_vat,
                })

            legacy_added = {}
            if ActivityLog is not None:
                for log in ActivityLog.query.filter(ActivityLog.action == 'NEW_PRODUCT').order_by(ActivityLog.timestamp.asc()).all():
                    details = log.details or ''
                    prefix = 'מוצר חדש: '
                    if details.startswith(prefix):
                        name = details[len(prefix):].split(', מחיר:', 1)[0].strip()
                        if name:
                            legacy_added.setdefault(_normalize(name), log.timestamp)

            today = date.today()
            zero_rows = []
            for product in products:
                if _normalize(product.name) in existing_names:
                    continue
                created_at = getattr(product, 'created_at', None) or legacy_added.get(_normalize(product.name))
                if created_at:
                    created_date = created_at.date() if hasattr(created_at, 'date') else created_at
                    if not (start <= created_date <= end):
                        continue
                    display_date = created_date
                else:
                    if end < today:
                        continue
                    display_date = end
                vat = _vat_for_product(vat_settings, product)
                price = float(product.price or 0)
                zero_rows.append({
                    'id': None,
                    'product_id': product.id,
                    'date': display_date.isoformat(),
                    'product_name': product.name,
                    'quantity': 0.0,
                    'is_extra': False,
                    'unit_price': price,
                    'total': 0.0,
                    'category': vat['category'],
                    'vat_rate': vat['vat_rate'],
                    'vat_amount': 0.0,
                    'total_with_vat': 0.0,
                })
            rows.extend(zero_rows)
            rows.sort(key=lambda r: (r['date'], r['product_name']), reverse=True)
            return jsonify({
                'start_date': start_date,
                'end_date': end_date,
                'rows': rows,
                'summary': {
                    'entries': len(entries),
                    'quantity': qty,
                    'regular_total': regular_net,
                    'extra_total': extra_net,
                    'grand_total': net_total,
                    'net_total': net_total,
                    'vat_total': vat_total,
                    'gross_total': gross_total,
                    'grand_total_with_vat': gross_total,
                    'catalog_products_added': len(zero_rows),
                },
            })
        except Exception:
            app.logger.exception('Period report query failed')
            return _json_error('שגיאה בטעינת הדוח. הנתונים לא שונו.', 500)

    @app.get('/api/report/products')
    def get_report_products():
        if Product is None:
            return jsonify({'products': [], 'count': 0})
        try:
            products = Product.query.order_by(Product.name.asc()).all()
            added = {}
            if ActivityLog is not None:
                for log in ActivityLog.query.filter(ActivityLog.action == 'NEW_PRODUCT').order_by(ActivityLog.timestamp.asc()).all():
                    details = log.details or ''
                    prefix = 'מוצר חדש: '
                    if details.startswith(prefix):
                        name = details[len(prefix):].split(', מחיר:', 1)[0].strip()
                        added.setdefault(name, log.timestamp)
            def added_at(p):
                return p.created_at.isoformat() if getattr(p, 'created_at', None) else (added.get(p.name).isoformat() if added.get(p.name) else None)
            return jsonify({'products': [{'id': p.id, 'name': p.name, 'price': float(p.price or 0), 'added_at': added_at(p)} for p in products], 'count': len(products)})
        except Exception:
            app.logger.exception('Period report product query failed')
            return _json_error('שגיאה בטעינת המחירון. הנתונים לא שונו.', 500)

    @app.get('/products/new')
    def product_add_page():
        return render_template('product_add.html')

    @app.get('/dashboard')
    def dashboard_page():
        return render_template('dashboard.html')

    @app.get('/settings')
    def settings_page():
        return render_template('settings.html')

    @app.get('/period-report')
    def period_report_page_alias():
        return _render_period_report_page()

    @app.get('/')
    def period_report_page():
        return _render_period_report_page()
