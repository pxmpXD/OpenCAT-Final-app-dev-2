let currentTopicId = null;
let gradesCache = [];

const $ = (id) => document.getElementById(id);

function showSection(id) {
  ['login-section', 'main-section', 'topic-detail-section']
    .forEach((s) => $(s).classList.toggle('hidden', s !== id));
}


$('login-btn').addEventListener('click', async () => {
  try {
    await apiPost('/api/teacher/login', { password: $('teacher-password').value });
    showSection('main-section');
    init();
  } catch (e) {
    alert(e.error || 'Login failed');
  }
});


async function init() {
  gradesCache = await apiGet('/api/grades');
  const options = gradesCache.map((g) => `<option value="${g.id}">${g.name}</option>`).join('');
  $('new-topic-grade').innerHTML = options;
  $('filter-grade').innerHTML = options;

  $('filter-grade').addEventListener('change', () => loadTopics());
  loadTopics();
}


$('add-topic-btn').addEventListener('click', async () => {
  const name = $('new-topic-name').value.trim();
  if (!name) return alert('Enter a topic name');

  await apiPost('/api/topics', {
    name,
    grade_id: $('new-topic-grade').value,
    description: $('new-topic-desc').value.trim(),
  });
  $('new-topic-name').value = '';
  $('new-topic-desc').value = '';
  loadTopics();
});

async function loadTopics() {
  const gradeId = $('filter-grade').value;
  const topics = await apiGet(`/api/topics?grade_id=${gradeId}`);
  const container = $('topics-list');

  if (topics.length === 0) {
    container.innerHTML = '<p>No topics for this grade yet.</p>';
    return;
  }

  container.innerHTML = topics.map((t) => `
    <div class="card topic-item">
      <span><strong>${t.name}</strong> -- ${t.description || ''}</span>
      <span>
        <button data-id="${t.id}" data-name="${t.name}" class="manage-btn">Manage</button>
        <button data-id="${t.id}" class="delete-topic-btn">Delete</button>
      </span>
    </div>`).join('');

  document.querySelectorAll('.manage-btn').forEach((btn) =>
    btn.addEventListener('click', () => openTopicDetail(btn.dataset.id, btn.dataset.name)));
  document.querySelectorAll('.delete-topic-btn').forEach((btn) =>
    btn.addEventListener('click', async () => {
      if (confirm('Delete this topic and all its notes/questions?')) {
        await apiDelete(`/api/topics/${btn.dataset.id}`);
        loadTopics();
      }
    }));
}


async function openTopicDetail(topicId, topicName) {
  currentTopicId = topicId;
  $('topic-detail-title').textContent = topicName;
  showSection('topic-detail-section');
  await loadNotes();
  await loadQuestions();
  await loadFlashcards();
}

$('back-to-topics-btn').addEventListener('click', () => showSection('main-section'));


const dropzone = $('dropzone');
const fileInput = $('file-input');

dropzone.addEventListener('click', () => fileInput.click());

dropzone.addEventListener('dragover', (e) => {
  e.preventDefault();
  dropzone.classList.add('dragover');
});
dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
dropzone.addEventListener('drop', async (e) => {
  e.preventDefault();
  dropzone.classList.remove('dragover');
  await uploadFiles(e.dataTransfer.files);
});
fileInput.addEventListener('change', async (e) => {
  await uploadFiles(e.target.files);
  fileInput.value = '';
});

async function uploadFiles(fileList) {
  for (const file of fileList) {
    try {
      await apiUploadFile(`/api/topics/${currentTopicId}/notes/upload`, file);
    } catch (e) {
      alert(`Failed to upload ${file.name}: ${e.error || 'unknown error'}`);
    }
  }
  loadNotes();
}

async function loadNotes() {
  const notes = await apiGet(`/api/topics/${currentTopicId}/notes`);
  $('notes-list').innerHTML = notes.length
    ? notes.map((n) => `
        <div class="topic-item">
          <a href="/api/notes/${n.id}/download">${n.original_filename}</a>
          <button data-id="${n.id}" class="delete-note-btn">Delete</button>
        </div>`).join('')
    : '<p>No notes uploaded yet.</p>';

  document.querySelectorAll('.delete-note-btn').forEach((btn) =>
    btn.addEventListener('click', async () => {
      await apiDelete(`/api/notes/${btn.dataset.id}`);
      loadNotes();
    }));
}


function setAiStatus(message, isError = false) {
  const el = $('ai-generate-status');
  el.textContent = message;
  el.classList.toggle('error', isError);
}

$('ai-generate-questions-btn').addEventListener('click', async () => {
  const count = parseInt($('ai-question-count').value, 10) || 6;
  const btn = $('ai-generate-questions-btn');
  btn.disabled = true;
  setAiStatus(`Generating ${count} questions from your notes...`);
  try {
    const created = await apiPost(`/api/topics/${currentTopicId}/generate-questions`, { count });
    setAiStatus(`Added ${created.length} questions.`);
    loadQuestions();
  } catch (e) {
    setAiStatus(e.error || 'Generation failed', true);
  } finally {
    btn.disabled = false;
  }
});

