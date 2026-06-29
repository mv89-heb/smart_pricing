import os
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# הגדרת חיבור למסד נתונים (תמיכה ב-Neon PostgreSQL, ואם אין - שימוש ב-SQLite לוקאלי)
db_url = os.environ.get('DATABASE_URL', 'sqlite:///local_products.db')
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# מודל המוצרים במסד הנתונים
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    price = db.Column(db.Float, nullable=False)

# יצירת הטבלאות (אם הן לא קיימות)
with app.app_context():
    db.create_all()

@app.route('/')
def index():
    return render_template('index.html')

# API לשליפת כל המוצרים
@app.route('/api/products', methods=['GET'])
def get_products():
    products = Product.query.all()
    return jsonify({p.name: p.price for p in products})

# API להוספת/עדכון מוצר
@app.route('/api/products', methods=['POST'])
def add_product():
    data = request.json
    name = data.get('name')
    price = data.get('price')
    
    product = Product.query.filter_by(name=name).first()
    if product:
        product.price = price # עדכון מחיר אם קיים
    else:
        product = Product(name=name, price=price)
        db.session.add(product)
    
    db.session.commit()
    return jsonify({"success": True})

# API למחיקת מוצר
@app.route('/api/products/<name>', methods=['DELETE'])
def delete_product(name):
    product = Product.query.filter_by(name=name).first()
    if product:
        db.session.delete(product)
        db.session.commit()
    return jsonify({"success": True})

if __name__ == '__main__':
    app.run(debug=True)
