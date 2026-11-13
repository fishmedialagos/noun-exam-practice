from flask import Flask, render_template, redirect, url_for, flash, request, jsonify, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from datetime import datetime, timedelta
import json
import os
import csv
import io
import re

from config import Config
from models import db, User, Exam, Question, Attempt

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'warning'


@app.template_filter('safe_bold')
def safe_bold_filter(text):
    """Safely render **markdown bold** text into <strong> tags without exposing XSS."""
    if not text:
        return ''
    import markupsafe
    escaped = markupsafe.escape(str(text))
    rendered = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', str(escaped))
    return markupsafe.Markup(rendered)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/sync-courses')
@login_required
def trigger_sync():
    """Manual sync route for admin to refresh all 8 courses and 362 questions anytime."""
    if not current_user.is_teacher():
        flash('Access denied.', 'danger')
        return redirect(url_for('student_dashboard'))
    
    admin = User.query.filter_by(role='admin').first() or current_user
    json_file = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'courses_data.json')
    if not os.path.exists(json_file):
        flash('courses_data.json file not found on server.', 'danger')
        return redirect(url_for('admin_exams'))
        
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            seed_data = json.load(f)
            
        id_map = {}
        added_exams = 0
        for e in seed_data.get('exams', []):
            ex = Exam.query.filter_by(course_code=e['course_code'], title=e['title']).first()
            if not ex:
                ex = Exam(
                    title=e['title'],
                    description=e.get('description', ''),
                    course_code=e.get('course_code', ''),
                    faculty=e.get('faculty', 'General Studies'),
                    credit_units=e.get('credit_units', 2),
                    duration_minutes=e.get('duration_minutes', 30),
                    total_questions=e.get('total_questions', 0),
                    is_published=e.get('is_published', True),
                    created_by=admin.id
                )
                db.session.add(ex)
                db.session.flush()
                added_exams += 1
            id_map[e['id']] = ex.id
            
        db.session.commit()
        
        added_questions = 0
        for q in seed_data.get('questions', []):
            target_id = id_map.get(q['exam_id'])
            if target_id:
                existing_q = Question.query.filter_by(exam_id=target_id, question_text=q['question_text']).first()
                if not existing_q:
                    qn = Question(
                        exam_id=target_id,
                        question_text=q['question_text'],
                        question_type=q.get('question_type', 'mcq'),
                        option_a=q.get('option_a'),
                        option_b=q.get('option_b'),
                        option_c=q.get('option_c'),
                        option_d=q.get('option_d'),
                        correct_answer=q.get('correct_answer'),
                        explanation=q.get('explanation'),
                        order=q.get('order', 1)
                    )
                    db.session.add(qn)
                    added_questions += 1
                    
        db.session.commit()
        for real_id in set(id_map.values()):
            ex_obj = db.session.get(Exam, real_id)
            if ex_obj:
                ex_obj.total_questions = ex_obj.questions.count()
        db.session.commit()
        
        flash(f'Synchronization successful! Total courses verified: {Exam.query.count()}. Added {added_exams} new courses & {added_questions} questions.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error during sync: {e}', 'danger')
        
    return redirect(url_for('admin_exams'))


# ==================== AUTH ROUTES ====================

@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.is_teacher():
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('student_dashboard'))
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        matric_no = request.form.get('matric_no', '').strip().upper()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        full_name = request.form.get('full_name', '').strip()
        faculty = request.form.get('faculty', '').strip()
        
        if not all([matric_no, email, password, full_name]):
            flash('Please fill in all required fields (including Matric Number).', 'danger')
            return redirect(url_for('register'))
        
        if User.query.filter_by(username=matric_no).first() or User.query.filter_by(matric_no=matric_no).first():
            flash('This Matric Number is already registered.', 'danger')
            return redirect(url_for('register'))
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return redirect(url_for('register'))
        
        user = User(
            username=matric_no,          # Matric number is the username
            matric_no=matric_no,
            email=email,
            full_name=full_name,
            faculty=faculty,
            role='student'
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! Login with your Matric Number and password.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        raw_user = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        # Match case-insensitively on username, matric_no, or email
        user = User.query.filter(
            (db.func.lower(User.username) == raw_user.lower()) |
            (db.func.lower(User.matric_no) == raw_user.lower()) |
            (db.func.lower(User.email) == raw_user.lower())
        ).first()
        
        if user and user.check_password(password):
            login_user(user, remember=True)
            flash(f'Welcome back, {user.full_name or user.username}!', 'success')
            
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            
            if user.is_teacher():
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('student_dashboard'))
        
        flash('Invalid Matric Number (or email) or password.', 'danger')
    
    return render_template('login.html')


@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip()
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        if not identifier or not new_password:
            flash('Please provide your Matric Number (or Email) and a new password.', 'danger')
            return redirect(url_for('reset_password'))
            
        if new_password != confirm_password:
            flash('Passwords do not match. Please try again.', 'danger')
            return redirect(url_for('reset_password'))
            
        if len(new_password) < 4:
            flash('Password must be at least 4 characters long.', 'danger')
            return redirect(url_for('reset_password'))
            
        user = User.query.filter(
            (db.func.lower(User.matric_no) == identifier.lower()) |
            (db.func.lower(User.username) == identifier.lower()) |
            (db.func.lower(User.email) == identifier.lower())
        ).first()
        
        if not user:
            flash('No account found with that Matric Number or Email.', 'danger')
            return redirect(url_for('reset_password'))
            
        user.set_password(new_password)
        db.session.commit()
        
        flash('Password successfully reset! You can now log in with your new password.', 'success')
        return redirect(url_for('login'))
        
    return render_template('reset_password.html')


@app.route('/staff/login', methods=['GET', 'POST'])
def staff_login():
    if current_user.is_authenticated:
        if current_user.is_teacher():
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('student_dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            if not user.is_teacher():
                flash('Access denied. This portal is for Admin and Teachers only. Students should use Student Login.', 'warning')
                return render_template('staff_login.html')
            
            login_user(user, remember=True)
            flash(f'Welcome back, {user.full_name or user.username}!', 'success')
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('admin_dashboard'))
        
        flash('Invalid staff credentials.', 'danger')
    
    return render_template('staff_login.html')


@app.route('/logout')
@login_required
def logout():
    session.clear()
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))


# ==================== COURSE MATERIALS (E-COURSEWARE) ====================

@app.route('/materials')
def course_materials():
    faculty = request.args.get('faculty', '').strip()
    search = request.args.get('search', '').strip().lower()
    
    json_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'timetable_courses.json')
    courses = []
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                courses = json.load(f)
        except Exception:
            courses = []
            
    # Filter
    filtered = []
    for c in courses:
        if faculty and c.get('faculty') != faculty:
            continue
        if search:
            code_match = search in c.get('course_code', '').lower()
            title_match = search in c.get('title', '').lower()
            if not (code_match or title_match):
                continue
        filtered.append(c)
        
    faculties = sorted(list(set(c.get('faculty') for c in courses if c.get('faculty'))))
    
    return render_template('materials/index.html', 
                           courses=filtered[:100], 
                           total_count=len(filtered),
                           faculties=faculties, 
                           current_faculty=faculty,
                           search_query=search)




def _resolve_material(course_code):
    """Return (code, title, local_path_or_None, url_list). Includes nounupdate.com."""
    code = course_code.replace(' ', '').upper()
    upload_dir = os.path.join(app.root_path, 'static', 'materials')
    os.makedirs(upload_dir, exist_ok=True)
    local_pdf = os.path.join(upload_dir, f"{code}.pdf")
    local_path = local_pdf if os.path.exists(local_pdf) else None

    cache_dir = os.path.join(app.root_path, 'static', 'materials_cache')
    os.makedirs(cache_dir, exist_ok=True)
    cache_pdf = os.path.join(cache_dir, f"{code}.pdf")
    if not local_path and os.path.exists(cache_pdf) and os.path.getsize(cache_pdf) > 1000:
        local_path = cache_pdf

    json_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'timetable_courses.json')
    matched_url = None
    course_title = code
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                c_list = json.load(f)
                for item in c_list:
                    if item.get('course_code') == code:
                        matched_url = item.get('pdf_url')
                        course_title = item.get('title', code)
                        break
        except Exception:
            pass

    # Priority order: local/cache handled above; remote candidates:
    # 1) nounupdate.com direct file  2) timetable url  3) official NOUN patterns
    candidates = [
        f"https://nounupdate.com/file-course-materials/{code}.pdf",
        f"https://nounupdate.com/file-course-materials/{code}_0.pdf",
    ]
    if matched_url:
        candidates.append(matched_url)
    candidates.extend([
        f"https://nou.edu.ng/coursewarecontent/{code}.pdf",
        f"https://nou.edu.ng/coursewarecontent/{code}_0.pdf",
        f"https://www.nou.edu.ng/coursewarecontent/{code}.pdf",
        f"https://www.nou.edu.ng/coursewarecontent/{code}_0.pdf",
    ])
    seen, urls = set(), []
    for u in candidates:
        if u and u not in seen:
            seen.add(u)
            urls.append(u)
    return code, course_title, local_path, urls


def _discover_nounupdate_pdf(code):
    """Scrape nounupdate course page for a downloadable PDF link."""
    import requests as http_requests
    page_url = f"https://nounupdate.com/courses/{code}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml',
    }
    try:
        r = http_requests.get(page_url, timeout=(3.0, 7.0), headers=headers, allow_redirects=True)
        if r.status_code != 200:
            return None, None
        html = r.text
        # Title
        title = code
        mt = re.search(r'<h1[^>]*>\s*' + re.escape(code) + r'\s*[—\-–:]\s*([^<]+)', html, re.I)
        if mt:
            title = mt.group(1).strip()
        else:
            mt2 = re.search(r'<title>\s*' + re.escape(code) + r'\s+([^|<]+)', html, re.I)
            if mt2:
                title = mt2.group(1).replace('Course Material', '').strip()
        # PDF links
        links = re.findall(r'href=["\']([^"\']*?(?:file-course-materials/[^"\']+\.pdf|coursewarecontent/[^"\']+\.pdf)[^"\']*)["\']', html, re.I)
        links += re.findall(r'href=["\']([^"\']+\.pdf)["\']', html, re.I)
        abs_links = []
        for link in links:
            if link.startswith('//'):
                link = 'https:' + link
            elif link.startswith('/'):
                link = 'https://nounupdate.com' + link
            if link.lower().endswith('.pdf') and link not in abs_links:
                abs_links.append(link)
        return (abs_links[0] if abs_links else None), title
    except Exception as e:
        app.logger.warning('nounupdate discover failed for %s: %s', code, e)
        return None, None


