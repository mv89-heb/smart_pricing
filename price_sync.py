from flask import jsonify, request
from sqlalchemy import func


def _normalize_name(value):
    """Normalize product names for matching duplicate variants."""
    return " ".join((value or "").strip().split()).casefold()


def register_price_sync(app, db, Product, DailyEntry, is_viewer):
    """Keep one current price across all duplicate product-name variants.

    DailyEntry.unit_price remains a historical snapshot. Product.price is the
    current source of truth. Product rows that differ only by whitespace or
    letter case are treated as the same logical product for price updates.
    """

    def products_matching(name):
        normalized = _normalize_name(name)
        return [p for p in Product.query.all() if _normalize_name(p.name) == normalized]

    def sync_product_price(name, price):
        """Apply the selected current price to every matching Product row."""
        matches = products_matching(name)
        changed = 0
        for product in matches:
            if product.price != price:
                product.price = price
                changed += 1
        return changed, len(matches)

    def reconcile_missing_snapshots():
        products = {}
        for product in Product.query.all():
            products[_normalize_name(product.name)] = product.price
        entries = DailyEntry.query.filter(DailyEntry.unit_price.is_(None)).all()
        changed = 0
        orphaned = []
        for entry in entries:
            key = _normalize_name(entry.product_name)
            if key in products:
                entry.unit_price = products[key]
                changed += 1
            else:
                orphaned.append(entry.product_name)
        if changed:
            db.session.commit()
        return changed, sorted(set(orphaned))

    with app.app_context():
        try:
            reconcile_missing_snapshots()
        except Exception:
            db.session.rollback()

    @app.before_request
    def validate_entry_product():
        if request.method not in {'POST', 'PUT'}:
            return None
        if is_viewer():
            return None

        data = request.get_json(silent=True) or {}

        # Price-list update: synchronize every duplicate product variant before
        # the original endpoint changes its single Product row.
        if request.endpoint in {'add_product', 'update_product'}:
            requested_name = (data.get('name') or '').strip()
            route_name = (request.view_args.get('name') if request.view_args else '') or ''
            product_name = requested_name or route_name
            if product_name and 'price' in data:
                try:
                    price = float(data.get('price'))
                except (TypeError, ValueError):
                    return None
                if price >= 0:
                    sync_product_price(product_name, price)
                    db.session.flush()
            return None

        if request.endpoint not in {'add_entry', 'update_entry'}:
            return None

        product_name = (data.get('product_name') or '').strip()
        entry = None
        if request.endpoint == 'update_entry':
            entry_id = request.view_args.get('entry_id') if request.view_args else None
            entry = db.session.get(DailyEntry, entry_id) if entry_id else None
            if not product_name and entry:
                product_name = entry.product_name

        matches = products_matching(product_name) if product_name else []
        product = matches[0] if matches else None
        if not product:
            if request.endpoint == 'update_entry' and entry is None:
                return None
            return jsonify({
                'success': False,
                'error': f'המוצר "{product_name}" אינו קיים במחירון. יש להוסיף אותו למחירון לפני החיוב.'
            }), 400

        # New/edited charges always use the one current price for the logical product.
        if request.endpoint == 'add_entry' and data.get('quantity') is not None:
            data['product_name'] = product.name
            # Do not rewrite the JSON body; app.py will resolve Product.price.
        if request.endpoint == 'update_entry' and entry:
            entry.unit_price = product.price
        return None

    @app.get('/api/price-sync/status')
    def price_sync_status():
        if is_viewer():
            return jsonify({'error': 'גישת עדכון נדרשת'}), 403
        products = Product.query.count()
        missing = DailyEntry.query.filter(DailyEntry.unit_price.is_(None)).count()
        grouped = {}
        for product in Product.query.all():
            key = _normalize_name(product.name)
            grouped.setdefault(key, []).append(product)
        duplicate_groups = [
            {'names': [p.name for p in rows], 'prices': [p.price for p in rows]}
            for rows in grouped.values() if len(rows) > 1
        ]
        product_names = set(grouped)
        entry_names = {
            _normalize_name(row[0])
            for row in db.session.query(DailyEntry.product_name).distinct().all()
        }
        orphans = sorted(entry_names - product_names)
        return jsonify({
            'products': products,
            'missing_price_snapshots': missing,
            'orphan_entry_products': orphans,
            'duplicate_product_groups': duplicate_groups,
            'synchronized': missing == 0 and not orphans and all(len(x['prices']) == 1 or len(set(x['prices'])) == 1 for x in duplicate_groups),
        })

    @app.post('/api/price-sync/reconcile')
    def reconcile_prices():
        if is_viewer():
            return jsonify({'success': False, 'error': 'אין הרשאות עדכון'}), 403
        try:
            # For duplicate product variants, use the most recently created row
            # as the authoritative current price, then synchronize all variants.
            grouped = {}
            for product in Product.query.order_by(Product.id.desc()).all():
                grouped.setdefault(_normalize_name(product.name), []).append(product)
            synchronized = 0
            for rows in grouped.values():
                if not rows:
                    continue
                price = rows[0].price
                for product in rows:
                    if product.price != price:
                        product.price = price
                        synchronized += 1
            changed, orphaned = reconcile_missing_snapshots()
            db.session.commit()
            return jsonify({
                'success': True,
                'updated_product_prices': synchronized,
                'updated_snapshots': changed,
                'orphan_entry_products': orphaned,
                'message': 'כל מופעי אותו מוצר במחירון מסונכרנים למחיר אחד. מחירי חיובים היסטוריים קיימים נשמרו.'
            })
        except Exception as exc:
            db.session.rollback()
            return jsonify({'success': False, 'error': str(exc)}), 500

    return reconcile_missing_snapshots
