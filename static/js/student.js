let currentStudent = null;
let currentQuizTopicId = null;
let currentQuizQuestions = [];

const $ = (id) => document.getElementById(id);

function showSection(id) {
  ['login-section', 'main-section', 'quiz-section', 'results-section', 'weakpoints-section', 'flashcards-section']
    .forEach((s) => $(s).classList.toggle('hidden', s !== id));
}


async function loadGrades() {
  const grades = await apiGet('/api/grades');
  const select = $('student-grade');
  select.innerHTML = grades.map((g) => `<option value="${g.id}">${g.name}</option>`).join('');
}

$('login-btn').addEventListener('click', async () => {
  const name = $('student-name').value.trim();
  const gradeId = $('student-grade').value;
  if (!name) return alert('Please enter your name');

  currentStudent = await apiPost('/api/students/login', { name, grade_id: gradeId });
  $('welcome-name').textContent = currentStudent.name;
  showSection('main-section');
  loadTopics(gradeId);
});


async function loadTopics(gradeId) {
  const topics = await apiGet(`/api/topics?grade_id=${gradeId}`);
  const container = $('topics-list');

  if (topics.length === 0) {
    container.innerHTML = '<p>No topics have been added for your grade yet.</p>';
    return;
  }

  container.innerHTML = '';
  for (const topic of topics) {
    const notes = await apiGet(`/api/topics/${topic.id}/notes`);
    const div = document.createElement('div');
    div.className = 'card';
    div.innerHTML = `
      <h3>${topic.name}</h3>
      <p>${topic.description || ''}</p>
      <strong>Notes:</strong>
      ${notes.length ? '<ul>' + notes.map((n) =>
        `<li><a href="/api/notes/${n.id}/download">${n.original_filename}</a></li>`).join('') + '</ul>'
        : '<p>No notes uploaded yet.</p>'}
      <button data-topic-id="${topic.id}" data-topic-name="${topic.name}" class="start-quiz-btn">Start Test</button>
      <button data-topic-id="${topic.id}" data-topic-name="${topic.name}" class="study-flashcards-btn">Study Flashcards</button>
    `;
    container.appendChild(div);
  }

  document.querySelectorAll('.start-quiz-btn').forEach((btn) => {
    btn.addEventListener('click', () => startQuiz(btn.dataset.topicId, btn.dataset.topicName));
  });
  document.querySelectorAll('.study-flashcards-btn').forEach((btn) => {
    btn.addEventListener('click', () => startFlashcards(btn.dataset.topicId, btn.dataset.topicName));
  });
}


async function startQuiz(topicId, topicName) {
  currentQuizQuestions = await apiGet(`/api/topics/${topicId}/quiz`);
  if (currentQuizQuestions.length === 0) {
    alert('This topic has no test questions yet.');
    return;
  }
  currentQuizTopicId = topicId;
  $('quiz-title').textContent = `Test: ${topicName}`;

  $('quiz-questions').innerHTML = currentQuizQuestions.map((q, i) => {
    if (q.question_type === 'mcq') {
      return `
        <div class="card">
          <p><strong>Q${i + 1}.</strong> ${q.question_text} (${q.marks} mark${q.marks > 1 ? 's' : ''})</p>
          ${q.options.map((opt, idx) => `
            <label style="display:block">
              <input type="radio" name="q${q.id}" value="${idx}"> ${opt}
            </label>`).join('')}
        </div>`;
    }
    return `
      <div class="card">
        <p><strong>Q${i + 1}.</strong> ${q.question_text} (${q.marks} mark${q.marks > 1 ? 's' : ''})</p>
        <textarea name="q${q.id}" rows="3" placeholder="Type your answer..."></textarea>
      </div>`;
  }).join('');

  showSection('quiz-section');
}

$('submit-quiz-btn').addEventListener('click', async () => {
  const answers = currentQuizQuestions.map((q) => {
    if (q.question_type === 'mcq') {
      const selected = document.querySelector(`input[name="q${q.id}"]:checked`);
      return { question_id: q.id, answer: selected ? selected.value : null };
    }
    const textarea = document.querySelector(`textarea[name="q${q.id}"]`);
    return { question_id: q.id, answer: textarea.value };
  });

  const result = await apiPost(`/api/topics/${currentQuizTopicId}/submit`, { answers });
  showResults(result);
});

