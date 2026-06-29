import os
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import SQLAlchemyError

app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default-secret-key-for-development')
db_url = os.environ.get('DATABASE_URL', 'sqlite:///local_products.db')
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ---------------------------------------------------------
# טבלאות קיימות - לא נוגעים! (Backward Compatible)
# ---------------------------------------------------------
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    price = db.Column(db.Float, nullable=False)

class DailyEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(20), nullable=False) 
    product_name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    is_extra = db.Column(db.Boolean, default=False)

# ---------------------------------------------------------
# טבלאות חדשות בלבד - מתווספות למסד הקיים (Additive)
# ---------------------------------------------------------
class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    action = db.Column(db.String(50), nullable=False) 
    details = db.Column(db.String(255), nullable=False)
    username = db.Column(db.String(100), default='מערכת')

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='viewer') # admin, editor, viewer

# הזרקת הטבלאות החדשות באופן מפורש למסד הנתונים הקיים
with app.app_context():
    # פקודות אלו מבטיחות שהטבלאות ייווצרו אם הן חסרות, בלי לפגוע בטבלאות הקיימות
    User.__table__.create(db.engine, checkfirst=True)
    ActivityLog.__table__.create(db.engine, checkfirst=True)
    db.create_all()
    
    # יצירת מנהל מערכת ראשוני אם הטבלה נוצרה הרגע והיא ריקה
    if User.query.count() == 0:
        default_admin = User(username='admin', password='password123', role='admin')
        db.session.add(default_admin)
        db.session.commit()
        print("DEBUG: נוצר משתמש מנהל ראשוני (admin / password123)")

def log_activity(action, details):
    try:
        current_user = session.get('username', 'מערכת')
        new_log = ActivityLog(action=action, details=details, username=current_user)
        db.session.add(new_log)
        db.session.commit()
    except Exception as e:
        db.session.rollback()

# ---------------------------------------------------------
# הרשאות
# ---------------------------------------------------------
@app.before_request
def require_login():
    allowed_routes = ['login', 'static']
    if request.endpoint not in allowed_routes and not session.get('logged_in'):
        if request.path.startswith('/api/'):
            return jsonify({"error": "Unauthorized"}), 401
        return redirect(url_for('login'))

def get_current_role():
    return session.get('role', 'viewer')

def is_admin():
    return get_current_role() == 'admin'

def is_viewer():
    return get_current_role() == 'viewer'

# ---------------------------------------------------------
# נתיבים וממשק
# ---------------------------------------------------------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
        
    data = request.json or {}
    username = data.get('username')
    password = data.get('password')
    
    user = User.query.filter_by(username=username, password=password).first()

    if user:
        session['logged_in'] = True
        session['username'] = user.username
        session['role'] = user.role
        log_activity('LOGIN', f"התחברות למערכת")
        return jsonify({"success": True, "role": user.role, "username": user.username})

    return jsonify({"success": False, "message": "שם משתמש או סיסמה שגויים"}), 401

@app.route('/logout')
def logout():
    log_activity('LOGOUT', f"התנתקות מהמערכת")
    session.clear()
    return redirect(url_for('login'))

@app.route('/api/products', methods=['GET'])
def get_products():
    try:
        products = Product.query.all()
        return jsonify({p.name: p.price for p in products})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/products', methods=['POST'])
def add_product():
    if is_viewer(): return jsonify({"success": False, "error": "אין הרשאות עדכון"}), 403
    data = request.json
    try:
        product = Product.query.filter_by(name=data['name']).first()
        if product:
            old_price = product.price
            product.price = data['price']
            log_activity('UPDATE_PRICE', f"מוצר: {data['name']}, {old_price} -> {data['price']}")
        else:
            db.session.add(Product(name=data['name'], price=data['price']))
            log_activity('NEW_PRODUCT', f"מוצר חדש: {data['name']}, מחיר: {data['price']}")
        db.session.commit()
        return jsonify({"success": True})
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/products/<name>', methods=['DELETE'])
def delete_product(name):
    if is_viewer(): return jsonify({"success": False, "error": "אין הרשאות מחיקה"}), 403
    try:
        product = Product.query.filter_by(name=name).first()
        if product:
            db.session.delete(product)
            db.session.commit()
            log_activity('DELETE_PRODUCT', f"מחיקת מוצר: {name}")
        return jsonify({"success": True})
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/entries/<date>', methods=['GET'])
def get_entries(date):
    try:
        entries = DailyEntry.query.filter_by(date=date).all()
        return jsonify([{'id': e.id, 'product_name': e.product_name, 'quantity': e.quantity, 'is_extra': e.is_extra} for e in entries])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/entries', methods=['POST'])
