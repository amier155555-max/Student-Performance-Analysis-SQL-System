"""
modules/analytics.py
----------------------
Milestone 2 - "Build analytical queries for hypothesis testing".

Each function below is a fixed, developer-authored SQL query (never
built from user input) that tests one specific, named hypothesis about
factors influencing student performance, run against the normalized
schema populated by schema_mapper.py.
"""

from __future__ import annotations

import pandas as pd

from . import db_manager

# Each entry: (title, hypothesis statement, SQL, chart kind)
QUERIES = [
    {
        "id": "studytime_vs_grade",
        "title": "Study time vs. final grade",
        "hypothesis": "Students who study more hours per week achieve higher final grades (G3).",
        "chart": "bar",
        "sql": """
            SELECT sb.studytime AS category,
                   ROUND(AVG(g.score), 2) AS avg_final_grade,
                   COUNT(DISTINCT sb.student_id) AS student_count
            FROM study_behavior sb
            JOIN grade g ON g.student_id = sb.student_id AND g.period = 3
            GROUP BY sb.studytime
            ORDER BY sb.studytime;
        """,
    },
    {
        "id": "absences_vs_grade",
        "title": "Absences vs. final grade",
        "hypothesis": "Higher absence counts are associated with lower final grades.",
        "chart": "line",
        "sql": """
            SELECT CASE
                     WHEN s.absences = 0 THEN '0'
                     WHEN s.absences BETWEEN 1 AND 5 THEN '1-5'
                     WHEN s.absences BETWEEN 6 AND 10 THEN '6-10'
                     WHEN s.absences BETWEEN 11 AND 20 THEN '11-20'
                     ELSE '20+'
                   END AS category,
                   ROUND(AVG(g.score), 2) AS avg_final_grade,
                   COUNT(DISTINCT s.student_id) AS student_count
            FROM student s
            JOIN grade g ON g.student_id = s.student_id AND g.period = 3
            GROUP BY category
            ORDER BY MIN(s.absences);
        """,
    },
    {
        "id": "parent_education_vs_grade",
        "title": "Parental education vs. final grade",
        "hypothesis": "Students whose mothers have higher education levels tend to score higher.",
        "chart": "bar",
        "sql": """
            SELECT f.medu AS category,
                   ROUND(AVG(g.score), 2) AS avg_final_grade,
                   COUNT(DISTINCT f.student_id) AS student_count
            FROM family f
            JOIN grade g ON g.student_id = f.student_id AND g.period = 3
            GROUP BY f.medu
            ORDER BY f.medu;
        """,
    },
    {
        "id": "alcohol_vs_grade",
        "title": "Weekend alcohol consumption vs. final grade",
        "hypothesis": "Higher weekend alcohol consumption correlates with lower final grades.",
        "chart": "line",
        "sql": """
            SELECT sb.walc AS category,
                   ROUND(AVG(g.score), 2) AS avg_final_grade,
                   COUNT(DISTINCT sb.student_id) AS student_count
            FROM study_behavior sb
            JOIN grade g ON g.student_id = sb.student_id AND g.period = 3
            GROUP BY sb.walc
            ORDER BY sb.walc;
        """,
    },
    {
        "id": "internet_vs_grade",
        "title": "Internet access vs. final grade",
        "hypothesis": "Students with home internet access score higher on average.",
        "chart": "doughnut",
        "sql": """
            SELECT CASE WHEN s.internet = 1 THEN 'Has internet' ELSE 'No internet' END AS category,
                   ROUND(AVG(g.score), 2) AS avg_final_grade,
                   COUNT(DISTINCT s.student_id) AS student_count
            FROM student s
            JOIN grade g ON g.student_id = s.student_id AND g.period = 3
            GROUP BY s.internet;
        """,
    },
    {
        "id": "schoolsup_vs_grade",
        "title": "Extra school support vs. final grade",
        "hypothesis": "Students receiving extra school educational support catch up in final grades.",
        "chart": "pie",
        "sql": """
            SELECT CASE WHEN e.schoolsup = 1 THEN 'Receives support' ELSE 'No extra support' END AS category,
                   ROUND(AVG(g.score), 2) AS avg_final_grade,
                   COUNT(DISTINCT e.student_id) AS student_count
            FROM enrollment e
            JOIN grade g ON g.student_id = e.student_id AND g.period = 3
            GROUP BY e.schoolsup;
        """,
    },
    {
        "id": "failures_vs_grade",
        "title": "Past class failures vs. final grade",
        "hypothesis": "Students with more past class failures score lower on their final grade.",
        "chart": "bar",
        "sql": """
            SELECT sb.failures AS category,
                   ROUND(AVG(g.score), 2) AS avg_final_grade,
                   COUNT(DISTINCT sb.student_id) AS student_count
            FROM study_behavior sb
            JOIN grade g ON g.student_id = sb.student_id AND g.period = 3
            GROUP BY sb.failures
            ORDER BY sb.failures;
        """,
    },
    {
        "id": "grade_trend",
        "title": "Grade trend across periods (G1 -> G2 -> G3)",
        "hypothesis": "Average grades stay broadly consistent across the three grading periods.",
        "chart": "line",
        "sql": """
            SELECT period AS category, ROUND(AVG(score), 2) AS avg_final_grade,
                   COUNT(DISTINCT student_id) AS student_count
            FROM grade
            GROUP BY period
            ORDER BY period;
        """,
    },
]


