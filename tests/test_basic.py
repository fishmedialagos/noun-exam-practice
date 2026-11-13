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

def test_student_reset_password(client):
    client.post('/register', data={
        'matric_no': 'NOU999999',
        'email': 'student99@noun.edu.ng',
        'password': 'oldpassword',
        'full_name': 'Test Student',
        'faculty': 'General Studies'
    }, follow_redirects=True)
    
    res = client.post('/reset-password', data={
        'identifier': 'nou999999',
        'new_password': 'newpassword123',
        'confirm_password': 'newpassword123'
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b'Password successfully reset' in res.data
    
    login_res = client.post('/login', data={
        'username': 'nou999999',
        'password': 'newpassword123'
    }, follow_redirects=True)
    assert login_res.status_code == 200
    assert b'Welcome back' in login_res.data

def test_admin_attempts_portal(client):
    # Log in as admin
    client.post('/staff/login', data={'username': client.test_admin_username, 'password': 'pass123'}, follow_redirects=True)
    res = client.get('/admin/attempts')
    assert res.status_code == 200
    assert b'Student Attempts & Performance' in res.data

def test_course_materials_hub(client):
    res = client.get('/materials')
    assert res.status_code == 200
    assert b'NOUN Course Materials Library' in res.data
    
    # Test search filter
    search_res = client.get('/materials?search=GST')
    assert search_res.status_code == 200
    assert b'GST' in search_res.data
    
    # Test embedded in-site reader
    reader_res = client.get('/materials/download/GST101')
    assert reader_res.status_code == 200
    assert b'In-Platform Document Viewer' in reader_res.data
    
    # Test materials summarizer route requires login
    sum_anon = client.get('/materials/summarize/GST101')
    assert sum_anon.status_code == 302
    assert '/login' in sum_anon.headers.get('Location', '')

    # Logged-in user accesses summary
    client.post('/staff/login', data={'username': client.test_admin_username, 'password': 'pass123'}, follow_redirects=True)
    sum_res = client.get('/materials/summarize/GST101')
    assert sum_res.status_code == 200
    assert b'GST101' in sum_res.data
    assert b'Summary' in sum_res.data
    
    # Test direct download redirect or file response
    dl_res = client.get('/materials/download/GST101?action=download')
    assert dl_res.status_code in (200, 302)


def test_csv_upload_with_true_false_and_yes_no(client):
    import io
    client.post('/staff/login', data={'username': client.test_admin_username, 'password': 'pass123'}, follow_redirects=True)
    
    # Create test exam
    create_res = client.post('/admin/exam/create', data={
        'title': 'Test Logic Course',
        'course_code': 'LOG101',
        'faculty': 'General Studies',
        'duration_minutes': 20,
        'credit_units': 2
    }, follow_redirects=True)
    assert create_res.status_code == 200
    
    with client.application.app_context():
        from app import Exam, Question
        exam = Exam.query.filter_by(course_code='LOG101').first()
        exam_id = exam.id
        
    csv_content = """type,question,option_a,option_b,option_c,option_d,correct,explanation
tf,The sun rises from the east.,True,False,,,True,Astronomy fact
tf,Computers only understand English.,True,False,,,False,They understand binary
yes_no,Is Python an interpreted language?,,,,,Yes,Python is interpreted
mcq,Is water H2O?,,,,,True,Water formula
fill,The full meaning of RAM is __________.,,,,,Random Access Memory,Memory terminology
"""
    data = {
        'csv_file': (io.BytesIO(csv_content.encode('utf-8')), 'questions.csv')
    }
    upload_res = client.post(f'/admin/exam/{exam_id}/upload-csv', data=data, content_type='multipart/form-data', follow_redirects=True)
    assert upload_res.status_code == 200
    assert b'Successfully imported 5 questions' in upload_res.data
    
    with client.application.app_context():
        qs = Question.query.filter_by(exam_id=exam_id).all()
        assert len(qs) == 5
        tf1 = [q for q in qs if 'sun rises' in q.question_text][0]
        assert tf1.correct_answer == 'A'
        assert tf1.option_a == 'True'
        assert tf1.option_b == 'False'
        
        tf2 = [q for q in qs if 'understand English' in q.question_text][0]
        assert tf2.correct_answer == 'B'
        
        yn = [q for q in qs if 'interpreted language' in q.question_text][0]
        assert yn.correct_answer == 'A'
        assert yn.option_a == 'Yes'
        assert yn.option_b == 'No'



