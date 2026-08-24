from flask import jsonify, request


def register_price_sync(app, db, Product, DailyEntry, is_viewer):
    """Keep Product.price as the single current price for each logical product.

    Every time a product price is changed, all existing DailyEntry rows for the
    same logical product are synchronized to that price. Future entries already
    read Product.price, so they automatically use the same value.
    """

    def _key(value):
        return (value or '').strip().casefold()

    def _find_product(name):
        key = _key(name)
        if not key:
            return None
        return next((p for p in Product.query.all() if _key(p.name) == key), None)

    def _sync_product_entries(product_name, price):
        """Update every existing charge row belonging to the logical product."""
        key = _key(product_name)
        if not key:
            return 0
        changed = 0
        for entry in DailyEntry.query.all():
            if _key(entry.product_name) == key and entry.unit_price != price:
                entry.unit_price = price
                changed += 1
        return changed

    def reconcile_all_prices():
        """Synchronize every charge snapshot with its current price-list product."""
        products = Product.query.all()
        product_map = {_key(p.name): p.price for p in products}
        changed = 0
        orphaned = []
        for entry in DailyEntry.query.all():
            key = _key(entry.product_name)
            if key in product_map:
                price = product_map[key]
                if entry.unit_price != price:
                    entry.unit_price = price
                    changed += 1
            else:
                orphaned.append(entry.product_name)
        if changed:
            db.session.commit()
        return changed, sorted(set(orphaned))

    with app.app_context():
        try:
            reconcile_all_prices()
        except Exception:
            db.session.rollback()

    @app.before_request
    def validate_and_sync_price():
        if request.endpoint not in {'add_entry', 'update_entry', 'add_product', 'update_product'}:
            return None
        if request.method not in {'POST', 'PUT'} or is_viewer():
            return None

        data = request.get_json(silent=True) or {}

        # Product price update is the authoritative operation. Synchronize
        # every existing charge for the same logical product immediately.
        if request.endpoint in {'add_product', 'update_product'}:
            route_name = request.view_args.get('name') if request.view_args else None
            product_name = (data.get('name') or route_name or '').strip()
            product = _find_product(product_name)

            if product and 'price' in data:
                try:
                    new_price = float(data.get('price'))
                except (TypeError, ValueError):
                    return None
                if new_price >= 0:
                    _sync_product_entries(product.name, new_price)
                    product.price = new_price
                    db.session.commit()
            return None

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
            return jsonify({
                'success': False,
                'error': f'המוצר "{product_name}" אינו קיים במחירון. יש להוסיף אותו למחירון לפני החיוב.'
            }), 400

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
                mismatched.append({
                    'product': product.name,
                    'entry_id': row.id,
                    'entry_price': row.unit_price,
                    'product_price': product.price,
                })
        return jsonify({
            'products': products,
            'missing_price_snapshots': missing,
            'mismatched_price_snapshots': len(mismatched),
            'mismatches': mismatched,
            'orphan_entry_products': sorted(set(orphaned)),
            'synchronized': missing == 0 and not mismatched and not orphaned,
        })

    @app.post('/api/price-sync/reconcile')
    def reconcile_prices():
        if is_viewer():
            return jsonify({'success': False, 'error': 'אין הרשאות עדכון'}), 403
        try:
            changed, orphaned = reconcile_all_prices()
            return jsonify({
                'success': True,
                'updated_snapshots': changed,
                'orphan_entry_products': orphaned,
                'message': 'כל החיובים של מוצרים קיימים סונכרנו למחיר המחירון הנוכחי.'
            })
        except Exception as exc:
            db.session.rollback()
            return jsonify({'success': False, 'error': str(exc)}), 500

    return reconcile_all_prices
