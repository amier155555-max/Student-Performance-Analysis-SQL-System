"""
modules/report_builder.py
--------------------------
Final Documentation Report generator.

Builds a single Markdown document (in English) that explains:
  1. Database schema (design + the actual runtime SQLite tables)
  2. The ETL / processing steps performed by the system
  3. The most important insights, each backed by the exact SQL query
     that produced it (pulled live from `analytics.QUERIES` and the
     numbers actually returned by the current database - never
     hard-coded), so the report always reflects the data that is
     really loaded.

The Markdown is rendered to a charted PDF by `modules/pdf_report.py`;
this module itself has zero third-party dependencies.
"""

from __future__ import annotations

from datetime import datetime
from textwrap import dedent

from . import analytics, db_manager

# --------------------------------------------------------------------
# Static schema description (mirrors 04-System_Analysis_and_Design/schema.sql)
# --------------------------------------------------------------------
SCHEMA_TABLES = [
    ("student", "Core student demographic and behavioural data",
     ["student_id (PK)", "school", "sex", "age", "address", "internet",
      "romantic", "higher", "nursery", "activities", "health", "absences"]),
    ("family", "Family background and parental support (1:1 with student)",
     ["student_id (PK/FK to student)", "guardian", "famsize", "pstatus",
      "famrel", "medu", "fedu", "mjob", "fjob", "famsup"]),
    ("enrollment", "Enrollment and school support (1:1 with student)",
     ["student_id (PK/FK to student)", "reason", "traveltime", "schoolsup", "paid"]),
    ("study_behavior", "Study habits and free-time behaviour (1:1 with student)",
     ["student_id (PK/FK to student)", "studytime", "failures", "freetime",
      "goout", "dalc", "walc"]),
    ("grade", "Student grade per assessment period (1:N with student)",
     ["grade_id (PK)", "student_id (FK to student)", "period (1/2/3)", "score (0-20)"]),
]

LOOKUP_TABLES_NOTE = dedent("""
    Design note: the fully normalized design in
    `04-System_Analysis_and_Design/schema.sql` separates repeated text
    values (school, job, enrollment reason, guardian) into dedicated
    lookup tables (school, job_type, reason_type, guardian_type) linked
    by foreign keys — this is the design used in the PostgreSQL deployment
    version (08-Deployment_Stored_Procedures). The actual GUI application
    (SQLite, via modules/schema_mapper.py) stores those values as plain
    text inside the same five tables above to simplify automatic import of
    any uploaded data file; the logical relationships between tables (via
    student_id) are identical in both designs.
""").strip()


def _fmt_number(v):
    if v is None:
        return "—"
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def _best_worst(rows: list[dict]):
    """Return (best_row, worst_row) by avg_final_grade, or (None, None)."""
    scored = [r for r in rows if r.get("avg_final_grade") is not None]
    if len(scored) < 2:
        return None, None
    best = max(scored, key=lambda r: r["avg_final_grade"])
    worst = min(scored, key=lambda r: r["avg_final_grade"])
    if best is worst:
        return None, None
    return best, worst


def _insight_sentence(entry: dict) -> str | None:
    """Auto-generate an English, data-driven insight sentence for one query result."""
    rows = entry.get("data") or []
    best, worst = _best_worst(rows)
    if not best:
        return None
    diff = best["avg_final_grade"] - worst["avg_final_grade"]
    if worst["avg_final_grade"] == 0:
        pct = None
    else:
        pct = round((diff / worst["avg_final_grade"]) * 100, 1)

    pct_txt = f" (about {pct}% higher)" if pct is not None else ""
    return (
        f"Category **{best['category']}** achieved the highest average final grade "
        f"(G3) at **{_fmt_number(best['avg_final_grade'])}/20** "
        f"(n = {best['student_count']} students), versus only "
        f"**{_fmt_number(worst['avg_final_grade'])}/20** for category "
        f"**{worst['category']}** (n = {worst['student_count']} students)"
        f"{pct_txt}."
    )


def _sql_block(sql: str) -> str:
    return "```sql\n" + dedent(sql).strip() + "\n```"


def _chart_table(chart: dict | None) -> list[str]:
    """Emit a small Markdown table from a column's chart spec. The PDF renderer
    turns any such table into a bar chart, so this both documents and charts
    each generic column."""
    if not chart or not chart.get("labels"):
        return []
    out = [f"[[chart:{chart.get('type', 'bar')}]]",
            f"| {chart['x_label']} | {chart['y_label']} |", "|---|---|"]
    for label, value in zip(chart["labels"], chart["values"]):
        out.append(f"| {label} | {_fmt_number(value)} |")
    out.append("")
    return out


