import os
import secrets
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default-secret-key-for-development')
db_url = os.environ.get('DATABASE_URL', 'sqlite:///local_products.db')
if db_url.startswith('postgres://'): db_url = db_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True); name = db.Column(db.String(100), unique=True, nullable=False); price = db.Column(db.Float, nullable=False)
class DailyEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True); date = db.Column(db.String(20), nullable=False); product_name = db.Column(db.String(100), nullable=False); quantity = db.Column(db.Float, nullable=False); is_extra = db.Column(db.Boolean, default=False); unit_price = db.Column(db.Float, nullable=True); note = db.Column(db.String(255), nullable=True)
class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True); timestamp = db.Column(db.DateTime, default=datetime.utcnow); action = db.Column(db.String(50), nullable=False); details = db.Column(db.String(255), nullable=False); username = db.Column(db.String(100), default='מערכת')
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True); username = db.Column(db.String(100), unique=True, nullable=False); password = db.Column(db.String(255), nullable=False); role = db.Column(db.String(20), nullable=False, default='viewer')
class BillingTemplate(db.Model):
    id = db.Column(db.Integer, primary_key=True); name = db.Column(db.String(100), unique=True, nullable=False); items = db.relationship('BillingTemplateItem', backref='template', cascade='all, delete-orphan')
class BillingTemplateItem(db.Model):
    id = db.Column(db.Integer, primary_key=True); template_id = db.Column(db.Integer, db.ForeignKey('billing_template.id'), nullable=False); product_name = db.Column(db.String(100), nullable=False); quantity = db.Column(db.Float, nullable=False); is_extra = db.Column(db.Boolean, default=False)

def _column_exists(table_name, column_name):
    try: return column_name in [c['name'] for c in db.inspect(db.engine).get_columns(table_name)]
    except Exception: return True

def _run_migrations():
    for sql, table, column in [('ALTER TABLE daily_entry ADD COLUMN unit_price FLOAT','daily_entry','unit_price'),('ALTER TABLE daily_entry ADD COLUMN note VARCHAR(255)','daily_entry','note')]:
        try:
            if not _column_exists(table,column): db.session.execute(text(sql)); db.session.commit()
        except Exception: db.session.rollback()
    try:
        if db.engine.name != 'sqlite': db.session.execute(text('ALTER TABLE "user" ALTER COLUMN password TYPE VARCHAR(255)')); db.session.commit()
    except Exception: db.session.rollback()

with app.app_context():
    User.__table__.create(db.engine, checkfirst=True); ActivityLog.__table__.create(db.engine, checkfirst=True); BillingTemplate.__table__.create(db.engine, checkfirst=True); BillingTemplateItem.__table__.create(db.engine, checkfirst=True); db.create_all(); _run_migrations()
    if User.query.count() == 0:
        temp_pass = secrets.token_hex(4); db.session.add(User(username='admin',password=generate_password_hash(temp_pass),role='admin')); db.session.commit(); print(f'\nSECURITY NOTICE: Admin created. User: admin | Pass: {temp_pass}\n')

def log_activity(action, details):
    try:
        db.session.add(ActivityLog(action=action,details=details,username=session.get('username','מערכת')))
        if ActivityLog.query.count()>1000:
            oldest=ActivityLog.query.order_by(ActivityLog.timestamp.asc()).first()
            if oldest: db.session.delete(oldest)
        db.session.commit()
    except Exception: db.session.rollback()

@app.before_request
def require_login():
    if request.endpoint not in ['login','static']:
        if request.path.startswith('/api/'):
            if request.method in ['POST','PUT','DELETE'] and request.headers.get('X-Requested-With')!='XMLHttpRequest': return jsonify({'error':'CSRF verification failed'}),403
            if not session.get('logged_in'): return jsonify({'error':'Unauthorized'}),401
        elif not session.get('logged_in'): return redirect(url_for('login'))

def is_admin(): return session.get('role','viewer')=='admin'
def is_viewer(): return session.get('role','viewer')=='viewer'
def entry_json(e): return {'id':e.id,'date':e.date,'product_name':e.product_name,'quantity':e.quantity,'is_extra':bool(e.is_extra),'unit_price':e.unit_price,'note':e.note}

@app.route('/')
def index():
    html = render_template('index.html')
    button = '''<a href="/periodic-report" class="text-sm font-bold text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-950/50 hover:bg-indigo-100 px-3 py-2 rounded-lg transition-colors flex items-center gap-2" title="דוח חיובים חודשי ותקופתי"><i class="fa-solid fa-calendar-days"></i><span class="hidden sm:inline">דוח תקופתי</span></a>'''
    marker = '<button onclick="openDashboard()"'
    if 'href="/periodic-report"' not in html and marker in html: html = html.replace(marker, button + '\n                    ' + marker, 1)
    return html

