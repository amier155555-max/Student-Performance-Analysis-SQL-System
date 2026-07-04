"""
app.py
------
Flask application entry point for the Student Performance Analysis GUI.

Routes
------
GET  /                 Landing page - upload the raw file from the client
POST /upload            Handle the upload, run the cleaning pipeline, load DB
GET  /preview            Before/after cleaning report + sample of cleaned rows
GET  /dashboard          Hypothesis-testing analytics
GET  /settings           View current settings
POST /settings           Save updated settings
POST /settings/reset      Restore default settings
POST /database/reset      Wipe the SQLite database
GET  /download/<kind>     Download the cleaned CSV or a SQL export
GET  /health              Simple health check (useful for deployment/monitoring)
"""

from __future__ import annotations

import io
import os
import sqlite3
import time
import uuid
from datetime import datetime

from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, send_file, jsonify, session,
)
from werkzeug.utils import secure_filename

import config
from modules import (
    activity_log, analytics, db_manager, deployment, report_builder, schema_mapper,
)
from modules.data_cleaner import DataCleaner, UnsupportedFileError, load_raw_file

app = Flask(__name__)
app.secret_key = os.environ.get("SPA_SECRET_KEY", "dev-key-change-in-production")
app.config["MAX_CONTENT_LENGTH"] = config.MAX_CONTENT_LENGTH_MB * 1024 * 1024

config.ensure_dirs()


def _allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in config.ALLOWED_EXTENSIONS


@app.context_processor
def inject_globals():
    settings = config.load_settings()
    return {"app_name": settings.get("app_name", "Student Performance Analysis System"),
             "current_year": datetime.now().year,
             "max_upload_mb": config.MAX_CONTENT_LENGTH_MB}


# ----------------------------------------------------------------------
# Landing page / upload
# ----------------------------------------------------------------------
@app.route("/")
def index():
    settings = config.load_settings()
    tables = db_manager.list_tables(settings["database_path"])
    has_data = "cleaned_data" in tables
    return render_template("upload.html", has_data=has_data)


@app.route("/upload", methods=["POST"])
def upload():
    settings = config.load_settings()

    if "raw_file" not in request.files or request.files["raw_file"].filename == "":
        flash("Please choose a file before uploading.", "error")
        return redirect(url_for("index"))

    file = request.files["raw_file"]
    if not _allowed_file(file.filename):
        flash(
            f"Unsupported file type. Allowed types: {', '.join(sorted(config.ALLOWED_EXTENSIONS))}.",
            "error",
        )
        return redirect(url_for("index"))

    filename = secure_filename(file.filename)
    unique_name = f"{int(time.time())}_{uuid.uuid4().hex[:8]}_{filename}"
    save_path = os.path.join(config.UPLOAD_DIR, unique_name)

    try:
        file.save(save_path)
        raw_df = load_raw_file(save_path)

        if raw_df.empty:
            flash("The uploaded file has no rows to process.", "error")
            return redirect(url_for("index"))

        cleaner = DataCleaner(settings)
        cleaned_df, report = cleaner.run(raw_df)

        # Persist the cleaned flat table (works for ANY dataset)
        db_manager.write_dataframe(settings["database_path"], "cleaned_data", cleaned_df)

        # Always clear any normalized tables left over from a previous upload,
        # so the dashboard never shows stale analytics for a newly uploaded file.
        db_manager.drop_tables(settings["database_path"], db_manager.NORMALIZED_TABLES)

        # Best-effort: also populate the normalized education schema
        normalized_written = {}
        mapping = schema_mapper.detect_education_schema(cleaned_df)
        if mapping and settings.get("auto_populate_normalized_schema", True):
            tables = schema_mapper.build_normalized_tables(cleaned_df, mapping)
            normalized_written = db_manager.write_normalized_tables(settings["database_path"], tables)

        # Save the cleaned CSV to disk for download
        cleaned_csv_path = os.path.join(config.CLEANED_DIR, f"cleaned_{filename.rsplit('.', 1)[0]}.csv")
        cleaned_df.to_csv(cleaned_csv_path, index=False)

        session["last_report"] = report.to_dict()
        session["last_filename"] = filename
        session["last_cleaned_csv"] = cleaned_csv_path
        session["schema_matched"] = bool(mapping)
        session["normalized_written"] = normalized_written

        rep = report.to_dict()
        activity_log.log_event(
            "upload", f"Uploaded and cleaned '{filename}'.", "success",
            rows_in=rep["original_rows"], rows_out=rep["final_rows"],
            duplicates_removed=rep["duplicate_rows_removed"],
            empty_rows_removed=rep["empty_rows_removed"],
            schema_matched=bool(mapping),
        )
        flash(f"'{filename}' was cleaned and loaded successfully.", "success")
        return redirect(url_for("preview"))

    except UnsupportedFileError as exc:
        activity_log.log_event("upload", f"Rejected file: {exc}", "error")
        flash(str(exc), "error")
        return redirect(url_for("index"))
    except db_manager.DatabaseError as exc:
        activity_log.log_event("upload", f"Database error: {exc}", "error")
        flash(f"Database error: {exc}", "error")
        return redirect(url_for("index"))
    except Exception as exc:  # noqa: BLE001 - last line of defense for the user
        activity_log.log_event("upload", f"Unexpected error: {exc}", "error")
        flash(f"Unexpected error while processing the file: {exc}", "error")
        return redirect(url_for("index"))


