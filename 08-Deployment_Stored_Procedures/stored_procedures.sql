-- ============================================================
--  Student Performance Analysis — Stored Procedures & Functions
--  Milestone 3: Deployment (Real-Time or Batch)
--  Target engine: PostgreSQL 13+ (matches 04-System_Analysis_and_Design/schema.sql)
--
--  Purpose:
--  Wrap the hypothesis-testing queries from Milestone 2
--  (see 07-Implementation_Source_Code/spa/modules/analytics.py) as
--  reusable, parameterized database objects so any client (the Flask
--  GUI, a BI tool, psql, or the nightly automation job in
--  09-Automation_Monitoring) can trigger the same analysis without
--  re-writing SQL, and so results can be re-run on a schedule or
--  on demand against the live dataset.
-- ============================================================

-- ------------------------------------------------------------
-- 1. Report log table
--    Every procedure call below writes one row here. This gives
--    the automation job (Milestone 4) an audit trail of what ran,
--    when, and how many rows it produced.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS analysis_run_log (
    run_id       SERIAL PRIMARY KEY,
    procedure    VARCHAR(100) NOT NULL,
    started_at   TIMESTAMP    NOT NULL DEFAULT NOW(),
    finished_at  TIMESTAMP,
    row_count    INT,
    status       VARCHAR(20)  NOT NULL DEFAULT 'RUNNING',  -- RUNNING | SUCCESS | FAILED
    error_message TEXT
);

-- ------------------------------------------------------------
-- 2. Results table
--    Stored procedures persist their output here instead of only
--    returning a result set, so a dashboard or the nightly job can
--    read "yesterday's numbers" without re-running the analysis.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS analysis_results (
    result_id    SERIAL PRIMARY KEY,
    run_id       INT REFERENCES analysis_run_log(run_id) ON DELETE CASCADE,
    procedure    VARCHAR(100) NOT NULL,
    category     VARCHAR(100),
    avg_final_grade NUMERIC(5,2),
    student_count   INT,
    created_at   TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_results_procedure ON analysis_results(procedure, created_at);

-- ============================================================
-- 3. Hypothesis-testing procedures
--    One procedure per Milestone-2 query. Each procedure:
--      a) logs a RUNNING row in analysis_run_log
--      b) executes the analytical query
--      c) writes every result row to analysis_results
--      d) marks the log row SUCCESS/FAILED with a row count
--    They are safe to call repeatedly (idempotent per run_id) and
--    take no free-text input, so they cannot be used for SQL
--    injection when exposed through the API.
-- ============================================================

CREATE OR REPLACE PROCEDURE sp_studytime_vs_grade()
LANGUAGE plpgsql
AS $$
DECLARE
    v_run_id INT;
    v_rows   INT;
BEGIN
    INSERT INTO analysis_run_log(procedure) VALUES ('sp_studytime_vs_grade') RETURNING run_id INTO v_run_id;

    INSERT INTO analysis_results (run_id, procedure, category, avg_final_grade, student_count)
    SELECT v_run_id, 'sp_studytime_vs_grade', sb.studytime::TEXT,
           ROUND(AVG(g.score), 2), COUNT(DISTINCT sb.student_id)
    FROM study_behavior sb
    JOIN grade g ON g.student_id = sb.student_id AND g.period = 3
    GROUP BY sb.studytime
    ORDER BY sb.studytime;

    GET DIAGNOSTICS v_rows = ROW_COUNT;
    UPDATE analysis_run_log
       SET finished_at = NOW(), status = 'SUCCESS', row_count = v_rows
     WHERE run_id = v_run_id;
EXCEPTION WHEN OTHERS THEN
    UPDATE analysis_run_log
       SET finished_at = NOW(), status = 'FAILED', error_message = SQLERRM
     WHERE run_id = v_run_id;
    RAISE;
END;
$$;

CREATE OR REPLACE PROCEDURE sp_absences_vs_grade()
LANGUAGE plpgsql
AS $$
DECLARE
    v_run_id INT;
    v_rows   INT;
BEGIN
    INSERT INTO analysis_run_log(procedure) VALUES ('sp_absences_vs_grade') RETURNING run_id INTO v_run_id;

    INSERT INTO analysis_results (run_id, procedure, category, avg_final_grade, student_count)
    SELECT v_run_id, 'sp_absences_vs_grade',
           CASE
               WHEN s.absences = 0 THEN '0'
               WHEN s.absences BETWEEN 1 AND 5 THEN '1-5'
               WHEN s.absences BETWEEN 6 AND 10 THEN '6-10'
               WHEN s.absences BETWEEN 11 AND 20 THEN '11-20'
               ELSE '20+'
           END,
           ROUND(AVG(g.score), 2), COUNT(DISTINCT s.student_id)
    FROM student s
    JOIN grade g ON g.student_id = s.student_id AND g.period = 3
    GROUP BY 1
    ORDER BY MIN(s.absences);

    GET DIAGNOSTICS v_rows = ROW_COUNT;
    UPDATE analysis_run_log SET finished_at = NOW(), status = 'SUCCESS', row_count = v_rows WHERE run_id = v_run_id;
