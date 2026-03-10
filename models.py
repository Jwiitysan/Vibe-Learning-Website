from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    background_image = db.Column(db.String(255), nullable=True)
    topics = db.relationship('Topic', backref='course', lazy=True, cascade="all, delete-orphan")


class Topic(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    order_index = db.Column(db.Integer, default=0)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    bubbles = db.relationship('Bubble', backref='topic', lazy=True, cascade="all, delete-orphan")


class Bubble(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    order_index = db.Column(db.Integer, default=0)
    topic_id = db.Column(db.Integer, db.ForeignKey('topic.id'), nullable=False)
    include_in_random = db.Column(db.Boolean, default=True)


class PlayerProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    level = db.Column(db.Integer, default=1, nullable=False)
    exp_current = db.Column(db.Float, default=0.0, nullable=False)
    exp_total = db.Column(db.Float, default=0.0, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Monster(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=False)

    ratio_easy = db.Column(db.Integer, default=25, nullable=False)
    ratio_normal = db.Column(db.Integer, default=25, nullable=False)
    ratio_hard = db.Column(db.Integer, default=25, nullable=False)
    ratio_hell = db.Column(db.Integer, default=25, nullable=False)

    damage_easy = db.Column(db.Integer, default=1, nullable=False)
    damage_normal = db.Column(db.Integer, default=2, nullable=False)
    damage_hard = db.Column(db.Integer, default=4, nullable=False)
    damage_hell = db.Column(db.Integer, default=6, nullable=False)


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='pending')
    subtasks = db.relationship('Subtask', backref='task', lazy=True, cascade="all, delete-orphan")


class Subtask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(20), default='pending')
