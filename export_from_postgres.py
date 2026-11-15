"""
Export all exams and questions from remote PostgreSQL into courses_data.json and noun_exam.db
Usage:
    python export_from_postgres.py "postgresql://user:pass@host/dbname"
Or set DATABASE_URL environment variable and run:
    python export_from_postgres.py
"""
import os
import sys
import json
import sqlite3

db_url = sys.argv[1] if len(sys.argv) > 1 else os.environ.get('DATABASE_URL')

if not db_url:
    print("Error: Please provide your PostgreSQL database URL from Render.")
    print("Example: python export_from_postgres.py 'postgresql://noun_user:xxxx@xxxx.oregon-postgres.render.com/noun_db'")
    sys.exit(1)

# Normalize URL
if db_url.startswith('postgres://'):
    db_url = db_url.replace('postgres://', 'postgresql://', 1)

try:
    import psycopg2
except ImportError:
    print("Installing psycopg2-binary...")
    os.system("pip install psycopg2-binary")
    import psycopg2

print("Connecting to Render PostgreSQL...")
conn = psycopg2.connect(db_url)
cur = conn.cursor()

# Fetch all exams
cur.execute("""
    SELECT id, title, description, course_code, faculty, credit_units, duration_minutes, total_questions, is_published, created_by 
    FROM exams ORDER BY id;
""")
exams = cur.fetchall()

# Fetch all questions
cur.execute("""
    SELECT id, exam_id, question_text, question_type, option_a, option_b, option_c, option_d, correct_answer, explanation, "order" 
    FROM questions ORDER BY id;
""")
questions = cur.fetchall()

print(f"✓ Found {len(exams)} courses and {len(questions)} questions in PostgreSQL!")

# Build JSON structure
data = {
    'exams': [
        {
            'id': e[0], 'title': e[1], 'description': e[2], 'course_code': e[3],
            'faculty': e[4], 'credit_units': e[5], 'duration_minutes': e[6],
            'total_questions': e[7], 'is_published': bool(e[8])
        } for e in exams
    ],
    'questions': [
        {
            'exam_id': q[1], 'question_text': q[2], 'question_type': q[3],
            'option_a': q[4], 'option_b': q[5], 'option_c': q[6], 'option_d': q[7],
            'correct_answer': q[8], 'explanation': q[9], 'order': q[10]
        } for q in questions
    ]
}

# Save courses_data.json
json_path = os.path.join(os.path.dirname(__file__), 'courses_data.json')
with open(json_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
print(f"✓ Successfully wrote {json_path}")

# Rebuild local SQLite noun_exam.db
sqlite_path = os.path.join(os.path.dirname(__file__), 'noun_exam.db')
if os.path.exists(sqlite_path):
    os.remove(sqlite_path)

s_conn = sqlite3.connect(sqlite_path)
s_cur = s_conn.cursor()

s_cur.execute("""
CREATE TABLE IF NOT EXISTS exams (
    id INTEGER PRIMARY KEY,
    title VARCHAR(120) NOT NULL,
    description TEXT,
    course_code VARCHAR(20),
    faculty VARCHAR(100),
    credit_units INTEGER DEFAULT 2,
    duration_minutes INTEGER DEFAULT 30,
    total_questions INTEGER DEFAULT 0,
    is_published BOOLEAN DEFAULT 1,
    created_by INTEGER
);
""")

s_cur.execute("""
CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY,
    exam_id INTEGER NOT NULL,
    question_text TEXT NOT NULL,
    question_type VARCHAR(20) DEFAULT 'mcq',
    option_a TEXT,
    option_b TEXT,
    option_c TEXT,
    option_d TEXT,
    correct_answer VARCHAR(10),
    explanation TEXT,
    [order] INTEGER DEFAULT 1
);
""")

for e in exams:
    s_cur.execute("""
        INSERT INTO exams (id, title, description, course_code, faculty, credit_units, duration_minutes, total_questions, is_published, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, e)

for q in questions:
    s_cur.execute("""
        INSERT INTO questions (id, exam_id, question_text, question_type, option_a, option_b, option_c, option_d, correct_answer, explanation, [order])
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, q)

s_conn.commit()
s_conn.close()
conn.close()

print(f"✓ Successfully created {sqlite_path} with all {len(exams)} courses and {len(questions)} questions!")
print("\nDone! Your local environment now has all courses matching Render.")