def summary_stats(db_path: str) -> dict:
    """High-level KPIs shown at the top of the dashboard."""
    stats = {"students": 0, "avg_g3": None, "avg_absences": None, "schools": 0}
    if not db_manager.table_exists(db_path, "student"):
        return stats
    try:
        df = db_manager.run_query(db_path, "SELECT COUNT(*) AS n FROM student;")
        stats["students"] = int(df.iloc[0]["n"])

        df = db_manager.run_query(db_path, "SELECT AVG(score) AS a FROM grade WHERE period = 3;")
        val = df.iloc[0]["a"]
        stats["avg_g3"] = round(float(val), 2) if val is not None else None

        df = db_manager.run_query(db_path, "SELECT AVG(absences) AS a FROM student;")
        val = df.iloc[0]["a"]
        stats["avg_absences"] = round(float(val), 2) if val is not None else None

        df = db_manager.run_query(db_path, "SELECT COUNT(DISTINCT school) AS n FROM student;")
        stats["schools"] = int(df.iloc[0]["n"])
    except db_manager.DatabaseError:
        pass
    return stats


def run_all(db_path: str) -> list[dict]:
    """Execute every hypothesis query and attach its results (or an error)."""
    results = []
    for spec in QUERIES:
        entry = dict(spec)
        try:
            df = db_manager.run_query(db_path, spec["sql"])
            entry["data"] = df.to_dict(orient="records")
            entry["error"] = None
        except db_manager.DatabaseError as exc:
            entry["data"] = []
            entry["error"] = str(exc)
        results.append(entry)
    return results


def generic_profile(db_path: str, table_name: str = "cleaned_data") -> dict:
    """Fallback profiling for uploads that don't match the education schema.

    Each column also carries a `chart` spec ({x_label, y_label, labels,
    values}) so the dashboard and the PDF report can draw a small bar chart
    per column:
      * numeric column     -> Min / Mean / Max bars
      * categorical column -> top value counts
    """
    profile = {"row_count": 0, "sampled_rows": 0, "columns": []}
    if not db_manager.table_exists(db_path, table_name):
        return profile
    try:
        # True total row count (not the sampled slice used for profiling).
        total = db_manager.run_query(db_path, f'SELECT COUNT(*) AS n FROM "{table_name}";')
        profile["row_count"] = int(total.iloc[0]["n"])

        df = db_manager.run_query(db_path, f'SELECT * FROM "{table_name}" LIMIT 5000;')
        profile["sampled_rows"] = len(df)
        for col in df.columns:
            series = df[col]
            col_info = {"name": col, "dtype": str(series.dtype), "chart": None}
            if pd.api.types.is_numeric_dtype(series) and series.notna().any():
                mn = round(float(series.min()), 2)
                mean = round(float(series.mean()), 2)
                mx = round(float(series.max()), 2)
                col_info.update({"mean": mean, "min": mn, "max": mx})
                col_info["chart"] = {
                    "type": "bar",
                    "x_label": "Metric", "y_label": "Value",
                    "labels": ["Min", "Mean", "Max"], "values": [mn, mean, mx],
                }
            else:
                counts = series.value_counts().head(6)
                col_info["top_value"] = str(counts.index[0]) if not counts.empty else None
                if not counts.empty:
                    col_info["chart"] = {
                        "type": "doughnut",
                        "x_label": "Value", "y_label": "Count",
                        "labels": [str(i) for i in counts.index.tolist()],
                        "values": [int(v) for v in counts.tolist()],
                    }
            profile["columns"].append(col_info)
    except db_manager.DatabaseError:
        pass
    return profile
