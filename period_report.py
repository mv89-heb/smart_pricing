from datetime import datetime, date
from difflib import SequenceMatcher
from flask import render_template, request, jsonify
from sqlalchemy import text


def _json_error(message, status=400):
    return jsonify({'error': message}), status


def _canonical_product_name(raw_name, products):
    raw = (raw_name or '').strip()
    if not raw or not products:
        return raw
    normalized = ' '.join(raw.split()).casefold()
    exact = [p for p in products if ' '.join((p.name or '').split()).casefold() == normalized]
    if len(exact) == 1:
        return exact[0].name
    candidates = []
    for p in products:
        candidate = ' '.join((p.name or '').split()).casefold()
        if not candidate:
            continue
        ratio = SequenceMatcher(None, normalized, candidate).ratio()
        length_gap = abs(len(normalized) - len(candidate))
        if ratio >= 0.80 and length_gap <= 3:
            candidates.append((ratio, p))
    candidates.sort(key=lambda item: item[0], reverse=True)
    if candidates:
        best_ratio, best = candidates[0]
        second_ratio = candidates[1][0] if len(candidates) > 1 else 0
        if best_ratio >= 0.86 and (len(candidates) == 1 or best_ratio - second_ratio >= 0.06):
            return best.name
    return raw


def _products_to_zero_rows(products, start_date, end_date, existing_product_ids):
    rows = []
    start = datetime.strptime(start_date, '%Y-%m-%d').date()
    end = datetime.strptime(end_date, '%Y-%m-%d').date()
    for product in products:
        if product.id in existing_product_ids:
            continue
        created_at = getattr(product, 'created_at', None)
        if not created_at:
            continue
        created_date = created_at.date() if hasattr(created_at, 'date') else created_at
        if start <= created_date <= end:
            rows.append({
                'id': None, 'product_id': product.id, 'date': created_date.isoformat(),
                'product_name': product.name, 'quantity': 0.0, 'is_extra': False,
                'unit_price': float(product.price or 0), 'total': 0.0,
            })
    return rows


def _vat_settings(db):
    try:
        result = db.session.execute(text('''
            SELECT product_id, category, vat_rate
            FROM product_vat_settings
        ''')).mappings().all()
        settings = {}
        for row in result:
            category = (row['category'] or 'כללי').strip()
            rate = 0.0 if category == 'ירקות' else float(row['vat_rate'] or 0)
            settings[int(row['product_id'])] = {'category': category, 'vat_rate': rate}
        return settings
    except Exception:
        # Keep the period report available if VAT support has not been initialized yet.
        db.session.rollback()
        return {}


def _vat_for_product(settings, product_id):
    item = settings.get(int(product_id)) if product_id is not None else None
    if not item:
        return {'category': 'כללי', 'vat_rate': 18.0}
    return item


def _render_period_report_page():
    html = render_template('period_report.html')
    # The existing template is intentionally kept intact. Inject the final VAT-aware
    # renderer into the page so the deployed report cannot silently use the old table.
    injection = r'''<script>
(function(){
  const originalRenderRows = window.renderRows;
  window.renderRows = function(){
    const q=document.getElementById('search').value.trim().toLowerCase();
    let v=window.rows.filter(r=>`${r.product_name} ${r.date}`.toLowerCase().includes(q));
    v=window.sortRows(v,window.rowsSort);
    document.getElementById('rows').innerHTML=v.map(r=>`<tr><td>${window.fmt(r.date)}</td><td class="font-black">${window.esc(r.product_name)}</td><td><span class="sp-badge ${r.is_extra?'extra':'normal'}">${r.is_extra?'אקסטרה':'רגיל'}</span></td><td class="text-center sp-number">${Number(r.quantity).toLocaleString('he-IL')}</td><td class="text-center sp-number">${window.money(r.unit_price)}</td><td class="text-center sp-number">${Number(r.vat_rate??18).toLocaleString('he-IL',{maximumFractionDigits:2})}%</td><td class="text-center sp-number">${window.money(r.vat_amount||0)}</td><td class="text-center font-black sp-number">${window.money(r.total_with_vat??r.total)}</td></tr>`).join('');
    document.getElementById('empty').classList.toggle('hidden',v.length!==0);
  };
  const head=document.getElementById('rows-head');
  if(head){
    const tr=head.querySelector('tr');
    if(tr && !tr.querySelector('[data-vat-column]')){
      const th=document.createElement('th'); th.setAttribute('data-vat-column','1'); th.className='text-center'; th.textContent='מע״מ'; tr.appendChild(th);
      const th2=document.createElement('th'); th2.className='text-center'; th2.textContent='סה״כ כולל מע״מ'; tr.appendChild(th2);
    }
  }
  const oldExport=window.exportCsv;
  window.exportCsv=function(){
    if(!window.rows.length){alert('אין נתונים לייצוא');return}
    const head=['תאריך','מוצר','סוג','כמות','מחיר יחידה','מע״מ','סכום מע״מ','סה״כ כולל מע״מ'];
    const lines=[head,...window.rows.map(r=>[r.date,r.product_name,r.is_extra?'אקסטרה':'רגיל',r.quantity,r.unit_price,`${Number(r.vat_rate??18).toFixed(2)}%`,r.vat_amount||0,r.total_with_vat??r.total])].map(a=>a.map(v=>`"${String(v??'').replace(/"/g,'""')}"`).join(','));
    const blob=new Blob(['\ufeff'+lines.join('\n')],{type:'text/csv;charset=utf-8'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=`smart-pricing-${document.getElementById('start').value}-${document.getElementById('end').value}.csv`;a.click();URL.revokeObjectURL(a.href);
  };
})();
</script>'''
    return html.replace('</body>', injection + '</body>')


