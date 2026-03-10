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


class GeneratedQuestion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=True)
    course_title = db.Column(db.String(150), nullable=False)
    topic_name = db.Column(db.String(150), nullable=True)

    question_type = db.Column(db.String(40), nullable=False, default='general_knowledge')
    question_text = db.Column(db.Text, nullable=False)

    choice_a = db.Column(db.Text, nullable=False)
    choice_b = db.Column(db.Text, nullable=False)
    choice_c = db.Column(db.Text, nullable=False)
    choice_d = db.Column(db.Text, nullable=False)

    answer_index = db.Column(db.Integer, nullable=False, default=0)
    explanation = db.Column(db.Text, nullable=True)


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
