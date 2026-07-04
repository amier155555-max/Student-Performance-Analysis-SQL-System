# Technical Documentation — Student Performance Analysis System
Project 6: Factors Influencing Student Performance with SQL

## 1. System Architecture
- **Frontend**: Server-rendered HTML (Jinja2 templates) + Chart.js for
  dashboard visualizations. See `04-System_Analysis_and_Design/Architecture_Design_Project_6_EN.pdf`
  and `05-UI_UX_and_API/Figma_Design_Screens_Documentation.pdf` for the
  wireframes and design rationale.
- **Backend**: Flask (Python) application (`07-Implementation_Source_Code/spa/app.py`),
  organized into modules:
  - `data_cleaner.py` — generic, reusable cleaning pipeline
  - `schema_mapper.py` — maps cleaned data onto the normalized education schema
  - `db_manager.py` — parameterized SQL read/write layer (injection-safe)
  - `analytics.py` — Milestone 2 hypothesis-testing queries
- **Database**: SQLite for the local/demo deployment; the schema and
  queries are engine-agnostic and portable to PostgreSQL for production
  (see `08-Deployment_Stored_Procedures/Deployment_Guide.md`).

## 2. Database Schema
Defined in `04-System_Analysis_and_Design/schema.sql`. Normalized into:
- `school`, `job_type`, `reason_type`, `guardian_type` — lookup tables
- `student` — core demographic/behavioral attributes
- `family` — guardian, parental education, family support
- `enrollment` — school choice reason, travel time, support/paid classes
- `study_behavior` — study time, failures, free time, alcohol use
- `grade` — G1/G2/G3 scores per grading period

Entity relationships are diagrammed in `04-System_Analysis_and_Design/ERD.png`.

## 3. Data Flow
1. Client uploads a raw file (CSV/TSV/Excel).
2. `data_cleaner.DataCleaner.run()` standardizes columns, strips
   whitespace, drops empty rows/columns, removes duplicates, coerces
   types, fills missing values, and caps outliers (IQR method).
3. The cleaned data is always saved as a flat `cleaned_data` table.
4. `schema_mapper.detect_education_schema()` checks for recognizable
   student-performance columns; if found, `build_normalized_tables()`
   splits the data into the five normalized tables above.
5. `analytics.run_all()` executes the fixed hypothesis queries against
   the normalized tables and returns chart-ready results.

Full context-level and detailed DFDs: `04-System_Analysis_and_Design/DFD_level0.png`, `DFD_level1.png`.

## 4. Analytical Queries (Milestone 2)
Eight fixed, developer-authored hypothesis tests (never built from user
input) — see `07-Implementation_Source_Code/spa/modules/analytics.py`:
study time vs. grade, absences vs. grade, parental education vs. grade,
weekend alcohol vs. grade, internet access vs. grade, school support vs.
grade, past failures vs. grade, and grade trend across G1→G2→G3.

## 5. Repeatable Analysis / Deployment (Milestone 3)
Stored procedures wrap each hypothesis query for repeatable, auditable
execution:
- `08-Deployment_Stored_Procedures/stored_procedures.sql` — PostgreSQL
  implementation matching the schema, with a `sp_run_all_analyses()`
  master procedure, a run-log table, and a results table.
- `08-Deployment_Stored_Procedures/sqlite_equivalent.py` — the same
  behavior implemented for the SQLite deployment used by the GUI today.

## 6. Automation & Monitoring (Milestone 4)
`09-Automation_Monitoring/nightly_job.py` runs the full analysis batch,
logs each procedure's outcome, and writes a timestamped JSON report.
Scheduling examples for cron, systemd timers, and CI/CD are provided in
`09-Automation_Monitoring/README.md`. Exit codes (0/1/2) let any
scheduler alert on failure.

## 7. API Reference
See `05-UI_UX_and_API/api.docx - API Documentation Project 6.pdf` for
the full endpoint reference (auth, students, grades, correlation
analysis). Tech stack reference: Node.js/Express or Flask, MySQL or
PostgreSQL, deployable via GitHub + Render/Netlify.

## 8. Testing
See `06-Testing_Report/Testing_Report_Project_6.pdf` for the full
testing strategy (unit, integration, performance, UAT) and test
execution log. `07-Implementation_Source_Code/spa/tests/test_cleaner.py`
contains automated unit tests for the cleaning pipeline, schema mapper,
and database layer; run with:
```bash
python -m unittest discover -s tests -v
```

## 9. Security
- All SQL is parameterized; no query is built from raw user input
  (`db_manager.py`).
- Fixed, developer-authored analytical queries only — user uploads
  cannot inject SQL through column names or values.
- Production deployments should set `SPA_SECRET_KEY` as an environment
  variable rather than relying on the development default.

## 10. Repository Layout
```
01-Planning_and_Management/        Project proposal, plan, risk assessment, KPIs
02-Literature_Review/              Background research and comparative approaches
03-Requirements_Gathering/         Stakeholder analysis, requirements spec
04-System_Analysis_and_Design/     ERD, DFD, sequence/class/state/use-case diagrams, schema.sql
05-UI_UX_and_API/                  Wireframes, UI/UX guidelines, API documentation
06-Testing_Report/                 Testing strategy and execution log
07-Implementation_Source_Code/     Flask GUI application (source code & execution)
08-Deployment_Stored_Procedures/   Milestone 3 — stored procedures, deployment guide
09-Automation_Monitoring/          Milestone 4 — nightly automation, scheduling, monitoring
10-Final_Presentation_and_Reports/ User manual, technical documentation, presentation
```
