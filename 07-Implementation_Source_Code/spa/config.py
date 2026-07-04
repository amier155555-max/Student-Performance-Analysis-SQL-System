"""
config.py
---------
Central configuration for the Student Performance Analysis GUI.

Runtime-editable settings (missing value strategy, duplicate handling,
outlier handling, etc.) are persisted to data/settings.json so changes
made on the Settings page survive an app restart. This module only
defines defaults and file locations; it never hard-codes secrets.
"""

import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# All runtime data lives under DATA_DIR. On a host with a persistent disk
# (e.g. Render), set SPA_DATA_DIR to the mounted disk path so uploads and the
# SQLite database survive restarts; otherwise it defaults to ./data.
DATA_DIR = os.environ.get("SPA_DATA_DIR", os.path.join(BASE_DIR, "data"))

UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
CLEANED_DIR = os.path.join(DATA_DIR, "cleaned")
DB_DIR = os.path.join(DATA_DIR, "db")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
DEFAULT_DB_PATH = os.path.join(DB_DIR, "student_performance.db")

ALLOWED_EXTENSIONS = {"csv", "xlsx", "xls", "tsv"}
MAX_CONTENT_LENGTH_MB = 50

DEFAULT_SETTINGS = {
    # -- Cleaning behavior --------------------------------------------
    "missing_strategy": "auto",       # auto | drop_rows | fill_mean | fill_median | fill_mode | fill_zero
    "missing_threshold_pct": 60,      # drop a column if more than this % of it is missing
    "remove_duplicates": True,
    "trim_whitespace": True,
    "standardize_column_names": True,
    "outlier_handling": "cap_iqr",    # none | cap_iqr | flag_only
    "outlier_iqr_multiplier": 1.5,
    "coerce_numeric_types": True,

    # -- Database / storage --------------------------------------------
    "database_path": DEFAULT_DB_PATH,
    "auto_populate_normalized_schema": True,
    "keep_upload_history": True,
    "max_upload_history": 10,

    # -- Application ------------------------------------------------
    "app_name": "Student Performance Analysis System",
    "theme": "calm-sage",
    "records_per_preview_page": 15,
}


def ensure_dirs():
    for d in (UPLOAD_DIR, CLEANED_DIR, DB_DIR, os.path.dirname(SETTINGS_FILE)):
        os.makedirs(d, exist_ok=True)


def load_settings() -> dict:
    """Load persisted settings, falling back to defaults for any missing key."""
    ensure_dirs()
    settings = dict(DEFAULT_SETTINGS)
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            settings.update({k: v for k, v in saved.items() if k in DEFAULT_SETTINGS})
        except (json.JSONDecodeError, OSError):
            # Corrupt or unreadable settings file -> fall back to defaults
            pass
    return settings


def save_settings(new_settings: dict) -> dict:
    """Validate and persist settings, returning the final merged dict."""
    ensure_dirs()
    current = load_settings()
    current.update({k: v for k, v in new_settings.items() if k in DEFAULT_SETTINGS})
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2)
    return current


def reset_settings() -> dict:
    ensure_dirs()
    if os.path.exists(SETTINGS_FILE):
        os.remove(SETTINGS_FILE)
    return load_settings()
