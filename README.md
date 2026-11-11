# NOUN Exam Mock Platform

A full-stack exam preparation platform built for **National Open University of Nigeria (NOUN)** students.

## Features

### For Students
- Free registration & login
- Browse mock exams by faculty / course code
- Timed multiple-choice exams (real exam conditions)
- Instant scoring + detailed answer review with explanations
- Personal progress history & average score tracking

### For Teachers / Admins
- Create and manage exams
- Add / delete multiple-choice questions
- Set duration, course code, faculty
- Publish or unpublish exams
- View registered students
- Role-based access (Admin / Teacher / Student)

## Default Accounts

| Role     | Username  | Password    |
|----------|-----------|-------------|
| Admin    | `admin`   | `admin123`  |
| Teacher  | `teacher1`| `teacher123`|

Students should register from the website.

## Sample Exams Included

1. **CIT 211** – Introduction to Operating Systems (Faculty of Sciences)
2. **GST 101** – Use of English and Communication Skills (Faculty of Arts)
3. **EDU 212** – Psychology of Learning (Faculty of Education)

## How to Run

```bash
cd noun_exam_platform
pip install -r requirements.txt
python app.py
```

Then open: **http://127.0.0.1:5000**

## Tech Stack

- **Backend**: Python 3 + Flask
- **Database**: SQLite (via SQLAlchemy)
- **Auth**: Flask-Login + password hashing
- **Frontend**: Bootstrap 5 (mobile-friendly)

## Project Structure

```
noun_exam_platform/
├── app.py              # Main application
├── models.py           # Database models
├── config.py           # Configuration
├── requirements.txt
├── noun_exam.db        # SQLite database (auto-created)
├── templates/
│   ├── base.html
│   ├── index.html, login.html, register.html
│   ├── student/        # Student pages
│   └── admin/          # Admin/Teacher pages
└── static/
```

## Next Possible Improvements

- PDF export of results
- More question types (True/False, Fill-in-the-blank)
- Student performance analytics charts
- Email notifications
- Bulk question import (CSV/Excel)
- Deploy to a VPS or Render/Railway

---

Built for NOUN students 🎓
```