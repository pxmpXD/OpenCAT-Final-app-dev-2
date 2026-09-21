
import os
import json
from functools import wraps

from dotenv import load_dotenv
load_dotenv()  

from flask import Flask, request, jsonify, session, send_from_directory, render_template
from werkzeug.utils import secure_filename

from database import get_db, init_db
from text_extract import extract_text
from grading import grade_answer
from ai_generate import generate_flashcards, generate_questions, AIGenerationError

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.txt', '.pptx', '.png', '.jpg', '.jpeg'}
ADMIN_PASSWORD = os.environ.get('CAT_ADMIN_PASSWORD', 'admin123')

os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get('CAT_SECRET_KEY', 'dev-secret-change-me')
app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024  # 25MB per uploaded file



@app.route('/')
def home():
    return render_template('index.html')


@app.route('/student')
def student_page():
    return render_template('student.html')


@app.route('/teacher')
def teacher_page():
    return render_template('teacher.html')



def teacher_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get('is_teacher'):
            return jsonify({'error': 'Teacher login required'}), 401
        return fn(*args, **kwargs)
    return wrapper


def row_to_dict(row):
    return dict(row) if row else None


def _topic_notes_text(db, topic_id):
    """Concatenates every uploaded note's extracted text for a topic --
    this is what gets sent to Gemini as the source material."""
    rows = db.execute(
        'SELECT extracted_text FROM notes_files WHERE topic_id = ? ORDER BY uploaded_at', (topic_id,)
    ).fetchall()
    return '\n\n'.join(r['extracted_text'] for r in rows if r['extracted_text'])



@app.route('/api/teacher/login', methods=['POST'])
def teacher_login():
    data = request.get_json(force=True)
    if data.get('password') == ADMIN_PASSWORD:
        session['is_teacher'] = True
        return jsonify({'ok': True})
    return jsonify({'error': 'Incorrect password'}), 403


@app.route('/api/teacher/logout', methods=['POST'])
def teacher_logout():
    session.pop('is_teacher', None)
    return jsonify({'ok': True})


@app.route('/api/students/login', methods=['POST'])
def student_login():
    """No password -- a student just gives their name + grade. Keeps things
    simple for a classroom setting. Re-using the same name+grade logs back
    into the same history."""
    data = request.get_json(force=True)
    name = (data.get('name') or '').strip()
    grade_id = data.get('grade_id')
    if not name or not grade_id:
        return jsonify({'error': 'Name and grade are required'}), 400

    db = get_db()
    existing = db.execute(
        'SELECT * FROM students WHERE name = ? AND grade_id = ?', (name, grade_id)
    ).fetchone()
    if existing:
        student = existing
    else:
        cur = db.execute('INSERT INTO students (name, grade_id) VALUES (?, ?)', (name, grade_id))
        db.commit()
        student = db.execute('SELECT * FROM students WHERE id = ?', (cur.lastrowid,)).fetchone()
    db.close()

    session['student_id'] = student['id']
    return jsonify(row_to_dict(student))



@app.route('/api/grades')
def list_grades():
    db = get_db()
    grades = db.execute('SELECT * FROM grades ORDER BY name').fetchall()
    db.close()
    return jsonify([row_to_dict(g) for g in grades])


@app.route('/api/topics')
def list_topics():
    grade_id = request.args.get('grade_id')
    db = get_db()
    if grade_id:
        topics = db.execute('SELECT * FROM topics WHERE grade_id = ? ORDER BY name', (grade_id,)).fetchall()
    else:
        topics = db.execute('SELECT * FROM topics ORDER BY name').fetchall()
    db.close()
    return jsonify([row_to_dict(t) for t in topics])


