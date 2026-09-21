



CREATE TABLE IF NOT EXISTS grades (
    id   INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS topics (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    grade_id    INT NOT NULL,
    name        VARCHAR(200) NOT NULL,
    description TEXT,
    FOREIGN KEY (grade_id) REFERENCES grades(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS notes_files (
    id                 INT AUTO_INCREMENT PRIMARY KEY,
    topic_id           INT NOT NULL,
    original_filename  VARCHAR(255) NOT NULL,
    stored_filename    VARCHAR(255) NOT NULL,
    file_type          VARCHAR(20),
    extracted_text     LONGTEXT,
    uploaded_at         DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (topic_id) REFERENCES topics(id)
) ENGINE=InnoDB;


CREATE TABLE IF NOT EXISTS questions (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    topic_id       INT NOT NULL,
    question_type  VARCHAR(10) NOT NULL,
    question_text  TEXT NOT NULL,
    options        TEXT,
    correct_option INT,
    keywords       TEXT,
    model_answer   TEXT,
    marks          INT DEFAULT 1,
    FOREIGN KEY (topic_id) REFERENCES topics(id),
    CONSTRAINT chk_question_type CHECK (question_type IN ('mcq','short'))
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS students (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    name       VARCHAR(200) NOT NULL,
    grade_id   INT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (grade_id) REFERENCES grades(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS attempts (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    topic_id   INT NOT NULL,
    score      FLOAT,
    total      FLOAT,
    taken_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(id),
    FOREIGN KEY (topic_id) REFERENCES topics(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS attempt_answers (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    attempt_id     INT NOT NULL,
    question_id    INT NOT NULL,
    student_answer TEXT,
    is_correct     TINYINT,
    marks_awarded  FLOAT,
    needs_review   TINYINT DEFAULT 0,
    FOREIGN KEY (attempt_id) REFERENCES attempts(id),
    FOREIGN KEY (question_id) REFERENCES questions(id)
) ENGINE=InnoDB;


CREATE TABLE IF NOT EXISTS flashcards (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    topic_id   INT NOT NULL,
    front_text TEXT NOT NULL,
    back_text  TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (topic_id) REFERENCES topics(id)
) ENGINE=InnoDB;