EXCEPTION WHEN OTHERS THEN
    UPDATE analysis_run_log SET finished_at = NOW(), status = 'FAILED', error_message = SQLERRM WHERE run_id = v_run_id;
    RAISE;
END;
$$;

CREATE OR REPLACE PROCEDURE sp_parent_education_vs_grade()
LANGUAGE plpgsql
AS $$
DECLARE
    v_run_id INT;
    v_rows   INT;
BEGIN
    INSERT INTO analysis_run_log(procedure) VALUES ('sp_parent_education_vs_grade') RETURNING run_id INTO v_run_id;

    INSERT INTO analysis_results (run_id, procedure, category, avg_final_grade, student_count)
    SELECT v_run_id, 'sp_parent_education_vs_grade', f.medu::TEXT,
           ROUND(AVG(g.score), 2), COUNT(DISTINCT f.student_id)
    FROM family f
    JOIN grade g ON g.student_id = f.student_id AND g.period = 3
    GROUP BY f.medu
    ORDER BY f.medu;

    GET DIAGNOSTICS v_rows = ROW_COUNT;
    UPDATE analysis_run_log SET finished_at = NOW(), status = 'SUCCESS', row_count = v_rows WHERE run_id = v_run_id;
EXCEPTION WHEN OTHERS THEN
    UPDATE analysis_run_log SET finished_at = NOW(), status = 'FAILED', error_message = SQLERRM WHERE run_id = v_run_id;
    RAISE;
END;
$$;

CREATE OR REPLACE PROCEDURE sp_alcohol_vs_grade()
LANGUAGE plpgsql
AS $$
DECLARE
    v_run_id INT;
    v_rows   INT;
BEGIN
    INSERT INTO analysis_run_log(procedure) VALUES ('sp_alcohol_vs_grade') RETURNING run_id INTO v_run_id;

    INSERT INTO analysis_results (run_id, procedure, category, avg_final_grade, student_count)
    SELECT v_run_id, 'sp_alcohol_vs_grade', sb.walc::TEXT,
           ROUND(AVG(g.score), 2), COUNT(DISTINCT sb.student_id)
    FROM study_behavior sb
    JOIN grade g ON g.student_id = sb.student_id AND g.period = 3
    GROUP BY sb.walc
    ORDER BY sb.walc;

    GET DIAGNOSTICS v_rows = ROW_COUNT;
    UPDATE analysis_run_log SET finished_at = NOW(), status = 'SUCCESS', row_count = v_rows WHERE run_id = v_run_id;
EXCEPTION WHEN OTHERS THEN
    UPDATE analysis_run_log SET finished_at = NOW(), status = 'FAILED', error_message = SQLERRM WHERE run_id = v_run_id;
    RAISE;
END;
$$;

CREATE OR REPLACE PROCEDURE sp_failures_vs_grade()
LANGUAGE plpgsql
AS $$
DECLARE
    v_run_id INT;
    v_rows   INT;
BEGIN
    INSERT INTO analysis_run_log(procedure) VALUES ('sp_failures_vs_grade') RETURNING run_id INTO v_run_id;

    INSERT INTO analysis_results (run_id, procedure, category, avg_final_grade, student_count)
    SELECT v_run_id, 'sp_failures_vs_grade', sb.failures::TEXT,
           ROUND(AVG(g.score), 2), COUNT(DISTINCT sb.student_id)
    FROM study_behavior sb
    JOIN grade g ON g.student_id = sb.student_id AND g.period = 3
    GROUP BY sb.failures
    ORDER BY sb.failures;

    GET DIAGNOSTICS v_rows = ROW_COUNT;
    UPDATE analysis_run_log SET finished_at = NOW(), status = 'SUCCESS', row_count = v_rows WHERE run_id = v_run_id;
EXCEPTION WHEN OTHERS THEN
    UPDATE analysis_run_log SET finished_at = NOW(), status = 'FAILED', error_message = SQLERRM WHERE run_id = v_run_id;
    RAISE;
END;
$$;

CREATE OR REPLACE PROCEDURE sp_internet_vs_grade()
LANGUAGE plpgsql
AS $$
DECLARE
    v_run_id INT;
    v_rows   INT;