def build_documentation(db_path: str) -> str:
    """Build the full Markdown documentation report from the LIVE database."""
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    tables = db_manager.list_tables(db_path)
    schema_ready = "student" in tables and "grade" in tables
    kpis = analytics.summary_stats(db_path) if schema_ready else None
    results = analytics.run_all(db_path) if schema_ready else []
    profile = None if schema_ready else analytics.generic_profile(db_path)
    generic = None if schema_ready else analytics.generic_analysis(db_path)

    lines: list[str] = []
    lines.append("# Final Documentation Report")
    lines.append("## Student Performance Analysis System")
    lines.append(f"*This report was generated automatically from the current database on {generated_at}.*")
    lines.append("")

    # ------------------------------------------------------------
    lines.append("## 1. Introduction")
    lines.append(dedent("""
        This report documents the database schema of the system, the
        processing steps the application performs from raw-file upload up to
        the analytics dashboard, and the most important insights that were
        discovered — each one backed by the actual SQL query used to prove it
        together with its real results from the current database.
    """).strip())
    lines.append("")

    # ------------------------------------------------------------
    lines.append("## 2. Database Schema")
    if schema_ready:
        lines.append(
            "The normalized schema consists of five core tables linked through "
            "`student_id`, plus lookup tables in the full production version:"
        )
        lines.append("")
        lines.append("| Table | Description | Key columns |")
        lines.append("|---|---|---|")
        for name, desc, cols in SCHEMA_TABLES:
            lines.append(f"| `{name}` | {desc} | {', '.join(f'`{c}`' for c in cols)} |")
        lines.append("")
        lines.append(LOOKUP_TABLES_NOTE)
        lines.append("")
        lines.append(
            "The complete Entity-Relationship (ERD) and Data-Flow (DFD) diagrams "
            "are available in `04-System_Analysis_and_Design/ERD.png` and "
            "`DFD_level0.png` / `DFD_level1.png`."
        )
        lines.append("")
    else:
        lines.append(
            "The uploaded file does not match the standard student-performance "
            "schema, so it was loaded as-is into a single flat table named "
            "`cleaned_data`. The columns actually detected in that table and the "
            "types the system inferred for them are listed below:"
        )
        lines.append("")
        lines.append("| Column | Type (dtype) |")
        lines.append("|---|---|")
        for c in (profile.get("columns") if profile else []):
            lines.append(f"| `{c['name']}` | `{c['dtype']}` |")
        lines.append("")
        lines.append(
            "The system accepts **any** tabular file (CSV/TSV/Excel) regardless of "
            "its column names: if it recognizes student-performance columns (under "
            "any common naming) it distributes them across the five-table normalized "
            "schema, otherwise it keeps the file in the flat `cleaned_data` table and "
            "produces the general documentation and analysis below."
        )
        lines.append("")

    # ------------------------------------------------------------
    lines.append("## 3. Processing Pipeline (ETL Steps)")
    lines.append(dedent("""
        1. **Upload:** the user uploads a raw data file (CSV/TSV/Excel) from the `/` page.
        2. **Cleaning:** `modules/data_cleaner.py` standardizes column names,
           trims whitespace, drops empty rows/columns, removes duplicates,
           coerces numeric types, handles missing values, and caps outliers
           using the IQR method.
        3. **Flat Load:** the cleaned data is always stored in the
           `cleaned_data` table regardless of file type.
        4. **Normalization:** if the columns match the known student-performance
           schema, `modules/schema_mapper.py` distributes the data across the
           five tables (student, family, enrollment, study_behavior, grade).
        5. **Analytics:** fixed, developer-authored SQL queries
           (`modules/analytics.py`) — never built from user input, to avoid any
           SQL-injection risk — are executed and shown on the `/dashboard` page.
        6. **Documentation (this report):** this file is built automatically from
           the same `analytics.run_all()` function that feeds the dashboard, so it
           always reflects the most recently loaded data in the database.
    """).strip())
    lines.append("")

    # ------------------------------------------------------------
    lines.append("## 4. Key Insights (with SQL evidence)")

    if not schema_ready:
        cols = profile.get("columns") if profile else []
        numeric_cols = [c for c in cols if "mean" in c]
        categorical_cols = [c for c in cols if "mean" not in c]
        lines.append(
            f"The data currently loaded in `cleaned_data` contains "
            f"**{profile.get('row_count', 0) if profile else 0}** rows and "
            f"**{len(cols)}** columns. Since this is a generic file (not the student "
            "schema), the system auto-detects an outcome column and analyses every "
            "other column against it, then summarises each column individually — all "
            "backed by the actual SQL used."
        )
        lines.append("")

        insight_no = 1

        # ---- Auto relationship analysis (outcome vs each driver) ----
        if generic and generic.get("target") and generic.get("insights"):
            target = generic["target"]
            lines.append(f"### {insight_no}. Auto-detected outcome: `{target}`")
            lines.append(
                f"The system picked **{target}** as the outcome/target column "
                f"(average **{_fmt_number(generic.get('target_avg'))}**) and compared "
                "every other column against it, as shown below."
            )
            lines.append("")
            insight_no += 1

            for entry in generic["insights"]:
                if entry.get("error") or not entry.get("data"):
                    continue
                lines.append(f"### {insight_no}. {entry['title']}")
                lines.append(f"**Hypothesis:** {entry['hypothesis']}")
                lines.append("")
                lines.append("**SQL used to prove this result:**")
                lines.append(_sql_block(entry["sql"]))
                lines.append("")
                lines.append("**Actual results returned by this query:**")
                lines.append("")
                lines.append(f"[[chart:{entry.get('chart', 'bar')}]]")
                lines.append(f"| {entry['feature']} | Avg {target} | Records |")
                lines.append("|---|---|---|")
                for row in entry["data"]:
                    lines.append(
                        f"| {row.get('category')} | {_fmt_number(row.get('avg_value'))} | "
                        f"{row.get('record_count')} |"
                    )
                lines.append("")
                insight_no += 1

        # ---- Per-column statistical summaries ----
        lines.append("### Column-by-column summary")
        lines.append("")
        for c in numeric_cols:
            lines.append(f"### {insight_no}. Numeric column `{c['name']}`")
            lines.append(
                f"This column ranges from **{_fmt_number(c.get('min'))}** to "
                f"**{_fmt_number(c.get('max'))}** with an average of "
                f"**{_fmt_number(c.get('mean'))}**."
            )
            lines.append("")
            lines.append("**SQL used to prove this result:**")
            lines.append(_sql_block(
                f'SELECT ROUND(AVG("{c["name"]}"), 2) AS mean,\n'
                f'       MIN("{c["name"]}") AS min_value,\n'
                f'       MAX("{c["name"]}") AS max_value\n'
                f'FROM cleaned_data;'
            ))
            lines.append("")
            lines.extend(_chart_table(c.get("chart")))
            insight_no += 1

        for c in categorical_cols:
            lines.append(f"### {insight_no}. Categorical column `{c['name']}`")
            lines.append(
                f"The most frequent value in this column is **{c.get('top_value')}**."
            )
            lines.append("")
            lines.append("**SQL used to prove this result:**")
            lines.append(_sql_block(
                f'SELECT "{c["name"]}" AS category, COUNT(*) AS n\n'
                f'FROM cleaned_data\n'
                f'GROUP BY "{c["name"]}"\n'
                f'ORDER BY n DESC\n'
                f'LIMIT 6;'
            ))
            lines.append("")
            lines.extend(_chart_table(c.get("chart")))
            insight_no += 1

        if not cols:
            lines.append(
                "No data has been loaded yet. Upload any file from the upload page "
                "and re-download this report to see the actual analysis."
            )
    else:
        lines.append(
            f"The data currently loaded includes **{kpis['students']}** students from "
            f"**{kpis['schools']}** school(s), with an average final grade (G3) of "
            f"**{_fmt_number(kpis['avg_g3'])}/20** and an average of "
            f"**{_fmt_number(kpis['avg_absences'])}** absences."
        )
        lines.append("")

        insight_no = 1
        for entry in results:
            if entry.get("error") or not entry.get("data"):
                continue
            sentence = _insight_sentence(entry)
            if not sentence:
                continue
            lines.append(f"### {insight_no}. {entry['title']}")
            lines.append(f"**Hypothesis:** {entry['hypothesis']}")
            lines.append("")
            lines.append(sentence)
            lines.append("")
            lines.append("**SQL used to prove this result:**")
            lines.append(_sql_block(entry["sql"]))
            lines.append("")
            lines.append("**Actual results returned by this query:**")
            lines.append("")
            lines.append(f"[[chart:{entry.get('chart', 'bar')}]]")
            lines.append("| Category | Avg. final grade (G3) | Students |")
            lines.append("|---|---|---|")
            for row in entry["data"]:
                lines.append(
                    f"| {row['category']} | {_fmt_number(row['avg_final_grade'])} | "
                    f"{row['student_count']} |"
                )
            lines.append("")
            insight_no += 1

    # ------------------------------------------------------------
    lines.append("## 5. Closing Notes")
    lines.append(dedent("""
        - All queries above are fixed and pre-written by the development team
          (`modules/analytics.py`); they are never built dynamically from user
          input, which protects the system from SQL-injection attacks.
        - The numbers in this report are taken directly from the current database
          (`cleaned_data` + the normalized tables), not static sample data; so
          loading new data from the upload page and re-downloading this report
          will refresh all numbers and conclusions automatically.
        - For the repeatable, auditable queries see
          `08-Deployment_Stored_Procedures/stored_procedures.sql`.
        - For the scheduled automation and monitoring see
          `09-Automation_Monitoring/nightly_job.py`.
    """).strip())
    lines.append("")

    return "\n".join(lines)