@app.route('/api/topics', methods=['POST'])
@teacher_required
def create_topic():
    data = request.get_json(force=True)
    name = (data.get('name') or '').strip()
    grade_id = data.get('grade_id')
    description = data.get('description', '')
    if not name or not grade_id:
        return jsonify({'error': 'name and grade_id are required'}), 400

    db = get_db()
    cur = db.execute('INSERT INTO topics (grade_id, name, description) VALUES (?, ?, ?)',
                      (grade_id, name, description))
    db.commit()
    topic = db.execute('SELECT * FROM topics WHERE id = ?', (cur.lastrowid,)).fetchone()
    db.close()
    return jsonify(row_to_dict(topic)), 201


@app.route('/api/topics/<int:topic_id>', methods=['DELETE'])
@teacher_required
def delete_topic(topic_id):
    db = get_db()
    db.execute('DELETE FROM topics WHERE id = ?', (topic_id,))
    db.commit()
    db.close()
    return jsonify({'ok': True})



@app.route('/api/topics/<int:topic_id>/notes')
def list_notes(topic_id):
    db = get_db()
    notes = db.execute(
        '''SELECT id, topic_id, original_filename, file_type, uploaded_at
           FROM notes_files WHERE topic_id = ? ORDER BY uploaded_at DESC''',
        (topic_id,)
    ).fetchall()
    db.close()
    return jsonify([row_to_dict(n) for n in notes])


