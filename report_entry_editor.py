from flask import jsonify, request
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError


def register_report_entry_editor(app, db, DailyEntry, Product, is_viewer):
    """Edit a period-report row while keeping the catalog canonical."""

    def product_for_entry(entry):
        product_id = db.session.execute(
            text('SELECT product_id FROM daily_entry WHERE id = :id'),
            {'id': entry.id},
        ).scalar()
        product = db.session.get(Product, product_id) if product_id else None
        if product is None:
            normalized = (entry.product_name or '').strip().casefold()
            product = next(
                (p for p in Product.query.all() if (p.name or '').strip().casefold() == normalized),
                None,
            )
        return product

    @app.put('/api/report/entries/<int:entry_id>')
    def edit_report_entry(entry_id):
        if is_viewer():
            return jsonify({'success': False, 'error': 'אין הרשאות עדכון'}), 403
        data = request.json or {}
        try:
            entry = DailyEntry.query.get(entry_id)
            if not entry:
                return jsonify({'success': False, 'error': 'החיוב לא נמצא'}), 404

            product = product_for_entry(entry)
            if product is None:
                return jsonify({'success': False, 'error': 'המוצר המקושר לא נמצא במחירון'}), 409

            quantity = float(data.get('quantity', entry.quantity))
            if quantity <= 0:
                return jsonify({'success': False, 'error': 'הכמות חייבת להיות גדולה מאפס'}), 400

            new_name = (data.get('product_name', product.name) or '').strip()
            if not new_name:
                return jsonify({'success': False, 'error': 'שם מוצר לא יכול להיות ריק'}), 400

            unit_price = float(data.get('unit_price', product.price))
            if unit_price < 0:
                return jsonify({'success': False, 'error': 'מחיר היחידה לא יכול להיות שלילי'}), 400

            duplicate = Product.query.filter(
                Product.id != product.id,
                Product.name == new_name,
            ).first()
            if duplicate:
                return jsonify({'success': False, 'error': f'מוצר בשם "{new_name}" כבר קיים'}), 400

            old_name = product.name
            old_price = float(product.price or 0)
            product.name = new_name
            product.price = unit_price

            db.session.execute(
                text(
                    'UPDATE daily_entry '
                    'SET product_id = :pid, product_name = :name, unit_price = :price '
                    'WHERE product_id = :pid'
                ),
                {'pid': product.id, 'name': new_name, 'price': unit_price},
            )
            db.session.execute(
                text(
                    'UPDATE daily_entry SET product_id = :pid, product_name = :name, unit_price = :price '
                    'WHERE product_id IS NULL AND LOWER(TRIM(product_name)) = LOWER(TRIM(:old_name))'
                ),
                {'pid': product.id, 'name': new_name, 'price': unit_price, 'old_name': old_name},
            )

            entry.quantity = quantity
            if 'is_extra' in data:
                entry.is_extra = bool(data['is_extra'])

            db.session.commit()
            return jsonify({
                'success': True,
                'entry': {
                    'id': entry.id,
                    'product_name': new_name,
                    'quantity': float(entry.quantity),
                    'is_extra': bool(entry.is_extra),
                    'unit_price': unit_price,
                    'total': float(entry.quantity) * unit_price,
                },
                'product': {'id': product.id, 'name': new_name, 'price': unit_price},
                'previous': {'name': old_name, 'price': old_price},
            })
        except (TypeError, ValueError):
            db.session.rollback()
            return jsonify({'success': False, 'error': 'נתונים לא תקינים'}), 400
        except SQLAlchemyError as exc:
            db.session.rollback()
            app.logger.exception('Report entry edit failed')
            return jsonify({'success': False, 'error': str(exc)}), 500