@app.route('/periodic-report')
def periodic_report(): return send_from_directory(app.static_folder,'periodic_report.html')

@app.route('/login',methods=['GET','POST'])
def login():
    if request.method=='GET': return render_template('login.html')
    data=request.json or {}; user=User.query.filter_by(username=data.get('username')).first(); valid=False
    if user:
        try: valid=check_password_hash(user.password,data.get('password'))
        except Exception: valid=False
        if not valid and user.password==data.get('password'):
            valid=True; user.password=generate_password_hash(data.get('password')); db.session.commit()
    if user and valid:
        session['logged_in']=True; session['username']=user.username; session['role']=user.role; log_activity('LOGIN','התחברות למערכת'); return jsonify({'success':True,'role':user.role,'username':user.username})
    return jsonify({'success':False,'message':'שם משתמש או סיסמה שגויים'}),401
@app.route('/logout')
def logout(): log_activity('LOGOUT','התנתקות מהמערכת'); session.clear(); return redirect(url_for('login'))
@app.route('/api/products',methods=['GET'])
def get_products(): return jsonify({p.name:p.price for p in Product.query.all()})
@app.route('/api/products',methods=['POST'])
def add_product():
    if is_viewer(): return jsonify({'success':False,'error':'אין הרשאות'}),403
    data=request.json or {}
    try:
        name=(data.get('name') or '').strip(); price=float(data.get('price'))
        if not name or price<0: return jsonify({'success':False,'error':'נתונים שגויים'}),400
        product=Product.query.filter_by(name=name).first()
        if product: product.price=price; log_activity('UPDATE_PRICE',f'מוצר: {name}, מחיר: {price}')
        else: db.session.add(Product(name=name,price=price)); log_activity('NEW_PRODUCT',f'מוצר חדש: {name}')
        db.session.commit(); return jsonify({'success':True})
    except (TypeError,ValueError): return jsonify({'success':False,'error':'נתונים שגויים'}),400
    except SQLAlchemyError: db.session.rollback(); return jsonify({'success':False,'error':'שגיאת שרת'}),500
@app.route('/api/products/<path:name>',methods=['PUT'])
def update_product(name):
    if is_viewer(): return jsonify({'success':False,'error':'אין הרשאות'}),403
    data=request.json or {}
    try:
        product=Product.query.filter_by(name=name).first()
        if not product: return jsonify({'success':False,'error':'לא נמצא'}),404
        new_name=(data.get('name') or name).strip(); price=float(data.get('price',product.price))
        if price<0 or not new_name: return jsonify({'success':False,'error':'נתונים שגויים'}),400
        if new_name!=name and Product.query.filter_by(name=new_name).first(): return jsonify({'success':False,'error':'מוצר קיים'}),400
        product.price=price; product.name=new_name
        if new_name!=name: DailyEntry.query.filter_by(product_name=name).update({DailyEntry.product_name:new_name})
        db.session.commit(); return jsonify({'success':True})
    except (TypeError,ValueError): return jsonify({'success':False,'error':'נתונים שגויים'}),400
    except SQLAlchemyError: db.session.rollback(); return jsonify({'success':False,'error':'שגיאת שרת'}),500
@app.route('/api/products/<path:name>',methods=['DELETE'])
def delete_product(name):
    if is_viewer(): return jsonify({'success':False,'error':'אין הרשאות'}),403
    try:
        product=Product.query.filter_by(name=name).first()
        if product: db.session.delete(product); db.session.commit()
        return jsonify({'success':True})
    except SQLAlchemyError: db.session.rollback(); return jsonify({'success':False,'error':'שגיאת שרת'}),500
@app.route('/api/entries/<date>',methods=['GET'])
def get_entries(date): return jsonify([entry_json(e) for e in DailyEntry.query.filter_by(date=date).all()])
@app.route('/api/entries',methods=['POST'])
def add_entry():
    if is_viewer(): return jsonify({'success':False,'error':'אין הרשאות'}),403
    data=request.json or {}
    try:
        date=data['date']; product_name=data['product_name']; quantity=float(data['quantity']); is_extra=bool(data.get('is_extra',False)); note=(data.get('note') or '').strip()
        if quantity<=0: return jsonify({'success':False,'error':'כמות חייבת להיות גדולה מאפס'}),400
        product=Product.query.filter_by(name=product_name).first(); current_price=product.price if product else 0; entry=DailyEntry.query.filter_by(date=date,product_name=product_name,is_extra=is_extra).first()
        if entry and not note: entry.quantity+=quantity; entry.unit_price=current_price
        else: db.session.add(DailyEntry(date=date,product_name=product_name,quantity=quantity,is_extra=is_extra,unit_price=current_price,note=note or None))
        db.session.commit(); return jsonify({'success':True})
    except (KeyError,TypeError,ValueError): return jsonify({'success':False,'error':'נתונים שגויים'}),400
    except SQLAlchemyError: db.session.rollback(); return jsonify({'success':False,'error':'שגיאת שרת'}),500
