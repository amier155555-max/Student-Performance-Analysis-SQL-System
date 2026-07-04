"""
tests/test_cleaner.py
-----------------------
Unit tests for the cleaning pipeline, schema mapper, and DB manager.
Run with:  python -m unittest discover -s tests -v
"""

import os
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.data_cleaner import DataCleaner, UnsupportedFileError, load_raw_file
from modules.schema_mapper import detect_education_schema, build_normalized_tables
from modules import db_manager
import config


DEFAULT_SETTINGS = dict(config.DEFAULT_SETTINGS)


class TestDataCleaner(unittest.TestCase):
    def setUp(self):
        self.settings = dict(DEFAULT_SETTINGS)

    def test_standardizes_column_names(self):
        df = pd.DataFrame({"  First Name ": ["a"], "Age (Years)": [10]})
        cleaned, report = DataCleaner(self.settings).run(df)
        self.assertIn("first_name", cleaned.columns)
        self.assertIn("age_years", cleaned.columns)
        self.assertEqual(report.renamed_columns["  First Name "], "first_name")

    def test_removes_duplicate_rows(self):
        df = pd.DataFrame({"a": [1, 1, 2], "b": [2, 2, 3]})
        cleaned, report = DataCleaner(self.settings).run(df)
        self.assertEqual(len(cleaned), 2)
        self.assertEqual(report.duplicate_rows_removed, 1)

    def test_drops_mostly_empty_columns(self):
        df = pd.DataFrame({
            "a": [1, 2, 3, 4, 5],
            "mostly_empty": [np.nan, np.nan, np.nan, np.nan, 1],
        })
        cleaned, report = DataCleaner(self.settings).run(df)
        self.assertNotIn("mostly_empty", cleaned.columns)
        self.assertIn("mostly_empty", report.dropped_columns)

    def test_fills_missing_values_with_median_by_default(self):
        df = pd.DataFrame({"score": [10.0, 20.0, np.nan, 30.0, 40.0, 50.0]})
        cleaned, _ = DataCleaner(self.settings).run(df)
        self.assertEqual(cleaned["score"].isna().sum(), 0)

    def test_trims_whitespace_and_normalizes_blanks(self):
        df = pd.DataFrame({"x": ["  hi  ", "N/A", "ok"], "n": [1, 2, 3]})
        cleaned, _ = DataCleaner(self.settings).run(df)
        self.assertEqual(cleaned.loc[0, "x"], "hi")
        # N/A should have been treated as missing then filled by mode
        self.assertNotEqual(str(cleaned.loc[1, "x"]).lower(), "n/a")

    def test_caps_outliers_with_iqr(self):
        values = [10, 11, 12, 13, 14, 500]  # 500 is an extreme outlier
        df = pd.DataFrame({"v": values})
        cleaned, report = DataCleaner(self.settings).run(df)
        self.assertLess(cleaned["v"].max(), 500)
        self.assertIn("v", report.outliers_capped)

    def test_empty_dataframe_does_not_crash(self):
        df = pd.DataFrame()
        cleaned, report = DataCleaner(self.settings).run(df)
        self.assertEqual(len(cleaned), 0)

    def test_unsupported_extension_raises(self):
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as f:
            f.write(b"not a table")
            path = f.name
        try:
            with self.assertRaises(UnsupportedFileError):
                load_raw_file(path)
        finally:
            os.remove(path)


class TestSchemaMapper(unittest.TestCase):
    def test_detects_education_schema(self):
        df = pd.DataFrame({
            "sex": ["F", "M"], "age": [16, 17], "studytime": [2, 3],
            "failures": [0, 1], "absences": [2, 4],
        })
        mapping = detect_education_schema(df)
        self.assertIsNotNone(mapping)
        self.assertIn("sex", mapping)

    def test_rejects_unrelated_schema(self):
        df = pd.DataFrame({"product": ["a"], "price": [10]})
        mapping = detect_education_schema(df)
        self.assertIsNone(mapping)

    def test_builds_normalized_tables(self):
        df = pd.DataFrame({
            "sex": ["F", "M"], "age": [16, 17], "studytime": [2, 3],
            "failures": [0, 1], "absences": [2, 4], "g3": [15, 12],
        })
        mapping = detect_education_schema(df)
        tables = build_normalized_tables(df, mapping)
        self.assertIn("student", tables)
        self.assertIn("grade", tables)
        self.assertEqual(len(tables["student"]), 2)


class TestDbManager(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp_dir, "test.db")

    def test_write_and_query_dataframe(self):
        df = pd.DataFrame({"a": [1, 2, 3]})
        db_manager.write_dataframe(self.db_path, "t", df)
        self.assertTrue(db_manager.table_exists(self.db_path, "t"))
        result = db_manager.run_query(self.db_path, "SELECT * FROM t;")
        self.assertEqual(len(result), 3)

    def test_rejects_non_select_queries(self):
        with self.assertRaises(db_manager.DatabaseError):
            db_manager.run_query(self.db_path, "DROP TABLE t;")


if __name__ == "__main__":
    unittest.main()
