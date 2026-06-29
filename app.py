import os
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
app = Flask(__name__)

# מפתח אבטחה להצפנת הסשן - חובה ב-Flask
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'super-secret-key-123')

# שם משתמש וסיסמה ממשתני הסביבה או ברירת מחדל
AUTH_USER = os.environ.get('AUTH_USER', 'admin')
AUTH_PASS = os.environ.get('AUTH_PASS', '1234')

# הגדרות מסד נתונים (SQLAlchemy ו-Neon)
from flask_sqlalchemy import SQLAlchemy
db_url = os.environ.get('DATABASE_URL', 'sqlite:///local_products.db')
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

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

with app.app_context():
    db.create_all()

# --- מנגנון בדיקת התחברות (Middleware) ---
@app.before_request
def require_login():
    # רשימת נתיבים שמותר לגשת אליהם ללא התחברות
    allowed_routes = ['login', 'static']
    if request.endpoint not in allowed_routes and not session.get('logged_in'):
        return render_template('login.html')

# --- נתיבי המערכת ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['POST'])
def login():
    data = request.json or {}
    username = data.get('username')
    password = data.get('password')
    
    if username == AUTH_USER and password == AUTH_PASS:
        session['logged_in'] = True
        return jsonify({"success": True})
    return jsonify({"success": False, "message": "שם משתמש או סיסמה שגויים"}), 401

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# --- APIs לניהול מוצרים וחיובים (כולם מוגנים אוטומטית) ---

@app.route('/api/products', methods=['GET'])
def get_products():
    products = Product.query.all()
    return jsonify({p.name: p.price for p in products})

@app.route('/api/products', methods=['POST'])
def add_product():
    data = request.json
    product = Product.query.filter_by(name=data['name']).first()
    if product:
        product.price = data['price']
    else:
        db.session.add(Product(name=data['name'], price=data['price']))
    db.session.commit()
    return jsonify({"success": True})

@app.route('/api/products/<name>', methods=['DELETE'])
def delete_product(name):
    product = Product.query.filter_by(name=name).first()
    if product:
        db.session.delete(product)
        db.session.commit()
    return jsonify({"success": True})

@app.route('/api/entries/<date>', methods=['GET'])
def get_entries(date):
    entries = DailyEntry.query.filter_by(date=date).all()
    return jsonify([{
        'id': e.id, 'product_name': e.product_name, 
        'quantity': e.quantity, 'is_extra': e.is_extra
    } for e in entries])

@app.route('/api/entries', methods=['POST'])
def add_entry():
    data = request.json
    date = data['date']
    product_name = data['product_name']
    quantity = float(data['quantity'])
    is_extra = data.get('is_extra', False)
    
    entry = DailyEntry.query.filter_by(date=date, product_name=product_name, is_extra=is_extra).first()
    if entry:
        entry.quantity += quantity
    else:
        entry = DailyEntry(date=date, product_name=product_name, quantity=quantity, is_extra=is_extra)
        db.session.add(entry)
        
    db.session.commit()
    return jsonify({"success": True})

@app.route('/api/entries/<int:entry_id>', methods=['DELETE'])
def delete_entry(entry_id):
    entry = DailyEntry.query.get(entry_id)
    if entry:
        db.session.delete(entry)
        db.session.commit()
    return jsonify({"success": True})

@app.route('/api/report/month/<year_month>', methods=['GET'])
def get_monthly_report(year_month):
    entries = DailyEntry.query.filter(DailyEntry.date.startswith(year_month)).all()
    return jsonify([{
        'id': e.id, 'date': e.date, 'product_name': e.product_name,
        'quantity': e.quantity, 'is_extra': e.is_extra
    } for e in entries])

if __name__ == '__main__':
    app.run(debug=True)
