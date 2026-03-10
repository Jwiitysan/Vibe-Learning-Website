import os
from flask import Flask
from models import db
from routes import learning_bp
from todo_routes import todo_bp

app = Flask(__name__)

# ตั้งค่า Database เป็น SQLite
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'learning.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# ตั้งค่าโฟลเดอร์อัปโหลดรูปภาพ
UPLOAD_FOLDER = os.path.join(basedir, 'static/uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# เชื่อม DB กับ App
db.init_app(app)

# ลงทะเบียน Blueprint /learning
app.register_blueprint(learning_bp)
app.register_blueprint(todo_bp)
# สร้างตารางใน Database หากยังไม่มี
with app.app_context():
    db.create_all()
    # Ensure new column exists for bubbles (manual migration)
    engine = db.engine
    from sqlalchemy import text
    with engine.connect() as conn:
        # check table schema for column
        result = conn.execute(text("PRAGMA table_info(bubble)"))
        cols = [r[1] for r in result.fetchall()]
        if 'include_in_random' not in cols:
            try:
                conn.execute(text("ALTER TABLE bubble ADD COLUMN include_in_random BOOLEAN DEFAULT 1"))
                print('Migration: added include_in_random column to bubble')
            except Exception as e:
                print('Migration failed:', e)
        else:
            print('Migration: include_in_random column already present')

if __name__ == '__main__':
    app.run(debug=True, port=8080)