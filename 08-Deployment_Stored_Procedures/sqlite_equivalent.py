"""
sqlite_equivalent.py
---------------------
Milestone 3 - "Structure stored procedures for repeat analysis",
implemented for the SQLite database used by the Flask GUI
(07-Implementation_Source_Code/spa).

SQLite has no CREATE PROCEDURE statement, so the same behavior described
in stored_procedures.sql (log a run, execute the hypothesis query, persist
results, mark success/failure) is implemented here as plain Python
functions that can be imported and called exactly like a stored procedure:

    from sqlite_equivalent import run_all_analyses
    run_all_analyses("data/db/spa.sqlite3")

Drop this module into spa/modules/ to wire it into the running app, or run
it standalone (see __main__ block) for a one-off / scheduled batch run.
"""

from __future__ import annotations

import sqlite3
import datetime as dt
from contextlib import contextmanager

DDL = """
CREATE TABLE IF NOT EXISTS analysis_run_log (
    run_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    procedure    TEXT NOT NULL,
    started_at   TEXT NOT NULL,
    finished_at  TEXT,
    row_count    INTEGER,
    status       TEXT NOT NULL DEFAULT 'RUNNING',
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS analysis_results (
    result_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          INTEGER REFERENCES analysis_run_log(run_id) ON DELETE CASCADE,
    procedure       TEXT NOT NULL,
    category        TEXT,
    avg_final_grade REAL,
    student_count   INTEGER,
    created_at      TEXT NOT NULL
);
"""

# Same fixed SQL as modules/analytics.py QUERIES, reused here so the
# "procedure" and the GUI dashboard never drift apart.
from importlib import import_module


def _load_queries():
    """Reuse the exact query definitions from the GUI's analytics module."""
    try:
        analytics = import_module("modules.analytics")
        return analytics.QUERIES
    except ImportError:
        # Fallback path when running standalone outside the spa/ package
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "07-Implementation_Source_Code", "spa"))
        analytics = import_module("modules.analytics")
        return analytics.QUERIES


@contextmanager
def _conn(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _ensure_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(DDL)


def _call_procedure(conn: sqlite3.Connection, spec: dict) -> int:
    """Equivalent of one CREATE OR REPLACE PROCEDURE sp_* block."""
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    cur = conn.execute(
        "INSERT INTO analysis_run_log (procedure, started_at, status) VALUES (?, ?, 'RUNNING')",
        (spec["id"], now),
    )
    run_id = cur.lastrowid
    try:
        rows = conn.execute(spec["sql"]).fetchall()
        for row in rows:
            conn.execute(
                """INSERT INTO analysis_results
                   (run_id, procedure, category, avg_final_grade, student_count, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    run_id,
                    spec["id"],
                    str(row["category"]) if "category" in row.keys() else None,
                    row["avg_final_grade"] if "avg_final_grade" in row.keys() else None,
                    row["student_count"] if "student_count" in row.keys() else None,
                    now,
                ),
            )
        conn.execute(
            "UPDATE analysis_run_log SET finished_at=?, status='SUCCESS', row_count=? WHERE run_id=?",
            (dt.datetime.now(dt.timezone.utc).isoformat(), len(rows), run_id),
        )
        return len(rows)
    except sqlite3.Error as exc:
        conn.execute(
            "UPDATE analysis_run_log SET finished_at=?, status='FAILED', error_message=? WHERE run_id=?",
            (dt.datetime.now(dt.timezone.utc).isoformat(), str(exc), run_id),
        )
        raise


def run_all_analyses(db_path: str) -> dict:
    """Equivalent of `CALL sp_run_all_analyses();` — run every hypothesis
    query, log each run, persist results. Returns a summary dict."""
    queries = _load_queries()
    summary = {"ok": [], "failed": []}
    with _conn(db_path) as conn:
        _ensure_tables(conn)
        for spec in queries:
            try:
                n = _call_procedure(conn, spec)
                summary["ok"].append({"procedure": spec["id"], "rows": n})
            except sqlite3.Error as exc:
                summary["failed"].append({"procedure": spec["id"], "error": str(exc)})
    return summary


def latest_results(db_path: str) -> list[dict]:
    """Equivalent of `SELECT * FROM v_latest_analysis_results;`"""
    with _conn(db_path) as conn:
        _ensure_tables(conn)
        rows = conn.execute(
            """
            SELECT r.* FROM analysis_results r
            JOIN (
                SELECT procedure, MAX(run_id) AS latest_run_id
                FROM analysis_results GROUP BY procedure
            ) latest ON latest.procedure = r.procedure AND latest.latest_run_id = r.run_id
            ORDER BY r.procedure, r.category
            """
        ).fetchall()
        return [dict(r) for r in rows]


if __name__ == "__main__":
    import sys
    db_path = sys.argv[1] if len(sys.argv) > 1 else "07-Implementation_Source_Code/spa/data/db/spa.sqlite3"
    result = run_all_analyses(db_path)
    print(f"Completed: {len(result['ok'])} succeeded, {len(result['failed'])} failed")
    for f in result["failed"]:
        print(f"  FAILED {f['procedure']}: {f['error']}")
