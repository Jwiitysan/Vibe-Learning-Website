import os
import re
import random
import json
import html
import uuid
import requests
from sqlalchemy import text
from sqlalchemy.sql.expression import func
from flask import Blueprint, render_template, request, redirect, url_for, jsonify, current_app
from werkzeug.utils import secure_filename
from models import db, Course, Topic, Bubble, PlayerProfile, Monster

learning_bp = Blueprint('learning', __name__, url_prefix='/learning')

BATTLE_SESSIONS = {}
MODE_CONFIG = {
    'easy': {'count': 5, 'exp': 0.5},
    'normal': {'count': 8, 'exp': 1.0},
    'hard': {'count': 10, 'exp': 2.0},
    'hell': {'count': 12, 'exp': 3.0},
}

_cached_include_check = None


def _exp_to_next_level(level):
    return 10 + (level - 1) * 5


def _grant_exp(profile, amount):
    profile.exp_total += amount
    profile.exp_current += amount
    while profile.exp_current >= _exp_to_next_level(profile.level):
        profile.exp_current -= _exp_to_next_level(profile.level)
        profile.level += 1


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
                except Exception:
                    exists = False
            _cached_include_check = exists
        except Exception:
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


def _extract_text_from_responses_payload(payload):
    if not isinstance(payload, dict):
        return ''
    output_text = payload.get('output_text')
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    texts = []
    output_items = payload.get('output') or []
    if isinstance(output_items, list):
        for item in output_items:
            if not isinstance(item, dict):
                continue
            for part in item.get('content') or []:
                if isinstance(part, dict) and isinstance(part.get('text'), str) and part.get('text').strip():
                    texts.append(part.get('text').strip())
    return "\n".join(texts)


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
            try:
                parsed = json.loads(text_value[start:end + 1])
                return parsed if isinstance(parsed, list) else []
            except json.JSONDecodeError:
                return []
    return []


def _build_random_markdown(min_courses=1, max_bubbles_per_course=3):
    courses = Course.query.join(Topic).join(Bubble)
    courses = courses.filter(Bubble.include_in_random.is_(True)).distinct().all() if _has_include_column() else courses.distinct().all()
    if not courses:
        return ''

    lines = []
    sampled = random.sample(courses, random.randint(min(min_courses, len(courses)), len(courses)))
    for course in sampled:
        lines.append(f"## Course: {course.title}")
        bubbles = _uncensored_bubble_query().join(Topic).filter(Topic.course_id == course.id).all()
        if not bubbles:
            continue
        for bubble in random.sample(bubbles, random.randint(1, min(max_bubbles_per_course, len(bubbles)))):
            lines.append(f"### Topic: {bubble.topic.name}")
            lines.append(_html_to_text(bubble.content))
            lines.append("")
    return "\n".join(lines).strip()


def _normalize_question_items(items):
    cleaned = []
    for q in items:
        if not isinstance(q, dict):
            continue
        choices = q.get('choices') or []
        if not isinstance(choices, list) or len(choices) != 4:
            continue
        answer_index = q.get('answer_index')
        if not isinstance(answer_index, int) or answer_index < 0 or answer_index > 3:
            continue
        cleaned.append({
            'course_title': (q.get('course_title') or 'Unknown Course').strip(),
            'topic_name': (q.get('topic_name') or '').strip(),
            'question': (q.get('question') or '').strip(),
            'choices': [str(c).strip() for c in choices],
            'answer_index': answer_index,
            'explanation': (q.get('explanation') or '').strip(),
        })
    return [x for x in cleaned if x['question']]


def _build_mode_instruction(mode):
    if mode == 'easy':
        return "Measure only core concept recall (remember/not remember)."
    if mode == 'normal':
        return "Ask simple practical scenarios where users can infer answers with basic application."
    if mode == 'hard':
        return "Ask concept + application in varied situations. Choices should have similar length."
    return "Ask tougher-than-hard questions with deep application and edge cases. Choices should have similar length."


@learning_bp.route('/')
def index():
    courses = Course.query.all()
    categories = sorted(list(set([c.category for c in courses if c.category])))
    monsters = Monster.query.order_by(Monster.id.asc()).all()

    profile = PlayerProfile.query.first()
    if not profile:
        profile = PlayerProfile(level=1, exp_current=0, exp_total=0)
        db.session.add(profile)
        db.session.commit()

    random_knowledge = []
    bubbles = _uncensored_bubble_query().join(Topic).join(Course).order_by(func.random()).limit(5).all()
    for bubble in bubbles:
        random_knowledge.append({'course_title': bubble.topic.course.title, 'topic_name': bubble.topic.name, 'content': bubble.content})

    return render_template(
        'learning/index.html',
        courses=courses,
        categories=categories,
        random_knowledge=random_knowledge,
        monsters=monsters,
        profile=profile,
        exp_to_next=_exp_to_next_level(profile.level)
    )