@app.route('/api/entries/<int:entry_id>',methods=['PUT'])
def update_entry(entry_id):
    if is_viewer(): return jsonify({'success':False,'error':'אין הרשאות'}),403
    data=request.json or {}
    try:
        entry=db.session.get(DailyEntry,entry_id)
        if not entry: return jsonify({'success':False,'error':'לא נמצא'}),404
        if 'quantity' in data:
            q=float(data['quantity'])
            if q<=0: return jsonify({'success':False,'error':'כמות שגויה'}),400
            entry.quantity=q
        if 'is_extra' in data: entry.is_extra=bool(data['is_extra'])
        if 'note' in data: entry.note=(data['note'] or '').strip() or None
        db.session.commit(); log_activity('UPDATE_ENTRY',f'חיוב #{entry.id} עודכן'); return jsonify({'success':True})
    except (TypeError,ValueError): return jsonify({'success':False,'error':'נתונים שגויים'}),400
    except SQLAlchemyError: db.session.rollback(); return jsonify({'success':False,'error':'שגיאת שרת'}),500
@app.route('/api/entries/<int:entry_id>',methods=['DELETE'])
def delete_entry(entry_id):
    if is_viewer(): return jsonify({'success':False,'error':'אין הרשאות'}),403
    try:
        entry=db.session.get(DailyEntry,entry_id)
        if entry:
            details=f'חיוב #{entry.id}: {entry.product_name}, {entry.date}'; db.session.delete(entry); db.session.commit(); log_activity('DELETE_ENTRY',details)
        return jsonify({'success':True})
    except SQLAlchemyError: db.session.rollback(); return jsonify({'success':False,'error':'שגיאת שרת'}),500
@app.route('/api/bulk/entries/<date>',methods=['DELETE'])
def clear_date_entries(date):
    if is_viewer(): return jsonify({'success':False,'error':'אין הרשאות'}),403
    try: DailyEntry.query.filter_by(date=date).delete(); db.session.commit(); return jsonify({'success':True})
    except SQLAlchemyError: db.session.rollback(); return jsonify({'success':False,'error':'שגיאת שרת'}),500
@app.route('/api/bulk/season',methods=['DELETE'])
def reset_season():
    if not is_admin(): return jsonify({'success':False,'error':'נדרש מנהל'}),403
    try: DailyEntry.query.delete(); db.session.commit(); return jsonify({'success':True})
    except SQLAlchemyError: db.session.rollback(); return jsonify({'success':False,'error':'שגיאת שרת'}),500
@app.route('/api/report/month/<year_month>',methods=['GET'])
def get_monthly_report(year_month):
    if len(year_month)!=7 or year_month[4]!='-' or not year_month[:4].isdigit() or not year_month[5:].isdigit(): return jsonify({'error':'חודש לא תקין'}),400
    return jsonify([entry_json(e) for e in DailyEntry.query.filter(DailyEntry.date.startswith(year_month)).order_by(DailyEntry.date.asc(),DailyEntry.id.asc()).all()])
@app.route('/api/report/period',methods=['GET'])
def get_period_report():
    start=(request.args.get('from') or '').strip(); end=(request.args.get('to') or '').strip()
    if not start or not end or len(start)!=10 or len(end)!=10 or start>end: return jsonify({'error':'טווח תאריכים לא תקין'}),400
    try: datetime.strptime(start,'%Y-%m-%d'); datetime.strptime(end,'%Y-%m-%d')
    except ValueError: return jsonify({'error':'תאריך לא תקין'}),400
    entries=DailyEntry.query.filter(DailyEntry.date>=start,DailyEntry.date<=end).order_by(DailyEntry.date.asc(),DailyEntry.id.asc()).all(); regular=extra=0.0; product_summary={}; day_summary={}
    for e in entries:
        total=float(e.quantity or 0)*float(e.unit_price or 0); p=product_summary.setdefault(e.product_name,{'quantity':0.0,'total':0.0}); p['quantity']+=float(e.quantity or 0); p['total']+=total; d=day_summary.setdefault(e.date,{'regular':0.0,'extra':0.0,'total':0.0})
        if e.is_extra: extra+=total; d['extra']+=total
        else: regular+=total; d['regular']+=total
        d['total']+=total
    grand=regular+extra
    return jsonify({'from':start,'to':end,'entries':[entry_json(e) for e in entries],'summary':{'regular_total':regular,'extra_total':extra,'grand_total':grand,'days_count':len(day_summary),'average_day':grand/len(day_summary) if day_summary else 0},'product_summary':product_summary,'day_summary':day_summary})
