# Milestone 3 — Deployment (Real-Time or Batch)

## 1. Goal
Structure repeatable analysis as **stored procedures** so the same hypothesis
tests from Milestone 2 can be re-run on demand or on a schedule, with a full
audit trail, instead of being copy-pasted ad hoc each time.

## 2. What's included

| File | Purpose |
|---|---|
| `stored_procedures.sql` | PostgreSQL stored procedures/functions matching `04-System_Analysis_and_Design/schema.sql`. Wraps every hypothesis query from `analytics.py`, logs each run, and persists results. |
| `sqlite_equivalent.py` | SQLite doesn't support stored procedures natively (no `CREATE PROCEDURE`). This script gives the GUI's SQLite deployment the same behavior — callable "procedures" as Python functions that log runs and persist results to `analysis_run_log` / `analysis_results` tables inside the same `.db` file. |

## 3. Two supported deployment modes

### A. Real-time (interactive) — used by the Flask GUI today
The dashboard route in `07-Implementation_Source_Code/spa/app.py` calls
`analytics.run_all(db_path)` on every page load, which executes the
hypothesis queries directly against SQLite and renders the charts
immediately. This satisfies "real-time" analysis for a single user session.

### B. Batch (scheduled) — new in this deliverable
For a shared/production deployment (PostgreSQL), the same logic is exposed
as callable stored procedures:

```sql
CALL sp_run_all_analyses();
SELECT * FROM v_latest_analysis_results ORDER BY procedure, category;
```

This lets:
- the nightly automation job (`09-Automation_Monitoring`) trigger analysis
  without embedding SQL in application code,
- any BI tool or `psql` session re-run the same tested queries,
- every run to be audited via `analysis_run_log` (start/end time, row
  count, success/failure).

## 4. Migrating the GUI from SQLite to PostgreSQL (optional, for production)
The GUI is intentionally engine-agnostic at the `db_manager.py` layer
(parameterized queries only, no engine-specific SQL in the app code). To
move from the local SQLite demo to the PostgreSQL schema used here:

1. Provision PostgreSQL and run `04-System_Analysis_and_Design/schema.sql`.
2. Run `stored_procedures.sql` against the same database.
3. Point `config.py` / `database_path` at the PostgreSQL connection string
   and swap the `sqlite3` calls in `db_manager.py` for `psycopg2`
   (interface is identical: `run_query(db_path, sql)`).
4. Replace the direct `analytics.QUERIES` execution with
   `CALL sp_run_all_analyses();` followed by
   `SELECT * FROM v_latest_analysis_results;` for the dashboard read path.

No schema or query logic changes are required — only the connection layer.