# ----------------------------------------------------------------------
# Preview
# ----------------------------------------------------------------------
@app.route("/preview")
def preview():
    settings = config.load_settings()
    report = session.get("last_report")
    if not report:
        flash("Upload a file first to see its cleaning report.", "error")
        return redirect(url_for("index"))

    sample_rows = []
    columns = []
    try:
        n = settings.get("records_per_preview_page", 15)
        df = db_manager.run_query(settings["database_path"], f'SELECT * FROM "cleaned_data" LIMIT {int(n)};')
        columns = list(df.columns)
        sample_rows = df.to_dict(orient="records")
    except db_manager.DatabaseError as exc:
        flash(f"Could not load preview rows: {exc}", "error")

    return render_template(
        "preview.html",
        report=report,
        filename=session.get("last_filename"),
        columns=columns,
        rows=sample_rows,
        schema_matched=session.get("schema_matched", False),
        normalized_written=session.get("normalized_written", {}),
    )


# ----------------------------------------------------------------------
# Dashboard (hypothesis-testing queries)
# ----------------------------------------------------------------------
@app.route("/dashboard")
def dashboard():
    settings = config.load_settings()
    db_path = settings["database_path"]
    tables = db_manager.list_tables(db_path)

    if not tables:
        flash("No data loaded yet. Upload a file to see analytics.", "error")
        return redirect(url_for("index"))

    schema_ready = "student" in tables and "grade" in tables
    kpis = analytics.summary_stats(db_path) if schema_ready else None
    results = analytics.run_all(db_path) if schema_ready else []
    profile = analytics.generic_profile(db_path) if not schema_ready else None

    return render_template(
        "dashboard.html",
        schema_ready=schema_ready,
        kpis=kpis,
        results=results,
        profile=profile,
    )


# ----------------------------------------------------------------------
# Settings (project configuration)
# ----------------------------------------------------------------------
@app.route("/settings", methods=["GET"])
def settings_page():
    current = config.load_settings()
    db_path = current["database_path"]
    db_size_kb = round(os.path.getsize(db_path) / 1024, 1) if os.path.exists(db_path) else 0
    return render_template("settings.html", settings=current, db_size_kb=db_size_kb,
                            defaults=config.DEFAULT_SETTINGS)


