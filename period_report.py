from datetime import datetime
from flask import render_template, request, jsonify


def register_period_report(app, db, DailyEntry):
    """Register the period-report UI/API without changing existing entry routes."""

    @app.get('/api/report/range')
    def get_period_report():
        start_date = (request.args.get('start_date') or '').strip()
        end_date = (request.args.get('end_date') or '').strip()
        if not start_date or not end_date:
            return jsonify({'error': 'יש לבחור תאריך התחלה ותאריך סיום'}), 400
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': 'טווח תאריכים לא תקין'}), 400
        if start > end:
            return jsonify({'error': 'תאריך ההתחלה חייב להיות לפני תאריך הסיום'}), 400

        entries = (
            DailyEntry.query
            .filter(DailyEntry.date >= start_date, DailyEntry.date <= end_date)
            .order_by(DailyEntry.date.desc(), DailyEntry.product_name.asc(), DailyEntry.id.asc())
            .all()
        )

        rows = []
        grand_total = 0.0
        regular_total = 0.0
        extra_total = 0.0
        total_quantity = 0.0
        for entry in entries:
            unit_price = entry.unit_price if entry.unit_price is not None else 0.0
            line_total = float(unit_price) * float(entry.quantity)
            grand_total += line_total
            total_quantity += float(entry.quantity)
            if entry.is_extra:
                extra_total += line_total
            else:
                regular_total += line_total
            rows.append({
                'id': entry.id,
                'date': entry.date,
                'product_name': entry.product_name,
                'quantity': entry.quantity,
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

    @app.get('/period-report')
    def period_report_page():
        return render_template('period_report.html')

    # Keep the existing full daily-entry UI available without changing its code.
    @app.get('/daily')
    def daily_entry_page():
        return render_template('index.html')

    # The existing root view remains the daily UI in app.py; wsgi swaps only
    # the view function so the new period report becomes the landing screen.
    existing_index = app.view_functions.get('index')
    if existing_index is not None:
        app.view_functions['legacy_daily_index'] = existing_index

    app.view_functions['index'] = period_report_page
