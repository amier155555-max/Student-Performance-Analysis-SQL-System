-- ============================================================
--  Student Performance Database Schema
--  Member 4: Database Engineer
--  Based on: student_data.csv (395 records, 33 attributes)
-- ============================================================

-- --------------------------
-- LOOKUP / REFERENCE TABLES
-- --------------------------

CREATE TABLE school (
    school_id   SERIAL PRIMARY KEY,
    code        CHAR(2)      NOT NULL UNIQUE,   -- 'GP', 'MS'
    name        VARCHAR(100) NOT NULL
);

CREATE TABLE job_type (
    job_id   SERIAL PRIMARY KEY,
    name     VARCHAR(50) NOT NULL UNIQUE        -- 'teacher','health','services','at_home','other'
);

CREATE TABLE reason_type (
    reason_id   SERIAL PRIMARY KEY,
    name        VARCHAR(50) NOT NULL UNIQUE     -- 'course','home','reputation','other'
);

CREATE TABLE guardian_type (
    guardian_id SERIAL PRIMARY KEY,
    name        VARCHAR(20) NOT NULL UNIQUE     -- 'mother','father','other'
);

-- --------------------------
-- CORE ENTITIES
-- --------------------------

CREATE TABLE student (
    student_id  SERIAL PRIMARY KEY,
    school_id   INT         NOT NULL REFERENCES school(school_id),
    sex         CHAR(1)     NOT NULL CHECK (sex IN ('F','M')),
    age         SMALLINT    NOT NULL CHECK (age BETWEEN 15 AND 22),
    address     CHAR(1)     NOT NULL CHECK (address IN ('U','R')),   -- Urban / Rural
    internet    BOOLEAN     NOT NULL DEFAULT FALSE,
    romantic    BOOLEAN     NOT NULL DEFAULT FALSE,
    higher      BOOLEAN     NOT NULL DEFAULT FALSE,                  -- wants higher education
    nursery     BOOLEAN     NOT NULL DEFAULT FALSE,
    activities  BOOLEAN     NOT NULL DEFAULT FALSE,
    health      SMALLINT    NOT NULL CHECK (health BETWEEN 1 AND 5),
    absences    SMALLINT    NOT NULL DEFAULT 0 CHECK (absences >= 0)
);

CREATE TABLE family (
    family_id   SERIAL PRIMARY KEY,
    student_id  INT         NOT NULL UNIQUE REFERENCES student(student_id) ON DELETE CASCADE,
    guardian_id INT         NOT NULL REFERENCES guardian_type(guardian_id),
    famsize     VARCHAR(5)  NOT NULL CHECK (famsize IN ('GT3','LE3')), -- >3 or <=3
    pstatus     CHAR(1)     NOT NULL CHECK (pstatus IN ('T','A')),     -- Together / Apart
    famrel      SMALLINT    NOT NULL CHECK (famrel BETWEEN 1 AND 5),
    medu        SMALLINT    NOT NULL CHECK (medu BETWEEN 0 AND 4),     -- Mother education
    fedu        SMALLINT    NOT NULL CHECK (fedu BETWEEN 0 AND 4),     -- Father education
    mjob_id     INT         NOT NULL REFERENCES job_type(job_id),
    fjob_id     INT         NOT NULL REFERENCES job_type(job_id),
    famsup      BOOLEAN     NOT NULL DEFAULT FALSE                      -- family educational support
);

CREATE TABLE enrollment (
    enrollment_id   SERIAL PRIMARY KEY,
    student_id      INT         NOT NULL UNIQUE REFERENCES student(student_id) ON DELETE CASCADE,
    reason_id       INT         NOT NULL REFERENCES reason_type(reason_id),
    traveltime      SMALLINT    NOT NULL CHECK (traveltime BETWEEN 1 AND 4),
    schoolsup       BOOLEAN     NOT NULL DEFAULT FALSE,                 -- school extra support
    paid            BOOLEAN     NOT NULL DEFAULT FALSE                  -- extra paid classes
);

CREATE TABLE study_behavior (
    behavior_id SERIAL PRIMARY KEY,
    student_id  INT         NOT NULL UNIQUE REFERENCES student(student_id) ON DELETE CASCADE,
    studytime   SMALLINT    NOT NULL CHECK (studytime BETWEEN 1 AND 4),
    failures    SMALLINT    NOT NULL DEFAULT 0 CHECK (failures >= 0),
    freetime    SMALLINT    NOT NULL CHECK (freetime BETWEEN 1 AND 5),
    goout       SMALLINT    NOT NULL CHECK (goout BETWEEN 1 AND 5),
    dalc        SMALLINT    NOT NULL CHECK (dalc BETWEEN 1 AND 5),     -- Workday alcohol
    walc        SMALLINT    NOT NULL CHECK (walc BETWEEN 1 AND 5)      -- Weekend alcohol
);

CREATE TABLE grade (
    grade_id    SERIAL PRIMARY KEY,
    student_id  INT         NOT NULL REFERENCES student(student_id) ON DELETE CASCADE,
    period      SMALLINT    NOT NULL CHECK (period IN (1, 2, 3)),       -- G1, G2, G3
    score       SMALLINT    NOT NULL CHECK (score BETWEEN 0 AND 20),
    UNIQUE (student_id, period)
);

-- --------------------------
-- INDEXES
-- --------------------------

CREATE INDEX idx_student_school   ON student(school_id);
CREATE INDEX idx_student_sex_age  ON student(sex, age);
CREATE INDEX idx_family_student   ON family(student_id);
CREATE INDEX idx_enrollment_reason ON enrollment(reason_id);
CREATE INDEX idx_grade_student    ON grade(student_id);
CREATE INDEX idx_grade_period     ON grade(period);

-- --------------------------
-- SAMPLE SEED DATA
-- --------------------------

INSERT INTO school (code, name) VALUES
    ('GP', 'Gabriel Pereira'),
    ('MS', 'Mousinho da Silveira');

INSERT INTO job_type (name) VALUES
    ('at_home'), ('health'), ('other'), ('services'), ('teacher');

INSERT INTO reason_type (name) VALUES
    ('course'), ('home'), ('reputation'), ('other');

INSERT INTO guardian_type (name) VALUES
    ('mother'), ('father'), ('other');

-- ============================================================
-- END OF SCHEMA
-- ============================================================