def add_entry():
    if is_viewer(): return jsonify({"success": False, "error": "אין הרשאות הזנה"}), 403
    data = request.json
    try:
        date, product_name, quantity, is_extra = data['date'], data['product_name'], float(data['quantity']), data.get('is_extra', False)
        entry = DailyEntry.query.filter_by(date=date, product_name=product_name, is_extra=is_extra).first()
        if entry:
            entry.quantity += quantity
            log_activity('UPDATE_ENTRY', f"עדכון כמות: {quantity} ל-{product_name} בתאריך {date}")
        else:
            entry = DailyEntry(date=date, product_name=product_name, quantity=quantity, is_extra=is_extra)
            db.session.add(entry)
            log_activity('NEW_ENTRY', f"חיוב חדש: {quantity} x {product_name} בתאריך {date}")
        db.session.commit()
        return jsonify({"success": True})
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/entries/<int:entry_id>', methods=['DELETE'])
def delete_entry(entry_id):
    if is_viewer(): return jsonify({"success": False, "error": "אין הרשאות מחיקה"}), 403
    try:
        entry = DailyEntry.query.get(entry_id)
        if entry:
            log_activity('DELETE_ENTRY', f"מחיקת חיוב: {entry.quantity} x {entry.product_name} מתאריך {entry.date}")
            db.session.delete(entry)
            db.session.commit()
        return jsonify({"success": True})
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/report/month/<year_month>', methods=['GET'])
def get_monthly_report(year_month):
    try:
        entries = DailyEntry.query.filter(DailyEntry.date.startswith(year_month)).all()
        return jsonify([{'id': e.id, 'date': e.date, 'product_name': e.product_name, 'quantity': e.quantity, 'is_extra': e.is_extra} for e in entries])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---------------------------------------------------------
# API של מנהלים (משתמשים ולוגים)
# ---------------------------------------------------------
@app.route('/api/logs', methods=['GET'])
def get_logs():
    if not is_admin(): return jsonify({"error": "גישת מנהל נדרשת"}), 403
    try:
        logs = ActivityLog.query.order_by(ActivityLog.timestamp.desc()).limit(100).all()
        return jsonify([{'time': l.timestamp.strftime('%d/%m/%Y %H:%M'), 'user': l.username, 'action': l.action, 'details': l.details} for l in logs])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/users', methods=['GET'])
def get_users():
    if not is_admin(): return jsonify({"error": "גישת מנהל נדרשת"}), 403
    try:
        users = User.query.all()
        return jsonify([{'id': u.id, 'username': u.username, 'role': u.role, 'password': u.password} for u in users])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/users', methods=['POST'])
def create_or_update_user():
    if not is_admin(): return jsonify({"error": "גישת מנהל נדרשת"}), 403
    data = request.json
    try:
        user = User.query.filter_by(username=data['username']).first()
        if user:
            user.password = data['password']
            user.role = data['role']
            log_activity('UPDATE_USER', f"עדכון משתמש: {data['username']} לתפקיד {data['role']}")
        else:
            db.session.add(User(username=data['username'], password=data['password'], role=data['role']))
            log_activity('CREATE_USER', f"משתמש חדש: {data['username']} ({data['role']})")
        db.session.commit()
        return jsonify({"success": True})
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    if not is_admin(): return jsonify({"error": "גישת מנהל נדרשת"}), 403
    try:
        user = User.query.get(user_id)
        if user:
            if user.username == session.get('username'):
                return jsonify({"success": False, "error": "אינך יכול למחוק את עצמך"}), 400
            log_activity('DELETE_USER', f"מחיקת משתמש: {user.username}")
            db.session.delete(user)
            db.session.commit()
        return jsonify({"success": True})
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/backup', methods=['GET'])
def backup_data():
    if not is_admin(): return jsonify({"error": "גישת מנהל נדרשת"}), 403
    try:
        products = {p.name: p.price for p in Product.query.all()}
        return jsonify({"products": products, "timestamp": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/current_user', methods=['GET'])
def get_current_user_info():
    return jsonify({
        "username": session.get('username', 'אורח'),
        "role": session.get('role', 'viewer')
    })

if __name__ == '__main__':
    app.run(debug=True)
