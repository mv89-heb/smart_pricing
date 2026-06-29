import os
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)

# התחברות למסד הנתונים
db_url = os.environ.get('DATABASE_URL', 'sqlite:///local_products.db')
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- מודלים של מסד הנתונים ---

# 1. טבלת מחירון בסיס
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    price = db.Column(db.Float, nullable=False)

# 2. טבלת רישום שוטף (לפי תאריך) - חדש!
class DailyEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(20), nullable=False) # שומר תאריך בפורמט YYYY-MM-DD
    product_name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Float, nullable=False)

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    return render_template('index.html')

# --- ניהול מחירון ---
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

# --- ניהול רישום לפי תאריכים ---
@app.route('/api/entries/<date>', methods=['GET'])
def get_entries(date):
    entries = DailyEntry.query.filter_by(date=date).all()
    return jsonify([{'id': e.id, 'product_name': e.product_name, 'quantity': e.quantity} for e in entries])

@app.route('/api/entries', methods=['POST'])
def add_entry():
    data = request.json
    date = data['date']
    product_name = data['product_name']
    quantity = float(data['quantity'])
    
    # אם כבר קיים רישום למוצר הזה באותו תאריך, נוסיף לכמות. אחרת, ניצור חדש.
    entry = DailyEntry.query.filter_by(date=date, product_name=product_name).first()
    if entry:
        entry.quantity += quantity
    else:
        entry = DailyEntry(date=date, product_name=product_name, quantity=quantity)
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

if __name__ == '__main__':
    app.run(debug=True)
