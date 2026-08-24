from datetime import datetime, date
from difflib import SequenceMatcher
from flask import render_template, request, jsonify
from sqlalchemy import text


def _json_error(message, status=400):
    return jsonify({'error': message}), status


def _normalize(value):
    return ' '.join((value or '').split()).casefold()


def _canonical_product(raw_name, products):
    raw = (raw_name or '').strip()
    if not raw or not products:
        return raw, None
    normalized = _normalize(raw)
    exact = [p for p in products if _normalize(p.name) == normalized]
    if len(exact) == 1:
        return exact[0].name, exact[0]
    candidates = []
    for p in products:
        candidate = _normalize(p.name)
        if not candidate:
            continue
        ratio = SequenceMatcher(None, normalized, candidate).ratio()
        gap = abs(len(normalized) - len(candidate))
        if ratio >= 0.80 and gap <= 3:
            candidates.append((ratio, p))
    candidates.sort(key=lambda x: x[0], reverse=True)
    if candidates:
        best_ratio, best = candidates[0]
        second_ratio = candidates[1][0] if len(candidates) > 1 else 0
        if best_ratio >= 0.86 and (len(candidates) == 1 or best_ratio - second_ratio >= 0.06):
            return best.name, best
    return raw, None


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
        db.session.rollback()
        return {}


def _vat_for_product(settings, product):
    if product is not None and product.id in settings:
        return settings[product.id]
    return {'category': 'כללי', 'vat_rate': 18.0}


