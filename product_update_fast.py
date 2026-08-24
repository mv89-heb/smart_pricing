"""Fast, single-transaction product update endpoint.

The legacy endpoint calls log_activity(), which commits the transaction every
 time it is called. On a remote Postgres database that turns one product edit
into multiple network round trips. This module replaces only that endpoint
with an equivalent implementation that writes activity rows into the same
transaction and commits once.
"""

from flask import jsonify, request, session
from sqlalchemy.exc import SQLAlchemyError


def register_fast_product_update(app, db, Product, DailyEntry, ActivityLog, is_viewer):
    def fast_update_product(name):
        if is_viewer():
            return jsonify({"success": False, "error": "אין הרשאות עדכון"}), 403

        data = request.json or {}
        try:
            product = Product.query.filter_by(name=name).first()
            if not product:
                return jsonify({"success": False, "error": "המוצר לא נמצא"}), 404

            new_name = (data.get('name') or name).strip()
            price = data.get('price', product.price)
            try:
                price = float(price)
            except (TypeError, ValueError):
                return jsonify({"success": False, "error": "מחיר לא תקין"}), 400

            if price < 0:
                return jsonify({"success": False, "error": "המחיר לא יכול להיות שלילי"}), 400
            if not new_name:
                return jsonify({"success": False, "error": "שם מוצר לא יכול להיות ריק"}), 400

            if new_name != name and Product.query.filter_by(name=new_name).first():
                return jsonify({"success": False, "error": f'מוצר בשם "{new_name}" כבר קיים'}), 400

            old_price = product.price
            old_name = product.name
            name_changed = new_name != old_name
            price_changed = old_price != price

            product.price = price
            product.name = new_name

            if name_changed:
                DailyEntry.query.filter_by(product_name=old_name).update(
                    {DailyEntry.product_name: new_name}, synchronize_session=False
                )

            username = session.get('username', 'מערכת')
            if name_changed:
                db.session.add(ActivityLog(
                    action='RENAME_PRODUCT',
                    details=f"שינוי שם מוצר: {old_name} -> {new_name}",
                    username=username,
                ))
            if price_changed:
                db.session.add(ActivityLog(
                    action='UPDATE_PRICE',
                    details=f"מוצר: {new_name}, {old_price} -> {price}",
                    username=username,
                ))

            db.session.commit()
            return jsonify({"success": True})
        except SQLAlchemyError as e:
            db.session.rollback()
            return jsonify({"success": False, "error": str(e)}), 500
        except Exception as e:
            db.session.rollback()
            return jsonify({"success": False, "error": str(e)}), 500

    # Replace only the existing endpoint implementation; keep its URL/rules.
    app.view_functions['update_product'] = fast_update_product
