import os
import random
from sqlalchemy import text
from sqlalchemy.sql.expression import func
from flask import Blueprint, render_template, request, redirect, url_for, jsonify, current_app, Response
from werkzeug.utils import secure_filename
from models import db, Course, Topic, Bubble

learning_bp = Blueprint('learning', __name__, url_prefix='/learning')

# helper to check if include_in_random column exists in DB
_cached_include_check = None

def _has_include_column():
    global _cached_include_check
    if _cached_include_check is None:
        try:
            info = db.session.execute(text("PRAGMA table_info(bubble)")).fetchall()
            exists = any(r[1] == 'include_in_random' for r in info)
            if not exists:
                # try to add column on the fly
                try:
                    db.session.execute(text("ALTER TABLE bubble ADD COLUMN include_in_random BOOLEAN DEFAULT 1"))
                    db.session.commit()
                    exists = True
                    print('runtime migration: added include_in_random')
                except Exception as e:
                    print('runtime migration failed:', e)
            _cached_include_check = exists
        except Exception as e:
            print('PRAGMA failed', e)
            _cached_include_check = False
    return _cached_include_check


def _uncensored_bubble_query():
    """Return a Bubble query that includes only content not censored in course.html."""
    q = Bubble.query
    if _has_include_column():
        q = q.filter(Bubble.include_in_random.is_(True))
    return q


@learning_bp.route('/')
def index():
    courses = Course.query.all()
    # 🟢 ดึงหมวดหมู่ทั้งหมดที่มีมาทำปุ่ม Filter (ตัดค่าซ้ำและค่าว่าง)
    categories = sorted(list(set([c.category for c in courses if c.category])))
    
    # 🎲 Logic: Random Knowledge Discovery (คงไว้)
    random_knowledge = []
    # Daily Knowledge ต้องเลือกเฉพาะ bubble ที่ไม่ถูก censor ในหน้า course.html
    bubbles = _uncensored_bubble_query().join(Topic).join(Course).order_by(func.random()).limit(5).all()
    for bubble in bubbles:
        random_knowledge.append({
            'course_title': bubble.topic.course.title,
            'topic_name': bubble.topic.name,
            'content': bubble.content
        })

    return render_template('learning/index.html', 
                           courses=courses, 
                           categories=categories, 
                           random_knowledge=random_knowledge)
# --- หน้าสร้างวิชาใหม่ ---
@learning_bp.route('/create', methods=['POST'])
def create_course():
    title = request.form.get('title')
    category = request.form.get('category')
    image_file = request.files.get('background_image')
    filename = None
    if image_file and image_file.filename != '':
        filename = secure_filename(image_file.filename)
        image_file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
    new_course = Course(title=title, category=category, background_image=filename)
    db.session.add(new_course)
    db.session.commit()
    return redirect(url_for('learning.index'))

@learning_bp.route('/update', methods=['POST'])
def update_course():
    course_id = request.form.get('id', type=int)
    course = Course.query.get_or_404(course_id)
    course.title = request.form.get('title')
    course.category = request.form.get('category')
    image_file = request.files.get('background_image')
    if image_file and image_file.filename != '':
        filename = secure_filename(image_file.filename)
        image_file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
        course.background_image = filename
    db.session.commit()
    return redirect(url_for('learning.index'))

