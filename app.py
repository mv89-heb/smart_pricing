import os
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default-secret-key-for-development')
db_url = os.environ.get('DATABASE_URL', 'sqlite:///local_products.db')
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ---------------------------------------------------------
# טבלאות קיימות - לא נוגעים במבנה הבסיסי (Backward Compatible)
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
    # עמודה חדשה: מקפיאה את המחיר בזמן ההזנה כדי שדוחות היסטוריים לא ישתנו
    # אם המחיר במחירון עודכן/נמחק מאוחר יותר. Nullable כדי לא לשבור רשומות ישנות.
    unit_price = db.Column(db.Float, nullable=True)

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
    password = db.Column(db.String(255), nullable=False)  # מכיל הַאש, לא סיסמה גלויה
    role = db.Column(db.String(20), nullable=False, default='viewer')  # admin, editor, viewer

def _column_exists(table_name, column_name):
    try:
        insp = db.inspect(db.engine)
        cols = [c['name'] for c in insp.get_columns(table_name)]
        return column_name in cols
    except Exception:
        return True  # אם אי אפשר לבדוק, לא ננסה להוסיף כדי לא לשבור כלום

def _run_migrations():
    """מיגרציות תוספתיות קטנות שלא פוגעות בנתונים קיימים."""
    try:
        if not _column_exists('daily_entry', 'unit_price'):
            db.session.execute(text('ALTER TABLE daily_entry ADD COLUMN unit_price FLOAT'))
            db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"DEBUG: מיגרציית unit_price נכשלה (כנראה כבר קיימת): {e}")

    try:
        # תיקון אורך עמודת הסיסמה: טבלאות ישנות נוצרו עם VARCHAR(100),
        # אבל ה-hash של werkzeug (scrypt) ארוך יותר -> מרחיבים ל-255
        db.session.execute(text('ALTER TABLE "user" ALTER COLUMN password TYPE VARCHAR(255)'))
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"DEBUG: מיגרציית הרחבת password נכשלה (כנראה כבר תוקנה): {e}")

# הזרקת הטבלאות החדשות באופן מפורש למסד הנתונים הקיים
with app.app_context():
    User.__table__.create(db.engine, checkfirst=True)
    ActivityLog.__table__.create(db.engine, checkfirst=True)
    db.create_all()
    _run_migrations()

    # יצירת מנהל מערכת ראשוני אם הטבלה נוצרה הרגע והיא ריקה
    if User.query.count() == 0:
        default_admin = User(username='admin', password=generate_password_hash('password123'), role='admin')
        db.session.add(default_admin)
        db.session.commit()
        print("DEBUG: נוצר משתמש מנהל ראשוני (admin / password123)")

def log_activity(action, details):
    try:
        current_user = session.get('username', 'מערכת')
        new_log = ActivityLog(action=action, details=details, username=current_user)
        db.session.add(new_log)
        db.session.commit()
    except Exception:
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

    user = User.query.filter_by(username=username).first()
    valid = False

    if user:
        try:
            valid = check_password_hash(user.password, password)
        except Exception:
            valid = False
        # תאימות לאחור: משתמשים ישנים שנשמרו לפני שהוספנו הַאשינג לסיסמאות
        if not valid and user.password == password:
            valid = True
            user.password = generate_password_hash(password)
            db.session.commit()

    if user and valid:
        session['logged_in'] = True
        session['username'] = user.username
        session['role'] = user.role
        log_activity('LOGIN', "התחברות למערכת")
        return jsonify({"success": True, "role": user.role, "username": user.username})

    return jsonify({"success": False, "message": "שם משתמש או סיסמה שגויים"}), 401

@app.route('/logout')
def logout():
    log_activity('LOGOUT', "התנתקות מהמערכת")
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
    data = request.json or {}
    try:
        name = (data.get('name') or '').strip()
        price = data.get('price')
        if not name:
            return jsonify({"success": False, "error": "שם מוצר לא יכול להיות ריק"}), 400
        try:
            price = float(price)
        except (TypeError, ValueError):
            return jsonify({"success": False, "error": "מחיר לא תקין"}), 400
        if price < 0:
            return jsonify({"success": False, "error": "המחיר לא יכול להיות שלילי"}), 400

        product = Product.query.filter_by(name=name).first()
        if product:
            old_price = product.price
            product.price = price
            log_activity('UPDATE_PRICE', f"מוצר: {name}, {old_price} -> {price}")
        else:
            db.session.add(Product(name=name, price=price))
            log_activity('NEW_PRODUCT', f"מוצר חדש: {name}, מחיר: {price}")
        db.session.commit()
        return jsonify({"success": True})
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/products/<path:name>', methods=['PUT'])
def update_product(name):
    """עדכון מוצר קיים: שינוי מחיר ו/או שינוי שם, כולל שרשור השם החדש
    לכל הרשומות ההיסטוריות (DailyEntry) כדי לשמור על עקביות הדוחות."""
    if is_viewer(): return jsonify({"success": False, "error": "אין הרשאות עדכון"}), 403
    data = request.json or {}
    try:
        product = Product.query.filter_by(name=name).first()
        if not product:
            return jsonify({"success": False, "error": "המוצר לא נמצא"}), 404

        new_name = (data.get('name') or name).strip()
        price = data.get('price', product.price)
        try:
            price = float(price)
        except (TypeError, ValueError):
            return jsonify({"success": False, "error": "מחיר לא תקין"}), 400
        if price < 0:
            return jsonify({"success": False, "error": "המחיר לא יכול להיות שלילי"}), 400
        if not new_name:
            return jsonify({"success": False, "error": "שם מוצר לא יכול להיות ריק"}), 400

        if new_name != name and Product.query.filter_by(name=new_name).first():
            return jsonify({"success": False, "error": f'מוצר בשם "{new_name}" כבר קיים'}), 400

        old_price = product.price
        old_name = product.name
        product.price = price
        product.name = new_name

        if new_name != old_name:
            DailyEntry.query.filter_by(product_name=old_name).update({DailyEntry.product_name: new_name})
            log_activity('RENAME_PRODUCT', f"שינוי שם מוצר: {old_name} -> {new_name}")

        if old_price != price:
            log_activity('UPDATE_PRICE', f"מוצר: {new_name}, {old_price} -> {price}")

        db.session.commit()
        return jsonify({"success": True})
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/products/<path:name>', methods=['DELETE'])
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
        return jsonify([{
            'id': e.id, 'product_name': e.product_name, 'quantity': e.quantity,
            'is_extra': e.is_extra, 'unit_price': e.unit_price
        } for e in entries])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/entries', methods=['POST'])
