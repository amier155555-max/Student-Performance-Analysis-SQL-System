# User Manual — Student Performance Analysis System
Project 6: Factors Influencing Student Performance with SQL

## 1. Who this is for
Educators, administrators, or analysts who want to upload a student
dataset and get back cleaned data plus a hypothesis-testing dashboard —
no SQL or coding required.

## 2. Getting started

### Requirements
- Python 3.10+
- A raw dataset file: `.csv`, `.tsv`, `.xlsx`, or `.xls`

### Installation
```bash
cd 07-Implementation_Source_Code/spa
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Running the app
```bash
python app.py
```
Open **http://127.0.0.1:5000** in a browser.

## 3. Using the system

### Step 1 — Upload
On the landing page, drag and drop (or browse to) your data file. Sample
files are provided in `sample_data/` if you want to try the system
first.

### Step 2 — Review the cleaning report
After upload, the Preview page shows exactly what changed:
- columns renamed to a consistent format
- columns dropped for being mostly empty
- duplicate rows removed
- missing values filled
- statistical outliers capped

A sample of the cleaned rows is shown below the report so you can
confirm the data looks right before continuing.

### Step 3 — Explore the dashboard
The Dashboard page runs a fixed set of hypothesis tests against the
data and renders each as a chart, for example:
- Study time vs. final grade
- Absences vs. final grade
- Parental education vs. final grade
- Weekend alcohol consumption vs. final grade
- Internet access vs. final grade
- Extra school support vs. final grade
- Past class failures vs. final grade
- Grade trend across the three grading periods

If your file doesn't match the recognized student-performance columns,
the dashboard automatically falls back to a general column-by-column
profile instead of failing.

### Step 4 — Adjust settings (optional)
The Settings page lets you change how incoming data is cleaned
(missing-value strategy, duplicate handling, outlier handling) without
touching any code. A "danger zone" lets you reset the database or
restore default settings.

## 4. Automated nightly analysis
For a persisted, auditable history of results (not just what's shown
live in the browser), the system includes a nightly batch job:
```bash
cd 09-Automation_Monitoring
python nightly_job.py --db ../07-Implementation_Source_Code/spa/data/db/spa.sqlite3
```
This re-runs every hypothesis test, logs the outcome, and writes a
timestamped JSON report to `09-Automation_Monitoring/reports/`. See
`09-Automation_Monitoring/README.md` for how to schedule it to run
automatically every night.

## 5. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| "Unsupported file" error on upload | File isn't a recognized CSV/TSV/Excel format | Re-save the file as `.csv` or `.xlsx` |
| Dashboard shows a generic profile instead of hypothesis charts | Uploaded data doesn't contain the expected student-performance columns (sex, age, studytime, failures, absences) | Check column names match the expected schema in `04-System_Analysis_and_Design/schema.sql` |
| Dashboard is empty after upload | Cleaning removed all rows (e.g. every row was a duplicate or fully empty) | Check the Preview page's cleaning report for what was dropped |
| Nightly job exits with code 2 | Database file doesn't exist yet | Upload a file through the GUI at least once first |

## 6. Where to find more detail
- **Technical Documentation.md** (this folder) — architecture, schema, and API reference.
- **04-System_Analysis_and_Design/** — diagrams (ERD, DFD, sequence, class, use case).
- **08-Deployment_Stored_Procedures/** — how repeat analysis is structured as stored procedures.
- **09-Automation_Monitoring/** — nightly automation and monitoring setup.
