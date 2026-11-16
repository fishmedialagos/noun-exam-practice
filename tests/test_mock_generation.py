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

    # 4. Launch mock exam - should locate or auto-generate exam and redirect to instructions
    mock_auth = client.get('/materials/GST101/mock', follow_redirects=True)
    assert mock_auth.status_code == 200
    assert b'Instructions' in mock_auth.data or b'Examination' in mock_auth.data

def test_auto_generate_mock_questions_unit_scaling():
    """
    Verify question generator produces >= 70 questions for 2-unit courses
    and up to 100 questions for 3-unit courses.
    """
    from question_generator import generate_mock_exam_questions
    
    # Generate distinct sentences to ensure full target count is met
    sample_modules = []
    for m in range(1, 5):
        units = []
        for u in range(1, 5):
            body_parts = []
            for p in range(1, 15):
                body_parts.append(
                    f"3.{p} Essential Subject Topic {m}_{u}_{p}\n"
                    f"The specific academic discipline of study unit {m}_{u}_{p} establishes key concepts for distance learners. "
                    f"Research scholars investigate foundational theories regarding institutional administration and cognitive advancement {m}_{u}_{p}."
                )
            units.append({
                'label': f'Unit {u}',
                'title': f'Concept Foundation {m}.{u}',
                'body': '\n'.join(body_parts)
            })
        sample_modules.append({
            'label': f'Module {m}',
            'units': units
        })

    # Test 2-unit course -> target 70
    qs_70 = generate_mock_exam_questions(sample_modules, 'GST101', 'Use of English', target_count=70)
    assert len(qs_70) == 70
    assert any(q['question_type'] == 'mcq' for q in qs_70)
    assert any(q['question_type'] == 'fill' for q in qs_70)

    # Test 3-unit course -> target 100
    qs_100 = generate_mock_exam_questions(sample_modules, 'GST103', 'Computer Fundamentals', target_count=100)
    assert len(qs_100) == 100
    for q in qs_100:
        assert q.get('question_text')
        assert q.get('correct_answer')
        assert q.get('explanation')