@learning_bp.route('/create', methods=['POST'])
def create_course():
    title = request.form.get('title')
    category = request.form.get('category')
    image_file = request.files.get('background_image')
    filename = None
    if image_file and image_file.filename != '':
        filename = secure_filename(image_file.filename)
        image_file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
    db.session.add(Course(title=title, category=category, background_image=filename))
    db.session.commit()
    return redirect(url_for('learning.index'))


@learning_bp.route('/update', methods=['POST'])
def update_course():
    course = Course.query.get_or_404(request.form.get('id', type=int))
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
    return jsonify({'markdown': _build_random_markdown()})


@learning_bp.route('/api/add_monster', methods=['POST'])
def add_monster():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    desc = (data.get('description') or '').strip()
    if not name or not desc:
        return jsonify({'success': False, 'error': 'name and description are required'}), 400

    m = Monster(
        name=name,
        description=desc,
        ratio_easy=int(data.get('ratio_easy', 25)),
        ratio_normal=int(data.get('ratio_normal', 25)),
        ratio_hard=int(data.get('ratio_hard', 25)),
        ratio_hell=int(data.get('ratio_hell', 25)),
        damage_easy=int(data.get('damage_easy', 1)),
        damage_normal=int(data.get('damage_normal', 2)),
        damage_hard=int(data.get('damage_hard', 4)),
        damage_hell=int(data.get('damage_hell', 6)),
    )
    db.session.add(m)
    db.session.commit()
    return jsonify({'success': True, 'monster_id': m.id})


@learning_bp.route('/api/start_battle', methods=['POST'])
def start_battle():
    data = request.get_json() or {}
    mode = (data.get('mode') or 'normal').lower()
    monster_id = data.get('monster_id', type=int) if hasattr(data, 'get') else None
    if mode not in MODE_CONFIG:
        return jsonify({'success': False, 'error': 'invalid mode'}), 400

    monster = Monster.query.get_or_404(monster_id)
    count = MODE_CONFIG[mode]['count']
    markdown_text = _build_random_markdown(min_courses=2, max_bubbles_per_course=4)
    if not markdown_text:
        return jsonify({'success': False, 'error': 'No markdown content available.'}), 400

    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        return jsonify({'success': False, 'error': 'OPENAI_API_KEY is not configured on server'}), 500

    answer_pattern = [random.randint(0, 3) for _ in range(count)]
    mode_instruction = _build_mode_instruction(mode)
    prompt = f"""
You are generating quiz questions for a monster battle.
Language: English only.
Count: {count}
Mode: {mode.upper()}
Mode guidance: {mode_instruction}

Return ONLY JSON array. No markdown, no extra text.
Each item must be:
{{
  "course_title": "...",
  "topic_name": "...",
  "question": "...",
  "choices": ["...","...","...","..."],
  "answer_index": 0,
  "explanation": "..."
}}

Use this target answer_index pattern to distribute answer positions:
{answer_pattern}
(Question 1 uses pattern[0], Question 2 uses pattern[1], ...)

Knowledge base:
{markdown_text}
""".strip()

    try:
        response = requests.post(
            'https://api.openai.com/v1/responses',
            headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
            json={'model': os.environ.get('OPENAI_MODEL', 'gpt-4o-mini'), 'input': prompt, 'temperature': 0.7},
            timeout=70,
        )
        response.raise_for_status()
        output_text = _extract_text_from_responses_payload(response.json())
        questions = _normalize_question_items(_extract_json_array(output_text))
        if len(questions) < 3:
            return jsonify({'success': False, 'error': 'Could not generate enough valid questions.'}), 502

        session_id = str(uuid.uuid4())
        BATTLE_SESSIONS[session_id] = {
            'mode': mode,
            'monster_id': monster.id,
            'monster_name': monster.name,
            'hp': 100,
            'questions': questions,
            'current': 0,
            'exp_reward': MODE_CONFIG[mode]['exp'],
        }
        return jsonify({'success': True, 'battle_url': url_for('learning.battle_page', session_id=session_id)})
    except requests.RequestException as e:
        return jsonify({'success': False, 'error': f'OpenAI request failed: {e}'}), 502


