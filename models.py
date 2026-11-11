from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)  # Matric No for students
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(150))
    matric_no = db.Column(db.String(50), unique=True)
    role = db.Column(db.String(20), default='student')
    faculty = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    attempts = db.relationship('Attempt', backref='student', lazy='dynamic')
    created_exams = db.relationship('Exam', backref='creator', lazy='dynamic')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def is_admin(self):
        return self.role == 'admin'
    
    def is_teacher(self):
        return self.role in ['teacher', 'admin']
    
    def __repr__(self):
        return f'<User {self.username}>'


class Exam(db.Model):
    __tablename__ = 'exams'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    course_code = db.Column(db.String(20))
    faculty = db.Column(db.String(100))
    credit_units = db.Column(db.Integer, default=2)  # 2 or 3 credit units
    duration_minutes = db.Column(db.Integer, default=60)
    total_questions = db.Column(db.Integer, default=0)
    is_published = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    questions = db.relationship('Question', backref='exam', lazy='dynamic', cascade='all, delete-orphan')
    attempts = db.relationship('Attempt', backref='exam', lazy='dynamic')
    
    def __repr__(self):
        return f'<Exam {self.title}>'


class Question(db.Model):
    __tablename__ = 'questions'
    
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey('exams.id'), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    question_type = db.Column(db.String(20), default='mcq')  # mcq or fill
    option_a = db.Column(db.String(500))
    option_b = db.Column(db.String(500))
    option_c = db.Column(db.String(500))
    option_d = db.Column(db.String(500))
    correct_answer = db.Column(db.String(200), nullable=False)
    explanation = db.Column(db.Text)
    order = db.Column(db.Integer, default=0)
    
    def __repr__(self):
        return f'<Question {self.id}>'


class Attempt(db.Model):
    __tablename__ = 'attempts'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    exam_id = db.Column(db.Integer, db.ForeignKey('exams.id'), nullable=False)
    score = db.Column(db.Integer, default=0)
    total_questions = db.Column(db.Integer, default=0)
    percentage = db.Column(db.Float, default=0.0)
    answers = db.Column(db.Text)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    time_taken_seconds = db.Column(db.Integer)
    
    def __repr__(self):
        return f'<Attempt {self.id}>'