BEGIN
    INSERT INTO analysis_run_log(procedure) VALUES ('sp_internet_vs_grade') RETURNING run_id INTO v_run_id;

    INSERT INTO analysis_results (run_id, procedure, category, avg_final_grade, student_count)
    SELECT v_run_id, 'sp_internet_vs_grade',
           CASE WHEN s.internet THEN 'Has internet' ELSE 'No internet' END,
           ROUND(AVG(g.score), 2), COUNT(DISTINCT s.student_id)
    FROM student s
    JOIN grade g ON g.student_id = s.student_id AND g.period = 3
    GROUP BY s.internet
    ORDER BY s.internet;

    GET DIAGNOSTICS v_rows = ROW_COUNT;
    UPDATE analysis_run_log SET finished_at = NOW(), status = 'SUCCESS', row_count = v_rows WHERE run_id = v_run_id;
EXCEPTION WHEN OTHERS THEN
    UPDATE analysis_run_log SET finished_at = NOW(), status = 'FAILED', error_message = SQLERRM WHERE run_id = v_run_id;
    RAISE;
END;
$$;

CREATE OR REPLACE PROCEDURE sp_schoolsup_vs_grade()
LANGUAGE plpgsql
AS $$
DECLARE
    v_run_id INT;
    v_rows   INT;
BEGIN
    INSERT INTO analysis_run_log(procedure) VALUES ('sp_schoolsup_vs_grade') RETURNING run_id INTO v_run_id;

    INSERT INTO analysis_results (run_id, procedure, category, avg_final_grade, student_count)
    SELECT v_run_id, 'sp_schoolsup_vs_grade',
           CASE WHEN e.schoolsup THEN 'Receives support' ELSE 'No extra support' END,
           ROUND(AVG(g.score), 2), COUNT(DISTINCT e.student_id)
    FROM enrollment e
    JOIN grade g ON g.student_id = e.student_id AND g.period = 3
    GROUP BY e.schoolsup
    ORDER BY e.schoolsup;

    GET DIAGNOSTICS v_rows = ROW_COUNT;
    UPDATE analysis_run_log SET finished_at = NOW(), status = 'SUCCESS', row_count = v_rows WHERE run_id = v_run_id;
EXCEPTION WHEN OTHERS THEN
    UPDATE analysis_run_log SET finished_at = NOW(), status = 'FAILED', error_message = SQLERRM WHERE run_id = v_run_id;
    RAISE;
END;
$$;

CREATE OR REPLACE PROCEDURE sp_grade_trend()
LANGUAGE plpgsql
AS $$
DECLARE
    v_run_id INT;
    v_rows   INT;
BEGIN
    INSERT INTO analysis_run_log(procedure) VALUES ('sp_grade_trend') RETURNING run_id INTO v_run_id;

    INSERT INTO analysis_results (run_id, procedure, category, avg_final_grade, student_count)
    SELECT v_run_id, 'sp_grade_trend', period::TEXT,
           ROUND(AVG(score), 2), COUNT(DISTINCT student_id)
    FROM grade
    GROUP BY period
    ORDER BY period;

    GET DIAGNOSTICS v_rows = ROW_COUNT;
    UPDATE analysis_run_log SET finished_at = NOW(), status = 'SUCCESS', row_count = v_rows WHERE run_id = v_run_id;
EXCEPTION WHEN OTHERS THEN
    UPDATE analysis_run_log SET finished_at = NOW(), status = 'FAILED', error_message = SQLERRM WHERE run_id = v_run_id;
    RAISE;
END;
$$;

-- ------------------------------------------------------------
-- 4. Master procedure — runs every hypothesis test in one call.
--    This is the single entry point the nightly automation job
--    (09-Automation_Monitoring) invokes.
-- ------------------------------------------------------------
CREATE OR REPLACE PROCEDURE sp_run_all_analyses()
LANGUAGE plpgsql
AS $$
BEGIN
    CALL sp_studytime_vs_grade();
    CALL sp_absences_vs_grade();
    CALL sp_parent_education_vs_grade();
    CALL sp_alcohol_vs_grade();
    CALL sp_failures_vs_grade();
    CALL sp_internet_vs_grade();
    CALL sp_schoolsup_vs_grade();
    CALL sp_grade_trend();
END;
$$;

-- ------------------------------------------------------------
-- 5. Convenience view — latest result set per procedure, for the
--    dashboard/API to read without knowing about run_id bookkeeping.
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW v_latest_analysis_results AS
SELECT r.*
FROM analysis_results r
JOIN (
    SELECT procedure, MAX(run_id) AS latest_run_id
    FROM analysis_results
    GROUP BY procedure
) latest ON latest.procedure = r.procedure AND latest.latest_run_id = r.run_id;

-- ============================================================
-- Usage:
--   CALL sp_run_all_analyses();
--   SELECT * FROM v_latest_analysis_results ORDER BY procedure, category;
--   SELECT * FROM analysis_run_log ORDER BY started_at DESC LIMIT 10;
-- ============================================================