def _fetch_and_cache_pdf(code, urls):
    """Download first working PDF and cache locally. Also tries nounupdate page scrape."""
    import time
    import requests as http_requests
    cache_dir = os.path.join(app.root_path, 'static', 'materials_cache')
    os.makedirs(cache_dir, exist_ok=True)
    cache_pdf = os.path.join(cache_dir, f"{code}.pdf")
    if os.path.exists(cache_pdf) and os.path.getsize(cache_pdf) > 1000:
        return cache_pdf

    # Live discover from nounupdate course page
    discovered, _ = _discover_nounupdate_pdf(code)
    all_urls = []
    if discovered:
        all_urls.append(discovered)
    for u in urls:
        if u not in all_urls:
            all_urls.append(u)

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/pdf,*/*',
    }
    start_t = time.time()
    for url in all_urls:
        # Enforce 20s overall timeout to prevent Render 60s HTTP 502 Bad Gateway
        if time.time() - start_t > 20:
            app.logger.warning('PDF fetch overall timeout exceeded for %s', code)
            break
        try:
            r = http_requests.get(url, timeout=(3.5, 9.0), stream=True, headers=headers, allow_redirects=True)
            ctype = (r.headers.get('Content-Type') or '').lower()
            if r.status_code != 200:
                continue
            if 'pdf' not in ctype and 'octet' not in ctype and not url.lower().endswith('.pdf'):
                continue
            tmp = cache_pdf + '.part'
            size = 0
            with open(tmp, 'wb') as f:
                for chunk in r.iter_content(chunk_size=64 * 1024):
                    if chunk:
                        f.write(chunk)
                        size += len(chunk)
            if size < 1500:
                try:
                    os.remove(tmp)
                except OSError:
                    pass
                continue
            os.replace(tmp, cache_pdf)
            return cache_pdf
        except Exception as e:
            app.logger.warning('PDF fetch failed %s from %s: %s', code, url, e)
            continue
    return None


@app.route('/materials/proxy/<course_code>')
def proxy_material(course_code):
    """Serve PDF same-origin so on-page viewer works for (almost) all courses."""
    from flask import send_file, abort
    code, title, local_path, urls = _resolve_material(course_code)
    path = local_path or _fetch_and_cache_pdf(code, urls)
    if path and os.path.exists(path):
        return send_file(path, mimetype='application/pdf', as_attachment=False,
                         download_name=f'{code}.pdf', max_age=3600)
    # Return 404 so reader.html shows in-page friendly status instead of redirecting to broken external 404
    abort(404)


@app.route('/materials/download/<course_code>')
def download_material(course_code):
    """View online (in-platform) or force download."""
    from flask import send_file
    code, course_title, local_path, urls = _resolve_material(course_code)
    # Enrich title from nounupdate when possible
    if course_title == code:
        _, nu_title = _discover_nounupdate_pdf(code)
        if nu_title:
            course_title = nu_title
    action = request.args.get('action', 'view')
    if action == 'download':
        path = local_path or _fetch_and_cache_pdf(code, urls)
        if path and os.path.exists(path):
            return send_file(path, mimetype='application/pdf', as_attachment=True,
                             download_name=f'{code}.pdf')
        flash(f'Material for {code} is currently unavailable for direct download.', 'warning')
        return redirect(url_for('download_material', course_code=code))

    proxy_url = url_for('proxy_material', course_code=code)
    download_url = url_for('download_material', course_code=code, action='download')
    return render_template('materials/reader.html',
                           course_code=code,
                           course_title=course_title,
                           proxy_url=proxy_url,
                           download_url=download_url,
                           pdf_url=urls[0] if urls else '')


def _extract_pdf_text(path, max_pages=200):
    """Extract text page by page (extended coverage)."""
    try:
        from pypdf import PdfReader
    except ImportError:
        return [], 'PDF engine not installed on server (pypdf).'
    try:
        reader = PdfReader(path)
        pages = []
        n = min(len(reader.pages), max_pages)
        for i in range(n):
            try:
                t = reader.pages[i].extract_text() or ''
            except Exception:
                t = ''
            pages.append(t)
        return pages, None
    except Exception as e:
        return [], f'Could not read PDF text: {e}'


def _split_modules_units(full_text):
    """Robust split of NOUN materials into modules and units."""
    text = re.sub(r'\r', '', full_text)

    word_to_num = {
        'one': '1', 'two': '2', 'three': '3', 'four': '4', 'five': '5',
        'six': '6', 'seven': '7', 'eight': '8', 'nine': '9', 'ten': '10',
        'eleven': '11', 'twelve': '12', 'thirteen': '13', 'fourteen': '14', 'fifteen': '15',
        'sixteen': '16', 'seventeen': '17', 'eighteen': '18', 'nineteen': '19', 'twenty': '20',
        'twenty-one': '21', 'twenty-two': '22', 'twenty-three': '23', 'twenty-four': '24', 'twenty-five': '25',
        'i': '1', 'ii': '2', 'iii': '3', 'iv': '4', 'v': '5',
        'vi': '6', 'vii': '7', 'viii': '8', 'ix': '9', 'x': '10',
        'xi': '11', 'xii': '12', 'xiii': '13', 'xiv': '14', 'xv': '15',
        'xvi': '16', 'xvii': '17', 'xviii': '18', 'xix': '19', 'xx': '20',
    }
    num_words_pat = '|'.join(word_to_num.keys())

    module_pat = re.compile(
        rf'(?im)^(?:module|mod\.?)\s*([0-9]{{1,2}}|{num_words_pat})\b(?:\s*[:\-–—.]\s*|\s+)?(.*)$'
    )
    unit_pat = re.compile(
        rf'(?im)^(?:unit|unt\.?)\s*([0-9]{{1,2}}|{num_words_pat})\b(?:\s*[:\-–—.]\s*|\s+)?(.*)$'
    )

    def is_toc_line(line):
        """Detect if line is a Table of Contents entry (dot leaders or page numbers)."""
        if re.search(r'[\.·•]{3,}', line):
            return True
        if re.search(r'\s*\.{2,}\s*\d+\s*$', line):
            return True
        if re.search(r'(?i)\b(?:page|pg\.?)\s*\d+$', line):
            return True
        return False

    lines = text.split('\n')
    modules = []
    current_mod = None
    current_unit = None
    buf = []

    def flush_unit():
        nonlocal current_unit, buf
        if current_unit is not None:
            current_unit['body'] = '\n'.join(buf).strip()
            current_mod['units'].append(current_unit)
            current_unit = None
            buf = []

    def flush_mod():
        nonlocal current_mod, buf
        flush_unit()
        if current_mod is not None:
            if buf:
                current_mod['body'] = ((current_mod.get('body') or '') + '\n' + '\n'.join(buf)).strip()
            modules.append(current_mod)
            current_mod = None
            buf = []

    i = 0
    total_lines = len(lines)
    while i < total_lines:
        raw = lines[i].strip()
        i += 1
        if not raw:
            buf.append('')
            continue

        if is_toc_line(raw):
            continue

        clean = re.sub(r'^[\d\W]+', '', raw).strip() or raw

        # Check Module
        mm = module_pat.match(raw) or module_pat.match(clean)
        if mm:
            raw_num = mm.group(1).lower()
            num = word_to_num.get(raw_num, mm.group(1))
            title = (mm.group(2) or '').strip()
            if not title and i < total_lines:
                next_line = lines[i].strip()
                if next_line and not is_toc_line(next_line) and not module_pat.match(next_line) and not unit_pat.match(next_line) and len(next_line) < 120:
                    title = next_line
                    i += 1

            flush_mod()
            current_mod = {
                'label': f'Module {num}',
                'title': title or f'Module {num}',
                'units': [],
                'body': '',
            }
            buf = []
            continue

        # Check Unit
        um = unit_pat.match(raw) or unit_pat.match(clean)
        if um:
            raw_num = um.group(1).lower()
            num = word_to_num.get(raw_num, um.group(1))
            title = (um.group(2) or '').strip()
            if not title and i < total_lines:
                next_line = lines[i].strip()
                if next_line and not is_toc_line(next_line) and not module_pat.match(next_line) and not unit_pat.match(next_line) and len(next_line) < 120:
                    title = next_line
                    i += 1

            if current_mod is None:
                current_mod = {
                    'label': 'Module 1',
                    'title': 'General Course Content',
                    'units': [],
                    'body': '',
                }

            flush_unit()
            current_unit = {
                'label': f'Unit {num}',
                'title': title or f'Unit {num}',
                'body': '',
            }
            buf = []
            continue

        buf.append(raw)

    flush_mod()

    # Deduplicate modules: keep the instance of each Module that has the richest unit content
    by_label = {}
    for m in modules:
        label = m['label']
        # Clean title from TOC dot leaders or page numbers
        m['title'] = re.sub(r'[\.·•]{2,}.*$', '', m.get('title', '')).strip() or m.get('title', '')

        valid_units = []
        seen_unit_labels = {}
        for u in m.get('units', []):
            u['title'] = re.sub(r'[\.·•]{2,}.*$', '', u.get('title', '')).strip() or u.get('title', '')
            u_label = u['label']
            u_len = len(u.get('body', ''))
            if u_label in seen_unit_labels:
                prev_idx = seen_unit_labels[u_label]
                if u_len > len(valid_units[prev_idx].get('body', '')):
                    valid_units[prev_idx] = u
            else:
                if u_len > 40 or u['title'] != u_label:
                    seen_unit_labels[u_label] = len(valid_units)
                    valid_units.append(u)
        m['units'] = valid_units

        total_substantive = len(m.get('body', '')) + sum(len(u.get('body', '')) for u in valid_units)
        if total_substantive < 100:
            continue

        if label not in by_label:
            by_label[label] = m
        else:
            prev_m = by_label[label]
            prev_len = len(prev_m.get('body', '')) + sum(len(u.get('body', '')) for u in prev_m.get('units', []))
            if total_substantive > prev_len:
                by_label[label] = m

    def mod_sort_key(mod):
        m = re.search(r'\d+', mod.get('label', ''))
        return int(m.group()) if m else 999

    return sorted(by_label.values(), key=mod_sort_key)


def _normalize_key_point(p):
    """Normalize a keypoint into a structured dict with 'concept' and 'explanation'."""
    if isinstance(p, dict):
        concept = str(p.get('concept') or p.get('topic') or p.get('title') or p.get('term') or '').strip()
        explanation = str(p.get('explanation') or p.get('detail') or p.get('desc') or p.get('definition') or '').strip()
        if not concept and explanation:
            return _normalize_key_point(explanation)
        return {'concept': concept or 'Key Concept', 'explanation': explanation}

    s = str(p or '').strip()
    s = re.sub(r'^(?:[-*•]|\d+[\.\)])\s*', '', s).strip()
    # Match "**Concept**: Explanation" or "**Concept** - Explanation"
    m = re.match(r'^\*{0,2}(.+?)\*{0,2}\s*[:\-–—]\s*(.+)$', s)
    if m:
        c = m.group(1).replace('*', '').strip()
        e = m.group(2).strip()
        if len(c) <= 65 and len(e) > 5:
            return {'concept': c, 'explanation': e}

    # Split on first sentence if short
    parts = re.split(r'(?<=[\.\!\?])\s+', s, maxsplit=1)
    if len(parts) == 2 and len(parts[0]) <= 80:
        return {'concept': parts[0].replace('*', '').strip(), 'explanation': parts[1].strip()}

    words = s.split()
    if len(words) > 5:
        return {'concept': ' '.join(words[:4]).strip('.,:- '), 'explanation': s}
    return {'concept': 'Exam Takeaway', 'explanation': s}


def _clean_sentence_for_point(s):
    """Format concepts and explanations for study notes."""
    s = s.strip()
    s = re.sub(r'[\uf000-\uf0ff\ufb00-\ufb4f•·\u2022]+', ', ', s)
    s = re.sub(r'\s*,\s*', ', ', s)
    s = re.sub(r':\s*,', ':', s)
    s = re.sub(r'^(?:[0-9\.\)\-\*•]+\s*)+', '', s).strip()
    s = re.sub(r'^(?:[A-Z][A-Za-z0-9\s\-]{2,30}\?\s+)', '', s).strip()

    m = re.match(
        r'^([A-Z][A-Za-z0-9\s\-]{2,35}?)\s+(is defined as|refers to|is the study of|is a form of|is known as|means|is)\s+(.+)$',
        s, re.IGNORECASE
    )
    if m:
        term = m.group(1).strip()
        verb = m.group(2).strip()
        rest = m.group(3).strip()
        return {'concept': term, 'explanation': f"{term} {verb} {rest}"}

    m2 = re.match(
        r'^([A-Za-z0-9\s\-]{3,35})\s+(can (?:therefore )?be divided into|is divided into|consists of|comprises of|includes)\s+(.+)$',
        s, re.IGNORECASE
    )
    if m2:
        term = m2.group(1).strip().title()
        verb = m2.group(2).strip()
        rest = m2.group(3).strip()
        return {'concept': term, 'explanation': f"{term} {verb} {rest}"}

    return _normalize_key_point(s)


def _summarize_block(text, max_points=7, max_chars=1200):
    """High-yield extractive summary extracting keypoints and definitions."""
    if not text:
        return '', [], []

    # Filter out boilerplate, running headers, and noise lines
    lines = []
    for l in text.split('\n'):
        l_str = l.strip()
        if not l_str:
            continue
        if re.search(r'(?i)\b(?:self-assessment|tma|exercise|tutor-marked|fig\.?|table|www\.|http|copyright)\b', l_str):
            continue
        # Running header / code lines
        if re.match(r'^(?:[A-Z]{2,4}\s*\d{2,3})\b', l_str, re.IGNORECASE):
            continue
        if re.match(r'^\d{1,4}$', l_str):
            continue
        lines.append(l_str)
    cleaned_text = ' '.join(lines)
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()

    parts = re.split(r'(?<=[\.\!\?])\s+', cleaned_text)
    scored = []
    key_terms = []

    for s in parts:
        s = s.strip()
        if len(s) < 35 or len(s) > 380:
            continue
        # Skip blanks / underscores
        if re.search(r'_{2,}', s):
            continue
        low = s.lower()
        if re.search(r'(?i)\b(in this unit|in this module|you will learn|we shall discuss|turn to|see above|as mentioned earlier|you are following me|welcome to this unit|dear student)\b', low):
            continue
        if re.search(r'(?i)\b(objectives|at the end of this unit|you should be able to)\b', low):
            continue

        score = 0
        is_def = False

        # Definition check
        for kw in (' is defined as ', ' refers to ', ' is the study of ', ' means ', ' is known as ', ' is a concept '):
            if kw in low:
                score += 4
                is_def = True

        # Taxonomy / classification
        for kw in (' types of ', ' branches of ', ' classified into ', ' consists of ', ' divided into ', ' forms of ', ' elements of ', ' categories of '):
            if kw in low:
                score += 3

        # Concepts / objectives / functions
        for kw in (' objective', ' principle', ' purpose', ' aim', ' characteristic', ' feature', ' function', ' advantage', ' stage', ' step'):
            if kw in low:
                score += 2

        # Scholar / theory
        for kw in (' according to ', ' propounded by ', ' argued by ', ' introduced by ', ' theory of ', ' father of '):
            if kw in low:
                score += 2.5

        if re.search(r'\b(e\.g\.|for example|such as|namely|specifically)\b', low):
            score += 1
        if re.search(r'\d', s):
            score += 0.3

        if is_def and len(key_terms) < 4:
            tm = re.match(r'^([A-Z][A-Za-z0-9\s\-]{2,30}?)\s+(?:is defined as|refers to|is the study of|means)\s+(.+)$', s, re.IGNORECASE)
            if tm:
                key_terms.append({'term': tm.group(1).strip(), 'definition': tm.group(2).strip()})

        scored.append((score, s))

    scored.sort(key=lambda x: (-x[0], -len(x[1])))
    picked, seen = [], set()
    for _, s in scored:
        key = s[:45].lower()
        if key in seen:
            continue
        seen.add(key)
        picked.append(_clean_sentence_for_point(s))
        if len(picked) >= max_points:
            break

    summary = ' '.join(p['explanation'] for p in picked[:3])[:max_chars] if picked else ''
    return summary, picked, key_terms


def _extract_decimal_keypoints(body, max_points=12):
    """Extract decimal (e.g. 3.1) or multilevel (e.g. 3.1.1) numbered sections and brief segment explanations."""
    if not body:
        return []

    pat = re.compile(r'(?im)^(?:\s*)((?:[1-9]\d?\.\d+(?:\.\d+)?)\s*[:\-–—.]?\s+[A-Za-z][^\n]{2,80})')
    matches = list(pat.finditer(body))
    real_matches = []
    for idx, m in enumerate(matches):
        next_start = matches[idx+1].start() if idx + 1 < len(matches) else len(body)
        if (next_start - m.end()) > 45:
            real_matches.append((m, next_start))

    points = []
    for m, next_start in real_matches:
        heading = re.sub(r'\s+', ' ', m.group(1)).strip()
        num_m = re.match(r'^(\d+\.\d+(?:\.\d+)?)\s*[:\-–—.]?\s*(.+)$', heading)
        if not num_m:
            continue
        num, title = num_m.group(1), num_m.group(2).strip()

        # Skip outer unit skeleton numbers or generic assignments
        if num in ('1.0', '2.0', '3.0', '4.0', '5.0', '6.0', '7.0', '8.0'):
            continue
        if re.search(r'(?i)\b(tutor-marked|assignment|reference|further reading|introduction|objective)\b', title):
            continue

        seg_text = body[m.end():next_start].strip()
        lines = [l.strip() for l in seg_text.split('\n') if l.strip()]
        lines = [l for l in lines if not re.match(r'^(?:[A-Z]{2,4}\s*\d{2,3})\b', l, re.IGNORECASE)]
        lines = [l for l in lines if not re.match(r'^\d{1,4}$', l)]
        lines = [l for l in lines if not re.search(r'(?i)\b(self-assessment|exercise|tma|activity|fig\.?|table|tutor-marked|copyright)\b', l)]
        cleaned = re.sub(r'\s+', ' ', ' '.join(lines)).strip()
        sentences = [s.strip() for s in re.split(r'(?<=[\.\!\?])\s+', cleaned) if len(s.strip()) > 20 and len(s.strip()) < 350]

        explanation = ''
        for s in sentences:
            if re.search(r'(?i)\b(is defined as|refers to|means|is known as|is a concept|is an act|consists of|classified into|types of|divided into|essential for|purpose of)\b', s):
                explanation = s
                break
        if not explanation:
            for s in sentences:
                if re.search(r'(?i)\b(principle|characteristic|function|importance|objective|feature|process|stage|technique)\b', s):
                    explanation = s
                    break
        if not explanation:
            for s in sentences:
                if not re.search(r'(?i)\b(turn to|look at|in this section|let us|write down|as mentioned|above|below|dear student)\b', s):
                    explanation = s
                    break
        if not explanation and sentences:
            explanation = sentences[0]

        if explanation:
            points.append({
                'concept': f'{num} {title}',
                'explanation': explanation[:320].strip()
            })
            if len(points) >= max_points:
                break

    return points


def _summary_cache_path(code):
    d = os.path.join(app.root_path, 'static', 'summary_cache')
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f'{code}.json')


def _parse_ai_summary_response(raw_text):
    """Robust parser for AI summary output (handles JSON, markdown code blocks, or plaintext)."""
    raw_text = (raw_text or '').strip()
    if not raw_text:
        return None

    # 1. Direct JSON parse
    try:
        data = json.loads(raw_text)
        if isinstance(data, dict):
            pts = [_normalize_key_point(p) for p in (data.get('key_points') or []) if p]
            return {
                'summary': str(data.get('summary') or '').strip(),
                'key_points': pts,
                'key_terms': data.get('key_terms') or []
            }
    except Exception:
        pass

    # 2. Extract ```json ... ``` codeblock
    match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', raw_text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(1))
            if isinstance(data, dict):
                pts = [_normalize_key_point(p) for p in (data.get('key_points') or []) if p]
                return {
                    'summary': str(data.get('summary') or '').strip(),
                    'key_points': pts,
                    'key_terms': data.get('key_terms') or []
                }
        except Exception:
            pass

    # 3. Fallback: Parse structured plaintext / markdown
    summary_lines = []
    key_points = []
    key_terms = []
    current_section = 'summary'

    for line in raw_text.split('\n'):
        sline = line.strip()
        if not sline:
            continue
        low = sline.lower()
        if re.match(r'^#*\s*(?:key\s*points?|exam\s*key\s*points?|bullet\s*points?|takeaways|concepts)\b', low):
            current_section = 'points'
            continue
        elif re.match(r'^#*\s*(?:key\s*terms?|definitions?|glossary)\b', low):
            current_section = 'terms'
            continue
        elif re.match(r'^#*\s*(?:summary|overview)\b', low):
            current_section = 'summary'
            continue

        if current_section == 'points':
            pt = re.sub(r'^(?:[-*•]|\d+[\.\)])\s*', '', sline).strip()
            if pt and len(pt) > 5:
                key_points.append(_normalize_key_point(pt))
        elif current_section == 'terms':
            tm = re.match(r'^(?:[-*•]\s*)?\*{0,2}([^:*]+)\*{0,2}\s*[:\-–]\s*(.+)$', sline)
            if tm:
                key_terms.append({'term': tm.group(1).strip(), 'definition': tm.group(2).strip()})
            else:
                pt = re.sub(r'^(?:[-*•]|\d+[\.\)])\s*', '', sline).strip()
                if pt:
                    key_points.append(_normalize_key_point(pt))
        else:
            if re.match(r'^(?:[-*•]|\d+[\.\)])\s*', sline):
                pt = re.sub(r'^(?:[-*•]|\d+[\.\)])\s*', '', sline).strip()
                if pt and len(pt) > 5:
                    key_points.append(_normalize_key_point(pt))
            else:
                summary_lines.append(sline)

    summary = ' '.join(summary_lines).strip()
    if summary or key_points:
        return {
            'summary': summary,
            'key_points': key_points,
            'key_terms': key_terms
        }
    return None


def _ai_summarize_content(text, course_code, section_type='unit', label='', title=''):
    """High-yield AI summary with concepts and brief explanations for exam revision via Groq or OpenAI."""
    text = (text or '').strip()
    if len(text) < 100:
        return None
    text = text[:8000]

    api_key = os.environ.get('GROQ_API_KEY') or os.environ.get('OPENAI_API_KEY')
    if not api_key:
        return None

    use_groq = bool(os.environ.get('GROQ_API_KEY'))
    try:
        import requests as http_requests
        prompt = (
            f"You are an expert university academic exam tutor preparing National Open University of Nigeria (NOUN) students for examinations.\n"
            f"Summarize the following {section_type.upper()} material from course {course_code}: {label} - {title}.\n"
            f"Students use this on their phones while on the go for fast, high-retention exam revision.\n\n"
            f"REQUIREMENT: Do NOT output bare, terse bullet phrases. For each key point, provide an explicit 'concept' heading AND a brief 2-3 sentence clear 'explanation' explaining what it means, the rules/steps/principles involved, and why it is critical for exams.\n\n"
            f"Respond with a JSON object in this exact schema:\n"
            f"{{\n"
            f"  \"summary\": \"A concise 2-3 sentence overview of this {section_type}'s core subject.\",\n"
            f"  \"key_points\": [\n"
            f"    {{\n"
            f"      \"concept\": \"Core Exam Concept / Rule / Classification / Scholar\",\n"
            f"      \"explanation\": \"Brief 2-3 sentence explanation explaining the rule, definition, classification, or exam implication so students studying on the go can fully understand and memorize it.\"\n"
            f"    }}\n"
            f"  ],\n"
            f"  \"key_terms\": [\n"
            f"    {{\"term\": \"Core Term\", \"definition\": \"Accurate definition based on the text.\"}}\n"
            f"  ]\n"
            f"}}\n\n"
            f"Provide 5 to 8 exam-focused key_points with brief explanations. Return ONLY valid JSON.\n\n"
            f"MATERIAL:\n{text}"
        )

        if use_groq:
            url = 'https://api.groq.com/openai/v1/chat/completions'
            model = os.environ.get('GROQ_MODEL', 'llama-3.3-70b-versatile')
            headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
            payload = {
                'model': model,
                'messages': [
                    {'role': 'system', 'content': 'You are an elite university exam tutor. You output only valid JSON with high-yield exam concepts, brief explanations, and definitions.'},
                    {'role': 'user', 'content': prompt},
                ],
                'temperature': 0.2,
                'max_tokens': 1400,
                'response_format': {'type': 'json_object'},
            }
        else:
            url = 'https://api.openai.com/v1/chat/completions'
            model = os.environ.get('OPENAI_MODEL', 'gpt-4o-mini')
            headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
            payload = {
                'model': model,
                'messages': [
                    {'role': 'system', 'content': 'You are an elite university exam tutor. You output only valid JSON with high-yield exam concepts, brief explanations, and definitions.'},
                    {'role': 'user', 'content': prompt},
                ],
                'temperature': 0.2,
                'max_tokens': 1400,
                'response_format': {'type': 'json_object'},
            }

        r = http_requests.post(url, headers=headers, json=payload, timeout=(3.0, 5.5))
        if r.status_code != 200:
            app.logger.warning('AI summarize HTTP %s: %s', r.status_code, r.text[:300])
            return None
        data = r.json()
        raw_content = data['choices'][0]['message']['content'].strip()
        return _parse_ai_summary_response(raw_content)
    except Exception as e:
        app.logger.warning('AI summarize failed: %s', e)
        return None


@app.route('/materials/summarize/<course_code>')
@login_required
def summarize_material(course_code):
    """Fast, resilient module/unit auto-summarizer with instant caching and exam keypoints."""
    code, course_title, local_path, urls = _resolve_material(course_code)
    if course_title == code:
        _, nu_title = _discover_nounupdate_pdf(code)
        if nu_title:
            course_title = nu_title

    # Serve cached summary when available (unless ?refresh=1)
    cache_file = _summary_cache_path(code)
    if request.args.get('refresh') != '1' and os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached = json.load(f)
            return render_template('materials/summary.html',
                                   course_code=code,
                                   course_title=cached.get('course_title') or course_title,
                                   error=None,
                                   modules=cached.get('modules') or [],
                                   overview=cached.get('overview') or '',
                                   highlights=cached.get('highlights') or [],
                                   ai_generated=cached.get('ai_generated', False),
                                   page_count=cached.get('page_count') or 0)
        except Exception:
            pass

    path = local_path or _fetch_and_cache_pdf(code, urls)
    if not path:
        return render_template('materials/summary.html',
                               course_code=code, course_title=course_title,
                               error='Could not download the course PDF to summarize. Open the full material first, then try again.',
                               modules=[], overview='', highlights=[], ai_generated=False, page_count=0)

    pages, err = _extract_pdf_text(path, max_pages=110)
    if err:
        return render_template('materials/summary.html',
                               course_code=code, course_title=course_title,
                               error=err, modules=[], overview='', highlights=[], ai_generated=False, page_count=0)

    full_text = '\n'.join(pages)
    if len(full_text.strip()) < 200:
        return render_template('materials/summary.html',
                               course_code=code, course_title=course_title,
                               error='This PDF has little extractable text (likely scanned images). The on-page PDF viewer still works; summary needs a text-based PDF.',
                               modules=[], overview='', highlights=[], ai_generated=False, page_count=len(pages))

    raw_modules = _split_modules_units(full_text)

    # Fast extractive breakdown for all modules and units (takes < 0.05s)
    modules = []
    for m_idx, m in enumerate(raw_modules[:12]):
        body = m.get('body') or ''
        if len(body) < 100:
            body = '\n'.join((u.get('body') or '') for u in m.get('units') or [])
        ext_sum, ext_pts, ext_terms = _summarize_block(body, max_points=6, max_chars=800)

        units_out = []
        for u_idx, u in enumerate((m.get('units') or [])[:12]):
            u_body = u.get('body') or ''
            dec_pts = _extract_decimal_keypoints(u_body)
            u_ext_sum, u_ext_pts, u_ext_terms = _summarize_block(u_body, max_points=6, max_chars=600)
            final_pts = dec_pts if len(dec_pts) >= 1 else u_ext_pts

            units_out.append({
                'label': u.get('label'),
                'title': u.get('title'),
                'summary': u_ext_sum,
                'key_points': final_pts,
                'key_terms': u_ext_terms,
            })

        m_dec_pts = _extract_decimal_keypoints(body)
        final_m_pts = m_dec_pts if len(m_dec_pts) >= 2 else ext_pts

        modules.append({
            'label': m.get('label'),
            'title': m.get('title'),
            'summary': ext_sum,
            'key_points': final_m_pts,
            'key_terms': ext_terms,
            'units': units_out,
        })

    ext_overview, ext_highlights, _ = _summarize_block(full_text[:14000], max_points=7, max_chars=1200)
    overview = ext_overview
    highlights = ext_highlights
    ai_generated = False

    # Targeted fast AI enhancement for Course Overview (capped with 5-second timeout)
    ai_enabled = bool(os.environ.get('GROQ_API_KEY') or os.environ.get('OPENAI_API_KEY'))
    if ai_enabled and len(full_text.strip()) > 300:
        try:
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=1) as executor:
                ai_fut = executor.submit(
                    _ai_summarize_content, full_text[:12000], code, 'course_overview', 'Course Overview', course_title
                )
                try:
                    res = ai_fut.result(timeout=5.0)
                    if res:
                        if res.get('summary'):
                            overview = res.get('summary')
                        if res.get('key_points'):
                            highlights = res.get('key_points')
                        ai_generated = True
                except Exception as e:
                    app.logger.warning('AI overview timeout/error for %s: %s (falling back to extractive)', code, e)
        except Exception as e:
            app.logger.warning('AI executor error: %s', e)

    # Cache result
    try:
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump({
                'course_code': code,
                'course_title': course_title,
                'modules': modules,
                'overview': overview,
                'highlights': highlights[:12],
                'ai_generated': ai_generated,
                'page_count': len(pages),
            }, f, ensure_ascii=False)
    except Exception:
        pass

    return render_template('materials/summary.html',
                           course_code=code,
                           course_title=course_title,
                           error=None,
                           modules=modules,
                           overview=overview,
                           highlights=highlights[:12],
                           ai_generated=ai_generated,
                           page_count=len(pages))


@app.route('/materials/search-nounupdate')
@login_required
def search_nounupdate():
    """Search external course material sources for a code/title and list matches."""
    import requests as http_requests
    q = (request.args.get('q') or '').strip()
    results = []
    error = None
    if len(q) >= 2:
        try:
            # Prefer direct course page if looks like a code
            code_guess = re.sub(r'[^A-Za-z0-9]', '', q).upper()
            if re.match(r'^[A-Z]{2,4}\d{2,3}$', code_guess):
                url = f'https://nounupdate.com/courses/{code_guess}'
                pdf, title = _discover_nounupdate_pdf(code_guess)
                results.append({
                    'course_code': code_guess,
                    'title': title or code_guess,
                    'page_url': url,
                    'pdf_url': pdf or f'https://nounupdate.com/file-course-materials/{code_guess}.pdf',
                })
            # Also scan main courses page for link matches
            r = http_requests.get('https://nounupdate.com/courses/', timeout=25, headers={
                'User-Agent': 'Mozilla/5.0',
                'Accept': 'text/html',
            })
            if r.status_code == 200:
                # Links like /courses/BIO201 or ACC101 Elements...
                for m in re.finditer(r'href=["\']/courses/([A-Za-z]{2,4}\d{2,3})["\'][^>]*>([^<]+)', r.text):
                    code = m.group(1).upper()
                    label = re.sub(r'\s+', ' ', m.group(2)).strip()
                    if q.lower() in code.lower() or q.lower() in label.lower():
                        if not any(x['course_code'] == code for x in results):
                            results.append({
                                'course_code': code,
                                'title': label,
                                'page_url': f'https://nounupdate.com/courses/{code}',
                                'pdf_url': f'https://nounupdate.com/file-course-materials/{code}.pdf',
                            })
                # Fallback broader pattern
                if not results:
                    for m in re.finditer(r'/courses/([A-Za-z]{2,4}\d{2,3})', r.text):
                        code = m.group(1).upper()
                        if q.lower() in code.lower() and not any(x['course_code'] == code for x in results):
                            results.append({
                                'course_code': code,
                                'title': code,
                                'page_url': f'https://nounupdate.com/courses/{code}',
                                'pdf_url': f'https://nounupdate.com/file-course-materials/{code}.pdf',
                            })
            results = results[:40]
        except Exception as e:
            error = f'Search failed: {e}'
    return render_template('materials/nounupdate_search.html', q=q, results=results, error=error)



# ==================== STUDENT ROUTES ====================

@app.route('/dashboard')
@login_required
def student_dashboard():
    if current_user.is_teacher():
        return redirect(url_for('admin_dashboard'))
    
    # Available published exams
    exams = Exam.query.filter_by(is_published=True).order_by(Exam.created_at.desc()).all()
    
    # Recent attempts
    recent_attempts = Attempt.query.filter_by(user_id=current_user.id)\
        .order_by(Attempt.completed_at.desc()).limit(5).all()
    
    # Stats
    total_attempts = Attempt.query.filter_by(user_id=current_user.id).count()
    avg_score = db.session.query(db.func.avg(Attempt.percentage))\
        .filter_by(user_id=current_user.id).scalar() or 0
    
    return render_template('student/dashboard.html',
                           exams=exams,
                           recent_attempts=recent_attempts,
                           total_attempts=total_attempts,
                           avg_score=round(avg_score, 1))


@app.route('/exams')
@login_required
def exam_list():
    faculty = request.args.get('faculty')
    search = request.args.get('search', '').strip()
    
    query = Exam.query.filter_by(is_published=True)
    
    if faculty:
        query = query.filter_by(faculty=faculty)
    if search:
        query = query.filter(
            db.or_(
                Exam.title.ilike(f'%{search}%'),
                Exam.course_code.ilike(f'%{search}%')
            )
        )
    
    exams = query.order_by(Exam.created_at.desc()).all()
    
    # Get unique faculties for filter
    faculties = db.session.query(Exam.faculty).filter(
        Exam.faculty.isnot(None), Exam.is_published == True
    ).distinct().all()
    faculties = [f[0] for f in faculties if f[0]]
    
    return render_template('student/exam_list.html', exams=exams, faculties=faculties,
                           selected_faculty=faculty, search=search)


@app.route('/exam/<int:exam_id>')
@login_required
def exam_detail(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    if not exam.is_published and not current_user.is_teacher():
        flash('This exam is not available.', 'warning')
        return redirect(url_for('exam_list'))
    
    # Previous attempts by this student
    previous = Attempt.query.filter_by(
        user_id=current_user.id, exam_id=exam_id
    ).order_by(Attempt.completed_at.desc()).all()
    
    return render_template('student/exam_detail.html', exam=exam, previous=previous)


@app.route('/exam/<int:exam_id>/instructions')
@login_required
def exam_instructions(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    if not exam.is_published and not current_user.is_teacher():
        flash('This exam is not available.', 'warning')
        return redirect(url_for('exam_list'))
    if exam.total_questions == 0:
        flash('This exam has no questions yet.', 'warning')
        return redirect(url_for('exam_detail', exam_id=exam_id))
    return render_template('student/exam_instructions.html', exam=exam)


@app.route('/exam/<int:exam_id>/start', methods=['POST'])
@login_required
def start_exam(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    
    if not exam.is_published and not current_user.is_teacher():
        flash('This exam is not available.', 'warning')
        return redirect(url_for('exam_list'))
    
    questions = exam.questions.order_by(Question.order, Question.id).all()
    if not questions:
        flash('This exam has no questions yet.', 'warning')
        return redirect(url_for('exam_detail', exam_id=exam_id))
    
    # Create a random order of question IDs for this student attempt
    import random
    q_ids = [q.id for q in questions]
    random.shuffle(q_ids)
    
    session['exam_start'] = {
        'exam_id': exam_id,
        'started_at': datetime.utcnow().isoformat(),
        'duration': exam.duration_minutes,
        'question_order': q_ids   # shuffled order unique to this attempt
    }
    
    return redirect(url_for('take_exam', exam_id=exam_id))


@app.route('/exam/<int:exam_id>/take')
@login_required
def take_exam(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    
    # Check if exam was started
    exam_start = session.get('exam_start')
    if not exam_start or exam_start.get('exam_id') != exam_id:
        flash('Please start the exam properly.', 'warning')
        return redirect(url_for('exam_detail', exam_id=exam_id))
    
    # Use the shuffled question order stored for this student attempt
    question_order = exam_start.get('question_order')
    if question_order:
        # Fetch questions and sort them according to the shuffled order
        questions_map = {q.id: q for q in exam.questions.all()}
        questions = [questions_map[qid] for qid in question_order if qid in questions_map]
    else:
        questions = exam.questions.order_by(Question.order, Question.id).all()
    
    if not questions:
        flash('No questions available.', 'warning')
        return redirect(url_for('exam_detail', exam_id=exam_id))
    
    started_at = datetime.fromisoformat(exam_start['started_at'])
    duration = exam_start['duration']
    end_time = started_at + timedelta(minutes=duration)
    
    remaining = (end_time - datetime.utcnow()).total_seconds()
    if remaining <= 0:
        flash('Time is up! Submitting your exam.', 'warning')
        return redirect(url_for('submit_exam', exam_id=exam_id))
    
    return render_template('student/take_exam.html',
                           exam=exam,
                           questions=questions,
                           remaining_seconds=int(remaining),
                           end_time=end_time.isoformat())


@app.route('/exam/<int:exam_id>/submit', methods=['POST'])
@login_required
def submit_exam(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    questions = exam.questions.order_by(Question.order, Question.id).all()
    
    exam_start = session.pop('exam_start', None)
    
    answers = {}
    score = 0
    
    for q in questions:
        selected = request.form.get(f'q_{q.id}', '').strip()
        answers[str(q.id)] = selected
        
        if selected:
            if q.question_type == 'fill':
                # Case-insensitive, strip spaces for fill-in-the-gap
                if selected.lower().strip() == q.correct_answer.lower().strip():
                    score += 1
            else:
                # MCQ
                if selected.upper() == q.correct_answer.upper():
                    score += 1
    
    total = len(questions)
    percentage = (score / total * 100) if total > 0 else 0
    
    # Calculate time taken
    time_taken = None
    if exam_start:
        started_at = datetime.fromisoformat(exam_start['started_at'])
        time_taken = int((datetime.utcnow() - started_at).total_seconds())
    
    attempt = Attempt(
        user_id=current_user.id,
        exam_id=exam_id,
        score=score,
        total_questions=total,
        percentage=round(percentage, 1),
        answers=json.dumps(answers),
        completed_at=datetime.utcnow(),
        time_taken_seconds=time_taken
    )
    db.session.add(attempt)
    db.session.commit()
    
    flash(f'Exam submitted! You scored {score}/{total} ({percentage:.1f}%)', 'success')
    return redirect(url_for('view_result', attempt_id=attempt.id))


@app.route('/result/<int:attempt_id>')
@login_required
def view_result(attempt_id):
    attempt = Attempt.query.get_or_404(attempt_id)
    
    # Only the student or teachers can view
    if attempt.user_id != current_user.id and not current_user.is_teacher():
        flash('Access denied.', 'danger')
        return redirect(url_for('student_dashboard'))
    
    exam = attempt.exam
    questions = exam.questions.order_by(Question.order, Question.id).all()
    answers = json.loads(attempt.answers) if attempt.answers else {}
    
    return render_template('student/result.html',
                           attempt=attempt,
                           exam=exam,
                           questions=questions,
                           answers=answers)


@app.route('/my-results')
@login_required
def my_results():
    attempts = Attempt.query.filter_by(user_id=current_user.id)\
        .order_by(Attempt.completed_at.desc()).all()
    return render_template('student/my_results.html', attempts=attempts)


# ==================== ADMIN / TEACHER ROUTES ====================

@app.route('/admin')
@login_required
def admin_dashboard():
    if not current_user.is_teacher():
        flash('Access denied. Teachers/Admins only.', 'danger')
        return redirect(url_for('student_dashboard'))
    
    total_exams = Exam.query.count()
    total_students = User.query.filter_by(role='student').count()
    total_attempts = Attempt.query.count()
    
    recent_exams = Exam.query.order_by(Exam.created_at.desc()).limit(5).all()
    
    return render_template('admin/dashboard.html',
                           total_exams=total_exams,
                           total_students=total_students,
                           total_attempts=total_attempts,
                           recent_exams=recent_exams)


@app.route('/admin/exams')
@login_required
def admin_exams():
    if not current_user.is_teacher():
        flash('Access denied.', 'danger')
        return redirect(url_for('student_dashboard'))
    
    exams = Exam.query.order_by(Exam.created_at.desc()).all()
    return render_template('admin/exams.html', exams=exams)


@app.route('/admin/exam/create', methods=['GET', 'POST'])
@login_required
def create_exam():
    if not current_user.is_teacher():
        flash('Access denied.', 'danger')
        return redirect(url_for('student_dashboard'))
    
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        course_code = request.form.get('course_code', '').strip().upper()
        faculty = request.form.get('faculty', '').strip()
        duration = request.form.get('duration_minutes', 30)
        credit_units = request.form.get('credit_units', 2)
        
        if not title:
            flash('Exam title is required.', 'danger')
            return redirect(url_for('create_exam'))
        
        try:
            duration = int(duration)
        except:
            duration = 30

        try:
            credit_units = int(credit_units)
            if credit_units not in [2, 3]:
                credit_units = 2
        except:
            credit_units = 2
        
        exam = Exam(
            title=title,
            description=description,
            course_code=course_code,
            faculty=faculty,
            credit_units=credit_units,
            duration_minutes=duration,
            created_by=current_user.id,
            is_published=True
        )
        db.session.add(exam)
        db.session.commit()
        
        flash('Exam created! Now add questions.', 'success')
        return redirect(url_for('manage_questions', exam_id=exam.id))
    
    return render_template('admin/create_exam.html')


@app.route('/admin/exam/<int:exam_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_exam(exam_id):
    if not current_user.is_teacher():
        flash('Access denied.', 'danger')
        return redirect(url_for('student_dashboard'))
    
    exam = Exam.query.get_or_404(exam_id)
    
    if request.method == 'POST':
        exam.title = request.form.get('title', '').strip()
        exam.description = request.form.get('description', '').strip()
        exam.course_code = request.form.get('course_code', '').strip().upper()
        exam.faculty = request.form.get('faculty', '').strip()
        try:
            credit_units = int(request.form.get('credit_units', 2))
            if credit_units in [2, 3]:
                exam.credit_units = credit_units
        except:
            pass
        try:
            exam.duration_minutes = int(request.form.get('duration_minutes', 30))
        except:
            pass
        exam.is_published = 'is_published' in request.form
        
        db.session.commit()
        flash('Exam updated successfully.', 'success')
        return redirect(url_for('admin_exams'))
    
    return render_template('admin/edit_exam.html', exam=exam)


@app.route('/admin/exam/<int:exam_id>/questions', methods=['GET', 'POST'])
@login_required
def manage_questions(exam_id):
    if not current_user.is_teacher():
        flash('Access denied.', 'danger')
        return redirect(url_for('student_dashboard'))
    
    exam = Exam.query.get_or_404(exam_id)
    
    if request.method == 'POST':
        question_text = request.form.get('question_text', '').strip()
        question_type = request.form.get('question_type', 'mcq')
        explanation = request.form.get('explanation', '').strip()
        
        if not question_text:
            flash('Question text is required.', 'danger')
            return redirect(url_for('manage_questions', exam_id=exam_id))
        
        if question_type == 'fill':
            correct = request.form.get('correct_answer_fill', '').strip()
            if not correct:
                flash('Correct answer is required for fill-in questions.', 'danger')
                return redirect(url_for('manage_questions', exam_id=exam_id))
            option_a = option_b = option_c = option_d = None
        else:
            option_a = request.form.get('option_a', '').strip()
            option_b = request.form.get('option_b', '').strip()
            option_c = request.form.get('option_c', '').strip()
            option_d = request.form.get('option_d', '').strip()
            correct = request.form.get('correct_answer_mcq', '').upper()
            if not all([option_a, option_b, option_c, option_d, correct]):
                flash('Please fill all MCQ options and select correct answer.', 'danger')
                return redirect(url_for('manage_questions', exam_id=exam_id))
            if correct not in ['A', 'B', 'C', 'D']:
                flash('Correct answer must be A, B, C or D.', 'danger')
                return redirect(url_for('manage_questions', exam_id=exam_id))
        
        max_order = db.session.query(db.func.max(Question.order))\
            .filter_by(exam_id=exam_id).scalar() or 0
        
        question = Question(
            exam_id=exam_id,
            question_text=question_text,
            question_type=question_type,
            option_a=option_a,
            option_b=option_b,
            option_c=option_c,
            option_d=option_d,
            correct_answer=correct,
            explanation=explanation,
            order=max_order + 1
        )
        db.session.add(question)
        
        exam.total_questions = exam.questions.count() + 1
        db.session.commit()
        
        flash('Question added successfully!', 'success')
        return redirect(url_for('manage_questions', exam_id=exam_id))
    
    questions = exam.questions.order_by(Question.order, Question.id).all()
    return render_template('admin/manage_questions.html', exam=exam, questions=questions)


@app.route('/admin/question/<int:question_id>/delete', methods=['POST'])
@login_required
def delete_question(question_id):
    if not current_user.is_teacher():
        flash('Access denied.', 'danger')
        return redirect(url_for('student_dashboard'))
    
    question = Question.query.get_or_404(question_id)
    exam_id = question.exam_id
    exam = question.exam
    
    db.session.delete(question)
    exam.total_questions = exam.questions.count() - 1
    db.session.commit()
    
    flash('Question deleted.', 'info')
    return redirect(url_for('manage_questions', exam_id=exam_id))


@app.route('/admin/exam/<int:exam_id>/delete', methods=['POST'])
@login_required
def delete_exam(exam_id):
    if not current_user.is_admin():
        flash('Only admins can delete exams.', 'danger')
        return redirect(url_for('admin_exams'))
    
    exam = Exam.query.get_or_404(exam_id)
    db.session.delete(exam)
    db.session.commit()
    
    flash('Exam deleted.', 'info')
    return redirect(url_for('admin_exams'))


@app.route('/admin/students')
@login_required
def admin_students():
    if not current_user.is_teacher():
        flash('Access denied.', 'danger')
        return redirect(url_for('student_dashboard'))
    
    students = User.query.filter_by(role='student').order_by(User.created_at.desc()).all()
    return render_template('admin/students.html', students=students)


@app.route('/admin/attempts')
@login_required
def admin_attempts():
    if not current_user.is_teacher():
        flash('Access denied.', 'danger')
        return redirect(url_for('student_dashboard'))
    
    attempts = Attempt.query.order_by(Attempt.completed_at.desc()).all()
    return render_template('admin/attempts.html', attempts=attempts)


@app.route('/admin/exam/<int:exam_id>/upload-csv', methods=['GET', 'POST'])
@login_required
def upload_questions_csv(exam_id):
    if not current_user.is_teacher():
        flash('Access denied.', 'danger')
        return redirect(url_for('student_dashboard'))
    
    exam = Exam.query.get_or_404(exam_id)
    
    if request.method == 'POST':
        file = request.files.get('csv_file')
        if not file or not file.filename.endswith('.csv'):
            flash('Please upload a valid CSV file.', 'danger')
            return redirect(url_for('upload_questions_csv', exam_id=exam_id))
        
        try:
            raw = file.stream.read()
            # Handle BOM (Excel often adds it)
            if raw.startswith(b'\xef\xbb\xbf'):
                raw = raw[3:]
            text_data = raw.decode('utf-8-sig')  # utf-8-sig also strips BOM
            stream = io.StringIO(text_data)
            reader = csv.DictReader(stream)
            
            # Normalize headers (strip BOM/spaces)
            if reader.fieldnames:
                reader.fieldnames = [h.lstrip('\ufeff').strip() if h else h for h in reader.fieldnames]
            
            added = 0
            max_order = db.session.query(db.func.max(Question.order)).filter_by(exam_id=exam_id).scalar() or 0
            
            for row in reader:
                # Normalize keys
                row = { (k.lstrip('\ufeff').strip() if k else k): v for k, v in row.items() }
                
                qtype = (row.get('type') or 'mcq').strip().lower()
                text = (row.get('question') or '').strip()
                if not text:
                    continue
                
                if qtype in ['tf', 'true_false', 'true/false', 'boolean', 'yes_no', 'yes/no']:
                    raw_correct = (row.get('correct') or '').strip().lower()
                    opt_a = (row.get('option_a') or '').strip()
                    opt_b = (row.get('option_b') or '').strip()
                    
                    # If options are not specified, default to True / False or Yes / No based on format
                    is_yes_no = ('yes' in raw_correct or 'no' in raw_correct or 
                                 opt_a.lower() in ['yes', 'no'] or opt_b.lower() in ['yes', 'no'] or
                                 'yes' in qtype)
                    
                    if not opt_a:
                        opt_a = 'Yes' if is_yes_no else 'True'
                    if not opt_b:
                        opt_b = 'No' if is_yes_no else 'False'
                    
                    # Determine whether the correct answer maps to A or B
                    if raw_correct in ['a', 'true', 't', 'yes', 'y', '1'] or raw_correct == opt_a.lower():
                        correct = 'A'
                    elif raw_correct in ['b', 'false', 'f', 'no', 'n', '0'] or raw_correct == opt_b.lower():
                        correct = 'B'
                    else:
                        continue
                        
                    q = Question(
                        exam_id=exam_id,
                        question_text=text,
                        question_type='mcq',
                        option_a=opt_a,
                        option_b=opt_b,
                        option_c='',
                        option_d='',
                        correct_answer=correct,
                        explanation=(row.get('explanation') or '').strip(),
                        order=max_order + added + 1
                    )
                elif qtype == 'fill':
                    correct = (row.get('correct') or '').strip()
                    if not correct:
                        continue
                    q = Question(
                        exam_id=exam_id,
                        question_text=text,
                        question_type='fill',
                        correct_answer=correct,
                        explanation=(row.get('explanation') or '').strip(),
                        order=max_order + added + 1
                    )
                else:
                    raw_correct = (row.get('correct') or '').strip()
                    upper_correct = raw_correct.upper()
                    
                    # If marked as MCQ but options or correct are True/False or Yes/No, auto-handle as True/False
                    opt_a = (row.get('option_a') or '').strip()
                    opt_b = (row.get('option_b') or '').strip()
                    opt_c = (row.get('option_c') or '').strip()
                    opt_d = (row.get('option_d') or '').strip()
                    
                    if raw_correct.lower() in ['true', 'false', 'yes', 'no']:
                        is_yes_no = raw_correct.lower() in ['yes', 'no'] or opt_a.lower() in ['yes', 'no']
                        if not opt_a:
                            opt_a = 'Yes' if is_yes_no else 'True'
                        if not opt_b:
                            opt_b = 'No' if is_yes_no else 'False'
                        correct = 'A' if raw_correct.lower() in ['true', 'yes'] else 'B'
                    elif upper_correct in ['A', 'B', 'C', 'D']:
                        correct = upper_correct
                    else:
                        continue
                        
                    q = Question(
                        exam_id=exam_id,
                        question_text=text,
                        question_type='mcq',
                        option_a=opt_a,
                        option_b=opt_b,
                        option_c=opt_c,
                        option_d=opt_d,
                        correct_answer=correct,
                        explanation=(row.get('explanation') or '').strip(),
                        order=max_order + added + 1
                    )
                db.session.add(q)
                added += 1
            
            db.session.flush()
            
            # Auto-intermix: shuffle all questions for this exam so MCQ and Fill-in are mixed
            import random
            all_questions = Question.query.filter_by(exam_id=exam_id).order_by(Question.order).all()
            random.shuffle(all_questions)
            for idx, q in enumerate(all_questions, start=1):
                q.order = idx
            
            exam.total_questions = len(all_questions)
            db.session.commit()
            flash(f'Successfully imported {added} questions! Questions have been automatically mixed (MCQ + Fill-in intermixed).', 'success')
            return redirect(url_for('manage_questions', exam_id=exam_id))
        except Exception as e:
            flash(f'Error reading CSV: {str(e)}', 'danger')
            return redirect(url_for('upload_questions_csv', exam_id=exam_id))
    
    return render_template('admin/upload_csv.html', exam=exam)


@app.route('/admin/sample-csv')
@login_required
def download_sample_csv():
    if not current_user.is_teacher():
        flash('Access denied.', 'danger')
        return redirect(url_for('student_dashboard'))
    
    sample = """type,question,option_a,option_b,option_c,option_d,correct,explanation
mcq,What does SQL stand for?,Structured Query Language,Simple Query Language,Standard Question Language,Sequential Query Logic,A,SQL means Structured Query Language
tf,Operating systems manage computer hardware and software resources.,True,False,,,True,OS manages hardware and software
tf,Python is a compiled machine code language only.,True,False,,,False,Python is an interpreted language
tf,Is RAM volatile memory?,Yes,No,,,Yes,RAM loses its content when power is turned off
fill,The full meaning of FIFO is __________.,,,,First In First Out,FIFO stands for First In First Out
fill,A __________ is a program in execution.,,,,process,A process is a program in execution
mcq,Which scheduling algorithm can cause starvation?,Round Robin,First Come First Served,Shortest Job First,None of the above,C,SJF can cause starvation of long processes
"""
    from flask import Response
    return Response(
        sample,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=sample_questions.csv'}
    )


@app.route('/admin/exam/<int:exam_id>/shuffle', methods=['POST'])
@login_required
def shuffle_questions(exam_id):
    if not current_user.is_teacher():
        flash('Access denied.', 'danger')
        return redirect(url_for('student_dashboard'))
    
    exam = Exam.query.get_or_404(exam_id)
    import random
    questions = Question.query.filter_by(exam_id=exam_id).all()
    random.shuffle(questions)
    for idx, q in enumerate(questions, start=1):
        q.order = idx
    db.session.commit()
    flash('Questions have been randomly intermixed (MCQ + Fill-in mixed).', 'success')
    return redirect(url_for('manage_questions', exam_id=exam_id))


@app.route('/admin/materials/upload', methods=['GET', 'POST'])
@login_required
def admin_upload_material():
    """Allow Admin/Teachers to upload course material PDFs and make them available to all students."""
    if not current_user.is_teacher():
        flash('Access denied. Teachers/Admins only.', 'danger')
        return redirect(url_for('student_dashboard'))

    json_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'timetable_courses.json')
    courses = []
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                courses = json.load(f)
        except Exception:
            courses = []

    faculties = sorted(list(set(c.get('faculty') for c in courses if c.get('faculty'))))

    if request.method == 'POST':
        code = request.form.get('course_code', '').strip().replace(' ', '').upper()
        title = request.form.get('title', '').strip()
        faculty = request.form.get('faculty', '').strip()
        pdf_file = request.files.get('pdf_file')

        if not code:
            flash('Course Code is required (e.g. GST101, LAW101).', 'danger')
            return redirect(url_for('admin_upload_material'))

        if not pdf_file or not pdf_file.filename:
            flash('Please select a PDF file to upload.', 'danger')
            return redirect(url_for('admin_upload_material'))

        if not pdf_file.filename.lower().endswith('.pdf'):
            flash('Only .pdf files are accepted.', 'danger')
            return redirect(url_for('admin_upload_material'))

        # Save to static/materials/{code}.pdf
        upload_dir = os.path.join(app.root_path, 'static', 'materials')
        os.makedirs(upload_dir, exist_ok=True)
        target_path = os.path.join(upload_dir, f"{code}.pdf")
        pdf_file.save(target_path)

        # Update timetable_courses.json
        updated = False
        for c in courses:
            if c.get('course_code', '').upper() == code:
                if title:
                    c['title'] = title
                if faculty:
                    c['faculty'] = faculty
                c['is_verified'] = True
                updated = True
                break
        if not updated:
            courses.append({
                'course_code': code,
                'title': title or code,
                'faculty': faculty or 'General',
                'is_verified': True
            })

        try:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(courses, f, indent=2, ensure_ascii=False)
        except Exception as e:
            app.logger.warning('Failed to update timetable_courses.json: %s', e)

        # Automatically pre-cache summary for this course so it loads instantly for all students
        try:
            pages, err = _extract_pdf_text(target_path, max_pages=110)
            if not err and pages:
                full_text = '\n'.join(pages)
                raw_modules = _split_modules_units(full_text)
                mods_out = []
                for m_idx, m in enumerate(raw_modules[:12]):
                    m_body = m.get('body') or ''
                    if len(m_body) < 100:
                        m_body = '\n'.join((u.get('body') or '') for u in m.get('units') or [])
                    ext_sum, ext_pts, ext_terms = _summarize_block(m_body, max_points=6, max_chars=800)
                    units_out = []
                    for u in (m.get('units') or [])[:12]:
                        u_body = u.get('body') or ''
                        u_dec_pts = _extract_decimal_keypoints(u_body)
                        u_ext_sum, u_ext_pts, u_ext_terms = _summarize_block(u_body, max_points=6, max_chars=600)
                        units_out.append({
                            'label': u.get('label'),
                            'title': u.get('title'),
                            'summary': u_ext_sum,
                            'key_points': u_dec_pts if len(u_dec_pts) >= 1 else u_ext_pts,
                            'key_terms': u_ext_terms,
                        })
                    m_dec_pts = _extract_decimal_keypoints(m_body)
                    mods_out.append({
                        'label': m.get('label'),
                        'title': m.get('title'),
                        'summary': ext_sum,
                        'key_points': m_dec_pts if len(m_dec_pts) >= 2 else ext_pts,
                        'key_terms': ext_terms,
                        'units': units_out,
                    })
                ext_ov, ext_high, _ = _summarize_block(full_text[:14000], max_points=7, max_chars=1200)
                cache_file = _summary_cache_path(code)
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump({
                        'course_code': code,
                        'course_title': title or code,
                        'modules': mods_out,
                        'overview': ext_ov,
                        'highlights': ext_high[:12],
                        'ai_generated': False,
                        'page_count': len(pages),
                    }, f, ensure_ascii=False)
        except Exception as e:
            app.logger.warning('Pre-cache summary failed for %s: %s', code, e)

        flash(f'Course material for {code} uploaded successfully! It is now live for all students to read and summarize.', 'success')
        return redirect(url_for('course_materials', search=code))

    return render_template('admin/upload_material.html', faculties=faculties)


# ==================== INITIALIZE DATABASE ====================

def init_db():
    with app.app_context():
        db.create_all()
        
        # Create default admin if not exists
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(
                username='admin',
                email='admin@noun.edu.ng',
                full_name='System Administrator',
                role='admin',
                faculty='Administration'
            )
            admin.set_password('admin123')
            db.session.add(admin)
            
            # Create a sample teacher
            teacher = User(
                username='teacher1',
                email='teacher1@noun.edu.ng',
                full_name='Dr. Adebayo Okonkwo',
                role='teacher',
                faculty='Faculty of Sciences'
            )
            teacher.set_password('teacher123')
            db.session.add(teacher)
            
            db.session.commit()
            print("✓ Default admin and teacher created")
            print("  Admin  → username: admin  | password: admin123")
            print("  Teacher → username: teacher1 | password: teacher123")
        
        # Automatically seed and synchronize all 8 courses and 362 questions from courses_data.json
        json_file = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'courses_data.json')
        if os.path.exists(json_file):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    seed_data = json.load(f)
                
                # Map old json exam_id to newly created/found exam.id
                id_map = {}
                for e in seed_data.get('exams', []):
                    ex = Exam.query.filter_by(course_code=e['course_code'], title=e['title']).first()
                    if not ex:
                        ex = Exam(
                            title=e['title'],
                            description=e.get('description', ''),
                            course_code=e.get('course_code', ''),
                            faculty=e.get('faculty', 'General Studies'),
                            credit_units=e.get('credit_units', 2),
                            duration_minutes=e.get('duration_minutes', 30),
                            total_questions=e.get('total_questions', 0),
                            is_published=e.get('is_published', True),
                            created_by=admin.id
                        )
                        db.session.add(ex)
                        db.session.flush()
                    id_map[e['id']] = ex.id
                
                db.session.commit()
                
                # Check and populate questions for exams that have none
                for q in seed_data.get('questions', []):
                    target_exam_id = id_map.get(q['exam_id'])
                    if target_exam_id:
                        # Only add if not already in database
                        existing_q = Question.query.filter_by(exam_id=target_exam_id, question_text=q['question_text']).first()
                        if not existing_q:
                            qn = Question(
                                exam_id=target_exam_id,
                                question_text=q['question_text'],
                                question_type=q.get('question_type', 'mcq'),
                                option_a=q.get('option_a'),
                                option_b=q.get('option_b'),
                                option_c=q.get('option_c'),
                                option_d=q.get('option_d'),
                                correct_answer=q.get('correct_answer'),
                                explanation=q.get('explanation'),
                                order=q.get('order', 1)
                            )
                            db.session.add(qn)
                
                # Update total_questions count
                db.session.commit()
                for real_id in set(id_map.values()):
                    ex_obj = Exam.query.get(real_id)
                    if ex_obj:
                        ex_obj.total_questions = ex_obj.questions.count()
                db.session.commit()
                print("✓ Successfully synchronized courses_data.json into database!")
            except Exception as err:
                db.session.rollback()
                print(f"courses_data.json sync notice: {err}")
        elif Exam.query.count() == 0:
            create_sample_data()


def create_sample_data():
    admin = User.query.filter_by(username='admin').first()
    
    # Sample Exam 1 - CIT
    exam1 = Exam(
        title='CIT 211 - Introduction to Operating Systems',
        description='Mock examination covering processes, memory management, and file systems.',
        course_code='CIT211',
        faculty='Faculty of Sciences',
        duration_minutes=20,
        created_by=admin.id,
        is_published=True
    )
    db.session.add(exam1)
    db.session.flush()
    
    questions1 = [
        {
            'text': 'Which of the following is NOT a function of an operating system?',
            'a': 'Process management',
            'b': 'Memory management',
            'c': 'Compiling source code',
            'd': 'File management',
            'correct': 'C',
            'exp': 'Compiling is done by a compiler, not the operating system.'
        },
        {
            'text': 'What is the main purpose of a process scheduler?',
            'a': 'To allocate memory to processes',
            'b': 'To decide which process runs next on the CPU',
            'c': 'To manage file permissions',
            'd': 'To handle network connections',
            'correct': 'B',
            'exp': 'The process scheduler selects which ready process should be allocated the CPU next.'
        },
        {
            'text': 'In virtual memory, what is a page fault?',
            'a': 'When a process tries to access a page not currently in physical memory',
            'b': 'When the hard disk is full',
            'c': 'When a process terminates unexpectedly',
            'd': 'When CPU temperature is too high',
            'correct': 'A',
            'exp': 'A page fault occurs when the required page is not in RAM and must be loaded from disk.'
        },
        {
            'text': 'Which scheduling algorithm can lead to starvation?',
            'a': 'Round Robin',
            'b': 'First Come First Served',
            'c': 'Shortest Job First',
            'd': 'None of the above',
            'correct': 'C',
            'exp': 'Shortest Job First can cause long processes to wait indefinitely if short processes keep arriving.'
        },
        {
            'text': 'What does FIFO stand for in page replacement?',
            'a': 'First In First Out',
            'b': 'Fast Input Fast Output',
            'c': 'File Input File Output',
            'd': 'First Instruction First Operation',
            'correct': 'A',
            'exp': 'FIFO replaces the oldest page in memory (the one that arrived first).'
        },
    ]
    
    for i, q in enumerate(questions1):
        question = Question(
            exam_id=exam1.id,
            question_text=q['text'],
            option_a=q['a'],
            option_b=q['b'],
            option_c=q['c'],
            option_d=q['d'],
            correct_answer=q['correct'],
            explanation=q['exp'],
            order=i + 1
        )
        db.session.add(question)
    
    exam1.total_questions = len(questions1)
    
    # Sample Exam 2 - GST
    exam2 = Exam(
        title='GST 101 - Use of English and Communication Skills',
        description='Practice questions on grammar, comprehension and communication.',
        course_code='GST101',
        faculty='Faculty of Arts',
        duration_minutes=15,
        created_by=admin.id,
        is_published=True
    )
    db.session.add(exam2)
    db.session.flush()
    
    questions2 = [
        {
            'text': 'Which of the following is a complex sentence?',
            'a': 'She sang and danced.',
            'b': 'Although it was raining, we went out.',
            'c': 'John is tall.',
            'd': 'Come here.',
            'correct': 'B',
            'exp': 'A complex sentence has one independent clause and at least one dependent clause.'
        },
        {
            'text': 'The opposite of "benevolent" is:',
            'a': 'Kind',
            'b': 'Malevolent',
            'c': 'Generous',
            'd': 'Friendly',
            'correct': 'B',
            'exp': 'Benevolent means kind/generous; malevolent means wishing harm.'
        },
        {
            'text': 'Which word is correctly spelt?',
            'a': 'Accomodation',
            'b': 'Acommodation',
            'c': 'Accommodation',
            'd': 'Acomodation',
            'correct': 'C',
            'exp': 'Accommodation has double "c" and double "m".'
        },
        {
            'text': 'Identify the figure of speech: "The classroom was a zoo."',
            'a': 'Simile',
            'b': 'Metaphor',
            'c': 'Personification',
            'd': 'Hyperbole',
            'correct': 'B',
            'exp': 'It is a metaphor because it directly compares the classroom to a zoo without using "like" or "as".'
        },
    ]
    
    for i, q in enumerate(questions2):
        question = Question(
            exam_id=exam2.id,
            question_text=q['text'],
            option_a=q['a'],
            option_b=q['b'],
            option_c=q['c'],
            option_d=q['d'],
            correct_answer=q['correct'],
            explanation=q['exp'],
            order=i + 1
        )
        db.session.add(question)
    
    exam2.total_questions = len(questions2)
    
    # Sample Exam 3 - EDU
    exam3 = Exam(
        title='EDU 212 - Psychology of Learning',
        description='Key concepts in educational psychology and learning theories.',
        course_code='EDU212',
        faculty='Faculty of Education',
        duration_minutes=25,
        created_by=admin.id,
        is_published=True
    )
    db.session.add(exam3)
    db.session.flush()
    
    questions3 = [
        {
            'text': 'Who is regarded as the father of classical conditioning?',
            'a': 'B.F. Skinner',
            'b': 'Ivan Pavlov',
            'c': 'Jean Piaget',
            'd': 'Albert Bandura',
            'correct': 'B',
            'exp': 'Ivan Pavlov discovered classical conditioning through his experiments with dogs.'
        },
        {
            'text': 'Operant conditioning was mainly developed by:',
            'a': 'Ivan Pavlov',
            'b': 'John Watson',
            'c': 'B.F. Skinner',
            'd': 'Lev Vygotsky',
            'correct': 'C',
            'exp': 'B.F. Skinner is the major proponent of operant conditioning.'
        },
        {
            'text': 'In Piaget\'s theory, the stage where children develop object permanence is:',
            'a': 'Sensorimotor',
            'b': 'Preoperational',
            'c': 'Concrete operational',
            'd': 'Formal operational',
            'correct': 'A',
            'exp': 'Object permanence develops during the sensorimotor stage (0-2 years).'
        },
    ]
    
    for i, q in enumerate(questions3):
        question = Question(
            exam_id=exam3.id,
            question_text=q['text'],
            option_a=q['a'],
            option_b=q['b'],
            option_c=q['c'],
            option_d=q['d'],
            correct_answer=q['correct'],
            explanation=q['exp'],
            order=i + 1
        )
        db.session.add(question)
    
    exam3.total_questions = len(questions3)
    
    db.session.commit()
    print("✓ Sample NOUN exams and questions created")


with app.app_context():
    init_db()


if __name__ == '__main__':
    print("\n🚀 NOUN Exam Mock Platform is running!")
    print("   Open: http://127.0.0.1:5000")
    print("\nDefault accounts:")
    print("   Admin   → admin / admin123")
    print("   Teacher → teacher1 / teacher123")
    print("   (Register as student from the website)\n")
    app.run(debug=True, host='0.0.0.0', port=5000)