import os
from flask import jsonify, request
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

DEFAULT_VAT_RATE = float(os.environ.get('DEFAULT_VAT_RATE', '18'))
# Business rule requested: vegetables are VAT-exempt. Other categories use the default rate.
ZERO_VAT_CATEGORIES = {'ירקות'}
CATEGORY_OPTIONS = [
    'כללי',
    'ירקות',
    'פירות',
    'ממרחים וממתיקים',
    'דגנים',
    'שמנים',
    'חד-פעמי',
    'מוצרי מזון',
    'אחר',
]

# Seed only the products currently represented in the report/catalog.
# Existing user choices are preserved by ON CONFLICT DO NOTHING.
CURRENT_PRODUCT_CATEGORIES = {
    'אבוקדו': 'פירות',
    'אבטיח': 'פירות',
    'דבש': 'ממרחים וממתיקים',
    'כוסות שבת': 'חד-פעמי',
    'מגש פירות גדול': 'פירות',
    'מייפל': 'ממרחים וממתיקים',
    'מלון': 'פירות',
    'סילאן': 'ממרחים וממתיקים',
    'שיבולת שועל': 'דגנים',
    'שמן זית': 'שמנים',
    'תפוח': 'פירות',
    'בננה': 'פירות',
    'בננות': 'פירות',
}


def _ensure_table(db):
    db.session.execute(text('''
        CREATE TABLE IF NOT EXISTS product_vat_settings (
            product_id INTEGER PRIMARY KEY,
            category VARCHAR(100) NOT NULL DEFAULT 'כללי',
            vat_rate DOUBLE PRECISION NOT NULL DEFAULT 18,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    '''))
    db.session.commit()


def _seed_existing_products(db, Product):
    """Assign categories to the known current catalog without overwriting manual choices."""
    products = Product.query.all()
    changed = False
    for product in products:
        category = CURRENT_PRODUCT_CATEGORIES.get((product.name or '').strip(), 'כללי')
        result = db.session.execute(text('''
            INSERT INTO product_vat_settings(product_id, category, vat_rate, updated_at)
            VALUES (:id, :category, :rate, CURRENT_TIMESTAMP)
            ON CONFLICT(product_id) DO NOTHING
        '''), {
            'id': product.id,
            'category': category,
            'rate': 0.0 if category in ZERO_VAT_CATEGORIES else DEFAULT_VAT_RATE,
        })
        if result.rowcount:
            changed = True
    if changed:
        db.session.commit()


def _row(db, product_id):
    return db.session.execute(text('''
        SELECT product_id, category, vat_rate
        FROM product_vat_settings
        WHERE product_id = :product_id
    '''), {'product_id': product_id}).mappings().first()


def _effective(category, supplied_rate=None):
    if category in ZERO_VAT_CATEGORIES:
        return 0.0
    if supplied_rate is None:
        return DEFAULT_VAT_RATE
    rate = float(supplied_rate)
    if rate < 0 or rate > 100:
        raise ValueError('שיעור מע״מ חייב להיות בין 0 ל-100')
    return rate


def register_vat_features(app, db, Product, is_viewer):
    with app.app_context():
        _ensure_table(db)
        _seed_existing_products(db, Product)

    @app.route('/api/vat/config', methods=['GET'])
    def vat_config():
        return jsonify({
            'default_rate': DEFAULT_VAT_RATE,
            'categories': CATEGORY_OPTIONS,
            'zero_vat_categories': sorted(ZERO_VAT_CATEGORIES),
            'price_basis': 'before_vat',
        })

    @app.route('/api/vat/products', methods=['GET'])
    def vat_products():
        try:
            products = Product.query.order_by(Product.name.asc()).all()
            rows = db.session.execute(text('''
                SELECT product_id, category, vat_rate
                FROM product_vat_settings
            ''')).mappings().all()
            settings = {int(r['product_id']): {'category': r['category'], 'vat_rate': float(r['vat_rate'])} for r in rows}
            result = []
            for p in products:
                s = settings.get(p.id, {'category': 'כללי', 'vat_rate': DEFAULT_VAT_RATE})
                if s['category'] in ZERO_VAT_CATEGORIES:
                    s['vat_rate'] = 0.0
                result.append({
                    'id': p.id,
                    'name': p.name,
                    'price': float(p.price or 0),
                    'category': s['category'],
                    'vat_rate': s['vat_rate'],
                })
            return jsonify({'products': result})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/vat/products/<int:product_id>', methods=['PUT'])
    def update_vat_product(product_id):
        if is_viewer():
            return jsonify({'success': False, 'error': 'אין הרשאות עדכון'}), 403
        data = request.json or {}
        category = (data.get('category') or 'כללי').strip()
        if not category:
            category = 'כללי'
        if category not in CATEGORY_OPTIONS:
            return jsonify({'success': False, 'error': 'קטגוריה לא תקינה'}), 400
        try:
            rate = _effective(category, data.get('vat_rate'))
            if not Product.query.get(product_id):
                return jsonify({'success': False, 'error': 'המוצר לא נמצא'}), 404
            db.session.execute(text('''
                INSERT INTO product_vat_settings(product_id, category, vat_rate, updated_at)
                VALUES (:id, :category, :rate, CURRENT_TIMESTAMP)
                ON CONFLICT(product_id) DO UPDATE SET
                    category = EXCLUDED.category,
                    vat_rate = EXCLUDED.vat_rate,
                    updated_at = CURRENT_TIMESTAMP
            '''), {'id': product_id, 'category': category, 'rate': rate})
            db.session.commit()
            return jsonify({'success': True, 'product_id': product_id, 'category': category, 'vat_rate': rate})
        except (TypeError, ValueError):
            db.session.rollback()
            return jsonify({'success': False, 'error': 'שיעור מע״מ לא תקין'}), 400
        except SQLAlchemyError as e:
            db.session.rollback()
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/vat/products/by-name/<path:name>', methods=['GET'])
    def vat_product_by_name(name):
        product = Product.query.filter_by(name=name).first()
        if not product:
            return jsonify({'error': 'המוצר לא נמצא'}), 404
        row = _row(db, product.id)
        category = row['category'] if row else 'כללי'
        rate = float(row['vat_rate']) if row else DEFAULT_VAT_RATE
        if category in ZERO_VAT_CATEGORIES:
            rate = 0.0
        return jsonify({'id': product.id, 'name': product.name, 'category': category, 'vat_rate': rate, 'price': float(product.price or 0)})