def add_entry():
    if is_viewer(): return jsonify({"success": False, "error": "אין הרשאות הזנה"}), 403
    data = request.json or {}
    try:
        date = data['date']
        product_name = data['product_name']
        quantity = float(data['quantity'])
        is_extra = bool(data.get('is_extra', False))

        if quantity <= 0:
            return jsonify({"success": False, "error": "הכמות חייבת להיות גדולה מאפס"}), 400

        product = Product.query.filter_by(name=product_name).first()
        current_price = product.price if product else 0

        entry = DailyEntry.query.filter_by(date=date, product_name=product_name, is_extra=is_extra).first()
        if entry:
            entry.quantity += quantity
            entry.unit_price = current_price  # רענון המחיר הקפוא לעדכני ביותר
            log_activity('UPDATE_ENTRY', f"עדכון כמות: {quantity} ל-{product_name} בתאריך {date}")
        else:
            entry = DailyEntry(date=date, product_name=product_name, quantity=quantity,
                                is_extra=is_extra, unit_price=current_price)
            db.session.add(entry)
            log_activity('NEW_ENTRY', f"חיוב חדש: {quantity} x {product_name} בתאריך {date}")
        db.session.commit()
        return jsonify({"success": True})
    except (KeyError, TypeError, ValueError):
        return jsonify({"success": False, "error": "נתונים חסרים או לא תקינים"}), 400
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/entries/<int:entry_id>', methods=['PUT'])
def update_entry(entry_id):
    """עריכת כמות/סוג חיוב קיים בלי למחוק ולהוסיף מחדש."""
    if is_viewer(): return jsonify({"success": False, "error": "אין הרשאות עדכון"}), 403
    data = request.json or {}
    try:
        entry = DailyEntry.query.get(entry_id)
        if not entry:
            return jsonify({"success": False, "error": "החיוב לא נמצא"}), 404

        if 'quantity' in data:
            quantity = float(data['quantity'])
            if quantity <= 0:
                return jsonify({"success": False, "error": "הכמות חייבת להיות גדולה מאפס"}), 400
            entry.quantity = quantity
        if 'is_extra' in data:
            entry.is_extra = bool(data['is_extra'])

        log_activity('EDIT_ENTRY', f"עריכת חיוב: {entry.quantity} x {entry.product_name} בתאריך {entry.date}")
        db.session.commit()
        return jsonify({"success": True})
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "נתונים לא תקינים"}), 400
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
        return jsonify([{
            'id': e.id, 'date': e.date, 'product_name': e.product_name, 'quantity': e.quantity,
            'is_extra': e.is_extra, 'unit_price': e.unit_price
        } for e in entries])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---------------------------------------------------------
# API של מנהלים (משתמשים ולוגים)
# ---------------------------------------------------------
@app.route('/api/logs', methods=['GET'])
def get_logs():
    if not is_admin(): return jsonify({"error": "גישת מנהל נדרשת"}), 403
    try:
        logs = ActivityLog.query.order_by(ActivityLog.timestamp.desc()).limit(200).all()
        return jsonify([{'time': l.timestamp.strftime('%d/%m/%Y %H:%M'), 'user': l.username, 'action': l.action, 'details': l.details} for l in logs])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/users', methods=['GET'])
def get_users():
    if not is_admin(): return jsonify({"error": "גישת מנהל נדרשת"}), 403
    try:
        users = User.query.all()
        # לעולם לא מחזירים סיסמאות (גם לא מוצפנות) ללקוח
        return jsonify([{'id': u.id, 'username': u.username, 'role': u.role} for u in users])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/users', methods=['POST'])
def create_or_update_user():
    if not is_admin(): return jsonify({"error": "גישת מנהל נדרשת"}), 403
    data = request.json or {}
    try:
        username = (data.get('username') or '').strip()
        password = data.get('password') or ''
        role = data.get('role', 'viewer')
        if not username:
            return jsonify({"success": False, "error": "שם משתמש לא יכול להיות ריק"}), 400

        user = User.query.filter_by(username=username).first()
        if user:
            if password:  # סיסמה ריקה בעריכה = השארת הסיסמה הקיימת
                user.password = generate_password_hash(password)
            user.role = role
            log_activity('UPDATE_USER', f"עדכון משתמש: {username} לתפקיד {role}")
        else:
            if not password:
                return jsonify({"success": False, "error": "יש להזין סיסמה למשתמש חדש"}), 400
            db.session.add(User(username=username, password=generate_password_hash(password), role=role))
            log_activity('CREATE_USER', f"משתמש חדש: {username} ({role})")
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
        entries = [{'date': e.date, 'product_name': e.product_name, 'quantity': e.quantity,
                    'is_extra': e.is_extra, 'unit_price': e.unit_price} for e in DailyEntry.query.all()]
        return jsonify({"products": products, "entries": entries, "timestamp": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')})
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
