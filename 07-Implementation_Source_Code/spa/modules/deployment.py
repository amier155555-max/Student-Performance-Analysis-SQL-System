"""
modules/deployment.py
----------------------
GUI bridge for Milestone 3 (stored procedures for repeat analysis) and
Milestone 4 (nightly / batch automation).

It reuses the exact same "stored procedure" implementation that the
deployment package and the nightly job use
(08-Deployment_Stored_Procedures/sqlite_equivalent.py), so the buttons in
the GUI trigger identical logic to the command-line / scheduled runs — no
duplicated analysis SQL.

  * run_procedures()  -> Milestone 3: run every stored-procedure-equivalent,
                          logging each run and persisting results.
  * run_batch()       -> Milestone 4: the same run, plus a timestamped JSON
                          report written to 09-Automation_Monitoring/reports,
                          exactly like nightly_job.py produces on a schedule.
  * run_log() / latest_results() -> read back what the procedures recorded.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sqlite3
import sys

import config

# Make the deployment package importable so we reuse its logic verbatim.
_DEPLOY_DIR = os.path.abspath(
    os.path.join(config.BASE_DIR, "..", "..", "08-Deployment_Stored_Procedures")
)
_AUTOMATION_DIR = os.path.abspath(
    os.path.join(config.BASE_DIR, "..", "..", "09-Automation_Monitoring")
)
if _DEPLOY_DIR not in sys.path:
    sys.path.insert(0, _DEPLOY_DIR)

import sqlite_equivalent as _sp  # noqa: E402  (path set above)


def run_procedures(db_path: str) -> dict:
    """Milestone 3 — run all stored-procedure-equivalents once."""
    return _sp.run_all_analyses(db_path)


def latest_results(db_path: str) -> list[dict]:
    """Latest persisted result rows per procedure (Milestone 3 output)."""
    try:
        return _sp.latest_results(db_path)
    except Exception:  # noqa: BLE001
        return []


def run_log(db_path: str, limit: int = 20) -> list[dict]:
    """Recent rows from analysis_run_log (audit trail of every run)."""
    if not os.path.exists(db_path):
        return []
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT run_id, procedure, started_at, finished_at, row_count, status "
                "FROM analysis_run_log ORDER BY run_id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
    except sqlite3.Error:
        return []


def run_batch(db_path: str) -> dict:
    """Milestone 4 — run the analysis as a batch job and write a JSON report
    snapshot into 09-Automation_Monitoring/reports (same output the scheduled
    nightly_job.py produces). Returns a status summary."""
    started = dt.datetime.now(dt.timezone.utc)
    summary = run_procedures(db_path)

    report_dir = os.path.join(_AUTOMATION_DIR, "reports")
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, f"report_{started.strftime('%Y%m%d_%H%M%S')}.json")
    finished = dt.datetime.now(dt.timezone.utc)
    payload = {
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "database": db_path,
        "succeeded": summary["ok"],
        "failed": summary["failed"],
        "latest_results_sample": latest_results(db_path)[:10],
    }
    try:
        with open(report_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
    except OSError:
        report_path = None

    return {
        "ok": summary["ok"],
        "failed": summary["failed"],
        "report_path": report_path,
        "duration_s": round((finished - started).total_seconds(), 2),
    }


def last_batch_report() -> dict | None:
    """Return the most recent nightly/batch JSON report, if any."""
    report_dir = os.path.join(_AUTOMATION_DIR, "reports")
    if not os.path.isdir(report_dir):
        return None
    files = [f for f in os.listdir(report_dir) if f.endswith(".json")]
    if not files:
        return None
    latest = max(files, key=lambda f: os.path.getmtime(os.path.join(report_dir, f)))
    try:
        with open(os.path.join(report_dir, latest), "r", encoding="utf-8") as fh:
            data = json.load(fh)
        data["_file"] = latest
        return data
    except (OSError, json.JSONDecodeError):
        return None