@app.route('/api/topics/<int:topic_id>/notes/upload', methods=['POST'])
@teacher_required
def upload_note(topic_id):
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Empty filename'}), 400

    original_filename = secure_filename(file.filename)
    ext = os.path.splitext(original_filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({'error': f'File type {ext} is not allowed'}), 400

    
    stored_filename = f'{topic_id}_{os.urandom(4).hex()}_{original_filename}'
    filepath = os.path.join(UPLOAD_DIR, stored_filename)
    file.save(filepath)

    extracted = extract_text(filepath, ext)

    db = get_db()
    cur = db.execute(
        '''INSERT INTO notes_files (topic_id, original_filename, stored_filename, file_type, extracted_text)
           VALUES (?, ?, ?, ?, ?)''',
        (topic_id, original_filename, stored_filename, ext, extracted)
    )
    db.commit()
    note = db.execute(
        'SELECT id, topic_id, original_filename, file_type, uploaded_at FROM notes_files WHERE id = ?',
        (cur.lastrowid,)
    ).fetchone()
    db.close()
    return jsonify(row_to_dict(note)), 201


@app.route('/api/notes/<int:note_id>/download')
def download_note(note_id):
    db = get_db()
    note = db.execute('SELECT * FROM notes_files WHERE id = ?', (note_id,)).fetchone()
    db.close()
    if not note:
        return jsonify({'error': 'Not found'}), 404
    return send_from_directory(
        UPLOAD_DIR, note['stored_filename'], as_attachment=True,
        download_name=note['original_filename']
    )


@app.route('/api/notes/<int:note_id>', methods=['DELETE'])
@teacher_required
def delete_note(note_id):
    db = get_db()
    note = db.execute('SELECT * FROM notes_files WHERE id = ?', (note_id,)).fetchone()
    if note:
        filepath = os.path.join(UPLOAD_DIR, note['stored_filename'])
        if os.path.exists(filepath):
            os.remove(filepath)
        db.execute('DELETE FROM notes_files WHERE id = ?', (note_id,))
        db.commit()
    db.close()
    return jsonify({'ok': True})



@app.route('/api/topics/<int:topic_id>/questions', methods=['GET'])
@teacher_required
def list_questions(topic_id):
    """Teacher-only view -- includes correct answers."""
    db = get_db()
    questions = db.execute('SELECT * FROM questions WHERE topic_id = ?', (topic_id,)).fetchall()
    db.close()
    out = []
    for q in questions:
        d = row_to_dict(q)
        if d['options']:
            d['options'] = json.loads(d['options'])
        if d['keywords']:
            d['keywords'] = json.loads(d['keywords'])
        out.append(d)
    return jsonify(out)


@app.route('/api/topics/<int:topic_id>/questions', methods=['POST'])
@teacher_required
def add_question(topic_id):
    data = request.get_json(force=True)
    qtype = data.get('question_type')
    text = (data.get('question_text') or '').strip()
    marks = data.get('marks', 1)

    if qtype not in ('mcq', 'short') or not text:
        return jsonify({'error': 'question_type must be mcq or short, and question_text is required'}), 400

    options = json.dumps(data.get('options', [])) if qtype == 'mcq' else None
    correct_option = data.get('correct_option') if qtype == 'mcq' else None
    keywords = json.dumps(data.get('keywords', [])) if qtype == 'short' else None
    model_answer = data.get('model_answer') if qtype == 'short' else None

    db = get_db()
    cur = db.execute(
        '''INSERT INTO questions
           (topic_id, question_type, question_text, options, correct_option, keywords, model_answer, marks)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
        (topic_id, qtype, text, options, correct_option, keywords, model_answer, marks)
    )
    db.commit()
    question = db.execute('SELECT * FROM questions WHERE id = ?', (cur.lastrowid,)).fetchone()
    db.close()
    return jsonify(row_to_dict(question)), 201


@app.route('/api/questions/<int:question_id>', methods=['DELETE'])
@teacher_required
def delete_question(question_id):
    db = get_db()
    db.execute('DELETE FROM questions WHERE id = ?', (question_id,))
    db.commit()
    db.close()
    return jsonify({'ok': True})


@app.route('/api/topics/<int:topic_id>/generate-questions', methods=['POST'])
@teacher_required
def ai_generate_questions(topic_id):
    """Uses Gemini to turn this topic's uploaded notes into a batch of
    mcq/short test questions, and saves them straight into the topic."""
    data = request.get_json(silent=True) or {}
    count = max(1, min(int(data.get('count', 6)), 20))

    db = get_db()
    topic = db.execute('SELECT * FROM topics WHERE id = ?', (topic_id,)).fetchone()
    if not topic:
        db.close()
        return jsonify({'error': 'Topic not found'}), 404

    notes_text = _topic_notes_text(db, topic_id)
    try:
        questions = generate_questions(notes_text, topic['name'], count)
    except AIGenerationError as e:
        db.close()
        return jsonify({'error': str(e)}), 400

    if not questions:
        db.close()
        return jsonify({'error': 'Gemini did not return any questions -- try again or add more detailed notes'}), 502

    inserted_ids = []
    for q in questions:
        qtype = q['question_type']
        options = json.dumps(q.get('options', [])) if qtype == 'mcq' else None
        correct_option = q.get('correct_option') if qtype == 'mcq' else None
        keywords = json.dumps(q.get('keywords', [])) if qtype == 'short' else None
        model_answer = q.get('model_answer') if qtype == 'short' else None
        marks = q.get('marks') or (1 if qtype == 'mcq' else 2)

        cur = db.execute(
            '''INSERT INTO questions
               (topic_id, question_type, question_text, options, correct_option, keywords, model_answer, marks)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (topic_id, qtype, q['question_text'], options, correct_option, keywords, model_answer, marks)
        )
        inserted_ids.append(cur.lastrowid)
    db.commit()

    placeholders = ','.join(['?'] * len(inserted_ids))
    rows = db.execute(f'SELECT * FROM questions WHERE id IN ({placeholders})', inserted_ids).fetchall()
    db.close()

    out = []
    for r in rows:
        d = row_to_dict(r)
        if d['options']:
            d['options'] = json.loads(d['options'])
        if d['keywords']:
            d['keywords'] = json.loads(d['keywords'])
        out.append(d)
    return jsonify(out), 201



@app.route('/api/topics/<int:topic_id>/flashcards')
def list_flashcards(topic_id):
    """Both teacher and student use this -- flashcards have no 'correct
    answer' to hide, they're just front/back study cards."""
    db = get_db()
    cards = db.execute(
        'SELECT * FROM flashcards WHERE topic_id = ? ORDER BY created_at', (topic_id,)
    ).fetchall()
    db.close()
    return jsonify([row_to_dict(c) for c in cards])


@app.route('/api/topics/<int:topic_id>/flashcards', methods=['POST'])
@teacher_required
def add_flashcard(topic_id):
    data = request.get_json(force=True)
    front_text = (data.get('front_text') or '').strip()
    back_text = (data.get('back_text') or '').strip()
    if not front_text or not back_text:
        return jsonify({'error': 'front_text and back_text are required'}), 400

    db = get_db()
    cur = db.execute(
        'INSERT INTO flashcards (topic_id, front_text, back_text) VALUES (?, ?, ?)',
        (topic_id, front_text, back_text)
    )
    db.commit()
    card = db.execute('SELECT * FROM flashcards WHERE id = ?', (cur.lastrowid,)).fetchone()
    db.close()
    return jsonify(row_to_dict(card)), 201


@app.route('/api/flashcards/<int:flashcard_id>', methods=['DELETE'])
@teacher_required
def delete_flashcard(flashcard_id):
    db = get_db()
    db.execute('DELETE FROM flashcards WHERE id = ?', (flashcard_id,))
    db.commit()
    db.close()
    return jsonify({'ok': True})


@app.route('/api/topics/<int:topic_id>/generate-flashcards', methods=['POST'])
@teacher_required
def ai_generate_flashcards(topic_id):
    """Uses Gemini to turn this topic's uploaded notes into a batch of
    front/back flashcards, and saves them straight into the topic."""
    data = request.get_json(silent=True) or {}
    count = max(1, min(int(data.get('count', 8)), 20))

    db = get_db()
    topic = db.execute('SELECT * FROM topics WHERE id = ?', (topic_id,)).fetchone()
    if not topic:
        db.close()
        return jsonify({'error': 'Topic not found'}), 404

    notes_text = _topic_notes_text(db, topic_id)
    try:
        cards = generate_flashcards(notes_text, topic['name'], count)
    except AIGenerationError as e:
        db.close()
        return jsonify({'error': str(e)}), 400

    if not cards:
        db.close()
        return jsonify({'error': 'Gemini did not return any flashcards -- try again or add more detailed notes'}), 502

    inserted_ids = []
    for c in cards:
        cur = db.execute(
            'INSERT INTO flashcards (topic_id, front_text, back_text) VALUES (?, ?, ?)',
            (topic_id, c['front_text'], c['back_text'])
        )
        inserted_ids.append(cur.lastrowid)
    db.commit()

    placeholders = ','.join(['?'] * len(inserted_ids))
    rows = db.execute(f'SELECT * FROM flashcards WHERE id IN ({placeholders})', inserted_ids).fetchall()
    db.close()
    return jsonify([row_to_dict(r) for r in rows]), 201


@app.route('/api/topics/<int:topic_id>/quiz')
def get_quiz(topic_id):
    """Student-facing version -- never leaks correct answers or keywords."""
    db = get_db()
    rows = db.execute('SELECT * FROM questions WHERE topic_id = ?', (topic_id,)).fetchall()
    db.close()
    quiz = []
    for r in rows:
        item = {
            'id': r['id'], 'question_type': r['question_type'],
            'question_text': r['question_text'], 'marks': r['marks']
        }
        if r['question_type'] == 'mcq':
            item['options'] = json.loads(r['options'] or '[]')
        quiz.append(item)
    return jsonify(quiz)



@app.route('/api/topics/<int:topic_id>/submit', methods=['POST'])
def submit_quiz(topic_id):
    student_id = session.get('student_id')
    if not student_id:
        return jsonify({'error': 'Student login required'}), 401

    data = request.get_json(force=True)
    answers = data.get('answers', [])  # [{question_id, answer}]

    db = get_db()
    questions = {
        q['id']: q for q in db.execute('SELECT * FROM questions WHERE topic_id = ?', (topic_id,)).fetchall()
    }
    total_marks = sum(q['marks'] for q in questions.values())
    score = 0
    results = []

    cur = db.execute('INSERT INTO attempts (student_id, topic_id, score, total) VALUES (?, ?, ?, ?)',
                      (student_id, topic_id, 0, total_marks))
    attempt_id = cur.lastrowid

    for ans in answers:
        qid = ans.get('question_id')
        question = questions.get(qid)
        if not question:
            continue
        student_answer = ans.get('answer')
        is_correct, marks_awarded, needs_review = grade_answer(question, student_answer)
        score += marks_awarded

        db.execute(
            '''INSERT INTO attempt_answers
               (attempt_id, question_id, student_answer, is_correct, marks_awarded, needs_review)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (attempt_id, qid, json.dumps(student_answer), is_correct, marks_awarded, int(needs_review))
        )
        results.append({
            'question_id': qid, 'is_correct': is_correct,
            'marks_awarded': marks_awarded, 'needs_review': needs_review
        })

    db.execute('UPDATE attempts SET score = ? WHERE id = ?', (score, attempt_id))
    db.commit()
    db.close()

    return jsonify({'attempt_id': attempt_id, 'score': score, 'total': total_marks, 'results': results})



@app.route('/api/students/<int:student_id>/weakpoints')
def student_weakpoints(student_id):
    db = get_db()

    by_topic = db.execute('''
        SELECT t.id AS topic_id, t.name AS topic_name,
               SUM(CASE WHEN aa.is_correct = 0 THEN 1 ELSE 0 END) AS wrong,
               COUNT(aa.id) AS attempted
        FROM attempt_answers aa
        JOIN attempts a ON aa.attempt_id = a.id
        JOIN questions q ON aa.question_id = q.id
        JOIN topics t ON q.topic_id = t.id
        WHERE a.student_id = ?
        GROUP BY t.id
        HAVING wrong > 0
        ORDER BY wrong DESC
    ''', (student_id,)).fetchall()

    by_question = db.execute('''
        SELECT q.id AS question_id, q.question_text, t.name AS topic_name,
               SUM(CASE WHEN aa.is_correct = 0 THEN 1 ELSE 0 END) AS wrong,
               COUNT(aa.id) AS attempted
        FROM attempt_answers aa
        JOIN attempts a ON aa.attempt_id = a.id
        JOIN questions q ON aa.question_id = q.id
        JOIN topics t ON q.topic_id = t.id
        WHERE a.student_id = ?
        GROUP BY q.id
        HAVING wrong > 0
        ORDER BY wrong DESC
    ''', (student_id,)).fetchall()

    db.close()
    return jsonify({
        'by_topic': [row_to_dict(r) for r in by_topic],
        'by_question': [row_to_dict(r) for r in by_question]
    })


@app.route('/api/students/<int:student_id>/attempts')
def student_attempts(student_id):
    db = get_db()
    attempts = db.execute('''
        SELECT a.*, t.name AS topic_name FROM attempts a
        JOIN topics t ON a.topic_id = t.id
        WHERE a.student_id = ? ORDER BY a.taken_at DESC
    ''', (student_id,)).fetchall()
    db.close()
    return jsonify([row_to_dict(r) for r in attempts])


@app.route('/api/teacher/class-weakpoints')
@teacher_required
def class_weakpoints():
    """Same idea as student_weakpoints, but aggregated across a whole grade
    so the teacher can see which topics the class as a whole is struggling
    with -- this is what makes the tool useful for lesson planning."""
    grade_id = request.args.get('grade_id')
    db = get_db()
    query = '''
        SELECT t.name AS topic_name,
               SUM(CASE WHEN aa.is_correct = 0 THEN 1 ELSE 0 END) AS wrong,
               COUNT(aa.id) AS attempted
        FROM attempt_answers aa
        JOIN attempts a ON aa.attempt_id = a.id
        JOIN questions q ON aa.question_id = q.id
        JOIN topics t ON q.topic_id = t.id
        JOIN students s ON a.student_id = s.id
    '''
    params = []
    if grade_id:
        query += ' WHERE s.grade_id = ?'
        params.append(grade_id)
    query += ' GROUP BY t.id ORDER BY wrong DESC'
    rows = db.execute(query, params).fetchall()
    db.close()
    return jsonify([row_to_dict(r) for r in rows])


if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)
