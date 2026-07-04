"""
modules/schema_mapper.py
--------------------------
Best-effort mapping from a cleaned, generic DataFrame onto the
normalized Student Performance schema (see
04-System_Analysis_and_Design/schema.sql in the docs bundle).

If the uploaded file is the familiar UCI-style "student-mat"/"student-por"
dataset (or close enough - column names are matched loosely and case
insensitively), this module will populate the relational tables so the
analytics dashboard can run its hypothesis-testing SQL. If the columns
don't match, the flat `cleaned_data` table is still available and the
dashboard falls back to generic profiling.
"""

from __future__ import annotations

import re

import pandas as pd

# Canonical column -> accepted aliases found in the wild. The matcher below
# is tolerant of separators/casing (it normalizes "Study Time", "study-time"
# and "study_time" to the same thing), so aliases here only need to cover
# genuinely *different wording* for the same concept, not spelling variants.
COLUMN_ALIASES = {
    "school": ["school", "school_name", "institution"],
    "sex": ["sex", "gender", "student_sex"],
    "age": ["age", "student_age"],
    "address": ["address", "address_type", "location_type", "residence"],
    "famsize": ["famsize", "family_size", "household_size"],
    "pstatus": ["pstatus", "parent_status", "parental_status", "cohabitation_status"],
    "medu": ["medu", "mother_education", "mom_education", "mother_edu"],
    "fedu": ["fedu", "father_education", "dad_education", "father_edu"],
    "mjob": ["mjob", "mother_job", "mom_job"],
    "fjob": ["fjob", "father_job", "dad_job"],
    "reason": ["reason", "enrollment_reason", "reason_to_choose_school"],
    "guardian": ["guardian", "guardian_type"],
    "traveltime": ["traveltime", "travel_time", "commute_time"],
    "studytime": ["studytime", "study_time", "study_hours", "weekly_study_time",
                   "hours_studied", "study_time_weekly"],
    "failures": ["failures", "past_failures", "class_failures", "num_failures",
                  "number_of_failures"],
    "schoolsup": ["schoolsup", "school_support", "extra_school_support"],
    "famsup": ["famsup", "family_support", "family_educational_support"],
    "paid": ["paid", "paid_classes", "extra_paid_classes"],
    "activities": ["activities", "extra_activities", "extracurricular_activities"],
    "nursery": ["nursery", "attended_nursery"],
    "higher": ["higher", "wants_higher_education", "higher_education"],
    "internet": ["internet", "internet_access", "home_internet"],
    "romantic": ["romantic", "in_relationship", "romantic_relationship"],
    "famrel": ["famrel", "family_relationship", "family_relation_quality"],
    "freetime": ["freetime", "free_time", "leisure_time"],
    "goout": ["goout", "go_out", "going_out", "goes_out"],
    "dalc": ["dalc", "workday_alcohol", "weekday_alcohol", "daily_alcohol"],
    "walc": ["walc", "weekend_alcohol"],
    "health": ["health", "health_status"],
    "absences": ["absences", "absence", "days_absent", "total_absences",
                  "number_of_absences"],
    "g1": ["g1", "grade1", "period1_grade", "first_period_grade", "grade_1"],
    "g2": ["g2", "grade2", "period2_grade", "second_period_grade", "grade_2"],
    "g3": ["g3", "grade3", "period3_grade", "final_grade", "grade_3",
            "final_score", "final_result"],
}

# Columns that must be present (after alias resolution) for the education
# schema to be considered a confident match.
CORE_REQUIRED = ["sex", "age", "studytime", "failures", "absences"]

BOOLISH_TRUE = {"yes", "true", "1", "1.0", "t", "y"}


def _norm(text: str) -> str:
    """Collapse a name to lowercase alphanumerics only (drops _, -, space)."""
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


def _tokens(text: str) -> set[str]:
    """Split a name into its lowercase alphanumeric word tokens."""
    return {t for t in re.split(r"[^a-z0-9]+", str(text).lower()) if t}


def _resolve_aliases(columns: list[str]) -> dict[str, str]:
    """Map each canonical schema field to the best-matching actual column.

    Matching is tolerant of different separators and casing, and also matches
    when an alias appears as a whole word inside a longer column name (e.g.
    canonical ``age`` matches a column literally named ``Student Age``). Each
    actual column is claimed by at most one canonical field.
    """
    # Precompute normalized forms + normalized token sets for every column.
    col_forms = [(c, _norm(c), {_norm(t) for t in _tokens(c)}) for c in columns]
    found: dict[str, str] = {}
    used: set[str] = set()

    for canonical, aliases in COLUMN_ALIASES.items():
        alias_norms = {_norm(a) for a in aliases}
        match_col = None

        # Pass 1 (strongest): the whole column name normalizes to an alias.
        for actual, norm, _toks in col_forms:
            if actual not in used and norm in alias_norms:
                match_col = actual
                break

        # Pass 2: an alias appears as a standalone word token of the column.
        if match_col is None:
            for actual, _norm_val, toks in col_forms:
                if actual not in used and alias_norms & toks:
                    match_col = actual
                    break

        if match_col is not None:
            found[canonical] = match_col
            used.add(match_col)

    return found


