"""
modules/analytics.py
----------------------
Analytical SQL queries for hypothesis testing.

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


# Column-name keywords that hint a numeric column is an outcome/target worth
# analysing everything else against.
_TARGET_KEYWORDS = (
    "score", "grade", "gpa", "mark", "result", "final", "total", "target",
    "rating", "price", "sales", "revenue", "amount", "salary", "income", "output",
)


def _is_id_like(name: str) -> bool:
    n = name.lower()
    return n == "id" or n.endswith("_id") or n.startswith("id_") or n == "index"


def generic_analysis(db_path: str, table_name: str = "cleaned_data",
                      max_features: int = 8) -> dict:
    """General, dataset-agnostic relationship analysis for ANY uploaded file.

    Picks a numeric "target" column (an outcome like a score/price/rating) and
    compares every other column against it, exactly like the student dashboard
    tests hypotheses — but for whatever columns the file happens to have:
      * categorical column -> average target per category (bar chart)
      * numeric column     -> average target across value quartiles (line chart)

    Returns {target, target_avg, row_count, insights:[...]} where each insight
    carries its title, hypothesis, the actual SQL, the returned rows, and a
    `chart` spec the dashboard/PDF can draw. Returns target=None when the file
    has no usable numeric outcome column.
    """
    result = {"target": None, "target_avg": None, "row_count": 0, "insights": []}
    if not db_manager.table_exists(db_path, table_name):
        return result
    try:
        sample = db_manager.run_query(db_path, f'SELECT * FROM "{table_name}" LIMIT 20000;')
    except db_manager.DatabaseError:
        return result
    if sample.empty:
        return result

    numeric_cols, categorical_cols = [], []
    for col in sample.columns:
        s = sample[col]
        if pd.api.types.is_numeric_dtype(s) and s.notna().sum() > 1:
            variance = float(s.var()) if s.var() == s.var() else 0.0  # NaN guard
            numeric_cols.append((col, _is_id_like(col), variance))
        else:
            nun = int(s.nunique(dropna=True))
            if 2 <= nun <= 12:
                categorical_cols.append(col)

    non_id_numeric = [c for c, is_id, _ in numeric_cols if not is_id]
    if not non_id_numeric:
        return result

    target = next((c for c in non_id_numeric
                   if any(k in c.lower() for k in _TARGET_KEYWORDS)), None)
    if target is None:
        target = max(((c, v) for c, is_id, v in numeric_cols if not is_id),
                      key=lambda x: x[1])[0]
    result["target"] = target

    try:
        row = db_manager.run_query(
            db_path, f'SELECT ROUND(AVG("{target}"), 2) AS a, COUNT(*) AS n FROM "{table_name}";')
        result["target_avg"] = float(row.iloc[0]["a"]) if row.iloc[0]["a"] is not None else None
        result["row_count"] = int(row.iloc[0]["n"])
    except db_manager.DatabaseError:
        return result

    specs = []
    # Categorical drivers -> average target per category (bar).
    for c in categorical_cols:
        if c == target:
            continue
        specs.append({
            "id": f"cat_{c}", "chart": "bar", "feature": c,
            "title": f"{target} by {c}",
            "hypothesis": f"Average {target} differs across {c} groups.",
            "sql": (f'SELECT "{c}" AS category,\n'
                     f'       ROUND(AVG("{target}"), 2) AS avg_value,\n'
                     f'       COUNT(*) AS record_count\n'
                     f'FROM {table_name}\n'
                     f'GROUP BY "{c}"\n'
                     f'ORDER BY avg_value DESC\n'
                     f'LIMIT 12;'),
        })

    # Numeric drivers -> average target across quartile buckets (line).
    for c, is_id, _ in numeric_cols:
        if is_id or c == target:
            continue
        vals = sample[c].dropna()
        if vals.nunique() < 4:
            continue
        q1, q2, q3 = (round(float(vals.quantile(q)), 4) for q in (0.25, 0.5, 0.75))
        if not (q1 < q2 < q3):
            continue
        specs.append({
            "id": f"num_{c}", "chart": "line", "feature": c,
            "title": f"{target} by {c} (quartiles)",
            "hypothesis": f"{target} changes as {c} increases.",
            "sql": (f"SELECT CASE\n"
                     f"         WHEN \"{c}\" <= {q1} THEN 'Q1 (low)'\n"
                     f"         WHEN \"{c}\" <= {q2} THEN 'Q2'\n"
                     f"         WHEN \"{c}\" <= {q3} THEN 'Q3'\n"
                     f"         ELSE 'Q4 (high)'\n"
                     f"       END AS category,\n"
                     f'       ROUND(AVG("{target}"), 2) AS avg_value,\n'
                     f'       COUNT(*) AS record_count\n'
                     f'FROM {table_name}\n'
                     f'GROUP BY category\n'
                     f'ORDER BY MIN("{c}");'),
        })

    for spec in specs[:max_features]:
        entry = dict(spec)
        try:
            df = db_manager.run_query(db_path, spec["sql"])
            rows = df.to_dict(orient="records")
            entry["data"] = rows
            entry["error"] = None
            entry["chart_data"] = {
                "type": spec["chart"],
                "x_label": spec["feature"],
                "y_label": f"Avg {target}",
                "labels": [str(r["category"]) for r in rows],
                "values": [r["avg_value"] for r in rows],
            }
        except db_manager.DatabaseError as exc:
            entry["data"] = []
            entry["error"] = str(exc)
            entry["chart_data"] = None
        result["insights"].append(entry)

    return result
