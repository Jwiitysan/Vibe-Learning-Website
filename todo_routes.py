from flask import Blueprint, render_template, request, redirect, url_for, jsonify
from models import db, Task, Subtask

# สร้าง Blueprint สำหรับ /todo
todo_bp = Blueprint('todo', __name__, url_prefix='/todo')

# --- หน้าแรก: แสดงแฟ้มงานทั้งหมด และสรุปจำนวน ---
@todo_bp.route('/')
def index():
    tasks = Task.query.all()
    # คำนวณงานที่ยังค้างอยู่
    pending_count = sum(1 for task in tasks if task.status == 'pending')
    completed_count = len(tasks) - pending_count
    
    return render_template('todo/index.html', tasks=tasks, pending_count=pending_count, completed_count=completed_count)

# --- API: สร้างแฟ้มงานใหม่ ---
@todo_bp.route('/create', methods=['POST'])
def create_task():
    title = request.form.get('title')
    description = request.form.get('description')
    
    if title:
        new_task = Task(title=title, description=description)
        db.session.add(new_task)
        db.session.commit()
    return redirect(url_for('todo.index'))

# --- หน้ารายละเอียดงาน (Report View) ---
@todo_bp.route('/<int:task_id>')
def task_detail(task_id):
    task = Task.query.get_or_404(task_id)
    return render_template('todo/task.html', task=task)

# --- API: เพิ่มงานย่อย (Subtask) ---
@todo_bp.route('/api/add_subtask', methods=['POST'])
def add_subtask():
    data = request.get_json()
    new_subtask = Subtask(title=data['title'], task_id=data['task_id'])
    db.session.add(new_subtask)
    db.session.commit()
    return jsonify({'success': True})

# --- API: สลับสถานะงานย่อย (ติ๊กถูก/เอาออก) ---
@todo_bp.route('/api/toggle_subtask/<int:subtask_id>', methods=['POST'])
def toggle_subtask(subtask_id):
    subtask = Subtask.query.get_or_404(subtask_id)
    subtask.status = 'completed' if subtask.status == 'pending' else 'pending'
    db.session.commit()
    return jsonify({'success': True, 'status': subtask.status})
    
# --- API: สลับสถานะงานหลัก (แสตมป์ตรายาง) ---
@todo_bp.route('/api/toggle_task/<int:task_id>', methods=['POST'])
def toggle_task(task_id):
    task = Task.query.get_or_404(task_id)
    task.status = 'completed' if task.status == 'pending' else 'pending'
    db.session.commit()
    return jsonify({'success': True, 'status': task.status})

# --- API: ทำลายแฟ้มเอกสาร (ลบ Task) ---
@todo_bp.route('/api/delete_task/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    db.session.delete(task)
    db.session.commit()
    return jsonify({'success': True})