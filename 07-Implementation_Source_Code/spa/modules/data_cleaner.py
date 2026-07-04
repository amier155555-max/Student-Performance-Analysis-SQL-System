"""
modules/data_cleaner.py
------------------------
Reusable, dataset-agnostic cleaning pipeline.

Given ANY raw CSV/TSV/Excel file the client uploads, `DataCleaner.run()`
produces:
  1. a cleaned pandas DataFrame
  2. a JSON-serializable report describing exactly what was changed,
     so the client can see and trust the transformation.

The pipeline is intentionally generic (it does not assume the student
performance schema) so it can safely be reused for other datasets, but
`schema_mapper.py` layers the education-specific normalization on top
when the recognizable columns are present.
"""

from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd


class UnsupportedFileError(Exception):
    """Raised when an uploaded file cannot be parsed as tabular data."""


@dataclass
class CleaningReport:
    original_rows: int = 0
    original_columns: int = 0
    final_rows: int = 0
    final_columns: int = 0
    renamed_columns: dict = field(default_factory=dict)
    dropped_columns: list = field(default_factory=list)
    duplicate_rows_removed: int = 0
    empty_rows_removed: int = 0
    missing_values_before: dict = field(default_factory=dict)
    missing_values_after: dict = field(default_factory=dict)
    missing_value_strategy: str = ""
    outliers_capped: dict = field(default_factory=dict)
    dtype_conversions: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "original_rows": self.original_rows,
            "original_columns": self.original_columns,
            "final_rows": self.final_rows,
            "final_columns": self.final_columns,
            "renamed_columns": self.renamed_columns,
            "dropped_columns": self.dropped_columns,
            "duplicate_rows_removed": self.duplicate_rows_removed,
            "empty_rows_removed": self.empty_rows_removed,
            "missing_values_before": self.missing_values_before,
            "missing_values_after": self.missing_values_after,
            "missing_value_strategy": self.missing_value_strategy,
            "outliers_capped": self.outliers_capped,
            "dtype_conversions": self.dtype_conversions,
            "warnings": self.warnings,
        }


def load_raw_file(filepath: str) -> pd.DataFrame:
    """Read a client-supplied CSV/TSV/Excel file into a DataFrame.

    Raises UnsupportedFileError with a human-readable message on failure,
    instead of letting a raw parser exception reach the user.
    """
    ext = os.path.splitext(filepath)[1].lower().lstrip(".")
    try:
        if ext in ("csv",):
            return _read_csv_robust(filepath, sep=",")
        if ext in ("tsv",):
            return _read_csv_robust(filepath, sep="\t")
        if ext in ("xlsx", "xls"):
            return pd.read_excel(filepath)
        raise UnsupportedFileError(f"Unsupported file extension: '.{ext}'")
    except UnsupportedFileError:
        raise
    except Exception as exc:  # noqa: BLE001 - surfaced as a friendly error
        raise UnsupportedFileError(
            f"Could not read '{os.path.basename(filepath)}'. The file may be "
            f"corrupted or not a valid table. Details: {exc}"
        ) from exc


def _read_csv_robust(filepath: str, sep: str) -> pd.DataFrame:
    """Try a few common delimiters/encodings before giving up."""
    attempts = [
        {"sep": sep, "encoding": "utf-8"},
        {"sep": sep, "encoding": "latin-1"},
        {"sep": None, "engine": "python", "encoding": "utf-8"},
    ]
    last_error: Exception | None = None
    for kwargs in attempts:
        try:
            df = pd.read_csv(filepath, **kwargs)
            if df.shape[1] >= 1:
                return df
        except Exception as exc:  # noqa: BLE001
            last_error = exc
    raise UnsupportedFileError(f"Could not parse file as delimited text: {last_error}")


