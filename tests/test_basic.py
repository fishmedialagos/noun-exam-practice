import pytest
import os
import tempfile
import uuid
from app import app
from models import db, User, Exam, Question, Attempt

@pytest.fixture
def client():
    db_fd, db_path = tempfile.mkstemp()
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False

    uid = uuid.uuid4().hex[:6]
    student_uname = f'NOUN_{uid}'
    admin_uname = f'admin_{uid}'

    with app.app_context():
        db.create_all()
        admin = User(username=admin_uname, email=f'adm_{uid}@test.com', role='admin')
        admin.set_password('pass123')
        student = User(username=student_uname, matric_no=student_uname, email=f'stu_{uid}@test.com', role='student', full_name='Test Student')
        student.set_password('pass123')
        db.session.add_all([admin, student])
        db.session.commit()

        exam = Exam(
            title='CIT 101 - Intro to Computing',
            course_code='CIT101',
            faculty='Faculty of Computing',
            credit_units=3,
            duration_minutes=30,
            created_by=admin.id,
            is_published=True
        )
        db.session.add(exam)
        db.session.commit()

        q1 = Question(
            exam_id=exam.id,
            question_text='Sample Question 1?',
            question_type='mcq',
            option_a='Alpha',
            option_b='Beta',
            option_c='Gamma',
            option_d='Delta',
            correct_answer='A',
            order=1
        )
        db.session.add(q1)
        exam.total_questions = 1
        db.session.commit()

    with app.test_client() as client:
        client.test_student_username = student_uname
        client.test_admin_username = admin_uname
        yield client

    with app.app_context():
        db.session.remove()
        db.drop_all()

    os.close(db_fd)
    os.unlink(db_path)

def test_home_page_with_quote(client):
    res = client.get('/')
    assert res.status_code == 200
    assert b'Study, Focus, Achieve' in res.data
    assert b'NOW OR NEVER' in res.data
    assert b'landing_hero.png' in res.data

def test_student_login_and_no_demo_credentials_shown(client):
    res = client.get('/login')
    assert res.status_code == 200
    assert b'Student Login' in res.data
    assert b'Demo accounts (Admin/Teacher)' not in res.data
    assert b'admin123' not in res.data

def test_staff_login_portal(client):
    res = client.get('/staff/login')
    assert res.status_code == 200
    assert b'Staff Portal Login' in res.data

    # Admin can login through staff portal
    login_res = client.post('/staff/login', data={'username': client.test_admin_username, 'password': 'pass123'}, follow_redirects=True)
    assert login_res.status_code == 200
    assert b'Admin' in login_res.data

def test_exam_units_and_faculty_computing(client):
    # Log in as admin and create a 3-unit exam under Faculty of Computing
    client.post('/staff/login', data={'username': client.test_admin_username, 'password': 'pass123'}, follow_redirects=True)
    create_res = client.post('/admin/exam/create', data={
        'title': 'CMP 201 - Data Structures',
        'course_code': 'CMP201',
        'faculty': 'Faculty of Computing',
        'credit_units': 3,
        'duration_minutes': 45
    }, follow_redirects=True)
    assert create_res.status_code == 200

    with app.app_context():
        exam = Exam.query.filter_by(course_code='CMP201').first()
        assert exam is not None
        assert exam.faculty == 'Faculty of Computing'
        assert exam.credit_units == 3