$('back-from-quiz-btn').addEventListener('click', () => showSection('main-section'));


function showResults(result) {
  $('results-summary').innerHTML = `<h3>Score: ${result.score} / ${result.total}</h3>`;

  $('results-breakdown').innerHTML = result.results.map((r, i) => {
    const q = currentQuizQuestions.find((qq) => qq.id === r.question_id);
    let statusClass = 'incorrect';
    let statusText = 'Incorrect';
    if (r.needs_review) { statusClass = 'review'; statusText = 'Needs teacher review'; }
    else if (r.is_correct) { statusClass = 'correct'; statusText = 'Correct'; }

    return `<p class="${statusClass}">Q${i + 1} (${q ? q.question_text : ''}): ${statusText}
      -- ${r.marks_awarded} mark(s)</p>`;
  }).join('');

  showSection('results-section');
}

$('back-from-results-btn').addEventListener('click', () => showSection('main-section'));


let currentFlashcards = [];
let currentFlashcardIndex = 0;
let flashcardShowingBack = false;

async function startFlashcards(topicId, topicName) {
  currentFlashcards = await apiGet(`/api/topics/${topicId}/flashcards`);
  currentFlashcardIndex = 0;
  flashcardShowingBack = false;
  $('flashcards-title').textContent = `Flashcards: ${topicName}`;

  const hasCards = currentFlashcards.length > 0;
  $('flashcard-empty').classList.toggle('hidden', hasCards);
  $('flashcard-viewer').classList.toggle('hidden', !hasCards);
  $('flashcards-progress').classList.toggle('hidden', !hasCards);

  if (hasCards) renderFlashcard();
  showSection('flashcards-section');
}

function renderFlashcard() {
  const card = currentFlashcards[currentFlashcardIndex];
  $('flashcards-progress').textContent = `Card ${currentFlashcardIndex + 1} of ${currentFlashcards.length}`;
  $('flashcard-text').textContent = flashcardShowingBack ? card.back_text : card.front_text;
  $('flashcard-hint').textContent = flashcardShowingBack ? 'Click the card to flip back' : 'Click the card to flip';
  $('flashcard').classList.toggle('flipped', flashcardShowingBack);
}

$('flashcard').addEventListener('click', () => {
  flashcardShowingBack = !flashcardShowingBack;
  renderFlashcard();
});

$('flashcard-flip-btn').addEventListener('click', () => {
  flashcardShowingBack = !flashcardShowingBack;
  renderFlashcard();
});

$('flashcard-prev-btn').addEventListener('click', () => {
  currentFlashcardIndex = (currentFlashcardIndex - 1 + currentFlashcards.length) % currentFlashcards.length;
  flashcardShowingBack = false;
  renderFlashcard();
});

$('flashcard-next-btn').addEventListener('click', () => {
  currentFlashcardIndex = (currentFlashcardIndex + 1) % currentFlashcards.length;
  flashcardShowingBack = false;
  renderFlashcard();
});

$('back-from-flashcards-btn').addEventListener('click', () => showSection('main-section'));


$('weakpoints-btn').addEventListener('click', async () => {
  const data = await apiGet(`/api/students/${currentStudent.id}/weakpoints`);

  $('weak-by-topic').innerHTML = data.by_topic.length
    ? data.by_topic.map((t) => `<p><strong>${t.topic_name}</strong>: got ${t.wrong} of ${t.attempted} wrong so far</p>`).join('')
    : '<p>No weak topics yet -- keep taking tests!</p>';

  $('weak-by-question').innerHTML = data.by_question.length
    ? data.by_question.map((q) => `<p><strong>${q.topic_name}</strong> -- "${q.question_text}": missed ${q.wrong}/${q.attempted} times</p>`).join('')
    : '<p>No repeated mistakes yet.</p>';

  showSection('weakpoints-section');
});

$('back-from-weak-btn').addEventListener('click', () => showSection('main-section'));


loadGrades();
