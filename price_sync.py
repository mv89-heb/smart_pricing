from flask import jsonify, request, session
from sqlalchemy import func, text, update


def register_price_sync(app, db, Product, DailyEntry, is_viewer, ActivityLog=None):
    """Keep the price-list product authoritative for matching charge rows."""

    def _log(action, details):
        if ActivityLog is None:
            return
        db.session.add(ActivityLog(
            action=action,
            details=details,
            username=session.get('username', 'מערכת'),
        ))

    def _key(value):
        return (value or '').strip().casefold()

    def _find_product(name):
        key = (name or '').strip()
        if not key:
            return None
        # The product name is UNIQUE, so use the indexed exact lookup first.
        product = Product.query.filter_by(name=key).first()
        if product:
            return product
        # Legacy rows/names may differ only by surrounding whitespace/case.
        # Use trim(), not the Postgres-only btrim(): trim() exists on both
        # Postgres and SQLite (the local-dev fallback engine) and trims both
        # sides by default, so behaviour is unchanged on Postgres.
        normalized = _key(key)
        return Product.query.filter(func.lower(func.trim(Product.name)) == normalized).first()

    def _ensure_performance_index():
        db.session.execute(text(
            'CREATE INDEX IF NOT EXISTS ix_daily_entry_product_name_norm '
            'ON daily_entry (lower(trim(product_name)))'
        ))
        db.session.commit()

    def _sync_product_entries(product_name, price, new_name=None):
        """Update matching charge rows with one set-based DB statement."""
        key = _key(product_name)
        if not key:
            return 0

        values = {'unit_price': price}
        if new_name is not None:
            values['product_name'] = new_name

        stmt = update(DailyEntry).where(
            func.lower(func.trim(DailyEntry.product_name)) == key
        )

        # Avoid rewriting rows that already contain the desired values.
        if new_name is None:
            stmt = stmt.where(DailyEntry.unit_price.is_distinct_from(price))
        else:
            stmt = stmt.where(
                (DailyEntry.unit_price.is_distinct_from(price)) |
                (DailyEntry.product_name != new_name)
            )

        result = db.session.execute(
            stmt.values(**values).execution_options(synchronize_session=False)
        )
        return int(result.rowcount or 0)

    def reconcile_all_prices():
        """Synchronize all matching entries with one set-based UPDATE."""
        result = db.session.execute(text('''
            UPDATE daily_entry AS d
            SET unit_price = p.price
            FROM product AS p
            WHERE lower(trim(d.product_name)) = lower(trim(p.name))
              AND d.unit_price IS DISTINCT FROM p.price
        '''))
        return int(result.rowcount or 0), []

    with app.app_context():
        try:
            _ensure_performance_index()
            reconcile_all_prices()
            db.session.commit()
        except Exception:
            db.session.rollback()

    @app.before_request
    def validate_and_sync_price():
        if request.endpoint not in {'add_entry', 'update_entry', 'add_product', 'update_product'}:
            return None
        if request.method not in {'POST', 'PUT'} or is_viewer():
            return None
        data = request.get_json(silent=True) or {}

        if request.endpoint == 'update_product':
            route_name = request.view_args.get('name') if request.view_args else None
            old_name = (route_name or '').strip()
            product = _find_product(old_name)
            if not product:
                return jsonify({'success': False, 'error': 'המוצר לא נמצא'}), 404

            new_name = (data.get('name') if data.get('name') is not None else product.name).strip()
            if not new_name:
                return jsonify({'success': False, 'error': 'שם מוצר לא יכול להיות ריק'}), 400

            try:
                new_price = float(data.get('price', product.price))
            except (TypeError, ValueError):
                return jsonify({'success': False, 'error': 'מחיר לא תקין'}), 400
            if new_price < 0:
                return jsonify({'success': False, 'error': 'המחיר לא יכול להיות שלילי'}), 400

            # Exact lookup first; Product.name is unique and indexed.
            existing = Product.query.filter_by(name=new_name).first()
            if existing is not None and existing.id != product.id:
                return jsonify({'success': False, 'error': f'מוצר בשם "{new_name}" כבר קיים'}), 400

            old_price = product.price
            old_product_name = product.name
            renamed = old_product_name != new_name
            price_changed = old_price != new_price

            # Nothing changed: return immediately without touching DailyEntry.
            if not renamed and not price_changed:
                return jsonify({
                    'success': True,
                    'product': {'id': product.id, 'name': product.name, 'price': product.price},
                    'renamed': False,
                    'price_updated': False,
                    'updated_entries': 0,
                })

            product.name = new_name
            product.price = new_price

            updated_entries = 0
            if renamed or price_changed:
                updated_entries = _sync_product_entries(
                    old_product_name,
                    new_price,
                    new_name=new_name if renamed else None,
                )

            if renamed:
                _log('RENAME_PRODUCT', f"שינוי שם מוצר: {old_product_name} -> {new_name}")
            if price_changed:
                _log('UPDATE_PRICE', f"מוצר: {new_name}, {old_price} -> {new_price}")

            # Single transaction: product + all matching entries commit together.
            db.session.commit()
            return jsonify({
                'success': True,
                'product': {'id': product.id, 'name': product.name, 'price': product.price},
                'renamed': renamed,
                'price_updated': price_changed,
                'updated_entries': updated_entries,
            })

        if request.endpoint == 'add_product':
            product_name = (data.get('name') or '').strip()
            product = _find_product(product_name)
            # No existing product with this name: let add_product's own view
            # handle creation (and its own NEW_PRODUCT log entry) normally.
            if not product or 'price' not in data:
                return None
            try:
                new_price = float(data.get('price'))
            except (TypeError, ValueError):
                return None
            if new_price < 0:
                return None
            old_price = product.price
            price_changed = old_price != new_price
            # Own this request end-to-end (sync + log + commit) instead of
            # mutating the price here and letting add_product's view log
            # again afterwards - that used to compute "old_price" from the
            # value we had *already written*, so every price change through
            # this endpoint was logged as e.g. "9.0 -> 9.0" instead of the
            # real before/after prices.
            updated_entries = 0
            if price_changed:
                updated_entries = _sync_product_entries(product.name, new_price)
                product.price = new_price
                _log('UPDATE_PRICE', f"מוצר: {product.name}, {old_price} -> {new_price}")
            db.session.commit()
            return jsonify({
                'success': True,
                'product': {'id': product.id, 'name': product.name, 'price': product.price},
                'price_updated': price_changed,
                'updated_entries': updated_entries,
            })

        product_name = (data.get('product_name') or '').strip()
        entry = None
        if request.endpoint == 'update_entry':
            entry_id = request.view_args.get('entry_id') if request.view_args else None
            entry = db.session.get(DailyEntry, entry_id) if entry_id else None
            if not product_name and entry:
                product_name = entry.product_name
        product = _find_product(product_name) if product_name else None
        if not product:
            if request.endpoint == 'update_entry' and entry is None:
                return None
            return jsonify({'success': False, 'error': f'המוצר "{product_name}" אינו קיים במחירון. יש להוסיף אותו למחירון לפני החיוב.'}), 400
        if entry:
            entry.unit_price = product.price
        return None

    @app.get('/api/price-sync/status')
    def price_sync_status():
        if is_viewer():
            return jsonify({'error': 'גישת עדכון נדרשת'}), 403
        products = Product.query.count()
        missing = DailyEntry.query.filter(DailyEntry.unit_price.is_(None)).count()
        product_map = {_key(p.name): p for p in Product.query.all()}
        mismatched = []
        orphaned = []
        for row in DailyEntry.query.all():
            product = product_map.get(_key(row.product_name))
            if not product:
                orphaned.append(row.product_name)
            elif row.unit_price != product.price:
                mismatched.append({'product': product.name, 'entry_id': row.id, 'entry_price': row.unit_price, 'product_price': product.price})
        return jsonify({'products': products, 'missing_price_snapshots': missing, 'mismatched_price_snapshots': len(mismatched), 'mismatches': mismatched, 'orphan_entry_products': sorted(set(orphaned)), 'synchronized': missing == 0 and not mismatched and not orphaned})

    @app.post('/api/price-sync/reconcile')
    def reconcile_prices():
        if is_viewer():
            return jsonify({'success': False, 'error': 'אין הרשאות עדכון'}), 403
        try:
            changed, orphaned = reconcile_all_prices()
            db.session.commit()
            return jsonify({'success': True, 'updated_snapshots': changed, 'orphan_entry_products': orphaned, 'message': 'כל החיובים של מוצרים קיימים סונכרנו למחיר המחירון הנוכחי.'})
        except Exception as exc:
            db.session.rollback()
            return jsonify({'success': False, 'error': str(exc)}), 500

    return reconcile_all_prices