@app.route("/settings", methods=["POST"])
def settings_save():
    form = request.form
    new_settings = {
        "app_name": form.get("app_name", "Student Performance Analysis System").strip()[:80],
        "missing_strategy": form.get("missing_strategy", "auto"),
        "missing_threshold_pct": _safe_int(form.get("missing_threshold_pct"), 60, 0, 100),
        "remove_duplicates": form.get("remove_duplicates") == "on",
        "trim_whitespace": form.get("trim_whitespace") == "on",
        "standardize_column_names": form.get("standardize_column_names") == "on",
        "outlier_handling": form.get("outlier_handling", "cap_iqr"),
        "outlier_iqr_multiplier": _safe_float(form.get("outlier_iqr_multiplier"), 1.5, 0.5, 5.0),
        "coerce_numeric_types": form.get("coerce_numeric_types") == "on",
        "auto_populate_normalized_schema": form.get("auto_populate_normalized_schema") == "on",
        "records_per_preview_page": _safe_int(form.get("records_per_preview_page"), 15, 1, 1_000_000),
    }
    config.save_settings(new_settings)
    activity_log.log_event("settings", "Settings updated.", "info",
                            preview_rows=new_settings["records_per_preview_page"],
                            missing_strategy=new_settings["missing_strategy"])
    flash("Settings saved.", "success")
    return redirect(url_for("settings_page"))


@app.route("/settings/reset", methods=["POST"])
def settings_reset():
    config.reset_settings()
    flash("Settings restored to defaults.", "success")
    return redirect(url_for("settings_page"))


@app.route("/database/reset", methods=["POST"])
def database_reset():
    settings = config.load_settings()
    db_manager.reset_database(settings["database_path"])
    session.clear()
    activity_log.log_event("database", "Database cleared.", "warning")
    flash("Database cleared. Upload a new file to start again.", "success")
    return redirect(url_for("index"))


def _safe_int(value, default, lo, hi):
    try:
        v = int(value)
        return max(lo, min(hi, v))
    except (TypeError, ValueError):
        return default


def _safe_float(value, default, lo, hi):
    try:
        v = float(value)
        return max(lo, min(hi, v))
    except (TypeError, ValueError):
        return default


# ----------------------------------------------------------------------
# Downloads
# ----------------------------------------------------------------------
@app.route("/download/csv")
def download_csv():
    path = session.get("last_cleaned_csv")
    if not path or not os.path.exists(path):
        flash("No cleaned file available yet.", "error")
        return redirect(url_for("index"))
    return send_file(path, as_attachment=True, download_name=os.path.basename(path))


@app.route("/download/sql")
def download_sql():
    settings = config.load_settings()
    db_path = settings["database_path"]
    if not os.path.exists(db_path):
        flash("No database available yet.", "error")
        return redirect(url_for("index"))

    buffer = io.StringIO()
    conn = sqlite3.connect(db_path)
    try:
        for line in conn.iterdump():
            buffer.write(f"{line}\n")
    finally:
        conn.close()

    mem = io.BytesIO(buffer.getvalue().encode("utf-8"))
    mem.seek(0)
    return send_file(mem, as_attachment=True, download_name="student_performance_export.sql",
                      mimetype="text/plain")


@app.route("/download/documentation")
def download_documentation():
    """Generate and download the final documentation report (schema
    explanation + processing steps + data-driven insights with the SQL
    that proves each one), built live from the current DB.

    Served as a PDF; if the PDF libraries/fonts are unavailable, it falls
    back to the Markdown version so the button always works."""
    settings = config.load_settings()
    db_path = settings["database_path"]
    if not os.path.exists(db_path):
        flash("No database available yet. Upload a file first.", "error")
        return redirect(url_for("index"))

    markdown_text = report_builder.build_documentation(db_path)

    try:
        from modules import pdf_report
        pdf_bytes = pdf_report.markdown_to_pdf(markdown_text)
        mem = io.BytesIO(pdf_bytes)
        mem.seek(0)
        activity_log.log_event("report", "Downloaded final documentation report (PDF).", "info")
        return send_file(
            mem,
            as_attachment=True,
            download_name="Final_Documentation_Report.pdf",
            mimetype="application/pdf",
        )
    except Exception as exc:  # noqa: BLE001 - fall back to Markdown on any PDF error
        app.logger.warning("PDF generation failed, serving Markdown instead: %s", exc)
        mem = io.BytesIO(markdown_text.encode("utf-8"))
        mem.seek(0)
        return send_file(
            mem,
            as_attachment=True,
            download_name="Final_Documentation_Report.md",
            mimetype="text/markdown",
        )


