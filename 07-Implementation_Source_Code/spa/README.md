# Student Performance Analysis — GUI

A web interface for **Project 6: Factors Influencing Student Performance
with SQL**. It gives the client a single place to hand over a raw data
file and get back a cleaned, query-ready SQL database plus a
hypothesis-testing analytics dashboard — no manual data wrangling
required.

```
Raw file  →  Clean  →  SQL database  →  Insights
```

## What it does

1. **Upload (Milestone 1)** — the landing page accepts the client's raw
   file (`.csv`, `.tsv`, `.xlsx`, `.xls`).
2. **Clean & load (Milestone 1)** — the file is automatically:
   - column names standardized (lowercase, underscores)
   - whitespace trimmed and blank markers (`N/A`, `?`, `-`, …) normalized
   - fully empty rows removed, columns that are mostly empty dropped
   - duplicate rows removed
   - numeric-looking text columns coerced to numbers
   - missing values filled using the strategy set on the Settings page
   - statistical outliers capped using the IQR method
3. **Store (Milestone 1 → 2)** — the cleaned data is always saved as a
   flat `cleaned_data` table. If the columns match the student-performance
   dataset, it is also split into the normalized relational schema
   (`student`, `family`, `enrollment`, `study_behavior`, `grade`) so SQL
   analytics can run immediately.
4. **Preview** — a report shows exactly what changed (renamed columns,
   dropped columns, duplicates removed, missing values filled, outliers
   capped) plus a sample of the cleaned rows.
5. **Dashboard (Milestone 2)** — a set of fixed, named SQL queries test
   specific hypotheses (study time vs. grade, absences vs. grade,
   parental education vs. grade, alcohol use vs. grade, etc.) and render
   as charts. Uploads that don't match the education schema fall back to
   a generic column-by-column profile instead of failing.
6. **Settings** — configure the cleaning pipeline (missing-value
   strategy, duplicate handling, outlier handling, column-name
   standardization, database path) without touching code, plus a
   "danger zone" to reset the database or restore default settings.

## Project structure

```
app.py                     Flask routes
config.py                  Settings load/save (data/settings.json)
modules/
  data_cleaner.py          Generic, reusable cleaning pipeline
  schema_mapper.py         Maps cleaned data onto the normalized schema
  db_manager.py            SQLite read/write (parameterized, injection-safe)
  analytics.py             Hypothesis-testing SQL queries (Milestone 2)
templates/                 Jinja2 HTML (upload, preview, dashboard, settings)
static/css/style.css       Design system (calm sage / warm paper palette)
static/js/                 Dropzone interactivity + Chart.js rendering
tests/test_cleaner.py      Unit tests for cleaning, schema mapping, DB layer
sample_data/                Example raw files to try the pipeline with
data/                       Runtime storage: uploads, cleaned CSVs, SQLite DB
```

## System requirements

- Python 3.10+
- pip

## Installation

```bash
# from the project's GUI folder
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Running locally

```bash
python app.py
```

The app starts at **http://127.0.0.1:5000**. Open it in a browser, drop
in a file from `sample_data/` (or your own), and follow the flow:
Upload → Preview → Dashboard.

To run in production, use a WSGI server instead of the Flask dev
server, for example:

```bash
pip install gunicorn
gunicorn -w 2 -b 0.0.0.0:8000 app:app
```

## Configuration

Runtime settings live in `data/settings.json` (created automatically on
first save) and are editable from the **Settings** page in the app —
no restart needed. Key options:

| Setting | Purpose |
|---|---|
| `missing_strategy` | `auto`, `fill_mean`, `fill_median`, `fill_mode`, `fill_zero`, or `drop_rows` |
| `missing_threshold_pct` | Drop a column if more than this % of it is missing |
| `remove_duplicates` | Toggle duplicate-row removal |
| `outlier_handling` | `cap_iqr`, `flag_only`, or `none` |
| `database_path` | Where the SQLite database file is written |

Set `SPA_SECRET_KEY` as an environment variable in production instead of
relying on the development default in `app.py`.

## Running tests

```bash
python -m unittest discover -s tests -v
```

## Notes on the underlying schema

The normalized schema this GUI populates matches
`04-System_Analysis_and_Design/schema.sql` from the project's planning
documents (school, student, family, enrollment, study_behavior, grade).
Any dataset with recognizable student-performance columns (sex, age,
studytime, failures, absences, at minimum) is automatically mapped onto
it; everything else is stored as a single cleaned table and profiled
generically so the tool never rejects a file outright.
