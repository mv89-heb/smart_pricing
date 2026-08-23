from datetime import datetime
from flask import render_template, request, jsonify


def _json_error(message, status=400):
    return jsonify({'error': message}), status


def register_period_report(app, db, DailyEntry, Product=None):
    """Register the period-report UI/API without changing existing entry routes."""

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
            # DailyEntry.date is a String in the existing schema. ISO YYYY-MM-DD
            # values sort chronologically, so compare normalized strings.
            entries = (
                DailyEntry.query
                .filter(DailyEntry.date >= start_date, DailyEntry.date <= end_date)
                .order_by(DailyEntry.date.desc(), DailyEntry.product_name.asc(), DailyEntry.id.asc())
                .all()
            )
            rows = []
            grand_total = regular_total = extra_total = total_quantity = 0.0
            for entry in entries:
                unit_price = float(entry.unit_price or 0)
                quantity = float(entry.quantity or 0)
                line_total = unit_price * quantity
                grand_total += line_total
                total_quantity += quantity
                if entry.is_extra:
                    extra_total += line_total
                else:
                    regular_total += line_total
                rows.append({
                    'id': entry.id,
                    'date': entry.date.isoformat() if hasattr(entry.date, 'isoformat') else str(entry.date),
                    'product_name': entry.product_name,
                    'quantity': quantity,
                    'is_extra': bool(entry.is_extra),
                    'unit_price': unit_price,
                    'total': line_total,
                })
            return jsonify({
                'start_date': start_date,
                'end_date': end_date,
                'rows': rows,
                'summary': {
                    'entries': len(rows),
                    'quantity': total_quantity,
                    'regular_total': regular_total,
                    'extra_total': extra_total,
                    'grand_total': grand_total,
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
            return jsonify({
                'products': [{'name': p.name, 'price': float(p.price or 0), 'updated_at': None} for p in products],
                'count': len(products),
            })
        except Exception:
            app.logger.exception('Period report product query failed')
            return _json_error('שגיאה בטעינת המחירון. הנתונים לא שונו.', 500)

    @app.get('/period-report')
    def period_report_page():
        return render_template('period_report.html')

    @app.get('/daily')
    def daily_entry_page():
        return render_template('index.html')

    existing_index = app.view_functions.get('index')
    if existing_index is not None:
        app.view_functions['legacy_daily_index'] = existing_index
    app.view_functions['index'] = period_report_page
