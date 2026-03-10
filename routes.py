import os
import re
import random
import json
import html
import requests
from sqlalchemy import text
from sqlalchemy.sql.expression import func
from flask import Blueprint, render_template, request, redirect, url_for, jsonify, current_app
from werkzeug.utils import secure_filename
from models import db, Course, Topic, Bubble, GeneratedQuestion

learning_bp = Blueprint('learning', __name__, url_prefix='/learning')

QUESTION_TYPES = [
    'general_knowledge',
    'applied_analysis_calculation',
    'deep_thinking'
]

# helper to check if include_in_random column exists in DB
_cached_include_check = None


def _has_include_column():
    global _cached_include_check
    if _cached_include_check is None:
        try:
            info = db.session.execute(text("PRAGMA table_info(bubble)")).fetchall()
            exists = any(r[1] == 'include_in_random' for r in info)
            if not exists:
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
    q = Bubble.query
    if _has_include_column():
        q = q.filter(Bubble.include_in_random.is_(True))
    return q


def _html_to_text(raw_html):
    cleaned = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', raw_html or '', flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r'<br\s*/?>', '\n', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'</p\s*>', '\n', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'<[^>]+>', ' ', cleaned)
    cleaned = html.unescape(cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


def _extract_json_array(text_value):
    if not text_value:
        return []
    try:
        parsed = json.loads(text_value)
        return parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        start = text_value.find('[')
        end = text_value.rfind(']')
        if start != -1 and end != -1 and end > start:
            snippet = text_value[start:end + 1]
            try:
                parsed = json.loads(snippet)
                return parsed if isinstance(parsed, list) else []
            except json.JSONDecodeError:
                return []
    return []


def _build_random_markdown(min_courses=1, max_bubbles_per_course=3):
    courses = Course.query.join(Topic).join(Bubble)
    courses = courses.filter(Bubble.include_in_random.is_(True)).distinct().all() if _has_include_column() else courses.distinct().all()

    lines = []
    if not courses:
        return ''

    num_courses = random.randint(min(min_courses, len(courses)), len(courses))
    sampled = random.sample(courses, num_courses)

    for course in sampled:
        lines.append(f"## Course: {course.title}")
        q = _uncensored_bubble_query().join(Topic).filter(Topic.course_id == course.id)
        bubbles = q.all()
        if not bubbles:
            lines.append("_(no content)_")
            lines.append("")
            continue

        count = random.randint(1, min(max_bubbles_per_course, len(bubbles)))
        for bubble in random.sample(bubbles, count):
            lines.append(f"### Topic: {bubble.topic.name}")
            lines.append(_html_to_text(bubble.content))
            lines.append("")

    return "\n".join(lines).strip()


def _save_generated_questions(items):
    saved = []
    for q in items:
        choices = q.get('choices') or []
        if not isinstance(choices, list) or len(choices) != 4:
            continue
        answer_index = q.get('answer_index', 0)
        if not isinstance(answer_index, int) or answer_index < 0 or answer_index > 3:
            continue
        question_type = q.get('question_type', 'general_knowledge')
        if question_type not in QUESTION_TYPES:
            question_type = 'general_knowledge'

        new_q = GeneratedQuestion(
            course_id=q.get('course_id'),
            course_title=(q.get('course_title') or 'Unknown Course').strip(),
            topic_name=(q.get('topic_name') or '').strip(),
            question_type=question_type,
            question_text=(q.get('question') or '').strip(),
            choice_a=(choices[0] or '').strip(),
            choice_b=(choices[1] or '').strip(),
            choice_c=(choices[2] or '').strip(),
            choice_d=(choices[3] or '').strip(),
            answer_index=answer_index,
            explanation=(q.get('explanation') or '').strip()
        )
        if not new_q.question_text:
            continue
        db.session.add(new_q)
        saved.append(new_q)

    db.session.commit()
    return saved


def _question_to_dict(item):
    return {
        'id': item.id,
        'course_id': item.course_id,
        'course_title': item.course_title,
        'topic_name': item.topic_name,
        'question_type': item.question_type,
        'question': item.question_text,
        'choices': [item.choice_a, item.choice_b, item.choice_c, item.choice_d],
        'answer_index': item.answer_index,
        'explanation': item.explanation
    }


@learning_bp.route('/')
def index():
    courses = Course.query.all()
    categories = sorted(list(set([c.category for c in courses if c.category])))

    random_knowledge = []
    bubbles = _uncensored_bubble_query().join(Topic).join(Course).order_by(func.random()).limit(5).all()
    for bubble in bubbles:
        random_knowledge.append({
            'course_title': bubble.topic.course.title,
            'topic_name': bubble.topic.name,
            'content': bubble.content
        })

    return render_template('learning/index.html', courses=courses, categories=categories, random_knowledge=random_knowledge)


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


@learning_bp.route('/generate_markdown')
def generate_markdown():
    markdown = _build_random_markdown(min_courses=1, max_bubbles_per_course=3)
    return jsonify({'markdown': markdown})


@learning_bp.route('/api/generate_questions', methods=['POST'])
def generate_questions():
    data = request.get_json() or {}
    markdown_text = (data.get('markdown') or '').strip()
    question_count = max(3, min(int(data.get('count', 9)), 30))

    if not markdown_text:
        markdown_text = _build_random_markdown(min_courses=2, max_bubbles_per_course=4)

    if not markdown_text:
        return jsonify({'success': False, 'error': 'No markdown content available.'}), 400

    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        return jsonify({'success': False, 'error': 'OPENAI_API_KEY is not configured on the server.'}), 500

    model = os.environ.get('OPENAI_MODEL', 'gpt-4o-mini')

    prompt = f"""
You are a quiz content generator for an RPG learning battle.

TASK:
Generate exactly {question_count} multiple-choice questions from the MARKDOWN KNOWLEDGE BASE.
All text must be in English.

STRICT RULES:
1) Return ONLY a JSON array.
2) Every item must include exactly these keys:
   - course_title (string)
   - topic_name (string)
   - question_type (one of: general_knowledge, applied_analysis_calculation, deep_thinking)
   - question (string)
   - choices (array of exactly 4 strings)
   - answer_index (integer 0-3)
   - explanation (string)
3) Balance question types across the full set:
   - general_knowledge
   - applied_analysis_calculation
   - deep_thinking
4) Questions must be grounded in the markdown only.
5) Do not include markdown fences.

MARKDOWN KNOWLEDGE BASE:
{markdown_text}
""".strip()

    try:
        response = requests.post(
            'https://api.openai.com/v1/responses',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            },
            json={
                'model': model,
                'input': prompt,
                'temperature': 0.5
            },
            timeout=60
        )
        response.raise_for_status()
        result = response.json()
        output_text = result.get('output_text', '')
        questions = _extract_json_array(output_text)

        if not questions:
            return jsonify({'success': False, 'error': 'Model response was not valid JSON question array.', 'raw_output': output_text}), 502

        saved = _save_generated_questions(questions)
        return jsonify({'success': True, 'saved_count': len(saved), 'questions': [_question_to_dict(s) for s in saved]})
    except requests.RequestException as e:
        return jsonify({'success': False, 'error': f'OpenAI request failed: {e}'}), 502


