"""
modules/db_manager.py
-----------------------
Thin, secure wrapper around SQLite storage for the cleaned data.

Design notes:
  * All SQL is parameterized or built from a fixed whitelist of table/
    column names defined in this codebase - never from raw user input -
    which avoids SQL injection.
  * A context manager (`get_connection`) guarantees connections are
    always closed, even on error.
  * Every public function has explicit error handling so a bad upload
    can never crash the whole app; failures surface as readable
    exceptions the Flask routes turn into flash messages.
"""

from __future__ import annotations

import contextlib
import os
import sqlite3
from typing import Iterable

import pandas as pd


class DatabaseError(Exception):
    """Raised for any recoverable database operation failure."""


@contextlib.contextmanager
def get_connection(db_path: str):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def write_dataframe(db_path: str, table_name: str, df: pd.DataFrame, if_exists: str = "replace") -> int:
    """Persist a DataFrame to SQLite. Returns the number of rows written."""
    try:
        with get_connection(db_path) as conn:
            df.to_sql(table_name, conn, if_exists=if_exists, index=False)
        return len(df)
    except Exception as exc:  # noqa: BLE001
        raise DatabaseError(f"Failed writing table '{table_name}': {exc}") from exc


def write_normalized_tables(db_path: str, tables: dict[str, pd.DataFrame]) -> dict[str, int]:
    written = {}
    for name, frame in tables.items():
        written[name] = write_dataframe(db_path, name, frame, if_exists="replace")
    return written


# The five tables that make up the normalized education schema. Kept here so
# every upload can wipe stale copies before (re)populating — otherwise data
# from a previous student file would linger and the dashboard would keep
# showing old analytics after a new, non-matching file is uploaded.
NORMALIZED_TABLES = ["grade", "study_behavior", "enrollment", "family", "student"]


def drop_tables(db_path: str, table_names: Iterable[str]) -> None:
    """Drop the given tables if they exist (order matters for FKs)."""
    if not os.path.exists(db_path):
        return
    try:
        with get_connection(db_path) as conn:
            for name in table_names:
                conn.execute(f'DROP TABLE IF EXISTS "{name}"')
    except Exception as exc:  # noqa: BLE001
        raise DatabaseError(f"Failed dropping tables: {exc}") from exc


def run_query(db_path: str, sql: str, params: Iterable = ()) -> pd.DataFrame:
    """Run a read-only analytics query and return the results as a DataFrame.

    Only SELECT statements are permitted here - this function is used
    exclusively for the analytics dashboard's fixed, developer-authored
    queries, never for arbitrary user-supplied SQL.
    """
    normalized = sql.strip().lower()
    if not normalized.startswith("select"):
        raise DatabaseError("Only SELECT statements may be run through run_query().")
    try:
        with get_connection(db_path) as conn:
            return pd.read_sql_query(sql, conn, params=params)
    except Exception as exc:  # noqa: BLE001
        raise DatabaseError(f"Query failed: {exc}") from exc


def table_exists(db_path: str, table_name: str) -> bool:
    if not os.path.exists(db_path):
        return False
    try:
        with get_connection(db_path) as conn:
            cur = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,),
            )
            return cur.fetchone() is not None
    except Exception:
        return False


def list_tables(db_path: str) -> list[str]:
    if not os.path.exists(db_path):
        return []
    try:
        with get_connection(db_path) as conn:
            cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            return [row[0] for row in cur.fetchall()]
    except Exception:
        return []


def reset_database(db_path: str) -> None:
    """Remove the SQLite file entirely (used by Settings -> Reset)."""
    if os.path.exists(db_path):
        os.remove(db_path)
