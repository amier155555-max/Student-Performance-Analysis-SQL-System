# Student Performance Analysis System — Factors Influencing Student Performance with SQL

A data-driven **SQL Analytics Studio**: upload **any** tabular dataset
(CSV/TSV/Excel) and the app cleans it, loads it into a SQL database, tests
relationships, and produces evidence-backed insights — with the SQL that
proves them, interactive charts, and a downloadable PDF report.

Built around the UCI Student-Performance dataset (G1/G2/G3), then generalised
to work with **any** dataset that has a numeric outcome column (score, price,
rating, sales, …).

🔗 **Live app:** https://student-performance-analysis-8uff.onrender.com
📄 **Full documentation:** [PROJECT_DOCUMENTATION.md](PROJECT_DOCUMENTATION.md)

---

## Repository organisation (by documentation section)

The repository is organised to follow the **Project Documentation Guidelines**.
Each section below maps to the folder(s) that contain its deliverables.

| # | Documentation section | Folder(s) | Contents |
|---|---|---|---|
| 1 | **Project Planning & Management** | [`01-Planning_and_Management/`](01-Planning_and_Management) | Proposal, plan/Gantt, roles, risk plan, KPIs |
| 2 | **Literature Review** | [`02-Literature_Review/`](02-Literature_Review) | Related work, evaluation, grading criteria |
| 3 | **Requirements Gathering** | [`03-Requirements_Gathering/`](03-Requirements_Gathering) | Stakeholders, use cases, functional/non-functional |
| 4 | **System Analysis & Design** | [`04-System_Analysis_and_Design/`](04-System_Analysis_and_Design) | Problem statement, ERD, `schema.sql`, DFD, class/sequence/activity/state diagrams |
| 4 | **UI/UX Design & API Docs** | [`05-UI_UX_and_API/`](05-UI_UX_and_API) | Wireframes, UI/UX guidelines, API documentation |
| 5 | **Implementation (Source Code & Execution)** | [`07-Implementation_Source_Code/spa/`](07-Implementation_Source_Code/spa) | The working Flask application |
| 5 | **System Deployment & Stored Procedures** | [`08-Deployment_Stored_Procedures/`](08-Deployment_Stored_Procedures) | Stored procedures (PostgreSQL) + SQLite equivalent |
| 5 | **Automation & Monitoring** | [`09-Automation_Monitoring/`](09-Automation_Monitoring) | Nightly batch job + cron/systemd scheduling |
| 6 | **Testing & Quality Assurance** | [`06-Testing_Report/`](06-Testing_Report), [`07-.../spa/tests/`](07-Implementation_Source_Code/spa/tests) | Test plan/report + unit tests |
| 7 | **Final Presentation & Reports** | [`10-Final_Presentation_and_Reports/`](10-Final_Presentation_and_Reports) | User manual, technical docs, slide deck |

> The full narrative that maps each of the above sections onto the actual
> implementation is in **[PROJECT_DOCUMENTATION.md](PROJECT_DOCUMENTATION.md)**.

---

## The application (Implementation)

A Flask web app in [`07-Implementation_Source_Code/spa/`](07-Implementation_Source_Code/spa).

**Features**
- **Upload & clean** any CSV/TSV/Excel (≤ 50 MB) — standardise columns, trim,
  drop empties, remove duplicates, coerce types, fill missing, cap outliers (IQR).
- **Preview** exactly what the cleaning changed.
- **Dashboard** — for student data: fixed hypothesis charts (bar/line/pie/doughnut);
  for any other file: **auto-detects a numeric outcome** and analyses every other
  column against it.
- **Deployment** — run the repeatable stored-procedure analysis and the nightly
  batch on demand (works for any dataset), with an audit run-log.
- **Logs** — activity/audit trail of uploads, runs, downloads, resets.
- **Documentation** — download a charted **PDF** report (schema + steps +
  insights + the SQL behind each one), generated live from the current data.
- **Settings** — configure the cleaning pipeline without touching code.

**Run locally**
```bash
cd 07-Implementation_Source_Code/spa
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
# open http://127.0.0.1:5000
```

**Tech stack:** Python 3.12 · Flask · gunicorn · pandas · numpy · SQLite ·
reportlab (PDF) · Chart.js · deployed on Render.

---

## Deployment

Hosted on **Render** as a web service (`gunicorn app:app`), configured by
[`render.yaml`](render.yaml). Any push to `main` can be deployed from the
Render dashboard (or automatically with Auto-Deploy enabled).

> Note: on Render's free tier the filesystem is ephemeral — uploaded data and
> the SQLite database reset when the service restarts. For persistence, attach
> a disk (set `SPA_DATA_DIR`) or migrate to the provided PostgreSQL schema.
