import os
from flask import Flask
from models import db, Monster, PlayerProfile
from routes import learning_bp
from todo_routes import todo_bp


def load_env_file(env_path='.env'):
    if not os.path.exists(env_path):
        return
    with open(env_path, 'r', encoding='utf-8') as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def seed_monsters():
    if Monster.query.count() > 0:
        return

    default_monsters = [
        {
            'name': 'Baby Slime',
            'description': 'A tiny cute slime. Questions focus on simple understanding and recall.',
            'ratio_easy': 70, 'ratio_normal': 30, 'ratio_hard': 0, 'ratio_hell': 0,
            'damage_easy': 1, 'damage_normal': 1, 'damage_hard': 2, 'damage_hell': 2,
        },
        {
            'name': 'Goblin Scout',
            'description': 'A quick goblin that tests basic application in short situations.',
            'ratio_easy': 40, 'ratio_normal': 50, 'ratio_hard': 10, 'ratio_hell': 0,
            'damage_easy': 1, 'damage_normal': 2, 'damage_hard': 3, 'damage_hell': 4,
        },
        {
            'name': 'Arcane Golem',
            'description': 'A magic construct that emphasizes concept + applied reasoning.',
            'ratio_easy': 10, 'ratio_normal': 30, 'ratio_hard': 50, 'ratio_hell': 10,
            'damage_easy': 2, 'damage_normal': 3, 'damage_hard': 5, 'damage_hell': 6,
        },
        {
            'name': 'Shadow Wyvern',
            'description': 'A ruthless predator asking deep scenario-based questions.',
            'ratio_easy': 0, 'ratio_normal': 20, 'ratio_hard': 50, 'ratio_hell': 30,
            'damage_easy': 2, 'damage_normal': 4, 'damage_hard': 6, 'damage_hell': 8,
        },
        {
            'name': 'Abyss Titan',
            'description': 'Endgame monster. The challenge is extreme and covers all advanced ideas.',
            'ratio_easy': 0, 'ratio_normal': 10, 'ratio_hard': 40, 'ratio_hell': 50,
            'damage_easy': 3, 'damage_normal': 5, 'damage_hard': 8, 'damage_hell': 10,
        },
    ]

    for m in default_monsters:
        db.session.add(Monster(**m))


load_env_file()

app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'learning.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

upload_folder = os.path.join(basedir, 'static/uploads')
os.makedirs(upload_folder, exist_ok=True)
app.config['UPLOAD_FOLDER'] = upload_folder

db.init_app(app)
app.register_blueprint(learning_bp)
app.register_blueprint(todo_bp)

with app.app_context():
    db.create_all()
    from sqlalchemy import text
    info = db.session.execute(text("PRAGMA table_info(bubble)")).fetchall()
    cols = [r[1] for r in info]
    if 'include_in_random' not in cols:
        try:
            db.session.execute(text("ALTER TABLE bubble ADD COLUMN include_in_random BOOLEAN DEFAULT 1"))
            db.session.commit()
        except Exception:
            db.session.rollback()

    if not PlayerProfile.query.first():
        db.session.add(PlayerProfile(level=1, exp_current=0, exp_total=0))

    seed_monsters()
    db.session.commit()

if __name__ == '__main__':
    app.run(debug=True, port=8080)