@learning_bp.route('/battle')
def battle_page():
    session_id = request.args.get('session_id', '')
    if session_id not in BATTLE_SESSIONS:
        return redirect(url_for('learning.index'))
    return render_template('learning/battle.html', session_id=session_id)


@learning_bp.route('/api/battle_state/<session_id>')
def battle_state(session_id):
    s = BATTLE_SESSIONS.get(session_id)
    if not s:
        return jsonify({'success': False, 'error': 'battle session not found'}), 404

    q = s['questions'][s['current']]
    return jsonify({
        'success': True,
        'monster_name': s['monster_name'],
        'mode': s['mode'],
        'player_hp': s['hp'],
        'progress': {'current': s['current'] + 1, 'total': len(s['questions'])},
        'question': {
            'course_title': q['course_title'],
            'topic_name': q['topic_name'],
            'question': q['question'],
            'choices': q['choices']
        }
    })


@learning_bp.route('/api/battle_answer/<session_id>', methods=['POST'])
def battle_answer(session_id):
    s = BATTLE_SESSIONS.get(session_id)
    if not s:
        return jsonify({'success': False, 'error': 'battle session not found'}), 404

    data = request.get_json() or {}
    choice = int(data.get('choice_index', -1))
    q = s['questions'][s['current']]

    if choice == q['answer_index']:
        s['current'] += 1
        if s['current'] >= len(s['questions']):
            profile = PlayerProfile.query.first()
            if not profile:
                profile = PlayerProfile(level=1, exp_current=0, exp_total=0)
                db.session.add(profile)
            _grant_exp(profile, s['exp_reward'])
            db.session.commit()
            del BATTLE_SESSIONS[session_id]
            return jsonify({'success': True, 'completed': True, 'message': f"Victory! +{s['exp_reward']} EXP"})

        return jsonify({'success': True, 'correct': True, 'completed': False, 'message': 'Correct! Go next.'})

    monster = Monster.query.get(s['monster_id'])
    dmg = getattr(monster, f"damage_{s['mode']}", 2) if monster else 2
    s['hp'] = max(0, s['hp'] - dmg)
    if s['hp'] <= 0:
        del BATTLE_SESSIONS[session_id]
        return jsonify({'success': True, 'dead': True, 'redirect_url': url_for('learning.index'), 'message': 'You were defeated.'})

    return jsonify({
        'success': True,
        'correct': False,
        'player_hp': s['hp'],
        'message': f"Wrong! -{dmg} HP. Try again.",
        'answer_index': q['answer_index']
    })


@learning_bp.route('/<int:course_id>')
def course_detail(course_id):
    course = Course.query.get_or_404(course_id)
    topics = Topic.query.filter_by(course_id=course.id).order_by(Topic.order_index.asc()).all()
    active_topic_id = request.args.get('topic_id', type=int)
    active_topic = next((t for t in topics if t.id == active_topic_id), topics[0]) if topics else None
    bubbles = Bubble.query.filter_by(topic_id=active_topic.id).order_by(Bubble.order_index.asc()).all() if active_topic else []
    return render_template('learning/course.html', course=course, topics=topics, active_topic=active_topic, bubbles=bubbles)


@learning_bp.route('/api/add_topic', methods=['POST'])
def add_topic():
    data = request.get_json()
    db.session.add(Topic(name=data['name'], course_id=data['course_id']))
    db.session.commit()
    return jsonify({'success': True})


@learning_bp.route('/api/add_bubble', methods=['POST'])
def add_bubble():
    data = request.get_json()
    topic_id = data['topic_id']
    max_index = db.session.query(db.func.max(Bubble.order_index)).filter(Bubble.topic_id == topic_id).scalar()
    max_index = -1 if max_index is None else max_index
    db.session.add(Bubble(content=data['content'], topic_id=topic_id, order_index=max_index + 1))
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
    ids = (request.get_json() or {}).get('ids', [])
    for idx, bid in enumerate(ids):
        bubble = Bubble.query.get(bid)
        if bubble:
            bubble.order_index = idx
    db.session.commit()
    return jsonify({'success': True})


@learning_bp.route('/api/set_bubble_status/<int:bubble_id>', methods=['POST'])
def set_bubble_status(bubble_id):
    val = (request.get_json() or {}).get('include', True)
    bubble = Bubble.query.get_or_404(bubble_id)
    bubble.include_in_random = bool(val)
    db.session.commit()
    return jsonify({'success': True, 'included': bubble.include_in_random})
