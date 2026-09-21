"""
Gemini-powered generation of flashcards and test questions from a topic's
uploaded notes.

Needs a GEMINI_API_KEY (free key from https://aistudio.google.com/apikey)
set in a .env file at the project root -- see .env.example. app.py loads
that .env file on startup, so this module just reads the environment.
"""
import json
import os
import time

from google import genai
from google.genai import types

MODEL_NAME = os.environ.get('CAT_GEMINI_MODEL', 'gemini-3.6-flash')
MAX_NOTES_CHARS = 60000  


class AIGenerationError(Exception):
    """Anything that stops us turning notes into flashcards/questions --
    app.py catches this and turns it into a clean error response instead
    of a 500."""


api_key = os.environ.get('GEMINI_API_KEY')
if not api_key:
    raise AIGenerationError('GEMINI_API_KEY is not set. Add it to a .env file.')

client = genai.Client(api_key=api_key)

def _call_gemini_with_retry(**kwargs):
    """Retries a few times on transient server errors (like a 503
    'model overloaded') before giving up for real."""
    max_attempts = 5
    delay = 2  # seconds
    for attempt in range(1, max_attempts + 1):
        try:
            return client.models.generate_content(**kwargs)
        except Exception as e:
            transient = 'UNAVAILABLE' in str(e) or '503' in str(e)
            if not transient or attempt == max_attempts:
                raise
            time.sleep(delay)
            delay *= 2  # 2s, then 4s




FLASHCARD_SCHEMA = {
    'type': 'ARRAY',
    'items': {
        'type': 'OBJECT',
        'properties': {
            'front_text': {'type': 'STRING', 'description': 'The term or question side of the card'},
            'back_text': {'type': 'STRING', 'description': 'The definition or answer side of the card'},
        },
        'required': ['front_text', 'back_text'],
    },
}

QUESTION_SCHEMA = {
    'type': 'ARRAY',
    'items': {
        'type': 'OBJECT',
        'properties': {
            'question_type': {'type': 'STRING', 'enum': ['mcq', 'short']},
            'question_text': {'type': 'STRING'},
            'options': {
                'type': 'ARRAY', 'items': {'type': 'STRING'},
                'description': 'Exactly 4 options for mcq questions, [] for short questions',
            },
            'correct_option': {
                'type': 'INTEGER',
                'description': 'Index (0-3) of the correct option for mcq questions, 0 for short questions',
            },
            'keywords': {
                'type': 'ARRAY', 'items': {'type': 'STRING'},
                'description': '2-5 keywords a correct short answer should contain, [] for mcq questions',
            },
            'model_answer': {
                'type': 'STRING',
                'description': 'A 1-2 sentence reference answer for short questions, "" for mcq questions',
            },
            'marks': {'type': 'INTEGER'},
        },
        'required': [
            'question_type', 'question_text', 'options', 'correct_option',
            'keywords', 'model_answer', 'marks',
        ],
    },
}


def _generate_json(prompt, schema):
    try:
                response = _call_gemini_with_retry(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type='application/json',
                response_schema=schema,
                temperature=0.7,
            ),
        )
    except AIGenerationError:
        raise
    except Exception as e:
        raise AIGenerationError(f'Gemini request failed: {e}')

    try:
        return json.loads(response.text)
    except (ValueError, TypeError) as e:
        raise AIGenerationError(f'Gemini returned something that was not valid JSON: {e}')


def generate_flashcards(notes_text, topic_name, count=8):
    if not notes_text.strip():
        raise AIGenerationError('This topic has no notes to generate from yet -- upload some first.')

    prompt = (
        f'You are creating study flashcards for a "{topic_name}" class. '
        f'Based ONLY on the notes below, generate exactly {count} flashcards. '
        f'Each front_text should be a short term or question; each back_text should be a concise, '
        f'accurate answer or definition drawn from the notes. Do not invent facts that are not in '
        f'the notes.\n\n--- NOTES ---\n{notes_text[:MAX_NOTES_CHARS]}'
    )
    cards = _generate_json(prompt, FLASHCARD_SCHEMA)
    return [
        {'front_text': c['front_text'].strip(), 'back_text': c['back_text'].strip()}
        for c in cards if c.get('front_text') and c.get('back_text')
    ]


def generate_questions(notes_text, topic_name, count=6):
    if not notes_text.strip():
        raise AIGenerationError('This topic has no notes to generate from yet -- upload some first.')

    prompt = (
        f'You are creating a graded test for a "{topic_name}" class. '
        f'Based ONLY on the notes below, generate exactly {count} questions, mixing question_type '
        f'"mcq" and "short" (aim for roughly half of each). '
        f'For "mcq": provide exactly 4 plausible options in "options" and the correct one\'s index '
        f'(0-3) in "correct_option"; leave "keywords" as [] and "model_answer" as "". '
        f'For "short": leave "options" as [] and "correct_option" as 0; give 2-5 short "keywords" '
        f'a correct answer should contain, and a 1-2 sentence "model_answer". '
        f'Set "marks" to 1 for mcq and 2 for short. Do not invent facts that are not in the notes.\n\n'
        f'--- NOTES ---\n{notes_text[:MAX_NOTES_CHARS]}'
    )
    questions = _generate_json(prompt, QUESTION_SCHEMA)
    return [
        q for q in questions
        if q.get('question_type') in ('mcq', 'short') and q.get('question_text')
    ]