def detect_education_schema(df: pd.DataFrame) -> dict[str, str] | None:
    """Return the alias map if this looks like the student-performance dataset."""
    mapping = _resolve_aliases(list(df.columns))
    if all(req in mapping for req in CORE_REQUIRED):
        return mapping
    return None


def _to_bool(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin(BOOLISH_TRUE)


def build_normalized_tables(df: pd.DataFrame, mapping: dict[str, str]) -> dict[str, pd.DataFrame]:
    """Split the flat cleaned DataFrame into the normalized schema's tables.

    Returns a dict of {table_name: DataFrame} ready to be written with
    to_sql(). Foreign keys are expressed via a shared synthetic
    `student_id` (the DataFrame's row position), matching schema.sql's
    student.student_id being the hub of every child table.
    """
    n = len(df)
    student_id = pd.RangeIndex(1, n + 1)
    tables: dict[str, pd.DataFrame] = {}

    def col(name, default=None):
        return df[mapping[name]] if name in mapping else pd.Series([default] * n)

    tables["student"] = pd.DataFrame({
        "student_id": student_id,
        "school": col("school", "NA").astype(str),
        "sex": col("sex", "NA").astype(str).str.upper().str[0],
        "age": pd.to_numeric(col("age"), errors="coerce"),
        "address": col("address", "U").astype(str).str.upper().str[0],
        "internet": _to_bool(col("internet", "no")) if "internet" in mapping else False,
        "romantic": _to_bool(col("romantic", "no")) if "romantic" in mapping else False,
        "higher": _to_bool(col("higher", "yes")) if "higher" in mapping else True,
        "nursery": _to_bool(col("nursery", "no")) if "nursery" in mapping else False,
        "activities": _to_bool(col("activities", "no")) if "activities" in mapping else False,
        "health": pd.to_numeric(col("health", 3), errors="coerce").fillna(3),
        "absences": pd.to_numeric(col("absences", 0), errors="coerce").fillna(0),
    })

    tables["family"] = pd.DataFrame({
        "student_id": student_id,
        "guardian": col("guardian", "mother").astype(str),
        "famsize": col("famsize", "GT3").astype(str),
        "pstatus": col("pstatus", "T").astype(str).str.upper().str[0],
        "famrel": pd.to_numeric(col("famrel", 4), errors="coerce").fillna(4),
        "medu": pd.to_numeric(col("medu", 2), errors="coerce").fillna(2),
        "fedu": pd.to_numeric(col("fedu", 2), errors="coerce").fillna(2),
        "mjob": col("mjob", "other").astype(str),
        "fjob": col("fjob", "other").astype(str),
        "famsup": _to_bool(col("famsup", "no")) if "famsup" in mapping else False,
    })

    tables["enrollment"] = pd.DataFrame({
        "student_id": student_id,
        "reason": col("reason", "course").astype(str),
        "traveltime": pd.to_numeric(col("traveltime", 1), errors="coerce").fillna(1),
        "schoolsup": _to_bool(col("schoolsup", "no")) if "schoolsup" in mapping else False,
        "paid": _to_bool(col("paid", "no")) if "paid" in mapping else False,
    })

    tables["study_behavior"] = pd.DataFrame({
        "student_id": student_id,
        "studytime": pd.to_numeric(col("studytime"), errors="coerce"),
        "failures": pd.to_numeric(col("failures", 0), errors="coerce").fillna(0),
        "freetime": pd.to_numeric(col("freetime", 3), errors="coerce").fillna(3),
        "goout": pd.to_numeric(col("goout", 3), errors="coerce").fillna(3),
        "dalc": pd.to_numeric(col("dalc", 1), errors="coerce").fillna(1),
        "walc": pd.to_numeric(col("walc", 1), errors="coerce").fillna(1),
    })

    grade_rows = []
    for period, key in ((1, "g1"), (2, "g2"), (3, "g3")):
        if key in mapping:
            values = pd.to_numeric(df[mapping[key]], errors="coerce")
            for sid, score in zip(student_id, values):
                if pd.notna(score):
                    grade_rows.append({"student_id": sid, "period": period, "score": score})
    tables["grade"] = pd.DataFrame(grade_rows, columns=["student_id", "period", "score"])

    return tables