def _render_period_report_page():
    html = render_template('period_report.html')
    injection = r'''<style>
.sp-period-table-wrap{width:100%;overflow-x:auto;overflow-y:visible;-webkit-overflow-scrolling:touch}
.sp-period-table{min-width:920px}
@media(max-width:900px){.sp-period-table-wrap{border:1px solid var(--sp-border);border-radius:12px}.sp-period-table{min-width:920px}}
</style><script>
(function(){
  function installPeriodReportFixes(){
    const table=document.querySelector('#rows-head')?.closest('table');
    const wrap=table?.closest('.sp-table-wrap');
    if(table){table.classList.add('sp-period-table');}
    if(wrap){wrap.classList.add('sp-period-table-wrap');}
    const head=document.getElementById('rows-head')?.querySelector('tr');
    if(head && !head.querySelector('[data-vat-column]')){
      const th=document.createElement('th');
      th.dataset.vatColumn='1'; th.className='text-center'; th.textContent='מע״מ'; head.appendChild(th);
      const th2=document.createElement('th');
      th2.dataset.vatAmountColumn='1'; th2.className='text-center'; th2.textContent='סכום מע״מ'; head.appendChild(th2);
      const th3=document.createElement('th');
      th3.dataset.totalVatColumn='1'; th3.className='text-center'; th3.textContent='סה״כ כולל מע״מ'; head.appendChild(th3);
    }
  }
  function renderPeriodRows(){
    if(typeof rows==='undefined' || typeof $==='undefined') return;
    const q=$('search').value.trim().toLowerCase();
    let v=rows.filter(r=>`${r.product_name} ${r.date}`.toLowerCase().includes(q));
    if(typeof sortRows==='function') v=sortRows(v,rowsSort);
    $('rows').innerHTML=v.map(r=>`<tr><td>${fmt(r.date)}</td><td class="font-black">${esc(r.product_name)}</td><td><span class="sp-badge ${r.is_extra?'extra':'normal'}">${r.is_extra?'אקסטרה':'רגיל'}</span></td><td class="text-center sp-number">${Number(r.quantity||0).toLocaleString('he-IL')}</td><td class="text-center sp-number">${money(r.unit_price)}</td><td class="text-center sp-number">${Number(r.vat_rate??18).toLocaleString('he-IL',{maximumFractionDigits:2})}%</td><td class="text-center sp-number">${money(r.vat_amount||0)}</td><td class="text-center font-black sp-number">${money(r.total_with_vat??r.total)}</td></tr>`).join('');
    $('empty').classList.toggle('hidden',v.length!==0);
  }
  function patch(){
    installPeriodReportFixes();
    if(typeof renderRows==='function' && !renderRows.__vatFixed){
      const original=renderRows;
      window.__originalPeriodRenderRows=original;
      renderRows=renderPeriodRows;
      renderRows.__vatFixed=true;
      renderRows();
    }
  }
  function patchExport(){
    if(typeof exportCsv==='function' && !exportCsv.__vatFixed){
      exportCsv=function(){
        if(!rows.length){alert('אין נתונים לייצוא');return;}
        const head=['תאריך','מוצר','סוג','כמות','מחיר יחידה','מע״מ','סכום מע״מ','סה״כ כולל מע״מ'];
        const lines=[head,...rows.map(r=>[r.date,r.product_name,r.is_extra?'אקסטרה':'רגיל',r.quantity,r.unit_price,`${Number(r.vat_rate??18).toFixed(2)}%`,r.vat_amount||0,r.total_with_vat??r.total])].map(a=>a.map(v=>`"${String(v??'').replace(/"/g,'""')}"`).join(','));
        const blob=new Blob(['\ufeff'+lines.join('\n')],{type:'text/csv;charset=utf-8'});
        const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=`smart-pricing-${$('start').value}-${$('end').value}.csv`;a.click();URL.revokeObjectURL(a.href);
      };
      exportCsv.__vatFixed=true;
    }
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',()=>{patch();patchExport();}); else {patch();patchExport();}
})();
</script>'''
    return html.replace('</body>', injection + '</body>', 1)


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
            rows=[]; grand=regular=extra=qty=vat_total=grand_with_vat=0.0
            entries=(DailyEntry.query.filter(DailyEntry.date >= start_date, DailyEntry.date <= end_date)
                     .order_by(DailyEntry.date.desc(), DailyEntry.product_name.asc(), DailyEntry.id.asc()).all())
            existing_names=set()
            for e in entries:
                display_name, product = _canonical_product(e.product_name, products)
                price=float(e.unit_price or 0); amount=float(e.quantity or 0); total=price*amount
                vat=_vat_for_product(vat_settings, product)
                vat_amount=total*vat['vat_rate']/100.0; total_with_vat=total+vat_amount
                grand+=total; vat_total+=vat_amount; grand_with_vat+=total_with_vat; qty+=amount
                if e.is_extra: extra+=total
                else: regular+=total
                existing_names.add(_normalize(display_name))
                rows.append({'id':e.id,'product_id':getattr(product,'id',None),'date':str(e.date)[:10],
                             'product_name':display_name,'quantity':amount,'is_extra':bool(e.is_extra),
                             'unit_price':price,'total':total,'category':vat['category'],'vat_rate':vat['vat_rate'],
                             'vat_amount':vat_amount,'total_with_vat':total_with_vat})

            legacy_added={}
            if ActivityLog is not None:
                for log in ActivityLog.query.filter(ActivityLog.action=='NEW_PRODUCT').order_by(ActivityLog.timestamp.asc()).all():
                    details=log.details or ''; prefix='מוצר חדש: '
                    if details.startswith(prefix):
                        name=details[len(prefix):].split(', מחיר:',1)[0].strip()
                        if name: legacy_added.setdefault(_normalize(name),log.timestamp)

            today=date.today(); zero_rows=[]
            for product in products:
                if _normalize(product.name) in existing_names: continue
                created_at=getattr(product,'created_at',None) or legacy_added.get(_normalize(product.name))
                if created_at:
                    created_date=created_at.date() if hasattr(created_at,'date') else created_at
                    if not (start <= created_date <= end): continue
                    display_date=created_date
                else:
                    if end < today: continue
                    display_date=end
                vat=_vat_for_product(vat_settings,product); price=float(product.price or 0)
                zero_rows.append({'id':None,'product_id':product.id,'date':display_date.isoformat(),'product_name':product.name,
                                  'quantity':0.0,'is_extra':False,'unit_price':price,'total':0.0,'category':vat['category'],
                                  'vat_rate':vat['vat_rate'],'vat_amount':0.0,'total_with_vat':0.0})
            rows.extend(zero_rows); rows.sort(key=lambda r:(r['date'],r['product_name']),reverse=True)
            return jsonify({'start_date':start_date,'end_date':end_date,'rows':rows,'summary':{
                'entries':len(entries),'quantity':qty,'regular_total':regular,'extra_total':extra,'grand_total':grand,
                'vat_total':vat_total,'grand_total_with_vat':grand_with_vat,'catalog_products_added':len(zero_rows)}})
        except Exception:
            app.logger.exception('Period report query failed')
            return _json_error('שגיאה בטעינת הדוח. הנתונים לא שונו.',500)

    @app.get('/api/report/products')
    def get_report_products():
        if Product is None: return jsonify({'products':[],'count':0})
        try:
            products=Product.query.order_by(Product.name.asc()).all(); added={}
            if ActivityLog is not None:
                for log in ActivityLog.query.filter(ActivityLog.action=='NEW_PRODUCT').order_by(ActivityLog.timestamp.asc()).all():
                    details=log.details or ''; prefix='מוצר חדש: '
                    if details.startswith(prefix):
                        name=details[len(prefix):].split(', מחיר:',1)[0].strip(); added.setdefault(name,log.timestamp)
            def added_at(p):
                return p.created_at.isoformat() if getattr(p,'created_at',None) else (added.get(p.name).isoformat() if added.get(p.name) else None)
            return jsonify({'products':[{'id':p.id,'name':p.name,'price':float(p.price or 0),'added_at':added_at(p)} for p in products],'count':len(products)})
        except Exception:
            app.logger.exception('Period report product query failed')
            return _json_error('שגיאה בטעינת המחירון. הנתונים לא שונו.',500)

    @app.get('/products/new')
    def product_add_page(): return render_template('product_add.html')

    @app.get('/dashboard')
    def dashboard_page(): return render_template('dashboard.html')

    @app.get('/settings')
    def settings_page(): return render_template('settings.html')

    @app.get('/period-report')
    def period_report_page_alias(): return _render_period_report_page()

    @app.get('/')
    def period_report_page(): return _render_period_report_page()
