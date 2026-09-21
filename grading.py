
import re
import json


def normalize(text):
    text = (text or '').lower().strip()
    text = re.sub(r'[^\w\s]', '', text)
    return text


def grade_mcq(question, student_answer_index):
    correct = question['correct_option']
    try:
        is_correct = int(student_answer_index) == int(correct)
    except (TypeError, ValueError):
        is_correct = False
    marks_awarded = question['marks'] if is_correct else 0
    return is_correct, marks_awarded, False


def grade_short(question, student_answer_text):
    keywords = json.loads(question['keywords'] or '[]')
    marks = question['marks']

    if not keywords:
        
        return None, 0, True

    norm_answer = normalize(student_answer_text)
    hits = sum(1 for kw in keywords if normalize(kw) in norm_answer)
    ratio = hits / len(keywords)

    if ratio >= 0.6:
        return True, marks, False
    elif ratio >= 0.3:
        partial = round(marks * ratio, 1)
        return None, partial, True
    else:
        return False, 0, False


def grade_answer(question, student_answer):
    if question['question_type'] == 'mcq':
        return grade_mcq(question, student_answer)
    else:
        return grade_short(question, student_answer)
