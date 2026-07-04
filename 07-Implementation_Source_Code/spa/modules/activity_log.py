"""
modules/activity_log.py
------------------------
Lightweight activity / audit log for the GUI.

Every meaningful action (upload, cleaning result, analysis view, report
download, database reset, settings change) is appended as one JSON line to
`data/activity_log.jsonl`. The `/logs` page reads them back, newest first.

Kept dependency-free and defensive: logging must never crash a request, so
every function swallows its own I/O errors.
"""

from __future__ import annotations

import json
import os
from datetime import datetime

import config

LOG_PATH = os.path.join(config.BASE_DIR, "data", "activity_log.jsonl")

# Recognized levels -> used only for colour-coding in the UI.
LEVELS = {"info", "success", "warning", "error"}


def log_event(event: str, message: str, level: str = "info", **details) -> None:
    """Append one event to the activity log. Never raises."""
    try:
        config.ensure_dirs()
        record = {
            "time": datetime.now().isoformat(timespec="seconds"),
            "level": level if level in LEVELS else "info",
            "event": event,
            "message": message,
        }
        if details:
            record["details"] = details
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001 - logging must never break a request
        pass


def read_events(limit: int = 200) -> list[dict]:
    """Return the most recent events, newest first."""
    if not os.path.exists(LOG_PATH):
        return []
    try:
        with open(LOG_PATH, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
    except OSError:
        return []
    events = []
    for line in lines[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    events.reverse()
    return events


def clear() -> None:
    """Erase the activity log (used by the Clear button on /logs)."""
    try:
        if os.path.exists(LOG_PATH):
            os.remove(LOG_PATH)
    except OSError:
        pass
