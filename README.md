# Project 6 — Factors Influencing Student Performance with SQL

A data-driven analytical platform that ingests, cleans, models, and
queries educational datasets to identify the factors most strongly
associated with student grades (G1/G2/G3).

## Project status
All items from the university's **Project Documentation Guidelines**
are now covered. Folders `01` through `06` are the original team
deliverables; folders `07` through `10` were added to complete the
guideline's remaining requirements (Implementation, Deployment/Stored
Procedures, Automation/Monitoring, and Final Presentation & Reports).

## Repository structure

| Folder | Guideline section | Status |
|---|---|---|
| `01-Planning_and_Management/` | Project Planning & Management | Original |
| `02-Literature_Review/` | Literature Review | Original |
| `03-Requirements_Gathering/` | Requirements Gathering | Original |
| `04-System_Analysis_and_Design/` | System Analysis & Design | Original |
| `05-UI_UX_and_API/` | UI/UX Design & API Docs | Original |
| `06-Testing_Report/` | Testing & Quality Assurance | Original |
| `07-Implementation_Source_Code/` | Implementation (Source Code & Execution) | **Added** — working Flask GUI (`spa/`) |
| `08-Deployment_Stored_Procedures/` | System Development & Evaluation / Deployment | **Added** — stored procedures for repeat analysis |
| `09-Automation_Monitoring/` | MLOps / Monitoring / Automation | **Added** — nightly batch job + scheduling |
| `10-Final_Presentation_and_Reports/` | Final Presentation & Reports | **Added** — user manual, technical docs, slide deck |

## Quick start
```bash
cd 07-Implementation_Source_Code/spa
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app.py
# open http://127.0.0.1:5000
```

## What was added and why
The uploaded materials covered planning, research, design, and testing
in depth, and a separate GUI implementation existed but wasn't wired
into the documentation set. Comparing everything against the five
project milestones and the official documentation checklist, three
gaps stood out and were filled:

1. **Milestone 3 (stored procedures for repeat analysis)** — added
   `08-Deployment_Stored_Procedures/`: a PostgreSQL stored-procedure
   implementation matching the existing schema, plus a SQLite
   equivalent for the GUI's current database, both of which log every
   run and persist results for later reuse.
2. **Milestone 4 (automate nightly query runs)** — added
   `09-Automation_Monitoring/`: a `nightly_job.py` batch runner with
   cron / systemd / CI scheduling examples, logging, and JSON reports,
   verified to run successfully end-to-end against real sample data.
3. **Final Presentation & Reports** — added
   `10-Final_Presentation_and_Reports/`: a User Manual, a Technical
   Documentation reference tying the architecture/schema/API together,
   and an 8-slide `Project_Presentation.pptx` summarizing the project.

Everything in `08-` and `09-` was executed against the sample dataset
before packaging to confirm it runs cleanly (8/8 hypothesis queries
succeeded, exit code 0).

## Contact / Roles
See `01-Planning_and_Management/Project Proposal and Plan - Updated
Deadline (Thursday).pdf` for team roles, the Gantt chart, and KPIs.
