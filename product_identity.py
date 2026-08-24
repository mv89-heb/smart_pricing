from flask import request
from sqlalchemy import text


def register_product_identity(app, db, Product, DailyEntry):
    """Give each DailyEntry a stable Product.id identity and current Product.name."""

    def key(value):
        return (value or '').strip().casefold()

    def ensure_schema():
        inspector = db.inspect(db.engine)
        columns = {c['name'] for c in inspector.get_columns('daily_entry')}
        if 'product_id' not in columns:
            db.session.execute(text('ALTER TABLE daily_entry ADD COLUMN product_id INTEGER'))
            db.session.commit()
        db.session.execute(text(
            'CREATE INDEX IF NOT EXISTS ix_daily_entry_product_id '
            'ON daily_entry (product_id)'
        ))
        db.session.commit()

    def reconcile():
        ensure_schema()
        products = Product.query.all()
        by_name = {}
        for product in sorted(products, key=lambda p: p.id):
            by_name.setdefault(key(product.name), product)

        changed = 0
        orphaned = []
        for entry in DailyEntry.query.all():
            product_id = db.session.execute(
                text('SELECT product_id FROM daily_entry WHERE id = :id'),
                {'id': entry.id},
            ).scalar()
            product = db.session.get(Product, product_id) if product_id else by_name.get(key(entry.product_name))

            if product is None:
                orphaned.append(entry.product_name)
                continue

            if product_id != product.id:
                db.session.execute(
                    text('UPDATE daily_entry SET product_id = :pid WHERE id = :id'),
                    {'pid': product.id, 'id': entry.id},
                )
                changed += 1

            if entry.product_name != product.name:
                entry.product_name = product.name
                changed += 1

            if entry.unit_price != product.price:
                entry.unit_price = product.price
                changed += 1

        if changed:
            db.session.commit()
        return changed, sorted(set(orphaned))

    # Migration is deliberately fail-fast: if schema/data migration cannot be
    # completed, startup fails instead of running with a partially migrated DB.
    with app.app_context():
        reconcile()

    @app.after_request
    def normalize_product_identity(response):
        if request.endpoint not in {
            'add_entry', 'update_entry', 'add_product', 'update_product',
            'delete_product', 'delete_entry', 'reconcile_prices'
        }:
            return response
        if response.status_code >= 400:
            return response
        try:
            reconcile()
        except Exception:
            db.session.rollback()
            app.logger.exception('Product identity synchronization failed after request')
        return response

    @app.get('/api/product-identity/status')
    def product_identity_status():
        try:
            changed, orphaned = reconcile()
            return {
                'success': True,
                'reconciled_rows': changed,
                'orphan_entry_products': orphaned,
            }
        except Exception as exc:
            db.session.rollback()
            return {'success': False, 'error': str(exc)}, 500

    return reconcile
