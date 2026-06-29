import os
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import SQLAlchemyError

app = Flask(__name__)

# הגדרת סשן
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default-secret-key-for-development')

# התחברות למסד הנתונים (Neon / SQLite)
db_url = os.environ.get('DATABASE_URL', 'sqlite:///local_products.db')
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ---------------------------------------------------------
# מודלים ישנים - ללא שום שינוי! (Backward Compatible)
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
# מודל חדש! - יומן פעולות (Audit Log) לא נוגע בקיים
# ---------------------------------------------------------
class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    action = db.Column(db.String(50), nullable=False) # למשל: 'DELETE_ENTRY', 'UPDATE_PRICE'
    details = db.Column(db.String(255), nullable=False)

# יצירת טבלאות (ייצור רק את החדשה, הישנות יישארו בשלמותן)
with app.app_context():
    db.create_all()

# פונקציית עזר לכתיבת לוגים מבלי לעצור את המערכת
def log_activity(action, details):
    try:
        new_log = ActivityLog(action=action, details=details)
        db.session.add(new_log)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Failed to log activity: {e}")

# ---------------------------------------------------------
# הגנת התחברות והרשאות (RBAC)
# ---------------------------------------------------------
@app.before_request
def require_login():
    allowed_routes = ['login', 'static']
    if request.endpoint not in allowed_routes and not session.get('logged_in'):
        if request.path.startswith('/api/'):
            return jsonify({"error": "Unauthorized"}), 401
        return redirect(url_for('login'))

def is_viewer():
    """בודק אם המשתמש מחובר במצב קריאה בלבד"""
    return session.get('role') == 'viewer'

# ---------------------------------------------------------
# נתיבי תצוגה
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
    
    # מנהל ראשי
    admin_user = os.environ.get('AUTH_USER', 'admin')
    admin_pass = os.environ.get('AUTH_PASS', '1234')
    
    # מצב צופה/עובד
    viewer_pass = os.environ.get('VIEWER_PASS', '1111') 

    if username == admin_user and password == admin_pass:
        session['logged_in'] = True
        session['role'] = 'admin'
        log_activity('LOGIN', 'Admin logged in')
        return jsonify({"success": True, "role": "admin"})
        
    elif username == admin_user and password == viewer_pass:
        session['logged_in'] = True
        session['role'] = 'viewer'
        log_activity('LOGIN', 'Viewer logged in')
        return jsonify({"success": True, "role": "viewer"})

    return jsonify({"success": False, "message": "שם משתמש או סיסמה שגויים"}), 401

@app.route('/logout')
def logout():
    log_activity('LOGOUT', f"User role {session.get('role')} logged out")
    session.clear()
    return redirect(url_for('login'))

# ---------------------------------------------------------
# API לניהול נתונים - עם Audit Logs והגנת צופה
# ---------------------------------------------------------
@app.route('/api/products', methods=['GET'])
def get_products():
    try:
        products = Product.query.all()
        return jsonify({p.name: p.price for p in products})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/products', methods=['POST'])
def add_product():
    if is_viewer():
        return jsonify({"success": False, "error": "אין הרשאות עדכון למחירון"}), 403
        
    data = request.json
    try:
        product = Product.query.filter_by(name=data['name']).first()
        if product:
            old_price = product.price
            product.price = data['price']
            log_activity('UPDATE_PRICE', f"Product: {data['name']}, {old_price} -> {data['price']}")
        else:
            db.session.add(Product(name=data['name'], price=data['price']))
            log_activity('NEW_PRODUCT', f"Product: {data['name']}, Price: {data['price']}")
            
        db.session.commit()
        return jsonify({"success": True})
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/products/<name>', methods=['DELETE'])
def delete_product(name):
    if is_viewer():
        return jsonify({"success": False, "error": "אין הרשאות מחיקה"}), 403

    try:
        product = Product.query.filter_by(name=name).first()
        if product:
            db.session.delete(product)
            db.session.commit()
            log_activity('DELETE_PRODUCT', f"Deleted Product: {name}")
        return jsonify({"success": True})
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/entries/<date>', methods=['GET'])
def get_entries(date):
    try:
        entries = DailyEntry.query.filter_by(date=date).all()
        return jsonify([{
            'id': e.id, 'product_name': e.product_name, 
            'quantity': e.quantity, 'is_extra': e.is_extra
        } for e in entries])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/entries', methods=['POST'])
def add_entry():
    data = request.json
    try:
        date = data['date']
        product_name = data['product_name']
        quantity = float(data['quantity'])
        is_extra = data.get('is_extra', False)
        
        entry = DailyEntry.query.filter_by(date=date, product_name=product_name, is_extra=is_extra).first()
        if entry:
            entry.quantity += quantity
            log_activity('UPDATE_ENTRY', f"Added {quantity} to {product_name} on {date}")
        else:
            entry = DailyEntry(date=date, product_name=product_name, quantity=quantity, is_extra=is_extra)
            db.session.add(entry)
            log_activity('NEW_ENTRY', f"Added {quantity} x {product_name} on {date}")
            
        db.session.commit()
        return jsonify({"success": True})
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/entries/<int:entry_id>', methods=['DELETE'])
def delete_entry(entry_id):
    if is_viewer():
        return jsonify({"success": False, "error": "אין הרשאות מחיקה"}), 403

    try:
        entry = DailyEntry.query.get(entry_id)
        if entry:
            log_activity('DELETE_ENTRY', f"Deleted {entry.quantity} x {entry.product_name} from {entry.date}")
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
        return jsonify([{
            'id': e.id, 'date': e.date, 'product_name': e.product_name,
            'quantity': e.quantity, 'is_extra': e.is_extra
        } for e in entries])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
