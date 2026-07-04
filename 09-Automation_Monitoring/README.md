# Milestone 4 — MLOps / Monitoring / Automation

## Goal
Automate nightly query runs against the student-performance database so
insights stay fresh without a human re-running queries by hand, and make
failures visible instead of silent.

## Components

| File | Role |
|---|---|
| `nightly_job.py` | Batch entry point. Runs every hypothesis test (Milestone 3), logs progress, writes a JSON report snapshot, and returns a non-zero exit code on failure. |
| `logs/nightly_job.log` | Rolling text log (created on first run). One line per procedure per run. |
| `reports/report_<timestamp>.json` | Machine-readable snapshot of each run: what succeeded, what failed, and a sample of the latest results — for a monitoring dashboard or alerting hook to consume. |
| `crontab.txt` | Example cron schedule for Linux/macOS. |
| `nightly-analysis.service` / `nightly-analysis.timer` | Example systemd timer unit (recommended over cron on modern Linux servers — gives built-in logging via `journalctl` and retry/monitoring hooks). |

## Running manually
```bash
cd 09-Automation_Monitoring
python nightly_job.py --db ../07-Implementation_Source_Code/spa/data/db/spa.sqlite3
```

## Scheduling (pick one)

### Option A — cron (Linux/macOS)
```
# crontab.txt — runs every night at 02:00 server time
0 2 * * * cd /opt/student-performance/09-Automation_Monitoring && /usr/bin/python3 nightly_job.py >> logs/cron_stdout.log 2>&1
```
Install with `crontab crontab.txt`.

### Option B — systemd timer (recommended for production Linux)
See `nightly-analysis.service` and `nightly-analysis.timer`. Install with:
```bash
sudo cp nightly-analysis.service nightly-analysis.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now nightly-analysis.timer
```
Check status / logs:
```bash
systemctl list-timers nightly-analysis.timer
journalctl -u nightly-analysis.service
```

### Option C — CI/CD scheduled workflow (e.g., GitHub Actions)
If the database is reachable from a CI runner (e.g., a managed
PostgreSQL instance), the same script can be triggered by a
`schedule:` cron trigger in a workflow file, reusing the repository's
existing CI/CD pipeline (see `01-Planning_and_Management` for the
branching/CI strategy) instead of a separate server.

## Monitoring & alerting
- **Exit code**: `0` success, `1` one or more procedures failed, `2` job
  could not start (e.g. missing database). Wire this into your
  scheduler's built-in failure notifications (cron mail, systemd
  `OnFailure=`, or a CI job's "failed" status).
- **`analysis_run_log` table** (written by the stored procedures /
  `sqlite_equivalent.py`): query it directly for a full audit trail —
  start time, end time, row count, and error message per run.
- **JSON reports**: point a dashboard (or a simple cron that emails the
  latest `reports/report_*.json` diff) at the `reports/` folder for a
  lightweight monitoring view without extra infrastructure.

## Extending
- Add a `--notify-webhook` flag to `nightly_job.py` to POST the JSON
  report to Slack/Teams/email on failure.
- Add a retention job to prune `reports/*.json` older than N days.
- For real-time (not just nightly) freshness, the Flask GUI already
  re-runs the same analytics on every dashboard page load — this batch
  job is specifically for keeping a persisted, auditable historical
  record even when nobody opens the GUI.
