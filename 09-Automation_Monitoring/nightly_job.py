"""
nightly_job.py
----------------
Milestone 4: MLOps / Monitoring / Automation - "Automate nightly query runs".

Runs the full hypothesis-testing analysis (Milestone 3's
sp_run_all_analyses equivalent) end to end, writes a timestamped report,
and exits non-zero on failure so any scheduler (cron, systemd timer,
Windows Task Scheduler, GitHub Actions) can alert on failed runs.

Usage:
    python nightly_job.py --db path/to/spa.sqlite3

Exit codes:
    0  all analyses succeeded
    1  one or more analyses failed (see logs/nightly_job.log)
    2  could not open the database at all
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "08-Deployment_Stored_Procedures"))
from sqlite_equivalent import run_all_analyses, latest_results  # noqa: E402

LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
REPORT_DIR = os.path.join(os.path.dirname(__file__), "reports")


def _setup_logging() -> logging.Logger:
    os.makedirs(LOG_DIR, exist_ok=True)
    logger = logging.getLogger("nightly_job")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    fh = logging.FileHandler(os.path.join(LOG_DIR, "nightly_job.log"))
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(fh)

    sh = logging.StreamHandler()
    sh.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(sh)
    return logger


def main() -> int:
    parser = argparse.ArgumentParser(description="Run nightly student-performance analysis batch.")
    parser.add_argument(
        "--db",
        default=os.path.join(os.path.dirname(__file__), "..", "07-Implementation_Source_Code", "spa", "data", "db", "spa.sqlite3"),
        help="Path to the SQLite database populated by the GUI.",
    )
    args = parser.parse_args()

    logger = _setup_logging()
    started = dt.datetime.now(dt.timezone.utc)
    logger.info("Nightly analysis run starting for db=%s", args.db)

    if not os.path.exists(args.db):
        logger.error("Database not found at %s. Has the GUI ingested any data yet?", args.db)
        return 2

    try:
        summary = run_all_analyses(args.db)
    except Exception:
        logger.exception("Nightly job crashed before completing.")
        return 2

    ok, failed = summary["ok"], summary["failed"]
    for item in ok:
        logger.info("SUCCESS  %-30s rows=%s", item["procedure"], item["rows"])
    for item in failed:
        logger.error("FAILED   %-30s %s", item["procedure"], item["error"])

    # Write a timestamped JSON report snapshot for monitoring dashboards / alerting hooks.
    os.makedirs(REPORT_DIR, exist_ok=True)
    report_path = os.path.join(REPORT_DIR, f"report_{started.strftime('%Y%m%d_%H%M%S')}.json")
    with open(report_path, "w") as fh:
        json.dump(
            {
                "started_at": started.isoformat(),
                "finished_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                "database": args.db,
                "succeeded": ok,
                "failed": failed,
                "latest_results_sample": latest_results(args.db)[:10],
            },
            fh,
            indent=2,
        )
    logger.info("Report written to %s", report_path)

    duration = (dt.datetime.now(dt.timezone.utc) - started).total_seconds()
    logger.info("Nightly run finished in %.2fs (%d succeeded, %d failed)", duration, len(ok), len(failed))

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