def register_period_report(app, db, DailyEntry, Product=None, ActivityLog=None):
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
            products = Product.query.order_by(Product.name.asc()).all() if Product is not None else []
            vat_settings = _vat_settings(db)
            rows = []
            grand = regular = extra = qty = vat_total = grand_with_vat = 0.0
            entries = (DailyEntry.query
                       .filter(DailyEntry.date >= start_date, DailyEntry.date <= end_date)
                       .order_by(DailyEntry.date.desc(), DailyEntry.product_name.asc(), DailyEntry.id.asc())
                       .all())
            existing_product_names = set()
            existing_product_ids = set()
            for e in entries:
                price = float(e.unit_price or 0)
                amount = float(e.quantity or 0)
                total = price * amount
                product_id = getattr(e, 'product_id', None)
                vat = _vat_for_product(vat_settings, product_id)
                vat_amount = total * vat['vat_rate'] / 100.0
                total_with_vat = total + vat_amount
                grand += total
                vat_total += vat_amount
                grand_with_vat += total_with_vat
                qty += amount
                if e.is_extra:
                    extra += total
                else:
                    regular += total
                display_name = _canonical_product_name(e.product_name, products)
                existing_product_names.add(' '.join(display_name.split()).casefold())
                if product_id is not None:
                    existing_product_ids.add(product_id)
                rows.append({
                    'id': e.id,
                    'product_id': product_id,
                    'date': e.date.isoformat() if hasattr(e.date, 'isoformat') else str(e.date),
                    'product_name': display_name,
                    'quantity': amount,
                    'is_extra': bool(e.is_extra),
                    'unit_price': price,
                    'total': total,
                    'category': vat['category'],
                    'vat_rate': vat['vat_rate'],
                    'vat_amount': vat_amount,
                    'total_with_vat': total_with_vat,
                })

            zero_rows = []
            legacy_added = {}
            if ActivityLog is not None:
                prefix = 'מוצר חדש: '
                legacy_logs = (ActivityLog.query
                               .filter(ActivityLog.action == 'NEW_PRODUCT')
                               .order_by(ActivityLog.timestamp.asc())
                               .all())
                for log in legacy_logs:
                    details = log.details or ''
                    if details.startswith(prefix):
                        logged_name = details[len(prefix):].split(', מחיר:', 1)[0].strip()
                        if logged_name:
                            legacy_added.setdefault(' '.join(logged_name.split()).casefold(), log.timestamp)

            today = date.today()
            for product in products:
                normalized_name = ' '.join((product.name or '').split()).casefold()
                if normalized_name in existing_product_names or product.id in existing_product_ids:
                    continue
                created_at = getattr(product, 'created_at', None)
                if not created_at:
                    created_at = legacy_added.get(normalized_name)
                if created_at:
                    created_date = created_at.date() if hasattr(created_at, 'date') else created_at
                    if not (start <= created_date <= end):
                        continue
                    display_date = created_date
                else:
                    if end < today:
                        continue
                    display_date = end
                vat = _vat_for_product(vat_settings, product.id)
                price = float(product.price or 0)
                zero_rows.append({
                    'id': None,
                    'product_id': product.id,
                    'date': display_date.isoformat(),
                    'product_name': product.name,
                    'quantity': 0.0,
                    'is_extra': False,
                    'unit_price': price,
                    'total': 0.0,
                    'category': vat['category'],
                    'vat_rate': vat['vat_rate'],
                    'vat_amount': 0.0,
                    'total_with_vat': 0.0,
                })

            rows.extend(zero_rows)
            rows.sort(key=lambda r: (r['date'], r['product_name']), reverse=True)
            return jsonify({
                'start_date': start_date,
                'end_date': end_date,
                'rows': rows,
                'summary': {
                    'entries': len(entries),
                    'quantity': qty,
                    'regular_total': regular,
                    'extra_total': extra,
                    'grand_total': grand,
                    'vat_total': vat_total,
                    'grand_total_with_vat': grand_with_vat,
                    'catalog_products_added': len(zero_rows),
                }
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
            needs_legacy_lookup = any(getattr(p, 'created_at', None) is None for p in products)
            added = {}
            if needs_legacy_lookup and ActivityLog is not None:
                for log in ActivityLog.query.filter(ActivityLog.action == 'NEW_PRODUCT').order_by(ActivityLog.timestamp.asc()).all():
                    prefix = 'מוצר חדש: '
                    details = log.details or ''
                    if details.startswith(prefix):
                        name = details[len(prefix):].split(', מחיר:', 1)[0].strip()
                        added.setdefault(name, log.timestamp)
            def added_at(p):
                if getattr(p, 'created_at', None):
                    return p.created_at.isoformat()
                legacy = added.get(p.name)
                return legacy.isoformat() if legacy else None
            return jsonify({'products': [{'id': p.id, 'name': p.name, 'price': float(p.price or 0), 'added_at': added_at(p)} for p in products], 'count': len(products)})
        except Exception:
            app.logger.exception('Period report product query failed')
            return _json_error('שגיאה בטעינת המחירון. הנתונים לא שונו.', 500)

    @app.get('/products/new')
    def product_add_page():
        return render_template('product_add.html')

    @app.get('/dashboard')
    def dashboard_page():
        return render_template('dashboard.html')

    @app.get('/settings')
    def settings_page():
        return render_template('settings.html')

    @app.get('/period-report')
    def period_report_page_alias():
        return _render_period_report_page()

    @app.get('/')
    def period_report_page():
        return _render_period_report_page()
