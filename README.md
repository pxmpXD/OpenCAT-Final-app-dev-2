# CAT Study App

A web app that lets a CAT (Computer Applications Technology) teacher upload notes
for Grade 10-12, and lets students study those notes, take practice tests
built from them, and see exactly which topics/questions they keep getting
wrong so they know what to revise.

## Why I built this

CAT theory covers a lot of ground across three grades, and students often
don't find out they're weak on a topic until the exam. This app gives
students a low-pressure way to self-test against the actual class notes, and
gives the teacher a quick view of which topics the whole class is struggling
with -- useful for deciding what to go over again in the next lesson.

## How it works

- **Teacher** drags note files (PDF, DOCX, TXT, PPTX, images) straight into a
  topic. No forms, no manual typing -- just drop the file in.
- **Teacher** builds a short test per topic: multiple choice questions
  (auto-graded exactly) and short-answer questions (auto-graded by keyword
  matching, with anything the system isn't confident about flagged for the
  teacher to check manually).
- **Teacher** can also add quick **flashcards** per topic (front/back study
  cards) -- separate from the graded test, purely for self-study.
- **Teacher** can hit **"Generate from Notes"** to have Gemini turn a
  topic's uploaded notes straight into a batch of questions or flashcards,
  instead of writing every one by hand.
- **Student** logs in with just their name and grade, works through the
  notes, flips through flashcards, and takes the test whenever they're ready.
- After each test, the app tracks every wrong answer and works out **which
  topics** and **which specific questions** a student keeps struggling with,
  so revision time is spent where it actually helps.

## Tech stack

| Layer    | Choice                          | Why |
|----------|----------------------------------|-----|
| Backend  | Python (Flask)                   | Small, readable, easy to extend -- matches the course |
| Database | MySQL                            | Matches the MySQL environment used in class |
| AI       | Google Gemini (`gemini-2.5-flash` via the `google-genai` SDK) | Generates flashcards/questions from notes, constrained to strict JSON output |
| Frontend | Vanilla HTML/CSS/JS (no framework)| Keeps the build simple; styling is being added separately |

## Project structure

```
cat-study-app/
├── app.py              # Flask app + all API routes
├── database.py         # DB connection + first-time setup
├── grading.py          # Auto-grading logic (MCQ + short answer)
├── ai_generate.py       # Gemini-powered generation of flashcards/questions from notes
├── text_extract.py      # Pulls text out of uploaded PDFs/DOCX for storage
├── schema.sql           # Database tables
├── requirements.txt
├── .env.example          # Copy to .env and fill in your MySQL/Gemini credentials
├── templates/            # index.html, student.html, teacher.html
├── static/
│   ├── css/style.css
│   └── js/               # api.js, student.js, teacher.js
└── uploads/               # Uploaded note files land here (gitignored)
```

## Running it locally

### 1. Database (MySQL)

This app connects to a MySQL server -- the same one you'd connect to in
MySQL Workbench or the `mysql` CLI. You need MySQL Server running locally
(MySQL Community Server, XAMPP/WAMP's bundled MySQL, etc. all work).

You do **not** need to create the database or tables by hand -- `app.py`
calls `init_db()` on startup, which creates the `cat_study_app` database and
all tables automatically the first time it runs. If you'd rather run
`schema.sql` yourself in Workbench first, that works too (every statement is
`IF NOT EXISTS`, so it's safe to run more than once).

By default the app connects as `root` with **no password** on
`localhost:3306`. If your setup is different, set these environment
variables before running the app:

```bash
export CAT_MYSQL_HOST="localhost"
export CAT_MYSQL_PORT="3306"
export CAT_MYSQL_USER="root"
export CAT_MYSQL_PASSWORD="your_mysql_password"
export CAT_MYSQL_DATABASE="cat_study_app"
```

(On Windows/PowerShell, use `$env:CAT_MYSQL_HOST = "..."` instead of
`export`.)

### 2. Gemini API key (for AI-generated flashcards/questions)

The "Generate from Notes" feature calls Google's Gemini API, which needs its
own free API key -- separate from your MySQL setup.

1. Grab a free key at https://aistudio.google.com/apikey
2. Copy `.env.example` to a new file named `.env` in the project root
3. Paste your key in: `GEMINI_API_KEY=your-key-here`

`app.py` loads `.env` automatically on startup (via `python-dotenv`), and
`.env` is already in `.gitignore` so your key never gets committed. You can
put your MySQL settings from step 1 in `.env` too instead of `export`-ing
them, if you'd rather keep everything in one file.

If you skip this step, the rest of the app works fine -- you'll just get a
clear error message if you click "Generate from Notes" without a key set.

### 3. App

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Then open http://127.0.0.1:5000 in your browser.

The default teacher password is `admin123`. Change it before deploying by
setting an environment variable:

```bash
export CAT_ADMIN_PASSWORD="your-new-password"
export CAT_SECRET_KEY="some-random-string"
```

## Auto-grading approach

- **Multiple choice**: exact match against the correct option. No ambiguity.
- **Short answer**: the teacher supplies a small list of keywords when
  writing the question (e.g. for "What is RAM?" → `volatile, temporary,
  memory`). The student's answer is checked for how many of those keywords
  it contains:
  - 60%+ matched → marked correct automatically
  - 30-59% matched → partial marks awarded, and the answer is flagged
    `needs_review` so the teacher can confirm it by eye
  - under 30% matched → marked incorrect

  This is a simple, explainable system rather than a black-box AI grader --
  the teacher can always see and override what the system decided.

## Known limitations / possible improvements

- Short-answer grading is keyword-based, not true natural language
  understanding -- a well-worded answer using different vocabulary could be
  under-scored. A future version could use an NLP similarity model.
- No password/authentication for students -- fine for a low-stakes classroom
  tool, not suitable if graded marks needed to be tamper-proof.
- Extracted note text isn't surfaced in the UI yet (e.g. searching notes by
  keyword) -- the data is captured and ready for that feature.
- AI-generated questions/flashcards are only as good as the uploaded notes,
  and are added straight into the topic rather than held for review first --
  worth reading through what Gemini produced and deleting anything off before
  students see it.

## License

MIT