$('ai-generate-flashcards-btn').addEventListener('click', async () => {
  const count = parseInt($('ai-flashcard-count').value, 10) || 8;
  const btn = $('ai-generate-flashcards-btn');
  btn.disabled = true;
  setAiStatus(`Generating ${count} flashcards from your notes...`);
  try {
    const created = await apiPost(`/api/topics/${currentTopicId}/generate-flashcards`, { count });
    setAiStatus(`Added ${created.length} flashcards.`);
    loadFlashcards();
  } catch (e) {
    setAiStatus(e.error || 'Generation failed', true);
  } finally {
    btn.disabled = false;
  }
});


$('question-type').addEventListener('change', (e) => {
  const isMcq = e.target.value === 'mcq';
  $('mcq-fields').classList.toggle('hidden', !isMcq);
  $('short-fields').classList.toggle('hidden', isMcq);
});

$('add-question-btn').addEventListener('click', async () => {
  const qtype = $('question-type').value;
  const text = $('question-text').value.trim();
  const marks = parseInt($('question-marks').value, 10) || 1;
  if (!text) return alert('Enter question text');

  const payload = { question_type: qtype, question_text: text, marks };

  if (qtype === 'mcq') {
    const options = $('mcq-options').value.split('\n').map((s) => s.trim()).filter(Boolean);
    const correctIndex = parseInt($('mcq-correct-index').value, 10);
    if (options.length < 2 || isNaN(correctIndex)) {
      return alert('Add at least 2 options and set the correct index');
    }
    payload.options = options;
    payload.correct_option = correctIndex;
  } else {
    const keywords = $('short-keywords').value.split(',').map((s) => s.trim()).filter(Boolean);
    if (keywords.length === 0) return alert('Add at least one keyword for auto-grading');
    payload.keywords = keywords;
    payload.model_answer = $('short-model-answer').value.trim();
  }

  await apiPost(`/api/topics/${currentTopicId}/questions`, payload);

  $('question-text').value = '';
  $('mcq-options').value = '';
  $('mcq-correct-index').value = '';
  $('short-keywords').value = '';
  $('short-model-answer').value = '';
  loadQuestions();
});

async function loadQuestions() {
  const questions = await apiGet(`/api/topics/${currentTopicId}/questions`);
  $('questions-list').innerHTML = questions.length
    ? questions.map((q) => `
        <div class="card">
          <p><strong>[${q.question_type.toUpperCase()}, ${q.marks} mark(s)]</strong> ${q.question_text}</p>
          ${q.question_type === 'mcq'
            ? `<ul>${q.options.map((o, i) => `<li>${i === q.correct_option ? '<strong>' + o + ' (correct)</strong>' : o}</li>`).join('')}</ul>`
            : `<p>Keywords: ${q.keywords.join(', ')}</p><p>Model answer: ${q.model_answer || '-'}</p>`}
          <button data-id="${q.id}" class="delete-question-btn">Delete</button>
        </div>`).join('')
    : '<p>No questions yet.</p>';

  document.querySelectorAll('.delete-question-btn').forEach((btn) =>
    btn.addEventListener('click', async () => {
      await apiDelete(`/api/questions/${btn.dataset.id}`);
      loadQuestions();
    }));
}


$('add-flashcard-btn').addEventListener('click', async () => {
  const front_text = $('flashcard-front').value.trim();
  const back_text = $('flashcard-back').value.trim();
  if (!front_text || !back_text) return alert('Fill in both the front and back of the card');

  await apiPost(`/api/topics/${currentTopicId}/flashcards`, { front_text, back_text });
  $('flashcard-front').value = '';
  $('flashcard-back').value = '';
  loadFlashcards();
});

async function loadFlashcards() {
  const cards = await apiGet(`/api/topics/${currentTopicId}/flashcards`);
  $('flashcards-list').innerHTML = cards.length
    ? cards.map((c) => `
        <div class="card topic-item">
          <span><strong>${c.front_text}</strong> &rarr; ${c.back_text}</span>
          <button data-id="${c.id}" class="delete-flashcard-btn">Delete</button>
        </div>`).join('')
    : '<p>No flashcards yet.</p>';

  document.querySelectorAll('.delete-flashcard-btn').forEach((btn) =>
    btn.addEventListener('click', async () => {
      await apiDelete(`/api/flashcards/${btn.dataset.id}`);
      loadFlashcards();
    }));
}


$('load-class-weakpoints-btn').addEventListener('click', async () => {
  const gradeId = $('filter-grade').value;
  const data = await apiGet(`/api/teacher/class-weakpoints?grade_id=${gradeId}`);
  $('class-weakpoints').innerHTML = data.length
    ? data.map((t) => `<p><strong>${t.topic_name}</strong>: ${t.wrong} wrong out of ${t.attempted} answers given class-wide</p>`).join('')
    : '<p>No test data for this grade yet.</p>';
});
