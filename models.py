from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    background_image = db.Column(db.String(255), nullable=True) # เก็บชื่อไฟล์รูป
    
    # ความสัมพันธ์: 1 วิชา มีหลาย Topic
    topics = db.relationship('Topic', backref='course', lazy=True, cascade="all, delete-orphan")

class Topic(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    order_index = db.Column(db.Integer, default=0) # ใช้เรียงลำดับซ้ายมือ
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    
    # ความสัมพันธ์: 1 Topic มีหลาย Bubble
    bubbles = db.relationship('Bubble', backref='topic', lazy=True, cascade="all, delete-orphan")

class Bubble(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False) # เก็บเนื้อหา HTML (ตัวหนา, สี, โค้ด, LaTeX)
    order_index = db.Column(db.Integer, default=0) # ใช้เรียงลำดับขวามือ
    topic_id = db.Column(db.Integer, db.ForeignKey('topic.id'), nullable=False)
    include_in_random = db.Column(db.Boolean, default=True)  # whether bubble participates in random selections

# ... (โค้ดคลาส Course, Topic, Bubble ด้านบนเหมือนเดิม) ...

# ==========================================
# ส่วนของระบบ TODO List (คลังเอกสาร)
# ==========================================
class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True) # รายละเอียดภารกิจ (ถ้ามี)
    status = db.Column(db.String(20), default='pending') # สถานะ: pending, completed
    
    # ความสัมพันธ์: 1 งานหลัก มีหลายงานย่อย (Subtasks)
    subtasks = db.relationship('Subtask', backref='task', lazy=True, cascade="all, delete-orphan")

class Subtask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(20), default='pending') # สถานะ: pending, completed