# ----------------------------------------------------------------------
# Deployment & Automation (stored procedures; nightly / batch automation)
# ----------------------------------------------------------------------
@app.route("/deployment")
def deployment_page():
    settings = config.load_settings()
    db_path = settings["database_path"]
    schema_ready = "student" in db_manager.list_tables(db_path) and \
                   "grade" in db_manager.list_tables(db_path)
    return render_template(
        "deployment.html",
        schema_ready=schema_ready,
        run_log=deployment.run_log(db_path),
        latest_results=deployment.latest_results(db_path),
        last_batch=deployment.last_batch_report(),
    )


def _student_schema_ready(db_path):
    tables = db_manager.list_tables(db_path)
    return "student" in tables and "grade" in tables


@app.route("/deployment/run-procedures", methods=["POST"])
def deployment_run_procedures():
    settings = config.load_settings()
    db_path = settings["database_path"]
    if not _student_schema_ready(db_path):
        flash("Upload a student-performance file first — the analysis needs the "
              "student/grade tables to run.", "error")
        return redirect(url_for("deployment_page"))
    summary = deployment.run_procedures(db_path)
    n_ok, n_failed = len(summary["ok"]), len(summary["failed"])
    activity_log.log_event(
        "procedures", "Ran stored-procedure analysis.",
        "success" if not n_failed else "warning", succeeded=n_ok, failed=n_failed,
    )
    flash(f"Stored-procedure analysis complete: {n_ok} succeeded, {n_failed} failed.",
          "success" if not n_failed else "error")
    return redirect(url_for("deployment_page"))


@app.route("/deployment/run-batch", methods=["POST"])
def deployment_run_batch():
    settings = config.load_settings()
    db_path = settings["database_path"]
    if not _student_schema_ready(db_path):
        flash("Upload a student-performance file first — the batch analysis needs "
              "the student/grade tables to run.", "error")
        return redirect(url_for("deployment_page"))
    result = deployment.run_batch(db_path)
    n_ok, n_failed = len(result["ok"]), len(result["failed"])
    activity_log.log_event(
        "batch", "Ran nightly batch analysis on demand.",
        "success" if not n_failed else "warning",
        succeeded=n_ok, failed=n_failed, duration_s=result["duration_s"],
    )
    flash(f"Batch job finished in {result['duration_s']}s: {n_ok} succeeded, "
          f"{n_failed} failed. Report written to /reports.",
          "success" if not n_failed else "error")
    return redirect(url_for("deployment_page"))


# ----------------------------------------------------------------------
# Activity log (monitoring / auditability)
# ----------------------------------------------------------------------
@app.route("/logs")
def logs():
    events = activity_log.read_events(limit=300)
    return render_template("logs.html", events=events)


@app.route("/logs/clear", methods=["POST"])
def logs_clear():
    activity_log.clear()
    activity_log.log_event("logs", "Activity log cleared.", "warning")
    flash("Activity log cleared.", "success")
    return redirect(url_for("logs"))


# ----------------------------------------------------------------------
@app.route("/health")
def health():
    return jsonify(status="ok", time=datetime.utcnow().isoformat())


@app.errorhandler(413)
def too_large(_e):
    flash(f"File is too large. Maximum size is {config.MAX_CONTENT_LENGTH_MB} MB.", "error")
    return redirect(url_for("index"))


@app.errorhandler(404)
def not_found(_e):
    return render_template("404.html"), 404


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
