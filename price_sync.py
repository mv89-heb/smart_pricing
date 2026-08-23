from flask import jsonify, request


def register_price_sync(app, db, Product, DailyEntry, is_viewer):
    """Keep Product.price as the current source of truth.

    DailyEntry.unit_price is a historical snapshot. Changing the current
    product price therefore affects future charges, while historical reports
    remain financially stable. Missing legacy snapshots are backfilled safely.
    """

    def reconcile_missing_snapshots():
        products = {p.name: p.price for p in Product.query.all()}
        entries = DailyEntry.query.filter(DailyEntry.unit_price.is_(None)).all()
        changed = 0
        orphaned = []
        for entry in entries:
            if entry.product_name in products:
                entry.unit_price = products[entry.product_name]
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
        if request.endpoint not in {'add_entry', 'update_entry'} or request.method not in {'POST', 'PUT'}:
            return None
        if is_viewer():
            return None

        data = request.get_json(silent=True) or {}
        product_name = (data.get('product_name') or '').strip()
        if request.endpoint == 'update_entry' and not product_name:
            entry_id = request.view_args.get('entry_id') if request.view_args else None
            entry = db.session.get(DailyEntry, entry_id) if entry_id else None
            product_name = entry.product_name if entry else ''

        if product_name and not Product.query.filter_by(name=product_name).first():
            return jsonify({
                'success': False,
                'error': f'המוצר "{product_name}" אינו קיים במחירון. יש להוסיף אותו למחירון לפני החיוב.'
            }), 400
        return None

    @app.get('/api/price-sync/status')
    def price_sync_status():
        if is_viewer():
            return jsonify({'error': 'גישת עדכון נדרשת'}), 403
        products = Product.query.count()
        missing = DailyEntry.query.filter(DailyEntry.unit_price.is_(None)).count()
        product_names = {p.name for p in Product.query.all()}
        entry_names = {row[0] for row in db.session.query(DailyEntry.product_name).distinct().all()}
        orphans = sorted(entry_names - product_names)
        return jsonify({
            'products': products,
            'missing_price_snapshots': missing,
            'orphan_entry_products': orphans,
            'synchronized': missing == 0 and not orphans,
        })

    @app.post('/api/price-sync/reconcile')
    def reconcile_prices():
        if is_viewer():
            return jsonify({'success': False, 'error': 'אין הרשאות עדכון'}), 403
        try:
            changed, orphaned = reconcile_missing_snapshots()
            return jsonify({
                'success': True,
                'updated_snapshots': changed,
                'orphan_entry_products': orphaned,
                'message': 'חיובים ישנים ללא מחיר קיבלו את מחיר המחירון הנוכחי. מחירים היסטוריים קיימים לא שונו.'
            })
        except Exception as exc:
            db.session.rollback()
            return jsonify({'success': False, 'error': str(exc)}), 500

    return reconcile_missing_snapshots