# --- หน้าเนื้อหา (เรียงอันใหม่ไว้ล่างสุด) ---
# --- สร้าง Markdown แบบสุ่มทั้งวิชาและจำนวนเนื้อหา ---
@learning_bp.route('/generate_markdown')
def generate_markdown():
    # สร้าง markdown จากวิชาที่มีเนื้อหา uncensored เท่านั้น
    courses = Course.query.join(Topic).join(Bubble)
    courses = courses.filter(Bubble.include_in_random.is_(True)).distinct().all() if _has_include_column() else courses.distinct().all()
    lines = []
    if courses:
        # ตัดสินใจสุ่มจำนวนวิชา (อย่างน้อย 5 เมื่อมีมากพอ)
        if len(courses) >= 5:
            num_courses = random.randint(5, len(courses))
        else:
            num_courses = len(courses)
        sampled = random.sample(courses, num_courses)
        for course in sampled:
            lines.append(f"## {course.title}")
            # ดึงทุก Bubble ของวิชานั้นที่เปิดใช้งานสำหรับสุ่ม
            q = _uncensored_bubble_query().join(Topic).filter(Topic.course_id == course.id)
            bubbles = q.all()
            if bubbles:
                # สุ่มจำนวนบับเบิ้ล (1-3 หรือไม่เกินจำนวนที่มี)
                count = random.randint(1, min(3, len(bubbles)))
                for bubble in random.sample(bubbles, count):
                    lines.append(f"**Topic:** {bubble.topic.name}")
                    lines.append("")
                    lines.append(bubble.content)
                    lines.append("")
            else:
                lines.append("_(no content)_")
            lines.append("")
    markdown = "\n".join(lines)
    # ส่งกลับเป็น JSON เพื่อให้ฝั่ง client รับไปใช้งาน
    return jsonify({'markdown': markdown})

@learning_bp.route('/<int:course_id>')
def course_detail(course_id):
    course = Course.query.get_or_404(course_id)
    topics = Topic.query.filter_by(course_id=course.id).order_by(Topic.order_index.asc()).all()
    active_topic_id = request.args.get('topic_id', type=int)
    active_topic = None
    bubbles = []
    if topics:
        active_topic = next((t for t in topics if t.id == active_topic_id), topics[0])
        # เรียงตาม ID เพื่อให้อันใหม่ล่าสุดไปอยู่ล่างสุด
        bubbles = Bubble.query.filter_by(topic_id=active_topic.id).order_by(Bubble.order_index.asc()).all()
    return render_template('learning/course.html', course=course, topics=topics, active_topic=active_topic, bubbles=bubbles)

# --- API ต่างๆ ---
@learning_bp.route('/api/add_topic', methods=['POST'])
def add_topic():
    data = request.get_json()
    new_topic = Topic(name=data['name'], course_id=data['course_id'])
    db.session.add(new_topic)
    db.session.commit()
    return jsonify({'success': True})

@learning_bp.route('/api/add_bubble', methods=['POST'])
def add_bubble():
    data = request.get_json()
    topic_id = data['topic_id']
    # compute next order_index so bubble appears at end
    max_index = db.session.query(db.func.max(Bubble.order_index))\
                  .filter(Bubble.topic_id == topic_id).scalar()
    if max_index is None:
        max_index = -1
    new_bubble = Bubble(content=data['content'], topic_id=topic_id, order_index=max_index + 1)
    db.session.add(new_bubble)
    db.session.commit()
    return jsonify({'success': True})

@learning_bp.route('/api/edit_bubble/<int:bubble_id>', methods=['POST'])
def edit_bubble(bubble_id):
    bubble = Bubble.query.get_or_404(bubble_id)
    bubble.content = request.get_json()['content']
    db.session.commit()
    return jsonify({'success': True})

@learning_bp.route('/api/delete_bubble/<int:bubble_id>', methods=['DELETE'])
def delete_bubble(bubble_id):
    db.session.delete(Bubble.query.get_or_404(bubble_id))
    db.session.commit()
    return jsonify({'success': True})

@learning_bp.route('/api/delete_topic/<int:topic_id>', methods=['DELETE'])
def delete_topic(topic_id):
    db.session.delete(Topic.query.get_or_404(topic_id))
    db.session.commit()
    return jsonify({'success': True})

@learning_bp.route('/api/reorder_bubbles', methods=['POST'])

def reorder_bubbles():
    data = request.get_json()
    ids = data.get('ids', [])
    # update each bubble's order_index based on new sequence
    for idx, bid in enumerate(ids):
        bubble = Bubble.query.get(bid)
        if bubble:
            bubble.order_index = idx
    db.session.commit()
    return jsonify({'success': True})

@learning_bp.route('/api/set_bubble_status/<int:bubble_id>', methods=['POST'])
def set_bubble_status(bubble_id):
    data = request.get_json() or {}
    val = data.get('include', True)
    bubble = Bubble.query.get_or_404(bubble_id)
    bubble.include_in_random = bool(val)
    db.session.commit()
    return jsonify({'success': True, 'included': bubble.include_in_random})
