import pytest
import os
import tempfile
import uuid
from app import app
from models import db, User, Exam, Question

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

    with app.test_client() as client:
        yield client

    os.close(db_fd)
    if os.path.exists(db_path):
        os.unlink(db_path)

def test_course_mock_exam_and_summarizer_auth_gate(client):
    """
    Ensure students must be authenticated/registered to access the course summarizer
    and auto-generated mock exams.
    """
    # 1. Unauthenticated requests should redirect to login with prompt
    res_sum = client.get('/materials/summarize/GST101', follow_redirects=True)
    assert res_sum.status_code == 200
    assert b'Please register or log in' in res_sum.data or b'login' in res_sum.request.path
    
    res_mock = client.get('/materials/GST101/mock', follow_redirects=True)
    assert res_mock.status_code == 200
    assert b'Please register or log in' in res_mock.data or b'login' in res_mock.request.path

    # 2. Register student and login
    client.post('/register', data={
        'matric_no': 'NOU777777',
        'email': 'mock_student@noun.edu.ng',
        'password': 'password777',
        'full_name': 'Mock Test Student',
        'faculty': 'General Studies'
    }, follow_redirects=True)

    client.post('/login', data={
        'username': 'nou777777',
        'password': 'password777'
    }, follow_redirects=True)

    # 3. Access summarizer as authenticated student
    sum_auth = client.get('/materials/summarize/GST101')
    assert sum_auth.status_code == 200
    assert b'Module Summary' in sum_auth.data or b'Start Mock Exam' in sum_auth.data

    # 4. Seed a manually curated exam so this route test does not call a live AI API.
    with app.app_context():
        admin = User.query.filter_by(role='admin').first()
        curated_exam = Exam(
            title='GST101 Test Mock Examination',
            description='Manually prepared test exam',
            course_code='GST101', faculty='General Studies',
            credit_units=2, duration_minutes=60, total_questions=20,
            is_published=True, created_by=admin.id
        )
        db.session.add(curated_exam)
        db.session.commit()

    # 5. Launch mock exam and redirect to its instructions.
    mock_auth = client.get('/materials/GST101/mock', follow_redirects=True)
    assert mock_auth.status_code == 200
    assert b'Instructions' in mock_auth.data or b'Examination' in mock_auth.data