@learning_bp.route('/battle')
def battle_page():
    return render_template('learning/battle.html')


@learning_bp.route('/api/battle_questions')
def battle_questions():
    count = max(3, min(request.args.get('count', 9, type=int), 30))
    all_questions = GeneratedQuestion.query.all()

    if len(all_questions) < count:
        return jsonify({'success': False, 'error': 'Not enough questions in database. Please generate questions first.'}), 400

    grouped = {qtype: [] for qtype in QUESTION_TYPES}
    for q in all_questions:
        grouped.setdefault(q.question_type, []).append(q)

    selected = []
    per_type = max(1, count // 3)
    for qtype in QUESTION_TYPES:
        pool = grouped.get(qtype, [])
        if pool:
            selected.extend(random.sample(pool, min(per_type, len(pool))))

    remaining = [q for q in all_questions if q not in selected]
    if len(selected) < count and remaining:
        selected.extend(random.sample(remaining, min(count - len(selected), len(remaining))))

    random.shuffle(selected)
    selected = selected[:count]
    return jsonify({'success': True, 'questions': [_question_to_dict(q) for q in selected]})


@learning_bp.route('/<int:course_id>')
def course_detail(course_id):
    course = Course.query.get_or_404(course_id)
    topics = Topic.query.filter_by(course_id=course.id).order_by(Topic.order_index.asc()).all()
    active_topic_id = request.args.get('topic_id', type=int)
    active_topic = None
    bubbles = []
    if topics:
        active_topic = next((t for t in topics if t.id == active_topic_id), topics[0])
        bubbles = Bubble.query.filter_by(topic_id=active_topic.id).order_by(Bubble.order_index.asc()).all()
    return render_template('learning/course.html', course=course, topics=topics, active_topic=active_topic, bubbles=bubbles)


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
    max_index = db.session.query(db.func.max(Bubble.order_index)).filter(Bubble.topic_id == topic_id).scalar()
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