def _standardize_column_name(name: str) -> str:
    name = str(name).strip()
    name = unicodedata.normalize("NFKD", name)
    name = re.sub(r"[^\w\s]", "_", name)
    name = re.sub(r"\s+", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    return name.lower() or "column"


class DataCleaner:
    """Configurable cleaning pipeline driven by the Settings page."""

    def __init__(self, settings: dict):
        self.settings = settings
        self.report = CleaningReport()

    def run(self, df: pd.DataFrame) -> tuple[pd.DataFrame, CleaningReport]:
        df = df.copy()
        self.report.original_rows, self.report.original_columns = df.shape

        df = self._standardize_columns(df)
        df = self._strip_whitespace(df)
        df = self._drop_empty_rows_cols(df)
        df = self._remove_duplicates(df)
        df = self._coerce_types(df)
        self.report.missing_values_before = {
            c: int(n) for c, n in df.isna().sum().items() if n > 0
        }
        df = self._handle_missing(df)
        df = self._handle_outliers(df)

        self.report.missing_values_after = {
            c: int(n) for c, n in df.isna().sum().items() if n > 0
        }
        self.report.final_rows, self.report.final_columns = df.shape
        return df.reset_index(drop=True), self.report

    # ------------------------------------------------------------------
    def _standardize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        if not self.settings.get("standardize_column_names", True):
            return df
        renamed = {}
        seen = set()
        new_cols = []
        for col in df.columns:
            clean = _standardize_column_name(col)
            base = clean
            i = 1
            while clean in seen:
                clean = f"{base}_{i}"
                i += 1
            seen.add(clean)
            new_cols.append(clean)
            if clean != col:
                renamed[str(col)] = clean
        df.columns = new_cols
        self.report.renamed_columns = renamed
        return df

    def _strip_whitespace(self, df: pd.DataFrame) -> pd.DataFrame:
        if not self.settings.get("trim_whitespace", True):
            return df
        obj_cols = df.select_dtypes(include=["object", "string"]).columns
        for col in obj_cols:
            df[col] = df[col].astype(str).str.strip().replace(
                {"": np.nan, "nan": np.nan, "NaN": np.nan, "null": np.nan,
                 "NULL": np.nan, "None": np.nan, "N/A": np.nan, "n/a": np.nan,
                 "?": np.nan, "-": np.nan}
            )
        return df

    def _drop_empty_rows_cols(self, df: pd.DataFrame) -> pd.DataFrame:
        before_rows = len(df)
        df = df.dropna(axis=0, how="all")
        self.report.empty_rows_removed = before_rows - len(df)

        threshold = self.settings.get("missing_threshold_pct", 60) / 100.0
        dropped = []
        for col in df.columns:
            if df[col].isna().mean() > threshold:
                dropped.append(col)
        if dropped:
            df = df.drop(columns=dropped)
        self.report.dropped_columns = dropped
        return df

    def _remove_duplicates(self, df: pd.DataFrame) -> pd.DataFrame:
        if not self.settings.get("remove_duplicates", True):
            return df
        before = len(df)
        df = df.drop_duplicates()
        self.report.duplicate_rows_removed = before - len(df)
        return df

    def _coerce_types(self, df: pd.DataFrame) -> pd.DataFrame:
        if not self.settings.get("coerce_numeric_types", True):
            return df
        conversions = {}
        for col in df.columns:
            if df[col].dtype != object:
                continue
            coerced = pd.to_numeric(df[col], errors="coerce")
            # Only adopt the numeric version if we didn't blow away real data
            non_null = df[col].notna().sum()
            if non_null > 0 and coerced.notna().sum() / non_null >= 0.9:
                df[col] = coerced
                conversions[col] = "numeric"
        self.report.dtype_conversions = conversions
        return df

    def _handle_missing(self, df: pd.DataFrame) -> pd.DataFrame:
        strategy = self.settings.get("missing_strategy", "auto")
        self.report.missing_value_strategy = strategy
        if strategy == "drop_rows":
            return df.dropna(axis=0, how="any")

        for col in df.columns:
            if df[col].isna().sum() == 0:
                continue
            is_numeric = pd.api.types.is_numeric_dtype(df[col])
            if strategy == "fill_zero":
                df[col] = df[col].fillna(0 if is_numeric else "unknown")
            elif strategy == "fill_mean" and is_numeric:
                df[col] = df[col].fillna(round(df[col].mean(), 2))
            elif strategy == "fill_median" and is_numeric:
                df[col] = df[col].fillna(df[col].median())
            elif strategy == "fill_mode" or (strategy == "fill_mean" and not is_numeric):
                mode = df[col].mode(dropna=True)
                df[col] = df[col].fillna(mode.iloc[0] if not mode.empty else "unknown")
            else:  # "auto": numeric -> median, categorical -> mode
                if is_numeric:
                    df[col] = df[col].fillna(df[col].median())
                else:
                    mode = df[col].mode(dropna=True)
                    df[col] = df[col].fillna(mode.iloc[0] if not mode.empty else "unknown")
        return df

    def _handle_outliers(self, df: pd.DataFrame) -> pd.DataFrame:
        mode = self.settings.get("outlier_handling", "cap_iqr")
        if mode == "none":
            return df
        k = float(self.settings.get("outlier_iqr_multiplier", 1.5))
        capped = {}
        for col in df.select_dtypes(include=[np.number]).columns:
            q1, q3 = df[col].quantile(0.25), df[col].quantile(0.75)
            iqr = q3 - q1
            if iqr == 0 or pd.isna(iqr):
                continue
            low, high = q1 - k * iqr, q3 + k * iqr
            n_outliers = int(((df[col] < low) | (df[col] > high)).sum())
            if n_outliers == 0:
                continue
            if mode == "cap_iqr":
                df[col] = df[col].clip(lower=low, upper=high)
            capped[col] = n_outliers
        self.report.outliers_capped = capped
        return df