@app.route('/api/templates',methods=['GET'])
def get_templates(): return jsonify({t.name:[{'product_name':i.product_name,'quantity':i.quantity,'is_extra':i.is_extra} for i in t.items] for t in BillingTemplate.query.all()})
@app.route('/api/templates',methods=['POST'])
def save_template():
    if is_viewer(): return jsonify({'success':False,'error':'אין הרשאות'}),403
    data=request.json or {}; name=data.get('name'); items=data.get('items',[])
    if not name or not items: return jsonify({'success':False,'error':'נתונים חסרים'}),400
    try:
        existing=BillingTemplate.query.filter_by(name=name).first()
        if existing: db.session.delete(existing)
        t=BillingTemplate(name=name); db.session.add(t)
        for i in items: db.session.add(BillingTemplateItem(template=t,product_name=i['product_name'],quantity=i['quantity'],is_extra=i.get('is_extra',False)))
        db.session.commit(); return jsonify({'success':True})
    except SQLAlchemyError: db.session.rollback(); return jsonify({'success':False,'error':'שגיאת שרת'}),500
@app.route('/api/templates/<path:name>',methods=['DELETE'])
def delete_template(name):
    if is_viewer(): return jsonify({'success':False,'error':'אין הרשאות'}),403
    try:
        t=BillingTemplate.query.filter_by(name=name).first()
        if t: db.session.delete(t); db.session.commit()
        return jsonify({'success':True})
    except SQLAlchemyError: db.session.rollback(); return jsonify({'success':False,'error':'שגיאת שרת'}),500
@app.route('/api/logs',methods=['GET'])
def get_logs():
    if not is_admin(): return jsonify({'error':'נדרש מנהל'}),403
    return jsonify([{'time':l.timestamp.strftime('%d/%m/%Y %H:%M'),'user':l.username,'action':l.action,'details':l.details} for l in ActivityLog.query.order_by(ActivityLog.timestamp.desc()).limit(200).all()])
@app.route('/api/users',methods=['GET'])
def get_users():
    if not is_admin(): return jsonify({'error':'נדרש מנהל'}),403
    return jsonify([{'id':u.id,'username':u.username,'role':u.role} for u in User.query.all()])
@app.route('/api/users',methods=['POST'])
def create_or_update_user():
    if not is_admin(): return jsonify({'error':'נדרש מנהל'}),403
    data=request.json or {}
    try:
        username=(data.get('username') or '').strip(); password=data.get('password') or ''; role=data.get('role','viewer')
        if not username: return jsonify({'success':False,'error':'שם משתמש ריק'}),400
        user=User.query.filter_by(username=username).first()
        if user:
            if password: user.password=generate_password_hash(password)
            user.role=role
        else:
            if not password: return jsonify({'success':False,'error':'חובה סיסמה'}),400
            db.session.add(User(username=username,password=generate_password_hash(password),role=role))
        db.session.commit(); return jsonify({'success':True})
    except SQLAlchemyError: db.session.rollback(); return jsonify({'success':False,'error':'שגיאת שרת'}),500
@app.route('/api/users/<int:user_id>',methods=['DELETE'])
def delete_user(user_id):
    if not is_admin(): return jsonify({'error':'נדרש מנהל'}),403
    try:
        u=db.session.get(User,user_id)
        if u and u.username!=session.get('username'): db.session.delete(u); db.session.commit()
        return jsonify({'success':True})
    except SQLAlchemyError: db.session.rollback(); return jsonify({'success':False,'error':'שגיאת שרת'}),500
@app.route('/api/backup',methods=['GET'])
def backup_data():
    if not is_admin(): return jsonify({'error':'נדרש מנהל'}),403
    return jsonify({'products':{p.name:p.price for p in Product.query.all()},'entries':[entry_json(e) for e in DailyEntry.query.all()],'timestamp':datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')})
@app.route('/api/current_user',methods=['GET'])
def get_current_user_info(): return jsonify({'username':session.get('username','אורח'),'role':session.get('role','viewer')})
if __name__=='__main__': app.run(debug=True)
